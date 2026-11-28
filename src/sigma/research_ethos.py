"""Immutable research philosophy plus isolated, optional per-user Markdown overrides.

Never persist this preference inside a portable project. Frozen snapshots belong
to individual *new* research/paper runs, not retroactively to past artifacts.
"""

from __future__ import annotations

import fcntl
import hashlib
import json
import os
import stat
import tempfile
from pathlib import Path
from typing import Any

from sigma import project_types
from sigma.projects import ProjectError

DEFAULT_VERSION = "research-ethos-v2"
DEFAULT_MARKDOWN = """1. **Pursue discovery freely.** Follow promising ideas wherever they lead. Explore unconventional hypotheses, unexpected connections, and novel approaches that offer credible paths toward understanding. Never manufacture support for predetermined conclusions.

2. **Let evidence govern conclusions.** Distinguish established findings, plausible interpretations, assumptions, speculation, and unresolved questions. Ground hypothetical scenarios in verifiable reality, never invent evidence or established rules, and rigorously test novel conclusions without overstating certainty.

3. **Make obstacles productive.** Use skepticism to expose weaknesses, challenge assumptions, and improve promising ideas rather than merely dismiss them. When unconditional conclusions are unavailable, seek conditional results, alternative formulations, structural relationships, counterexamples, or narrower discoveries. Uncertainty should stimulate exploration, not suppress it.

4. **Build understanding cumulatively.** Preserve valid findings, failed approaches, useful evidence, and unresolved questions. Each iteration should advance understanding rather than repeat previous work. Judge success by knowledge gained: disproving a hypothesis, discovering limitations, or establishing that a problem remains unresolved can constitute valuable progress.

5. **Publish faithfully and respect the reader.** Communicate what was actually discovered, including substantive reasoning, limitations, uncertainty, and open questions. Never disguise incomplete research as a breakthrough. Give every paragraph a distinct explanatory purpose, preserving scientific depth and precise qualifications while eliminating padding, unnecessary process narration, and repeated results or disclaimers.

**Pursue discovery freely, advance understanding rigorously, and report findings faithfully.**"""
FILENAME = ".sigma-research-ethos.json"
LOCK = ".sigma-research-ethos.lock"
MAX_CHARS = 16_000


def _root() -> Path:
    root = project_types._store_path().parent
    if root.is_symlink() or not root.is_dir():
        raise ProjectError("Research Ethos directory is unsafe")
    return root


def _validate(markdown: Any) -> str:
    if (
        not isinstance(markdown, str)
        or not markdown.strip()
        or len(markdown) > MAX_CHARS
        or "\x00" in markdown
    ):
        raise ProjectError("Research Ethos must be nonempty Markdown (at most 16000 characters)")
    return markdown


def _override(root: Path) -> str | None:
    try:
        fd = os.open(root / FILENAME, os.O_RDONLY | getattr(os, "O_NOFOLLOW", 0))
    except FileNotFoundError:
        return None
    try:
        info = os.fstat(fd)
        if (
            not stat.S_ISREG(info.st_mode)
            or info.st_uid != os.geteuid()
            or info.st_mode & 0o077
            or info.st_size > MAX_CHARS * 4 + 1024
        ):
            raise ProjectError("Research Ethos file is unsafe")
        with os.fdopen(fd, "rb", closefd=False) as handle:
            raw = json.loads(handle.read(MAX_CHARS * 4 + 1025))
        if not isinstance(raw, dict) or set(raw) != {"version", "markdown"} or raw["version"] != 1:
            raise ProjectError("Research Ethos file is invalid")
        return _validate(raw["markdown"])
    except (ValueError, UnicodeError) as exc:
        raise ProjectError("Research Ethos file is invalid") from exc
    finally:
        os.close(fd)


def current() -> dict[str, str | bool]:
    override = _override(_root())
    markdown = override if override is not None else DEFAULT_MARKDOWN
    return {
        "markdown": markdown,
        "is_override": override is not None,
        "version": DEFAULT_VERSION,
        "sha256": hashlib.sha256(markdown.encode("utf-8")).hexdigest(),
    }


def frozen_snapshot() -> dict[str, str]:
    state = current()
    return {
        "markdown": str(state["markdown"]),
        "version": str(state["version"]),
        "sha256": str(state["sha256"]),
    }


def save_override(markdown: str | None) -> dict[str, str | bool]:
    """None removes the override; errors never silently destroy the old file."""
    if markdown is not None:
        _validate(markdown)
    root = _root()
    lockfd = os.open(root / LOCK, os.O_CREAT | os.O_RDWR | getattr(os, "O_NOFOLLOW", 0), 0o600)
    try:
        info = os.fstat(lockfd)
        if not stat.S_ISREG(info.st_mode) or info.st_uid != os.geteuid() or info.st_mode & 0o077:
            raise ProjectError("Research Ethos lock is unsafe")
        fcntl.flock(lockfd, fcntl.LOCK_EX)
        _override(root)  # Malformed state must fail closed, not be overwritten.
        target = root / FILENAME
        if markdown is None:
            target.unlink(missing_ok=True)
        else:
            payload = json.dumps({"version": 1, "markdown": markdown}, ensure_ascii=False).encode(
                "utf-8"
            )
            fd, name = tempfile.mkstemp(prefix=".sigma-ethos-", dir=root)
            try:
                with os.fdopen(fd, "wb") as handle:
                    handle.write(payload)
                    handle.flush()
                    os.fsync(handle.fileno())
                os.chmod(name, 0o600)
                os.replace(name, target)
            finally:
                Path(name).unlink(missing_ok=True)
        parent = os.open(root, os.O_RDONLY | getattr(os, "O_DIRECTORY", 0))
        try:
            os.fsync(parent)
        finally:
            os.close(parent)
        return current()
    finally:
        os.close(lockfd)


def quarantine_invalid_override() -> dict[str, str | bool]:
    """Explicit recovery only: retain corrupt content in a private archive.

    Never unlink or replace an unsafe file (symlink, foreign owner or broad
    permissions). A valid override cannot be quarantined through this route.
    """
    from uuid import uuid4

    root = _root()
    lockfd = os.open(root / LOCK, os.O_CREAT | os.O_RDWR | getattr(os, "O_NOFOLLOW", 0), 0o600)
    try:
        info = os.fstat(lockfd)
        if not stat.S_ISREG(info.st_mode) or info.st_uid != os.geteuid() or info.st_mode & 0o077:
            raise ProjectError("Research Ethos lock is unsafe")
        fcntl.flock(lockfd, fcntl.LOCK_EX)
        target = root / FILENAME
        try:
            fd = os.open(target, os.O_RDONLY | getattr(os, "O_NOFOLLOW", 0))
        except FileNotFoundError:
            return current()
        try:
            info = os.fstat(fd)
            if (
                not stat.S_ISREG(info.st_mode)
                or info.st_uid != os.geteuid()
                or info.st_mode & 0o077
                or info.st_size > MAX_CHARS * 4 + 1024
            ):
                raise ProjectError(
                    "Unsafe Research Ethos file must be repaired by an administrator"
                )
        finally:
            os.close(fd)
        try:
            _override(root)
        except ProjectError:
            archive = root / (".sigma-research-ethos.invalid-" + uuid4().hex + ".json")
            os.replace(target, archive)
            parent = os.open(root, os.O_RDONLY | getattr(os, "O_DIRECTORY", 0))
            try:
                os.fsync(parent)
            finally:
                os.close(parent)
            return current()
        raise ProjectError("Research Ethos is valid; use the normal Restore Default control")
    finally:
        os.close(lockfd)
