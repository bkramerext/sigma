"""Bounded Docker adapter for untrusted, generated research Python."""

from __future__ import annotations

import asyncio
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
from typing import Any
from uuid import UUID, uuid4

from sigma.projects import ProjectError, _stage, inspect_project, project_path

IMAGE = "sigma-research-python:0.1"
CONTAINER_RUNTIME = "docker"
MAX_SOURCE_BYTES = 16_000
MAX_OUTPUT_BYTES = 32_000
EXECUTION_TIMEOUT_SECONDS = 15
MAX_STORAGE_BYTES = 16_000_000
MAX_ARTIFACT_BYTES = 64_000
MAX_CAPTURED_ARTIFACT_BYTES = 4_000_000
MAX_CAPTURED_ARTIFACTS = 8
MAX_CAPTURE_ARCHIVE_BYTES = 16 * 1024 * 1024
_EXECUTION_GATE = threading.BoundedSemaphore(1)


@dataclass(frozen=True)
class ExecutionResult:
    status: str
    exit_code: int | None
    stdout: str
    stderr: str
    duration_ms: int
    image_id: str | None = None
    artifacts: tuple[tuple[str, str, bytes], ...] = ()


def docker_command(cidfile: str | None = None, image: str = IMAGE) -> list[str]:
    """Return fixed container arguments; user values never enter command tokens."""
    command = [
        CONTAINER_RUNTIME,
        "run",
        "--interactive",
        "--pull=never",
        "--network=none",
        "--memory=512m",
        "--memory-swap=512m",
        "--cpus=1",
        "--pids-limit=64",
        "--read-only",
        "--tmpfs=/tmp:rw,noexec,nosuid,size=64m",
        "--tmpfs=/artifacts:rw,noexec,nosuid,size=16m",
        "--user=65532:65532",
        "--cap-drop=ALL",
        "--security-opt=no-new-privileges",
        "--env=MPLCONFIGDIR=/tmp/matplotlib",
    ]
    if cidfile:
        command.append(f"--cidfile={cidfile}")
    command.append(image)
    return command


