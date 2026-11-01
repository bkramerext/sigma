"""Discover shipped sample projects and create independent working projects."""

import hashlib
import json
import os
import re
import shutil
import stat
from dataclasses import asdict, dataclass
from pathlib import Path
from typing import Any
from uuid import UUID, uuid4

from sigma.projects import (
    ROOT,
    STATE,
    ProjectError,
    ProjectView,
    _decode,
    _occupied_titles,
    _stage,
    _title_key,
    _title_registry_lock,
    inspect_project,
    projects_root,
)

SAMPLES = ROOT / "samples"
SAMPLE_EVIDENCE = "sample-evidence.json"
SAMPLE_LIMITS = "limits.json"
SAMPLE_PAPERS = "sample-papers"
MAX_EXPORT_BYTES = 32 * 1024 * 1024
MAX_SAMPLE_NAME = re.compile(r"^[a-z0-9](?:[a-z0-9-]{0,62}[a-z0-9])?$")
_SAMPLE_PROJECT_ID = "$SIGMA_SAMPLE_PROJECT_ID"
_SAMPLE_PROJECT_PATH = "$SIGMA_SAMPLE_PROJECT_PATH"
_SENSITIVE_FIELD = re.compile(
    r"(?:api[_-]?key|access[_-]?token|refresh[_-]?token|authorization|password|passwd|"
    r"secret|credential|cookie|identity[_-]?hash|guard[_-]?hash|idempotency[_-]?key|"
    r"client[_-]?secret|private[_-]?key|account[_-]?id|provider[_-]?account)",
    re.IGNORECASE,
)
_PRIVATE_FIELDS = {
    "account",
    "auth",
    "config",
    "configuration",
    "credentials",
    "identity",
    "private_config",
    "token",
}
_PATH_FIELD = re.compile(r"(?:^|[_-])(?:path|file|directory|root|home)(?:$|[_-])", re.IGNORECASE)
_USER_PATH = re.compile(
    r"(?<![A-Za-z0-9])(?:/Users/[^/\s\"'<>`,;]+(?:/[^\s\"'<>`,;]*)?|"
    r"/home/[^/\s\"'<>`,;]+(?:/[^\s\"'<>`,;]*)?|"
    r"[A-Za-z]:\\Users\\[^\\\s\"'<>`,;]+(?:\\[^\s\"'<>`,;]*)?)"
)
_LITERAL_SECRET = re.compile(
    r"(?i)\b(?:Bearer\s+[A-Za-z0-9._~+/=-]{16,}|sk-(?:proj-)?[A-Za-z0-9_-]{20,}|"
    r"gh[pousr]_[A-Za-z0-9]{20,}|AKIA[0-9A-Z]{16})\b"
)


@dataclass(frozen=True)
class SampleProject:
    id: str
    title: str
    problem: str
    investigation_type: str
    difficulty: str | None
    strategy_count: int


def _projects() -> list[tuple[str, Path]]:
    if not SAMPLES.is_dir() or SAMPLES.is_symlink():
        raise ProjectError("Samples catalog is unavailable.")
    return [
        (directory.name, directory / STATE)
        for directory in sorted(
            SAMPLES.iterdir(), key=lambda path: (path.name == "jesus-cannabis", path.name)
        )
        if directory.is_dir() and not directory.is_symlink() and (directory / STATE).is_file()
    ]


def _load(identifier: str) -> tuple[dict[str, Any], SampleProject]:
    match = next(((name, path) for name, path in _projects() if name == identifier), None)
    if match is None or match[1].is_symlink():
        raise ProjectError("Sample project was not found.")
    try:
        raw = json.loads(match[1].read_bytes())
        project = _decode(raw)
    except (OSError, ValueError, TypeError, KeyError) as exc:
        raise ProjectError(f"Sample project {identifier} is unavailable: {exc}") from exc
    return (
        raw,
        SampleProject(
            identifier,
            project.title,
            project.problem,
            project.investigation_type,
            project.difficulty.value if project.difficulty is not None else None,
            len(project.active_order),
        ),
    )


