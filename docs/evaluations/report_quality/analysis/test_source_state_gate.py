"""Offline tests for source-state extraction."""

import unittest

from source_state_gate import extract


class SourceStateTests(unittest.TestCase):
    def test_failed_last_skeptic_not_erased_by_ended_session(self):
        bundle = {
            "files": {
                "project.json": {"id": "p", "title": "Test"},
                "research-sessions/s.json": {
                    "id": "s",
                    "status": "ended",
                    "termination_reason_code": "provider_or_strategy_failure",
                    "terminal_reason": "Research is incomplete.",
                    "steps": [
                        {"id": "t1", "call_number": 1, "status": "completed"},
                        {
                            "id": "t2",
                            "call_number": 2,
                            "status": "failed",
                            "role": "skeptic",
                            "failure_kind": "provider_error",
                            "provider_input_audit": {
                                "status": "call_failed_dispatch_unknown",
                                "request_body_compressed": "SECRET",
                            },
                        },
                    ],
                    "artifacts": [
                        {
                            "id": "a",
                            "skeptic_output": {
                                "verification_status": "convincing_unverified",
                                "objective_status": "partial",
                            },
                        }
                    ],
                },
            }
        }
        result = extract(bundle)
        self.assertEqual(result["sessions"][0]["failed_or_incomplete_steps"][0]["call_number"], 2)
        self.assertEqual(
            result["sessions"][0]["artifact_verification"][0]["objective_status"], "partial"
        )
        self.assertNotIn("SECRET", str(result))
        self.assertEqual(result["sessions"][0]["status"], "ended")


if __name__ == "__main__":
    unittest.main()
