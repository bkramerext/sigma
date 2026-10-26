"""Deploy one reviewed SIGMA commit on the prepared GCE host.

Checks and image builds happen before the release pin or service changes. This
script never edits credentials or state data. Upgrades require explicit backup
and schema-compatibility assertions because code rollback cannot undo migration.
"""

from __future__ import annotations

import argparse
import json
import os
import re
import stat
import subprocess
import sys
import tempfile
import time
from collections.abc import Callable
from pathlib import Path

REPOSITORY = Path("/opt/sigma/current")
ENV_FILE = Path("/etc/sigma/deploy.env")
PREFLIGHT = Path("/usr/local/libexec/sigma/gce_preflight.py")
SHA_RE = re.compile(r"[0-9a-f]{40}")
Runner = Callable[..., subprocess.CompletedProcess[str]]


class DeployFailure(RuntimeError):
    pass


def _run(argv: list[str], **kwargs: object) -> subprocess.CompletedProcess[str]:
    return subprocess.run(argv, text=True, capture_output=True, check=False, **kwargs)


def _call(runner: Runner, argv: list[str], *, env: dict[str, str] | None = None) -> str:
    try:
        result = runner(argv, env=env)
    except (OSError, subprocess.TimeoutExpired) as error:
        raise DeployFailure(f"command unavailable or timed out: {argv[0]}") from error
    if result.returncode:
        # Command output may contain credentials, user data, or provider errors.
        # Keep diagnostics safe and direct operators to the relevant journal.
        raise DeployFailure(
            f"command failed ({argv[0]}, exit {result.returncode}); raw output withheld to protect secrets and user data"
        )
    return result.stdout.strip()


def _read_release(path: Path, owner: int = 0) -> tuple[bytes, str]:
    try:
        metadata = path.lstat()
        content = path.read_bytes()
    except OSError as error:
        raise DeployFailure("protected deploy.env is missing or unreadable") from error
    if not stat.S_ISREG(metadata.st_mode) or stat.S_ISLNK(metadata.st_mode):
        raise DeployFailure("deploy.env must be a regular file, not a symlink")
    if metadata.st_uid != owner or stat.S_IMODE(metadata.st_mode) != 0o600:
        raise DeployFailure("deploy.env must be root-owned mode 0600")
    try:
        lines = content.decode("utf-8").splitlines(keepends=True)
    except UnicodeError as error:
        raise DeployFailure("deploy.env is not valid UTF-8") from error
    matches = [line for line in lines if line.startswith("SIGMA_RELEASE=")]
    if len(matches) != 1:
        raise DeployFailure("deploy.env must contain exactly one SIGMA_RELEASE")
    current = matches[0].partition("=")[2].strip()
    if not SHA_RE.fullmatch(current):
        raise DeployFailure("configured SIGMA_RELEASE is invalid")
    return content, current


def _replace_release(path: Path, content: bytes, sha: str, owner: int = 0) -> None:
    try:
        lines = content.decode("utf-8").splitlines(keepends=True)
    except UnicodeError as error:
        raise DeployFailure("deploy.env is not valid UTF-8") from error
    replaced = False
    for index, line in enumerate(lines):
        if line.startswith("SIGMA_RELEASE="):
            lines[index] = f"SIGMA_RELEASE={sha}\n"
            replaced = True
    if not replaced:
        raise DeployFailure("deploy.env release pin disappeared")
    fd, name = tempfile.mkstemp(prefix=".deploy.env.", dir=path.parent)
    try:
        with os.fdopen(fd, "w", encoding="utf-8") as stream:
            stream.writelines(lines)
            stream.flush()
            os.fsync(stream.fileno())
        os.chown(name, owner, -1)
        os.chmod(name, 0o600)
        os.replace(name, path)
        directory_fd = os.open(path.parent, os.O_RDONLY | os.O_DIRECTORY)
        try:
            os.fsync(directory_fd)
        finally:
            os.close(directory_fd)
    except OSError as error:
        raise DeployFailure("atomic deploy.env update failed") from error
    finally:
        if os.path.exists(name):
            os.unlink(name)


