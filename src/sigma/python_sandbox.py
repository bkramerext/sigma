"""Bounded Docker adapter for untrusted, generated research Python."""

from __future__ import annotations

import asyncio
import base64
import fcntl
import hashlib
import json
import mimetypes
import os
import secrets
import selectors
import signal
import subprocess
import tarfile
import tempfile
import threading
import time
from dataclasses import dataclass
from datetime import UTC, datetime
from io import BytesIO
from pathlib import Path
from typing import Any, Literal
from uuid import UUID, uuid4

from sigma.projects import ProjectError, _stage, inspect_project, project_path

IMAGE = "sigma-research-python:0.1"
CONTAINER_RUNTIME = "docker"
MAX_SOURCE_BYTES = 16_000
MAX_OUTPUT_BYTES = 32_000
EXECUTION_TIMEOUT_SECONDS = 15
MAX_STORAGE_BYTES = 16_000_000
# JSON escapes control bytes by up to 6x. Source/output caps must still be
# persistable, including optional base64 for non-UTF-8 output and file metadata.
MAX_ARTIFACT_BYTES = 384_000
MAX_CAPTURED_ARTIFACT_BYTES = 4_000_000
MAX_CAPTURED_ARTIFACTS = 8
MAX_CAPTURE_ARCHIVE_BYTES = 16 * 1024 * 1024
_EXECUTION_GATE = threading.BoundedSemaphore(1)


RuntimeName = Literal["python", "sagemath"]
SAGE_IMAGE = "sigma-research-sage:10.8"
SAGE_TIMEOUT_SECONDS = 60


def _runtime_environment() -> dict[str, str]:
    """Keep subprocess env sparse while allowing one operator-selected Unix daemon."""
    environment = {"PATH": os.environ.get("PATH", "/usr/bin:/bin")}
    configured_host = os.environ.get("SIGMA_RESEARCH_DOCKER_HOST", "").strip()
    if configured_host:
        if not configured_host.startswith("unix:///") or any(
            ord(character) < 32 for character in configured_host
        ):
            raise ProjectError("Research runtime must use a local Unix Docker socket.")
        environment["DOCKER_HOST"] = configured_host
    return environment


def runtime_settings(runtime_name: str = "python") -> dict[str, Any]:
    if runtime_name not in {"python", "sagemath"}:
        raise ProjectError("Unknown research runtime")
    sage = runtime_name == "sagemath"
    return {
        "runtime": runtime_name,
        "image": SAGE_IMAGE if sage else IMAGE,
        "version": "10.8" if sage else "3.12.8",
        "syntax": "sage-preparsed" if sage else "python",
        "wall_seconds": SAGE_TIMEOUT_SECONDS if sage else EXECUTION_TIMEOUT_SECONDS,
        "memory_mib": 1024 if sage else 512,
        "tmp_mib": 128 if sage else 64,
    }


@dataclass(frozen=True)
class ExecutionResult:
    status: str
    exit_code: int | None
    stdout: str
    stderr: str
    duration_ms: int
    image_id: str | None = None
    artifacts: tuple[tuple[str, str, bytes], ...] = ()
    artifact_error: str | None = None
    stdout_base64: str | None = None
    stderr_base64: str | None = None
    runtime: str = "python"


def docker_command(
    cidfile: str | None = None, image: str | None = None, runtime_name: str = "python"
) -> list[str]:
    """Return fixed container arguments; user values never enter command tokens."""
    settings = runtime_settings(runtime_name)
    command = [
        CONTAINER_RUNTIME,
        "run",
        "--rm",
        "--interactive",
        "--pull=never",
        "--network=none",
        f"--memory={settings['memory_mib']}m",
        f"--memory-swap={settings['memory_mib']}m",
        "--cpus=1",
        "--pids-limit=64",
        "--read-only",
        f"--tmpfs=/tmp:rw,noexec,nosuid,size={settings['tmp_mib']}m",
        "--tmpfs=/artifacts:rw,noexec,nosuid,size=16m",
        "--user=65532:65532",
        "--cap-drop=ALL",
        "--security-opt=no-new-privileges",
        "--env=MPLCONFIGDIR=/tmp/matplotlib",
    ]
    if runtime_name == "sagemath":
        command.extend(["--platform=linux/amd64", "--env=HOME=/tmp"])
    if cidfile:
        command.append(f"--cidfile={cidfile}")
    command.append(image or settings["image"])
    return command


