"""Local counterpart of the production auth-browser Docker service.

Both modes build the same Dockerfile. Localhost is only a transport for SIGMA's
backend -> container API; it is not the OpenAI callback in the user's browser.
"""
from __future__ import annotations

import os
import secrets
import subprocess
from pathlib import Path

from sigma.projects import ROOT

CONTAINER = "sigma-auth-browser-poc-local"
PORT = 18765


def _docker(*args: str, timeout: int = 1200) -> str:
    try:
        process = subprocess.run(
            ["docker", *args], cwd=ROOT, text=True,
            stdout=subprocess.PIPE, stderr=subprocess.PIPE, timeout=timeout,
            check=False,
        )
    except (OSError, subprocess.TimeoutExpired) as exc:
        raise RuntimeError("The Docker authentication experiment could not start.") from exc
    if process.returncode:
        # Docker stderr can contain server or credential detail; do not echo it.
        raise RuntimeError(
            "Docker command failed while preparing the auth-browser experiment. "
            "Verify Docker Desktop is running and Docker images can be built."
        )
    return process.stdout.strip()


def _key_file() -> Path:
    parent = Path.home() / ".sigma" / "auth-browser-poc"
    parent.mkdir(mode=0o700, parents=True, exist_ok=True)
    if parent.is_symlink() or parent.stat().st_uid != os.getuid():
        raise RuntimeError("Unsafe local auth-browser directory")
    os.chmod(parent, 0o700)
    secret = parent / "key"
    if not secret.exists():
        fd = os.open(secret, os.O_WRONLY | os.O_CREAT | os.O_EXCL, 0o600)
        with os.fdopen(fd, "w", encoding="ascii") as output:
            output.write(secrets.token_hex(32) + "\n")
    if secret.is_symlink() or secret.stat().st_uid != os.getuid() or secret.stat().st_mode & 0o077:
        raise RuntimeError("Unsafe local auth-browser key file")
    return secret


def start_local() -> tuple[str, Path]:
    sha = _docker_git_commit()
    backend_image = f"sigma-backend:{sha}"
    image = f"sigma-auth-browser-poc:{sha}"
    if not _has_image(backend_image):
        print("Building SIGMA backend Docker image for the portable OAuth POC...", flush=True)
        _docker("build", "--platform", "linux/amd64", "-t", backend_image,
                "-f", "Dockerfile", ".", timeout=1800)
    if not _has_image(image):
        print("Building Chromium/OAuth Docker image (first run only)...", flush=True)
        _docker("build", "--platform", "linux/amd64", "--build-arg",
                f"SIGMA_RELEASE={sha}", "-t", image, "-f",
                "auth-browser-poc/Dockerfile", ".", timeout=1800)
    key = _key_file()
    stop_local()
    _docker(
        "run", "--detach", "--rm", "--init",
        "--name", CONTAINER, "--platform", "linux/amd64",
        "--publish", f"127.0.0.1:{PORT}:8765",
        "--mount", f"type=bind,source={key},target=/run/secrets/auth_browser_poc_key,readonly",
        "--mount", "type=volume,source=sigma-auth-browser-poc-state,target=/var/lib/sigma-auth",
        "--env", "SIGMA_AUTH_BROWSER_POC_KEY_FILE=/run/secrets/auth_browser_poc_key",
        "--read-only", "--cap-drop=ALL", "--security-opt=no-new-privileges",
        "--memory=1500m", "--cpus=2", "--pids-limit=256",
        "--tmpfs", "/tmp:rw,nosuid,size=512m",
        image,
    )
    return CONTAINER, key


def _docker_git_commit() -> str:
    result = subprocess.run(
        ["git", "rev-parse", "HEAD"], cwd=ROOT, capture_output=True, text=True, check=True
    )
    value = result.stdout.strip()
    if len(value) != 40 or any(c not in "0123456789abcdef" for c in value):
        raise RuntimeError("An exact Git commit is required for the portable OAuth POC")
    return value


def _has_image(image: str) -> bool:
    try:
        return subprocess.run(
            ["docker", "image", "inspect", image], cwd=ROOT,
            capture_output=True, timeout=15, check=False,
        ).returncode == 0
    except (OSError, subprocess.TimeoutExpired):
        return False


def stop_local() -> None:
    try:
        subprocess.run(["docker", "rm", "-f", CONTAINER], capture_output=True,
                       timeout=20, check=False)
    except (OSError, subprocess.TimeoutExpired):
        pass
