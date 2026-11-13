"""Promote a complete local project bundle to a curated, source-controlled sample.

The source is immutable. Publication removes Google-account attribution while
retaining model provenance, sessions, papers and content-addressed evidence.
Only the destination sample path is included in the new local Git commit.
"""

from __future__ import annotations

import hashlib
import json
import os
import re
import shutil
import subprocess
import tempfile
import unicodedata
from pathlib import Path
from typing import Any
from uuid import uuid4

from sigma import paper_scores, project_bundle, samples
from sigma.project_copy import rebase_copy
from sigma.projects import ProjectError
from sigma.projects import _decode as decode_project

SNAPSHOT_NAME = "sample-snapshot.json"
CURATION_NAME = "sample-curation.json"
_TEMPLATE_PATH = "/sigma-curated-sample-template"
_VERSION_SUFFIX = re.compile(r"\s+v[0-9]+(?:\.[0-9]+)*\s*$", re.IGNORECASE)
_PAPER_METADATA = re.compile(r"artifacts/papers/([0-9a-f]{32})\.json$")
_ACCOUNT_EMAIL = re.compile(r"^[^\s@]+@[^\s@]+\.[^\s@]+$")
_ATTRIBUTION_KEYS = {
    "created_by",
    "creator",
    "creator_email",
    "author_email",
    "owner_email",
    "user_email",
    "account_email",
    "started_by",
    "initiated_by",
    "submitted_by",
    "requested_by",
    "actor_email",
    "last_modified_by",
}


def _unversioned(title: str) -> str:
    return _VERSION_SUFFIX.sub("", title).strip()


def _slug(title: str) -> str:
    folded = unicodedata.normalize("NFKD", title).encode("ascii", "ignore").decode("ascii")
    slug = re.sub(r"[^a-z0-9]+", "-", folded.casefold()).strip("-")
    if not samples.MAX_SAMPLE_NAME.fullmatch(slug):
        raise ProjectError("Cannot derive a safe sample identifier; supply --name.")
    return slug


def _sample_name(title: str, requested: str | None) -> str:
    if requested is not None and not samples.MAX_SAMPLE_NAME.fullmatch(requested):
        raise ProjectError("Sample name must use lowercase letters, digits and hyphens.")
    matches = []
    for identifier, project_path in samples._projects():
        other_title = samples._sample_index_metadata(identifier, project_path)[1]
        if _unversioned(other_title).casefold() == title.casefold():
            matches.append(identifier)
    if len(matches) > 1:
        raise ProjectError("Several existing samples match this title; use --name.")
    if requested is not None:
        if matches and requested != matches[0]:
            raise ProjectError("That title already belongs to a different sample.")
        return requested
    return matches[0] if matches else _slug(title)


def _is_publishable_member(name: str) -> bool:
    """No private workspace settings, attachments, provider tokens or lock files."""
    if Path(name).name.endswith(".lock"):
        return False
    if name == "project.json" or name == "artifacts/research-qa/records.json":
        return True
    if name.startswith(("research-sessions/", "agentic-runs/", "evidence/agentic-runs/")):
        return name.endswith(".json")
    if name.startswith(("papers/", "artifacts/papers/", "artifacts/generated_papers/")):
        return not any(part.startswith(".") and part != ".snapshots" for part in name.split("/"))
    return False


def _account_emails(members: dict[str, bytes]) -> set[str]:
    """Discover ONLY execution-account emails; do not redact scholarly citations."""
    found: set[str] = set()

    def walk(value: Any) -> None:
        if isinstance(value, dict):
            for key, entry in value.items():
                if not isinstance(key, str):
                    continue
                key_lower = key.casefold()
                if (
                    key_lower in {
                        "created_by",
                        "creator_email",
                        "owner_email",
                        "user_email",
                        "account_email",
                        "started_by",
                        "initiated_by",
                        "submitted_by",
                    }
                    and isinstance(entry, str)
                    and _ACCOUNT_EMAIL.fullmatch(entry)
                ):
                    found.add(entry)
                if key_lower == "artifact_authors" and isinstance(entry, dict):
                    for address in entry.values():
                        if isinstance(address, str) and _ACCOUNT_EMAIL.fullmatch(address):
                            found.add(address)
                walk(entry)
        elif isinstance(value, list):
            for entry in value:
                walk(entry)

    for name, data in members.items():
        if not name.endswith(".json"):
            continue
        try:
            walk(json.loads(data))
        except (ValueError, UnicodeDecodeError):
            continue
    return found


