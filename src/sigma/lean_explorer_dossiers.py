"""Private, durable expository dossiers created by Lean Explorer.

A dossier is evidence/interpretation, not Lean verification. All source links
refer to pinned repository revisions and actual snippets retrieved on insertion.
"""

from __future__ import annotations

import fcntl
import json
import os
import stat
from datetime import UTC, datetime
from pathlib import Path
from uuid import UUID, uuid4

from sigma import lean_explorer, lean_explorer_local, lean_explorer_map
from sigma.projects import ProjectError
from sigma.recents import state_directory
from sigma.ui_instance import private_directory

MAX_DOSSIER_BYTES = 4 * 1024 * 1024
MAX_ENTRIES = 160
MAX_NOTE_CHARS = 24_000
MAX_SCOPE_DECLARATIONS = 32


def _directory() -> Path:
    path = state_directory() / "lean-explorer-dossiers"
    try:
        private_directory(path)
    except (OSError, RuntimeError) as exc:
        raise ProjectError("The private Lean Explorer dossier directory is unavailable.") from exc
    return path


def _identifier(value: str) -> str:
    try:
        identifier = str(UUID(value))
    except (ValueError, AttributeError, TypeError) as exc:
        raise ProjectError("Invalid Lean Explorer dossier identifier.") from exc
    if identifier != value:
        raise ProjectError("Noncanonical Lean Explorer dossier identifier.")
    return identifier


def _check(fd: int) -> None:
    info = os.fstat(fd)
    if (
        not stat.S_ISREG(info.st_mode)
        or info.st_uid != os.getuid()
        or info.st_nlink != 1
        or info.st_mode & 0o077
    ):
        raise ProjectError("Lean Explorer dossier file is not a private regular file.")


def _read(identifier: str) -> dict:
    path = _directory() / (_identifier(identifier) + ".json")
    try:
        fd = os.open(path, os.O_RDONLY | os.O_NOFOLLOW)
        with os.fdopen(fd, "rb") as stream:
            _check(stream.fileno())
            data = stream.read(MAX_DOSSIER_BYTES + 1)
        if len(data) > MAX_DOSSIER_BYTES:
            raise ProjectError("The dossier exceeds the supported size.")
        record = json.loads(data)
    except (OSError, ValueError, UnicodeError) as exc:
        raise ProjectError("The requested Lean Explorer dossier could not be read.") from exc
    if not isinstance(record, dict) or record.get("id") != identifier:
        raise ProjectError("The dossier has invalid metadata.")
    return record


def _revision(source_mode: str) -> str:
    if source_mode == "mirror":
        return lean_explorer.MIRROR_SHA
    if source_mode == "local":
        active = lean_explorer_local.source()
        if active is None:
            raise ProjectError("Select a local Lean directory first.")
        return "local:" + active["root_id"]
    raise ProjectError("Unknown Lean Explorer source mode.")


def create(
    source_mode: str = "mirror",
    section_path: str = "",
    section_title: str = "",
    section_focus: str = "",
    section_id: str = "",
) -> dict:
    revision = _revision(source_mode)
    # Sections partition *mathematical arguments*, not filesystem subtrees.
    # An exposition may require declarations from unrelated Lean modules.
    if section_path:
        raise ProjectError("Lean source-tree directories cannot be used as mathematical sections.")
    mapped = lean_explorer_map.section(section_id) if section_id else None
    if mapped:
        section_title = mapped["title"]
        section_focus = mapped["question"]
    if not isinstance(section_title, str) or len(section_title.strip()) > 180:
        raise ProjectError("Invalid expository section title.")
    if not isinstance(section_focus, str) or len(section_focus) > 6000:
        raise ProjectError("Invalid expository section question.")
    title = section_title.strip() or "New mathematical section"
    local_source = lean_explorer_local.source() if source_mode == "local" else None
    if source_mode == "local" and local_source is None:
        raise ProjectError("Select a local Lean directory first.")
    identifier = str(uuid4())
    timestamp = datetime.now(UTC).isoformat()
    document = {
        "id": identifier,
        "title": f"Lean Explorer — {title}",
        "study_title": lean_explorer_map.catalog()["title"],
        "created_at": timestamp,
        "updated_at": timestamp,
        "formal_repository": (
            str(local_source["directory"]) if local_source is not None else lean_explorer.MIRROR
        ),
        "formal_commit": revision,
        "source_mode": source_mode,
        "section_path": "",
        "section_id": section_id,
        "section_title": title,
        "section_focus": section_focus.strip(),
        "section_basis": "conceptual; declaration membership is source-linked",
        "entries": [],
        "scope": [],
        "paper_project": None,
        "discovery": None,
    }
    data = json.dumps(document, ensure_ascii=False, indent=2).encode("utf-8")
    path = _directory() / (identifier + ".json")
    try:
        fd = os.open(path, os.O_WRONLY | os.O_CREAT | os.O_EXCL | os.O_NOFOLLOW, 0o600)
        with os.fdopen(fd, "wb") as stream:
            _check(stream.fileno())
            stream.write(data)
            stream.flush()
            os.fsync(stream.fileno())
    except OSError as exc:
        raise ProjectError("The Lean Explorer dossier could not be created.") from exc
    return document


