"""Fast Samples catalog regression tests."""

import json
import tempfile
import unittest
from pathlib import Path
from unittest.mock import patch
from uuid import uuid4

from sigma import samples
from sigma.projects import STATE


class SampleCatalogFastListingTests(unittest.TestCase):
    def test_list_does_not_decode_project_and_invalidates_on_change(self):
        with tempfile.TemporaryDirectory() as temp:
            root = Path(temp)
            directory = root / "example"
            directory.mkdir()
            path = directory / STATE
            project = {
                "id": str(uuid4()),
                "title": "Original title",
                "problem": "Question",
                "investigation_type": "computer_science",
                "difficulty": "hard",
                "active_order": ["a", "b"],
                "events": [{"kind": "unused"}] * 100,
            }
            path.write_text(json.dumps(project), encoding="utf-8")
            with patch.object(samples, "SAMPLES", root), patch.object(
                samples, "_decode", side_effect=AssertionError("catalog decoded a project")
            ):
                first = samples.sample_projects()["projects"]
                self.assertEqual(first[0]["title"], "Original title")
                self.assertEqual(first[0]["strategy_count"], 2)
                self.assertEqual(samples.sample_projects()["projects"], first)

                project["title"] = "Updated longer title"
                path.write_text(json.dumps(project), encoding="utf-8")
                second = samples.sample_projects()["projects"]
                self.assertEqual(second[0]["title"], "Updated longer title")


if __name__ == "__main__":
    unittest.main()