class Deployment:
    def __init__(
        self,
        repository: Path,
        env_file: Path,
        preflight: Path,
        runner: Runner = _run,
        root_check: bool = True,
    ) -> None:
        self.repository, self.env_file, self.preflight = repository, env_file, preflight
        self.runner, self.root_check = runner, root_check

    def check_preflight(self) -> None:
        argv = [
            "python3",
            str(self.preflight),
            "--json",
            "--repository",
            str(self.repository),
            "--env-file",
            str(self.env_file),
        ]
        try:
            result = self.runner(argv)
        except (OSError, subprocess.TimeoutExpired) as error:
            raise DeployFailure("host preflight command is unavailable or timed out") from error
        if result.returncode:
            safe_failures = []
            try:
                rows = json.loads(result.stdout)
                safe_failures = [
                    f"{row['status']} {row['name']}: {row['detail']}"
                    for row in rows
                    if row.get("status") != "PASS"
                ]
            except (json.JSONDecodeError, KeyError, TypeError):
                pass
            summary = "; ".join(safe_failures[:8]) or "no safe check summary available"
            raise DeployFailure(f"host preflight failed (exit {result.returncode}): {summary}")

    def deploy(
        self, sha: str, backup_verified: bool, schema_compatible: bool, initial: bool = False
    ) -> str:
        if not SHA_RE.fullmatch(sha):
            raise DeployFailure("release must be a full lowercase 40-character commit SHA")
        if self.root_check and os.geteuid() != 0:
            raise DeployFailure("run this command with sudo on the prepared GCE host")
        owner = 0 if self.root_check else os.geteuid()
        original_env, old_sha = _read_release(self.env_file, owner)
        if sha == old_sha and not initial:
            self.check_preflight()
            self.verify_health(sha)
            print(f"PASS: release {sha} is already configured; no changes made")
            return "unchanged"
        if not initial and (not backup_verified or not schema_compatible):
            raise DeployFailure("upgrade requires --backup-verified and --schema-compatible")

        self.check_preflight()
        if initial:
            try:
                active = self.runner(["systemctl", "is-active", "--quiet", "sigma.service"])
            except (OSError, subprocess.TimeoutExpired) as error:
                raise DeployFailure("cannot inspect initial service state") from error
            if active.returncode == 0:
                raise DeployFailure("--initial requires sigma.service to be inactive")
            try:
                enabled = self.runner(["systemctl", "is-enabled", "--quiet", "sigma.service"])
            except (OSError, subprocess.TimeoutExpired) as error:
                raise DeployFailure("cannot inspect initial service enablement") from error
            if enabled.returncode == 0:
                raise DeployFailure("--initial requires sigma.service to be disabled")
        dirty = _call(self.runner, ["git", "-C", str(self.repository), "status", "--porcelain"])
        if dirty:
            raise DeployFailure("release checkout has local changes; refusing deployment")
        _call(self.runner, ["git", "-C", str(self.repository), "fetch", "--no-tags", "origin", sha])
        _call(
            self.runner, ["git", "-C", str(self.repository), "cat-file", "-e", f"{sha}^{{commit}}"]
        )
        previous = _call(self.runner, ["git", "-C", str(self.repository), "rev-parse", "HEAD"])
        if not SHA_RE.fullmatch(previous):
            raise DeployFailure("current checkout does not identify a full commit SHA")
        if not initial and previous != old_sha:
            raise DeployFailure("current checkout and configured release pin disagree")

        # Build from a git-archive of the exact requested commit and attach
        # source-SHA labels; never build a requested tag from the active checkout.
        service_stopped = False
        candidate_started = False
        candidate_checkout_changed = False
        release_pin_changed = False
        try:
            _call(
                self.runner,
                [
                    "python3",
                    str(self.repository / "deploy/release_image.py"),
                    "build",
                    str(self.repository),
                    sha,
                ],
            )
            if not initial:
                _call(self.runner, ["systemctl", "stop", "sigma.service"])
                service_stopped = True
            _call(self.runner, ["git", "-C", str(self.repository), "checkout", "--detach", sha])
            candidate_checkout_changed = True
            _replace_release(self.env_file, original_env, sha, owner)
            self.check_preflight()
            _call(self.runner, ["systemctl", "start", "sigma.service"])
            service_stopped = False
            candidate_started = True
            self.verify_health(sha)
            if initial:
                _call(self.runner, ["systemctl", "enable", "sigma.service"])
        except DeployFailure as failure:
            # A build failure occurs before the active checkout, release pin, or
            # service changes. Leave the running release entirely untouched.
            if not (
                service_stopped
                or candidate_started
                or candidate_checkout_changed
                or release_pin_changed
            ):
                raise
            # Restore the code and release pin atomically, preserving every other
            # deploy.env byte. Existing disk state and credentials are untouched.
            try:
                _replace_release(self.env_file, self.env_file.read_bytes(), previous, owner)
                _call(
                    self.runner,
                    ["git", "-C", str(self.repository), "checkout", "--detach", previous],
                )
                if initial:
                    _call(self.runner, ["systemctl", "stop", "sigma.service"])
                    _call(self.runner, ["systemctl", "disable", "sigma.service"])
                elif service_stopped:
                    _call(self.runner, ["systemctl", "start", "sigma.service"])
                elif candidate_started:
                    _call(self.runner, ["systemctl", "restart", "sigma.service"])
                if not initial:
                    self.verify_health(previous)
            except (DeployFailure, OSError) as recovery_error:
                raise DeployFailure(
                    f"{failure}; automatic recovery also failed; keep ingress closed and inspect systemd journal"
                ) from recovery_error
            raise DeployFailure(
                f"{failure}; prior code and release pin restored and service restart attempted"
            ) from failure
        print(
            f"PASS: release {sha} started; container health, service release and state mount verified"
        )
        return "deployed"

    def verify_health(self, sha: str) -> None:
        compose = [
            "docker",
            "compose",
            "--project-name",
            "sigma",
            "--env-file",
            str(self.env_file),
            "-f",
            str(self.repository / "deploy/compose.yaml"),
            "-f",
            str(self.repository / "deploy/compose.gce.yaml"),
        ]
        deadline = time.monotonic() + 180
        while True:
            waiting_for: list[str] = []
            for service in ("backend", "frontend", "edge"):
                container = _call(self.runner, compose + ["ps", "-q", service])
                if not container:
                    waiting_for.append(service)
                    continue
                status = _call(
                    self.runner,
                    ["docker", "inspect", "--format", "{{.State.Health.Status}}", container],
                )
                if status != "healthy":
                    waiting_for.append(service)
                    continue
                image = _call(
                    self.runner,
                    ["docker", "inspect", "--format", "{{.Config.Image}}", container],
                )
                expected_image = f"sigma-{service}:{sha}" if service != "edge" else None
                if expected_image and image != expected_image:
                    raise DeployFailure(
                        f"{service} container image does not match selected release"
                    )
                if expected_image:
                    source_sha = _call(
                        self.runner,
                        [
                            "docker",
                            "inspect",
                            "--format",
                            '{{ index .Config.Labels "org.opencontainers.image.revision" }}',
                            container,
                        ],
                    )
                    if source_sha != sha:
                        raise DeployFailure(
                            f"{service} image source label does not match selected release"
                        )
            if not waiting_for:
                break
            if time.monotonic() >= deadline:
                raise DeployFailure(
                    "container health timed out after 180 seconds: " + ", ".join(waiting_for)
                )
            time.sleep(5)
        actual = _call(self.runner, ["git", "-C", str(self.repository), "rev-parse", "HEAD"])
        if actual != sha:
            raise DeployFailure("active checkout release identity does not match selected SHA")
        _call(self.runner, ["findmnt", "--mountpoint", "/srv/sigma-state"])
        _call(self.runner, ["test", "-d", "/srv/sigma-state/auth"])
        active = _call(self.runner, ["systemctl", "is-active", "sigma.service"])
        if active != "active":
            raise DeployFailure("sigma.service is not active after launch")


def main() -> int:
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("release_sha")
    parser.add_argument(
        "--initial",
        action="store_true",
        help="first application start; requires service currently inactive",
    )
    parser.add_argument("--backup-verified", action="store_true")
    parser.add_argument("--schema-compatible", action="store_true")
    parser.add_argument("--repository", type=Path, default=REPOSITORY)
    parser.add_argument("--env-file", type=Path, default=ENV_FILE)
    parser.add_argument("--preflight", type=Path, default=PREFLIGHT)
    args = parser.parse_args()
    try:
        Deployment(args.repository, args.env_file, args.preflight).deploy(
            args.release_sha, args.backup_verified, args.schema_compatible, args.initial
        )
    except DeployFailure as error:
        print(f"FAIL: {error}", file=sys.stderr)
        return 1
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