def get(identifier: str) -> dict:
    return _read(identifier)


def list_dossiers() -> list[dict]:
    root = _directory()
    items: list[dict] = []
    for path in root.glob("*.json"):
        if len(items) >= 1000:
            break
        try:
            record = _read(path.stem)
        except ProjectError:
            continue
        items.append(
            {
                "id": record["id"],
                "title": record["title"],
                "created_at": record["created_at"],
                "updated_at": record["updated_at"],
                "entry_count": len(record.get("entries", [])),
                "scope_count": len(record.get("scope", [])),
                "paper_project": record.get("paper_project"),
                "source_mode": record.get("source_mode", "mirror"),
                "formal_commit": record.get("formal_commit", ""),
                "section_path": record.get("section_path", ""),
                "section_title": record.get("section_title", "Complete proof"),
                "section_id": record.get("section_id", ""),
                "section_focus": record.get("section_focus", ""),
            }
        )
    return sorted(items, key=lambda item: item["updated_at"], reverse=True)


def append(
    identifier: str,
    *,
    formal_path: str,
    declaration_name: str,
    mode: str,
    text: str,
    supplementary_sources: list[dict] | None = None,
    source_mode: str = "mirror",
) -> dict:
    if mode not in {"note", "explain", "audit"}:
        raise ProjectError("Unknown dossier entry type.")
    if not isinstance(text, str) or not text.strip() or len(text) > MAX_NOTE_CHARS:
        raise ProjectError("The exposition text must be nonempty and within 24,000 characters.")

    # Re-read the declaration server-side; never trust client-supplied proof
    # locations, commit identifiers, declaration snippets or source hashes.
    selected = lean_explorer.declaration(formal_path, declaration_name, source_mode=source_mode)
    source = {
        key: selected[key]
        for key in (
            "path",
            "name",
            "kind",
            "commit",
            "url",
            "sha256",
            "start_line",
            "end_line",
            "complete",
            "excerpt",
        )
    }
    root = _directory()
    identifier = _identifier(identifier)
    # A separate stable lockfile protects writers across atomic JSON replacement.
    lock_path = root / (identifier + ".lock")
    try:
        lock_fd = os.open(lock_path, os.O_RDWR | os.O_CREAT | os.O_NOFOLLOW, 0o600)
        with os.fdopen(lock_fd, "rb+") as lock:
            _check(lock.fileno())
            fcntl.flock(lock.fileno(), fcntl.LOCK_EX)
            record = _read(identifier)
            if (
                record.get("formal_commit") != _revision(source_mode)
                or record.get("source_mode", "mirror") != source_mode
            ):
                raise ProjectError("Dossier source differs from the selected formal source.")
            # Any declaration in the pinned proof can contribute to an expository
            # section; chapter boundaries are mathematical, not file boundaries.
            entries = record.get("entries")
            if not isinstance(entries, list) or len(entries) >= MAX_ENTRIES:
                raise ProjectError("The dossier has reached its entry limit.")
            item = {
                "id": str(uuid4()),
                "created_at": datetime.now(UTC).isoformat(),
                "mode": mode,
                "interpretation_status": "unverified commentary",
                "text": text.strip(),
                "source": source,
                "supplementary_sources": supplementary_sources or [],
            }
            entries.append(item)
            record["updated_at"] = item["created_at"]
            data = json.dumps(record, ensure_ascii=False, indent=2).encode("utf-8")
            if len(data) > MAX_DOSSIER_BYTES:
                raise ProjectError("The dossier exceeds its 4 MiB size limit.")
            temp = root / (identifier + "." + str(uuid4()) + ".tmp")
            try:
                fd = os.open(temp, os.O_WRONLY | os.O_CREAT | os.O_EXCL | os.O_NOFOLLOW, 0o600)
                with os.fdopen(fd, "wb") as stream:
                    _check(stream.fileno())
                    stream.write(data)
                    stream.flush()
                    os.fsync(stream.fileno())
                os.replace(temp, root / (identifier + ".json"))
            finally:
                if temp.exists():
                    temp.unlink()
            return item
    except OSError as exc:
        raise ProjectError("The Lean Explorer dossier could not be updated.") from exc


