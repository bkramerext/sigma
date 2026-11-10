"""Project PDF evidence retention and paper provenance regression tests."""

from __future__ import annotations

import hashlib
from pathlib import Path
from tempfile import TemporaryDirectory
from unittest.mock import patch

from sigma import papers, project_evidence
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


if __name__ == "__main__":
    test_project_evidence_lifecycle()
    test_project_evidence_validation()
    print("Project evidence tests passed.")