def _capture_artifacts(
    container_id: str, timeout_seconds: float = 5
) -> tuple[tuple[str, str, bytes], ...]:
    try:
        process = subprocess.Popen(
            [CONTAINER_RUNTIME, "exec", container_id, "tar", "-C", "/artifacts", "-cf", "-", "."],
            stdout=subprocess.PIPE,
            stderr=subprocess.DEVNULL,
            env=_runtime_environment(),
        )
    except OSError as exc:
        raise ProjectError("Could not capture research output files") from exc
    assert process.stdout
    selector = selectors.DefaultSelector()
    selector.register(process.stdout, selectors.EVENT_READ)
    archive_chunks = bytearray()
    deadline = time.monotonic() + timeout_seconds
    try:
        while selector.get_map():
            remaining = deadline - time.monotonic()
            if remaining <= 0:
                raise ProjectError("Could not capture research output files")
            if not selector.select(remaining):
                continue
            chunk = os.read(process.stdout.fileno(), 64 * 1024)
            if not chunk:
                selector.unregister(process.stdout)
                continue
            if len(archive_chunks) + len(chunk) > MAX_CAPTURE_ARCHIVE_BYTES:
                raise ProjectError("Research output files exceeded their combined size limit")
            archive_chunks.extend(chunk)
        if process.wait(timeout=max(0.01, deadline - time.monotonic())) != 0:
            raise ProjectError("Could not capture research output files")
    except (OSError, subprocess.TimeoutExpired) as exc:
        raise ProjectError("Could not capture research output files") from exc
    finally:
        selector.close()
        process.stdout.close()
        if process.poll() is None:
            process.kill()
            process.wait()
    archive_bytes = bytes(archive_chunks)
    if not archive_bytes:
        return ()
    captured: list[tuple[str, str, bytes]] = []
    total = 0
    try:
        with tarfile.open(fileobj=BytesIO(archive_bytes), mode="r:") as archive:
            for member in archive:
                filename = member.name.removeprefix("./")
                try:
                    filename.encode("utf-8")
                except UnicodeEncodeError as exc:
                    raise ProjectError("Research output filenames must be valid UTF-8") from exc
                if member.isdir() and filename in {"", "."}:
                    continue
                if (
                    len(captured) >= MAX_CAPTURED_ARTIFACTS
                    or not filename
                    or filename in {".", ".."}
                    or "/" in filename
                    or "\\" in filename
                    or not member.isfile()
                    or any(item[0] == filename for item in captured)
                    or member.size > MAX_CAPTURED_ARTIFACT_BYTES
                ):
                    raise ProjectError(
                        "Research output files must be small regular files with simple names"
                    )
                stream = archive.extractfile(member)
                if stream is None:
                    raise ProjectError("Could not read a research output file")
                content = stream.read(MAX_CAPTURED_ARTIFACT_BYTES + 1)
                if len(content) != member.size:
                    raise ProjectError(
                        "Research output file size did not match its archive metadata"
                    )
                total += len(content)
                if total > MAX_CAPTURED_ARTIFACT_BYTES:
                    raise ProjectError("Research output files exceeded their combined size limit")
                captured.append(
                    (
                        filename,
                        mimetypes.guess_type(filename)[0] or "application/octet-stream",
                        content,
                    )
                )
    except (tarfile.TarError, OSError) as exc:
        raise ProjectError("Research output files were not a valid artifact archive") from exc
    return tuple(captured)


def _validate_source(source: str) -> bytes:
    if not isinstance(source, str):
        raise ProjectError("Research code must be text")
    try:
        encoded = source.encode("utf-8")
    except UnicodeEncodeError as exc:
        raise ProjectError("Research code must contain valid UTF-8 text") from exc
    if not encoded or len(encoded) > MAX_SOURCE_BYTES:
        raise ProjectError(f"Research code must be 1–{MAX_SOURCE_BYTES} UTF-8 bytes")
    return encoded


def _image_identity(runtime_name: str = "python") -> str | None:
    runtime = CONTAINER_RUNTIME
    try:
        result = subprocess.run(
            [
                runtime,
                "image",
                "inspect",
                "--format={{.Id}}",
                runtime_settings(runtime_name)["image"],
            ],
            capture_output=True,
            timeout=3,
            check=False,
            env=_runtime_environment(),
        )
    except (OSError, subprocess.TimeoutExpired):
        return None
    image_id = result.stdout.decode("ascii", errors="ignore").strip()
    if result.returncode or len(image_id) != 71 or not image_id.startswith("sha256:"):
        return None
    if any(character not in "0123456789abcdef" for character in image_id[7:]):
        return None
    return image_id


def research_tool_capabilities() -> dict[str, Any]:
    """Return the bounded computation tools SIGMA can actually dispatch now."""
    image_id = _image_identity()
    return {
        "python": {
            "available": image_id is not None,
            "image": IMAGE if image_id is not None else None,
        }
    }


