"""Provider-free projections of existing session checkpoints.

These helpers never dispatch, reserve, retry, mutate budgets, or probe tools.
The only persisted addition is the diagnostic clock, initialized for new
sessions and updated at existing saves. Historical gaps remain unknown.
"""

from __future__ import annotations

import math
from datetime import datetime
from typing import Any, cast

_ACTIVE = ("queued", "running")
_TERMINAL = ("completed", "ended", "failed", "stopped")


def _timestamp(value: Any) -> datetime | None:
    if not isinstance(value, str):
        return None
    try:
        parsed = datetime.fromisoformat(value)
        return parsed if parsed.utcoffset() is not None else None
    except (ValueError, OverflowError):
        return None


def _number(value: Any) -> float | None:
    if type(value) not in (int, float):
        return None
    try:
        result = float(value)
    except OverflowError:
        return None
    return result if math.isfinite(result) and result >= 0 else None


def _seconds(start: Any, finish: Any) -> float | None:
    first, last = _timestamp(start), _timestamp(finish)
    if first is None or last is None:
        return None
    return _number((last - first).total_seconds())


def new_clock(started_at: str) -> dict[str, Any]:
    return {
        "version": 1,
        "active_seconds": 0.0,
        "active_since": started_at,
        "inactive_since": None,
    }


def checkpoint_clock(record: dict[str, Any], now: datetime) -> None:
    """Track the union of active session intervals, not individual calls."""
    clock = record.get("observability_clock")
    if not isinstance(clock, dict) or clock.get("version") != 1:
        return
    stamp = now.isoformat()
    if record.get("status") in _ACTIVE:
        if clock.get("active_since") is None:
            clock["active_since"] = stamp
            clock["inactive_since"] = None
        return
    if clock.get("active_since") is not None:
        previous = _number(clock.get("active_seconds"))
        interval = _seconds(clock["active_since"], stamp)
        clock["active_seconds"] = (
            previous + interval if previous is not None and interval is not None else None
        )
        clock["active_since"] = None
        clock["inactive_since"] = stamp
    elif clock.get("inactive_since") is None:
        clock["inactive_since"] = stamp


def invalidate_open_clock(record: dict[str, Any]) -> None:
    """A dead worker's actual suspension time cannot be inferred on restart."""
    clock = record.get("observability_clock")
    if isinstance(clock, dict) and clock.get("active_since") is not None:
        clock["active_seconds"] = None


def session_times(record: dict[str, Any], now: datetime) -> dict[str, float | None]:
    clock = record.get("observability_clock")
    active = None
    end = now.isoformat()
    if record.get("status") in _TERMINAL:
        end = (
            clock.get("inactive_since")
            if isinstance(clock, dict)
            else record.get("stopped_at") or record.get("updated_at")
        )
    wall = _seconds(record.get("created_at") or record.get("started_at"), end)
    if isinstance(clock, dict) and clock.get("version") == 1:
        active = _number(clock.get("active_seconds"))
        if record.get("status") in _ACTIVE:
            current = _seconds(clock.get("active_since"), now.isoformat())
            active = active + current if active is not None and current is not None else None
        elif clock.get("active_since") is not None:
            # A read-only recovered projection or malformed historical clock.
            active = None
        if active is not None and (wall is None or active > wall):
            active = None
    return {"wall_seconds": wall, "active_seconds": active}


def unique_rows(value: Any) -> list[dict[str, Any]]:
    """Deduplicate only established identities; retain unidentified evidence."""
    if not isinstance(value, list):
        return []
    result: list[dict[str, Any]] = []
    seen: set[str] = set()
    for row in value:
        if not isinstance(row, dict):
            continue
        key = row.get("id") or row.get("attempt_id")
        if isinstance(key, str) and key:
            if key in seen:
                continue
            seen.add(key)
        result.append(row)
    return result


def compiler_execution(stage: dict[str, Any]) -> dict[str, Any]:
    saved = stage.get("attempt_execution")
    metadata = saved if isinstance(saved, dict) else {}
    return {
        **{
            key: metadata[key]
            for key in ("model", "reasoning_effort", "backend_build_commit", "execution_settings")
            if key in metadata
        },
        "attempt_id": stage.get("attempt_id"),
    }