def _save_locked(root: Path, identifier: str, record: dict) -> None:
    """Atomically write a dossier while holding its stable per-ID file lock."""
    data = json.dumps(record, ensure_ascii=False, indent=2).encode("utf-8")
    if len(data) > MAX_DOSSIER_BYTES:
        raise ProjectError("The dossier exceeds its 4 MiB size limit.")
    temp = root / (identifier + "." + str(uuid4()) + ".tmp")
    try:
        fd = os.open(temp, os.O_WRONLY | os.O_CREAT | os.O_EXCL | os.O_NOFOLLOW, 0o600)
        with os.fdopen(fd, "wb") as stream:
            _check(stream.fileno())
            stream.write(data)
            stream.flush()
            os.fsync(stream.fileno())
        os.replace(temp, root / (identifier + ".json"))
    finally:
        temp.unlink(missing_ok=True)


def _with_dossier_lock(identifier: str, update) -> dict:
    root = _directory()
    identifier = _identifier(identifier)
    lock_path = root / (identifier + ".lock")
    try:
        fd = os.open(lock_path, os.O_RDWR | os.O_CREAT | os.O_NOFOLLOW, 0o600)
        with os.fdopen(fd, "rb+") as lock:
            _check(lock.fileno())
            fcntl.flock(lock.fileno(), fcntl.LOCK_EX)
            record = _read(identifier)
            changed = update(record)
            if changed:
                record["updated_at"] = datetime.now(UTC).isoformat()
                _save_locked(root, identifier, record)
            return record
    except OSError as exc:
        raise ProjectError("The Lean Explorer dossier could not be updated.") from exc


def select_declaration(
    identifier: str, *, formal_path: str, declaration_name: str, source_mode: str
) -> dict:
    """Attach an exact source declaration to the section's independent scope."""
    selected = lean_explorer.declaration(formal_path, declaration_name, source_mode=source_mode)
    item = {
        key: selected[key]
        for key in (
            "path",
            "name",
            "kind",
            "commit",
            "url",
            "sha256",
            "start_line",
            "end_line",
            "complete",
            "excerpt",
        )
    }

    def apply(record: dict) -> bool:
        if (
            record.get("formal_commit") != _revision(source_mode)
            or record.get("source_mode", "mirror") != source_mode
        ):
            raise ProjectError("This dossier belongs to another formal source.")
        scoped = record.setdefault("scope", [])
        if not isinstance(scoped, list):
            raise ProjectError("Dossier scope is invalid.")
        if any(x.get("path") == item["path"] and x.get("name") == item["name"] for x in scoped):
            return False
        if len(scoped) >= MAX_SCOPE_DECLARATIONS:
            raise ProjectError(
                "This section already has 32 selected declarations; divide the work."
            )
        if record.get("paper_project"):
            raise ProjectError(
                "This section already has a paper handoff. Make a new section dossier to change its scope."
            )
        scoped.append(item)
        return True

    return _with_dossier_lock(identifier, apply)


