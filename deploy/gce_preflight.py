#!/usr/bin/env python3
"""Read-only Ubuntu 24.04 preflight for the SIGMA GCE host contract.

This checker never starts services, changes mounts, invokes Compose up, or reads
secret file contents. Command output is captured and discarded; results contain
only fixed check names and safe status text.
"""

from __future__ import annotations

import argparse
import grp
import json
import os
import pwd
import re
import stat
import subprocess
from collections.abc import Callable
from dataclasses import asdict, dataclass
from pathlib import Path

ENV_FILE = Path("/etc/sigma/deploy.env")
STATE_MOUNT = Path("/srv/sigma-state")
SANDBOX_USER = "sigma-sandbox"
SANDBOX_GROUP = "sigma-sandbox"
SOCKET_TEMPLATE = "/run/user/{uid}/docker.sock"
ALLOWED_ENV_KEYS = {
    "SIGMA_RELEASE",
    "SIGMA_DOMAIN",
    "SIGMA_CADDY_SCHEME",
    "SIGMA_TLS_EMAIL",
    "SIGMA_CLOUD_ADMIN_CONTACT_EMAIL",
    "SIGMA_CLOUD_INFERENCE_PROVIDER",
    "SIGMA_CLOUD_SPONSOR_EMAIL",
    "SIGMA_CLOUD_SPONSORED_ENABLED",
    "SIGMA_CLOUD_FORCE_SPONSORED_MODE",
    "GOOGLE_OIDC_CLIENT_ID",
    "SIGMA_GOOGLE_OIDC_CLIENT_SECRET_FILE",
    "SIGMA_CLOUD_OPENAI_API_KEY_FILE",
    "SIGMA_INVITATION_SMTP_USERNAME",
    "SIGMA_INVITATION_SMTP_PASSWORD_FILE",
    "SIGMA_CLOUD_USER_SPEND_CEILING_USD",
    "SIGMA_CLOUD_GLOBAL_SPEND_CEILING_USD",
    "SIGMA_CLOUD_USER_MAX_CONCURRENT",
    "SIGMA_CLOUD_GLOBAL_MAX_CONCURRENT",
    "SIGMA_CLOUD_USER_MAX_QUEUED",
    "SIGMA_CLOUD_GLOBAL_MAX_QUEUED",
    "SIGMA_CLOUD_USER_TOKEN_BUDGET",
    "SIGMA_SANDBOX_DOCKER_SOCKET",
    "SIGMA_SANDBOX_DOCKER_GID",
    "SIGMA_STATE_DISK_MOUNT",
}


@dataclass(frozen=True)
class Result:
    name: str
    status: str
    detail: str


CommandRunner = Callable[..., subprocess.CompletedProcess[str]]


def _run(
    argv: list[str],
    *,
    timeout: float = 8,
    environment: dict[str, str] | None = None,
) -> subprocess.CompletedProcess[str]:
    return subprocess.run(
        argv,
        check=False,
        capture_output=True,
        text=True,
        timeout=timeout,
        env=environment,
    )


