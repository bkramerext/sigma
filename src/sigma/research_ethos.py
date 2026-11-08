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

DEFAULT_VERSION = "research-ethos-v1"
DEFAULT_MARKDOWN = """1. **Pursue discovery, not predetermined answers.** Research should follow promising ideas wherever they lead, rather than manufacture support for an expected conclusion.
2. **An unsuccessful hypothesis is not unsuccessful research.** Disproving an idea, discovering limitations, or establishing that a problem remains unresolved can constitute valuable scientific progress.
3. **Let evidence determine conclusions.** Distinguish established findings, plausible interpretations, speculation, and unresolved questions. Never overstate certainty.
4. **Be intellectually adventurous.** Explore unconventional hypotheses, unexpected connections, and novel approaches when they offer a credible path toward new understanding.
5. **Make criticism productive.** Skepticism should expose weaknesses, test assumptions, and improve the investigation, not merely obstruct or dismiss promising ideas.
6. **Build on what has been learned.** Preserve valid findings, failed approaches, useful evidence, and unresolved questions. Each research iteration should advance understanding rather than unnecessarily repeat previous work.
7. **Publish what was actually discovered.** The final paper should faithfully represent the investigation, including its findings, limitations, uncertainty, and open questions. Do not disguise incomplete research as a completed breakthrough.
8. **Judge progress by knowledge gained.** Evaluate research by the understanding it produces, not simply whether its original objectives were achieved.
9. **Ground hypothetical scenarios in reality.** Fictional or hypothetical situations are not permission to invent evidence, facts, or established rules. Ground analysis in verifiable knowledge, distinguish assumptions from reality, and rigorously test novel conclusions.
10. **Respect the reader's attention.** Papers should be succinct and non-repetitive. Give every paragraph a distinct explanatory purpose; state each result, proof step, caveat, or limitation where it is needed, without recycling it across the abstract, introduction, methods, body, and conclusion. Keep essential scientific depth and precise qualifications; omit padding, process narration, and repeated disclaimers.

**Pursue discovery freely, report findings faithfully, and never disguise incomplete work as success.**"""
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
