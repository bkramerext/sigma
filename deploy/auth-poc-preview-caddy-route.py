"""Prepare or remove the runtime-owned Caddy overlay for issue #874."""

from __future__ import annotations

import argparse
import hashlib
import json
import os
import re
import shutil
import stat
from pathlib import Path

SITE = "{$SIGMA_CADDY_SCHEME}://{$SIGMA_DOMAIN} {\n"
ENV_FILE = Path("/etc/sigma/personal-lab.env")
RUNTIME_ROOT = Path("/var/lib/sigma-personal-lab/runtime")
KEY_NAME = "SIGMA_PERSONAL_LAB_EDGE_KEY"
KEY_PATTERN = re.compile(r"[A-Za-z0-9_-]{40,128}\Z")
MANIFEST = ".sigma-personal-lab-runtime.json"


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
    """Add an import for the external secret-free preview snippet."""
    if KEY_PATTERN.fullmatch(edge_key) is None:
        raise ValueError("Preview edge key is malformed")
    if b"@personal_lab path" in current or b"import /etc/caddy/personal-lab.caddy" in current:
        raise ValueError("Preview route is already present")
    if current.count(SITE.encode()) != 1:
        raise ValueError("Production Caddy site marker is missing or ambiguous")
    if b"@api path /api /api/*" not in current:
        raise ValueError("Production API route does not match the reviewed baseline")
    decoded = snippet.decode("utf-8")
    placeholder = "{$SIGMA_PERSONAL_LAB_EDGE_KEY}"
    if decoded.count(placeholder) != 1:
        raise ValueError("Preview Caddy snippet has an unexpected edge-key placeholder")
    if edge_key in decoded:
        raise ValueError("Preview Caddy snippet must not contain the edge key")
    import_line = b"\timport /etc/caddy/personal-lab.caddy\n"
    return current.replace(SITE.encode(), SITE.encode() + import_line, 1)


def _write_atomic(path: Path, contents: bytes, mode: int) -> None:
    temp = path.with_name(path.name + ".tmp")
    if temp.exists() or temp.is_symlink():
        raise ValueError("Refusing pre-existing temporary preview config")
    descriptor = os.open(
        temp,
        os.O_WRONLY | os.O_CREAT | os.O_EXCL | getattr(os, "O_NOFOLLOW", 0),
        mode,
    )
    try:
        os.fchmod(descriptor, mode)
        with os.fdopen(descriptor, "wb", closefd=False) as output:
            output.write(contents)
            output.flush()
            os.fsync(descriptor)
        os.replace(temp, path)
        dir_fd = os.open(path.parent, os.O_RDONLY | getattr(os, "O_DIRECTORY", 0))
        try:
            os.fsync(dir_fd)
        finally:
            os.close(dir_fd)
    finally:
        os.close(descriptor)
        if temp.exists():
            temp.unlink()


def write_runtime_config(current: bytes, snippet: bytes, edge_key: str, root: Path) -> None:
    """Write only runtime-owned Caddy files; never mutate the release checkout."""
    if root.exists() or root.is_symlink():
        raise ValueError("Preview runtime config directory already exists")
    caddyfile = render(current, snippet, edge_key)
    # Ensure the key is passed only as a protected Compose environment value.
    if edge_key.encode() in caddyfile or edge_key.encode() in snippet:
        raise ValueError("Preview edge key must not be written to runtime config")
    manifest = (
        json.dumps(
            {
                "caddyfile_sha256": hashlib.sha256(caddyfile).hexdigest(),
                "snippet_sha256": hashlib.sha256(snippet).hexdigest(),
                "release_caddyfile_sha256": hashlib.sha256(current).hexdigest(),
            },
            sort_keys=True,
        ).encode("ascii")
        + b"\n"
    )
    staging = root.with_name(root.name + ".staging")
    if staging.exists() or staging.is_symlink():
        raise ValueError("Preview runtime staging directory already exists")
    staging.mkdir(mode=0o700, parents=False)
    try:
        _write_atomic(staging / "Caddyfile", caddyfile, 0o644)
        _write_atomic(staging / "personal-lab.caddy", snippet, 0o644)
        _write_atomic(staging / MANIFEST, manifest, 0o600)
        os.replace(staging, root)
        parent_fd = os.open(root.parent, os.O_RDONLY | getattr(os, "O_DIRECTORY", 0))
        try:
            os.fsync(parent_fd)
        finally:
            os.close(parent_fd)
    except BaseException:
        shutil.rmtree(staging, ignore_errors=True)
        raise