def _parse_env(path: Path) -> tuple[dict[str, str] | None, str]:
    """Parse only simple deploy.env assignments; never evaluate shell syntax."""
    values: dict[str, str] = {}
    try:
        with path.open(encoding="utf-8") as stream:
            for raw_line in stream:
                line = raw_line.strip()
                if not line or line.startswith("#"):
                    continue
                match = re.fullmatch(r"([A-Z][A-Z0-9_]*)=([^\s\"'`$;|&<>]*)", line)
                if not match:
                    return None, "contains unsupported or shell-evaluated syntax"
                key, value = match.groups()
                if key not in ALLOWED_ENV_KEYS:
                    return None, "contains an unsupported setting"
                if key in values:
                    return None, "contains a duplicate setting"
                values[key] = value
    except (OSError, UnicodeError):
        return None, "cannot be read"
    required = {
        "SIGMA_RELEASE",
        "SIGMA_DOMAIN",
        "SIGMA_TLS_EMAIL",
        "SIGMA_CLOUD_ADMIN_CONTACT_EMAIL",
        "GOOGLE_OIDC_CLIENT_ID",
        "SIGMA_GOOGLE_OIDC_CLIENT_SECRET_FILE",
        "SIGMA_CLOUD_OPENAI_API_KEY_FILE",
        "SIGMA_INVITATION_SMTP_USERNAME",
        "SIGMA_INVITATION_SMTP_PASSWORD_FILE",
        "SIGMA_SANDBOX_DOCKER_SOCKET",
        "SIGMA_SANDBOX_DOCKER_GID",
        "SIGMA_STATE_DISK_MOUNT",
    }
    if required - values.keys():
        return None, "is missing required settings"
    if not re.fullmatch(r"[0-9a-fA-F]{40}", values["SIGMA_RELEASE"]):
        return None, "release must be a full 40-character commit SHA"
    if not re.fullmatch(r"[A-Za-z0-9.-]+", values["SIGMA_DOMAIN"]):
        return None, "domain format is invalid"
    provider = values.get("SIGMA_CLOUD_INFERENCE_PROVIDER", "api_key")
    if values.get("SIGMA_CLOUD_SPONSORED_ENABLED", "false") not in {"true", "false"}:
        return None, "sponsored access setting must be true or false"
    if values.get("SIGMA_CLOUD_FORCE_SPONSORED_MODE", "false") not in {"true", "false"}:
        return None, "force sponsored mode setting must be true or false"
    if provider not in {"api_key", "chatgpt"}:
        return None, "inference provider is invalid"
    if provider == "chatgpt" and not re.fullmatch(
        r"[^@\s]+@[^@\s]+", values.get("SIGMA_CLOUD_SPONSOR_EMAIL", "")
    ):
        return None, "ChatGPT sponsor email is required"
    values.setdefault("SIGMA_CADDY_SCHEME", "https")
    if values["SIGMA_CADDY_SCHEME"] not in {"https", "http"}:
        return None, "Caddy scheme is invalid"
    for key in (
        "SIGMA_TLS_EMAIL",
        "SIGMA_CLOUD_ADMIN_CONTACT_EMAIL",
        "SIGMA_INVITATION_SMTP_USERNAME",
    ):
        if not re.fullmatch(r"[^@\s]+@[^@\s]+\.[^@\s]+", values[key]):
            return None, "an email setting is invalid"
    if not values["GOOGLE_OIDC_CLIENT_ID"].endswith(".apps.googleusercontent.com"):
        return None, "Google OAuth client ID format is invalid"
    if values["SIGMA_STATE_DISK_MOUNT"] != str(STATE_MOUNT):
        return None, "state disk mount must use the approved mount path"
    if not values["SIGMA_SANDBOX_DOCKER_GID"].isdigit():
        return None, "sandbox socket group ID must be numeric"
    if not re.fullmatch(r"/run/user/[0-9]+/docker\.sock", values["SIGMA_SANDBOX_DOCKER_SOCKET"]):
        return None, "sandbox socket path is invalid"
    for key in (
        "SIGMA_CLOUD_USER_SPEND_CEILING_USD",
        "SIGMA_CLOUD_GLOBAL_SPEND_CEILING_USD",
    ):
        if key in values and not re.fullmatch(r"[0-9]+(?:\.[0-9]{1,2})?", values[key]):
            return None, "a spend limit is invalid"
    for key in (
        "SIGMA_CLOUD_USER_MAX_CONCURRENT",
        "SIGMA_CLOUD_GLOBAL_MAX_CONCURRENT",
        "SIGMA_CLOUD_USER_MAX_QUEUED",
        "SIGMA_CLOUD_GLOBAL_MAX_QUEUED",
        "SIGMA_CLOUD_USER_TOKEN_BUDGET",
    ):
        if key in values and not values[key].isdigit():
            return None, "a concurrency or token limit is invalid"
    return values, "configuration is syntactically valid"


