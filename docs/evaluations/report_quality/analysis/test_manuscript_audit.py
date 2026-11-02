"""Deterministic offline unit tests for manuscript_audit.py (no provider calls)."""

from __future__ import annotations

import hashlib
import importlib.util
import json
import tempfile
import unittest
from pathlib import Path

MODULE = Path(__file__).with_name("manuscript_audit.py")
SPEC = importlib.util.spec_from_file_location("manuscript_audit", MODULE)
assert SPEC is not None and SPEC.loader is not None
AUDIT = importlib.util.module_from_spec(SPEC)
SPEC.loader.exec_module(AUDIT)


class ManuscriptAuditTests(unittest.TestCase):
    def setUp(self) -> None:
        self.tmp = tempfile.TemporaryDirectory()
        self.addCleanup(self.tmp.cleanup)
        self.root = Path(self.tmp.name)
        self.txt = "Abstract\nA conditional result [C02].\n\nClaim register\nC2 · established: Definition only.\n"
        self.metadata = {
            "project_id": "fixture-project",
            "paper_id": "fixture-paper",
            "hashes": {},
            "generation": {
                "evidence_fields_omitted": 42,
                "publication_status": "needs_review",
                "proofreading": {"status": "fallback", "unresolved_diagnostic_count": 1},
                "layout_warnings": ["test warning"],
            },
            "validation_warnings": [
                "C2 is labeled established, but cited saved evidence includes unverified material."
            ],
        }
        for ext, data in [
            ("txt", self.txt.encode()),
            ("tex", b"\\documentclass{article}"),
            ("pdf", b"%PDF-1.4 test fixture only"),
        ]:
            (self.root / ("sample." + ext)).write_bytes(data)
            self.metadata["hashes"][ext] = {
                "sha256": hashlib.sha256(data).hexdigest(),
                "bytes": len(data),
            }
        self.write_metadata()

    def write_metadata(self) -> None:
        (self.root / "sample.metadata.json").write_text(json.dumps(self.metadata))

    def test_valid_artifacts_and_normalized_claim_pointer(self) -> None:
        result = AUDIT.audit(self.root / "sample.metadata.json")
        self.assertEqual(result["objective_integrity_problems"], [])
        self.assertEqual(result["text_structure"]["claim_count"], 1)
        self.assertEqual(result["text_structure"]["unregistered_claim_pointers"], [])
        self.assertEqual(result["text_structure"]["claim_kinds"], {"established": 1})
        self.assertEqual(len(result["metadata_claim_provenance_warnings"]), 1)
        self.assertEqual(result["evidence_fields_omitted"], 42)
        self.assertEqual(result["publication_status"], "needs_review")

    def test_detects_missing_artifact(self) -> None:
        (self.root / "sample.pdf").unlink()
        result = AUDIT.audit(self.root / "sample.metadata.json")
        self.assertIn("pdf: missing", result["objective_integrity_problems"])

    def test_detects_corrupt_artifact(self) -> None:
        (self.root / "sample.tex").write_text("changed")
        result = AUDIT.audit(self.root / "sample.metadata.json")
        self.assertIn("tex: SHA-256 mismatch", result["objective_integrity_problems"])
        self.assertIn("tex: byte count mismatch", result["objective_integrity_problems"])

    def test_detects_unknown_claim_reference(self) -> None:
        (self.root / "sample.txt").write_text(self.txt.replace("[C02]", "[C99]"))
        result = AUDIT.audit(self.root / "sample.metadata.json")
        self.assertEqual(result["text_structure"]["unregistered_claim_pointers"], [99])


if __name__ == "__main__":
    unittest.main()