def save_discovered_scope(identifier: str, *, section_id: str, discovery: dict) -> dict:
    """Commit a complete cross-repository discovery as a suggested research scope.

    Preserve earlier manual selections. Any auto-added excerpts remain explicitly
    marked as unverified lexical candidates, never formal dependency edges.
    """
    from sigma import lean_explorer_discovery

    def apply(record: dict) -> bool:
        if (
            record.get("source_mode") != "local"
            or record.get("formal_commit") != _revision("local")
            or record.get("section_id") != section_id
        ):
            raise ProjectError("The discovery does not match this local proof and section.")
        if record.get("paper_project"):
            raise ProjectError(
                "This section's paper scope is frozen. Create a new dossier to investigate again."
            )
        if discovery.get("source_root_id") != lean_explorer_local.source()["root_id"]:
            raise ProjectError("The local proof root changed during discovery.")
        scoped = record.setdefault("scope", [])
        if not isinstance(scoped, list):
            raise ProjectError("Invalid section scope.")
        additions = 0
        total_excerpt_chars = sum(len(item.get("excerpt", "")) for item in scoped)
        for proposal in discovery["candidates"]:
            if additions >= lean_explorer_discovery.MAX_AUTO_SELECTED:
                break
            if len(scoped) >= MAX_SCOPE_DECLARATIONS:
                break
            key = (proposal["path"], proposal["name"])
            if any((x.get("path"), x.get("name")) == key for x in scoped):
                continue
            current = lean_explorer.declaration(
                proposal["path"], proposal["name"], source_mode="local"
            )
            if current["sha256"] != proposal["sha256"]:
                raise ProjectError(
                    "A source file changed during discovery; the results were not saved."
                )
            if total_excerpt_chars + len(current["excerpt"]) > 28_000:
                continue
            scoped.append(
                {
                    **current,
                    "selection_origin": "automatic_lexical_discovery",
                    "relevance_score": proposal["relevance_score"],
                    "why_candidate": proposal["why_candidate"],
                }
            )
            additions += 1
            total_excerpt_chars += len(current["excerpt"])
        record["discovery"] = {
            key: discovery[key]
            for key in (
                "section_id",
                "files_scanned",
                "bytes_scanned",
                "matching_declarations",
                "skipped_large_files",
                "index_type",
                "complete",
            )
        }
        record["discovery"]["auto_selected"] = additions
        return True

    return _with_dossier_lock(identifier, apply)


def deselect_declaration(
    identifier: str, *, formal_path: str, declaration_name: str, source_mode: str
) -> dict:
    """Only remove the selection, not prior source-backed research entries."""

    def apply(record: dict) -> bool:
        if (
            record.get("formal_commit") != _revision(source_mode)
            or record.get("source_mode", "mirror") != source_mode
        ):
            raise ProjectError("This dossier belongs to another formal source.")
        if record.get("paper_project"):
            raise ProjectError(
                "This section already has a paper handoff. Make a new dossier to change its scope."
            )
        scoped = record.get("scope", [])
        if not isinstance(scoped, list):
            raise ProjectError("Dossier scope is invalid.")
        remaining = [
            x for x in scoped if x.get("path") != formal_path or x.get("name") != declaration_name
        ]
        if len(remaining) == len(scoped):
            return False
        record["scope"] = remaining
        return True

    return _with_dossier_lock(identifier, apply)


def prepare_paper_project(identifier: str, *, source_mode: str) -> dict:
    """Hand selected and checked section evidence to SIGMA's existing paper flow.

    Creates a real project. Publication, scoring, PDF and resume remain owned
    by SIGMA's existing project Papers pipeline.
    """
    from sigma import global_research_settings, project_collaboration
    from sigma.projects import create_project, inspect_project

    def apply(record: dict) -> bool:
        if (
            record.get("formal_commit") != _revision(source_mode)
            or record.get("source_mode") != source_mode
        ):
            raise ProjectError("The selected Lean source differs from this dossier.")
        previous = record.get("paper_project")
        if previous:
            existing = inspect_project(previous["path"])
            if existing.project.id != previous.get("project_id"):
                raise ProjectError("The previous paper project identity has changed.")
            return False
        scope = record.get("scope") or []
        if not isinstance(scope, list) or not scope:
            raise ProjectError("Choose Lean evidence for this section before preparing a paper.")
        # A local source tree is mutable. Never silently switch a paper's
        # evidence when a selected Lean file changes after selection.
        for chosen in scope:
            current = lean_explorer.declaration(
                chosen["path"], chosen["name"], source_mode=source_mode
            )
            if current["sha256"] != chosen["sha256"] or current["commit"] != chosen["commit"]:
                raise ProjectError(
                    "A selected Lean source changed. Remove and re-add it before paper preparation."
                )
        title = str(record.get("section_title") or "Expository section")
        question = str(record.get("section_focus") or "Explain the selected mathematics")
        problem = (
            "Prepare a rigorous, readable mathematical exposition of the selected "
            "proof section.\n\n"
            f"Study: {record.get('study_title', 'Formal proof investigation')}\n"
            f"Section: {title}\nResearch question: {question}\n\n"
            "Use the exact Lean excerpts and citation records in the paper "
            "requirements as evidence. Explain the conceptual connections, "
            "all hypotheses, and any gaps. This Explorer has NOT kernel-checked "
            "the selected statements or verified their dependency relationships."
        )
        lines = [
            "# Scope and publication requirements",
            "",
            f"Mathematical section: {title}",
            f"Guiding question: {question}",
            f"Evidence identity: {record['formal_commit']}",
            f"Source mode: {source_mode}",
            "",
            (
                "The selected declarations below are a manual research scope, NOT "
                "a formal dependency closure. The interpretation is unverified. "
                "Do not assert kernel-checking or prove unverified connections."
            ),
            "",
            "## Exact Lean declarations",
        ]
        selected_keys = set()
        for chosen in scope:
            selected_keys.add((chosen["path"], chosen["name"]))
            lines.extend(
                [
                    "",
                    f"### {chosen['name']}",
                    f"Source: {chosen['path']} lines {chosen['start_line']}-{chosen['end_line']}",
                    f"Revision: {chosen['commit']} · file SHA256: {chosen['sha256']}",
                    f"Excerpt complete: {chosen['complete']}",
                    "~~~lean",
                    chosen["excerpt"],
                    "~~~",
                ]
            )
        commentary = [
            item
            for item in record.get("entries", [])
            if (item.get("source", {}).get("path"), item.get("source", {}).get("name"))
            in selected_keys
        ]
        if commentary:
            lines.extend(["", "## Explorer research notes and drafts", ""])
        for item in commentary:
            src = item["source"]
            lines.extend(
                [
                    f"### {src['name']} — {item['mode']}",
                    f"Status: {item['interpretation_status']}",
                    item["text"],
                    "",
                ]
            )
        requirements = "\n".join(lines)
        if len(requirements) > 20_000:
            raise ProjectError(
                "The section evidence exceeds the existing SIGMA paper context limit "
                "(20,000 characters). Select fewer declarations or divide the section. "
                "No source text has been silently discarded."
            )
        config = global_research_settings.load_config()
        view = create_project(
            f"Lean Explorer — {title[:130]} — {identifier[:8]}",
            problem,
            "mathematical",
            config["ai_model"],
            config["reasoning_effort"],
            "hard",
            False,
            "A human-readable, source-cited expository paper with explicit open obligations.",
            requirements,
        )
        project_collaboration.register_owner(view)
        record["paper_project"] = {"path": view.path, "project_id": view.project.id}
        return True

    updated = _with_dossier_lock(identifier, apply)
    return updated["paper_project"]


