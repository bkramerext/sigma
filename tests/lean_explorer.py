"""Deterministic Lean Explorer tests: real-source locators, dossier, AI stages."""

import hashlib
from pathlib import Path
from tempfile import TemporaryDirectory
from unittest.mock import AsyncMock, patch

from fastapi.testclient import TestClient

from sigma import lean_explorer
from sigma.api import app
from sigma.projects import ProjectError

LEAN = (
    b"import Mathlib\n\n"
    b"def RiemannZetaZerosOnLine : Prop :=\n"
    b"  forall s, True\n\n"
    b"def DirichletLZerosOnLine : Prop := True\n"
)
GUIDE = b"\\begin{document}\nOverview of proof.\n"
PDF = b"%PDF-1.7 fixture"
ANNOUNCEMENT = "[PDF page 1]\nAlpoge announcement"


def fake_retrieve(url: str) -> tuple[bytes, str, str]:
    if lean_explorer.MIRROR_SHA in url and url.endswith("/src/Statements.lean"):
        return LEAN, "text/plain", url
    if lean_explorer.GUIDE_SHA in url and url.endswith("/guide/proof-guide.tex"):
        return GUIDE, "text/plain", url
    if url == lean_explorer.ANNOUNCEMENT:
        return PDF, "application/pdf", url
    raise AssertionError(f"Unexpected or unpinned source URL: {url}")


def test_source_navigation() -> None:
    for invalid in (
        "../passwd",
        "src/../../secrets.lean",
        "src/a.txt",
        "https://example.com/x.lean",
        "src//abc.lean",
        "src/.env.lean",
    ):
        try:
            lean_explorer.formal_path(invalid)
        except ProjectError:
            pass
        else:
            raise AssertionError(f"Unsafe Lean path accepted: {invalid}")

    with patch("sigma.lean_explorer._retrieve", side_effect=fake_retrieve):
        preview = lean_explorer.read_source("formal", "src/Statements.lean")
        assert preview["text"] == LEAN.decode()
        assert preview["sha256"] == hashlib.sha256(LEAN).hexdigest()

        found = lean_explorer.declarations("src/Statements.lean")
        assert [item["name"] for item in found["declarations"]] == [
            "RiemannZetaZerosOnLine",
            "DirichletLZerosOnLine",
        ]
        assert found["index_type"].startswith("lexical")
        selected = lean_explorer.declaration(
            "src/Statements.lean", "RiemannZetaZerosOnLine"
        )
        assert selected["start_line"] == 3
        assert selected["complete"] is True
        assert "3: def RiemannZetaZerosOnLine" in selected["excerpt"]


def test_packet_provenance() -> None:
    with (
        patch("sigma.lean_explorer._retrieve", side_effect=fake_retrieve),
        patch(
            "sigma.lean_explorer.project_evidence._extract",
            return_value=(1, ANNOUNCEMENT, False),
        ),
    ):
        packet, sources, selected = lean_explorer.analysis_packet(
            "src/Statements.lean",
            "RiemannZetaZerosOnLine",
            include_guide=True,
            include_announcement=True,
        )
    assert selected["start_line"] == 3
    assert len(sources) == 3
    assert lean_explorer.MIRROR_SHA in packet
    assert lean_explorer.GUIDE_SHA in packet
    assert "Overview of proof" in packet
    assert "Alpoge announcement" in packet
    assert "have NOT been inspected" in packet
    assert all(source["sha256"] for source in sources)


def test_dossier_and_ai_flow() -> None:
    with TemporaryDirectory() as temp:
        with (
            patch("sigma.lean_explorer_dossiers.state_directory", return_value=Path(temp)),
            patch("sigma.lean_explorer._retrieve", side_effect=fake_retrieve),
            patch(
                "sigma.lean_explorer.project_evidence._extract",
                return_value=(1, ANNOUNCEMENT, False),
            ),
        ):
            client = TestClient(app)
            source = client.get(
                "/api/explorelean/declarations",
                params={"path": "src/Statements.lean"},
            )
            assert source.status_code == 200
            assert source.json()["total"] == 2

            created = client.post("/api/explorelean/dossiers")
            assert created.status_code == 201, created.text
            dossier_id = created.json()["id"]
            assert len(dossier_id) == 36

            saved_note = client.post(
                f"/api/explorelean/dossiers/{dossier_id}/notes",
                json={
                    "formal_path": "src/Statements.lean",
                    "declaration": "RiemannZetaZerosOnLine",
                    "text": "Explain quantifier scope in a future exposition.",
                },
            )
            assert saved_note.status_code == 201, saved_note.text
            assert saved_note.json()["source"]["start_line"] == 3
            assert saved_note.json()["interpretation_status"] == "unverified commentary"

            config = {
                "available": True,
                "models": [{"id": "gpt-6.1-sol", "efforts": ["medium"]}],
            }
            reply = AsyncMock(return_value="A sourced interpretation of the statement.")
            with (
                patch(
                    "sigma.api.chat.configuration",
                    new=AsyncMock(return_value=config),
                ),
                patch("sigma.api.chat.respond", new=reply),
            ):
                response = client.post(
                    "/api/explorelean/analyze",
                    json={
                        "formal_path": "src/Statements.lean",
                        "declaration": "RiemannZetaZerosOnLine",
                        "include_guide": True,
                        "include_announcement": True,
                        "model": "gpt-6.1-sol",
                        "reasoning_effort": "medium",
                        "objective": "Explain RH carefully",
                        "dossier_id": dossier_id,
                    },
                )
            assert response.status_code == 200, response.text
            assert '"stage": "source"' in response.text
            assert '"stage": "interpreting"' in response.text
            assert '"stage": "saving"' in response.text
            assert '"saved": true' in response.text

            kwargs = reply.call_args.kwargs
            assert "RiemannZetaZerosOnLine" in kwargs["repeated_text"]
            assert kwargs["instructions_override"] == lean_explorer.ANALYSIS_INSTRUCTIONS

            record = client.get(f"/api/explorelean/dossiers/{dossier_id}")
            assert record.status_code == 200
            assert len(record.json()["entries"]) == 2
            assert record.json()["entries"][1]["supplementary_sources"][0]["kind"] == "guide"

            markdown = client.get(
                f"/api/explorelean/dossiers/{dossier_id}/markdown"
            )
            assert markdown.status_code == 200
            assert "### Actual Lean source excerpt" in markdown.text
            assert "A sourced interpretation" in markdown.text
            assert "SHA256" in markdown.text

            wrong_pin = client.post(
                "/api/explorelean/dossiers/not-a-uuid/notes",
                json={
                    "formal_path": "src/Statements.lean",
                    "declaration": "RiemannZetaZerosOnLine",
                    "text": "Should fail",
                },
            )
            assert wrong_pin.status_code in {400, 422}


if __name__ == "__main__":
    test_source_navigation()
    test_packet_provenance()
    test_dossier_and_ai_flow()
    print("Lean Explorer source and dossier tests passed.")
