"""Single checkpoint authority for explicit, bounded paper recovery."""

from __future__ import annotations

from unittest import TestCase

from sigma import papers
from sigma.projects import ProjectError


class VerifiedPaperRecoveryTests(TestCase):
    def setUp(self) -> None:
        self.work = {
            "kind": "long_form",
            "plan": {"sections": [{"heading": "A"}, {"heading": "B"}, {"heading": "C"}]},
            "section_dispatches": {"1": [{"attempt": 1}], "2": [{"attempt": 1}]},
            "section_drafts": {"3": {"heading": "C", "paragraphs": ["saved"]}},
        }

    def test_play_authorizes_exact_multiple_unsaved_sections(self) -> None:
        self.assertEqual(
            papers._verify_section_recovery(
                self.work, (1, 2), long_form=True, resumed_checkpoint=True
            ),
            (1, 2),
        )

    def test_single_section_and_no_recovery_remain_supported(self) -> None:
        work = {**self.work, "section_dispatches": {"1": [{"attempt": 1}]}}
        self.assertEqual(
            papers._verify_section_recovery(work, (1,), long_form=True, resumed_checkpoint=True),
            (1,),
        )
        self.assertIsNone(
            papers._verify_section_recovery(work, None, long_form=True, resumed_checkpoint=True)
        )

    def test_changed_dispatches_or_invalid_replay_are_rejected_before_provider(self) -> None:
        for requested in ((), (1,), (2,), (2, 1), (1, 1), (1, 4), (True, 2)):
            with self.subTest(requested=requested):
                with self.assertRaisesRegex(ProjectError, "checkpoint"):
                    papers._verify_section_recovery(
                        self.work, requested, long_form=True, resumed_checkpoint=True
                    )
        with self.assertRaisesRegex(ProjectError, "checkpoint"):
            papers._verify_section_recovery(
                self.work, (1, 2), long_form=True, resumed_checkpoint=False
            )
        with self.assertRaisesRegex(ProjectError, "checkpoint"):
            papers._verify_section_recovery(
                self.work, (1, 2), long_form=False, resumed_checkpoint=True
            )

    def test_all_unsaved_sections_can_resume_when_exact_dispatched(self) -> None:
        # Nothing saved yet is still recoverable if each attempted call has
        # an explicit durable receipt. Play is the actual authorization.
        work = {**self.work, "section_drafts": {}}
        self.assertEqual(
            papers._verify_section_recovery(work, (1, 2), long_form=True, resumed_checkpoint=True),
            (1, 2),
        )
