"""Crucible P0: versioned 54-call scheduling and strict supplied evidence references.

Only deterministic local httpx.MockTransport responses are used; no paid provider.
"""

from __future__ import annotations

import asyncio
import json
import os
import sys
from collections import Counter
from pathlib import Path
from tempfile import TemporaryDirectory
from unittest.mock import AsyncMock, patch
from uuid import uuid4

import httpx

sys.path.insert(0, str(Path(__file__).resolve().parent))
import research_sessions as fixture

from sigma import api, global_research_settings, research_sessions, session_log
from sigma.projects import ProjectError, create_strategy
from sigma.research_context_budget import restrict_obligation_citations_to_supplied_context


async def verify_versioned_settings_and_peer_evidence(path: Path) -> None:
    view, _, _, _ = await fixture.setup(path)
    legacy = {
        **research_sessions.DEFAULT_LIMITS,
        "research_rounds": 3,
        "model_calls": 18,
    }
    research_sessions.save_limits(str(path), legacy)
    before = global_research_settings._path().read_bytes()
    assert research_sessions.get_limits(str(path)) == legacy
    assert research_sessions._session_start_limits(legacy, None) == legacy
    projected = api.research_limits_view(str(path))
    assert (
        projected["scheduler_version"],
        projected["research_rounds"],
        projected["turns_per_round"],
    ) == (2, 3, 3)
    assert projected["model_calls"] == 18
    assert global_research_settings._path().read_bytes() == before
    started_limits = research_sessions._session_start_limits(legacy, projected)
    assert started_limits["scheduler_version"] == 2
    assert research_sessions._paired_call_limit(started_limits, 3) == 54
    try:
        research_sessions._session_start_limits(legacy, {**projected, "turns_per_round": 4})
    except ProjectError as exc:
        assert "changed since confirmation" in str(exc)
    else:
        raise AssertionError("Stale start confirmation was accepted")

    request = api.ResearchLimitsRequest(
        path=str(path),
        scheduler_version=2,
        turns_per_round=3,
        research_rounds=3,
        model_calls=18,
        session_duration_minutes=60,
        output_tokens_per_call=4000,
        maximum_estimated_cost_usd=None,
        maximum_input_tokens_per_session=None,
        max_concurrent_sessions="1",
    )
    response = api.research_limits_update(request)
    assert response["scheduler_version"] == 2
    stored = json.loads(global_research_settings._path().read_text())["limits"]
    assert (stored["scheduler_version"], stored["turns_per_round"], stored["model_calls"]) == (
        2,
        3,
        18,
    )
    assert research_sessions.get_limits(str(path))["scheduler_version"] == 2

    context = {
        "scheduler_version": 2,
        "context_artifact_ids": ["own-artifact"],
        "prior_session_artifact_ids": ["saved-prior"],
        "other_strategy_evidence": [
            {"strategy_id": "peer-strategy", "artifact_id": "visible-peer"},
            {
                "strategy_id": "peer-strategy",
                "artifact_id": "pointer-peer",
                "evidence_availability": "pointer_only_original_not_supplied",
            },
        ],
        "investigator_step_id": "current-step",
        "obligation_ledger": [
            {
                "obligation_id": "obligation-1",
                "source_artifact_ids": ["own-artifact", "visible-peer", "pointer-peer", "lost"],
                "basis_artifact_ids": ["visible-peer", "pointer-peer"],
                "pointer_source_artifact_ids": ["pointer-peer"],
            }
        ],
    }
    restrict_obligation_citations_to_supplied_context(context)
    obligation = context["obligation_ledger"][0]
    assert obligation["source_artifact_ids"] == ["own-artifact", "visible-peer"]
    assert obligation["basis_artifact_ids"] == ["visible-peer"]
    assert obligation["unsupplied_source_artifact_count"] == 2
    assert obligation["withheld_pointer_source_count"] == 1
    good = {
        "obligation_id": "obligation-1",
        "basis_artifact_ids": ["visible-peer", "own-artifact", "saved-prior"],
        "basis_step_ids": ["current-step"],
    }
    research_sessions._validate_obligation_review_basis(context, good)
    for bad in ("pointer-peer", "fabricated-artifact"):
        try:
            research_sessions._validate_obligation_review_basis(
                context, {**good, "basis_artifact_ids": [bad]}
            )
        except ProjectError as exc:
            assert "obligation_reviews" in str(exc) and bad in str(exc)
        else:
            raise AssertionError(f"Unavailable evidence {bad} was accepted")
    try:
        research_sessions._validate_obligation_review_basis(
            context, {**good, "basis_step_ids": ["invented-step"]}
        )
    except ProjectError as exc:
        assert "invented-step" in str(exc)
    else:
        raise AssertionError("Fabricated Investigator step was accepted")
    assert view.project.id


