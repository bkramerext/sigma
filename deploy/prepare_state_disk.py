#!/usr/bin/env python3
"""Prepare the already-formatted GCE state disk for durable SIGMA mounts.

This tool never formats, wipes, or copies a disk. The operator supplies its
owner-confirmed filesystem UUID after verifying the GCE attachment.
"""

from __future__ import annotations

import argparse
import os
import re
import shutil
import stat
import subprocess
import sys
import tempfile
from pathlib import Path

MOUNTPOINT = Path("/srv/sigma-state")
FSTAB = Path("/etc/fstab")
FSTAB_BACKUP = Path("/etc/fstab.sigma-t128.bak")
SUPPORTED_FILESYSTEMS = {"ext4", "xfs"}
UUID_PATTERN = re.compile(
    r"[0-9a-fA-F]{8}-[0-9a-fA-F]{4}-[0-9a-fA-F]{4}-[0-9a-fA-F]{4}-[0-9a-fA-F]{12}"
)
HARDENED_OPTIONS = (
    "rw",
    "nodev",
    "nosuid",
    "noexec",
    "nofail",
    "x-systemd.device-timeout=60s",
)
OVERRIDDEN_OPTIONS = {"ro", "dev", "suid", "exec", "noauto", "user", "users"}


def validate_uuid(value: str) -> str:
    if not UUID_PATTERN.fullmatch(value):
        raise ValueError("filesystem UUID must use the standard 8-4-4-4-12 form")
    return value.lower()


def plan_fstab(contents: str, uuid: str, filesystem: str) -> str:
    """Return an idempotent UUID mount entry or reject ambiguous fstab state."""
    normalized_uuid = validate_uuid(uuid)
    if filesystem not in SUPPORTED_FILESYSTEMS:
        raise ValueError("state disk filesystem must be ext4 or xfs")
    source = f"UUID={normalized_uuid}"
    rows: list[tuple[int, list[str]]] = []
    for number, raw in enumerate(contents.splitlines(), start=1):
        line = raw.split("#", 1)[0].strip()
        if line:
            fields = re.split(r"\s+", line)
            if len(fields) < 6:
                raise ValueError(f"fstab line {number} is incomplete")
            rows.append((number, fields))

    targets = [(number, fields) for number, fields in rows if fields[1] == str(MOUNTPOINT)]
    uuid_rows = [
        (number, fields) for number, fields in rows if fields[0].casefold() == source.casefold()
    ]
    if len(targets) > 1:
        raise ValueError("state mountpoint is configured more than once")
    if len(uuid_rows) > 1:
        raise ValueError("state filesystem UUID is configured more than once")
    if uuid_rows and uuid_rows[0][1][1] != str(MOUNTPOINT):
        raise ValueError("state filesystem UUID is already configured at another mountpoint")

    if targets:
        number, fields = targets[0]
        if fields[0].casefold() != source.casefold():
            raise ValueError("state mountpoint is configured for a different filesystem")
        if fields[2] != filesystem:
            raise ValueError("state mountpoint filesystem type does not match the disk")
        existing = [option for option in fields[3].split(",") if option]
        options = [option for option in existing if option not in OVERRIDDEN_OPTIONS]
        for option in HARDENED_OPTIONS:
            if option not in options:
                options.append(option)
        fields[3] = ",".join(options)
        updated = "\t".join(fields[:6])
        lines = contents.splitlines()
        lines[number - 1] = updated
        result = "\n".join(lines)
        return result + ("\n" if contents.endswith("\n") or result else "")

    line = "\t".join(
        (
            source,
            str(MOUNTPOINT),
            filesystem,
            ",".join(("defaults", *HARDENED_OPTIONS)),
            "0",
            "2" if filesystem == "ext4" else "0",
        )
    )
    prefix = contents
    if prefix and not prefix.endswith("\n"):
        prefix += "\n"
    return prefix + line + "\n"


def _run(argv: list[str]) -> subprocess.CompletedProcess[str]:
    try:
        return subprocess.run(argv, check=False, capture_output=True, text=True, timeout=15)
    except (OSError, subprocess.TimeoutExpired) as exc:
        raise RuntimeError("required host command is unavailable or timed out") from exc


