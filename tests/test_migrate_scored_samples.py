"""Offline score-selected sample migration tests (no provider or private storage)."""

from __future__ import annotations

import hashlib
import importlib
import json
import shutil
import sys
import tempfile
import unittest
from pathlib import Path
from unittest.mock import patch
from uuid import uuid4

from sigma import agentic_evidence, paper_scores, project_bundle, samples
from sigma.projects import initialize_project

# These are direct-script test runs; the project checkout need not be on sys.path.
sys.path.insert(0, str(Path(__file__).resolve().parents[1]))
migrate_scored_samples = importlib.import_module("scripts.migrate_scored_samples")


class ScoredSampleMigrationTests(unittest.TestCase):
    def setUp(self) -> None:
        self.temp = tempfile.TemporaryDirectory(prefix="sigma-scored-samples-")
        self.addCleanup(self.temp.cleanup)
        root = Path(self.temp.name)
        self.saved = root / "projects"
        self.saved.mkdir()
        self.catalog = root / "samples"
        self.catalog.mkdir()
        mocked = patch.object(samples, "SAMPLES", self.catalog)
        mocked.start()
        self.addCleanup(mocked.stop)
        self.pdf = (Path(__file__).parent / "fixtures/sigma-valid-sample-paper.pdf").read_bytes()
        self.tex = (Path(__file__).parent / "fixtures/sigma-valid-sample-paper.tex").read_text(
            encoding="utf-8"
        )

    def source(self, title: str, score: int, *, invalid: bool = False) -> Path:
        folder = self.saved / (title.lower().replace(" ", "-") + ".sigma")
        view = initialize_project(folder, title, "A test project with frozen research.")
        directory = folder / "papers"
        directory.mkdir()
        paper_id = uuid4().hex
        sha = hashlib.sha256(self.pdf).hexdigest()
        judgment = paper_scores.PaperJudgment.model_validate(
            {
                name: {
                    "earned": score,
                    "explanation": "Deterministic fixture, not a real evaluation.",
                }
                for name in paper_scores.WEIGHTS
            }
        )
        stored_score = paper_scores._make_score(judgment, sha)
        if invalid:
            stored_score["rubric_version"] += 1
        record = {
            "paper_id": paper_id,
            "project_id": view.project.id,
            "paper_version": 1,
            "draft": {"title": "Example Warp Drive Paper"},
            "tex_source": self.tex,
            "pdf_sha256": sha,
            "pdf_size_bytes": len(self.pdf),
            "score": stored_score,
        }
        (directory / f"{paper_id}.json").write_text(json.dumps(record), encoding="utf-8")
        (directory / f"{paper_id}.pdf").write_bytes(self.pdf)
        agentic_evidence.save(
            folder,
            {
                "schema_version": 1,
                "run_id": uuid4().hex,
                "project_id": view.project.id,
                "started_at": "2026-11-02T12:00:00+00:00",
                "finished_at": "2026-11-02T12:00:01+00:00",
                "status": "completed",
                "timeline": [{"type": "decision", "message": "Saved research finding."}],
                "steps": [{"output": {"title": "Saved research evidence"}}],
            },
        )
        return folder

    def test_selects_every_qualifying_version_and_preserves_source(self) -> None:
        first = self.source("Warp Drive Design v2", 58)
        second = self.source("Warp Drive Design v3", 71)
        self.source("Other Project v1", 49)
        before = {
            path.resolve(): {relative.name: relative.read_bytes() for relative in (path / "papers").iterdir()}
            for path in (first, second)
        }
        selected = [
            candidate
            for path in migrate_scored_samples.saved_projects([self.saved])
            if (candidate := migrate_scored_samples.qualifying_project(path))
        ]
        self.assertEqual(len(selected), 2)
        self.assertEqual({candidate.score for candidate in selected}, {58, 71})
        self.assertEqual(migrate_scored_samples.run([self.saved], apply=False), 0)
        self.assertFalse(list(self.catalog.iterdir()))
        self.assertEqual(migrate_scored_samples.run([self.saved], apply=True), 0)
        for candidate in selected:
            files = {
                relative.name: relative.read_bytes()
                for relative in (candidate.directory / "papers").iterdir()
            }
            self.assertEqual(files, before[candidate.directory])
            result = next(
                item
                for item in samples.sample_projects()["projects"]
                if item["id"] == candidate.sample_id
            )
            self.assertEqual(result["best_paper_score"], candidate.score)
            self.assertEqual(samples.top_sample_pdf(candidate.sample_id), self.pdf)
            papers = samples._sample_papers(candidate.sample_id)
            record, pdf = papers[candidate.paper_id]
            self.assertEqual(pdf, self.pdf)
            self.assertEqual(record["tex_source"], self.tex)
            self.assertEqual(record["score"]["total"], candidate.score)
            self.assertEqual(
                paper_scores.validate_score(record["score"], hashlib.sha256(pdf).hexdigest()),
                record["score"],
            )

    def test_hosted_single_file_bundle_preserves_scored_paper_and_evidence(self) -> None:
        original = self.source("Warp Drive Design Hosted", 76)
        workspace = self.saved / "private-workspace"
        workspace.mkdir()
        bundled = workspace / "warp-drive.json"
        members = project_bundle._decode(json.loads(project_bundle.encode(original)))
        for name in list(members):
            if name.startswith("agentic-runs/"):
                members[f"evidence/{name}"] = members.pop(name)
            elif name.startswith("papers/"):
                members[f"artifacts/{name}"] = members.pop(name)
        bundled.write_text(json.dumps(project_bundle.portable_bundle(members)), encoding="utf-8")
        before = bundled.read_bytes()
        selected = migrate_scored_samples.saved_projects([workspace])
        self.assertEqual(selected, [bundled.resolve()])
        candidate = migrate_scored_samples.qualifying_project(bundled)
        self.assertIsNotNone(candidate)
        assert candidate is not None
        self.assertEqual(candidate.score, 76)
        self.assertEqual(migrate_scored_samples.run([workspace], apply=True), 0)
        self.assertEqual(bundled.read_bytes(), before)
        self.assertEqual(samples.top_sample_pdf(candidate.sample_id), self.pdf)
        evidence = samples._sample_evidence(candidate.sample_id)
        self.assertTrue(evidence["agentic_runs"])
        self.assertEqual(
            samples._sample_papers(candidate.sample_id)[candidate.paper_id][0]["score"]["total"],
            76,
        )

    def test_portable_bundle_with_directory_papers_layout(self) -> None:
        original = self.source("Portable Papers Layout", 69)
        bundled = self.saved / "portable-papers.json"
        bundled.write_bytes(project_bundle.encode(original))
        candidate = migrate_scored_samples.qualifying_project(bundled)
        self.assertIsNotNone(candidate)
        assert candidate is not None
        self.assertEqual(candidate.score, 69)
        migrate_scored_samples.install(candidate)
        self.assertEqual(samples.top_sample_pdf(candidate.sample_id), self.pdf)

    def test_mixed_paper_paths_reject_duplicates(self) -> None:
        original = self.source("Mixed Layout", 85)
        members = project_bundle._decode(json.loads(project_bundle.encode(original)))
        paper_name = next(
            name for name in members if name.startswith("papers/") and name.endswith(".json")
        )
        members["artifacts/" + paper_name] = members[paper_name]
        bundled = self.saved / "mixed-layout.json"
        bundled.write_text(json.dumps(project_bundle.portable_bundle(members)), encoding="utf-8")
        with self.assertRaisesRegex(ValueError, "Duplicate paper artifact"):
            migrate_scored_samples.qualifying_project(bundled)

    def test_scored_paper_without_research_is_rejected(self) -> None:
        source = self.source("Paper Only", 80)
        shutil.rmtree(source / "agentic-runs")
        with self.assertRaisesRegex(ValueError, "no original research evidence"):
            migrate_scored_samples.qualifying_project(source)
        self.assertEqual(migrate_scored_samples.run([self.saved], apply=True), 1)
        self.assertFalse(list(self.catalog.iterdir()))

    def test_stale_pdf_score_never_qualifies(self) -> None:
        source = self.source("Warp Drive Design v2", 80, invalid=True)
        self.assertIsNone(migrate_scored_samples.qualifying_project(source))
        self.assertEqual(migrate_scored_samples.run([self.saved], apply=True), 1)
        self.assertFalse(list(self.catalog.iterdir()))

    def test_source_must_exist_and_not_be_a_symlink(self) -> None:
        with self.assertRaises(ValueError):
            migrate_scored_samples.saved_projects([self.saved / "missing"])


if __name__ == "__main__":
    unittest.main()
