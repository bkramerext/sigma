"""Local --prod supervisor for SIGMA's isolated Personal browser experiment.

Only the developer's local SIGMA launcher starts this broker. It enables real local authorization only in the explicitly local --prod
workflow, never publishes a browser port, and never applies
the local Docker UID overlay on hosted infrastructure.
"""

from __future__ import annotations

import os
import re
import secrets
import shutil
import stat
import subprocess
import sys
import tempfile
import time
from dataclasses import dataclass
from pathlib import Path

ROOT = Path(__file__).resolve().parents[2]
WORKSPACE = re.compile(r"[0-9a-f]{32}\Z")
RELEASE = re.compile(r"[0-9a-f]{40}\Z")
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


def _release_images(env: dict[str, str]) -> tuple[str, str]:
    release = _command(["git", "rev-parse", "--verify", "HEAD"], env=env, timeout=10)
    if not RELEASE.fullmatch(release):
        raise LocalPersonalUnavailable("Unable to identify a pinned SIGMA release.")
    architecture = _command(
        ["docker", "info", "--format", "{{.Architecture}}"], env=env, timeout=15
    )
    platform = {
        "arm64": "linux/arm64",
        "aarch64": "linux/arm64",
        "amd64": "linux/amd64",
        "x86_64": "linux/amd64",
    }.get(architecture)
    if platform is None:
        raise LocalPersonalUnavailable("Docker Desktop architecture is unsupported.")
    # Reuse the exact current checkout's images on subsequent starts.
    tags = ("sigma-auth-poc:" + release, "sigma-auth-browser-poc:" + release)
    if any(
        subprocess.run(
            ["docker", "image", "inspect", tag],
            cwd=ROOT,
            env=env,
            stdout=subprocess.DEVNULL,
            stderr=subprocess.DEVNULL,
            timeout=10,
            check=False,
        ).returncode
        != 0
        for tag in tags
    ):
        print("Preparing isolated Personal ChatGPT containers…", flush=True)
        _command(
            ["docker", "compose", "-f", "deploy/auth-poc.compose.yaml", "build"],
            env=env,
            timeout=900,
        )
        for image, tag in zip(
            ("sigma-auth-poc:local", "sigma-auth-browser-poc:local"), tags, strict=True
        ):
            _command(["docker", "tag", image, tag], env=env, timeout=15)
    return release, platform


@dataclass
class LocalPersonalRuntime:
    """Owns the broker, ephemeral relays and container lifetime for one launch."""

    runtime: Path
    state_root: Path
    env: dict[str, str]
    broker: subprocess.Popen[bytes]

    @classmethod
    def start(cls) -> LocalPersonalRuntime:
        env = _docker_environment()
        release, platform = _release_images(env)
        # Use the established real local preview state. SIGMA --prod must
        # preserve the account already authorized through the old launcher.
        state_root = Path.home() / ".sigma" / "personal-signin-preview-state"
        _private_directory(state_root, 0o700)
        runtime = Path(tempfile.mkdtemp(prefix="sigma-personal-local-"))
        broker: subprocess.Popen[bytes] | None = None
        try:
            _private_directory(runtime / "broker", 0o711)
            _private_directory(runtime / "gateways", 0o711)
            env.update(
                {
                    "SIGMA_RELEASE": release,
                    "SIGMA_AUTH_BROKER_LOCAL_POC": "1",
                    "SIGMA_AUTH_BROKER_STATE_ROOT": str(state_root),
                    "SIGMA_AUTH_BROKER_GATEWAY_ROOT": str(runtime / "gateways"),
                    "SIGMA_AUTH_BROKER_SOCKET": str(runtime / "broker" / "broker.sock"),
                    "SIGMA_AUTH_BROKER_CLIENT_UID": str(os.geteuid()),
                    "SIGMA_AUTH_POC_BROWSER_PLATFORM": platform,
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
                        return cls(runtime, state_root, env, broker)
                    raise LocalPersonalUnavailable(
                        "Private Personal broker permissions are unsafe."
                    )
                time.sleep(0.1)
            raise LocalPersonalUnavailable(
                "Private Personal container broker did not become ready."
            )
        except BaseException:
            if broker is not None:
                broker.terminate()
                try:
                    broker.wait(timeout=3)
                except subprocess.TimeoutExpired:
                    broker.kill()
                    broker.wait()
            shutil.rmtree(runtime)
            raise

    def close(self) -> None:
        # Keep saved auth state; remove only ephemeral containers and sockets.
        try:
            gateway_root = self.runtime / "gateways"
            if gateway_root.is_dir():
                for gateway in gateway_root.iterdir():
                    if (
                        not WORKSPACE.fullmatch(gateway.name)
                        or not gateway.is_dir()
                        or gateway.is_symlink()
                    ):
                        continue
                    workspace = gateway.name
                    env = {
                        **self.env,
                        "SIGMA_STATE_DISK_MOUNT": str(self.state_root / workspace),
                        "SIGMA_AUTH_POC_WORKSPACE_ID": workspace,
                        "SIGMA_AUTH_POC_GATEWAY_DIR": str(gateway),
                        "SIGMA_AUTH_POC_LOCAL_UID": str(os.geteuid()),
                        "SIGMA_AUTH_POC_LOCAL_GID": str(os.getegid()),
                    }
                    try:
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
                            env=env,
                            timeout=45,
                        )
                    except LocalPersonalUnavailable:
                        print(
                            "Warning: a Personal browser container could not be stopped.",
                            file=sys.stderr,
                        )
        finally:
            if self.broker.poll() is None:
                self.broker.terminate()
                try:
                    self.broker.wait(timeout=5)
                except subprocess.TimeoutExpired:
                    self.broker.kill()
                    self.broker.wait()
            shutil.rmtree(self.runtime, ignore_errors=True)
