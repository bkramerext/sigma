"""Safe, stop-the-service tar backup/restore for the private SIGMA data volume."""

from __future__ import annotations

import argparse
import os
import shutil
import stat
import tarfile
from pathlib import Path, PurePosixPath


def _safe_tree(root: Path) -> list[Path]:
    result = [root]
    for directory, dirs, files in os.walk(root, followlinks=False):
        base = Path(directory)
        for name in [*dirs, *files]:
            path = base / name
            info = path.lstat()
            if not (stat.S_ISDIR(info.st_mode) or stat.S_ISREG(info.st_mode)):
                raise ValueError(f"backup contains unsupported filesystem entry: {path}")
            result.append(path)
    return result


def backup(source: Path, destination: Path, *, source_uid: int | None = None) -> None:
    root = source.resolve(strict=True)
    root_info = root.lstat()
    destination_parent = destination.parent.resolve(strict=True)
    parent_info = destination_parent.lstat()
    expected_source_uid = os.geteuid() if source_uid is None else source_uid
    if (
        not stat.S_ISDIR(root_info.st_mode)
        or root_info.st_uid != expected_source_uid
        or root_info.st_mode & 0o077
        or destination.exists()
        or not stat.S_ISDIR(parent_info.st_mode)
        or parent_info.st_uid != os.geteuid()
        or parent_info.st_mode & 0o077
    ):
        raise ValueError("source must be a directory and destination must not exist")
    paths = _safe_tree(root)
    destination.parent.mkdir(mode=0o700, parents=True, exist_ok=True)
    flags = os.O_WRONLY | os.O_CREAT | os.O_EXCL | getattr(os, "O_NOFOLLOW", 0)
    fd = os.open(destination, flags, 0o600)
    os.close(fd)
    try:
        with tarfile.open(destination, "w:gz") as archive:
            for path in paths:
                archive.add(path, arcname=path.relative_to(root).as_posix() or ".", recursive=False)
        os.chmod(destination, 0o600)
    except Exception:
        destination.unlink(missing_ok=True)
        raise


def restore(
    archive_path: Path, destination: Path, *, uid: int | None = None, gid: int | None = None
) -> None:
    if destination.is_symlink():
        raise ValueError("restore destination must not be a symlink")
    archive_info = archive_path.lstat()
    if (
        not stat.S_ISREG(archive_info.st_mode)
        or archive_info.st_uid != os.geteuid()
        or archive_info.st_mode & 0o077
    ):
        raise ValueError("backup archive must be a private regular file")
    if destination.exists() and any(destination.iterdir()):
        raise ValueError("restore destination must be empty")
    destination.mkdir(mode=0o700, parents=True, exist_ok=True)
    root = destination.resolve(strict=True)
    root_info = root.lstat()
    if (
        not stat.S_ISDIR(root_info.st_mode)
        or root_info.st_uid != (os.geteuid() if uid is None else uid)
        or root_info.st_mode & 0o077
    ):
        raise ValueError("restore destination must be an owned private directory")
    with tarfile.open(archive_path, "r:gz") as archive:
        members = archive.getmembers()
        for member in members:
            name = PurePosixPath(member.name)
            if name.is_absolute() or ".." in name.parts or not (member.isdir() or member.isreg()):
                raise ValueError("backup archive contains an unsafe path or entry")
            target = (root / Path(*name.parts)).resolve()
            if not target.is_relative_to(root):
                raise ValueError("backup archive escapes the restore destination")
        for member in members:
            name = PurePosixPath(member.name)
            target = root / Path(*name.parts)
            if member.isdir():
                target.mkdir(mode=0o700, parents=True, exist_ok=True)
            else:
                target.parent.mkdir(mode=0o700, parents=True, exist_ok=True)
                source = archive.extractfile(member)
                if source is None:
                    raise ValueError("backup archive contains an unreadable file")
                fd = os.open(
                    target,
                    os.O_WRONLY | os.O_CREAT | os.O_EXCL | getattr(os, "O_NOFOLLOW", 0),
                    0o600,
                )
                with os.fdopen(fd, "wb") as output, source:
                    shutil.copyfileobj(source, output)
    for path in _safe_tree(root):
        info = path.lstat()
        if uid is not None and gid is not None:
            os.chown(path, uid, gid, follow_symlinks=False)
        os.chmod(path, 0o700 if stat.S_ISDIR(info.st_mode) else 0o600)


def main() -> int:
    parser = argparse.ArgumentParser()
    subparsers = parser.add_subparsers(dest="action", required=True)
    make = subparsers.add_parser("backup")
    make.add_argument("source", type=Path)
    make.add_argument("destination", type=Path)
    make.add_argument("--source-uid", type=int)
    put = subparsers.add_parser("restore")
    put.add_argument("archive", type=Path)
    put.add_argument("destination", type=Path)
    put.add_argument("--uid", type=int)
    put.add_argument("--gid", type=int)
    args = parser.parse_args()
    try:
        if args.action == "backup":
            backup(args.source, args.destination, source_uid=args.source_uid)
        else:
            restore(args.archive, args.destination, uid=args.uid, gid=args.gid)
    except (OSError, tarfile.TarError, ValueError) as exc:
        parser.error(str(exc))
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