def install(caddyfile: Path, snippet: Path, env_file: Path, runtime_root: Path) -> None:
    if os.geteuid() != 0:
        raise PermissionError("Caddy preview installation requires root")
    caddy_info = _private_regular_file(caddyfile)
    if caddy_info.st_uid != 0:
        raise ValueError("Production Caddyfile must be root-owned")
    snippet_info = _private_regular_file(snippet)
    if snippet_info.st_uid != 0:
        raise ValueError("Pinned preview Caddy snippet must be root-owned")
    edge_key = _read_edge_key(env_file)
    if runtime_root.is_symlink():
        raise ValueError("Preview runtime config directory must not be a symlink")
    if runtime_root.exists():
        raise ValueError("Preview runtime config directory already exists")
    parent = runtime_root.parent
    if parent.is_symlink():
        raise ValueError("Preview runtime parent must not be a symlink")
    if parent.exists():
        parent_info = parent.stat()
        if parent_info.st_uid != 0 or stat.S_IMODE(parent_info.st_mode) != 0o700:
            raise ValueError("Existing preview runtime parent must be root-owned mode 0700")
    else:
        parent.mkdir(mode=0o700, parents=False)
        os.chown(parent, 0, 0)
    parent_info = parent.stat()
    if parent_info.st_uid != 0 or stat.S_IMODE(parent_info.st_mode) != 0o700:
        raise ValueError("Preview runtime parent must be root-owned mode 0700")
    write_runtime_config(caddyfile.read_bytes(), snippet.read_bytes(), edge_key, runtime_root)


def rollback(runtime_root: Path, *, require_root: bool = True) -> None:
    """Remove the runtime overlay after the edge is restarted without it."""
    if require_root and os.geteuid() != 0:
        raise PermissionError("Caddy preview rollback requires root")
    if runtime_root.is_symlink():
        raise ValueError("Preview runtime directory must not be a symlink")
    info = runtime_root.stat()
    if (require_root and info.st_uid != 0) or stat.S_IMODE(info.st_mode) != 0o700:
        raise ValueError("Preview runtime directory must be root-owned mode 0700")
    manifest_path = runtime_root / MANIFEST
    manifest_info = _private_regular_file(manifest_path)
    if (require_root and manifest_info.st_uid != 0) or stat.S_IMODE(manifest_info.st_mode) != 0o600:
        raise ValueError("Preview runtime manifest must be root-owned mode 0600")
    manifest = json.loads(manifest_path.read_text(encoding="ascii"))
    expected_files = {
        "Caddyfile": manifest["caddyfile_sha256"],
        "personal-lab.caddy": manifest["snippet_sha256"],
    }
    if {path.name for path in runtime_root.iterdir()} != set(expected_files) | {MANIFEST}:
        raise ValueError("Preview runtime directory has unexpected files")
    for name, expected_hash in expected_files.items():
        path = runtime_root / name
        file_info = _private_regular_file(path)
        if (require_root and file_info.st_uid != 0) or stat.S_IMODE(file_info.st_mode) != 0o644:
            raise ValueError("Preview runtime config file ownership or mode changed")
        if hashlib.sha256(path.read_bytes()).hexdigest() != expected_hash:
            raise ValueError("Preview runtime config changed since installation")
        path.unlink()
    manifest_path.unlink()
    runtime_root.rmdir()


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
    install_parser.add_argument("--runtime-root", type=Path, default=RUNTIME_ROOT)
    rollback_parser = commands.add_parser("rollback")
    rollback_parser.add_argument("--runtime-root", type=Path, default=RUNTIME_ROOT)
    args = parser.parse_args()
    if args.command == "install":
        install(args.caddyfile, args.snippet, args.env_file, args.runtime_root)
        print("PASS: prepared runtime-owned preview Caddy overlay; release checkout unchanged")
    else:
        rollback(args.runtime_root)
        print("PASS: removed preview Caddy overlay; restart edge without preview overlay")


if __name__ == "__main__":
    main()