async def verify_complete_54_call_session(path: Path) -> None:
    view, strategy, credential, config = await fixture.setup(path)
    second = create_strategy(
        path, "Second independent route", "Review a separate case."
    ).project.strategies[-1]
    third = create_strategy(
        path, "Third independent route", "Check a competing explanation."
    ).project.strategies[-1]
    strategy_ids = [strategy.id, second.id, third.id]
    limits = research_sessions._validate_limits(dict(research_sessions.NEW_DEFAULT_LIMITS))
    research_sessions.save_limits(str(path), limits)
    expected = api.research_limits_view(str(path))
    roles: list[str] = []

    async def handler(request: httpx.Request) -> httpx.Response:
        payload = json.loads(request.content)
        role = payload["text"]["format"]["name"]
        assert role in {"research_investigator", "research_skeptic"}, role
        context = json.loads(payload["input"])
        cycle = context["cycle"]
        assert 1 <= cycle <= 9
        assert context["scheduler_note"]
        roles.append(role)
        data = (
            fixture.investigation(cycle)
            if role == "research_investigator"
            else fixture.skeptic(cycle)
        )
        return httpx.Response(200, json=fixture.provider_response(data))

    with (
        patch.dict(os.environ, {"SIGMA_REFERENCE_COMPILATION_ENABLED": "false"}),
        patch.object(research_sessions, "auth_context", new=AsyncMock(return_value=credential)),
        patch.object(research_sessions, "configuration", new=AsyncMock(return_value=config)),
        patch(
            "sigma.research_sessions.httpx.AsyncClient",
            side_effect=lambda **kwargs: fixture.REAL_CLIENT(
                transport=httpx.MockTransport(handler), **kwargs
            ),
        ),
    ):
        started = await research_sessions.start_session(
            str(path),
            strategy.id,
            str(uuid4()),
            view.project.id,
            credential["identity"],
            expected_limits=expected,
            strategy_ids=strategy_ids,
        )
        assert started["scheduler_version"] == 2
        assert started["call_limit"] == 54
        assert started["cycle_limit"] == 9
        assert started["research_round_limit"] == 3
        assert started["turns_per_round"] == 3
        saved = research_sessions._read(str(path), started["id"])
        assert saved["scheduler_version"] == 2 and saved["call_limit"] == 54
        completed = await fixture.wait_for(path, started["id"], timeout_seconds=20)

    assert completed["calls_used"] == 54, (
        completed["status"],
        completed.get("message"),
        completed.get("termination_reason_code"),
        Counter(roles),
    )
    assert completed["call_limit"] == 54
    assert completed["scheduler_version"] == 2
    assert completed["termination_reason_code"] == "protocol_complete"
    assert len(completed["artifacts"]) == 27
    assert Counter(roles) == {"research_investigator": 27, "research_skeptic": 27}
    assert all(
        sum(
            1
            for step in completed["steps"]
            if step["strategy_id"] == sid and step["status"] == "completed"
        )
        == 18
        for sid in strategy_ids
    )
    assert all(
        {(item["role"], item["cycle"]) for item in completed["steps"] if item["strategy_id"] == sid}
        == {(role, cycle) for cycle in range(1, 10) for role in ("investigator", "skeptic")}
        for sid in strategy_ids
    )


async def main() -> None:
    with TemporaryDirectory() as directory:
        root = Path(directory)
        await verify_versioned_settings_and_peer_evidence(root / "legacy.sigma")
        await verify_complete_54_call_session(root / "v2.sigma")
        # Session diagnostics run on daemon writer threads. Drain queued writes
        # before TemporaryDirectory removes the project and its log root.
        session_log.flush()
    print(
        "PASS Crucible versioned settings, 54 provider-free calls, strict peer evidence provenance"
    )


if __name__ == "__main__":
    asyncio.run(main())