def _sanitize(value: Any, source_project_id: str | None = None, key: str = "") -> Any:
    """Remove private fields and replace user-specific references in exported evidence."""
    if isinstance(value, dict):
        clean: dict[str, Any] = {}
        for field, item in value.items():
            if (
                not isinstance(field, str)
                or _SENSITIVE_FIELD.search(field)
                or field.lower() in _PRIVATE_FIELDS
            ):
                continue
            if field.lower() == "project_path":
                clean[field] = _SAMPLE_PROJECT_PATH
            elif _PATH_FIELD.search(field):
                clean[field] = "[redacted path]"
            elif field.lower() == "project_id":
                clean[field] = _SAMPLE_PROJECT_ID
            else:
                clean[field] = _sanitize(item, source_project_id, field)
        return clean
    if isinstance(value, list):
        return [_sanitize(item, source_project_id, key) for item in value]
    if isinstance(value, str):
        sanitized = _USER_PATH.sub("[redacted user path]", value)
        sanitized = _LITERAL_SECRET.sub("[redacted credential]", sanitized)
        if source_project_id:
            sanitized = sanitized.replace(source_project_id, _SAMPLE_PROJECT_ID)
        return sanitized
    return value


def _sample_evidence(identifier: str) -> dict[str, Any]:
    match = next(((name, path) for name, path in _projects() if name == identifier), None)
    if match is None:
        raise ProjectError("Sample project was not found.")
    path = match[1].parent / SAMPLE_EVIDENCE
    if not path.exists() and not path.is_symlink():
        return {"schema_version": 1, "agentic_runs": [], "research_sessions": []}
    if path.is_symlink() or not path.is_file() or path.stat().st_size > MAX_EXPORT_BYTES:
        raise ProjectError("Sample evidence is unsafe or exceeds its size limit.")
    try:
        value = json.loads(path.read_text(encoding="utf-8"))
    except (OSError, ValueError) as exc:
        raise ProjectError("Sample evidence is unreadable.") from exc
    if (
        not isinstance(value, dict)
        or set(value) != {"schema_version", "agentic_runs", "research_sessions"}
        or value.get("schema_version") != 1
        or not isinstance(value.get("agentic_runs"), list)
        or not isinstance(value.get("research_sessions"), list)
    ):
        raise ProjectError("Sample evidence has an unsupported format.")
    return value


def _sample_limits(identifier: str) -> dict[str, Any] | None:
    """Load optional, validated limits for a shipped sample template."""
    match = next(((name, path) for name, path in _projects() if name == identifier), None)
    if match is None:
        raise ProjectError("Sample project was not found.")
    path = match[1].parent / SAMPLE_LIMITS
    if not path.exists() and not path.is_symlink():
        return None
    if path.is_symlink() or not path.is_file() or path.stat().st_size > 4096:
        raise ProjectError("Sample limits are unsafe or exceed their size limit.")
    try:
        value = json.loads(path.read_text(encoding="utf-8"))
        from sigma.research_sessions import DEFAULT_LIMITS, _validate_limits

        if not isinstance(value, dict) or not set(value) <= set(DEFAULT_LIMITS):
            raise ValueError("Invalid sample limits")
        return _validate_limits(value)
    except (OSError, ValueError, TypeError) as exc:
        raise ProjectError("Sample limits are invalid.") from exc