def markdown(identifier: str) -> str:
    record = _read(identifier)
    parts = [
        f"# {record['title']}",
        "",
        f"Formal source: {record['formal_repository']}",
        f"Source revision: `{record['formal_commit']}`",
        f"Study: {record.get('study_title', 'Formal proof investigation')}",
        f"Mathematical section: {record.get('section_title', 'Unassigned')}",
        f"Proof map section ID: `{record.get('section_id') or 'unassigned'}`",
        f"Section question: {record.get('section_focus', '')}",
        "Formal declaration membership is recorded per entry, across modules.",
        f"Selected Lean declarations: {len(record.get('scope', []))}",
        f"Created: {record['created_at']}",
        "",
        (
            "> This dossier contains source excerpts and unverified human/AI "
            "interpretation. Lean Explorer has not kernel-checked or "
            "mapped dependencies for these statements."
        ),
        "",
    ]
    if record.get("scope"):
        parts.extend(["## Selected Lean evidence", ""])
        for src in record["scope"]:
            parts.extend(
                [
                    f"- **{src['name']}** — `{src['path']}` lines {src['start_line']}-{src['end_line']}",
                    f"  revision `{src['commit']}` · file SHA256 `{src['sha256']}`",
                ]
            )
        parts.append("")
    for index, item in enumerate(record.get("entries", []), 1):
        src = item["source"]
        parts.extend(
            [
                f"## {index}. {src['name']} — {item['mode']}",
                "",
                (
                    f"Source: [{src['path']} lines {src['start_line']}-"
                    f"{src['end_line']}]({src['url']}#L{src['start_line']})"
                    if src.get("url", "").startswith("https://")
                    else f"Local source: {src['path']} lines {src['start_line']}-{src['end_line']}"
                ),
                f"Commit: `{src['commit']}` · SHA256: `{src['sha256']}`",
                f"Source excerpt complete: {src['complete']}",
                f"Interpretation: **{item['interpretation_status']}**",
                "",
                "### Actual Lean source excerpt",
                "",
                "```lean",
                src["excerpt"],
                "```",
                "",
                "### Commentary",
                "",
                item["text"],
                "",
            ]
        )
        for supp in item.get("supplementary_sources", []):
            parts.append(
                f"Supplementary: {supp['kind']} · [{supp['path']}]({supp['url']})"
                f" · revision `{supp['commit']}` · SHA256 `{supp['sha256']}`"
            )
        parts.append("")
    return "\n".join(parts)
