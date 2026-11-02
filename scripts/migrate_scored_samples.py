"""Inventory and migrate saved scored project versions to the public Samples catalog.

Only a *saved* valid score under each project's papers/ (or the equivalent
artifacts/papers/ in a single-file project bundle) is eligible. Scores are
never inferred from a standalone PDF or re-evaluated with an AI provider.
Run against the real local/workspace storage on a quiescent snapshot.

Example:
    python -m scripts.migrate_scored_samples --root /path/to/projects
    python -m scripts.migrate_scored_samples --root /path/to/projects --apply

For hosted storage, use --root /path/to/private/workspaces; the resulting
samples/ files must be reviewed and committed to the deployment branch.
"""

from __future__ import annotations

import argparse
import hashlib
import json
import os
import re
import sys
import tempfile
import unicodedata
from dataclasses import dataclass
from pathlib import Path
from typing import Any
from uuid import UUID

from sigma import paper_scores, project_bundle, samples
from sigma.projects import ProjectError

_RESEARCH_PREFIXES = ("research-sessions/", "agentic-runs/", "evidence/agentic-runs/")


@dataclass(frozen=True)
class Candidate:
    directory: Path
    project_id: str
    project_title: str
    paper_id: str
    paper_title: str
    score: int
    pdf_sha256: str

    @property
    def sample_id(self) -> str:
        normalized = unicodedata.normalize("NFKD", self.project_title).casefold()
        slug = re.sub(r"[^a-z0-9]+", "-", normalized).strip("-")
        digest = hashlib.sha256(self.project_id.encode("utf-8")).hexdigest()[:12]
        return f"{slug[:48].rstrip('-') or 'project'}-{digest}"


def saved_projects(roots: list[Path]) -> list[Path]:
    """Find directory-backed and single-file saved projects in explicit roots."""
    found: set[Path] = set()
    for root in roots:
        if root.is_symlink() or not root.is_dir():
            raise ValueError(f"Source root is not a safe directory: {root}")
        for current, children, files in os.walk(root, followlinks=False):
            directory = Path(current)
            children[:] = sorted(
                item
                for item in children
                if not (directory / item).is_symlink() and item not in {".git", "samples"}
            )
            if directory.suffix == ".sigma":
                children.clear()
                project_file = directory / "project.json"
                if project_file.is_file() and not project_file.is_symlink():
                    found.add(directory.resolve())
                continue
            for name in sorted(files):
                if not name.endswith(".json"):
                    continue
                candidate = directory / name
                if candidate.is_symlink() or not candidate.is_file():
                    continue
                try:
                    document = json.loads(candidate.read_text(encoding="utf-8"))
                except (OSError, ValueError, UnicodeError):
                    continue
                if isinstance(document, dict) and document.get("format") == project_bundle.FORMAT:
                    found.add(candidate.resolve())
    return sorted(found)


def _source_members(source: Path) -> tuple[dict[str, Any], dict[str, bytes], str]:
    """Read original saved artifacts without modifying a live project."""
    if source.is_symlink():
        raise ValueError("Project source must not be a symbolic link")
    if source.is_file() and source.suffix == ".json":
        bundle = json.loads(source.read_text(encoding="utf-8"))
        members = project_bundle._decode(bundle)
        # Hosted exports use artifacts/papers/, but bundles exported from an
        # on-disk .sigma project use papers/. Accept both without silently
        # choosing between duplicate artifacts in a mixed-layout bundle.
        for name in list(members):
            if name.startswith("papers/"):
                normalized = "artifacts/" + name
                if normalized in members:
                    raise ValueError(f"Duplicate paper artifact in saved bundle: {normalized}")
                members[normalized] = members.pop(name)
        return json.loads(members["project.json"]), members, "artifacts/papers/"
    if not source.is_dir() or source.suffix != ".sigma":
        raise ValueError("Project source must be a .sigma directory or JSON project bundle")
    project = json.loads((source / "project.json").read_text(encoding="utf-8"))
    members: dict[str, bytes] = {}
    for name in ("papers", "research-sessions", "agentic-runs"):
        directory = source / name
        if not directory.exists() and not directory.is_symlink():
            continue
        if directory.is_symlink() or not directory.is_dir():
            raise ValueError(f"Unsafe {name}/ directory")
        for item in sorted(directory.iterdir()):
            if item.is_symlink():
                raise ValueError(f"Unsafe {name}/ member")
            if item.is_file() and (name == "papers" or item.suffix == ".json"):
                members[f"{name}/{item.name}"] = item.read_bytes()
    return project, members, "papers/"


def _has_research_evidence(members: dict[str, bytes], project_id: str) -> bool:
    """Require actual saved research history, not a paper-only project shell."""
    for name, contents in members.items():
        if not name.endswith(".json") or not name.startswith(_RESEARCH_PREFIXES):
            continue
        try:
            record = json.loads(contents)
        except (ValueError, UnicodeError):
            continue
        if (
            isinstance(record, dict)
            and record.get("project_id") == project_id
            and any(record.get(key) for key in ("steps", "artifacts", "timeline"))
        ):
            return True
    return False