def _run(
    source: str, image_id: str, runtime_name: str = "python"
) -> tuple[int | None, bytes, bytes, str, tuple[tuple[str, str, bytes], ...], str | None]:
    encoded = _validate_source(source)
    cid_fd, cid_name = tempfile.mkstemp(prefix="sigma-python-", suffix=".cid")
    os.close(cid_fd)
    cidfile = Path(cid_name)
    cidfile.unlink()
    runtime = CONTAINER_RUNTIME
    runner_token = secrets.token_hex(16)

    def kill_container() -> None:
        try:
            cid = cidfile.read_text(encoding="ascii").strip()
        except (OSError, UnicodeError):
            return
        if len(cid) != 64 or any(character not in "0123456789abcdef" for character in cid):
            return
        try:
            subprocess.run(
                [runtime, "kill", cid],
                capture_output=True,
                timeout=3,
                check=False,
                env=_runtime_environment(),
            )
        except (OSError, subprocess.TimeoutExpired):
            pass

    try:
        process = subprocess.Popen(
            docker_command(str(cidfile), image_id, runtime_name),
            stdin=subprocess.PIPE,
            stdout=subprocess.PIPE,
            stderr=subprocess.PIPE,
            bufsize=0,
            start_new_session=True,
            env=_runtime_environment(),
        )
    except OSError:
        cidfile.unlink(missing_ok=True)
        return None, b"", b"Container runtime could not start.", "unavailable", (), None
    assert process.stdin and process.stdout and process.stderr
    started = time.monotonic()
    pending_input = (
        str(len(encoded)).encode("ascii") + b"\n" + encoded + runner_token.encode("ascii") + b"\n"
    )
    selector = selectors.DefaultSelector()
    os.set_blocking(process.stdin.fileno(), False)
    selector.register(process.stdin, selectors.EVENT_WRITE, "stdin")
    selector.register(process.stdout, selectors.EVENT_READ, "stdout")
    selector.register(process.stderr, selectors.EVENT_READ, "stderr")
    chunks = {"stdout": bytearray(), "stderr": bytearray()}
    status = "completed"
    marker = b"\x1eSIGMA_DONE:" + runner_token.encode("ascii") + b"\x1f\n"
    pending_stdout = bytearray()
    marker_seen = False
    artifacts: tuple[tuple[str, str, bytes], ...] = ()
    artifact_error = None
    wall_seconds = runtime_settings(runtime_name)["wall_seconds"]
    deadline = started + wall_seconds

    def close_pipes() -> None:
        for key in list(selector.get_map().values()):
            selector.unregister(key.fileobj)
            close = getattr(key.fileobj, "close", None)
            if callable(close):
                close()

    def stop_container(reason: str) -> str:
        kill_container()
        try:
            os.killpg(process.pid, signal.SIGKILL)
        except (PermissionError, ProcessLookupError):
            try:
                process.kill()
            except ProcessLookupError:
                pass
        close_pipes()
        return reason

    while selector.get_map():
        remaining = deadline - time.monotonic()
        if remaining <= 0:
            status = stop_container("failed" if marker_seen else "timeout")
            if marker_seen:
                artifact_error = "Container runtime did not exit after artifact capture."
            break
        for key, _ in selector.select(min(0.1, remaining)):
            if key.data == "stdin":
                try:
                    written = os.write(key.fd, pending_input)
                    pending_input = pending_input[written:]
                except BlockingIOError:
                    continue
                except BrokenPipeError:
                    pending_input = b""
                if not pending_input:
                    selector.unregister(key.fileobj)
                continue
            chunk = os.read(key.fd, MAX_OUTPUT_BYTES + 1)
            eof = not chunk
            if not chunk:
                selector.unregister(key.fileobj)
                if key.data != "stdout" or not pending_stdout:
                    continue
            just_finished = False
            if key.data == "stdout":
                pending_stdout.extend(chunk)
                marker_at = pending_stdout.find(marker)
                if marker_at >= 0 and not marker_seen:
                    output_chunk = bytes(pending_stdout[:marker_at])
                    pending_stdout.clear()
                    marker_seen = True
                    just_finished = True
                elif eof:
                    output_chunk = bytes(pending_stdout)
                    pending_stdout.clear()
                else:
                    keep = min(len(marker) - 1, len(pending_stdout))
                    output_chunk = bytes(pending_stdout[:-keep] if keep else pending_stdout)
                    if keep:
                        del pending_stdout[:-keep]
                    else:
                        pending_stdout.clear()
                buffer = chunks["stdout"]
            else:
                output_chunk = chunk
                buffer = chunks["stderr"]
            room = MAX_OUTPUT_BYTES - sum(len(value) for value in chunks.values())
            buffer.extend(output_chunk[: max(0, room)])
            if len(output_chunk) > room and status == "completed":
                status = stop_container("output_limit")
                break
            if just_finished:
                try:
                    cid = cidfile.read_text(encoding="ascii").strip()
                    artifacts = _capture_artifacts(
                        cid, timeout_seconds=max(0.001, min(5, deadline - time.monotonic()))
                    )
                except (OSError, UnicodeError, ProjectError) as exc:
                    status = "failed"
                    message = (
                        str(exc)
                        if isinstance(exc, ProjectError)
                        else "Could not capture research output files."
                    )
                    artifact_error = message
                try:
                    process.stdin.close()
                except BrokenPipeError:
                    pass
                deadline = min(deadline, time.monotonic() + 3)
        if process.poll() is not None and not selector.get_map():
            break
    try:
        return_code = process.wait(timeout=max(0.01, deadline - time.monotonic()))
    except subprocess.TimeoutExpired:
        status = stop_container("failed" if marker_seen else "timeout")
        return_code = process.wait(timeout=3)
    selector.close()
    if status == "completed" and not marker_seen:
        status = "failed"
        artifact_error = "Container exited without the execution completion marker; output files were not captured."
    process.stdin.close()
    process.stdout.close()
    process.stderr.close()
    try:
        cid = cidfile.read_text(encoding="ascii").strip()
    except (OSError, UnicodeError):
        cid = ""
    if len(cid) == 64 and all(character in "0123456789abcdef" for character in cid):
        try:
            subprocess.run(
                [runtime, "rm", "--force", cid],
                capture_output=True,
                timeout=3,
                check=False,
                env=_runtime_environment(),
            )
        except (OSError, subprocess.TimeoutExpired):
            pass
    cidfile.unlink(missing_ok=True)
    diagnostic = b""
    if status == "timeout":
        diagnostic = f"\nExecution exceeded the {wall_seconds}-second wall limit.".encode()
        return_code = 124
    elif status == "output_limit":
        diagnostic = b"\nExecution exceeded the 32,000-byte output limit."
        return_code = 125
    if diagnostic:
        room = MAX_OUTPUT_BYTES - len(diagnostic)
        stdout = chunks["stdout"][:room]
        stderr = chunks["stderr"][: max(0, room - len(stdout))]
        stderr.extend(diagnostic)
    else:
        stdout, stderr = chunks["stdout"], chunks["stderr"]
    return return_code, bytes(stdout), bytes(stderr), status, artifacts, artifact_error


