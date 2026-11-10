"""Project PDF evidence retention and paper provenance regression tests."""

from __future__ import annotations

import hashlib
from pathlib import Path
from tempfile import TemporaryDirectory
from types import SimpleNamespace
from unittest.mock import patch

from sigma import papers, project_evidence, research_sessions, research_supplied_evidence
from sigma.projects import ProjectError, initialize_project


def test_project_evidence_lifecycle() -> None:
    with TemporaryDirectory() as temporary:
        path = Path(temporary) / "evidence.sigma"
        initialize_project(path, "Evidence", "What does the document establish?")
        pdf = b"%PDF-1.7 fake fixture"
        with patch.object(
            project_evidence, "_extract", return_value=(2, "[PDF page 1]\nClaim A", False)
        ):
            entry = project_evidence.add_evidence(str(path), "draft.pdf", pdf)
            same = project_evidence.add_evidence(str(path), "duplicate.pdf", pdf)
        assert entry == same
        assert entry["sha256"] == hashlib.sha256(pdf).hexdigest()
        assert len(project_evidence.list_evidence(str(path))) == 1
        assert project_evidence.get_pdf(str(path), entry["id"])[1] == pdf
        context = project_evidence.evidence_context(str(path))
        assert context[0]["filename"] == "draft.pdf"
        assert context[0]["id"] == "uploaded-pdf:" + entry["id"]
        assert "PDF page 1" in context[0]["excerpt"]
        assert "unverified" in context[0]["provenance"]
        paper, _ = papers._snapshot(str(path))
        sources = [item for item in paper["sources"] if item["kind"] == "uploaded_pdf"]
        assert len(sources) == 1
        assert sources[0]["id"] == context[0]["id"]
        project_evidence.remove_evidence(str(path), entry["id"])
        assert project_evidence.list_evidence(str(path)) == []


def test_project_collaborator_can_remove_another_users_source_material() -> None:
    with TemporaryDirectory() as temporary:
        path = Path(temporary) / "shared-source.sigma"
        initialize_project(path, "Shared", "Test shared Source Material")
        with patch.object(
            project_evidence, "_extract", return_value=(1, "Document text", False)
        ):
            attachment = project_evidence.add_evidence(
                str(path), "other-owner.pdf", b"%PDF-1.7 fixture"
            )
        # The uploader is a different person; authorized collaborators can
        # remove entries from this project just as they can edit them.
        assert attachment["uploaded_by"] is None
        member = SimpleNamespace(email="collaborator@example.org", role="member")
        with patch("sigma.cloud_auth.current_principal", return_value=member):
            project_evidence.remove_evidence(str(path), attachment["id"])
        assert project_evidence.list_evidence(str(path)) == []


def test_source_material_removal_rejects_guest() -> None:
    with TemporaryDirectory() as temporary:
        path = Path(temporary) / "guest-source.sigma"
        initialize_project(path, "Guest", "Test read-only guest")
        with patch.object(
            project_evidence, "_extract", return_value=(1, "Document text", False)
        ):
            attachment = project_evidence.add_evidence(
                str(path), "attached.pdf", b"%PDF-1.7 fixture"
            )
        guest = SimpleNamespace(email="guest@example.org", role="guest")
        with patch("sigma.cloud_auth.current_principal", return_value=guest):
            try:
                project_evidence.remove_evidence(str(path), attachment["id"])
            except ProjectError:
                pass
            else:
                raise AssertionError("Guest removed Source Material")
        assert len(project_evidence.list_evidence(str(path))) == 1


def test_project_evidence_validation() -> None:
    with TemporaryDirectory() as temporary:
        path = Path(temporary) / "evidence.sigma"
        initialize_project(path, "Evidence", "PDF evidence")
        for name, data in (
            ("../outside.txt", b"%PDF-1.7 stub"),
            ("doc.pdf", b"not-a-pdf"),
            ("doc.pdf", b"%PDF-"),
        ):
            try:
                project_evidence.add_evidence(str(path), name, data)
            except ProjectError:
                pass
            else:
                raise AssertionError("Accepted invalid PDF evidence")
        with patch.object(project_evidence, "_extract", return_value=(1, "", False)):
            try:
                project_evidence.add_evidence(str(path), "blank.pdf", b"%PDF-1.7")
            except ProjectError:
                pass
            else:
                raise AssertionError("Accepted unreadable PDF evidence")


def test_compiled_evidence_is_never_silently_clipped() -> None:
    source = {"id": "uploaded-link:one", "excerpt": "A" * 60000}
    assert research_sessions._bounded_supplied_evidence([source]) == [source]
    try:
        research_sessions._bounded_supplied_evidence([source, {"id": "two", "excerpt": "B"}])
    except ValueError as exc:
        assert "60,000" in str(exc)
    else:
        raise AssertionError("Oversized source material was silently clipped")


