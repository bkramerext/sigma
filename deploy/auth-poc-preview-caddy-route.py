"""Install or restore the temporary same-host Caddy route for issue #874."""

from __future__ import annotations

import argparse
import os
import re
import stat
from datetime import UTC, datetime
from pathlib import Path

SITE = "{$SIGMA_CADDY_SCHEME}://{$SIGMA_DOMAIN} {\n"
BACKUP_ROOT = Path("/var/backups/sigma-personal-lab")
ENV_FILE = Path("/etc/sigma/personal-lab.env")
KEY_NAME = "SIGMA_PERSONAL_LAB_EDGE_KEY"
KEY_PATTERN = re.compile(r"[A-Za-z0-9_-]{40,128}\Z")


def _private_regular_file(path: Path) -> os.stat_result:
    if path.is_symlink():
        raise ValueError("Refusing symlinked preview deployment file")
    info = path.stat()
    if not stat.S_ISREG(info.st_mode):
        raise ValueError("Preview deployment path is not a regular file")
    return info


def _read_edge_key(path: Path) -> str:
    info = _private_regular_file(path)
    if info.st_uid != 0 or stat.S_IMODE(info.st_mode) != 0o600:
        raise ValueError("Preview environment file must be root-owned mode 0600")
    values: dict[str, str] = {}
    for line in path.read_text(encoding="utf-8").splitlines():
        if not line or line.lstrip().startswith("#"):
            continue
        name, separator, value = line.partition("=")
        if separator and name:
            values[name] = value
    key = values.get(KEY_NAME, "")
    if not KEY_PATTERN.fullmatch(key):
        raise ValueError("Preview edge key is missing or malformed")
    return key


def render(current: bytes, snippet: bytes, edge_key: str) -> bytes:
    if KEY_PATTERN.fullmatch(edge_key) is None:
        raise ValueError("Preview edge key is malformed")
    if b"@personal_lab path" in current:
        raise ValueError("Preview route is already present")
    if current.count(SITE.encode()) != 1:
        raise ValueError("Production Caddy site marker is missing or ambiguous")
    if b"@api path /api /api/*" not in current:
        raise ValueError("Production API route does not match the reviewed baseline")
    decoded = snippet.decode("utf-8")
    placeholder = "{$SIGMA_PERSONAL_LAB_EDGE_KEY}"
    if decoded.count(placeholder) != 1:
        raise ValueError("Preview Caddy snippet has an unexpected edge-key placeholder")
    safe_snippet = decoded.replace(placeholder, edge_key).encode("utf-8")
    return current.replace(SITE.encode(), SITE.encode() + safe_snippet + b"\n", 1)


def _write_in_place(path: Path, contents: bytes, mode: int) -> None:
    descriptor = os.open(path, os.O_WRONLY | os.O_TRUNC | getattr(os, "O_NOFOLLOW", 0))
    try:
        os.fchown(descriptor, 0, 0)
        os.fchmod(descriptor, mode)
        with os.fdopen(descriptor, "wb", closefd=False) as output:
            output.write(contents)
            output.flush()
            os.fsync(descriptor)
    finally:
        os.close(descriptor)