def _execute(source: str, runtime_name: str = "python") -> ExecutionResult:
    _validate_source(source)
    runtime_settings(runtime_name)
    image_id = _image_identity(runtime_name)
    if image_id is None:
        return ExecutionResult(
            "unavailable",
            None,
            f"Research runtime {runtime_name} unavailable. Run ./sigma sandbox-build --runtime {runtime_name}.",
            "",
            0,
            runtime=runtime_name,
        )
    started = time.monotonic()
    return_code, stdout, stderr, status, artifacts, artifact_error = (
        _run(source, image_id) if runtime_name == "python" else _run(source, image_id, runtime_name)
    )
    duration = round((time.monotonic() - started) * 1000)
    if status == "unavailable":
        return ExecutionResult(
            status, None, "", stderr.decode("utf-8"), duration, image_id, runtime=runtime_name
        )
    if status == "completed" and return_code != 0:
        status = "failed"
    return ExecutionResult(
        status,
        return_code,
        stdout.decode("utf-8", errors="replace"),
        stderr.decode("utf-8", errors="replace"),
        duration,
        image_id,
        artifacts,
        artifact_error,
        _non_utf8_base64(stdout),
        _non_utf8_base64(stderr),
        runtime=runtime_name,
    )


def _non_utf8_base64(value: bytes) -> str | None:
    try:
        value.decode("utf-8")
    except UnicodeDecodeError:
        return base64.b64encode(value).decode("ascii")
    return None


def _execute_admitted(source: str, runtime_name: str = "python") -> ExecutionResult:
    if not _EXECUTION_GATE.acquire(blocking=False):
        return ExecutionResult(
            "busy", None, "Another research code run is active.", "", 0, runtime=runtime_name
        )
    try:
        return _execute(source) if runtime_name == "python" else _execute(source, runtime_name)
    finally:
        _EXECUTION_GATE.release()


def _execution_directory(path: str | Path) -> Path:
    inspect_project(path)
    target = project_path(path)
    samples = (Path(__file__).resolve().parents[2] / "samples").resolve()
    if target.is_relative_to(samples):
        raise ProjectError("Research executions cannot be stored in sample projects")
    if target.suffix == ".json":
        # Runtime liveness locks are transient sidecars; execution records and
        # captured output bytes themselves are authoritative bundle members.
        directory = target.with_name("." + target.name + ".runtime")
        if directory.is_symlink():
            raise ProjectError("Research execution runtime directory is unsafe")
        try:
            directory.mkdir(mode=0o700, exist_ok=True)
            os.chmod(directory, 0o700)
        except OSError as exc:
            raise ProjectError("Research execution runtime storage is unavailable") from exc
        return directory
    directory = target / "research-executions"
    if directory.is_symlink():
        raise ProjectError("Research execution directory must not be a symbolic link")
    try:
        directory.mkdir(mode=0o700, exist_ok=True)
        os.chmod(directory, 0o700)
    except OSError as exc:
        raise ProjectError("Research execution storage is unavailable") from exc
    return directory


def _execution_bundle_path(directory: Path) -> Path | None:
    name = directory.name
    if not (name.startswith(".") and name.endswith(".json.runtime")):
        return None
    candidate = directory.with_name(name[1:-len(".runtime")])
    return candidate if candidate.suffix == ".json" else None


def _bundle_execution_member(identifier: str) -> str:
    return f"research-executions/{identifier}.json"


def _metadata_id(value: str | None, label: str) -> str | None:
    if value is None:
        return None
    try:
        return str(UUID(value))
    except (ValueError, TypeError) as exc:
        raise ProjectError(f"Invalid {label} identifier") from exc