def _scrubber(account_emails: set[str]):
    from sigma.samples import _LITERAL_SECRET, _PRIVATE_FIELDS, _SENSITIVE_FIELD, _USER_PATH

    account_lookup = {email.casefold() for email in account_emails}

    def scrub(value: Any) -> Any:
        if isinstance(value, dict):
            cleaned: dict[str, Any] = {}
            for key, item in value.items():
                if not isinstance(key, str):
                    continue
                lower = key.casefold()
                if _SENSITIVE_FIELD.search(key) or lower in _PRIVATE_FIELDS:
                    continue
                if lower == "artifact_authors":
                    cleaned[key] = {}
                elif lower in _ATTRIBUTION_KEYS or lower.endswith("_email"):
                    # Suppress execution-account identities only. Scholarly
                    # citation authors and unrelated addresses stay intact.
                    cleaned[key] = (
                        ""
                        if isinstance(item, str) and item.casefold() in account_lookup
                        else scrub(item)
                    )
                else:
                    cleaned[key] = scrub(item)
            return cleaned
        if isinstance(value, list):
            return [scrub(item) for item in value]
        if isinstance(value, str):
            text = _USER_PATH.sub("[redacted user path]", value)
            text = _LITERAL_SECRET.sub("[redacted credential]", text)
            for email in account_emails:
                text = re.sub(re.escape(email), "[sample account]", text, flags=re.IGNORECASE)
            return text
        return value

    return scrub


def _paper_inventory(members: dict[str, bytes]) -> tuple[str, int | None, int, int]:
    papers: list[tuple[int, int, str, str]] = []
    best: int | None = None
    for name, data in members.items():
        match = _PAPER_METADATA.fullmatch(name)
        if match is None:
            continue
        identifier = match.group(1)
        pdf = members.get(f"artifacts/papers/{identifier}.pdf")
        if pdf is None:
            raise ProjectError(f"Paper {identifier} has no PDF.")
        try:
            record = json.loads(data)
        except (ValueError, UnicodeDecodeError) as exc:
            raise ProjectError("Saved paper metadata is invalid.") from exc
        pdf_sha = hashlib.sha256(pdf).hexdigest()
        if (
            not isinstance(record, dict)
            or record.get("paper_id") != identifier
            or record.get("pdf_sha256") != pdf_sha
            or record.get("pdf_size_bytes") != len(pdf)
        ):
            raise ProjectError("Saved paper failed its PDF integrity check.")
        score = paper_scores.validate_score(record.get("score"), pdf_sha)
        total = score["total"] if score is not None else None
        if total is not None:
            best = max(best or 0, total)
        papers.append(
            (
                total if total is not None else -1,
                int(record.get("paper_version") or 0),
                str(record.get("created_at") or ""),
                identifier,
            )
        )
    if not papers:
        raise ProjectError("A curated sample must contain at least one published paper.")
    papers.sort(reverse=True)
    sessions = sum(
        1 for name in members if re.fullmatch(r"research-sessions/[0-9a-f-]{36}\.json", name)
    )
    return papers[0][3], best, len(papers), sessions


def _git(root: Path, *args: str, check: bool = True) -> subprocess.CompletedProcess[str]:
    result = subprocess.run(
        ["git", "-C", str(root), *args],
        text=True,
        capture_output=True,
        check=False,
    )
    if check and result.returncode:
        raise ProjectError(result.stderr.strip() or f"git {args[0]} failed.")
    return result


