"""Provider-free tests of canonical session observability."""

from copy import deepcopy
from datetime import UTC, datetime, timedelta
from typing import Any

from sigma import session_observability as obs


def _at(seconds: int) -> datetime:
    return datetime(2026, 1, 1, tzinfo=UTC) + timedelta(seconds=seconds)


def _usage(inp: int, out: int) -> dict[str, int]:
    return {"input_tokens": inp, "output_tokens": out}


def run() -> dict[str, Any]:
    record: dict[str, Any] = {
        "status": "queued",
        "created_at": _at(0).isoformat(),
        "started_at": _at(0).isoformat(),
        "observability_clock": obs.new_clock(_at(0).isoformat()),
    }
    obs.checkpoint_clock(record, _at(1))
    record["status"] = "running"
    obs.checkpoint_clock(record, _at(2))
    assert obs.session_times(record, _at(10)) == {"wall_seconds": 10, "active_seconds": 10}
    # Concurrent provider calls can consume sixteen call-seconds in ten active
    # seconds, and queue/worker transitions must not count overlapping time twice.
    concurrent = [
        {"status": "completed", "provider_attempt_duration_seconds": 8},
        {"status": "completed", "provider_attempt_duration_seconds": 8},
    ]
    assert obs.aggregate_attempt_seconds(concurrent, 0) == 16
    record["status"] = "paused"
    obs.checkpoint_clock(record, _at(10))
    obs.checkpoint_clock(record, _at(20))
    assert obs.session_times(record, _at(20)) == {"wall_seconds": 20, "active_seconds": 10}
    record["status"] = "queued"
    obs.checkpoint_clock(record, _at(30))
    record["status"] = "ended"
    obs.checkpoint_clock(record, _at(40))
    obs.checkpoint_clock(record, _at(50))
    assert obs.session_times(record, _at(50)) == {"wall_seconds": 40, "active_seconds": 20}

    interrupted = deepcopy(record)
    interrupted["status"] = "running"
    obs.checkpoint_clock(interrupted, _at(60))
    obs.invalidate_open_clock(interrupted)
    interrupted["status"] = "paused"
    obs.checkpoint_clock(interrupted, _at(90))
    assert obs.session_times(interrupted, _at(100))["active_seconds"] is None
    interrupted["status"] = "running"
    obs.checkpoint_clock(interrupted, _at(110))
    assert obs.session_times(interrupted, _at(120))["active_seconds"] is None
    historical = {key: value for key, value in record.items() if key != "observability_clock"}
    historical["updated_at"] = _at(40).isoformat()
    assert obs.session_times(historical, _at(50)) == {
        "wall_seconds": 40,
        "active_seconds": None,
    }

    common = {"strategy_id": "s", "cycle": 1, "model": "gpt-6.1-sol"}
    investigator = {
        **common,
        "id": "i",
        "role": "investigator",
        "status": "completed",
        "token_usage": _usage(10, 4),
        "provider_attempt_duration_seconds": 8,
        "execution_tools": [
            {
                "runtime": "python",
                "available": True,
                "image_id": "sha256:" + "a" * 64,
                "observed_at": _at(1).isoformat(),
            }
        ],
    }
    record.update(
        {
            "calls_used": 8,
            "mode": "chatgpt",
            "steps": [
                investigator,
                deepcopy(investigator),
                {
                    **common,
                    "id": "quota",
                    "role": "skeptic",
                    "status": "failed",
                    "failure_kind": "provider_limited",
                    "provider_http_status": 429,
                    "provider_error_code": "subscription_sharing_usage_limit_exceeded",
                    "provider_attempt_duration_seconds": 2,
                },
                {
                    **common,
                    "id": "timeout",
                    "role": "skeptic",
                    "status": "failed",
                    "failure_kind": "timeout",
                    "provider_attempt_duration_seconds": 3,
                },
                {
                    **common,
                    "id": "s",
                    "role": "skeptic",
                    "status": "completed",
                    "token_usage": _usage(6, 3),
                    "provider_attempt_duration_seconds": 7,
                    "execution_tools": [
                        {
                            "runtime": "python",
                            "available": False,
                            "image_id": None,
                            "observed_at": _at(5).isoformat(),
                        }
                    ],
                },
                {
                    **common,
                    "id": "denied",
                    "cycle": 2,
                    "role": "investigator",
                    "status": "failed",
                    "attempt_status": "not_dispatched",
                },
                {
                    **common,
                    "id": "interrupted",
                    "cycle": 2,
                    "role": "investigator",
                    "status": "interrupted",
                    "attempt_status": "unknown",
                },
                {
                    **common,
                    "id": "invalid",
                    "cycle": 3,
                    "role": "investigator",
                    "status": "failed",
                    "failure_kind": "response_invalid",
                    "token_usage_status": "reported",
                    "token_usage": _usage(2, 1),
                    "provider_attempt_duration_seconds": 4,
                },
            ],
            "supervisor_reviews": [
                {
                    **common,
                    "id": "review",
                    "status": "completed",
                    "assessment": {"action": "continue"},
                    "token_usage": _usage(3, 2),
                    "attempt_status": "settled",
                    "provider_attempt_duration_seconds": 2,
                }
            ],
            "reference_compilation": {
                "status": "fallback",
                "attempts": [
                    {
                        "number": 1,
                        "status": "completed",
                        "model": "gpt-6.1-sol",
                        "usage_status": "known",
                        "token_usage": _usage(5, 2),
                        "provider_attempt_duration_seconds": 3,
                    },
                    {"number": 1, "status": "completed", "usage_status": "unknown"},
                    {"number": 2, "status": "unknown", "usage_status": "unknown"},
                ],
            },
            "artifacts": [],
        }
    )
    snapshot = deepcopy(record)
    rows, gap = obs.attempts(record)
    attempted = [row for row in rows if row.get("attempt_status") != "not_dispatched"]
    assert len(attempted) == 9 and gap == 1
    assert obs.accepted_counts(obs.unique_rows(record["steps"]), rows) == {
        "research_calls": 2,
        "accepted_investigator_calls": 1,
        "accepted_skeptic_calls": 1,
        "supervisor_reviews": 1,
    }
    reported = [usage for row in attempted if (usage := obs.reported_usage(row)) is not None]
    assert len(reported) == 5
    total = sum(
        int(usage["input_tokens"] or 0) + int(usage["output_tokens"] or 0)
        for usage in reported
    )
    assert total == 38
    assert obs.aggregate_attempt_seconds(attempted, gap) is None
    assert obs.limit_categories(attempted) == {"subscription_usage_exhausted": 1}
    assert obs.limit_categories(
        [{"provider_http_status": 429, "failure_kind": "provider_limited"}]
    ) == {"http_429_unspecified": 1}
    assert obs.reported_usage({"status": "completed", "token_usage": _usage(-1, 0)}) is None
    assert obs.reported_usage({"status": "completed", "token_usage": _usage(0, 0)}) == {
        "input_tokens": 0,
        "output_tokens": 0,
        "cached_input_tokens": None,
    }
    tools = obs.tool_observations(obs.unique_rows(record["steps"]))
    assert tools["python"]["available"] is False and tools["python"]["step_id"] == "s"
    assert obs.tool_observations([]) == {}
    assert record == snapshot
    settings: dict[str, Any] = {
        "session_settings": {"name": "private", "turn_limit": 5},
        "mode": "chatgpt",
    }
    effective = obs.execution_settings(settings)
    settings["session_settings"]["turn_limit"] = 10
    assert effective == {"turn_limit": 5, "mode": "chatgpt"}
    assert obs.compiler_execution({}) == {"attempt_id": None}
    return record


if __name__ == "__main__":
    run()
    print("PASS session observability")
