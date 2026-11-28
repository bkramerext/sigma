"""Provider-free projections of existing session checkpoints.

These helpers never dispatch, reserve, retry, mutate budgets, or probe tools.
The diagnostic clock and attempt metadata are optional persisted observations.
Historical gaps remain unknown; these helpers never change enforcement.
"""

from __future__ import annotations

import math
from datetime import datetime
from typing import Any, Literal, cast

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
        "active_uncertain": False,
        "terminal_at": None,
    }


def checkpoint_clock(record: dict[str, Any], now: datetime) -> None:
    """Checkpoint the union of active intervals at durable save boundaries."""
    clock = record.get("observability_clock")
    if not isinstance(clock, dict) or clock.get("version") != 1:
        return
    stamp = now.isoformat()
    status = record.get("status")
    previous_start = clock.get("active_since")
    if previous_start is not None:
        # A confirmed Stop/provider-limit timestamp may precede persistence.
        end = stamp
        if status not in _ACTIVE:
            stopped = record.get("stopped_at")
            if (
                _seconds(previous_start, stopped) is not None
                and _seconds(stopped, stamp) is not None
            ):
                end = stopped
            elif _timestamp(stopped) is not None and _seconds(stopped, previous_start) is not None:
                clock["active_uncertain"] = True
                clock["active_seconds"] = None
                end = previous_start
        interval = _seconds(previous_start, end)
        previous = _number(clock.get("active_seconds"))
        if previous is None or interval is None:
            clock["active_uncertain"] = True
        else:
            clock["active_seconds"] = previous + interval
        if status in _ACTIVE and interval is None:
            # Do not double-count when the wall clock catches up after rollback.
            return
        clock["active_since"] = stamp if status in _ACTIVE else None
        if status not in _ACTIVE:
            clock["inactive_since"] = end
    elif status in _ACTIVE:
        clock["active_since"] = stamp
        clock["inactive_since"] = None
    elif clock.get("inactive_since") is None:
        clock["inactive_since"] = stamp

    if status in _ACTIVE:
        clock["terminal_at"] = None
    elif status in _TERMINAL and clock.get("terminal_at") is None:
        stopped = record.get("stopped_at")
        start = record.get("created_at") or record.get("started_at")
        clock["terminal_at"] = (
            stopped
            if status == "stopped"
            and _seconds(start, stopped) is not None
            and _seconds(stopped, stamp) is not None
            else stamp
        )


def invalidate_open_clock(record: dict[str, Any]) -> None:
    """Retain completed intervals, but do not charge an unknown dead-worker gap."""
    clock = record.get("observability_clock")
    if isinstance(clock, dict) and clock.get("active_since") is not None:
        clock["active_uncertain"] = True
        clock["active_since"] = None


def session_times(record: dict[str, Any], now: datetime) -> dict[str, float | None]:
    clock = record.get("observability_clock")
    active = None
    lower_bound = None
    stamp = now.isoformat()
    status = record.get("status")
    end = stamp
    if status in _TERMINAL:
        recorded_end = clock.get("terminal_at") if isinstance(clock, dict) else None
        end = recorded_end or (
            record.get("stopped_at") or record.get("updated_at")
            if status == "stopped"
            else record.get("updated_at")
        )
    start = record.get("created_at") or record.get("started_at")
    wall = _seconds(start, end)
    if isinstance(clock, dict) and clock.get("version") == 1:
        lower_bound = _number(clock.get("active_seconds"))
        current = _seconds(clock.get("active_since"), stamp) if status in _ACTIVE else 0.0
        consistent = status in _ACTIVE or clock.get("active_since") is None
        if (
            lower_bound is not None
            and current is not None
            and consistent
            and not clock.get("active_uncertain")
        ):
            active = lower_bound + current
        if active is not None and (wall is None or active > wall):
            active = None
        if lower_bound is not None and wall is not None and lower_bound > wall:
            lower_bound = None
    # Legacy event history does not prove continuous activity. Without a
    # diagnostic clock, only wall time is established by saved timestamps.
    return {
        "wall_seconds": wall,
        "active_seconds": active,
        "active_seconds_lower_bound": lower_bound,
    }