def _sample_papers(identifier: str) -> dict[str, tuple[dict[str, Any], bytes]]:
    directory = SAMPLES / identifier / SAMPLE_PAPERS
    if not directory.exists() and not directory.is_symlink():
        return {}
    if directory.is_symlink() or not directory.is_dir():
        raise ProjectError("Sample paper storage is unsafe.")
    entries = list(directory.iterdir())
    if any(item.is_symlink() or not item.is_file() for item in entries):
        raise ProjectError("Sample paper storage is unsafe.")
    names = {item.name for item in entries}
    json_ids = {item.stem for item in entries if item.suffix == ".json"}
    if (
        len(json_ids) > 50
        or names != {f"{paper_id}{suffix}" for paper_id in json_ids for suffix in (".json", ".pdf")}
        or sum(item.stat().st_size for item in entries) > MAX_EXPORT_BYTES
    ):
        raise ProjectError("Sample paper files are incomplete or exceed their storage bounds.")
    papers: dict[str, tuple[dict[str, Any], bytes]] = {}
    for metadata_path in sorted(directory.glob("*.json")):
        paper_id = metadata_path.stem
        pdf_path = directory / f"{paper_id}.pdf"
        if (
            not re.fullmatch(r"[0-9a-f]{32}", paper_id)
            or metadata_path.is_symlink()
            or not metadata_path.is_file()
            or metadata_path.stat().st_size > 12 * 1024 * 1024
            or pdf_path.is_symlink()
            or not pdf_path.is_file()
            or pdf_path.stat().st_size > 12 * 1024 * 1024
        ):
            raise ProjectError("Sample paper metadata or PDF is unsafe.")
        try:
            record = json.loads(metadata_path.read_text(encoding="utf-8"))
            pdf = pdf_path.read_bytes()
        except (OSError, ValueError) as exc:
            raise ProjectError("Sample paper is unreadable.") from exc
        if (
            not isinstance(record, dict)
            or record.get("paper_id") != paper_id
            or record.get("project_id") != _SAMPLE_PROJECT_ID
            or not isinstance(record.get("tex_source"), str)
            or not record["tex_source"].strip()
            or record.get("pdf_size_bytes") != len(pdf)
            or record.get("pdf_sha256") != hashlib.sha256(pdf).hexdigest()
        ):
            raise ProjectError("Sample paper provenance is invalid.")
        _validate_pdf_bytes(pdf)
        papers[paper_id] = (record, pdf)
    return papers


def _validate_pdf_bytes(pdf: bytes) -> None:
    """Require a parseable PDF with at least one page, not only a magic header."""
    if len(pdf) > 12 * 1024 * 1024:
        raise ProjectError("Sample paper PDF exceeds its safe storage limit.")
    try:
        import pypdfium2

        document = pypdfium2.PdfDocument(pdf)
        try:
            if len(document) < 1:
                raise ProjectError("Sample paper PDF contains no pages.")
        finally:
            document.close()
    except ProjectError:
        raise
    except (ValueError, RuntimeError, TypeError) as exc:
        raise ProjectError("Sample paper PDF is invalid or unreadable.") from exc


