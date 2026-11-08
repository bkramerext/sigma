"""Provider-free regression for per-user Ethos and three-field project bundles."""

from __future__ import annotations

import json
import os
import stat
from dataclasses import asdict
from pathlib import Path
from tempfile import TemporaryDirectory
from unittest.mock import patch

from fastapi.testclient import TestClient

from sigma import (
    papers,
    project_bundle,
    project_types,
    publication_audit,
    research_ethos,
    research_sessions,
)
from sigma.api import app
from sigma.projects import (
    _decode,
    _document,
    initialize_project,
    inspect_project,
    ProjectError,
    project_settings,
)


def main() -> None:
    with TemporaryDirectory() as directory:
        root = Path(directory)
        alice = root / "alice"
        bob = root / "bob"
        projects = root / "projects"
        for path in (alice, bob, projects):
            path.mkdir()

        with (
            patch.object(project_types, "_store_path", return_value=alice / "types.json"),
            patch.dict(os.environ, {"SIGMA_PROJECTS_ROOT": str(projects)}),
        ):
            defaults = research_ethos.current()
            assert defaults["is_override"] is False
            assert isinstance(defaults["markdown"], str)
            assert isinstance(defaults["sha256"], str)
            assert "Pursue discovery" in defaults["markdown"]
            assert len(defaults["sha256"]) == 64

            with TestClient(app) as client:
                received = client.get("/api/user-preferences/research-ethos")
                assert received.status_code == 200, received.text
                assert received.json() == defaults
                for invalid in ("", " ", "x" * (research_ethos.MAX_CHARS + 1)):
                    bad = client.put(
                        "/api/user-preferences/research-ethos",
                        json={"markdown": invalid},
                    )
                    assert bad.status_code == 400, bad.text
                override = "**Pursue testable discoveries** without inventing proof."
                saved = client.put(
                    "/api/user-preferences/research-ethos",
                    json={"markdown": override},
                )
                assert saved.status_code == 200, saved.text
                assert saved.json()["is_override"] is True

            state = research_ethos.frozen_snapshot()
            target = alice / research_ethos.FILENAME
            assert stat.S_IMODE(target.stat().st_mode) == 0o600
            assert state["markdown"] == override
            record = {
                "model": "gpt-6.1-sol",
                "mode": "api_key",
                "reasoning_effort": "high",
                "research_ethos": state,
                "desired_outcomes": "Improve understanding without false success.",
            }
            for role in ("investigator", "skeptic"):
                payload = research_sessions._role_request_payload(
                    record, role, {"investigation_type": "mathematical", "execution_tools": []}
                )
                assert override in payload["instructions"]
                assert payload["input"].find("Improve understanding") >= 0
                assert "research_ethos" not in json.loads(payload["input"])
                assert payload["instructions"].count(override) == 1
            assert override in papers._paper_ethos_instructions({"research_ethos": state})

            # All accepted publication obligations remain visible, even when
            # they cannot be verified without independent editorial judgment.
            reqs = "Include a counterexample table.\nDiscuss open limitations."
            empty_draft = {
                "sections": [{"heading": "Findings", "paragraphs": ["A finding."], "tables": []}],
                "diagrams": [],
            }
            report = publication_audit.reconcile(reqs, empty_draft)
            assert [item["status"] for item in report] == ["missing", "needs_review"]
            assert all(item["text"] for item in report)
            table_draft = {
                "sections": [
                    {
                        "heading": "Findings",
                        "paragraphs": [],
                        "tables": [{"caption": "Counterexamples to the proposed claim"}],
                    }
                ],
                "diagrams": [],
            }
            assert publication_audit.reconcile(reqs, table_draft)[0]["status"] == "needs_review"
            long_req = "Consider potential failures.\n" + ("X" * 12000)
            assert len(publication_audit.reconcile(long_req, empty_draft)[1]["text"]) == 12000
            paragraph = (
                "This derivation establishes a specific intermediate relation "
                "while preserving the counterexample boundary and avoiding claims of unearned certainty. "
            ) * 5
            repeated = {
                "sections": [
                    {"heading": "One", "paragraphs": [paragraph]},
                    {"heading": "Two", "paragraphs": [paragraph]},
                ]
            }
            assert publication_audit.overlap_warnings(repeated)
            assert not publication_audit.overlap_warnings(
                {"sections": [{"heading": "One", "paragraphs": [paragraph]}]}
            )

            # Resume keeps the saved model and thinking level by default and
            # refuses an unapproved change to the billing account.
            fake_fingerprint = "a" * 64
            checkpoint = {
                "model": "gpt-6.1-sol",
                "reasoning_effort": "high",
                "binding_fingerprint": fake_fingerprint,
            }
            assert papers._resume_provider_choice(
                checkpoint, fake_fingerprint, "other-model", "low"
            ) == ("gpt-6.1-sol", "high")
            try:
                papers._resume_provider_choice(checkpoint, "b" * 64, "other-model", "low")
            except ProjectError as exc:
                assert "explicit approval" in str(exc)
            else:
                raise AssertionError("Provider change must require approval")
            assert papers._resume_provider_choice(
                checkpoint, "b" * 64, "other-model", "low", True
            ) == ("other-model", "low")

            research_ethos.save_override("Different principles for the NEXT run.")
            old = research_sessions._role_request_payload(
                record, "investigator", {"investigation_type": "mathematical"}
            )
            assert override in old["instructions"]  # Frozen, not a live lookup.
            assert "NEXT run" not in old["instructions"]

            project = initialize_project(
                projects / "ethos-test.sigma",
                "Discovery example",
                "Can the observed pattern be explained?",
                desired_outcomes="Find a discriminating explanation.",
                paper_requirements="Include a counterexample table.",
            ).project
            assert project.schema_version == 13
            assert project.desired_outcomes and project.paper_requirements
            saved_project = json.loads(_document(project))
            assert "research_ethos" not in saved_project
            assert "ai_model" not in saved_project
            assert "reasoning_effort" not in saved_project
            assert "desired_outcomes" in saved_project
            assert "paper_requirements" in saved_project
            assert _decode(saved_project) == inspect_project(projects / "ethos-test.sigma").project

            old_project = dict(saved_project)
            old_project["schema_version"] = 12
            old_project.pop("desired_outcomes")
            old_project.pop("paper_requirements")
            legacy = _decode(old_project)
            assert legacy.problem == project.problem
            assert legacy.desired_outcomes == legacy.paper_requirements == ""
            assert legacy.events == project.events

            bundle = project_bundle.portable_bundle({"project.json": _document(project)})
            renamed = project_bundle.rename_bundle_project(bundle, "Renamed project")
            renamed_project = _decode(project_bundle.bundle_project_document(renamed))
            assert renamed_project.title == "Renamed project"
            assert renamed_project.desired_outcomes == project.desired_outcomes
            assert renamed_project.paper_requirements == project.paper_requirements
            assert renamed_project.events[:-1] == project.events
            assert renamed_project.events[-1].project_change is not None
            assert asdict(project_settings(renamed_project)) == asdict(
                renamed_project.events[-1].project_change.current
            )
            with patch.object(project_types, "_store_path", return_value=bob / "types.json"):
                assert research_ethos.current() == defaults
                research_ethos.save_override("Independent user ethos")
                assert research_ethos.current()["markdown"] == "Independent user ethos"
            assert research_ethos.current()["markdown"] == "Different principles for the NEXT run."
            # Explicit invalid-data recovery archives rather than destroys
            # the invalid override and refuses valid or unsafe files.
            old_bytes = target.read_bytes()
            target.write_text('{"version": 1, "markdown": ""}', encoding="utf-8")
            with TestClient(app) as client:
                assert client.get("/api/user-preferences/research-ethos").status_code == 400
                result = client.post("/api/user-preferences/research-ethos/recover")
                assert result.status_code == 200, result.text
                assert result.json() == defaults
            archived = list(alice.glob(".sigma-research-ethos.invalid-*.json"))
            assert len(archived) == 1
            assert archived[0].read_text() == '{"version": 1, "markdown": ""}'
            target.write_bytes(old_bytes)
            try:
                research_ethos.quarantine_invalid_override()
            except ProjectError as exc:
                assert "valid" in str(exc)
            else:
                raise AssertionError("Valid Ethos must not be quarantined")
            assert research_ethos.save_override(None) == defaults

        print("PASS user-scoped Research Ethos API, frozen I/S prompts, v12 reads, v13 bundles")


if __name__ == "__main__":
    main()
