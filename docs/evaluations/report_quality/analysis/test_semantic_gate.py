"""Offline tests for semantic_gate.py; fixtures are not research papers."""

from __future__ import annotations

import unittest

from semantic_gate import audit_text


class SemanticGateTests(unittest.TestCase):
    def test_operational_fallback_and_omission_discrepancy(self):
        text = (
            "Title\n\nAbstract\nA provisional note from "
            "investigator_output/reasoning_steps/0/argument.\n\n"
            "Problem framing\nSome background [C1].\n\nClaim register\n"
            "C1 · unresolved: title: Project title\n"
            "C2 · unresolved: events/4/project_change/previous/reasoning_effort: high\n"
            "C3 · limitation: A legitimate substantive caveat.\n\n"
            "Limitations\nUnverified.\n\nConclusions\nNothing was established.\n"
        )
        metadata = {
            "generation": {"evidence_fields_omitted": 32191},
            "validation_warnings": [
                "Evidence indexing omitted 32187 material saved research field fragment(s)."
            ],
        }
        result = audit_text(text, metadata)
        self.assertEqual(len(result["abstract_record_paths"]), 1)
        self.assertEqual([c["id"] for c in result["operational_claims"]], ["1", "2"])
        self.assertEqual(result["omission_counts_in_warnings"], [32187])
        self.assertEqual(len(result["review_flags"]), 4)

    def test_legitimate_scientific_claim_not_flagged(self):
        text = (
            "Title\n\nAbstract\nA bounded analytical claim.\n\n"
            "Problem framing\nThe question. [C3]\n\nClaim register\n"
            "C3 · established: Conditional mathematical deduction under assumptions.\n\n"
            "Limitations\nNo animal experiments.\n\nConclusions\n"
            + "A precise bounded conclusion. "
            * 10
        )
        result = audit_text(text, {"generation": {"evidence_fields_omitted": 0}})
        self.assertEqual(result["review_flags"], [])
        self.assertEqual(result["claim_mentions_in_body"]["3"], 1)

    def test_missing_sections_are_reviewable(self):
        result = audit_text("No sections", {})
        self.assertEqual(result["claim_count"], 0)
        self.assertEqual(result["conclusion_words"], 0)
        self.assertEqual(result["review_flags"], [])


if __name__ == "__main__":
    unittest.main()
