"""Provider-free regression coverage for admission numbering optimization."""

from __future__ import annotations

from unittest import TestCase, main
from unittest.mock import patch

from sigma import papers


class PaperAdmissionFastPathTests(TestCase):
    def test_reservation_does_not_read_the_ledger_twice(self) -> None:
        """The atomic run reservation will check the ledger under its own lock."""
        with (
            patch.object(papers, "_read_version_sequence", return_value=7),
            patch(
                "sigma.project_collaboration.list_execution_runs",
                side_effect=AssertionError("Redundant run-ledger read during admission"),
            ),
        ):
            self.assertEqual(
                papers.next_paper_number_for_activity("/not-needed", include_reserved=False),
                8,
            )

    def test_activity_display_still_accounts_for_reserved_numbers(self) -> None:
        """Non-admission callers must retain their original numbering semantics."""
        with (
            patch.object(papers, "_read_version_sequence", return_value=7),
            patch(
                "sigma.project_collaboration.list_execution_runs",
                return_value=[{"number": 10}, {"number": 12}],
            ) as runs,
        ):
            self.assertEqual(papers.next_paper_number_for_activity("/not-needed"), 13)
            runs.assert_called_once_with("/not-needed", "paper")

    def test_admission_passes_saved_max_to_atomic_reservation(self) -> None:
        """A saved monotonic sequence remains authoritative without run ledger reads."""
        with (
            patch.object(papers, "_read_version_sequence", return_value=19),
            patch(
                "sigma.project_collaboration.list_execution_runs",
                side_effect=AssertionError("Run ledger belongs to reservation transaction"),
            ),
        ):
            saved_max = (
                papers.next_paper_number_for_activity("/not-needed", include_reserved=False) - 1
            )
            self.assertEqual(saved_max, 19)


if __name__ == "__main__":
    main()