def install(caddyfile: Path, snippet: Path, env_file: Path, backup_root: Path) -> Path:
    if os.geteuid() != 0:
        raise PermissionError("Caddy preview installation requires root")
    caddy_info = _private_regular_file(caddyfile)
    if caddy_info.st_uid != 0:
        raise ValueError("Production Caddyfile must be root-owned")
    snippet_info = _private_regular_file(snippet)
    if snippet_info.st_uid != 0:
        raise ValueError("Pinned preview Caddy snippet must be root-owned")
    original = caddyfile.read_bytes()
    updated = render(original, snippet.read_bytes(), _read_edge_key(env_file))
    if updated == original:
        raise ValueError("Preview route produced no Caddy configuration change")
    if backup_root.is_symlink():
        raise ValueError("Preview backup directory must not be a symlink")
    backup_root.mkdir(mode=0o700, parents=True, exist_ok=True)
    os.chown(backup_root, 0, 0)
    os.chmod(backup_root, 0o700)
    backup_info = backup_root.stat()
    if backup_info.st_uid != 0 or stat.S_IMODE(backup_info.st_mode) != 0o700:
        raise ValueError("Preview backup directory must be root-owned mode 0700")
    timestamp = datetime.now(UTC).strftime("%Y%m%dT%H%M%SZ")
    backup = backup_root / f"Caddyfile.{timestamp}.pre-personal-lab"
    flags = os.O_WRONLY | os.O_CREAT | os.O_EXCL | getattr(os, "O_NOFOLLOW", 0)
    descriptor = os.open(backup, flags, 0o600)
    with os.fdopen(descriptor, "wb") as output:
        output.write(original)
        output.flush()
        os.fsync(output.fileno())
    mode_file = backup.with_suffix(backup.suffix + ".mode")
    mode_descriptor = os.open(mode_file, flags, 0o600)
    with os.fdopen(mode_descriptor, "w", encoding="ascii") as output:
        output.write(f"{stat.S_IMODE(caddy_info.st_mode):04o}\n")
        output.flush()
        os.fsync(output.fileno())
    _write_in_place(caddyfile, updated, 0o600)
    return backup


def rollback(caddyfile: Path, backup: Path, backup_root: Path) -> None:
    if os.geteuid() != 0:
        raise PermissionError("Caddy preview rollback requires root")
    _private_regular_file(caddyfile)
    backup_info = _private_regular_file(backup)
    if backup_root.is_symlink():
        raise ValueError("Caddy rollback directory must not be a symlink")
    root_info = backup_root.stat()
    if root_info.st_uid != 0 or stat.S_IMODE(root_info.st_mode) != 0o700:
        raise ValueError("Caddy rollback directory must be root-owned mode 0700")
    if not backup.resolve().is_relative_to(backup_root.resolve()):
        raise ValueError("Caddy rollback backup is outside the protected directory")
    if backup_info.st_uid != 0 or stat.S_IMODE(backup_info.st_mode) != 0o600:
        raise ValueError("Caddy rollback backup must be root-owned mode 0600")
    mode_file = backup.with_suffix(backup.suffix + ".mode")
    mode_info = _private_regular_file(mode_file)
    if mode_info.st_uid != 0 or stat.S_IMODE(mode_info.st_mode) != 0o600:
        raise ValueError("Caddy rollback mode record must be root-owned mode 0600")
    raw_mode = mode_file.read_text(encoding="ascii").strip()
    if not re.fullmatch(r"0[0-7]{3}", raw_mode):
        raise ValueError("Caddy rollback mode record is invalid")
    _write_in_place(caddyfile, backup.read_bytes(), int(raw_mode, 8))


def main() -> None:
    parser = argparse.ArgumentParser()
    commands = parser.add_subparsers(dest="command", required=True)
    install_parser = commands.add_parser("install")
    install_parser.add_argument(
        "--caddyfile", type=Path, default=Path("/opt/sigma/current/deploy/Caddyfile")
    )
    install_parser.add_argument(
        "--snippet",
        type=Path,
        default=Path("/opt/sigma/personal-lab/release/deploy/auth-poc.preview.caddy"),
    )
    install_parser.add_argument("--env-file", type=Path, default=ENV_FILE)
    install_parser.add_argument("--backup-root", type=Path, default=BACKUP_ROOT)
    rollback_parser = commands.add_parser("rollback")
    rollback_parser.add_argument("backup", type=Path)
    rollback_parser.add_argument(
        "--caddyfile", type=Path, default=Path("/opt/sigma/current/deploy/Caddyfile")
    )
    rollback_parser.add_argument("--backup-root", type=Path, default=BACKUP_ROOT)
    args = parser.parse_args()
    if args.command == "install":
        backup = install(args.caddyfile, args.snippet, args.env_file, args.backup_root)
        print(str(backup))
    else:
        rollback(args.caddyfile, args.backup, args.backup_root)
        print("PASS: restored original Caddy configuration")


if __name__ == "__main__":
    main()