class Preflight:
    def __init__(
        self,
        env_file: Path = ENV_FILE,
        repository: Path | None = None,
        *,
        command: CommandRunner = _run,
        root: Path = Path("/"),
        host_readiness: bool = False,
        after_reboot: bool = False,
    ) -> None:
        self.env_file = env_file if env_file.is_absolute() else env_file.resolve()
        self.repository = repository or Path(__file__).resolve().parent.parent
        self.command = command
        self.root = root
        self.host_readiness = host_readiness
        self.after_reboot = after_reboot
        self.results: list[Result] = []
        self.values: dict[str, str] = {}

    def add(self, name: str, status: str, detail: str) -> None:
        self.results.append(Result(name, status, detail))

    def _path(self, absolute: str | Path) -> Path:
        path = Path(absolute)
        return self.root / path.relative_to("/") if self.root != Path("/") else path

    def _command(self, name: str, argv: list[str], *, env: dict[str, str] | None = None) -> bool:
        try:
            result = self.command(argv, environment=env)
        except (OSError, subprocess.TimeoutExpired):
            self.add(name, "BLOCKED", "required local command is unavailable")
            return False
        if result.returncode == 0:
            self.add(name, "PASS", "check completed")
            return True
        self.add(name, "FAIL", "check did not pass")
        return False

    def check_platform(self) -> None:
        release = self._path("/etc/os-release")
        try:
            fields = {}
            for line in release.read_text(encoding="utf-8").splitlines():
                if "=" in line:
                    key, value = line.split("=", 1)
                    fields[key] = value.strip().strip('"')
        except OSError:
            self.add("Ubuntu 24.04 host", "BLOCKED", "Linux host identity is unavailable")
            return
        try:
            architecture = os.uname().machine
        except AttributeError:
            architecture = "unsupported"
        if (
            fields.get("ID") == "ubuntu"
            and fields.get("VERSION_ID") == "24.04"
            and architecture in {"x86_64", "amd64"}
        ):
            self.add("Ubuntu 24.04 amd64 host", "PASS", "supported host detected")
        else:
            self.add(
                "Ubuntu 24.04 amd64 host", "BLOCKED", "host does not match the production target"
            )

    def check_env(self) -> None:
        path = self._path(self.env_file)
        try:
            metadata = path.lstat()
        except OSError:
            self.add("Deployment environment", "BLOCKED", "protected deploy.env is not installed")
            return
        if not stat.S_ISREG(metadata.st_mode) or stat.S_ISLNK(metadata.st_mode):
            self.add(
                "Deployment environment", "FAIL", "deploy.env must be a regular non-symlink file"
            )
            return
        try:
            parent = path.parent.lstat()
        except OSError:
            self.add("Deployment environment", "FAIL", "deploy.env parent directory is unavailable")
            return
        if (
            not stat.S_ISDIR(parent.st_mode)
            or stat.S_ISLNK(parent.st_mode)
            or parent.st_uid != 0
            or stat.S_IMODE(parent.st_mode) & 0o027
        ):
            self.add(
                "Deployment environment",
                "FAIL",
                "deploy.env parent directory must be root-owned and private",
            )
            return
        if metadata.st_uid != 0 or stat.S_IMODE(metadata.st_mode) != 0o600:
            self.add(
                "Deployment environment permissions",
                "FAIL",
                "deploy.env must be root-owned mode 0600",
            )
        values, detail = _parse_env(path)
        if values is None:
            self.add("Deployment environment values", "FAIL", detail)
            return
        self.values = values
        self.add("Deployment environment values", "PASS", detail)
        try:
            sandbox = pwd.getpwnam(SANDBOX_USER)
            expected_socket = SOCKET_TEMPLATE.format(uid=sandbox.pw_uid)
            group = grp.getgrnam(SANDBOX_GROUP)
        except KeyError:
            self.add(
                "Sandbox account mapping", "BLOCKED", "dedicated sandbox account is not installed"
            )
            return
        if values["SIGMA_SANDBOX_DOCKER_SOCKET"] != expected_socket:
            self.add(
                "Sandbox account mapping", "FAIL", "configured socket does not match sandbox UID"
            )
        elif int(values["SIGMA_SANDBOX_DOCKER_GID"]) != group.gr_gid:
            self.add(
                "Sandbox account mapping",
                "FAIL",
                "configured socket group does not match sandbox group",
            )
        else:
            self.add(
                "Sandbox account mapping",
                "PASS",
                "socket path and numeric group match the dedicated account",
            )

    def check_secret_files(self) -> None:
        if not self.values:
            self.add("Secret file permissions", "BLOCKED", "valid deploy.env is required")
            return
        directory = self._path("/run/sigma-secrets")
        try:
            directory_stat = directory.lstat()
        except OSError:
            self.add(
                "Secret file permissions",
                "BLOCKED",
                "protected runtime secret files are unavailable",
            )
            return
        if (
            not stat.S_ISDIR(directory_stat.st_mode)
            or stat.S_ISLNK(directory_stat.st_mode)
            or directory_stat.st_uid != 0
            or stat.S_IMODE(directory_stat.st_mode) != 0o700
        ):
            self.add(
                "Secret file permissions",
                "FAIL",
                "runtime secret directory must be root-owned mode 0700",
            )
            return
        try:
            denied = self.command(
                ["runuser", "-u", SANDBOX_USER, "--", "test", "!", "-r", str(directory)],
                environment={"PATH": "/usr/sbin:/usr/bin:/sbin:/bin"},
            )
        except (OSError, subprocess.TimeoutExpired):
            self.add("Secret file isolation", "BLOCKED", "sandbox access check is unavailable")
            return
        if denied.returncode != 0:
            self.add(
                "Secret file isolation",
                "FAIL",
                "sandbox account can read the runtime secret directory",
            )
            return
        self.add(
            "Secret file isolation",
            "PASS",
            "sandbox account cannot read the runtime secret directory",
        )
        for key in (
            "SIGMA_GOOGLE_OIDC_CLIENT_SECRET_FILE",
            "SIGMA_CLOUD_OPENAI_API_KEY_FILE",
            "SIGMA_INVITATION_SMTP_PASSWORD_FILE",
        ):
            configured = Path(self.values[key])
            if not configured.is_absolute() or configured.parent != Path("/run/sigma-secrets"):
                self.add(
                    "Secret file permissions",
                    "FAIL",
                    "secret file path must be a direct child of the protected runtime directory",
                )
                return
            path = self._path(configured)
            try:
                metadata = path.lstat()
            except OSError:
                self.add(
                    "Secret file permissions",
                    "BLOCKED",
                    "a required runtime secret file is unavailable",
                )
                return
            if (
                not stat.S_ISREG(metadata.st_mode)
                or stat.S_ISLNK(metadata.st_mode)
                or metadata.st_uid != 10001
                or metadata.st_gid != 10001
                or stat.S_IMODE(metadata.st_mode) != 0o400
                or metadata.st_size == 0
            ):
                self.add(
                    "Secret file permissions",
                    "FAIL",
                    "runtime secret file owner, mode, or type is unsafe",
                )
                return
        self.add(
            "Secret file permissions",
            "PASS",
            "required runtime files exist with app-only read permissions; contents were not read",
        )

    def check_mount(self) -> None:
        mount = self._path(STATE_MOUNT)
        if mount.is_symlink():
            self.add("Persistent state mount", "FAIL", "state mount path is a symlink")
            return
        try:
            metadata = mount.stat()
        except OSError:
            self.add("Persistent state mount", "BLOCKED", "state mount path is unavailable")
            return
        if not stat.S_ISDIR(metadata.st_mode):
            self.add("Persistent state mount", "FAIL", "state mount path is not a directory")
            return
        if not os.path.ismount(mount):
            self.add(
                "Persistent state mount",
                "FAIL",
                "persistent disk is not mounted at the approved path",
            )
            return
        expected_source = self._mount_identity(mount, fstab=True)
        actual_source = self._mount_identity(mount, fstab=False)
        if expected_source is None or actual_source is None:
            self.add(
                "Persistent state source",
                "FAIL",
                "mounted state disk must have a UUID-backed fstab entry",
            )
            return
        if expected_source[:2] != actual_source[:2]:
            self.add(
                "Persistent state source",
                "FAIL",
                "mounted state filesystem does not match its persistent fstab entry",
            )
            return
        required_mount_options = {"nodev", "nosuid", "noexec"}
        if any(
            not required_mount_options.issubset(set(source[2].split(",")))
            for source in (expected_source, actual_source)
        ):
            self.add(
                "Persistent state options",
                "FAIL",
                "fstab and mounted state disk must use nodev, nosuid, and noexec",
            )
            return
        if not re.fullmatch(
            r"[0-9a-fA-F]{8}-[0-9a-fA-F]{4}-[0-9a-fA-F]{4}-[0-9a-fA-F]{4}-[0-9a-fA-F]{12}",
            actual_source[0],
        ) or actual_source[1] not in {"ext4", "xfs"}:
            self.add(
                "Persistent state source",
                "FAIL",
                "mounted state source is not a supported UUID-backed disk filesystem",
            )
            return
        self.add(
            "Persistent state source",
            "PASS",
            "mounted filesystem matches its UUID-backed fstab entry",
        )
        self.add(
            "Persistent state mount", "PASS", "persistent disk is mounted at the approved path"
        )
        if metadata.st_uid != 0 or stat.S_IMODE(metadata.st_mode) & 0o077:
            self.add(
                "Persistent state mount permissions",
                "FAIL",
                "mounted filesystem root must be root-owned and private",
            )
        else:
            self.add(
                "Persistent state mount permissions",
                "PASS",
                "mounted filesystem root is root-owned and private",
            )
        try:
            sandbox = pwd.getpwnam(SANDBOX_USER)
            denied = self.command(
                ["runuser", "-u", SANDBOX_USER, "--", "test", "!", "-r", str(mount)],
                environment={"PATH": "/usr/sbin:/usr/bin:/sbin:/bin"},
            )
        except (KeyError, OSError, subprocess.TimeoutExpired):
            self.add("Sandbox state isolation", "BLOCKED", "sandbox access check is unavailable")
            return
        del sandbox
        if denied.returncode == 0:
            self.add(
                "Sandbox state isolation",
                "PASS",
                "sandbox account cannot read the mounted state root",
            )
        else:
            self.add(
                "Sandbox state isolation", "FAIL", "sandbox account can read the mounted state root"
            )

    def _mount_identity(self, mount: Path, *, fstab: bool) -> tuple[str, str, str] | None:
        if fstab:
            arguments = [
                "findmnt",
                "--fstab",
                "--evaluate",
                "--noheadings",
                "--output",
                "UUID,FSTYPE,OPTIONS",
                "--target",
                str(mount),
            ]
        else:
            arguments = [
                "findmnt",
                "--mountpoint",
                str(mount),
                "--noheadings",
                "--output",
                "UUID,FSTYPE,OPTIONS",
            ]
        try:
            result = self.command(
                arguments,
                environment={"PATH": "/usr/sbin:/usr/bin:/sbin:/bin"},
            )
        except (OSError, subprocess.TimeoutExpired):
            return None
        values = result.stdout.split()
        if result.returncode != 0 or len(values) != 3:
            return None
        return values[0].lower(), values[1], values[2]

    def check_services(self) -> None:
        for unit in (
            "docker.service",
            "user@" + str(_sandbox_uid()) + ".service",
            "sigma-sandbox.service",
        ):
            self._command("Systemd " + unit, ["systemctl", "is-active", "--quiet", unit])
        if self.host_readiness:
            for unit in ("docker.service", "sigma-sandbox.service"):
                self._command(
                    "Enabled for reboot " + unit,
                    ["systemctl", "is-enabled", "--quiet", unit],
                )
            try:
                linger = self.command(
                    ["loginctl", "show-user", "--property=Linger", "--value", SANDBOX_USER],
                    environment={"PATH": "/usr/bin:/bin"},
                )
            except (OSError, subprocess.TimeoutExpired):
                self.add("Sandbox linger across reboot", "BLOCKED", "loginctl is unavailable")
            else:
                if linger.returncode == 0 and linger.stdout.strip().casefold() == "yes":
                    self.add(
                        "Sandbox linger across reboot",
                        "PASS",
                        "dedicated user manager persists across logout and reboot",
                    )
                else:
                    self.add(
                        "Sandbox linger across reboot",
                        "FAIL",
                        "dedicated user manager is not configured to persist",
                    )

    def check_host_daemon(self) -> None:
        try:
            result = self.command(
                ["docker", "info", "--format", "{{json .SecurityOptions}}"],
                environment={"PATH": "/usr/bin:/bin", "HOME": "/root"},
            )
        except (OSError, subprocess.TimeoutExpired):
            self.add("Host Docker Engine", "BLOCKED", "Docker CLI or host daemon is unavailable")
            return
        if result.returncode != 0:
            self.add("Host Docker Engine", "FAIL", "host Compose daemon did not answer")
            return
        try:
            options = json.loads(result.stdout)
        except (json.JSONDecodeError, TypeError):
            self.add(
                "Host Docker Engine", "FAIL", "host daemon security mode could not be verified"
            )
            return
        if any("rootless" in str(item).casefold() for item in options):
            self.add(
                "Host Docker Engine", "FAIL", "Compose daemon must remain the system Docker Engine"
            )
        else:
            self.add(
                "Host Docker Engine",
                "PASS",
                "system Compose daemon is separate from rootless research daemon",
            )

    def check_rootless_daemon(self) -> None:
        socket = self._sandbox_socket()
        if socket is None:
            self.add(
                "Rootless sandbox daemon", "BLOCKED", "dedicated sandbox account is unavailable"
            )
            return
        try:
            result = self.command(
                self._rootless_docker_argv(socket, "info", "--format", "{{json .SecurityOptions}}"),
                environment={"PATH": "/usr/bin:/bin", "HOME": "/root"},
            )
        except (OSError, subprocess.TimeoutExpired):
            self.add(
                "Rootless sandbox daemon", "BLOCKED", "Docker CLI or sandbox daemon is unavailable"
            )
            return
        if result.returncode != 0:
            self.add("Rootless sandbox daemon", "FAIL", "dedicated daemon did not answer")
            return
        try:
            options = json.loads(result.stdout)
        except (json.JSONDecodeError, TypeError):
            self.add(
                "Rootless sandbox daemon", "FAIL", "daemon security mode could not be verified"
            )
            return
        if not any("rootless" in str(item).casefold() for item in options):
            self.add(
                "Rootless sandbox daemon", "FAIL", "dedicated daemon does not report rootless mode"
            )
            return
        self.add("Rootless sandbox daemon", "PASS", "dedicated daemon reports rootless mode")

    def check_socket(self) -> None:
        socket = self._sandbox_socket()
        if socket is None:
            self.add(
                "Sandbox socket permissions", "BLOCKED", "dedicated sandbox account is unavailable"
            )
            return
        path = self._path(socket)
        try:
            metadata = path.lstat()
        except OSError:
            self.add(
                "Sandbox socket permissions", "BLOCKED", "rootless Docker socket is unavailable"
            )
            return
        try:
            sandbox_account = pwd.getpwnam(SANDBOX_USER)
            expected_uid = sandbox_account.pw_uid
            expected_gid = grp.getgrnam(SANDBOX_GROUP).gr_gid
        except KeyError:
            self.add(
                "Sandbox socket permissions",
                "BLOCKED",
                "dedicated sandbox account is not installed",
            )
            return
        if not stat.S_ISSOCK(metadata.st_mode):
            self.add("Sandbox socket permissions", "FAIL", "configured path is not a Unix socket")
        elif (metadata.st_uid, metadata.st_gid, stat.S_IMODE(metadata.st_mode)) != (
            expected_uid,
            expected_gid,
            0o660,
        ):
            self.add(
                "Sandbox socket permissions",
                "FAIL",
                "socket owner, group, or mode is not the approved 0660 sandbox setting",
            )
        else:
            self.add(
                "Sandbox socket permissions",
                "PASS",
                "socket is sandbox-owned and group-readable/writable only",
            )
        groups = set(os.getgrouplist(SANDBOX_USER, sandbox_account.pw_gid))
        for denied_group in ("docker", "sudo"):
            try:
                gid = grp.getgrnam(denied_group).gr_gid
            except KeyError:
                continue
            if gid in groups:
                self.add(
                    "Sandbox privilege boundary",
                    "FAIL",
                    "sandbox account belongs to a privileged host group",
                )
                return
        self.add(
            "Sandbox privilege boundary", "PASS", "sandbox account is not in docker or sudo groups"
        )

    def check_runtime_images(self) -> None:
        socket = self._sandbox_socket()
        if socket is None:
            self.add(
                "Python/Sage runner images", "BLOCKED", "dedicated sandbox account is unavailable"
            )
            return
        for image in ("sigma-research-python:0.1", "sigma-research-sage:10.8"):
            self._command(
                "Rootless image " + image,
                self._rootless_docker_argv(socket, "image", "inspect", image),
                env={"PATH": "/usr/bin:/bin", "HOME": "/root"},
            )

    @staticmethod
    def _rootless_docker_argv(socket: str, *arguments: str) -> list[str]:
        """Run rootless Docker as its socket owner with inherited contexts cleared."""
        uid = _sandbox_uid()
        return [
            "/usr/sbin/runuser",
            "--user",
            SANDBOX_USER,
            "--",
            "/usr/bin/env",
            "PATH=/usr/bin:/bin",
            "HOME=/home/sigma-sandbox",
            f"XDG_RUNTIME_DIR=/run/user/{uid}",
            "DOCKER_CONFIG=/etc/docker",
            "DOCKER_HOST=",
            "DOCKER_CONTEXT=",
            "docker",
            "--host",
            f"unix://{socket}",
            *arguments,
        ]

    def check_compose(self) -> None:
        if not self.values:
            self.add("Production Compose configuration", "BLOCKED", "valid deploy.env is required")
            return
        argv = [
            "docker",
            "compose",
            "--project-name",
            "sigma",
            "--env-file",
            str(self._path(self.env_file)),
            "-f",
            str(self.repository / "deploy/compose.yaml"),
            "-f",
            str(self.repository / "deploy/compose.gce.yaml"),
            "config",
            "--format",
            "json",
        ]
        try:
            result = self.command(
                argv,
                environment={
                    "PATH": "/usr/bin:/bin",
                    "HOME": "/root",
                    "DOCKER_CONFIG": "/root/.docker",
                },
            )
        except (OSError, subprocess.TimeoutExpired):
            self.add(
                "Production Compose configuration", "BLOCKED", "Docker Compose v2 is unavailable"
            )
            return
        if result.returncode != 0:
            self.add(
                "Production Compose configuration",
                "FAIL",
                "merged production Compose configuration is invalid",
            )
            return
        try:
            configuration = json.loads(result.stdout)
            services = configuration["services"]
            volumes = configuration["volumes"]
            backend = services["backend"]
            socket_mount = next(
                volume
                for volume in backend["volumes"]
                if volume.get("target") == "/run/sigma-sandbox/docker.sock"
            )
            state = volumes["sigma-state"]["driver_opts"]["device"]
            backend_groups = {str(group) for group in backend.get("group_add", [])}
            configured_gid = self.values["SIGMA_SANDBOX_DOCKER_GID"]
            backend_healthcheck = backend["healthcheck"]
            frontend_healthcheck = services["frontend"]["healthcheck"]
            edge_healthcheck = services["edge"]["healthcheck"]
            edge_dependencies = services["edge"]["depends_on"]
            valid = (
                {"backend", "frontend", "edge"}.issubset(services)
                and backend.get("read_only") is True
                and configured_gid in backend_groups
                and socket_mount.get("source") == self.values["SIGMA_SANDBOX_DOCKER_SOCKET"]
                and socket_mount.get("read_only") is True
                and state == "/srv/sigma-state/auth"
                and not services["backend"].get("ports")
                and not services["frontend"].get("ports")
                and bool(services["edge"].get("ports"))
                and bool(backend_healthcheck.get("test"))
                and bool(frontend_healthcheck.get("test"))
                and bool(edge_healthcheck.get("test"))
                and all(
                    edge_dependencies[name].get("condition") == "service_healthy"
                    for name in ("backend", "frontend")
                )
            )
        except (KeyError, TypeError, ValueError, json.JSONDecodeError):
            valid = False
        if valid:
            self.add(
                "Production Compose configuration",
                "PASS",
                "Caddy, backend, and frontend healthchecks, healthy edge dependencies, persistent state bind, and read-only rootless socket are configured",
            )
        else:
            self.add(
                "Production Compose configuration",
                "FAIL",
                "merged stack does not satisfy the production host and socket contract",
            )

    def check_app_unit(self) -> None:
        unit = self._path("/etc/systemd/system/sigma.service")
        try:
            metadata = unit.lstat()
            content = unit.read_text(encoding="utf-8")
        except OSError:
            self.add("SIGMA systemd service", "BLOCKED", "installed systemd unit is unavailable")
            return
        if (
            not stat.S_ISREG(metadata.st_mode)
            or stat.S_ISLNK(metadata.st_mode)
            or metadata.st_uid != 0
            or stat.S_IMODE(metadata.st_mode) & 0o022
        ):
            self.add(
                "SIGMA systemd service",
                "FAIL",
                "systemd unit must be a root-owned non-symlink file",
            )
            return
        required = (
            "Restart=on-failure",
            "SIGMA_DEPLOY_ENV_FILE=/etc/sigma/deploy.env",
            "SIGMA_STATE_DISK_MOUNT=/srv/sigma-state",
            "RequiresMountsFor=/srv/sigma-state",
            "/opt/sigma/current/deploy/start-gce.sh",
            "gce_preflight.py",
        )
        if all(item in content for item in required):
            self.add(
                "SIGMA systemd service",
                "PASS",
                "restart, mount ordering, preflight, and guarded startup are configured",
            )
        else:
            self.add(
                "SIGMA systemd service",
                "FAIL",
                "systemd unit does not satisfy the startup contract",
            )

    def run(self) -> list[Result]:
        self.check_platform()
        if self.results[-1].status != "PASS":
            self.add(
                "Ubuntu production host checks",
                "BLOCKED",
                "remaining checks require Ubuntu 24.04 amd64; no host services were inspected",
            )
            return self.results
        if os.geteuid() == 0:
            self.add("Host inspection privilege", "PASS", "preflight runs as root")
        else:
            self.add(
                "Host inspection privilege",
                "BLOCKED",
                "run preflight as root for complete host checks",
            )
        self.check_mount()
        self.check_services()
        if self.host_readiness:
            self.check_host_daemon()
            self.check_rootless_daemon()
            self.check_socket()
            self.check_runtime_images()
            self._command("Docker Compose v2", ["docker", "compose", "version"])
            self._command(
                "Systemd unit syntax",
                [
                    "systemd-analyze",
                    "verify",
                    "/etc/systemd/system/sigma-sandbox.service",
                    "/etc/systemd/system/sigma.service",
                ],
            )
            self.check_app_unit()
            if self.after_reboot:
                self.add(
                    "Reboot recovery scope",
                    "PASS" if all(r.status == "PASS" for r in self.results) else "BLOCKED",
                    "persistent mount and enabled host/rootless services checked; production sigma.service is intentionally not required",
                )
            return self.results
        self.check_env()
        self.check_secret_files()
        self.check_socket()
        self.check_host_daemon()
        self.check_rootless_daemon()
        self.check_runtime_images()
        self._command("Docker Compose v2", ["docker", "compose", "version"])
        self.check_compose()
        self.check_app_unit()
        self._command(
            "Systemd unit syntax",
            [
                "systemd-analyze",
                "verify",
                "/etc/systemd/system/sigma.service",
                "/etc/systemd/system/sigma-sandbox.service",
            ],
        )
        return self.results

    def _sandbox_socket(self) -> str | None:
        configured = self.values.get("SIGMA_SANDBOX_DOCKER_SOCKET")
        if configured:
            return configured
        if self.host_readiness:
            uid = _sandbox_uid()
            return SOCKET_TEMPLATE.format(uid=uid) if uid >= 0 else None
        return None


