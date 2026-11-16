"""Local --prod launcher for SIGMA's one shared Personal ChatGPT container.

The localhost-only Personal ports belong to a single shared Docker service.
Transient Chromium runs under a separate UID, not in a per-user container.
The hosted OAuth permission and deployment decisions remain separate.
"""

from __future__ import annotations

import hashlib
import os
import re
import secrets
import shutil
import signal
import stat
import subprocess
import sys
import tempfile
import time
from collections.abc import Callable
from dataclasses import dataclass
from pathlib import Path

from sigma import personal_diagnostics

ROOT = Path(__file__).resolve().parents[2]
WORKSPACE = re.compile(r"[0-9a-f]{32}\Z")
RELEASE = re.compile(r"[0-9a-f]{40}\Z")
CHECKOUT = re.compile(r"[0-9a-f]{32}\Z")
COMPOSE_FILES = ("deploy/personal-shared.compose.yaml",)


class LocalPersonalUnavailable(RuntimeError):
    """The optional local Docker Personal browser cannot be started safely."""


def _local_runtime_directory() -> Path:
    """Keep native macOS Unix relay socket names under sun_path's 104 bytes.

    Apple's usual /var/folders/.../T/TMPDIR is far too long once SIGMA appends
    a private workspace ID and socket name. A random mode-0700 directory under
    /tmp is short, owner-private and removed at normal launcher shutdown.
    """
    path = Path(tempfile.mkdtemp(prefix="sigma-personal-", dir="/tmp"))
    longest_socket = path / "gateways" / ("0" * 32) / "model.sock"
    if len(os.fsencode(longest_socket)) >= 104:
        shutil.rmtree(path)
        raise LocalPersonalUnavailable("Local Personal Unix socket path is too long.")
    return path


def _docker_failure_class(message: str) -> str:
    """Fixed output from Docker errors, never private stderr or mount paths."""
    normalized = message.lower()
    categories = (
        ("docker_desktop_file_sharing", ("mounts denied", "file sharing is not enabled")),
        ("port_conflict", ("port is already allocated", "address already in use")),
        (
            "docker_daemon_unavailable",
            ("cannot connect to the docker daemon", "is the docker daemon running"),
        ),
        (
            "image_platform_mismatch",
            ("no matching manifest", "exec format error", "requested image's platform"),
        ),
        ("insufficient_memory", ("out of memory", "oomkilled", "resource exhausted")),
        ("disk_full", ("no space left on device",)),
        ("permission_denied", ("permission denied", "operation not permitted", "access is denied")),
    )
    for category, patterns in categories:
        if any(pattern in normalized for pattern in patterns):
            return category
    return "unclassified"


def _command(args: list[str], *, env: dict[str, str], timeout: int = 90) -> str:
    # Suppress arbitrary process output and report only a fixed operation name.
    stage = args[0] + (
        " " + args[1]
        if len(args) > 1 and args[1] in {"compose", "info", "image", "tag", "ps"}
        else ""
    )
    begun = time.monotonic()
    personal_diagnostics.emit("preparation", "command_start", operation=stage.replace(" ", "_"))
    try:
        result = subprocess.run(
            args,
            cwd=ROOT,
            env=env,
            text=True,
            capture_output=True,
            timeout=timeout,
            check=False,
        )
    except (OSError, subprocess.TimeoutExpired) as exc:
        failure = "timeout" if isinstance(exc, subprocess.TimeoutExpired) else type(exc).__name__
        personal_diagnostics.emit(
            "preparation",
            "command_exception",
            operation=stage.replace(" ", "_"),
            failure=failure,
            elapsed_ms=int((time.monotonic() - begun) * 1000),
        )
        raise LocalPersonalUnavailable("Local Personal container preparation failed.") from exc
    if result.returncode:
        # Docker output can include credentials/host paths; keep errors generic.
        personal_diagnostics.emit(
            "preparation",
            "command_failed",
            operation=stage.replace(" ", "_"),
            exit_code=result.returncode,
            failure=_docker_failure_class(result.stderr or ""),
            elapsed_ms=int((time.monotonic() - begun) * 1000),
        )
        raise LocalPersonalUnavailable(
            "Local Personal container preparation failed. Check Docker Desktop."
        )
    personal_diagnostics.emit(
        "preparation",
        "command_ok",
        operation=stage.replace(" ", "_"),
        elapsed_ms=int((time.monotonic() - begun) * 1000),
    )
    return result.stdout.strip()