def _compiler_row(item: dict[str, Any]) -> dict[str, Any]:
    status = item.get("status")
    usage_status = item.get("usage_status")
    return {
        **item,
        "role": "reference_compiler",
        "cycle": 0,
        "status": (
            "interrupted"
            if status == "unknown"
            else "failed"
            if status in ("rejected", "not_dispatched")
            else status
        ),
        "attempt_status": (
            "not_dispatched"
            if status == "not_dispatched" or usage_status == "not_dispatched"
            else "unknown"
            if status in ("unknown", "running", "interrupted")
            else "provider_rejected"
            if status == "rejected"
            else None
        ),
        "failure_kind": (
            "provider_rejected" if status == "rejected" else item.get("failure_type")
        ),
        "token_usage_status": "reported" if usage_status == "known" else "unavailable",
    }


def attempts(record: dict[str, Any]) -> tuple[list[dict[str, Any]], int]:
    """Existing role, review and compiler attempt records; separate budget gaps.

    The scheduler's calls_used includes role and Supervisor calls, not compiler
    attempts. A discrepancy is evidence of missing status, never a synthetic
    success or an extra metered invocation.
    """
    rows = unique_rows(record.get("steps"))
    for review in unique_rows(record.get("supervisor_reviews")):
        if review.get("status") in ("running", "completed", "failed", "interrupted") or (
            review.get("attempt_status") == "not_dispatched"
        ):
            rows.append({**review, "role": "supervisor"})
    rows = unique_rows(rows)
    counted = sum(row.get("attempt_status") != "not_dispatched" for row in rows)
    saved = record.get("calls_used")
    gap = max(0, saved - counted) if type(saved) is int and saved >= 0 else 0

    compiler = record.get("reference_compilation")
    if isinstance(compiler, dict):
        history = unique_rows(compiler.get("attempts"))
        numbers: set[int] = set()
        for item in history:
            number = item.get("number")
            if type(number) is int:
                if number in numbers:
                    continue
                numbers.add(number)
            rows.append(_compiler_row(item))
        current = compiler.get("attempt_number")
        if compiler.get("status") in ("running", "interrupted") and (
            type(current) is not int or current not in numbers
        ):
            rows.append(
                _compiler_row(
                    {
                        **compiler_execution(compiler),
                        "status": compiler["status"],
                        "usage_status": "unknown",
                        "started_at": compiler.get("attempt_started_at"),
                    }
                )
            )
        elif not history and (
            isinstance(compiler.get("token_usage"), dict)
            or compiler.get("usage_status") == "unknown"
            or (compiler.get("status") == "completed" and compiler.get("started_at"))
        ):
            rows.append(
                _compiler_row(
                    {
                        **compiler,
                        **compiler_execution(compiler),
                        "usage_status": (
                            compiler.get("usage_status")
                            or ("known" if isinstance(compiler.get("token_usage"), dict) else None)
                        ),
                    }
                )
            )
    return rows, gap


def accepted_counts(steps: list[dict[str, Any]], rows: list[dict[str, Any]]) -> dict[str, int]:
    accepted = {
        role: sum(
            step.get("role") == role
            and step.get("status") == "completed"
            and step.get("attempt_status") != "not_dispatched"
            for step in steps
        )
        for role in ("investigator", "skeptic")
    }
    return {
        "research_calls": sum(accepted.values()),
        "accepted_investigator_calls": accepted["investigator"],
        "accepted_skeptic_calls": accepted["skeptic"],
        "supervisor_reviews": sum(
            row.get("role") == "supervisor"
            and row.get("status") == "completed"
            and isinstance(row.get("assessment"), dict)
            and row.get("attempt_status") != "not_dispatched"
            for row in rows
        ),
    }

def reported_usage(row: dict[str, Any]) -> dict[str, int | None] | None:
    if row.get("attempt_status") == "not_dispatched":
        return None
    if not (
        row.get("status") in ("completed", "incomplete")
        or row.get("attempt_status") in ("usage_estimated", "settled")
        or row.get("token_usage_status") == "reported"
    ):
        return None
    if row.get("token_usage_status") == "unavailable":
        return None
    usage = row.get("token_usage")
    if not isinstance(usage, dict):
        return None
    inp, out, cached = (
        usage.get("input_tokens"),
        usage.get("output_tokens"),
        usage.get("cached_input_tokens"),
    )
    if type(inp) is not int or type(out) is not int or inp < 0 or out < 0:
        return None
    if type(cached) is not int or not 0 <= cached <= inp:
        cached = None
    return {
        "input_tokens": cast(int, inp),
        "output_tokens": cast(int, out),
        "cached_input_tokens": cast(int | None, cached),
    }