def _save_record(
    directory: Path,
    record: dict[str, Any],
    artifacts: tuple[tuple[str, str, bytes], ...] = (),
    *,
    finalizing: bool = False,
) -> None:
    encoded = (json.dumps(record, ensure_ascii=False, separators=(",", ":")) + "\n").encode()
    if len(encoded) > MAX_ARTIFACT_BYTES:
        raise ProjectError("Research execution artifact exceeded its storage limit")
    bundle_path = _execution_bundle_path(directory)
    if bundle_path is not None:
        from sigma.project_bundle import BundleError, transform_members

        identifier = _metadata_id(str(record.get("id", "")), "execution")
        assert identifier
        if record.get("id") != identifier:
            raise ProjectError("Research execution identifier must be canonical")
        if record.get("project_id") != inspect_project(bundle_path).project.id:
            raise ProjectError("Research execution does not belong to this project")
        filenames = [filename for filename, _, _ in artifacts]
        if len(filenames) != len(set(filenames)):
            raise ProjectError("Research output artifact filenames must be unique")
        member = _bundle_execution_member(identifier)

        def update(members: dict[str, bytes]) -> dict[str, bytes | None]:
            if not isinstance(members.get("project.json"), bytes):
                raise ProjectError("Project document is missing from execution bundle")
            if not finalizing and record.get("session_id") is not None:
                for name, data in members.items():
                    if not name.startswith("research-executions/") or not name.endswith(".json"):
                        continue
                    try:
                        prior = json.loads(data)
                    except (ValueError, UnicodeDecodeError):
                        continue
                    if (isinstance(prior, dict)
                        and prior.get("runtime", "python") == record.get("runtime", "python")
                        and all(prior.get(key) == record.get(key) for key in (
                            "project_id", "session_id", "strategy_id", "cycle", "source"
                        ))):
                        raise ProjectError(
                            "This research proposal is already reserved; no second run was started"
                        )
            previous = members.get(member)
            if finalizing:
                try:
                    reserved = json.loads(previous) if previous is not None else None
                except (ValueError, UnicodeDecodeError) as exc:
                    raise ProjectError("Research execution reservation is unreadable") from exc
                if (not isinstance(reserved, dict)
                    or reserved.get("status") != "running"
                    or reserved.get("runtime", "python") != record.get("runtime", "python")
                    or any(reserved.get(key) != record.get(key) for key in (
                        "id", "project_id", "session_id", "strategy_id", "cycle",
                        "source", "runtime_version", "syntax", "source_sha256", "agent"
                    ))):
                    raise ProjectError("Research execution reservation does not match the result")
            artifact_records = []
            changes: dict[str, bytes | None] = {}
            prefix = f"research-executions/{identifier}.artifacts/"
            for name in members:
                if name.startswith(prefix):
                    changes[name] = None
            for filename, media_type, content in artifacts:
                if (len(content) > MAX_CAPTURED_ARTIFACT_BYTES
                    or Path(filename).name != filename or filename in {".", ".."}):
                    raise ProjectError("Research output artifact is invalid")
                artifact_records.append({
                    "filename": filename, "media_type": media_type,
                    "size_bytes": len(content), "sha256": hashlib.sha256(content).hexdigest(),
                })
                changes[prefix + filename] = content
            record["artifacts"] = artifact_records
            encoded_record = (json.dumps(record, ensure_ascii=False, separators=(",", ":")) + "\n").encode()
            if len(encoded_record) > MAX_ARTIFACT_BYTES:
                raise ProjectError("Research execution artifact exceeded its storage limit")
            changes[member] = encoded_record
            total = sum(len(value) for name, value in members.items() if name not in changes)
            total += sum(len(value) for value in changes.values() if value is not None)
            if total > MAX_STORAGE_BYTES:
                raise ProjectError("Research execution storage limit reached")
            return changes

        try:
            transform_members(bundle_path, update)
        except (BundleError, OSError, ValueError) as exc:
            if isinstance(exc, ProjectError):
                raise
            raise ProjectError("Could not store research execution in project bundle") from exc
        return
    try:
        fd = os.open(
            directory / ".lock", os.O_CREAT | os.O_RDWR | getattr(os, "O_NOFOLLOW", 0), 0o600
        )
        with os.fdopen(fd, "r+") as lock:
            fcntl.flock(lock, fcntl.LOCK_EX)
            if not finalizing and record.get("session_id") is not None:
                for candidate in directory.glob("*.json"):
                    if candidate.is_symlink() or candidate.stat().st_size > MAX_ARTIFACT_BYTES:
                        continue
                    try:
                        prior = json.loads(candidate.read_text(encoding="utf-8"))
                    except (OSError, ValueError):
                        continue
                    if (
                        isinstance(prior, dict)
                        and prior.get("runtime", "python") == record.get("runtime", "python")
                        and all(
                            prior.get(key) == record.get(key)
                            for key in (
                                "project_id",
                                "session_id",
                                "strategy_id",
                                "cycle",
                                "source",
                            )
                        )
                    ):
                        raise ProjectError(
                            "This research proposal is already reserved; no second run was started"
                        )
            target_record = directory / f"{record['id']}.json"
            previous = 0
            if finalizing:
                if target_record.is_symlink() or not target_record.is_file():
                    raise ProjectError("Research execution reservation is missing")
                previous = target_record.stat().st_size
                if previous > MAX_ARTIFACT_BYTES:
                    raise ProjectError("Research execution reservation is invalid")
                reserved = json.loads(target_record.read_text(encoding="utf-8"))
                if (
                    not isinstance(reserved, dict)
                    or reserved.get("status") != "running"
                    or reserved.get("runtime", "python") != record.get("runtime", "python")
                    or any(
                        reserved.get(key) != record.get(key)
                        for key in (
                            "id",
                            "project_id",
                            "session_id",
                            "strategy_id",
                            "cycle",
                            "source",
                            "runtime_version",
                            "syntax",
                            "source_sha256",
                            "agent",
                        )
                    )
                ):
                    raise ProjectError("Research execution reservation does not match the result")
            artifact_dir = directory / f"{record['id']}.artifacts"
            if artifact_dir.is_symlink():
                raise ProjectError("Research output directory must not be a symbolic link")
            artifact_dir.mkdir(mode=0o700, exist_ok=finalizing)
            artifact_records = []
            try:
                for filename, media_type, content in artifacts:
                    if (
                        len(content) > MAX_CAPTURED_ARTIFACT_BYTES
                        or Path(filename).name != filename
                        or filename in {".", ".."}
                    ):
                        raise ProjectError("Research output artifact is invalid")
                    target = artifact_dir / filename
                    fd = os.open(
                        target,
                        os.O_CREAT | os.O_EXCL | os.O_WRONLY | getattr(os, "O_NOFOLLOW", 0),
                        0o600,
                    )
                    with os.fdopen(fd, "wb") as output:
                        output.write(content)
                        output.flush()
                        os.fsync(output.fileno())
                    artifact_records.append(
                        {
                            "filename": filename,
                            "media_type": media_type,
                            "size_bytes": len(content),
                            "sha256": hashlib.sha256(content).hexdigest(),
                        }
                    )
                record["artifacts"] = artifact_records
                encoded = (
                    json.dumps(record, ensure_ascii=False, separators=(",", ":")) + "\n"
                ).encode()
                if len(encoded) > MAX_ARTIFACT_BYTES:
                    raise ProjectError("Research execution artifact exceeded its storage limit")
                existing_bytes = sum(
                    item.stat().st_size
                    for item in directory.rglob("*")
                    if item.is_file() and not item.is_symlink()
                )
                if existing_bytes - previous + len(encoded) > MAX_STORAGE_BYTES:
                    raise ProjectError("Research execution storage limit reached")
                staged = _stage(directory, encoded)
                try:
                    os.chmod(staged, 0o600)
                    os.replace(staged, target_record)
                finally:
                    staged.unlink(missing_ok=True)
            except BaseException:
                for item in artifact_dir.iterdir():
                    item.unlink(missing_ok=True)
                if not finalizing:
                    artifact_dir.rmdir()
                raise
            fcntl.flock(lock, fcntl.LOCK_UN)
    except (OSError, ValueError) as exc:
        raise ProjectError("Could not store research execution artifact") from exc


