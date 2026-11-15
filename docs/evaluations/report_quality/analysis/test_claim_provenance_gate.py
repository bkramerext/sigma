"""Offline provenance-locator gate tests."""

import unittest

from claim_provenance_gate import audit


class ProvenanceGateTests(unittest.TestCase):
    def test_coarse_and_fine_claims(self):
        tex = (
            r"\subsection{C1 -- Conjecture}"
            + "\n"
            + r"A conditional claim.\textit{Evidence: }[Research session 1]"
            + "\n"
            + r"\subsection{C2 -- Established}"
            + "\n"
            + r"A separate deduction.\textit{Evidence: }[Research session 1, artifact 3]"
            + "\n"
            + r"\section{Limitations}"
        )
        result = audit(tex)
        self.assertEqual(result["claim_count"], 2)
        self.assertEqual(result["coarse_only_claim_ids"], ["C1"])
        self.assertEqual(result["missing_claim_ids"], [])

    def test_missing_source_label(self):
        result = audit(r"\subsection{C7 -- Unresolved}" + "\n" + "No evidence locator.\n")
        self.assertEqual(result["missing_claim_ids"], ["C7"])


if __name__ == "__main__":
    unittest.main()
