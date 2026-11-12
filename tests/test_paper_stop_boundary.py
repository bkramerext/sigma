"""Provider-free regression coverage for the paper Stop phase boundary.

An accepted Stop can land while proofreading is handing control back to the
editorial pipeline. The next stage must not begin simply because an awaited
helper returned normally.
"""

from __future__ import annotations

import asyncio
import unittest

from sigma import papers


class PaperStopBoundaryTests(unittest.TestCase):
    def test_cancel_requested_prevents_next_phase_even_before_await(self) -> None:
        async def workflow() -> list[str]:
            phases = ["proofreading"]
            current = asyncio.current_task()
            assert current is not None
            current.cancel()
            # A synchronous helper or saved checkpoint can finish between the
            # Stop signal and asyncio's next cancellation-delivering await.
            with self.assertRaises(asyncio.CancelledError):
                papers._abort_stopping_generation()
            return phases

        self.assertEqual(asyncio.run(workflow()), ["proofreading"])

    def test_unrelated_task_still_can_start_next_phase(self) -> None:
        async def workflow() -> bool:
            papers._abort_stopping_generation()
            await asyncio.sleep(0)
            papers._abort_stopping_generation()
            return True

        self.assertTrue(asyncio.run(workflow()))

    def test_cancel_at_checkpoint_boundary_does_not_start_pdf(self) -> None:
        async def workflow() -> list[str]:
            phases = ["proofreading"]
            started = asyncio.Event()
            gate = asyncio.Event()

            async def paper_work() -> None:
                started.set()
                try:
                    await gate.wait()
                except asyncio.CancelledError:
                    # Simulate a library helper that suppresses cancellation
                    # after preserving its own durable checkpoint.
                    pass
                papers._abort_stopping_generation()
                phases.append("generate_pdf")

            task = asyncio.create_task(paper_work())
            await started.wait()
            task.cancel()
            await asyncio.gather(task, return_exceptions=True)
            return phases

        self.assertEqual(asyncio.run(workflow()), ["proofreading"])


if __name__ == "__main__":
    unittest.main()
