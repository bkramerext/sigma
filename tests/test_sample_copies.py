"""Sample examples are templates; opening them creates independent recent projects."""

import hashlib
import json
import tempfile
import unittest
from dataclasses import asdict
from datetime import UTC, datetime
from pathlib import Path
from unittest.mock import patch
from uuid import uuid4

from sigma import paper_scores, papers, projects, recents, samples
from sigma.projects import (
    STATE,
    ProjectError,
    create_project,
    initialize_project,
    inspect_project,
    project_destination,
    project_settings,
    update_project,
)


class SampleCopyTests(unittest.TestCase):
    def setUp(self):
        self.temporary = tempfile.TemporaryDirectory()
        self.addCleanup(self.temporary.cleanup)
        base = Path(self.temporary.name)
        self.samples = base / "samples"
        self.projects = base / "projects"
        self.state = base / "state"
        for directory in (self.samples, self.projects, self.state):
            directory.mkdir(mode=0o700)
        self.sample = self.samples / "sample"
        self.sample.mkdir()
        self.template_id = str(uuid4())
        self.template = {
            "schema_version": 1,
            "id": self.template_id,
            "title": "Sample Investigation",
            "problem": "Explore an example question",
            "events": [
                {
                    "sequence": 1,
                    "kind": "project.initialized",
                    "timestamp": datetime.now(UTC).isoformat(),
                }
            ],
        }
        (self.sample / STATE).write_text(json.dumps(self.template), encoding="utf-8")
        for target, attribute, value in (
            (samples, "SAMPLES", self.samples),
            (samples, "projects_root", lambda: self.projects),
            (projects, "projects_root", lambda: self.projects),
            (recents, "state_directory", lambda: self.state),
        ):
            patcher = patch.object(target, attribute, value)
            patcher.start()
            self.addCleanup(patcher.stop)

    def test_crucible_literature_sample_is_editable_and_methodologically_distinct(self):
        """Shipped literary template has three independent research methods and citation criteria."""
        catalog_root = Path(__file__).resolve().parents[1] / "samples"
        with patch.object(samples, "SAMPLES", catalog_root):
            sample = next(
                item
                for item in samples.sample_projects()["projects"]
                if item["id"] == "the-crucible"
            )
            self.assertEqual(sample["investigation_type"], "literature")
            self.assertEqual(sample["difficulty"], "medium")
            self.assertEqual(sample["strategy_count"], 3)
            copied = samples.open_sample_project("the-crucible")

        project = inspect_project(copied.path).project
        self.assertNotEqual(project.id, "7fa05c30-1b7c-4df3-9d0c-8d95187a2200")
        self.assertEqual(project.investigation_type, "literature")
        self.assertIsNotNone(project.difficulty)
        assert project.difficulty is not None
        self.assertEqual(project.difficulty.value, "medium")
        self.assertEqual(len(project.active_order), 3)
        self.assertEqual(len(set(project.active_order)), 3)
        methods = [strategy.title.casefold() for strategy in project.strategies]
        self.assertTrue(any("formalist" in title for title in methods))
        self.assertTrue(any("historical" in title for title in methods))
        self.assertTrue(any("reception" in title for title in methods))
        self.assertIn("How does Arthur Miller's The Crucible", project.problem)
        self.assertIn("published literary criticism", project.paper_requirements)
        self.assertIn("bibliography", project.paper_requirements)
        self.assertIn("Run three separate strategies", project.desired_outcomes)
        self.assertIn("non-overlapping primary methods", project.desired_outcomes)
        self.assertEqual(
            project.events[-1].sequence,
            len(json.loads((catalog_root / "the-crucible" / "project.json").read_text())["events"])
            + 1,
        )
        self.assertEqual(project.events[-1].kind, "project.updated")

    def test_medical_cochlear_microphone_sample_is_grounded_and_editable(self):
        """Clinical sample ships literature, anatomical alternatives and safe comparisons."""
        catalog_root = Path(__file__).resolve().parents[1] / "samples"
        with patch.object(samples, "SAMPLES", catalog_root):
            sample = next(
                item
                for item in samples.sample_projects()["projects"]
                if item["id"] == "fully-implantable-cochlear-microphone-placement"
            )
            self.assertEqual(sample["investigation_type"], "medical")
            self.assertEqual(sample["difficulty"], "hard")
            self.assertEqual(sample["strategy_count"], 3)
            copied = samples.open_sample_project(
                "fully-implantable-cochlear-microphone-placement"
            )

        project = inspect_project(copied.path).project
        self.assertEqual(project.investigation_type, "medical")
        self.assertNotEqual(project.id, "16cce18f-9cdb-44bb-9ca0-7e787d79a016")
        self.assertEqual(len(project.active_order), 3)
        self.assertEqual(len(project.source_material_links), 6)
        self.assertIn("middle ear", project.problem.lower())
        self.assertIn("chest/torso", project.problem)
        self.assertIn("PRISMA", project.paper_requirements)
        self.assertIn("ICMJE", project.paper_requirements)
        self.assertIn("safety", project.desired_outcomes.lower())
        self.assertTrue(all(item["enabled"] for item in project.source_material_links))

    def test_opening_twice_creates_two_independent_recent_copies(self):
        first = samples.open_sample_project("sample")
        second = samples.open_sample_project("sample")

        self.assertEqual(Path(first.path).name, "sample.sigma")
        self.assertEqual(Path(second.path).name, "sample-2.sigma")
        self.assertNotEqual(first.project.id, second.project.id)
        self.assertNotIn(self.template_id, {first.project.id, second.project.id})
        self.assertEqual(first.project.title, "Sample Investigation v1")
        self.assertEqual(second.project.title, "Sample Investigation v2")
        self.assertEqual(second.project.events, first.project.events)
        self.assertEqual(inspect_project(first.path).project.id, first.project.id)
        self.assertEqual(json.loads((self.sample / STATE).read_text()), self.template)

        recent = recents.home_projects()["projects"]
        self.assertEqual([item["id"] for item in recent], [second.project.id, first.project.id])
        self.assertEqual([item["path"] for item in recent], [second.path, first.path])
        self.assertTrue(all(item["available"] for item in recent))
        self.assertIsNone(first.project.difficulty)

    def test_easy_sample_difficulty_survives_sample_copy(self):
        source = self.projects / "sample-source.sigma"
        initialize_project(source, "Easy Sample", "A representative easy question")
        raw = json.loads((source / STATE).read_bytes())
        raw["difficulty"] = "easy"
        easy_sample = self.samples / "easy"
        easy_sample.mkdir()
        (easy_sample / STATE).write_text(json.dumps(raw), encoding="utf-8")

        copied = samples.open_sample_project("easy")

        assert copied.project.difficulty is not None
        self.assertEqual(copied.project.difficulty.value, "easy")
        reopened = inspect_project(copied.path).project
        assert reopened.difficulty is not None
        self.assertEqual(reopened.difficulty.value, "easy")
        catalog = {item["id"]: item for item in samples.sample_projects()["projects"]}
        self.assertEqual(catalog["easy"]["difficulty"], "easy")
        self.assertEqual(json.loads((easy_sample / STATE).read_bytes())["difficulty"], "easy")

    def test_existing_sample_install_is_preserved(self):
        existing = self.projects / "sample.sigma"
        existing.mkdir()
        (existing / STATE).write_text(json.dumps(self.template), encoding="utf-8")

        copy = samples.open_sample_project("sample")
        self.assertEqual(Path(copy.path).name, "sample-2.sigma")
        self.assertEqual(copy.project.title, "Sample Investigation v1")
        self.assertEqual(inspect_project(existing).project.id, self.template_id)
        self.assertEqual(recents.home_projects()["projects"][0]["id"], copy.project.id)

    def rename(self, view, title):
        settings = project_settings(view.project)
        return update_project(
            view.path,
            title,
            settings.problem,
            settings.investigation_type,
            settings.ai_model,
            settings.reasoning_effort,
            asdict(settings),
        )

    def test_rename_rejects_sample_and_recent_titles(self):
        first = samples.open_sample_project("sample")
        second = samples.open_sample_project("sample")
        for taken in (
            "Sample Investigation",
            "sample investigation",
            second.project.title,
            second.project.title.upper(),
        ):
            with self.subTest(taken=taken), self.assertRaisesRegex(ProjectError, "already uses"):
                self.rename(first, taken)
            self.assertEqual(inspect_project(first.path).project.title, first.project.title)

        renamed = self.rename(first, "Independent investigation")
        self.assertEqual(renamed.project.title, "Independent investigation")

    def test_recent_project_outside_root_blocks_rename(self):
        outside = Path(self.temporary.name) / "external.sigma"
        external = initialize_project(outside, "External work", "Research question")
        recents.record_access(external)
        copy = samples.open_sample_project("sample")
        with self.assertRaisesRegex(ProjectError, "already uses"):
            self.rename(copy, "external work")

    def test_new_project_rejects_sample_and_existing_titles(self):
        self.assertTrue(project_destination("sample investigation").exists)
        with self.assertRaisesRegex(ProjectError, "already uses"):
            create_project("Sample Investigation", "New problem")
        first = samples.open_sample_project("sample")
        self.assertTrue(project_destination(first.project.title).exists)
        with self.assertRaisesRegex(ProjectError, "already uses"):
            create_project(first.project.title, "New problem")

    def test_copy_suffix_checks_existing_recent_title(self):
        outside = Path(self.temporary.name) / "external.sigma"
        external = initialize_project(outside, "Sample Investigation (copy)", "Research question")
        recents.record_access(external)
        copied = samples.open_sample_project("sample")
        self.assertEqual(copied.project.title, "Sample Investigation v1")
        self.assertEqual(Path(copied.path).name, "sample.sigma")

    def test_copy_version_skips_existing_project_title(self):
        initialize_project(
            self.projects / "existing.sigma", "Sample Investigation v1", "Research question"
        )
        copied = samples.open_sample_project("sample")
        self.assertEqual(copied.project.title, "Sample Investigation v2")

    def test_scored_sample_star_selects_original_best_pdf_and_copy_retains_score(self):
        """The public top-paper selection uses the same strict score validator as Saved Projects."""
        paper_dir = self.sample / "sample-papers"
        paper_dir.mkdir()
        fixture = Path(__file__).resolve().parent / "fixtures/sigma-valid-sample-paper.pdf"
        other = Path(__file__).resolve().parents[1] / "papers/maximum-regions.pdf"
        low_pdf = fixture.read_bytes()
        high_pdf = other.read_bytes()
        ids = ("a" * 32, "b" * 32, "c" * 32, "d" * 32)
        for paper_id, pdf, earned, valid in (
            (ids[0], low_pdf, 49, True),
            (ids[1], low_pdf, 62, True),
            (ids[2], high_pdf, 83, True),
            (ids[3], high_pdf, 99, False),
        ):
            sha = hashlib.sha256(pdf).hexdigest()
            judgment = paper_scores.PaperJudgment.model_validate(
                {
                    key: {"earned": earned, "explanation": "Synthetic acceptance fixture."}
                    for key in paper_scores.WEIGHTS
                }
            )
            score = paper_scores._make_score(judgment, sha)
            if not valid:
                score["rubric_version"] += 1
            record = {
                "paper_id": paper_id,
                "project_id": "$SIGMA_SAMPLE_PROJECT_ID",
                "tex_source": "% Fixture TeX source\\n\\\\documentclass{article}",
                "pdf_sha256": sha,
                "pdf_size_bytes": len(pdf),
                "score": score,
                "research_session_id": None,
            }
            (paper_dir / f"{paper_id}.json").write_text(json.dumps(record), encoding="utf-8")
            (paper_dir / f"{paper_id}.pdf").write_bytes(pdf)

        catalog = samples.sample_projects()["projects"]
        self.assertEqual(catalog[0]["best_paper_score"], 83)
        self.assertEqual(samples.top_sample_pdf("sample"), high_pdf)
        copy = samples.open_sample_project("sample")
        copied_score = papers.get_paper(copy.path, ids[2])["score"]
        self.assertEqual(
            paper_scores.validate_score(copied_score, hashlib.sha256(high_pdf).hexdigest()),
            copied_score,
        )
        self.assertEqual(papers.get_pdf(copy.path, ids[2]), high_pdf)
        self.assertEqual(samples.top_sample_pdf("sample"), high_pdf)

        for paper_id in ids[1:]:
            (paper_dir / f"{paper_id}.json").unlink()
            (paper_dir / f"{paper_id}.pdf").unlink()
        self.assertEqual(samples.sample_projects()["projects"][0]["best_paper_score"], 49)
        with self.assertRaisesRegex(ProjectError, "no top-scoring paper"):
            samples.top_sample_pdf("sample")

    def test_sample_catalog_does_not_change_after_copy(self):
        before = samples.sample_projects()
        samples.open_sample_project("sample")
        self.assertEqual(samples.sample_projects(), before)


if __name__ == "__main__":
    unittest.main()