def _execution_state(record: dict[str, Any], directory: Path) -> dict[str, Any]:
    if record.get("status") == "running":
        active = directory / f"{record['id']}.active"
        try:
            fd = os.open(active, os.O_RDWR | getattr(os, "O_NOFOLLOW", 0))
        except OSError:
            fd = None
        if fd is not None:
            try:
                try:
                    fcntl.flock(fd, fcntl.LOCK_EX | fcntl.LOCK_NB)
                except BlockingIOError:
                    return record
                fcntl.flock(fd, fcntl.LOCK_UN)
            finally:
                os.close(fd)
        return {
            **record,
            "status": "interrupted",
            "interruption_reason": (
                "The backend lost this reserved execution before a terminal result was saved. "
                "The program may have run; no output or conclusion can be inferred. "
                "It will not be executed automatically again."
            ),
        }
    return record


def _read_record(path: str | Path, execution_id: str) -> dict[str, Any]:
    identifier = _metadata_id(execution_id, "execution")
    assert identifier
    directory = _execution_directory(path)
    bundle_path = _execution_bundle_path(directory)
    if bundle_path is not None:
        from sigma.project_bundle import BundleError, read_file
        try:
            raw = read_file(bundle_path, _bundle_execution_member(identifier))
            if len(raw) > MAX_ARTIFACT_BYTES:
                raise ProjectError("Research execution artifact is oversized")
            record = json.loads(raw)
        except (BundleError, ValueError, UnicodeDecodeError) as exc:
            raise ProjectError("Research execution artifact not found or unreadable") from exc
        if (not isinstance(record, dict) or record.get("id") != identifier
            or record.get("project_id") != inspect_project(path).project.id):
            raise ProjectError("Research execution artifact does not match this project")
        return _execution_state(record, directory)
    target = directory / f"{identifier}.json"
    if target.is_symlink() or not target.is_file() or target.stat().st_size > MAX_ARTIFACT_BYTES:
        raise ProjectError("Research execution artifact not found")
    try:
        record = json.loads(target.read_text(encoding="utf-8"))
    except (OSError, ValueError) as exc:
        raise ProjectError("Research execution artifact is unreadable") from exc
    if (
        not isinstance(record, dict)
        or record.get("id") != identifier
        or record.get("project_id") != inspect_project(path).project.id
    ):
        raise ProjectError("Research execution artifact does not match this project")
    return _execution_state(record, directory)


