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

from sigma import project_evidence, project_transfer, research_supplied_evidence
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
            compiled_pdf = research_supplied_evidence.compile_entry(
                str(origin),
                {
                    "id": "uploaded-pdf:" + attached["id"],
                    "sha256": attached["sha256"],
                    "filename": attached["filename"],
                },
                "11111111-1111-4111-8111-111111111111",
            )
        with patch.object(
            research_supplied_evidence,
            "_fetch_url",
            return_value=(b"Linked premise B", "text/plain", link["url"]),
        ):
            compiled = research_supplied_evidence.compile_entry(
                str(origin),
                {"id": "uploaded-link:" + link["id"], "url": link["url"]},
                "11111111-1111-4111-8111-111111111111",
            )
        assert compiled["status"] == "retrieved"
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
        assert members[compiled_pdf["snapshot_path"]] == pdf
        assert members[compiled["snapshot_path"] + ".bin"] == b"Linked premise B"
        assert members["artifacts/generated_papers/example.tex"] == b"Generated paper TeX"
        new = root / "imported.sigma"
        project_transfer.import_project(payload, new)
        assert new.is_dir()
        assert inspect_project(new).project.id != inspect_project(origin).project.id
        assert (
            new / "artifacts" / "generated_papers" / "example.tex"
        ).read_text() == "Generated paper TeX"
        assert project_evidence.get_pdf(str(new), attached["id"])[1] == pdf
        assert (new / compiled_pdf["snapshot_path"]).read_bytes() == pdf
        assert (new / (compiled["snapshot_path"] + ".bin")).read_bytes() == b"Linked premise B"
        restored_sources = project_evidence.list_evidence(str(new))
        assert [row["kind"] for row in restored_sources] == ["file", "link"]
        assert restored_sources[0]["id"] == attached["id"]
        assert restored_sources[0]["filename"] == attached["filename"]
        assert restored_sources[1]["id"] == link["id"]
        assert restored_sources[1]["url"] == link["url"]
        _expect_failure(lambda: project_transfer.decode_bundle({**payload, "version": 3}))


def test_multiframe_artifact_archive_is_lossless_and_bounded() -> None:
    # Use tiny frames so the test exercises the >256 MiB TAR code path
    # without allocating a large fixture. All actual member size limits stay
    # enforced by the production codec.
    artifacts = {
        "artifacts/source_material/a.txt": bytes(range(256)) * 128,
        "artifacts/generated_papers/b.tex": b"sample paper" * 2700,
    }
    with patch.object(project_transfer, "MAX_ARCHIVE_FRAME_BYTES", 2048):
        encoded = project_transfer._archive(artifacts)
        assert encoded["uncompressed_size"] > 2048
        assert project_transfer._unarchive(encoded) == artifacts

        packed = base64.b64decode(encoded["data"])
        extra = {
            **encoded,
            "data": base64.b64encode(packed + compress(b"surprise")).decode("ascii"),
        }
        _expect_failure(lambda: project_transfer._unarchive(extra))
        missing_final_frame = {
            **encoded,
            "data": base64.b64encode(packed[:-20]).decode("ascii"),
        }
        _expect_failure(lambda: project_transfer._unarchive(missing_final_frame))


def test_total_size_includes_metadata_and_artifacts() -> None:
    members = {
        "project.json": b'{"schema_version": 13}',
        "notes.txt": b"x" * 8192,
        "artifacts/source_material/premise.txt": b"y" * 4096,
    }
    bundle = project_transfer.make_bundle(members)
    # Each section fits below the limit; their combined size does not.
    with patch.object(project_transfer, "MAX_BUNDLE_BYTES", 11000):
        _expect_failure(lambda: project_transfer.make_bundle(members))
        _expect_failure(lambda: project_transfer.decode_bundle(bundle))


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
    test_multiframe_artifact_archive_is_lossless_and_bounded()
    test_total_size_includes_metadata_and_artifacts()
    test_rejects_traversal_in_archive()
    print("PASS v4 artifact archive, source links, restored files and unsafe path rejection.")
