"""Validate bundled sample descriptions use the three project-description fields."""

from __future__ import annotations

import json
import unittest
from pathlib import Path

SAMPLES = Path(__file__).resolve().parents[1] / "samples"


class SampleDescriptionFieldsTests(unittest.TestCase):
    def test_every_bundled_sample_has_all_three_nonempty_fields(self) -> None:
        paths = sorted(SAMPLES.glob("*/project.json"))
        self.assertGreaterEqual(len(paths), 21)
        for path in paths:
            with self.subTest(sample=path.parent.name):
                project = json.loads(path.read_text(encoding="utf-8"))
                for field in ("problem", "desired_outcomes", "paper_requirements"):
                    self.assertIsInstance(project.get(field), str)
                    self.assertTrue(project[field].strip(), f"{path}: missing {field}")

    def test_embedded_section_headers_are_in_their_respective_fields(self) -> None:
        expectations = {
            "the-crucible": (
                "Run three separate strategies",
                "Cite the primary literary text",
            ),
            "first-principles-catalysis": (
                "EXIT CRITERIA",
                "STARTING SOURCES",
            ),
            "xenopus-tail-regeneration": (
                "EXIT CRITERIA",
                "REFERENCES/STARTING DATA",
            ),
            "qubit-non-markovian-decoherence": (
                "ACCEPTANCE CRITERIA FOR A VALID RESEARCH OUTCOME",
                "QUANTITATIVE TEST",
            ),
        }
        for sample, (outcome_marker, paper_marker) in expectations.items():
            with self.subTest(sample=sample):
                project = json.loads(
                    (SAMPLES / sample / "project.json").read_text(encoding="utf-8")
                )
                self.assertNotIn(outcome_marker, project["problem"])
                self.assertNotIn(paper_marker, project["problem"])
                self.assertIn(outcome_marker, project["desired_outcomes"])
                self.assertIn(paper_marker, project["paper_requirements"])


if __name__ == "__main__":
    unittest.main()