def test_pdf_extraction_covers_every_page() -> None:
    class TextPage:
        def __init__(self, text: str) -> None:
            self.text = text

        def get_text_range(self) -> str:
            return self.text

        def close(self) -> None:
            pass

    class Page:
        def __init__(self, number: int) -> None:
            self.number = number

        def get_textpage(self) -> TextPage:
            return TextPage(f"Unique premise on page {self.number + 1}: " + "x" * 2000)

        def close(self) -> None:
            pass

    class Document:
        def __len__(self) -> int:
            return 50

        def __getitem__(self, number: int) -> Page:
            return Page(number)

        def close(self) -> None:
            pass

    with patch.object(project_evidence.pypdfium2, "PdfDocument", return_value=Document()):
        pages, text, incomplete = project_evidence._extract(b"%PDF-1.7 fixture")
    assert pages == 50 and not incomplete
    assert "Unique premise on page 1" in text
    assert "Unique premise on page 50" in text


def test_attachment_snapshot_survives_source_removal() -> None:
    with TemporaryDirectory() as temporary:
        path = Path(temporary) / "attached.sigma"
        initialize_project(path, "Attached", "Inspect the premise")
        pdf = b"%PDF-1.7 fixture source"
        with patch.object(
            project_evidence, "_extract", return_value=(1, "[PDF page 1]\nPremise A", False)
        ):
            attached = project_evidence.add_evidence(str(path), "source.pdf", pdf)
            compiled = research_supplied_evidence.compile_entry(
                str(path),
                {
                    "id": "uploaded-pdf:" + attached["id"],
                    "sha256": attached["sha256"],
                    "filename": attached["filename"],
                },
                "11111111-1111-4111-8111-111111111111",
            )
        assert compiled["status"] == "retrieved"
        project_evidence.remove_evidence(str(path), attached["id"])
        assert project_evidence._read(str(path), compiled["snapshot_path"]) == pdf


def test_link_snapshot_survives_resume() -> None:
    with TemporaryDirectory() as temporary:
        path = Path(temporary) / "linked.sigma"
        initialize_project(path, "Linked evidence", "Inspect the supplied claim")
        link = project_evidence.add_link(str(path), "https://example.org/evidence.txt")
        entry = {"id": "uploaded-link:" + link["id"], "url": link["url"]}
        session_id = "11111111-1111-4111-8111-111111111111"
        with patch.object(
            research_supplied_evidence,
            "_fetch_url",
            return_value=(b"Claim A is supplied.", "text/plain", link["url"]),
        ) as fetch:
            first = research_supplied_evidence.compile_entry(str(path), entry, session_id)
            second = research_supplied_evidence.compile_entry(str(path), entry, session_id)
        assert fetch.call_count == 1
        assert first["status"] == second["status"] == "retrieved"
        assert first["content_sha256"] == second["content_sha256"]
        assert first["excerpt"] == "Claim A is supplied."
        assert project_evidence._read(str(path), first["snapshot_path"] + ".bin") == (
            b"Claim A is supplied."
        )
        project_evidence.remove_evidence(str(path), link["id"])
        with patch(
            "sigma.api.export_project_view",
            return_value={
                "project": {
                    "id": "paper-project",
                    "investigation_type": "default",
                    "strategies": [],
                },
                "research_sessions": [
                    {
                        "id": session_id,
                        "created_at": "2026-01-01T00:00:00+00:00",
                        "supplied_evidence_compilation": {
                            "status": "completed",
                            "sources": [first],
                        },
                    }
                ],
            },
        ):
            package, _ = papers._snapshot(str(path))
        source = next(item for item in package["sources"] if item["id"] == entry["id"])
        assert source["data"]["excerpt"] == "Claim A is supplied."
        assert source["data"]["content_sha256"] == first["content_sha256"]


def test_unreadable_link_is_retried_without_caching_failure() -> None:
    with TemporaryDirectory() as temporary:
        path = Path(temporary) / "retry.sigma"
        initialize_project(path, "Retry", "Inspect the source")
        link = project_evidence.add_link(str(path), "https://example.org/retry.txt")
        entry = {"id": "uploaded-link:" + link["id"], "url": link["url"]}
        with patch.object(
            research_supplied_evidence,
            "_fetch_url",
            side_effect=[
                (b"", "text/plain", link["url"]),
                (b"Recovered premise", "text/plain", link["url"]),
            ],
        ) as fetch:
            first = research_supplied_evidence.compile_entry(
                str(path), entry, "11111111-1111-4111-8111-111111111111"
            )
            second = research_supplied_evidence.compile_entry(
                str(path), entry, "11111111-1111-4111-8111-111111111111"
            )
        assert first["status"] == "unavailable"
        assert second["status"] == "retrieved"
        assert fetch.call_count == 2