def _identity(row: dict[str, Any]) -> str | None:
    key = row.get("id") or row.get("attempt_id")
    return key if isinstance(key, str) and key else None


def _conflicts(first: dict[str, Any], second: dict[str, Any]) -> bool:
    fields = (
        "status",
        "role",
        "strategy_id",
        "cycle",
        "attempt_status",
        "token_usage",
        "token_usage_status",
        "usage_status",
        "model",
        "reasoning_effort",
        "backend_build_commit",
        "started_at",
        "finished_at",
        "attempt_id",
        "assessment",
        "output",
        "provider_attempt_duration_seconds",
        "provider_error_code",
        "provider_http_status",
        "retry_decision",
        "automatic_retry_of",
        "resume_sequence",
        "execution_settings",
        "observed_cached_input_tokens",
        "observed_cache_metadata_status",
        "provider_response_observed",
        "simulated",
        "provider_response_channel",
        "diagnostic_provider_http_status",
    )
    return any(
        first.get(key) is not None and second.get(key) is not None and first[key] != second[key]
        for key in fields
    )


def _combine(first: dict[str, Any], second: dict[str, Any]) -> dict[str, Any]:
    if (
        first.get("observability_conflict")
        or second.get("observability_conflict")
        or _conflicts(first, second)
    ):
        # Preserve identity for the inventory, not a disputed usage/result.
        return {
            "id": _identity(first),
            "number": first.get("number"),
            "role": first.get("role"),
            "observability_conflict": True,
        }
    return {**second, **{key: value for key, value in first.items() if value is not None}}


def unique_rows(value: Any) -> list[dict[str, Any]]:
    """Collapse compatible copies; a contradictory identity remains unknown."""
    if not isinstance(value, list):
        return []
    result: list[dict[str, Any]] = []
    seen: dict[str, int] = {}
    for row in value:
        if not isinstance(row, dict):
            continue
        key = _identity(row)
        if key is not None and key in seen:
            index = seen[key]
            result[index] = _combine(result[index], row)
            continue
        if key is not None:
            seen[key] = len(result)
        result.append(row)
    return result


def inventory_complete(record: dict[str, Any], rows: list[dict[str, Any]], gap: int) -> bool:
    if gap or type(record.get("calls_used")) is not int or record["calls_used"] < 0:
        return False
    for key in ("steps", "supervisor_reviews"):
        source = record.get(key, [] if key == "supervisor_reviews" else None)
        if not isinstance(source, list) or any(not isinstance(row, dict) for row in source):
            return False
    compiler = record.get("reference_compilation")
    if isinstance(compiler, dict) and "attempts" in compiler:
        source = compiler["attempts"]
        if not isinstance(source, list) or any(not isinstance(row, dict) for row in source):
            return False
    counted = sum(
        row.get("role") != "reference_compiler" and row.get("attempt_status") != "not_dispatched"
        for row in rows
    )
    return counted == record["calls_used"] and all(
        not row.get("observability_conflict")
        and (
            _identity(row) is not None
            or (row.get("role") == "reference_compiler" and type(row.get("number")) is int)
        )
        and (
            row.get("attempt_status") == "not_dispatched"
            or row.get("status") in ("running", "completed", "failed", "incomplete", "interrupted")
        )
        for row in rows
    )