def dispatch_uncertain(row: dict[str, Any]) -> bool:
    if row.get("attempt_status") == "not_dispatched":
        return False
    if (
        row.get("status") in ("completed", "incomplete")
        or reported_usage(row) is not None
        or row.get("attempt_status") in ("provider_rejected", "settled", "usage_estimated")
        or type(row.get("provider_http_status")) is int
    ):
        return False
    # A local checkpoint, timeout or interrupted transport is not proof that
    # the remote provider received the invocation.
    return True


def attempt_seconds(row: dict[str, Any]) -> float | None:
    observed = _number(row.get("provider_attempt_duration_seconds"))
    if observed is not None:
        return observed
    if row.get("status") in ("running", "interrupted", "cancelled", "canceled"):
        return None
    if dispatch_uncertain(row):
        return None
    return _seconds(row.get("started_at"), row.get("finished_at"))


def aggregate_attempt_seconds(rows: list[dict[str, Any]], gap: int) -> float | None:
    values = [attempt_seconds(row) for row in rows]
    if gap or any(value is None for value in values):
        return None
    return sum(cast(float, value) for value in values)


def limit_categories(rows: list[dict[str, Any]]) -> dict[str, int]:
    result: dict[str, int] = {}
    for row in rows:
        code = row.get("diagnostic_provider_error_code") or row.get("provider_error_code")
        status = row.get("diagnostic_provider_http_status") or row.get("provider_http_status")
        kind = row.get("failure_kind")
        if code == "subscription_sharing_usage_limit_exceeded":
            category = "subscription_usage_exhausted"
        elif code in (
            "project_spend_limit_exceeded",
            "insufficient_quota",
            "billing_hard_limit_reached",
            "billing_not_active",
        ):
            category = "quota_or_billing_exhausted"
        elif code in ("rate_limit_exceeded", "rate_limit_error"):
            category = "rate_limited"
        elif status == 429:
            category = "http_429_unspecified"
        elif kind == "provider_rate_limited":
            category = "rate_limit_unspecified"
        elif kind == "provider_limited":
            category = "provider_limit_unspecified"
        else:
            continue
        result[category] = result.get(category, 0) + 1
    return result


def execution_settings(record: dict[str, Any]) -> dict[str, Any]:
    """Capture only effective, non-sensitive execution controls, no prompts."""
    settings = record.get("session_settings")
    source = settings if isinstance(settings, dict) else {}
    result = {
        key: source[key]
        for key in ("brainstorm_mode", "supervisor_mode", "unlimited_turns", "turn_limit")
        if key in source and type(source[key]) in (bool, int, str)
    }
    for key in (
        "mode",
        "output_token_limit",
        "duration_limit_minutes",
        "call_limit",
        "scheduler_version",
    ):
        if key in record and (record[key] is None or type(record[key]) in (bool, int, str)):
            result[key] = record[key]
    return result


def tool_observations(steps: list[dict[str, Any]]) -> dict[str, dict[str, Any]]:
    """Latest recorded capability observations, never a new runtime probe."""
    result: dict[str, dict[str, Any]] = {}
    timestamps: dict[str, datetime] = {}
    for step in steps:
        tools = step.get("execution_tools")
        if not isinstance(tools, list):
            continue
        for tool in tools:
            if not isinstance(tool, dict):
                continue
            runtime = tool.get("runtime")
            observed = _timestamp(tool.get("observed_at"))
            if runtime not in ("python", "sagemath") or observed is None:
                continue
            if runtime in timestamps and observed < timestamps[runtime]:
                continue
            timestamps[runtime] = observed
            image = tool.get("image_id")
            available = tool.get("available")
            result[runtime] = {
                "observed_at": tool["observed_at"],
                "available": available if type(available) is bool else None,
                "image_id": image if isinstance(image, str) else None,
                "step_id": step.get("id"),
            }
    return result
