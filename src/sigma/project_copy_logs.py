"""Copy project-scoped diagnostic records into an independent Save As project.

The core project bundle excludes this private log store. Recreate validated
frames with fresh project/session identities; do not read another workspace's
logs or carry operational lock files into the clone.
"""

from __future__ import annotations

import fcntl
import json
import os
import shutil
import stat
import tempfile
from pathlib import Path

from sigma import session_log
from sigma.project_copy import _rewrite
from sigma.projects import ProjectError


def _safe_file(path: Path) -> None:
    info = path.lstat()
    if (
        not stat.S_ISREG(info.st_mode)
        or info.st_uid != os.geteuid()
        or info.st_mode & 0o077
    ):
        raise ProjectError("Session diagnostic log has unsafe ownership or permissions.")


def _safe_directory(path: Path) -> None:
    info = path.lstat()
    if (
        not stat.S_ISDIR(info.st_mode)
        or info.st_uid != os.geteuid()
        or info.st_mode & 0o077
    ):
        raise ProjectError("Session diagnostic directory has unsafe ownership or permissions.")


def _flush_source(source_dir: Path) -> None:
    """Wait only for the source project's queued diagnostic writes."""
    while True:
        with session_log._queues_guard:
            queues = [
                work
                for key, work in session_log._queues.items()
                if Path(key).parent == source_dir
            ]
        if not queues:
            return
        for queue in queues:
            queue.join()


def _read_frames(path: Path) -> list[dict]:
    lock_path = path.with_suffix(".lock")
    with session_log._lock(path):
        descriptor = None
        if os.path.lexists(lock_path):
            _safe_file(lock_path)
            descriptor = os.open(lock_path, os.O_RDONLY | os.O_NOFOLLOW)
        try:
            if descriptor is not None:
                fcntl.flock(descriptor, fcntl.LOCK_SH)
            return session_log._frames(path)[0]
        finally:
            if descriptor is not None:
                fcntl.flock(descriptor, fcntl.LOCK_UN)
                os.close(descriptor)


def clone_project_logs(
    source_path: Path,
    destination_path: Path,
    source_id: str,
    new_id: str,
    session_ids: dict[str, str],
    session_numbers: dict[str, int],
) -> bool:
    """Publish a cloned, project-owned log directory or leave no directory.

    Returns True if the new log directory was created. Call only after a
    successful project import and before making that project visible in recents.
    On failure the caller rolls back the newly imported project file.
    """
    old_root = session_log._root(source_path)
    new_root = session_log._root(destination_path)
    if not old_root.exists():
        return False
    _safe_directory(old_root)
    original = old_root / source_id
    if not original.exists():
        return False
    _safe_directory(original)
    # Local archived projects may live outside the new managed-project root.
    # Hosted projects always resolve both roots within the bound workspace.
    new_root.mkdir(mode=0o700, parents=True, exist_ok=True)
    _safe_directory(new_root)
    target = new_root / new_id
    if os.path.lexists(target):
        raise ProjectError("Save As diagnostic destination already exists.")
    _flush_source(original)
    mapping = {source_id: new_id, **session_ids, str(source_path): str(destination_path)}
    staged = Path(tempfile.mkdtemp(prefix=".sigma-save-as-", dir=new_root))
    try:
        with session_log._lock(original / ".project-read-guard"):
            for child in sorted(original.iterdir()):
                if child.is_symlink():
                    raise ProjectError("Unsafe source diagnostic log.")
                if child.name.endswith(".lock") or child.name.startswith(
                    (".short-name-", ".session-header-")
                ):
                    continue  # Operational lock and staging files never follow.
                _safe_file(child)
                if child.name == ".short-name":
                    data = _rewrite(child.read_text(encoding="utf-8"), mapping)
                    (staged / child.name).write_text(data, encoding="utf-8")
                elif child.name == "project-diagnostics.jsonl":
                    if child.stat().st_size > 1024 * 1024:
                        raise ProjectError("Project diagnostics exceed their size limit.")
                    lines = []
                    for line in child.read_text(encoding="utf-8").splitlines():
                        if not line.strip():
                            continue
                        try:
                            record = json.loads(line)
                        except (TypeError, ValueError) as exc:
                            raise ProjectError("Project diagnostics are not valid JSON.") from exc
                        if not isinstance(record, dict) or record.get("project_id") != source_id:
                            raise ProjectError("Project diagnostics belong to another project.")
                        lines.append(
                            json.dumps(
                                _rewrite(record, mapping),
                                ensure_ascii=False,
                                separators=(",", ":"),
                            )
                        )
                    (staged / child.name).write_text(
                        "\n".join(lines) + ("\n" if lines else ""),
                        encoding="utf-8",
                    )
                elif child.suffix == ".md" and child.stem in session_ids:
                    old_session = child.stem
                    new_session = session_ids[old_session]
                    destination_log = staged / f"{new_session}.md"
                    events = _read_frames(child)
                    session_log._ensure(
                        destination_log,
                        new_id,
                        new_session,
                        session_numbers[old_session],
                    )
                    earlier: list[dict] = []
                    for event in events:
                        rebased = _rewrite(event, mapping)
                        session_log._append_frame(
                            destination_log,
                            rebased,
                            session_log._event_markdown(rebased, earlier),
                        )
                        earlier.append(rebased)
                else:
                    raise ProjectError("Unexpected project diagnostic member.")
        if os.path.lexists(target):
            raise ProjectError("Save As diagnostic destination was created concurrently.")
        os.rename(staged, target)
        return True
    except Exception:
        shutil.rmtree(staged)
        raise
