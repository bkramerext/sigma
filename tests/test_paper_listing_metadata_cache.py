"""Paper-library reads are metadata-only, with no parallel stored index."""

from __future__ import annotations

import json
from pathlib import Path
from tempfile import TemporaryDirectory
from types import SimpleNamespace
from unittest import TestCase, main
from unittest.mock import patch

from sigma import papers


class PaperListingEndpointTests(TestCase):
    def test_metadata_only_endpoint_never_recovers_run_progress(self) -> None:
        from sigma import api

        with (
            patch.object(api.papers, "list_papers", return_value=[]) as listed,
            patch.object(api.papers, "next_paper_number_for_activity", return_value=11),
            patch.object(
                api.papers,
                "run_progress_list",
                side_effect=AssertionError("Paper listing must not load run checkpoints"),
            ) as recovered,
        ):
            result = api.papers_view("/unused", include_runs=False)
            self.assertEqual(result["papers"], [])
            self.assertEqual(result["runs"], [])
            self.assertEqual(result["next_paper_number"], 11)
            listed.assert_called_once_with("/unused")
            recovered.assert_not_called()


class PaperListingPerformanceTests(TestCase):
    def test_one_ten_and_fifty_papers_keep_pdf_opaque_and_reuse_canonical_metadata(self) -> None:
        original_read = Path.read_bytes
        reads: list[str] = []
        for count in (1, 10, 50):
            with self.subTest(count=count), TemporaryDirectory() as tmp:
                root = Path(tmp)
                files = []
                for number in range(count):
                    file = root / f"{number + 1:032x}.json"
                    file.write_text(
                        json.dumps(
                            {
                                "project_id": "project-1",
                                "paper_id": f"{number + 1:032x}",
                                "paper_version": number + 1,
                                "created_by": "researcher@example.test",
                                "created_at": f"2026-11-01T00:{number:02d}:00+00:00",
                                "draft": {"title": f"Paper {number}", "sections": ["x" * 80000]},
                                "snapshot_sha256": "b" * 64,
                                "validation_warnings": [],
                                "generation": {"model": "test", "reasoning_effort": "low"},
                                "pdf_sha256": "a" * 64,
                                "pdf_size_bytes": 1024,
                            }
                        ),
                        encoding="utf-8",
                    )
                    (root / f"{number + 1:032x}.pdf").write_bytes(b"%PDF-disabled-on-listing")
                    files.append(file)

                reads.clear()

                def observed_read(file: Path) -> bytes:
                    if file.suffix in {".pdf", ".tex"}:
                        raise AssertionError("Listing touched a PDF or TeX artifact")
                    reads.append(file.name)
                    return original_read(file)

                papers._cached_paper_listing_summary.cache_clear()
                view = SimpleNamespace(project=SimpleNamespace(id="project-1", title="Test"))
                with (
                    patch.object(papers, "project_path", return_value=root),
                    patch.object(papers, "_paper_dir", return_value=root),
                    patch.object(papers, "inspect_project", return_value=view),
                    patch.object(Path, "read_bytes", observed_read),
                ):
                    first = papers.list_papers(str(root))
                    self.assertEqual(len(first), count)
                    self.assertEqual(len(reads), count)
                    self.assertTrue(all(row["pdf_available"] for row in first))
                    self.assertTrue(all("draft" not in row for row in first))
                    self.assertTrue(all("download_basename" in row for row in first))

                    second = papers.list_papers(str(root))
                    self.assertEqual(first, second)
                    self.assertEqual(len(reads), count, "Unchanged records were re-parsed")

                    # Updating the sole canonical record invalidates only that
                    # record's transient summary. No persistent index is written.
                    updated = json.loads(files[0].read_text(encoding="utf-8"))
                    updated["draft"]["title"] = "Revised paper title"
                    files[0].write_text(json.dumps(updated), encoding="utf-8")
                    third = papers.list_papers(str(root))
                    self.assertEqual(len(reads), count + 1)
                    self.assertIn("Revised paper title", [row["title"] for row in third])
                    self.assertFalse(
                        any(file.name.endswith(".index.json") for file in root.iterdir())
                    )
                papers._cached_paper_listing_summary.cache_clear()


if __name__ == "__main__":
    main()