def _validate_export(value: Any) -> tuple[dict[str, Any], dict[str, Any], dict[str, bytes]]:
    paper_members: dict[str, bytes] = {}
    if isinstance(value, dict) and value.get("format") == "sigma.project.bundle":
        from sigma.project_bundle import BundleError
        from sigma.project_bundle import _decode as _decode_bundle

        try:
            members = _decode_bundle(value)
            project_document = json.loads(members["project.json"])
            sessions = [
                json.loads(contents)
                for name, contents in members.items()
                if name.startswith("research-sessions/")
                and name.endswith(".json")
                and name
                not in {
                    "research-sessions/limits.json",
                    "research-sessions/sequence.json",
                    "research-sessions/obligation-ids.json",
                }
            ]
            runs = [
                json.loads(contents)
                for name, contents in members.items()
                if name.startswith("agentic-runs/") and name.endswith(".json")
            ]
        except (BundleError, KeyError, ValueError, UnicodeDecodeError) as exc:
            raise ProjectError("Expected a valid complete SIGMA project bundle.") from exc
        value = {
            "export_version": 2,
            "project": project_document,
            "agentic_runs": runs,
            "research_sessions": sessions,
        }
        paper_members = {
            name: contents
            for name, contents in members.items()
            if name.startswith("artifacts/papers/")
        }
    if isinstance(value, dict) and value.get("continuations"):
        raise ProjectError(
            "Sample conversion of continuation approvals is not supported; preserve the Project Audit JSON and working project to retain lineage."
        )
    if (
        not isinstance(value, dict)
        or set(value) != {"export_version", "project", "agentic_runs", "research_sessions"}
        or value.get("export_version") != 2
        or type(value.get("export_version")) is not int
        or not isinstance(value.get("agentic_runs"), list)
        or not isinstance(value.get("research_sessions"), list)
    ):
        raise ProjectError("Expected a SIGMA project export (JSON export_version 2).")
    project_raw = value.get("project")
    if isinstance(project_raw, dict) and isinstance(project_raw.get("events"), list):
        # The API's dataclass export includes null optional Event fields, while
        # the canonical project document omits them. Normalize that known
        # representation difference before using the strict project decoder.
        project_raw = {
            **project_raw,
            "events": [
                {
                    key: item
                    for key, item in event.items()
                    if key
                    not in {
                        "strategy_id",
                        "change",
                        "stage_change",
                        "order",
                        "project_change",
                        "enabled_change",
                    }
                    or item is not None
                }
                if isinstance(event, dict)
                else event
                for event in project_raw["events"]
            ],
        }
    project = _decode(project_raw)
    source_id = project.id
    for record in value["research_sessions"]:
        if (
            not isinstance(record, dict)
            or record.get("project_id") != source_id
            or not isinstance(record.get("id"), str)
        ):
            raise ProjectError("Exported research session does not match the exported project.")
        try:
            UUID(record["id"])
        except (ValueError, TypeError) as exc:
            raise ProjectError("Exported research session has an invalid ID.") from exc
    for record in value["agentic_runs"]:
        if (
            not isinstance(record, dict)
            or type(record.get("schema_version")) is not int
            or record.get("schema_version") != 1
            or record.get("project_id") != source_id
            or not isinstance(record.get("run_id"), str)
        ):
            raise ProjectError("Exported agentic evidence does not match the exported project.")
        try:
            if UUID(hex=record["run_id"]).hex != record["run_id"]:
                raise ValueError
        except (ValueError, TypeError, AttributeError) as exc:
            raise ProjectError("Exported agentic evidence has an invalid run ID.") from exc

    clean_project = _sanitize(project_raw, source_id)
    clean_project["id"] = str(uuid4())
    _decode(clean_project)
    clean_sessions = _sanitize(value["research_sessions"], source_id)
    clean_runs = _sanitize(value["agentic_runs"], source_id)
    from sigma import agentic_evidence, research_sessions

    session_bytes = 0
    for record in clean_sessions:
        if not all(isinstance(record.get(key), list) for key in ("steps", "artifacts", "events")):
            raise ProjectError("Exported research session is missing reconstructable history.")
        record_size = len(
            (
                json.dumps(
                    {**record, "project_path": "x" * 4096},
                    ensure_ascii=False,
                    separators=(",", ":"),
                )
                + "\n"
            ).encode("utf-8")
        )
        if record_size > research_sessions.MAX_RECORD:
            raise ProjectError("Exported research session exceeds the existing record size limit.")
        session_bytes += record_size
    if session_bytes > research_sessions.MAX_TOTAL:
        raise ProjectError("Exported research sessions exceed the existing project history limit.")
    if len(clean_runs) > agentic_evidence.MAX_RECORDS:
        raise ProjectError("Exported agentic runs exceed the existing retention count.")
    run_bytes = sum(len(agentic_evidence._encoded(record)) for record in clean_runs)
    if run_bytes > agentic_evidence.MAX_TOTAL_BYTES:
        raise ProjectError("Exported agentic runs exceed the existing retention size limit.")
    evidence = {
        "schema_version": 1,
        "agentic_runs": clean_runs,
        "research_sessions": clean_sessions,
    }
    clean_papers: dict[str, bytes] = {}
    if paper_members:
        identifiers = {
            name.removeprefix("artifacts/papers/").removesuffix(".json")
            for name in paper_members
            if name.endswith(".json")
        }
        if len(identifiers) > 50:
            raise ProjectError("Exported papers exceed the existing per-project retention count.")
        expected_members = {
            f"artifacts/papers/{identifier}{suffix}"
            for identifier in identifiers
            for suffix in (".json", ".pdf")
        }
        if set(paper_members) != expected_members:
            raise ProjectError("Exported paper files are incomplete or have unsupported names.")
        for identifier in identifiers:
            if not re.fullmatch(r"[0-9a-f]{32}", identifier):
                raise ProjectError("Exported paper has an invalid identifier.")
            json_name = f"artifacts/papers/{identifier}.json"
            pdf_name = f"artifacts/papers/{identifier}.pdf"
            if json_name not in paper_members or pdf_name not in paper_members:
                raise ProjectError("Exported paper is missing its metadata or PDF file.")
            if len(paper_members[json_name]) + len(paper_members[pdf_name]) > 12 * 1024 * 1024:
                raise ProjectError("Exported paper exceeds its safe storage limit.")
            try:
                paper = json.loads(paper_members[json_name])
            except (ValueError, UnicodeDecodeError) as exc:
                raise ProjectError("Exported paper metadata is unreadable.") from exc
            pdf = paper_members[pdf_name]
            if (
                not isinstance(paper, dict)
                or paper.get("paper_id") != identifier
                or paper.get("project_id") != source_id
                or not isinstance(paper.get("tex_source"), str)
                or not paper["tex_source"].strip()
                or paper.get("pdf_size_bytes") != len(pdf)
                or paper.get("pdf_sha256") != hashlib.sha256(pdf).hexdigest()
            ):
                raise ProjectError("Exported paper identity, TeX, or PDF provenance is invalid.")
            _validate_pdf_bytes(pdf)
            clean_paper = _sanitize(paper, source_id)
            clean_papers[f"{identifier}.json"] = (
                json.dumps(clean_paper, ensure_ascii=False, separators=(",", ":")) + "\n"
            ).encode("utf-8")
            clean_papers[f"{identifier}.pdf"] = pdf
    return clean_project, evidence, clean_papers


