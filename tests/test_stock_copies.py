"""Stock examples are templates; opening them creates independent recent projects."""

import json
import tempfile
import unittest
from dataclasses import asdict
from datetime import UTC, datetime
from pathlib import Path
from unittest.mock import patch
from uuid import uuid4

from sigma import projects, recents, stock
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


class StockCopyTests(unittest.TestCase):
    def setUp(self):
        self.temporary = tempfile.TemporaryDirectory()
        self.addCleanup(self.temporary.cleanup)
        base = Path(self.temporary.name)
        self.examples = base / "examples"
        self.projects = base / "projects"
        self.state = base / "state"
        for directory in (self.examples, self.projects, self.state):
            directory.mkdir(mode=0o700)
        self.example = self.examples / "sample"
        self.example.mkdir()
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
        (self.example / STATE).write_text(json.dumps(self.template), encoding="utf-8")
        for target, attribute, value in (
            (stock, "EXAMPLES", self.examples),
            (stock, "projects_root", lambda: self.projects),
            (projects, "projects_root", lambda: self.projects),
            (recents, "state_directory", lambda: self.state),
        ):
            patcher = patch.object(target, attribute, value)
            patcher.start()
            self.addCleanup(patcher.stop)

    def test_opening_twice_creates_two_independent_recent_copies(self):
        first = stock.open_stock_project("sample")
        second = stock.open_stock_project("sample")

        self.assertEqual(Path(first.path).name, "sample.sigma")
        self.assertEqual(Path(second.path).name, "sample-2.sigma")
        self.assertNotEqual(first.project.id, second.project.id)
        self.assertNotIn(self.template_id, {first.project.id, second.project.id})
        self.assertEqual(first.project.title, "Sample Investigation (copy)")
        self.assertEqual(second.project.title, "Sample Investigation (copy 1)")
        self.assertEqual(second.project.events, first.project.events)
        self.assertEqual(inspect_project(first.path).project.id, first.project.id)
        self.assertEqual(json.loads((self.example / STATE).read_text()), self.template)

        recent = recents.home_projects()["projects"]
        self.assertEqual([item["id"] for item in recent], [second.project.id, first.project.id])
        self.assertEqual([item["path"] for item in recent], [second.path, first.path])
        self.assertTrue(all(item["available"] for item in recent))

    def test_existing_stock_install_is_preserved(self):
        existing = self.projects / "sample.sigma"
        existing.mkdir()
        (existing / STATE).write_text(json.dumps(self.template), encoding="utf-8")

        copy = stock.open_stock_project("sample")
        self.assertEqual(Path(copy.path).name, "sample-2.sigma")
        self.assertEqual(copy.project.title, "Sample Investigation (copy)")
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

    def test_rename_rejects_stock_and_recent_titles(self):
        first = stock.open_stock_project("sample")
        second = stock.open_stock_project("sample")
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
        copy = stock.open_stock_project("sample")
        with self.assertRaisesRegex(ProjectError, "already uses"):
            self.rename(copy, "external work")

    def test_new_project_rejects_stock_and_existing_titles(self):
        self.assertTrue(project_destination("sample investigation").exists)
        with self.assertRaisesRegex(ProjectError, "already uses"):
            create_project("Sample Investigation", "New problem")
        first = stock.open_stock_project("sample")
        self.assertTrue(project_destination(first.project.title).exists)
        with self.assertRaisesRegex(ProjectError, "already uses"):
            create_project(first.project.title, "New problem")

    def test_copy_suffix_checks_existing_recent_title(self):
        outside = Path(self.temporary.name) / "external.sigma"
        external = initialize_project(outside, "Sample Investigation (copy)", "Research question")
        recents.record_access(external)
        copied = stock.open_stock_project("sample")
        self.assertEqual(copied.project.title, "Sample Investigation (copy 1)")
        self.assertEqual(Path(copied.path).name, "sample.sigma")

    def test_stock_catalog_does_not_change_after_copy(self):
        before = stock.stock_projects()
        stock.open_stock_project("sample")
        self.assertEqual(stock.stock_projects(), before)


if __name__ == "__main__":
    unittest.main()
