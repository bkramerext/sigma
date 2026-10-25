"""Offline adversarial checks for the Increment 22 shared hard-budget ledger."""

from __future__ import annotations

import unittest

from sigma.increment22_baseline import dispatch_turn, new_arm_budget
from sigma.research_budget import (
    BudgetExceeded,
    mark_unknown,
    new_ledger,
    reserve_before_dispatch,
    settle_after_response,
    totals,
)


def ledger(
    *, calls: int = 4, input_tokens: int = 200_000, output_tokens: int = 1024, cost: float = 0.55
):
    return new_ledger(
        call_limit=calls,
        input_token_limit=input_tokens,
        output_tokens_per_call=output_tokens,
        cost_limit_usd=cost,
        input_price_per_million=2.5,
        output_price_per_million=10.0,
    )


class Increment22BudgetTests(unittest.TestCase):
    def test_pre_dispatch_reserves_request_bytes_overhead_output_and_cost(self):
        budget = ledger()
        reservation = reserve_before_dispatch(budget, call_id="call-1", request_body=b"x" * 1000)
        self.assertEqual(reservation["input_token_bound"], 1000 + 8192)
        self.assertEqual(reservation["output_token_reservation"], 1024)
        self.assertEqual(reservation["cost_bound_usd"], (9192 * 2.5 + 1024 * 10) / 1_000_000)
        self.assertEqual(totals(budget)["input_tokens_used_or_reserved"], 9192)

    def test_settled_usage_releases_bound_and_keeps_cost_upper_bound(self):
        budget = ledger()
        reserve_before_dispatch(budget, call_id="call-1", request_body=b"x" * 1000)
        settle_after_response(budget, call_id="call-1", input_tokens=7000, output_tokens=500)
        self.assertEqual(totals(budget)["input_tokens_used_or_reserved"], 7000)
        self.assertEqual(totals(budget)["output_tokens_used_or_reserved"], 500)
        self.assertEqual(totals(budget)["cost_usd_used_or_reserved"], 0.0225)

    def test_input_cap_is_checked_before_any_dispatch(self):
        budget = ledger(input_tokens=9191)
        before = totals(budget)
        with self.assertRaisesRegex(BudgetExceeded, "input-token limit"):
            reserve_before_dispatch(budget, call_id="call-1", request_body=b"x" * 1000)
        self.assertEqual(totals(budget), before)
        self.assertEqual(budget["calls"], [])

    def test_cost_cap_is_checked_before_dispatch(self):
        budget = ledger(input_tokens=100_000, cost=0.01)
        before = totals(budget)
        with self.assertRaisesRegex(BudgetExceeded, "cost limit"):
            reserve_before_dispatch(budget, call_id="call-1", request_body=b"x" * 1000)
        self.assertEqual(totals(budget), before)

    def test_unknown_call_retains_full_reservation_and_blocks_retry(self):
        budget = ledger()
        reserve_before_dispatch(budget, call_id="call-1", request_body=b"x" * 1000)
        mark_unknown(budget, call_id="call-1")
        self.assertEqual(totals(budget)["input_tokens_used_or_reserved"], 9192)
        self.assertEqual(totals(budget)["output_tokens_used_or_reserved"], 1024)
        self.assertIsNotNone(totals(budget)["blocked_reason"])
        with self.assertRaisesRegex(BudgetExceeded, "blocked"):
            reserve_before_dispatch(budget, call_id="retry", request_body=b"x")

    def test_unsettled_inflight_call_blocks_a_second_dispatch(self):
        budget = ledger()
        reserve_before_dispatch(budget, call_id="call-1", request_body=b"x")
        with self.assertRaisesRegex(BudgetExceeded, "still in flight"):
            reserve_before_dispatch(budget, call_id="call-2", request_body=b"y")

    def test_usage_outside_reservation_blocks_future_calls_and_keeps_hold(self):
        budget = ledger()
        reserve_before_dispatch(budget, call_id="call-1", request_body=b"x")
        with self.assertRaisesRegex(BudgetExceeded, "exceeded"):
            settle_after_response(budget, call_id="call-1", input_tokens=9000, output_tokens=1)
        self.assertEqual(totals(budget)["input_tokens_used_or_reserved"], 8193)
        with self.assertRaises(BudgetExceeded):
            reserve_before_dispatch(budget, call_id="call-2", request_body=b"y")

    def test_call_and_output_ceilings_are_frozen(self):
        budget = ledger(calls=1, output_tokens=32)
        reserve_before_dispatch(budget, call_id="call-1", request_body=b"x")
        settle_after_response(budget, call_id="call-1", input_tokens=10, output_tokens=32)
        with self.assertRaisesRegex(BudgetExceeded, "call limit"):
            reserve_before_dispatch(budget, call_id="call-2", request_body=b"x")

    def test_trial_caps_have_cost_headroom_for_both_arms(self):
        per_arm = ledger()
        for index in range(4):
            reserve_before_dispatch(per_arm, call_id=f"call-{index}", request_body=b"x" * 41_808)
            settle_after_response(
                per_arm, call_id=f"call-{index}", input_tokens=50_000, output_tokens=1024
            )
        upper = totals(per_arm)["cost_usd_used_or_reserved"]
        self.assertEqual(upper, 0.54096)
        self.assertLessEqual(upper, 0.55)

    def test_baseline_adapter_uses_same_actual_pre_dispatch_guard(self):
        baseline = new_arm_budget()
        self.assertEqual(baseline["call_limit"], 4)
        self.assertEqual(baseline["input_token_limit"], 200_000)
        self.assertEqual(baseline["output_tokens_per_call"], 1024)
        self.assertEqual(baseline["cost_limit_usd"], 0.55)
        dispatched = []

        def fake_transport(body):
            dispatched.append(body)
            return {"usage": {"input_tokens": 8000, "output_tokens": 800}}

        response = dispatch_turn(
            baseline, "turn-1", b"exact serialized baseline request", fake_transport
        )
        self.assertEqual(response["usage"]["input_tokens"], 8000)
        self.assertEqual(dispatched, [b"exact serialized baseline request"])
        self.assertEqual(totals(baseline)["input_tokens_used_or_reserved"], 8000)
        self.assertEqual(baseline["calls"][0]["status"], "settled")

        too_large = new_ledger(
            call_limit=4,
            input_token_limit=4096,
            output_tokens_per_call=1024,
            cost_limit_usd=0.55,
            input_price_per_million=2.5,
            output_price_per_million=10.0,
        )
        transport_invocations = []

        def forbidden_transport(body):
            transport_invocations.append(body)
            return {}

        with self.assertRaises(BudgetExceeded):
            dispatch_turn(
                too_large,
                "turn-over-limit",
                b"x",
                forbidden_transport,
            )
        self.assertEqual(transport_invocations, [])

    def test_baseline_ambiguous_dispatch_retains_reservation_and_stops(self):
        budget = new_arm_budget()

        def timed_out(_body):
            raise TimeoutError("ambiguous provider outcome")

        with self.assertRaisesRegex(TimeoutError, "ambiguous"):
            dispatch_turn(budget, "turn-timeout", b"x", timed_out)
        self.assertEqual(budget["calls"][0]["status"], "unknown")
        self.assertIsNotNone(totals(budget)["blocked_reason"])


if __name__ == "__main__":
    unittest.main()