def _capture_artifacts(container_id: str) -> tuple[tuple[str, str, bytes], ...]:
    try:
        process = subprocess.Popen(
            [CONTAINER_RUNTIME, "exec", container_id, "tar", "-C", "/artifacts", "-cf", "-", "."],
            stdout=subprocess.PIPE,
            stderr=subprocess.DEVNULL,
            env={"PATH": os.environ.get("PATH", "/usr/bin:/bin")},
        )
    except OSError as exc:
        raise ProjectError("Could not capture research output files") from exc
    assert process.stdout
    selector = selectors.DefaultSelector()
    selector.register(process.stdout, selectors.EVENT_READ)
    archive_chunks = bytearray()
    deadline = time.monotonic() + 5
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
                if member.isdir() and filename in {"", "."}:
                    continue
                if (
                    len(captured) >= MAX_CAPTURED_ARTIFACTS
                    or not filename
                    or filename in {".", ".."}
                    or "/" in filename
                    or "\\" in filename
                    or not member.isfile()
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


def _image_identity() -> str | None:
    runtime = CONTAINER_RUNTIME
    try:
        result = subprocess.run(
            [runtime, "image", "inspect", "--format={{.Id}}", IMAGE],
            capture_output=True,
            timeout=3,
            check=False,
            env={"PATH": os.environ.get("PATH", "/usr/bin:/bin")},
        )
    except (OSError, subprocess.TimeoutExpired):
        return None
    image_id = result.stdout.decode("ascii", errors="ignore").strip()
    if result.returncode or len(image_id) != 71 or not image_id.startswith("sha256:"):
        return None
    if any(character not in "0123456789abcdef" for character in image_id[7:]):
        return None
    return image_id


def _run(
    source: str, image_id: str
) -> tuple[int | None, bytes, bytes, str, tuple[tuple[str, str, bytes], ...]]:
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
                env={"PATH": os.environ.get("PATH", "/usr/bin:/bin")},
            )
        except (OSError, subprocess.TimeoutExpired):
            pass

    try:
        process = subprocess.Popen(
            docker_command(str(cidfile), image_id),
            stdin=subprocess.PIPE,
            stdout=subprocess.PIPE,
            stderr=subprocess.PIPE,
            bufsize=0,
            start_new_session=True,
            env={"PATH": os.environ.get("PATH", "/usr/bin:/bin")},
        )
    except OSError:
        cidfile.unlink(missing_ok=True)
        return None, b"", b"Container runtime could not start.", "unavailable", ()
    assert process.stdin and process.stdout and process.stderr
    started = time.monotonic()
    try:
        process.stdin.write(
            str(len(encoded)).encode("ascii")
            + b"\n"
            + encoded
            + runner_token.encode("ascii")
            + b"\n"
        )
    except BrokenPipeError:
        pass
    selector = selectors.DefaultSelector()
    selector.register(process.stdout, selectors.EVENT_READ, "stdout")
    selector.register(process.stderr, selectors.EVENT_READ, "stderr")
    chunks = {"stdout": bytearray(), "stderr": bytearray()}
    status = "completed"
    marker = b"\x1eSIGMA_DONE:" + runner_token.encode("ascii") + b"\x1f\n"
    pending_stdout = bytearray()
    marker_seen = False
    artifacts: tuple[tuple[str, str, bytes], ...] = ()

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
        elapsed = time.monotonic() - started
        if elapsed >= EXECUTION_TIMEOUT_SECONDS and status == "completed" and not marker_seen:
            status = stop_container("timeout")
            break
        for key, _ in selector.select(min(0.1, max(0.001, EXECUTION_TIMEOUT_SECONDS - elapsed))):
            chunk = os.read(key.fd, MAX_OUTPUT_BYTES + 1)
            if not chunk:
                if key.data == "stdout" and pending_stdout and not marker_seen:
                    chunk = bytes(pending_stdout)
                    pending_stdout.clear()
                else:
                    selector.unregister(key.fileobj)
                    continue
            if key.data == "stdout":
                pending_stdout.extend(chunk)
                marker_at = pending_stdout.find(marker)
                if marker_at >= 0:
                    output_chunk = bytes(pending_stdout[:marker_at])
                    pending_stdout.clear()
                    marker_seen = True
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
            if marker_seen:
                try:
                    cid = cidfile.read_text(encoding="ascii").strip()
                    artifacts = _capture_artifacts(cid)
                except (OSError, UnicodeError, ProjectError) as exc:
                    status = "failed"
                    message = (
                        str(exc)
                        if isinstance(exc, ProjectError)
                        else "Could not capture research output files."
                    )
                    chunks["stderr"] = bytearray(message.encode("utf-8")[:MAX_OUTPUT_BYTES])
                try:
                    process.stdin.close()
                except BrokenPipeError:
                    pass
                break
        if marker_seen:
            continue
        if process.poll() is not None and not selector.get_map():
            break
    selector.close()
    return_code = process.wait()
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
                env={"PATH": os.environ.get("PATH", "/usr/bin:/bin")},
            )
        except (OSError, subprocess.TimeoutExpired):
            pass
    cidfile.unlink(missing_ok=True)
    diagnostic = b""
    if status == "timeout":
        diagnostic = b"\nExecution exceeded the 15-second wall limit."
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
    return return_code, bytes(stdout), bytes(stderr), status, artifacts


def _execute(source: str) -> ExecutionResult:
    _validate_source(source)
    image_id = _image_identity()
    if image_id is None:
        return ExecutionResult(
            "unavailable",
            None,
            "No locally built research image is available; build sandbox-poc first.",
            "",
            0,
        )
    started = time.monotonic()
    return_code, stdout, stderr, status, artifacts = _run(source, image_id)
    duration = round((time.monotonic() - started) * 1000)
    if status == "unavailable":
        return ExecutionResult(status, None, "", stderr.decode("utf-8"), duration, image_id)
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
    )


def _execute_admitted(source: str) -> ExecutionResult:
    if not _EXECUTION_GATE.acquire(blocking=False):
        return ExecutionResult("busy", None, "Another research code run is active.", "", 0)
    try:
        return _execute(source)
    finally:
        _EXECUTION_GATE.release()


