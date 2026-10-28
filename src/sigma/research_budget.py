"""Fail-closed cumulative call, token and cost reservations for research arms."""

from __future__ import annotations

from typing import Any

LEDGER_VERSION = 1
INPUT_TOKEN_OVERHEAD_PER_CALL = 8192


class BudgetExceeded(ValueError):
    """A provider request would exceed a research arm's frozen budget."""


def new_ledger(
    *,
    call_limit: int,
    input_token_limit: int,
    output_tokens_per_call: int,
    cost_limit_usd: float,
    input_price_per_million: float,
    output_price_per_million: float,
) -> dict[str, Any]:
    if min(call_limit, input_token_limit, output_tokens_per_call) < 1:
        raise ValueError("Research budget limits must be positive")
    if min(cost_limit_usd, input_price_per_million, output_price_per_million) < 0:
        raise ValueError("Research budget prices and cost limit cannot be negative")
    return {
        "version": LEDGER_VERSION,
        "call_limit": call_limit,
        "input_token_limit": input_token_limit,
        "output_tokens_per_call": output_tokens_per_call,
        "cost_limit_usd": round(cost_limit_usd, 9),
        "input_price_per_million": input_price_per_million,
        "output_price_per_million": output_price_per_million,
        "calls": [],
        "blocked_reason": None,
    }


def _call_bounds(ledger: dict[str, Any]) -> tuple[int, int, float, int]:
    input_bound = output_bound = calls = 0
    cost_bound = 0.0
    for item in ledger["calls"]:
        calls += 1
        if item["status"] == "settled":
            input_bound += item["input_tokens"]
            output_bound += item["output_tokens"]
        else:
            # A dispatched request with unknown outcome keeps the entire
            # reservation. It is never silently treated as zero usage.
            input_bound += item["input_token_bound"]
            output_bound += item["output_token_reservation"]
        cost_bound += item["cost_bound_usd"]
    return input_bound, output_bound, cost_bound, calls


def reserve_before_dispatch(
    ledger: dict[str, Any], *, call_id: str, request_body: bytes
) -> dict[str, Any]:
    """Reserve usage/cost before dispatch; request bytes conservatively bound input tokens."""
    if ledger.get("version") != LEDGER_VERSION:
        raise BudgetExceeded("Research budget ledger version is invalid")
    if ledger.get("blocked_reason"):
        raise BudgetExceeded("Research arm is blocked by an unknown or invalid provider call")
    if any(item.get("status") == "reserved" for item in ledger["calls"]):
        raise BudgetExceeded("A prior provider call is still in flight or unsettled")
    if any(item.get("call_id") == call_id for item in ledger["calls"]):
        raise BudgetExceeded("Research call ID has already been reserved")
    input_token_bound = len(request_body) + INPUT_TOKEN_OVERHEAD_PER_CALL
    output_reservation = int(ledger["output_tokens_per_call"])
    used_input, used_output, used_cost, calls = _call_bounds(ledger)
    if calls + 1 > int(ledger["call_limit"]):
        raise BudgetExceeded("Research arm call limit would be exceeded")
    if used_input + input_token_bound > int(ledger["input_token_limit"]):
        raise BudgetExceeded("Research arm cumulative input-token limit would be exceeded")
    if used_cost + _cost_bound(ledger, input_token_bound, output_reservation) > float(
        ledger["cost_limit_usd"]
    ):
        raise BudgetExceeded("Research arm reserved cost limit would be exceeded")
    if used_output + output_reservation > int(ledger["call_limit"]) * output_reservation:
        raise BudgetExceeded("Research arm cumulative output-token limit would be exceeded")
    cost = _cost_bound(ledger, input_token_bound, output_reservation)
    reservation = {
        "call_id": call_id,
        "status": "reserved",
        "request_body_bytes": len(request_body),
        "input_token_bound": input_token_bound,
        "output_token_reservation": output_reservation,
        "cost_bound_usd": cost,
    }
    ledger["calls"].append(reservation)
    return reservation


def settle_after_response(
    ledger: dict[str, Any], *, call_id: str, input_tokens: int, output_tokens: int
) -> None:
    """Replace a reservation with verified provider usage or block on inconsistency."""
    item = next((entry for entry in ledger["calls"] if entry["call_id"] == call_id), None)
    if item is None or item["status"] != "reserved":
        raise BudgetExceeded("Research call has no unsettled pre-dispatch reservation")
    if (
        type(input_tokens) is not int
        or type(output_tokens) is not int
        or input_tokens < 0
        or output_tokens < 0
        or input_tokens > item["input_token_bound"]
        or output_tokens > item["output_token_reservation"]
    ):
        item["status"] = "unknown"
        ledger["blocked_reason"] = "Provider usage exceeded or failed its reserved bound"
        raise BudgetExceeded(ledger["blocked_reason"])
    item.update(
        {
            "status": "settled",
            "input_tokens": input_tokens,
            "output_tokens": output_tokens,
            "cost_bound_usd": _cost_bound(ledger, input_tokens, output_tokens),
        }
    )


def cancel_before_dispatch(ledger: dict[str, Any], *, call_id: str) -> None:
    """Release a reservation only when the transport definitely was not invoked."""
    index = next((i for i, item in enumerate(ledger["calls"]) if item["call_id"] == call_id), None)
    if index is None or ledger["calls"][index]["status"] != "reserved":
        raise BudgetExceeded("Only an undispatched reservation can be cancelled")
    del ledger["calls"][index]


def mark_unknown(ledger: dict[str, Any], *, call_id: str) -> None:
    """Keep the full reservation and prevent further dispatch after ambiguity."""
    item = next((entry for entry in ledger["calls"] if entry["call_id"] == call_id), None)
    if item is None:
        raise BudgetExceeded("Unknown research call has no pre-dispatch reservation")
    if item["status"] == "reserved":
        item["status"] = "unknown"
        ledger["blocked_reason"] = "Provider call outcome or usage is unknown"


def settle_rejected(ledger: dict[str, Any], *, call_id: str) -> None:
    """Record an explicit provider rejection as a zero-usage attempt."""
    item = next((entry for entry in ledger["calls"] if entry["call_id"] == call_id), None)
    if item is None or item["status"] != "reserved":
        raise BudgetExceeded("Rejected research call has no unsettled reservation")
    item.update({"status": "rejected", "input_tokens": 0, "output_tokens": 0, "cost_bound_usd": 0.0})


def _cost_bound(ledger: dict[str, Any], input_tokens: int, output_tokens: int) -> float:
    return (
        input_tokens * float(ledger["input_price_per_million"])
        + output_tokens * float(ledger["output_price_per_million"])
    ) / 1_000_000


def totals(ledger: dict[str, Any]) -> dict[str, Any]:
    input_bound, output_bound, cost_bound, calls = _call_bounds(ledger)
    return {
        "calls_including_unknown": calls,
        "input_tokens_used_or_reserved": input_bound,
        "output_tokens_used_or_reserved": output_bound,
        "cost_usd_used_or_reserved": round(cost_bound, 9),
        "blocked_reason": ledger.get("blocked_reason"),
    }