def make_sample(export_file: str | Path, name: str) -> Path:
    """Create a Samples catalog entry from the JSON project export contract."""
    if not isinstance(name, str) or not MAX_SAMPLE_NAME.fullmatch(name):
        raise ProjectError(
            "Sample name must use lowercase letters, digits, and hyphens; it cannot start or end with a hyphen."
        )
    if SAMPLES.is_symlink() or not SAMPLES.is_dir():
        raise ProjectError("Samples catalog is unavailable.")
    source = Path(export_file).expanduser().absolute()
    if source.is_symlink():
        raise ProjectError("Export file must be a regular, non-symlink JSON file.")
    try:
        descriptor = os.open(source, os.O_RDONLY | getattr(os, "O_NOFOLLOW", 0))
        try:
            metadata = os.fstat(descriptor)
            if not stat.S_ISREG(metadata.st_mode):
                raise ProjectError("Export file must be a regular, non-symlink JSON file.")
            if metadata.st_size > MAX_EXPORT_BYTES:
                raise ProjectError("Export file exceeds the 32 MB import limit.")
            chunks = bytearray()
            while len(chunks) <= MAX_EXPORT_BYTES:
                chunk = os.read(descriptor, min(1024 * 1024, MAX_EXPORT_BYTES + 1 - len(chunks)))
                if not chunk:
                    break
                chunks.extend(chunk)
            raw_bytes = bytes(chunks)
        finally:
            os.close(descriptor)
        if len(raw_bytes) > MAX_EXPORT_BYTES:
            raise ProjectError("Export file exceeds the 32 MB import limit.")
        exported = json.loads(raw_bytes)
    except ProjectError:
        raise
    except (OSError, ValueError, UnicodeError) as exc:
        raise ProjectError("Export file is unreadable or is not valid UTF-8 JSON.") from exc
    try:
        project, evidence, papers = _validate_export(exported)
    except RecursionError as exc:
        raise ProjectError("Export structure is too deeply nested to sanitize safely.") from exc
    project_bytes = (json.dumps(project, ensure_ascii=False, indent=2) + "\n").encode("utf-8")
    evidence_bytes = (json.dumps(evidence, ensure_ascii=False, indent=2) + "\n").encode("utf-8")
    if len(evidence_bytes) > MAX_EXPORT_BYTES:
        raise ProjectError("Sanitized sample evidence exceeds the 32 MB storage limit.")
    if sum(map(len, papers.values())) > MAX_EXPORT_BYTES:
        raise ProjectError("Sanitized sample papers exceed the 32 MB storage limit.")
    destination = SAMPLES / name
    try:
        destination.mkdir(mode=0o755)
    except FileExistsError as exc:
        raise ProjectError(f"Sample '{name}' already exists.") from exc
    except OSError as exc:
        raise ProjectError(f"Cannot create sample: {exc}") from exc
    try:
        for filename, contents in ((STATE, project_bytes), (SAMPLE_EVIDENCE, evidence_bytes)):
            staged = _stage(destination, contents)
            try:
                os.chmod(staged, 0o644)
                os.link(staged, destination / filename)
            finally:
                staged.unlink(missing_ok=True)
        if papers:
            paper_directory = destination / SAMPLE_PAPERS
            paper_directory.mkdir(mode=0o755)
            for filename, contents in papers.items():
                staged = _stage(paper_directory, contents)
                try:
                    os.chmod(staged, 0o644)
                    os.link(staged, paper_directory / filename)
                finally:
                    staged.unlink(missing_ok=True)
        return destination
    except BaseException as exc:
        # The destination was exclusively created above for this operation.
        # Remove the complete partial tree, including a paper directory, so a
        # failed copy never appears later as a valid catalog sample.
        if not destination.is_symlink() and destination.parent == SAMPLES:
            shutil.rmtree(destination, ignore_errors=True)
        if isinstance(exc, OSError):
            raise ProjectError(f"Cannot save sample: {exc}") from exc
        raise