def _docker_environment() -> dict[str, str]:
    env = dict(os.environ)
    desktop = Path("/Applications/Docker.app/Contents/Resources/bin")
    if (desktop / "docker-credential-desktop").is_file():
        env["PATH"] = str(desktop) + os.pathsep + env.get("PATH", "")
    if shutil.which("docker", path=env.get("PATH")) is None:
        raise LocalPersonalUnavailable(
            "Install and start Docker Desktop to use local Personal ChatGPT."
        )
    return env


def _private_directory(path: Path, mode: int) -> None:
    path.mkdir(parents=True, exist_ok=True)
    if path.is_symlink() or not stat.S_ISDIR(path.lstat().st_mode):
        raise LocalPersonalUnavailable("Unsafe local Personal directory.")
    if path.stat().st_uid != os.geteuid():
        raise LocalPersonalUnavailable("Local Personal directory has another owner.")
    path.chmod(mode)
    if stat.S_IMODE(path.stat().st_mode) != mode:
        raise LocalPersonalUnavailable("Could not secure local Personal directory.")


def _release_images(env: dict[str, str], *, build: bool = True) -> tuple[str, str]:
    """Build one native-architecture image; no legacy user-worker pair."""
    release = _command(["git", "rev-parse", "--verify", "HEAD"], env=env, timeout=10)
    if not RELEASE.fullmatch(release):
        raise LocalPersonalUnavailable("Unable to identify a pinned SIGMA release.")
    architecture = _command(
        ["docker", "info", "--format", "{{.Architecture}}"], env=env, timeout=20
    )
    platform = {
        "arm64": "linux/arm64",
        "aarch64": "linux/arm64",
        "amd64": "linux/amd64",
        "x86_64": "linux/amd64",
    }.get(architecture)
    if platform is None:
        raise LocalPersonalUnavailable("Docker Desktop architecture is unsupported.")
    env["SIGMA_RELEASE"] = release
    env["SIGMA_SHARED_PLATFORM"] = platform
    env["SIGMA_AUTH_POC_BROWSER_PLATFORM"] = platform
    personal_diagnostics.emit("preparation", "platform_selected", platform=platform)
    if build and not _images_compatible(env):
        # No live RPC secret is available to Docker image-build operations.
        build_env = {**env, "SIGMA_AUTH_POC_RPC_SEED": "0" * 64}
        _command(
            ["docker", "compose", "-f", COMPOSE_FILES[0], "build", "personal"],
            env=build_env,
            timeout=900,
        )
        if not _images_compatible(env):
            raise LocalPersonalUnavailable("Shared Personal image architecture mismatch.")
    return release, platform


def _images_compatible(env: dict[str, str]) -> bool:
    try:
        actual = _command(
            [
                "docker",
                "image",
                "inspect",
                "--format",
                "{{.Os}}/{{.Architecture}}",
                "sigma-shared-personal:" + env["SIGMA_RELEASE"],
            ],
            env=env,
            timeout=10,
        )
        return actual == env["SIGMA_SHARED_PLATFORM"]
    except LocalPersonalUnavailable:
        return False


def _checkout_id() -> str:
    # Stable across SIGMA restarts, and does not expose the checkout path.
    return hashlib.sha256(str(ROOT.resolve()).encode()).hexdigest()[:32]


def _down_shared(env: dict[str, str]) -> None:
    """Stop exactly this checkout's shared service; retain its two volumes."""
    checkout = env.get("SIGMA_AUTH_POC_CHECKOUT_ID", "")
    if not CHECKOUT.fullmatch(checkout):
        raise LocalPersonalUnavailable("Private checkout identity is invalid.")
    # Compose interpolates this even for down; never use the real secret here.
    safe_env = {**env, "SIGMA_AUTH_POC_RPC_SEED": "0" * 64}
    _command(
        [
            "docker",
            "compose",
            "--project-name",
            "sigma-shared-" + checkout,
            "-f",
            COMPOSE_FILES[0],
            "down",
            "--remove-orphans",
        ],
        env=safe_env,
        timeout=70,
    )