def list_executions(path: str | Path) -> list[dict[str, Any]]:
    directory = _execution_directory(path)
    project_id = inspect_project(path).project.id
    bundle_path = _execution_bundle_path(directory)
    if bundle_path is not None:
        from sigma.project_bundle import read_bundle
        import base64
        try:
            members = read_bundle(bundle_path)["files"]
        except (OSError, ValueError) as exc:
            raise ProjectError("Research execution bundle is unreadable") from exc
        records = []
        prefix = "research-executions/"
        for name, encoded in members.items():
            if not name.startswith(prefix) or not name.endswith(".json") or ".artifacts/" in name:
                continue
            try:
                raw = base64.b64decode(encoded, validate=True)
                if len(raw) > MAX_ARTIFACT_BYTES:
                    continue
                record = json.loads(raw)
            except (ValueError, UnicodeDecodeError):
                continue
            if (not isinstance(record, dict) or record.get("project_id") != project_id
                or name != _bundle_execution_member(str(record.get("id", "")))
                or not isinstance(record.get("created_at"), str)):
                continue
            try:
                _metadata_id(record["id"], "execution")
            except ProjectError:
                continue
            records.append(_execution_state(record, directory))
        return sorted(records, key=lambda item: item.get("created_at", ""), reverse=True)
    records = []
    for target in directory.glob("*.json"):
        if (
            target.is_symlink()
            or not target.is_file()
            or target.stat().st_size > MAX_ARTIFACT_BYTES
        ):
            continue
        try:
            record = json.loads(target.read_text(encoding="utf-8"))
        except (OSError, ValueError):
            continue
        if (
            not isinstance(record, dict)
            or record.get("project_id") != project_id
            or record.get("id") != target.stem
            or not isinstance(record.get("created_at"), str)
        ):
            continue
        try:
            _metadata_id(record["id"], "execution")
        except ProjectError:
            continue
        records.append(_execution_state(record, directory))
    return sorted(records, key=lambda item: item.get("created_at", ""), reverse=True)


def find_session_execution(
    path: str | Path,
    *,
    session_id: str,
    strategy_id: str,
    cycle: int,
    source: str,
    include_prior_failures: bool = False,
    runtime_name: str = "python",
) -> dict[str, Any] | None:
    """Find a durably saved exact proposal result for crash-safe session recovery."""
    return next(
        (
            record
            for record in list_executions(path)
            if record.get("runtime", "python") == runtime_name
            and record.get("session_id") == session_id
            and record.get("strategy_id") == strategy_id
            and (
                record.get("cycle") == cycle
                or (
                    include_prior_failures
                    and type(record.get("cycle")) is int
                    and record["cycle"] < cycle
                    and record.get("status") in {"failed", "timeout", "output_limit", "interrupted"}
                    and (
                        runtime_name == "python"
                        or (
                            record.get("runtime_version")
                            == runtime_settings(runtime_name)["version"]
                            and record.get("syntax") == runtime_settings(runtime_name)["syntax"]
                            and record.get("environment", {}).get("image")
                            == runtime_settings(runtime_name)["image"]
                        )
                    )
                )
            )
            and record.get("source") == source
        ),
        None,
    )


async def execute(source: str, runtime_name: str = "python") -> ExecutionResult:
    """Execute one bounded code proposal without blocking the event loop."""
    task = asyncio.create_task(asyncio.to_thread(_execute_admitted, source, runtime_name))
    try:
        return await asyncio.shield(task)
    except asyncio.CancelledError:
        # The container has a hard wall limit; wait for its bounded cleanup so
        # callers that persist the result can retain an honest execution record.
        return await asyncio.shield(task)


