"""V4 project interchange: directory runtime, one zstd artifact archive."""

from __future__ import annotations

import base64
import hashlib
import io
import json
import tarfile
from pathlib import Path
from tempfile import TemporaryDirectory
from unittest.mock import patch

from sigma import project_evidence, project_transfer
from sigma.project_bundle import BundleError
from sigma.projects import initialize_project, inspect_project
from sigma.zstd_codec import compress


def _expect_failure(call) -> None:
    try:
        call()
    except BundleError:
        return
    raise AssertionError("Unsafe or unsupported bundle was accepted")


def test_single_archive_roundtrip() -> None:
    with TemporaryDirectory() as temporary:
        root = Path(temporary)
        origin = root / "original.sigma"
        initialize_project(origin, "Original", "What follows from the premises?")
        link = project_evidence.add_link(str(origin), "https://example.org/report")
        pdf = b"%PDF-1.7 fake test source"
        with patch.object(
            project_evidence, "_extract", return_value=(2, "[PDF page 1]\nPremise A", False)
        ):
            attached = project_evidence.add_evidence(str(origin), "source.pdf", pdf)
        paper_dir = origin / "artifacts" / "generated_papers"
        paper_dir.mkdir(parents=True)
        (paper_dir / "example.tex").write_text("Generated paper TeX", encoding="utf-8")
        stored = project_transfer.export_project(origin)
        payload = json.loads(stored)
        assert payload["version"] == 4
        assert payload["artifacts"]["encoding"] == "tar+zstd+base64"
        assert set(payload) == {"format", "version", "files", "artifacts"}
        assert not any(key.startswith("artifacts/") for key in payload["files"])
        assert payload["files"]["project.json"]["source_material_links"][0]["id"] == link["id"]
        members = project_transfer.decode_bundle(payload)
        assert members[f"artifacts/source_material/{attached['id']}.pdf"] == pdf
        assert members["artifacts/generated_papers/example.tex"] == b"Generated paper TeX"
        new = root / "imported.sigma"
        project_transfer.import_project(payload, new)
        assert new.is_dir()
        assert inspect_project(new).project.id != inspect_project(origin).project.id
        assert (
            new / "artifacts" / "generated_papers" / "example.tex"
        ).read_text() == "Generated paper TeX"
        assert project_evidence.get_pdf(str(new), attached["id"])[1] == pdf
        assert any(row["url"] == link["url"] for row in project_evidence.list_evidence(str(new)))
        _expect_failure(lambda: project_transfer.decode_bundle({**payload, "version": 3}))


def test_rejects_traversal_in_archive() -> None:
    with TemporaryDirectory() as temporary:
        origin = Path(temporary) / "original.sigma"
        initialize_project(origin, "Original", "A research problem")
        payload = json.loads(project_transfer.export_project(origin))
        stream = io.BytesIO()
        with tarfile.open(fileobj=stream, mode="w") as archive:
            item = tarfile.TarInfo("artifacts/../../outside.txt")
            item.size = 4
            archive.addfile(item, io.BytesIO(b"evil"))
        raw = stream.getvalue()
        payload["artifacts"] = {
            "encoding": project_transfer.ARCHIVE_ENCODING,
            "uncompressed_size": len(raw),
            "sha256": hashlib.sha256(raw).hexdigest(),
            "data": base64.b64encode(compress(raw)).decode("ascii"),
        }
        _expect_failure(lambda: project_transfer.decode_bundle(payload))


if __name__ == "__main__":
    test_single_archive_roundtrip()
    test_rejects_traversal_in_archive()
    print("PASS v4 artifact archive, source links, restored files and unsafe path rejection.")