def qualifying_project(directory: Path) -> Candidate | None:
    """Use the original PDF and rubric validator, ignoring invalid/stale scores."""
    project, members, paper_prefix = _source_members(directory)
    project_id, title = project["id"], project["title"]
    UUID(project_id)
    if not isinstance(title, str) or not title:
        raise ValueError("Invalid project title")
    best: Candidate | None = None
    for name in sorted(members):
        if not name.startswith(paper_prefix) or not name.endswith(".json"):
            continue
        paper_id = name.removeprefix(paper_prefix).removesuffix(".json")
        if not re.fullmatch("[0-9a-f]{32}", paper_id):
            raise ValueError("Unsafe paper metadata filename")
        record: dict[str, Any] = json.loads(members[name])
        pdf = members.get(f"{paper_prefix}{paper_id}.pdf")
        if pdf is None:
            continue
        sha = hashlib.sha256(pdf).hexdigest()
        if (
            record.get("paper_id") != paper_id
            or record.get("project_id") != project_id
            or record.get("pdf_sha256") != sha
            or record.get("pdf_size_bytes") != len(pdf)
            or not isinstance(record.get("tex_source"), str)
            or not record["tex_source"].strip()
        ):
            continue
        score = paper_scores.validate_score(record.get("score"), sha)
        if score is None or score["total"] < 50:
            continue
        draft = record.get("draft")
        paper_title = (
            draft.get("title")
            if isinstance(draft, dict) and isinstance(draft.get("title"), str)
            else record.get("title")
        )
        if not isinstance(paper_title, str) or not paper_title:
            paper_title = "(untitled paper)"
        current = Candidate(
            directory, project_id, title, paper_id, paper_title, score["total"], sha
        )
        if (
            best is None
            or current.score > best.score
            or (current.score == best.score and current.paper_id < best.paper_id)
        ):
            best = current
    if best is not None and not _has_research_evidence(members, project_id):
        raise ValueError("Scored saved paper has no original research evidence")
    return best


def install(candidate: Candidate) -> None:
    """Publish a sanitized *complete* saved project, preserving originals."""
    identifier = candidate.sample_id
    destination = samples.SAMPLES / identifier
    if destination.exists() or destination.is_symlink():
        raise ProjectError(f"Destination already exists: samples/{identifier}")
    if qualifying_project(candidate.directory) != candidate:
        raise ProjectError("Saved project or best scored paper changed during migration")
    with tempfile.TemporaryDirectory(prefix="sigma-sample-migration-") as temporary:
        export = Path(temporary) / "project-export.json"
        if candidate.directory.is_file():
            export.write_bytes(candidate.directory.read_bytes())
        else:
            export.write_bytes(project_bundle.encode(candidate.directory))
        samples.make_sample(export, identifier)
    try:
        score, paper_id = samples._best_sample_paper(identifier)
        if (score, paper_id) != (candidate.score, candidate.paper_id):
            raise ProjectError("Migrated best paper does not match the source")
        if hashlib.sha256(samples.top_sample_pdf(identifier)).hexdigest() != candidate.pdf_sha256:
            raise ProjectError("Migrated PDF bytes differ from the original saved PDF")
        evidence = samples._sample_evidence(identifier)
        if not (evidence["research_sessions"] or evidence["agentic_runs"]):
            raise ProjectError("Migrated research evidence is unavailable")
    except BaseException:
        import shutil

        shutil.rmtree(destination)
        raise


def run(roots: list[Path], *, apply: bool) -> int:
    paths = saved_projects(roots)
    selected: list[Candidate] = []
    problems: list[str] = []
    for directory in paths:
        try:
            candidate = qualifying_project(directory)
            if candidate:
                selected.append(candidate)
        except (OSError, ValueError, KeyError, TypeError) as exc:
            problems.append(f"{directory}: {exc}")
    print(f"Scanned {len(paths)} saved project versions; {len(selected)} score >= 50.")
    for candidate in selected:
        print(
            f"{candidate.project_title} | {candidate.project_id} | "
            f"{candidate.paper_title} | {candidate.score}/100 | "
            f"paper={candidate.paper_id} | PDF SHA-256={candidate.pdf_sha256} | "
            f"samples/{candidate.sample_id}"
        )
    if problems:
        for item in problems:
            print("ERROR:", item, file=sys.stderr)
        return 1
    if not selected:
        print("No qualifying saved paper records found in the provided source roots.")
        return 1
    if not apply:
        print("Dry run only. Use --apply after reviewing the inventory.")
        return 0
    for candidate in selected:
        try:
            install(candidate)
            print(f"PUBLISHED: samples/{candidate.sample_id}")
        except (OSError, ValueError, ProjectError) as exc:
            problems.append(f"{candidate.project_title}: {exc}")
            print("ERROR:", problems[-1], file=sys.stderr)
    return 1 if problems else 0


def main() -> int:
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument(
        "--root",
        action="append",
        type=Path,
        required=True,
        help="A local projects/ or hosted private workspaces/ root (repeatable)",
    )
    parser.add_argument(
        "--apply",
        action="store_true",
        help="Create sanitized source-controlled samples (never modify source projects)",
    )
    arguments = parser.parse_args()
    return run(arguments.root, apply=arguments.apply)


if __name__ == "__main__":
    sys.exit(main())