def _preparation_state(path: Path, state: str) -> None:
    if state not in {"preparing", "ready", "failed"}:
        raise ValueError("Invalid local preparation state.")
    temporary = path.with_suffix(".next")
    temporary.write_text(state, encoding="ascii")
    temporary.chmod(0o600)
    temporary.replace(path)


def _prepare(env: dict[str, str]) -> int:
    """Replace the experimental Docker topology with one shared POC service."""
    marker = Path(env["SIGMA_LOCAL_PERSONAL_PREPARATION_FILE"])
    phase = "docker_reconciliation"
    try:
        personal_diagnostics.emit("preparation", "phase_begin", phase=phase)
        _down_shared(env)
        phase = "native_image_build"
        personal_diagnostics.emit("preparation", "phase_begin", phase=phase)
        _release_images(env)
        _preparation_state(marker, "ready")
        personal_diagnostics.emit("preparation", "ready")
        return 0
    except (OSError, RuntimeError, ValueError, KeyError) as exc:
        _preparation_state(marker, "failed")
        personal_diagnostics.emit(
            "preparation",
            "failed",
            phase=phase,
            failure=type(exc).__name__,
        )
        return 1


@dataclass
class LocalPersonalRuntime:
    """Owns the broker, ephemeral relays and container lifetime for one launch."""

    runtime: Path
    state_root: Path
    env: dict[str, str]
    broker: subprocess.Popen[bytes]
    preparation: subprocess.Popen[bytes]

    @classmethod
    def start(cls) -> LocalPersonalRuntime:
        # No diagnostic log, file path or verbose output during normal use.
        # Explicit SIGMA_PERSONAL_DIAGNOSTICS_ENABLED=1 opts into a private
        # per-launch log, even if Docker fails before the broker is ready.
        state_root = Path.home() / ".sigma" / "personal-shared-poc"
        _private_directory(state_root, 0o700)
        os.environ.pop("SIGMA_PERSONAL_DIAGNOSTICS_FILE", None)
        capture = None
        if personal_diagnostics.enabled():
            capture = personal_diagnostics.create_capture(state_root)
            os.environ["SIGMA_PERSONAL_DIAGNOSTICS_FILE"] = str(capture)
            print(f"SIGMA Personal diagnostics: {capture}", flush=True)
            personal_diagnostics.emit("launcher", "begin")
        try:
            env = _docker_environment()
            env.pop("SIGMA_PERSONAL_DIAGNOSTICS_FILE", None)
            if capture is not None:
                env["SIGMA_PERSONAL_DIAGNOSTICS_FILE"] = str(capture)
            release, platform = _release_images(env, build=False)
        except (OSError, RuntimeError) as exc:
            personal_diagnostics.emit("launcher", "preflight_failed", failure=type(exc).__name__)
            raise
        runtime = _local_runtime_directory()
        broker: subprocess.Popen[bytes] | None = None
        preparation: subprocess.Popen[bytes] | None = None
        try:
            _private_directory(runtime / "broker", 0o711)
            _private_directory(runtime / "gateways", 0o711)
            marker = runtime / "prepare.status"
            _preparation_state(marker, "preparing")
            env.update(
                {
                    "SIGMA_RELEASE": release,
                    "SIGMA_AUTH_BROKER_LOCAL_POC": "1",
                    "SIGMA_AUTH_BROKER_GATEWAY_ROOT": str(runtime / "gateways"),
                    "SIGMA_AUTH_BROKER_SOCKET": str(runtime / "broker" / "broker.sock"),
                    "SIGMA_AUTH_BROKER_CLIENT_UID": str(os.geteuid()),
                    "SIGMA_AUTH_POC_BROWSER_PLATFORM": platform,
                    "SIGMA_SHARED_PLATFORM": platform,
                    "SIGMA_PERSONAL_SHARED_MODE": "1",
                    "SIGMA_AUTH_POC_LOCAL_UID": str(os.geteuid()),
                    "SIGMA_AUTH_POC_CHECKOUT_ID": _checkout_id(),
                    "SIGMA_LOCAL_PERSONAL_PREPARATION_FILE": str(marker),
                    "SIGMA_AUTH_POC_LOCAL_REAL_SIGNIN": "1",
                    "SIGMA_AUTH_POC_REAL_SIGNIN": "0",
                    "SIGMA_PERSONAL_BROWSER_LAB_ENABLED": "1",
                    "SIGMA_PERSONAL_BROWSER_BROKER_SOCKET": str(runtime / "broker" / "broker.sock"),
                    "SIGMA_PERSONAL_BROWSER_GATEWAY_ROOT": str(runtime / "gateways"),
                    # Broker derives a separate HMAC key per Google workspace.
                    # SIGMA forwards only authorized, bounded Personal RPCs.
                    "SIGMA_AUTH_POC_RPC_SEED": secrets.token_hex(32),
                }
            )
            # The RPC seed is intentionally short lived: rederived per launch.
            personal_diagnostics.emit("launcher", "broker_spawn")
            broker = subprocess.Popen(
                [sys.executable, str(ROOT / "auth-poc" / "shared_broker.py")],
                cwd=ROOT,
                env=env,
                stdin=subprocess.DEVNULL,
            )
            socket_path = runtime / "broker" / "broker.sock"
            for _ in range(100):
                if broker.poll() is not None:
                    raise LocalPersonalUnavailable("Private Personal container broker exited.")
                if socket_path.is_socket():
                    info = socket_path.lstat()
                    if info.st_uid == os.geteuid() and stat.S_IMODE(info.st_mode) == 0o600:
                        prepare_env = dict(env)
                        prepare_env.pop("SIGMA_AUTH_POC_RPC_SEED", None)
                        personal_diagnostics.emit("launcher", "broker_ready")
                        personal_diagnostics.emit("launcher", "preparation_spawn")
                        preparation = subprocess.Popen(
                            [sys.executable, "-m", "sigma.local_personal", "--prepare"],
                            cwd=ROOT,
                            env=prepare_env,
                            stdin=subprocess.DEVNULL,
                            start_new_session=True,
                        )
                        return cls(runtime, state_root, env, broker, preparation)
                    raise LocalPersonalUnavailable(
                        "Private Personal broker permissions are unsafe."
                    )
                time.sleep(0.1)
            raise LocalPersonalUnavailable(
                "Private Personal container broker did not become ready."
            )
        except BaseException as exc:
            personal_diagnostics.emit("launcher", "startup_failed", failure=type(exc).__name__)
            if preparation is not None and preparation.poll() is None:
                preparation.terminate()
                preparation.wait(timeout=5)
            if broker is not None:
                broker.terminate()
                try:
                    broker.wait(timeout=3)
                except subprocess.TimeoutExpired:
                    broker.kill()
                    broker.wait()
            shutil.rmtree(runtime)
            raise

    def refresh_preparation(self) -> None:
        """Do not leave the dialog preparing forever if its child crashes."""
        if self.preparation.poll() is None:
            return
        marker = self.runtime / "prepare.status"
        try:
            phase = marker.read_text(encoding="ascii").strip()
        except OSError:
            return
        if phase == "preparing":
            personal_diagnostics.emit(
                "launcher",
                "preparation_exited",
                exit_code=self.preparation.returncode,
            )
            _preparation_state(marker, "failed")

    def close(self, progress: Callable[[], None] | None = None) -> None:
        """Stop one shared container while retaining encrypted credential volumes."""
        personal_diagnostics.emit("launcher", "shutdown_begin")
        failure: LocalPersonalUnavailable | None = None
        try:
            if self.preparation.poll() is None:
                try:
                    os.killpg(self.preparation.pid, signal.SIGTERM)
                except ProcessLookupError:
                    pass
                try:
                    self.preparation.wait(timeout=5)
                except subprocess.TimeoutExpired:
                    os.killpg(self.preparation.pid, signal.SIGKILL)
                    self.preparation.wait()
            try:
                _down_shared(self.env)
                if progress is not None:
                    progress()
            except LocalPersonalUnavailable as exc:
                failure = exc
        finally:
            if self.broker.poll() is None:
                self.broker.terminate()
                try:
                    self.broker.wait(timeout=5)
                except subprocess.TimeoutExpired:
                    self.broker.kill()
                    self.broker.wait()
            shutil.rmtree(self.runtime, ignore_errors=True)
            personal_diagnostics.emit("launcher", "shutdown_finished")
        if failure is not None:
            raise LocalPersonalUnavailable(
                "Could not stop the shared Personal container."
            ) from failure


if __name__ == "__main__":
    if sys.argv[1:] != ["--prepare"]:
        raise SystemExit("Unsupported local Personal operation.")
    raise SystemExit(_prepare(dict(os.environ)))