def _command_output(argv: list[str], failure: str) -> str:
    result = _run(argv)
    if result.returncode:
        raise RuntimeError(failure)
    return result.stdout.strip()


def _require_ubuntu_2404() -> None:
    try:
        fields = {}
        for line in Path("/etc/os-release").read_text(encoding="utf-8").splitlines():
            if "=" in line:
                key, value = line.split("=", 1)
                fields[key] = value.strip().strip('"')
    except OSError as exc:
        raise RuntimeError("Ubuntu host identity is unavailable") from exc
    if fields.get("ID") != "ubuntu" or fields.get("VERSION_ID") != "24.04":
        raise RuntimeError("host must be Ubuntu 24.04 LTS")
    if os.uname().machine not in {"x86_64", "amd64"}:
        raise RuntimeError("host must be amd64")


def _check_regular_root_file(path: Path, description: str, *, max_mode: int) -> os.stat_result:
    try:
        metadata = path.lstat()
    except OSError as exc:
        raise RuntimeError(f"{description} is unavailable") from exc
    if (
        not stat.S_ISREG(metadata.st_mode)
        or stat.S_ISLNK(metadata.st_mode)
        or metadata.st_uid != 0
        or stat.S_IMODE(metadata.st_mode) & max_mode
    ):
        raise RuntimeError(f"{description} must be a protected root-owned regular file")
    return metadata


def _write_fstab(path: Path, contents: str, metadata: os.stat_result) -> None:
    backup = FSTAB_BACKUP
    if backup.exists() or backup.is_symlink():
        _check_regular_root_file(backup, "existing fstab backup", max_mode=0o022)
    else:
        shutil.copy2(path, backup)
    descriptor, temporary = tempfile.mkstemp(prefix=".fstab.sigma-t128.", dir=path.parent)
    try:
        os.fchown(descriptor, metadata.st_uid, metadata.st_gid)
        os.fchmod(descriptor, stat.S_IMODE(metadata.st_mode))
        with os.fdopen(descriptor, "w", encoding="utf-8") as stream:
            stream.write(contents)
            stream.flush()
            os.fsync(stream.fileno())
        os.replace(temporary, path)
        directory = os.open(path.parent, os.O_RDONLY)
        try:
            os.fsync(directory)
        finally:
            os.close(directory)
    finally:
        if os.path.exists(temporary):
            os.unlink(temporary)