def compiler_execution(stage: dict[str, Any]) -> dict[str, Any]:
    saved = stage.get("attempt_execution")
    metadata = saved if isinstance(saved, dict) else {}
    return {
        **{
            key: metadata[key]
            for key in (
                "model",
                "reasoning_effort",
                "backend_build_commit",
                "execution_settings",
                "resume_sequence",
            )
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
        "failure_kind": ("provider_rejected" if status == "rejected" else item.get("failure_type")),
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
        by_number: dict[int, dict[str, Any]] = {}
        unidentified = []
        for item in history:
            number = item.get("number")
            if type(number) is int:
                by_number[number] = (
                    _combine(by_number[number], item) if number in by_number else item
                )
            else:
                unidentified.append(item)
        rows.extend(_compiler_row(item) for item in by_number.values())
        rows.extend(_compiler_row(item) for item in unidentified)
        current = compiler.get("attempt_number")
        if compiler.get("status") in ("running", "interrupted") and (
            type(current) is not int or current not in by_number
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
            and not step.get("observability_conflict")
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
    if row.get("attempt_status") == "not_dispatched" or row.get("observability_conflict"):
        return None
    if not (
        row.get("status") in ("completed", "incomplete")
        or row.get("attempt_status") == "settled"
        or row.get("token_usage_status") == "reported"
    ):
        return None
    if row.get("token_usage_status") in ("unavailable", "estimated", "unknown"):
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
    if cached is None and row.get("role") == "supervisor":
        cached = row.get("observed_cached_input_tokens")
    if type(cached) is not int or not 0 <= cached <= inp:
        cached = None
    return {
        "input_tokens": cast(int, inp),
        "output_tokens": cast(int, out),
        "cached_input_tokens": cast(int | None, cached),
    }


def receipt_state(
    row: dict[str, Any], *, simulated: bool = False
) -> Literal["confirmed", "uncertain", "not_dispatched", "simulated"]:
    """Remote receipt requires transport/usage evidence, never lifecycle status alone."""
    attempt_status = row.get("attempt_status")
    if attempt_status == "not_dispatched":
        return "not_dispatched"
    if simulated or row.get("simulated") is True or row.get("mode") == "mock":
        return "simulated"
    role = row.get("role")
    compiler = role == "reference_compiler"
    identified = _identity(row) is not None or (
        compiler and type(row.get("number")) is int and row["number"] > 0
    )
    if (
        row.get("observability_conflict")
        or not identified
        or role not in ("investigator", "skeptic", "supervisor", "reference_compiler")
        or attempt_status in ("preparing", "reserved")
        or row.get("status") not in ("completed", "incomplete", "failed", "interrupted", "running")
    ):
        return "uncertain"
    audit = row.get("provider_input_audit")
    if (
        isinstance(audit, dict)
        and audit.get("kind") == "exact_provider_request_body"
        and audit.get("status")
        in (
            "provider_response_received",
            "provider_response_incomplete",
            "provider_response_invalid",
        )
    ):
        return "confirmed"
    if row.get("token_usage_status") == "reported" and reported_usage(row) is not None:
        return "confirmed"
    if role == "supervisor" and row.get("provider_response_observed") is True:
        return "confirmed"
    status = row.get("provider_http_status")
    diagnostic_status = row.get("diagnostic_provider_http_status")
    if (
        type(status) is int
        and 100 <= status <= 599
        and (compiler or row.get("provider_response_channel") in ("http", "stream"))
    ) or (compiler and type(diagnostic_status) is int and 100 <= diagnostic_status <= 599):
        return "confirmed"
    return "uncertain"


def dispatch_uncertain(row: dict[str, Any]) -> bool:
    return receipt_state(row) == "uncertain"


def cache_metadata_status(row: dict[str, Any]) -> str:
    if row.get("observed_cache_metadata_status") in ("reported", "missing", "malformed"):
        return row["observed_cache_metadata_status"]
    usage = row.get("token_usage")
    if not isinstance(usage, dict) or usage.get("cached_input_tokens") is None:
        return "missing"
    cached = usage["cached_input_tokens"]
    inp = usage.get("input_tokens")
    return (
        "reported"
        if type(cached) is int and type(inp) is int and 0 <= cached <= inp
        else "malformed"
    )


def observed_cache(raw: Any) -> dict[str, Any]:
    """Optional Supervisor cache provenance, independent of settlement input."""
    usage = raw.get("usage") if isinstance(raw, dict) else None
    if not isinstance(usage, dict):
        return {"observed_cache_metadata_status": "missing"}
    details = usage.get("input_tokens_details")
    if details is None:
        return {"observed_cache_metadata_status": "missing"}
    if not isinstance(details, dict):
        return {"observed_cache_metadata_status": "malformed"}
    cached = details.get("cached_tokens")
    inp = usage.get("input_tokens")
    if cached is None:
        return {"observed_cache_metadata_status": "missing"}
    if type(cached) is int and type(inp) is int and 0 <= cached <= inp:
        return {
            "observed_cache_metadata_status": "reported",
            "observed_cached_input_tokens": cached,
        }
    return {"observed_cache_metadata_status": "malformed"}


def budget_observation(record: dict[str, Any]) -> dict[str, Any]:
    ledger = record.get("hard_budget_ledger")
    entries = ledger.get("calls") if isinstance(ledger, dict) else None
    if not isinstance(entries, list):
        return {"ledger_inventory_complete": False} if ledger is not None else {}
    counts: dict[str, int] = {}
    cost: dict[str, float | None] = {}
    seen: set[str] = set()
    complete = True
    for item in entries:
        if not isinstance(item, dict):
            return {"ledger_inventory_complete": False}
        identifier, status = item.get("call_id"), item.get("status")
        if (
            not isinstance(identifier, str)
            or not identifier
            or identifier in seen
            or status
            not in (
                "settled",
                "reserved",
                "unknown",
                "rejected",
                "unknown_supervisor_abandoned",
                "unknown_compiler_abandoned",
            )
        ):
            return {"ledger_inventory_complete": False}
        seen.add(identifier)
        counts[status] = counts.get(status, 0) + 1
        amount = _number(item.get("cost_bound_usd"))
        if amount is None:
            complete = False
        previous = cost.get(status, 0.0)
        cost[status] = previous + amount if previous is not None and amount is not None else None
    return {
        "ledger_inventory_complete": complete,
        "ledger_call_counts": counts,
        "ledger_cost_bound_usd_by_status": cost,
    }


def attempt_seconds(row: dict[str, Any]) -> float | None:
    if row.get("observability_conflict"):
        return None
    observed = _number(row.get("provider_attempt_duration_seconds"))
    if observed is not None:
        return observed
    # Historical step intervals include non-provider work; do not present them
    # as observed provider durations.
    return None


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


def resume_sequence(record: dict[str, Any]) -> int | None:
    """Identify an actual saved resume event; missing history is unknown."""
    events = record.get("events")
    if not isinstance(events, list) or not events or not isinstance(events[0], dict):
        return None
    if events[0].get("kind") not in ("queued", "simulation.queued"):
        return None
    latest = 0
    for event in events:
        if not isinstance(event, dict):
            return None
        if event.get("kind") == "resumed":
            sequence = event.get("sequence")
            if type(sequence) is not int or sequence <= latest:
                return None
            latest = sequence
    return latest


def retry_origins(rows: list[dict[str, Any]], legacy_strategy: Any) -> dict[str, int]:
    """Classify only distinct later attempts with explicit causal evidence."""
    result = {"automatic": 0, "operator": 0, "unknown": 0}
    prior: dict[tuple[str, int, str], dict[str, Any]] = {}
    for row in rows:
        role = row.get("role")
        cycle = row.get("cycle")
        strategy = row.get("strategy_id")
        if not isinstance(strategy, str):
            strategy = str(legacy_strategy)
        if not isinstance(role, str) or type(cycle) is not int:
            continue
        key = (strategy, cycle, role)
        previous = prior.get(key)
        if previous is not None:
            before = previous.get("resume_sequence")
            after = row.get("resume_sequence")
            if type(before) is int and type(after) is int and after > before:
                result["operator"] += 1
            elif (
                isinstance(row.get("automatic_retry_of"), str)
                and row["automatic_retry_of"] == _identity(previous)
            ) or (
                role == "reference_compiler"
                and previous.get("retry_decision") == "retry"
                and type(before) is int
                and before == after
            ):
                result["automatic"] += 1
            else:
                result["unknown"] += 1
        prior[key] = row
    return result