def _rebind_history(
    value: Any, project_id: str, project_path: str, session_ids: dict[str, str]
) -> Any:
    if isinstance(value, dict):
        result = {}
        for key, item in value.items():
            if key == "project_path":
                result[key] = project_path
            elif key == "project_id":
                result[key] = project_id
            else:
                result[key] = _rebind_history(item, project_id, project_path, session_ids)
        return result
    if isinstance(value, list):
        return [_rebind_history(item, project_id, project_path, session_ids) for item in value]
    if isinstance(value, str):
        if value in session_ids:
            return session_ids[value]
        if value == _SAMPLE_PROJECT_ID:
            return project_id
    return value


def _install_sample_evidence(
    destination: Path,
    project_id: str,
    evidence: dict[str, Any],
    session_ids: dict[str, str] | None = None,
) -> None:
    from sigma import agentic_evidence, research_sessions

    canonical_path = str(destination.resolve())
    # A sample's saved session IDs are template data. Each copy needs its own
    # IDs because the hosted research ledger is shared across workspaces and
    # enforces one owner/project for each session ID.
    session_ids = session_ids or {
        raw["id"]: str(uuid4())
        for raw in evidence["research_sessions"]
        if isinstance(raw, dict) and isinstance(raw.get("id"), str)
    }
    for raw in evidence["research_sessions"]:
        record = _rebind_history(raw, project_id, canonical_path, session_ids)
        record["project_id"] = project_id
        record["project_path"] = canonical_path
        research_sessions._save(canonical_path, record)
    for raw in evidence["agentic_runs"]:
        record = _rebind_history(raw, project_id, canonical_path, session_ids)
        agentic_evidence.save(destination, record)


def _discard_partial_copy(destination: Path) -> None:
    """Remove only regular files created in a reserved, not-yet-published copy."""
    for directory_name in ("research-sessions", "agentic-runs"):
        directory = destination / directory_name
        if directory.is_symlink() or not directory.is_dir():
            continue
        for item in directory.iterdir():
            if not item.is_symlink() and item.is_file():
                item.unlink(missing_ok=True)
        try:
            directory.rmdir()
        except OSError:
            pass
    for directory_name in ("papers", "artifacts/papers"):
        directory = destination / directory_name
        if directory.is_symlink() or not directory.is_dir():
            continue
        for item in directory.iterdir():
            if not item.is_symlink() and item.is_file():
                item.unlink(missing_ok=True)
        try:
            directory.rmdir()
            (destination / "artifacts").rmdir()
        except OSError:
            pass
    for filename in (STATE, ".agentic-runs.lock"):
        item = destination / filename
        if not item.is_symlink() and item.is_file():
            item.unlink(missing_ok=True)
    try:
        destination.rmdir()
    except OSError:
        pass