def prepare(uuid_argument: str) -> None:
    if os.geteuid() != 0:
        raise RuntimeError("run this preparation as root on the target VM")
    _require_ubuntu_2404()
    uuid = validate_uuid(uuid_argument)
    device = _command_output(["blkid", "--uuid", uuid], "filesystem UUID is not attached")
    try:
        if not stat.S_ISBLK(Path(device).stat().st_mode):
            raise RuntimeError("filesystem UUID did not resolve to a block device")
    except OSError as exc:
        raise RuntimeError("filesystem UUID did not resolve to a block device") from exc
    actual_uuid = _command_output(
        ["blkid", "--output", "value", "--match-tag", "UUID", device],
        "could not verify the attached filesystem UUID",
    ).lower()
    if actual_uuid != uuid:
        raise RuntimeError("attached filesystem UUID did not match the supplied UUID")
    filesystem = _command_output(
        ["blkid", "--output", "value", "--match-tag", "TYPE", device],
        "could not verify the attached filesystem type",
    )
    if filesystem not in SUPPORTED_FILESYSTEMS:
        raise RuntimeError("state disk filesystem must be ext4 or xfs")

    parent = MOUNTPOINT.parent
    try:
        parent_metadata = parent.lstat()
    except OSError as exc:
        raise RuntimeError("/srv is unavailable") from exc
    if (
        stat.S_ISLNK(parent_metadata.st_mode)
        or not stat.S_ISDIR(parent_metadata.st_mode)
        or parent_metadata.st_uid != 0
        or stat.S_IMODE(parent_metadata.st_mode) & 0o022
    ):
        raise RuntimeError("/srv must be a real directory")
    try:
        mount_metadata = MOUNTPOINT.lstat()
    except FileNotFoundError:
        MOUNTPOINT.mkdir(mode=0o700)
        mount_metadata = MOUNTPOINT.lstat()
    if stat.S_ISLNK(mount_metadata.st_mode) or not stat.S_ISDIR(mount_metadata.st_mode):
        raise RuntimeError("state mountpoint must be a real directory")

    mounted_target_result = _run(
        ["findmnt", "--noheadings", "--output", "TARGET", "--mountpoint", str(MOUNTPOINT)]
    )
    is_mounted = mounted_target_result.returncode == 0 and bool(
        mounted_target_result.stdout.strip()
    )
    if mounted_target_result.returncode not in (0, 1):
        raise RuntimeError("could not inspect the current state mount")
    if is_mounted:
        mounted_uuid_result = _run(
            ["findmnt", "--noheadings", "--output", "UUID", "--mountpoint", str(MOUNTPOINT)]
        )
        if mounted_uuid_result.returncode != 0:
            raise RuntimeError("could not verify filesystem mounted at the state mountpoint")
        if mounted_uuid_result.stdout.strip().lower() != uuid:
            raise RuntimeError("a different filesystem is already mounted at the state mountpoint")
        current_options = set(
            _command_output(
                ["findmnt", "--noheadings", "--output", "OPTIONS", "--mountpoint", str(MOUNTPOINT)],
                "could not inspect state mount options",
            ).split(",")
        )
        if not {"nodev", "nosuid", "noexec"}.issubset(current_options):
            raise RuntimeError("mounted state filesystem lacks nodev, nosuid, or noexec")
    else:
        try:
            if next(MOUNTPOINT.iterdir(), None) is not None:
                raise RuntimeError("unmounted state mountpoint is not empty")
        except OSError as exc:
            raise RuntimeError("could not inspect the unmounted state mountpoint") from exc
        other_mount = _run(
            ["findmnt", "--noheadings", "--output", "TARGET", "--source", f"UUID={uuid}"]
        )
        if other_mount.returncode == 0 and other_mount.stdout.strip():
            raise RuntimeError("state filesystem is already mounted at another path")
        if other_mount.returncode not in (0, 1):
            raise RuntimeError("could not inspect existing mounts for the state filesystem")

    fstab_metadata = _check_regular_root_file(FSTAB, "/etc/fstab", max_mode=0o022)
    try:
        original = FSTAB.read_text(encoding="utf-8")
    except (OSError, UnicodeError) as exc:
        raise RuntimeError("/etc/fstab cannot be read") from exc
    updated = plan_fstab(original, uuid, filesystem)
    if updated != original:
        _write_fstab(FSTAB, updated, fstab_metadata)
    _command_output(["systemctl", "daemon-reload"], "systemd could not reload mount units")

    os.chown(MOUNTPOINT, 0, 0)
    os.chmod(MOUNTPOINT, 0o700)
    if not is_mounted:
        _command_output(["mount", str(MOUNTPOINT)], "state disk could not be mounted")
    mounted_uuid = _command_output(
        ["findmnt", "--noheadings", "--output", "UUID", "--mountpoint", str(MOUNTPOINT)],
        "state filesystem is not mounted at the approved mountpoint",
    ).lower()
    if mounted_uuid != uuid:
        raise RuntimeError("mounted filesystem UUID does not match the requested state disk")
    mounted_options = set(
        _command_output(
            ["findmnt", "--noheadings", "--output", "OPTIONS", "--mountpoint", str(MOUNTPOINT)],
            "could not verify state mount options",
        ).split(",")
    )
    if not {"nodev", "nosuid", "noexec"}.issubset(mounted_options):
        raise RuntimeError("mounted state filesystem lacks nodev, nosuid, or noexec")
    os.chown(MOUNTPOINT, 0, 0)
    os.chmod(MOUNTPOINT, 0o700)
    print("PASS: verified state filesystem mounted privately at /srv/sigma-state.")
    print("No filesystem was formatted.")


def main() -> int:
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("uuid", help="owner-confirmed filesystem UUID of the attached state disk")
    args = parser.parse_args()
    try:
        prepare(args.uuid)
    except (RuntimeError, ValueError) as exc:
        print(f"FAIL: {exc}", file=sys.stderr)
        return 1
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
