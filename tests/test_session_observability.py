"""Provider-free tests of canonical session observability."""

from copy import deepcopy
from datetime import UTC, datetime, timedelta
from itertools import permutations
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
    assert obs.session_times(record, _at(10)) == {
        "wall_seconds": 10,
        "active_seconds": 10,
        "active_seconds_lower_bound": 2,
    }
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
    assert obs.session_times(record, _at(20)) == {
        "wall_seconds": 20,
        "active_seconds": 10,
        "active_seconds_lower_bound": 10,
    }
    record["status"] = "queued"
    obs.checkpoint_clock(record, _at(30))
    record["status"] = "ended"
    obs.checkpoint_clock(record, _at(40))
    obs.checkpoint_clock(record, _at(50))
    assert obs.session_times(record, _at(50)) == {
        "wall_seconds": 40,
        "active_seconds": 20,
        "active_seconds_lower_bound": 20,
    }

    interrupted = deepcopy(record)
    interrupted["status"] = "running"
    obs.checkpoint_clock(interrupted, _at(60))
    obs.invalidate_open_clock(interrupted)
    interrupted["status"] = "paused"
    obs.checkpoint_clock(interrupted, _at(90))
    assert obs.session_times(interrupted, _at(100))["active_seconds"] is None
    assert obs.session_times(interrupted, _at(100))["active_seconds_lower_bound"] == 20
    interrupted["status"] = "running"
    obs.checkpoint_clock(interrupted, _at(110))
    assert obs.session_times(interrupted, _at(120))["active_seconds"] is None
    historical = {key: value for key, value in record.items() if key != "observability_clock"}
    historical["updated_at"] = _at(40).isoformat()
    assert obs.session_times(historical, _at(50)) == {
        "wall_seconds": 40,
        "active_seconds": None,
        "active_seconds_lower_bound": None,
    }
    historical["events"] = [{"kind": "queued"}, {"kind": "completed"}]
    assert obs.session_times(historical, _at(50))["active_seconds"] is None
    historical["events"].insert(1, {"kind": "paused"})
    assert obs.session_times(historical, _at(50))["active_seconds"] is None
    rollback = deepcopy(record)
    rollback["status"] = "running"
    obs.checkpoint_clock(rollback, _at(60))
    obs.checkpoint_clock(rollback, _at(55))
    obs.checkpoint_clock(rollback, _at(70))
    assert obs.session_times(rollback, _at(70))["active_seconds"] is None
    assert obs.session_times(rollback, _at(70))["active_seconds_lower_bound"] == 30

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
    assert len(reported) == 4
    total = sum(
        int(usage["input_tokens"] or 0) + int(usage["output_tokens"] or 0) for usage in reported
    )
    assert total == 31
    assert not obs.inventory_complete(record, rows, gap)
    assert sum(bool(row.get("observability_conflict")) for row in rows) == 1
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
    assert obs.observed_cache(
        {
            "usage": {
                "input_tokens": 7,
                "output_tokens": 3,
                "input_tokens_details": {"cached_tokens": "bad"},
            }
        }
    ) == {"observed_cache_metadata_status": "malformed"}
    assert (
        obs.reported_usage(
            {"status": "failed", "attempt_status": "usage_estimated", "token_usage": _usage(4, 5)}
        )
        is None
    )
    conflicting = obs.unique_rows(
        [
            {"id": "same", "status": "completed", "token_usage": _usage(1, 2)},
            {"id": "same", "status": "failed", "token_usage": _usage(7, 8)},
        ]
    )
    assert len(conflicting) == 1 and conflicting[0]["observability_conflict"]
    assert obs.reported_usage(conflicting[0]) is None
    assert obs.dispatch_uncertain(conflicting[0])
    received = {
        "id": "audit",
        "role": "investigator",
        "status": "completed",
        "provider_input_audit": {
            "kind": "exact_provider_request_body",
            "status": "provider_response_received",
            "request_body_sha256": "a" * 64,
            "request_body_compressed": "not part of the diagnostic comparison",
        },
    }
    sparse = {"id": "audit", "provider_input_audit": {"kind": "exact_provider_request_body"}}
    contrary = {
        **received,
        "provider_input_audit": {"status": "call_failed_dispatch_unknown"},
    }
    for order in permutations([received, sparse, contrary]):
        reconciled = obs.unique_rows(list(order))
        assert len(reconciled) == 1
        assert reconciled[0]["observability_conflict"]
        assert obs.receipt_state(reconciled[0]) == "uncertain"
    for order in permutations([received, sparse]):
        reconciled = obs.unique_rows(list(order))
        assert obs.receipt_state(reconciled[0]) == "uncertain"
        assert "request_body_compressed" not in reconciled[0]["provider_input_audit"]
    legacy = {
        **received,
        "provider_input_audit": {
            "kind": "exact_provider_request_body",
            "status": "provider_response_received",
        },
    }
    for order in permutations([legacy, sparse]):
        assert obs.receipt_state(obs.unique_rows(list(order))[0]) == "confirmed"
    for key, left, right in (
        ("mode", "chatgpt", "mock"),
        ("provider_request_id", "req-a", "req-b"),
        ("diagnostic_provider_error_code", "rate_limit_exceeded", "insufficient_quota"),
        ("failure_kind", "timeout", "provider_rejected"),
    ):
        for order in permutations([{**received, key: left}, {**received, key: right}]):
            assert obs.receipt_state(obs.unique_rows(list(order))[0]) == "uncertain"
    for order in permutations(
        [
            {**received, "provider_request_id": "req-a"},
            {"id": "audit", "provider_input_audit": {"provider_request_id": "req-b"}},
        ]
    ):
        assert obs.receipt_state(obs.unique_rows(list(order))[0]) == "uncertain"
    assert received["provider_input_audit"]["request_body_compressed"]
    compiler = {"number": 1, "status": "completed", "provider_http_status": 200}
    for order in permutations(
        [{**compiler, "id": "compiler-a"}, {**compiler, "attempt_id": "compiler-b"}]
    ):
        duplicate_record = {
            "calls_used": 0,
            "steps": [],
            "reference_compilation": {"status": "fallback", "attempts": list(order)},
        }
        projected, missing = obs.attempts(duplicate_record)
        assert len(projected) == 1
        assert projected[0]["observability_conflict"]
        assert obs.receipt_state(projected[0]) == "uncertain"
        assert not obs.inventory_complete(duplicate_record, projected, missing)
    local = {"id": "local", "role": "investigator", "status": "completed"}
    metered = {**local, "token_usage_status": "reported", "token_usage": _usage(3, 2)}
    assert obs.receipt_state(local) == "uncertain"
    assert obs.receipt_state(metered) == "confirmed"
    assert obs.receipt_state(metered, simulated=True) == "simulated"
    assert obs.reported_usage(metered, simulated=True) is None
    assert obs.reported_usage({**metered, "mode": "mock"}) is None
    for status in ("preparing", "reserved"):
        assert obs.reported_usage({**metered, "attempt_status": status}) is None
    estimated = {**local, "attempt_status": "usage_estimated", "token_usage": _usage(3, 2)}
    assert obs.reported_usage(estimated) is None
    assert obs.reported_usage({**estimated, "token_usage_status": "reported"}) is not None
    assert obs.receipt_state({**metered, "id": "a", "attempt_id": "b"}) == "uncertain"
    contradictory = {
        **legacy,
        "provider_request_id": "a",
        "provider_input_audit": {**legacy["provider_input_audit"], "provider_request_id": "b"},
    }
    assert obs.receipt_state(contradictory) == "uncertain"
    for order in permutations(
        [
            {**metered, "id": "a", "attempt_id": "a"},
            {**metered, "id": "b", "attempt_id": "a"},
            {**metered, "id": "b", "attempt_id": "c"},
        ]
    ):
        rows = obs.unique_rows(list(order))
        assert len(rows) == 1 and rows[0]["observability_conflict"]
        assert obs.receipt_state(rows[0]) == "uncertain"
    assert obs.receipt_state({**metered, "attempt_status": "not_dispatched"}) == "not_dispatched"
    assert obs.receipt_state({**metered, "attempt_status": "preparing"}) == "uncertain"
    assert obs.receipt_state({**metered, "id": None}) == "uncertain"
    assert obs.receipt_state({**metered, "token_usage": _usage(-1, 2)}) == "uncertain"
    assert obs.receipt_state({**local, "provider_http_status": 429}) == "uncertain"
    assert obs.receipt_state({**local, "provider_http_status": 999}) == "uncertain"
    assert (
        obs.receipt_state(
            {**local, "provider_http_status": 429, "provider_response_channel": "http"}
        )
        == "confirmed"
    )
    assert obs.retry_origins(
        [
            {"id": "a", "cycle": 1, "role": "investigator", "resume_sequence": 0},
            {
                "id": "b",
                "cycle": 1,
                "role": "investigator",
                "resume_sequence": 0,
                "automatic_retry_of": "a",
            },
            {"id": "c", "cycle": 1, "role": "investigator", "resume_sequence": 3},
        ],
        "s",
    ) == {"automatic": 1, "operator": 1, "unknown": 0}
    ledger = {
        "hard_budget_ledger": {
            "calls": [
                {"call_id": "a", "status": "settled", "cost_bound_usd": 0.01},
                {"call_id": "b", "status": "unknown", "cost_bound_usd": 0.02},
                {"call_id": "c", "status": "reserved", "cost_bound_usd": 0.03},
                {"call_id": "d", "status": "rejected", "cost_bound_usd": 0.0},
            ]
        }
    }
    assert obs.budget_observation(ledger)["ledger_cost_bound_usd_by_status"] == {
        "settled": 0.01,
        "unknown": 0.02,
        "reserved": 0.03,
        "rejected": 0.0,
    }
    return record


if __name__ == "__main__":
    run()
    print("PASS session observability")