def sample_projects() -> dict[str, list[dict[str, Any]]]:
    """The Sample list always describes the untouched templates, not working projects."""
    return {"projects": [asdict(_load(name)[1]) for name, _ in _projects()]}


def sample_project_ids() -> set[str]:
    return {_load(name)[0]["id"] for name, _ in _projects()}


def open_sample_project(identifier: str) -> ProjectView:
    """Create an independent working project named 'Title v1', etc."""
    raw, _ = _load(identifier)
    evidence = _sample_evidence(identifier)
    limits = _sample_limits(identifier)
    papers = _sample_papers(identifier)
    root = projects_root()
    if root.is_relative_to(SAMPLES):
        raise ProjectError("Sample projects cannot be installed inside the source catalog.")

    with _title_registry_lock(root):
        occupied = _occupied_titles(root)
        working_title = ""
        for number in range(1, 10001):
            suffix = f" v{number}"
            title = raw["title"][: 200 - len(suffix)].rstrip() + suffix
            if _title_key(title) not in occupied:
                working_title = title
                break
        if not working_title:
            raise ProjectError("Too many working projects from this sample.")

        # Display-name suffixes are independent of directory numbering. A
        # previous release may have installed a sample project at sample.sigma.
        destination: Path | None = None
        for number in range(1, 10001):
            directory_suffix = "" if number == 1 else f"-{number}"
            candidate = root / f"{identifier}{directory_suffix}.sigma"
            try:
                candidate.mkdir(mode=0o700)
                destination = candidate
                break
            except FileExistsError:
                continue
            except OSError as exc:
                raise ProjectError(f"Cannot create sample working project: {exc}") from exc
        if destination is None:
            raise ProjectError("Too many copies of this sample project.")

        staged: Path | None = None
        try:
            copied = {**raw, "id": str(uuid4()), "title": working_title}
            # Keep the strategies and their history, but give this project
            # its own identity and a distinct display name.
            _decode(copied)
            staged = _stage(destination, (json.dumps(copied, indent=2) + "\n").encode("utf-8"))
            os.link(staged, destination / STATE)
            view = inspect_project(destination)
            session_ids = {
                raw["id"]: str(uuid4())
                for raw in evidence["research_sessions"]
                if isinstance(raw, dict) and isinstance(raw.get("id"), str)
            }
            if limits is not None:
                from sigma.research_sessions import save_limits

                save_limits(str(destination), limits)
            if papers:
                paper_directory = destination / "papers"
                paper_directory.mkdir(parents=True, mode=0o700)
                for paper_id, (sample_record, pdf) in papers.items():
                    record = _rebind_history(
                        sample_record,
                        view.project.id,
                        str(destination.resolve()),
                        session_ids,
                    )
                    metadata = (
                        json.dumps(record, ensure_ascii=False, separators=(",", ":")) + "\n"
                    ).encode("utf-8")
                    for suffix, contents in ((".json", metadata), (".pdf", pdf)):
                        staged_paper = _stage(paper_directory, contents)
                        try:
                            os.link(staged_paper, paper_directory / f"{paper_id}{suffix}")
                        finally:
                            staged_paper.unlink(missing_ok=True)
            view = inspect_project(destination)
            _install_sample_evidence(destination, view.project.id, evidence, session_ids)
            view = inspect_project(destination)
        except Exception as exc:
            _discard_partial_copy(destination)
            raise ProjectError(f"Cannot open sample working project: {exc}") from exc
        finally:
            if staged is not None:
                staged.unlink(missing_ok=True)

    from sigma.recents import record_access

    record_access(view)
    return view
