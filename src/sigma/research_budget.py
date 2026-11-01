"""Fail-closed cumulative call, token and cost reservations for research arms."""

from __future__ import annotations

from typing import Any

LEDGER_VERSION = 1
INPUT_TOKEN_OVERHEAD_PER_CALL = 8192


class BudgetExceeded(ValueError):
    """A provider request would exceed a research arm's frozen budget."""


def increase_call_limit(ledger: dict[str, Any], new_limit: int) -> tuple[int, int]:
    """Audibly extend only the call ceiling; token and cost ceilings stay fixed."""
    if ledger.get("version") != LEDGER_VERSION:
        raise BudgetExceeded("Research budget ledger version is invalid")
    if type(new_limit) is not int or new_limit < int(ledger.get("call_limit", 0)):
        raise BudgetExceeded("Research call limit can only be increased by an integer")
    old_limit = int(ledger["call_limit"])
    ledger["call_limit"] = new_limit
    return old_limit, new_limit


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
        if item["status"] in {"settled", "rejected"}:
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
    ledger: dict[str, Any],
    *,
    call_id: str,
    request_body: bytes,
    output_token_reservation: int | None = None,
    allow_concurrent: bool = False,
) -> dict[str, Any]:
    """Reserve usage/cost before dispatch; request bytes bound input tokens.

    Portfolio dispatch may permit multiple distinct reservations when the caller
    serializes ledger mutations under its session state lock. Every new claim
    still checks aggregate call, input-token and cost ceilings atomically.
    Standalone/legacy callers retain the one-outstanding-call default.
    """
    if ledger.get("version") != LEDGER_VERSION:
        raise BudgetExceeded("Research budget ledger version is invalid")
    if ledger.get("blocked_reason"):
        raise BudgetExceeded("Research arm is blocked by an unknown or invalid provider call")
    if not allow_concurrent and any(item.get("status") == "reserved" for item in ledger["calls"]):
        raise BudgetExceeded("A prior provider call is still in flight or unsettled")
    if any(item.get("call_id") == call_id for item in ledger["calls"]):
        raise BudgetExceeded("Research call ID has already been reserved")
    input_token_bound = len(request_body) + INPUT_TOKEN_OVERHEAD_PER_CALL
    output_reservation = (
        int(ledger["output_tokens_per_call"])
        if output_token_reservation is None
        else output_token_reservation
    )
    if type(output_reservation) is not int or output_reservation < 1:
        raise BudgetExceeded("Research output reservation must be a positive whole number")
    used_input, _used_output, used_cost, calls = _call_bounds(ledger)
    if calls + 1 > int(ledger["call_limit"]):
        raise BudgetExceeded("Research arm call limit would be exceeded")
    if used_input + input_token_bound > int(ledger["input_token_limit"]):
        raise BudgetExceeded("Research arm cumulative input-token limit would be exceeded")
    call_cost_bound = _cost_bound(ledger, input_token_bound, output_reservation)
    if used_cost + call_cost_bound > float(ledger["cost_limit_usd"]):
        remaining = max(0.0, float(ledger["cost_limit_usd"]) - used_cost)
        raise BudgetExceeded(
            "Research arm reserved cost limit would be exceeded: "
            f"the next call needs a conservative ${call_cost_bound:.4f} reservation, "
            f"but only ${remaining:.4f} remains of the project session cap. "
            "No provider call was dispatched. Increase the session cost allowance "
            "or wait until more account allowance is available."
        )
    cost = call_cost_bound
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
    ):
        item["status"] = "unknown"
        ledger["blocked_reason"] = "Provider input usage exceeded or failed its reserved bound"
        raise BudgetExceeded(ledger["blocked_reason"])
    # Output reservation is a pre-dispatch estimate for affordability, not a
    # response validity ceiling. A completed response is chargeable and must
    # be recorded even when actual output exceeds the estimate; its exact cost
    # then prevents subsequent calls from exceeding the session budget.
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
    item.update(
        {"status": "rejected", "input_tokens": 0, "output_tokens": 0, "cost_bound_usd": 0.0}
    )


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