def _sandbox_uid() -> int:
    try:
        return pwd.getpwnam(SANDBOX_USER).pw_uid
    except KeyError:
        return -1


def result_exit_code(results: list[Result]) -> int:
    """Return failure when a check failed, blocked when readiness is incomplete."""
    if any(result.status == "FAIL" for result in results):
        return 1
    if any(result.status == "BLOCKED" for result in results):
        return 2
    return 0


def main() -> int:
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("--env-file", type=Path, default=ENV_FILE)
    parser.add_argument("--repository", type=Path)
    parser.add_argument(
        "--host-readiness",
        action="store_true",
        help="check Ubuntu, persistent mount, Docker/rootless sandbox and runner images without T129 deploy.env or credentials",
    )
    parser.add_argument(
        "--after-reboot",
        action="store_true",
        help="include the explicit reboot recovery gate (implies --host-readiness)",
    )
    parser.add_argument("--json", action="store_true", help="emit only safe status fields as JSON")
    args = parser.parse_args()
    results = Preflight(
        env_file=args.env_file,
        repository=args.repository,
        host_readiness=args.host_readiness or args.after_reboot,
        after_reboot=args.after_reboot,
    ).run()
    if args.json:
        print(json.dumps([asdict(result) for result in results], indent=2))
    else:
        for result in results:
            print(f"{result.status}: {result.name} — {result.detail}")
    return result_exit_code(results)


if __name__ == "__main__":
    raise SystemExit(main())