def _publish(
    identifier: str,
    project_document: dict[str, Any],
    snapshot: dict[str, Any],
    curation: dict[str, Any],
) -> tuple[Path, str]:
    catalog = samples.SAMPLES
    root = catalog.parent.resolve()
    if _git(root, "rev-parse", "--show-toplevel").stdout.strip() != str(root):
        raise ProjectError("The Samples catalog must be in the current Git repository root.")
    if _git(root, "symbolic-ref", "--quiet", "--short", "HEAD", check=False).returncode:
        raise ProjectError("Switch to a branch before publishing a sample.")
    relative = f"samples/{identifier}"
    destination = catalog / identifier
    if destination.is_symlink() or _git(root, "status", "--porcelain", "--", relative).stdout:
        raise ProjectError("This sample has uncommitted changes; commit or restore them first.")

    # Stage and verify completely before replacing an existing sample.
    staged = Path(tempfile.mkdtemp(prefix=".sigma-sample-stage-", dir=catalog))
    backup = None
    published = False
    committed = False
    try:
        contents = {
            "project.json": project_document,
            SNAPSHOT_NAME: snapshot,
            CURATION_NAME: curation,
        }
        for filename, body in contents.items():
            (staged / filename).write_text(
                json.dumps(body, ensure_ascii=False, sort_keys=True, indent=2) + "\n",
                encoding="utf-8",
            )
        if destination.exists():
            backup = Path(tempfile.mkdtemp(prefix=".sigma-sample-backup-", dir=catalog))
            backup.rmdir()
            os.replace(destination, backup)
        os.replace(staged, destination)
        published = True
        _git(root, "add", "-A", "--", relative)
        if _git(root, "diff", "--cached", "--quiet", "--", relative, check=False).returncode:
            _git(
                root, "commit", "--only", "-m", f"Curate SIGMA sample: {identifier}", "--", relative
            )
            committed = True
        commit = _git(root, "rev-parse", "HEAD").stdout.strip()
        return destination, commit
    except BaseException:
        if published and not committed:
            _git(root, "reset", "-q", "HEAD", "--", relative, check=False)
            shutil.rmtree(destination, ignore_errors=True)
            if backup is not None and backup.exists():
                os.replace(backup, destination)
                backup = None
        elif backup is not None and not destination.exists() and backup.exists():
            os.replace(backup, destination)
            backup = None
        raise
    finally:
        if staged.exists():
            shutil.rmtree(staged, ignore_errors=True)
        if backup is not None and backup.exists():
            shutil.rmtree(backup, ignore_errors=True)


def promote_bundle(export_file: str | Path, name: str | None = None) -> dict[str, Any]:
    """Replace or create a matching sample and commit only its catalog files."""
    source = Path(export_file).expanduser().absolute()
    if source.is_symlink() or not source.is_file():
        raise ProjectError("Expected a regular project-bundle JSON file.")
    try:
        bundle = json.loads(source.read_text(encoding="utf-8"))
        members = project_bundle._decode(bundle)
        source_project = json.loads(members["project.json"])
        decode_project(source_project)
        title = _unversioned(source_project["title"])
        if not title:
            raise ProjectError("Sample title cannot be empty.")
        identifier = _sample_name(title, name)
        renamed = project_bundle.rename_bundle_project(bundle, title)
        members = {
            path: contents
            for path, contents in project_bundle._decode(renamed).items()
            if _is_publishable_member(path)
        }
        sample_id = str(uuid4())
        project = json.loads(members["project.json"])
        project["id"] = sample_id
        members["project.json"] = (json.dumps(project, ensure_ascii=False) + "\n").encode()
        safe = rebase_copy(
            project_bundle.portable_bundle(members),
            source_id=source_project["id"],
            new_id=sample_id,
            source_path="/sigma-original-sample-source",
            destination_path=_TEMPLATE_PATH,
            scrub_record=_scrubber(_account_emails(members)),
        )
        saved = project_bundle._decode(safe)
        project_bundle._verify_imported_papers(saved)
        project_document = json.loads(saved["project.json"])
        decode_project(project_document)
        featured, best, count, sessions = _paper_inventory(saved)
    except (
        OSError,
        UnicodeError,
        ValueError,
        TypeError,
        KeyError,
        project_bundle.BundleError,
    ) as exc:
        if isinstance(exc, ProjectError):
            raise
        raise ProjectError(f"Cannot publish project bundle: {exc}") from exc

    curation = {
        "schema_version": 1,
        "curated": True,
        "featured_paper_id": featured,
        "best_paper_score": best,
        "paper_count": count,
        "session_count": sessions,
    }
    destination, commit = _publish(identifier, project_document, safe, curation)
    return {
        "sample": identifier,
        "title": title,
        "path": str(destination),
        "paper_count": count,
        "session_count": sessions,
        "featured_paper_id": featured,
        "commit": commit,
    }