async def execute_research_code(
    path: str | Path,
    source: str,
    *,
    session_id: str | None = None,
    strategy_id: str | None = None,
    cycle: int | None = None,
    runtime_name: str = "python",
    step_id: str | None = None,
) -> dict[str, Any]:
    """Execute and durably capture one code proposal for later role-loop integration."""
    _validate_source(source)
    settings = runtime_settings(runtime_name)
    agent: dict[str, Any] | None = None
    view = inspect_project(path)
    provenance = (session_id, strategy_id, cycle)
    if any(item is not None for item in provenance):
        if not all(item is not None for item in provenance):
            raise ProjectError("Session, strategy, and cycle provenance must be supplied together")
        normalized_session = _metadata_id(session_id, "session")
        normalized_strategy = _metadata_id(strategy_id, "strategy")
        assert normalized_session and normalized_strategy and cycle is not None
        if type(cycle) is not int or cycle < 1:
            raise ProjectError("Research cycle must be a positive integer")
        # Import lazily because the research-session service calls this module.
        from sigma.research_sessions import _read as read_session

        session = read_session(str(path), normalized_session)
        if session.get("project_id") != view.project.id:
            raise ProjectError("Research session does not belong to this project")
        branch = next(
            (
                item
                for item in session.get("strategy_runs", [])
                if item.get("strategy_id") == normalized_strategy
            ),
            None,
        )
        if branch is None or branch.get("cycle") != cycle:
            raise ProjectError("Research strategy and cycle do not match this session")
        session_id, strategy_id = normalized_session, normalized_strategy
        if step_id is not None:
            origin = next(
                (step for step in session.get("steps", []) if step.get("id") == step_id), None
            )
            source_field = "sage_code" if runtime_name == "sagemath" else "python_code"
            if (
                not origin
                or origin.get("strategy_id") != strategy_id
                or origin.get("cycle") != cycle
                or origin.get("role") != "investigator"
                or origin.get("status") != "completed"
                or origin.get("output", {}).get(source_field) != source
            ):
                raise ProjectError("Execution step does not match the saved Investigator proposal")
            agent = {
                "role": "investigator",
                "step_id": step_id,
                "model": session.get("model"),
                "reasoning_effort": session.get("reasoning_effort"),
            }
        existing = find_session_execution(
            path,
            session_id=session_id,
            strategy_id=strategy_id,
            cycle=cycle,
            source=source,
            runtime_name=runtime_name,
        )
        if existing is not None:
            if existing["status"] == "running":
                raise ProjectError(
                    "This Python proposal is already active; no second run was started"
                )
            return existing
    if step_id is not None and agent is None:
        raise ProjectError("Step provenance requires a session")
    record = {
        "schema_version": 1,
        "runtime": runtime_name,
        "runtime_version": settings["version"],
        "syntax": settings["syntax"],
        "agent": agent,
        "source_sha256": hashlib.sha256(source.encode("utf-8")).hexdigest(),
        "id": str(uuid4()),
        "project_id": view.project.id,
        "session_id": _metadata_id(session_id, "session"),
        "strategy_id": _metadata_id(strategy_id, "strategy"),
        "cycle": cycle,
        "created_at": datetime.now(UTC).isoformat(),
        "status": "running",
        "exit_code": None,
        "stdout": "",
        "stderr": "",
        "duration_ms": None,
        "source": source,
        "artifact_error": None,
        "environment": {
            "image": settings["image"],
            "image_id": None,
            "network": "none",
            "memory_bytes": settings["memory_mib"] * 1024 * 1024,
            "cpu_limit": 1,
            "process_limit": 64,
            "wall_limit_seconds": settings["wall_seconds"],
        },
    }
    directory = _execution_directory(path)
    identifier = record["id"]
    active = directory / f"{identifier}.active"
    active_fd = os.open(
        active, os.O_CREAT | os.O_EXCL | os.O_RDWR | getattr(os, "O_NOFOLLOW", 0), 0o600
    )
    fcntl.flock(active_fd, fcntl.LOCK_EX)
    cancelled = False
    try:
        # Reserve before dispatch. A process death at any later point leaves
        # inspectable uncertain evidence and cannot silently trigger a rerun.
        _save_record(directory, record)
        execution_task = asyncio.create_task(
            execute(source) if runtime_name == "python" else execute(source, runtime_name)
        )
        while True:
            try:
                result = await asyncio.shield(execution_task)
                break
            except asyncio.CancelledError:
                cancelled = True
                if execution_task.cancelled():
                    raise
        record.update(
            status=result.status,
            exit_code=result.exit_code,
            stdout=result.stdout,
            stderr=result.stderr,
            duration_ms=result.duration_ms,
            artifact_error=result.artifact_error,
            finished_at=datetime.now(UTC).isoformat(),
        )
        record["environment"]["image_id"] = result.image_id
        for stream, raw in (("stdout", result.stdout_base64), ("stderr", result.stderr_base64)):
            if raw is not None:
                record[f"{stream}_base64"] = raw
        _save_record(directory, record, result.artifacts, finalizing=True)
    finally:
        fcntl.flock(active_fd, fcntl.LOCK_UN)
        os.close(active_fd)
        active.unlink(missing_ok=True)
    if cancelled:
        raise asyncio.CancelledError
    return record


def get_execution(path: str | Path, execution_id: str) -> dict[str, Any]:
    return _read_record(path, execution_id)


def get_execution_artifact(path: str | Path, execution_id: str, filename: str) -> tuple[bytes, str]:
    record = _read_record(path, execution_id)
    metadata = next(
        (item for item in record.get("artifacts", []) if item.get("filename") == filename), None
    )
    if metadata is None or Path(filename).name != filename:
        raise ProjectError("Research output artifact not found")
    execution_directory = _execution_directory(path)
    bundle_path = _execution_bundle_path(execution_directory)
    if bundle_path is not None:
        from sigma.project_bundle import read_file
        member = f"research-executions/{record['id']}.artifacts/{filename}"
        try:
            content = read_file(bundle_path, member)
        except (OSError, ValueError, KeyError) as exc:
            raise ProjectError("Research output artifact not found") from exc
        if len(content) != metadata["size_bytes"] or hashlib.sha256(content).hexdigest() != metadata["sha256"]:
            raise ProjectError("Research output artifact failed its integrity check")
        return content, str(metadata["media_type"])
    artifact_directory = execution_directory / f"{record['id']}.artifacts"
    if artifact_directory.is_symlink():
        raise ProjectError("Research output artifact directory is unsafe")
    target = artifact_directory / filename
    if (
        target.is_symlink()
        or not target.is_file()
        or target.stat().st_size != metadata["size_bytes"]
    ):
        raise ProjectError("Research output artifact not found")
    content = target.read_bytes()
    if hashlib.sha256(content).hexdigest() != metadata["sha256"]:
        raise ProjectError("Research output artifact failed its integrity check")
    return content, str(metadata["media_type"])
