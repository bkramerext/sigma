"""Local --prod supervisor for SIGMA's isolated Personal browser experiment.

Only the developer's local SIGMA launcher starts this broker. It enables real local authorization only in the explicitly local --prod
workflow, never publishes a browser port, and never applies
the local Docker UID overlay on hosted infrastructure.
"""

from __future__ import annotations

import hashlib
import os
import re
import secrets
import signal
import shutil
import stat
import subprocess
import sys
import tempfile
import time
from collections.abc import Callable
from dataclasses import dataclass
from pathlib import Path

ROOT = Path(__file__).resolve().parents[2]
WORKSPACE = re.compile(r"[0-9a-f]{32}\Z")
RELEASE = re.compile(r"[0-9a-f]{40}\Z")
CHECKOUT = re.compile(r"[0-9a-f]{32}\Z")
COMPOSE_FILES = (
    "deploy/auth-poc.compose.yaml",
    "deploy/auth-poc.gce.yaml",
    "deploy/auth-poc.user.gce.yaml",
    "deploy/auth-poc.user.local.yaml",
)


class LocalPersonalUnavailable(RuntimeError):
    """The optional local Docker Personal browser cannot be started safely."""


def _command(args: list[str], *, env: dict[str, str], timeout: int = 90) -> str:
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
        raise LocalPersonalUnavailable("Local Personal container preparation failed.") from exc
    if result.returncode:
        # Docker output can include credentials/host paths; keep errors generic.
        raise LocalPersonalUnavailable(
            "Local Personal container preparation failed. Check Docker Desktop."
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
    """Choose the platform before building and validate existing release tags."""
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
    env["SIGMA_AUTH_POC_BROWSER_PLATFORM"] = platform
    if build and not _images_compatible(env):
        print("Preparing isolated Personal ChatGPT images for this Mac…", flush=True)
        _command(
            ["docker", "compose", "-f", "deploy/auth-poc.compose.yaml", "build"],
            env=env,
            timeout=900,
        )
        for name in ("sigma-auth-poc", "sigma-auth-browser-poc"):
            _command(
                ["docker", "tag", name + ":local", name + ":" + release],
                env=env,
                timeout=20,
            )
        if not _images_compatible(env):
            raise LocalPersonalUnavailable(
                "The Personal browser images were built for the wrong architecture."
            )
    return release, platform


def _images_compatible(env: dict[str, str]) -> bool:
    """Reject cached images with the right SHA but the wrong architecture."""
    for name, desired in (
        ("sigma-auth-poc", "linux/amd64"),
        ("sigma-auth-browser-poc", env["SIGMA_AUTH_POC_BROWSER_PLATFORM"]),
    ):
        try:
            actual = _command(
                [
                    "docker",
                    "image",
                    "inspect",
                    "--format",
                    "{{.Os}}/{{.Architecture}}",
                    name + ":" + env["SIGMA_RELEASE"],
                ],
                env=env,
                timeout=10,
            )
        except LocalPersonalUnavailable:
            return False
        if actual != desired:
            return False
    return True


def _checkout_id() -> str:
    # Stable across SIGMA restarts, and does not expose the checkout path.
    return hashlib.sha256(str(ROOT.resolve()).encode()).hexdigest()[:32]


def _owned_workspaces(env: dict[str, str]) -> set[str]:
    """Recover only Docker projects labeled for this checkout and local UID."""
    checkout = env.get("SIGMA_AUTH_POC_CHECKOUT_ID", "")
    if not CHECKOUT.fullmatch(checkout):
        raise LocalPersonalUnavailable("Private checkout identity is invalid.")
    result = _command(
        [
            "docker",
            "ps",
            "-a",
            "--filter",
            "label=io.sigma.personal.checkout=" + checkout,
            "--filter",
            "label=io.sigma.personal.owner=" + str(os.geteuid()),
            "--format",
            '{{.Label "com.docker.compose.project"}}',
        ],
        env=env,
        timeout=20,
    )
    workspaces: set[str] = set()
    for name in result.splitlines():
        if name.startswith("sigma-personal-"):
            workspace = name.removeprefix("sigma-personal-")
            if WORKSPACE.fullmatch(workspace):
                workspaces.add(workspace)
    return workspaces


def _down_workspace(env: dict[str, str], workspace: str) -> None:
    if not WORKSPACE.fullmatch(workspace):
        raise LocalPersonalUnavailable("Unsafe Personal Docker project identifier.")
    compose_env = {
        **env,
        "SIGMA_STATE_DISK_MOUNT": str(
            Path(env["SIGMA_AUTH_BROKER_STATE_ROOT"]) / workspace
        ),
        "SIGMA_AUTH_POC_WORKSPACE_ID": workspace,
        "SIGMA_AUTH_POC_GATEWAY_DIR": str(
            Path(env["SIGMA_AUTH_BROKER_GATEWAY_ROOT"]) / workspace
        ),
        "SIGMA_AUTH_POC_LOCAL_UID": str(os.geteuid()),
        "SIGMA_AUTH_POC_LOCAL_GID": str(os.getegid()),
    }
    _command(
        [
            "docker",
            "compose",
            "--project-name",
            "sigma-personal-" + workspace,
            *(part for filename in COMPOSE_FILES for part in ("-f", filename)),
            "down",
            "--remove-orphans",
        ],
        env=compose_env,
        timeout=45,
    )


def _preparation_state(path: Path, state: str) -> None:
    if state not in {"preparing", "ready", "failed"}:
        raise ValueError("Invalid local preparation state.")
    temporary = path.with_suffix(".next")
    temporary.write_text(state, encoding="ascii")
    temporary.chmod(0o600)
    temporary.replace(path)


def _prepare(env: dict[str, str]) -> int:
    """Reconcile crashed launchers and build missing images off the UI path."""
    marker = Path(env["SIGMA_LOCAL_PERSONAL_PREPARATION_FILE"])
    try:
        for workspace in sorted(_owned_workspaces(env)):
            _down_workspace(env, workspace)
        _release_images(env)
        _preparation_state(marker, "ready")
        print("Personal ChatGPT browser preparation complete.", flush=True)
        return 0
    except (OSError, RuntimeError, ValueError, KeyError) as exc:
        _preparation_state(marker, "failed")
        print("Personal ChatGPT preparation failed: " + str(exc), file=sys.stderr)
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
        env = _docker_environment()
        release, platform = _release_images(env, build=False)
        # Use the established real local preview state. SIGMA --prod must
        # preserve the account already authorized through the old launcher.
        state_root = Path.home() / ".sigma" / "personal-signin-preview-state"
        _private_directory(state_root, 0o700)
        runtime = Path(tempfile.mkdtemp(prefix="sigma-personal-local-"))
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
                    "SIGMA_AUTH_BROKER_STATE_ROOT": str(state_root),
                    "SIGMA_AUTH_BROKER_GATEWAY_ROOT": str(runtime / "gateways"),
                    "SIGMA_AUTH_BROKER_SOCKET": str(runtime / "broker" / "broker.sock"),
                    "SIGMA_AUTH_BROKER_CLIENT_UID": str(os.geteuid()),
                    "SIGMA_AUTH_POC_BROWSER_PLATFORM": platform,
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
            broker = subprocess.Popen(
                [sys.executable, str(ROOT / "auth-poc" / "host_broker.py")],
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
        except BaseException:
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

    def close(self, progress: Callable[[], None] | None = None) -> None:
        """Stop verified SIGMA Docker projects, without deleting OAuth state."""
        failures: list[str] = []
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
            gateway_root = self.runtime / "gateways"
            workspaces: set[str] = set()
            if gateway_root.is_dir():
                workspaces = {
                    gateway.name
                    for gateway in gateway_root.iterdir()
                    if WORKSPACE.fullmatch(gateway.name)
                    and gateway.is_dir()
                    and not gateway.is_symlink()
                }
            try:
                workspaces |= _owned_workspaces(self.env)
            except LocalPersonalUnavailable:
                failures.append("Could not discover all Personal Docker containers.")
            for workspace in sorted(workspaces):
                try:
                    _down_workspace(self.env, workspace)
                except LocalPersonalUnavailable:
                    failures.append("Could not stop a Personal Docker container.")
                if progress is not None:
                    progress()
        finally:
            if self.broker.poll() is None:
                self.broker.terminate()
                try:
                    self.broker.wait(timeout=5)
                except subprocess.TimeoutExpired:
                    self.broker.kill()
                    self.broker.wait()
            shutil.rmtree(self.runtime, ignore_errors=True)
        if failures:
            raise LocalPersonalUnavailable(" ".join(failures))


if __name__ == "__main__":
    if sys.argv[1:] != ["--prepare"]:
        raise SystemExit("Unsupported local Personal operation.")
    raise SystemExit(_prepare(dict(os.environ)))