def _execution_directory(path: str | Path) -> Path:
    target = project_path(path)
    directory = target / "research-executions"
    if directory.is_symlink():
        raise ProjectError("Research execution directory must not be a symbolic link")
    try:
        directory.mkdir(mode=0o700, exist_ok=True)
        os.chmod(directory, 0o700)
    except OSError as exc:
        raise ProjectError("Research execution storage is unavailable") from exc
    return directory


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
) -> None:
    encoded = (json.dumps(record, ensure_ascii=False, separators=(",", ":")) + "\n").encode()
    if len(encoded) > MAX_ARTIFACT_BYTES:
        raise ProjectError("Research execution artifact exceeded its storage limit")
    try:
        fd = os.open(
            directory / ".lock", os.O_CREAT | os.O_RDWR | getattr(os, "O_NOFOLLOW", 0), 0o600
        )
        with os.fdopen(fd, "r+") as lock:
            fcntl.flock(lock, fcntl.LOCK_EX)
            artifact_dir = directory / f"{record['id']}.artifacts"
            artifact_dir.mkdir(mode=0o700, exist_ok=False)
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
                if existing_bytes + len(encoded) > MAX_STORAGE_BYTES:
                    raise ProjectError("Research execution storage limit reached")
                staged = _stage(directory, encoded)
                try:
                    os.chmod(staged, 0o600)
                    os.replace(staged, directory / f"{record['id']}.json")
                finally:
                    staged.unlink(missing_ok=True)
            except BaseException:
                for item in artifact_dir.iterdir():
                    item.unlink(missing_ok=True)
                artifact_dir.rmdir()
                raise
            fcntl.flock(lock, fcntl.LOCK_UN)
    except OSError as exc:
        raise ProjectError("Could not store research execution artifact") from exc


def _read_record(path: str | Path, execution_id: str) -> dict[str, Any]:
    identifier = _metadata_id(execution_id, "execution")
    assert identifier
    directory = _execution_directory(path)
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
    return record


def list_executions(path: str | Path) -> list[dict[str, Any]]:
    directory = _execution_directory(path)
    project_id = inspect_project(path).project.id
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
        if isinstance(record, dict) and record.get("project_id") == project_id:
            records.append(record)
    return sorted(records, key=lambda item: item.get("created_at", ""), reverse=True)


async def execute(source: str) -> ExecutionResult:
    """Execute one bounded code proposal without blocking the event loop."""
    task = asyncio.create_task(asyncio.to_thread(_execute_admitted, source))
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
) -> dict[str, Any]:
    """Execute and durably capture one code proposal for later role-loop integration."""
    _validate_source(source)
    view = inspect_project(path)
    if cycle is not None and (type(cycle) is not int or cycle < 1):
        raise ProjectError("Research cycle must be a positive integer")
    execution_task = asyncio.create_task(execute(source))
    cancelled = False
    try:
        result = await asyncio.shield(execution_task)
    except asyncio.CancelledError:
        cancelled = True
        result = await asyncio.shield(execution_task)
    record = {
        "schema_version": 1,
        "id": str(uuid4()),
        "project_id": view.project.id,
        "session_id": _metadata_id(session_id, "session"),
        "strategy_id": _metadata_id(strategy_id, "strategy"),
        "cycle": cycle,
        "created_at": datetime.now(UTC).isoformat(),
        "status": result.status,
        "exit_code": result.exit_code,
        "stdout": result.stdout,
        "stderr": result.stderr,
        "duration_ms": result.duration_ms,
        "source": source,
        "environment": {
            "image": IMAGE,
            "image_id": result.image_id,
            "network": "none",
            "memory_bytes": 512 * 1024 * 1024,
            "cpu_limit": 1,
            "process_limit": 64,
            "wall_limit_seconds": EXECUTION_TIMEOUT_SECONDS,
        },
    }
    _save_record(_execution_directory(path), record, result.artifacts)
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
    target = _execution_directory(path) / f"{record['id']}.artifacts" / filename
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