def test_link_rejects_invalid_utf8() -> None:
    result = research_supplied_evidence.read_link(
        "https://example.org/binary.txt",
        (b"\xff\xfe", "text/plain", "https://example.org/binary.txt"),
    )
    assert result["status"] == "unavailable"
    assert result["reason"]


def test_link_policy_allows_http_and_rejects_unsafe_targets() -> None:
    import socket

    from sigma import research_reference_content

    with TemporaryDirectory() as temporary:
        path = Path(temporary) / "urls.sigma"
        initialize_project(path, "URLs", "Validate linked sources")
        with patch("sigma.reference_titles.domain_status", return_value="valid"):
            link = project_evidence.add_link(str(path), "http://example.org/source.txt")
        assert link["url"] == "http://example.org/source.txt"
        assert link["enabled"] is True
        with patch("sigma.reference_titles.domain_status", return_value="invalid"):
            try:
                project_evidence.add_link(str(path), "https://nxdomain.invalid/source.txt")
            except ProjectError as exc:
                assert "Website could not be found" in str(exc)
            else:
                raise AssertionError("Accepted a definitively invalid Source Material host")

    try:
        research_reference_content._public_endpoint("http://example.org/source.txt")
    except ValueError:
        pass
    else:
        raise AssertionError("Research Standards' HTTPS-only endpoint was weakened")
    with patch(
        "sigma.research_reference_content.socket.getaddrinfo",
        return_value=[(socket.AF_INET, socket.SOCK_STREAM, 6, "", ("93.184.215.14", 80))],
    ):
        host, _, port, _, _ = research_reference_content._public_endpoint(
            "http://example.org/source.txt", allow_http=True
        )
    assert host == "example.org" and port == 80


def test_enable_disable_and_edit_applies_to_future_session_inputs() -> None:
    with TemporaryDirectory() as temporary:
        path = Path(temporary) / "source-toggles.sigma"
        initialize_project(path, "Source toggles", "Research only enabled premises")
        with patch("sigma.reference_titles.domain_status", return_value="valid"):
            link = project_evidence.add_link(str(path), "http://example.org/a.txt")
        with patch.object(
            project_evidence,
            "_extract",
            return_value=(1, "[PDF page 1] Premise", False),
        ):
            file = project_evidence.add_evidence(str(path), "source.pdf", b"%PDF-1.7 fixture")
        assert len(project_evidence.evidence_context(str(path))) == 2
        assert project_evidence.has_enabled_evidence(str(path))
        disabled_link = project_evidence.set_enabled(str(path), link["id"], False)
        disabled_file = project_evidence.set_enabled(str(path), file["id"], False)
        assert not disabled_link["enabled"] and not disabled_file["enabled"]
        assert not project_evidence.has_enabled_evidence(str(path))
        assert project_evidence.evidence_context(str(path)) == []
        assert not any(item["enabled"] for item in project_evidence.list_evidence(str(path)))
        with patch("sigma.reference_titles.domain_status", return_value="valid"):
            edited = project_evidence.edit_link(
                str(path), link["id"], "https://example.org/updated.txt"
            )
        assert edited["id"] == link["id"] and edited["enabled"] is False
        assert edited["url"] == "https://example.org/updated.txt"
        project_evidence.set_enabled(str(path), file["id"], True)
        context = project_evidence.evidence_context(str(path))
        assert len(context) == 1 and context[0]["filename"] == "source.pdf"
        project_evidence.set_enabled(str(path), link["id"], True)
        assert len(project_evidence.evidence_context(str(path))) == 2


if __name__ == "__main__":
    test_project_evidence_lifecycle()
    test_project_collaborator_can_remove_another_users_source_material()
    test_source_material_removal_rejects_guest()
    test_project_evidence_validation()
    test_compiled_evidence_is_never_silently_clipped()
    test_pdf_extraction_covers_every_page()
    test_attachment_snapshot_survives_source_removal()
    test_link_snapshot_survives_resume()
    test_unreadable_link_is_retried_without_caching_failure()
    test_link_rejects_invalid_utf8()
    test_link_policy_allows_http_and_rejects_unsafe_targets()
    test_enable_disable_and_edit_applies_to_future_session_inputs()
    print("Project evidence tests passed.")
