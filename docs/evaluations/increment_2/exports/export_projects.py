"""Capture actual SIGMA API export bytes from exercised disposable projects.

No provider sessions are started. Run from the repository root with an explicit
owned --projects-root if the study's retained working copies are elsewhere.
"""

import argparse
import hashlib
import json
import os
import subprocess
import tempfile
from datetime import UTC, datetime
from pathlib import Path

parser = argparse.ArgumentParser()
parser.add_argument(
    "--projects-root", type=Path, default=Path("/tmp/sigma-research-experience-blue/projects")
)
parser.add_argument("--output", type=Path, default=Path(__file__).resolve().parent)
args = parser.parse_args()
projects = args.projects_root.resolve()
output = args.output
output.mkdir(parents=True, exist_ok=True)
for key in list(os.environ):
    if key.startswith(("SIGMA_", "OPENAI_", "ANTHROPIC_")):
        os.environ.pop(key)
os.environ["SIGMA_PROJECTS_ROOT"] = str(projects)

with tempfile.TemporaryDirectory(prefix="sigma-export-only-") as temporary:
    for key, name in [
        ("SIGMA_STATE_DIR", "state"),
        ("SIGMA_AUTH_HOME", "auth"),
        ("SIGMA_CLOUD_AUTH_HOME", "cloud"),
    ]:
        directory = Path(temporary) / name
        directory.mkdir(mode=0o700)
        os.environ[key] = str(directory)
    import httpx

    class OfflineClient(httpx.AsyncClient):
        def __init__(self, *args, **kwargs):
            kwargs["transport"] = httpx.MockTransport(
                lambda request: httpx.Response(
                    503, json={"error": "No external provider requests in export capture"}
                )
            )
            super().__init__(*args, **kwargs)

    httpx.AsyncClient = OfflineClient
    from fastapi.testclient import TestClient

    from sigma.api import app

    manifest = {
        "captured_at": datetime.now(UTC).isoformat(),
        "app_revision": subprocess.check_output(["git", "rev-parse", "HEAD"], text=True).strip(),
        "method": "Actual GET responses from SIGMA's own Project Audit and deterministic report API, bytes preserved",
        "new_live_provider_calls": 0,
        "new_research_sessions": 0,
        "markdown_limit": "SIGMA has no native Markdown project-report export. Markdown-valued Outcome Conclusion fields, including historical fallbacks, are retained in audit JSON. No manually reconstructed Markdown is substituted.",
        "limitations": [
            "Audit Outcomes are SIGMA's current public projection, not a byte copy of stored session JSON.",
            "Internal guards/auth fields are excluded by SIGMA's standard export. No additional content was redacted or omitted.",
            "No AI paper authoring or PDF compilation performed; TeX/HTML/text are deterministic reports.",
        ],
        "projects": [],
    }
    with TestClient(app) as client:
        for slug, evidence_class, activity in [
            (
                "maximum-regions-archived",
                "historical provider archive; no fresh live research",
                "Earlier preserved four-call Maximum Regions provider investigation. This workspace was opened in actual Chrome for proof/objection inspection, findings-fork draft inspection (cancelled), and HTML export. No argument enrichment; only project_path relocated when importing the archive.",
            ),
            (
                "nonconsecutive-subset-sums",
                "five explicitly deterministic archived fixture sessions; not live research",
                "Actual Chrome review of five saved fixture sessions and computational evidence. The evaluator manually saved Close the phase-matrix proof obligation, toggled eligibility, reloaded and reopened. No new investigation or computation by SIGMA.",
            ),
            (
                "maximum-regions-by-lines",
                "stock sample working copy; no research sessions",
                "Actual Chrome opening, manual Separate the bound from attainment strategy fork, save/reload/eligibility/Recent and text export. The stock copy has no saved research session; it is distinct from the historical provider archive.",
            ),
        ]:
            path = projects / (slug + ".sigma")
            if not path.is_dir():
                raise RuntimeError(f"Exercised working copy unavailable: {path}")
            before = {
                str(p.relative_to(path)): hashlib.sha256(p.read_bytes()).hexdigest()
                for p in path.rglob("*")
                if p.is_file()
            }
            audit_response = client.get("/api/projects/export", params={"path": str(path)})
            assert audit_response.status_code == 200, audit_response.text
            audit = audit_response.json()

            def check_secrets(value):
                if isinstance(value, dict):
                    for key, child in value.items():
                        if (
                            key.casefold()
                            in {
                                "access_token",
                                "refresh_token",
                                "authorization",
                                "client_secret",
                                "openai_api_key",
                            }
                            and child
                        ):
                            raise RuntimeError("Credential field present; export not committed")
                        check_secrets(child)
                elif isinstance(value, list):
                    for child in value:
                        check_secrets(child)
                elif isinstance(value, str) and value.startswith(("sk-proj-", "Bearer ")):
                    raise RuntimeError("Credential-shaped value present; export not committed")

            check_secrets(audit)
            files = []
            filename = slug + ".audit.json"
            (output / filename).write_bytes(audit_response.content)
            files.append(
                {
                    "path": filename,
                    "format": "SIGMA Project Audit JSON",
                    "sha256": hashlib.sha256(audit_response.content).hexdigest(),
                    "bytes": len(audit_response.content),
                }
            )
            for format in ("txt", "html", "tex"):
                response = client.get(
                    "/api/projects/export/report", params={"path": str(path), "format": format}
                )
                assert response.status_code == 200, response.text
                filename = slug + ".report." + format
                (output / filename).write_bytes(response.content)
                files.append(
                    {
                        "path": filename,
                        "format": format,
                        "sha256": hashlib.sha256(response.content).hexdigest(),
                        "bytes": len(response.content),
                    }
                )
            after = {
                str(p.relative_to(path)): hashlib.sha256(p.read_bytes()).hexdigest()
                for p in path.rglob("*")
                if p.is_file()
            }
            assert before == after, "Export changed the exercised project"
            manifest["projects"].append(
                {
                    "slug": slug,
                    "project_id": audit["project"]["id"],
                    "title": audit["project"]["title"],
                    "evidence_class": evidence_class,
                    "actual_activity": activity,
                    "strategy_count": len(audit["project"]["strategies"]),
                    "session_ids": [row["id"] for row in audit["research_sessions"]],
                    "artifact_ids": [
                        a["id"] for row in audit["research_sessions"] for a in row["artifacts"]
                    ],
                    "files": files,
                    "source_file_sha256": before,
                    "source_bytes_unchanged": True,
                    "research_content_omissions": [],
                }
            )
    (output / "MANIFEST.json").write_text(json.dumps(manifest, indent=2, ensure_ascii=False) + "\n")
    print(
        json.dumps(
            {
                "projects": len(manifest["projects"]),
                "exports": sum(len(p["files"]) for p in manifest["projects"]),
                "revision": manifest["app_revision"],
                "provider_calls": 0,
            }
        )
    )
