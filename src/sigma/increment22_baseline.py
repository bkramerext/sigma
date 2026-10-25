"""Budget adapter for the offline-prepared Increment 22 single-agent arm."""

from collections.abc import Callable
from typing import Any

from sigma.research_budget import (
    BudgetExceeded,
    cancel_before_dispatch,
    mark_unknown,
    new_ledger,
    reserve_before_dispatch,
    settle_after_response,
)


def new_arm_budget() -> dict[str, Any]:
    """Return the exact per-arm ledger configuration frozen for T146."""
    return new_ledger(
        call_limit=4,
        input_token_limit=200_000,
        output_tokens_per_call=1024,
        cost_limit_usd=0.55,
        input_price_per_million=2.5,
        output_price_per_million=10.0,
    )


def reserve_turn(ledger: dict[str, Any], turn_id: str, request_body: bytes) -> dict[str, Any]:
    """Mandatory immediate preflight for the baseline's exact serialized body."""
    return reserve_before_dispatch(ledger, call_id=turn_id, request_body=request_body)


def dispatch_turn(
    ledger: dict[str, Any],
    turn_id: str,
    request_body: bytes,
    transport: Callable[[bytes], dict[str, Any]],
) -> dict[str, Any]:
    """Reserve first, then invoke transport, retaining ambiguous outcomes in full."""
    reserve_turn(ledger, turn_id, request_body)
    try:
        response = transport(request_body)
    except Exception:
        mark_turn_unknown(ledger, turn_id)
        raise
    usage = response.get("usage") if isinstance(response, dict) else None
    if not isinstance(usage, dict):
        mark_turn_unknown(ledger, turn_id)
        raise BudgetExceeded("Baseline provider usage is unknown; dispatch is blocked")
    input_tokens = usage.get("input_tokens")
    output_tokens = usage.get("output_tokens")
    if type(input_tokens) is not int or type(output_tokens) is not int:
        mark_turn_unknown(ledger, turn_id)
        raise BudgetExceeded("Baseline provider usage is unknown; dispatch is blocked")
    settle_turn(ledger, turn_id, input_tokens, output_tokens)
    return response


def settle_turn(
    ledger: dict[str, Any], turn_id: str, input_tokens: int, output_tokens: int
) -> None:
    settle_after_response(
        ledger,
        call_id=turn_id,
        input_tokens=input_tokens,
        output_tokens=output_tokens,
    )


def mark_turn_unknown(ledger: dict[str, Any], turn_id: str) -> None:
    mark_unknown(ledger, call_id=turn_id)


def cancel_undispatched_turn(ledger: dict[str, Any], turn_id: str) -> None:
    cancel_before_dispatch(ledger, call_id=turn_id)
