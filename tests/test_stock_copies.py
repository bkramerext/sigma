"""Stock examples are templates; opening them creates independent recent projects."""

import json
import tempfile
import unittest
from datetime import UTC, datetime
from pathlib import Path
from unittest.mock import patch
from uuid import uuid4

from sigma import recents, stock
from sigma.projects import STATE, inspect_project


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
        self.assertEqual(first.project.title, self.template["title"])
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
        self.assertEqual(inspect_project(existing).project.id, self.template_id)
        self.assertEqual(recents.home_projects()["projects"][0]["id"], copy.project.id)

    def test_stock_catalog_does_not_change_after_copy(self):
        before = stock.stock_projects()
        stock.open_stock_project("sample")
        self.assertEqual(stock.stock_projects(), before)


if __name__ == "__main__":
    unittest.main()
