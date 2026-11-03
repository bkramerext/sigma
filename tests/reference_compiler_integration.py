"""End-to-end, compiler-enabled research using a deterministic mock provider.

The normal legacy CI fixtures isolate research roles. This acceptance explicitly
enables the initial compilation step and verifies that a real session freezes
the source set, sends only the compact method guide to each role, and charges
the compiler without counting it as an Investigator/Skeptic turn.
"""

from __future__ import annotations

import asyncio
import json
import os
import sys
from pathlib import Path
from tempfile import TemporaryDirectory
from unittest.mock import AsyncMock, patch
from uuid import uuid4

import httpx

sys.path.insert(0, str(Path(__file__).resolve().parent))
import research_sessions as fixture

from sigma import research_sessions


async def verify_compilation(
    path: Path, *, multiple_strategies: bool = False, compiler_rejection: bool = False
) -> None:
    view, strategy, credential, config = await fixture.setup(path)
    limits = research_sessions.get_limits(str(path))
    limits.update(research_rounds=1, model_calls=4 if multiple_strategies else 2)
    research_sessions.save_limits(str(path), limits)
    strategy_ids = [strategy.id]
    if multiple_strategies:
        from sigma.projects import create_strategy

        extra = create_strategy(
            path, "Independent counterexample route", "Try a direct boundary counterexample."
        ).project.strategies[-1]
        strategy_ids.append(extra.id)
    # Explicit frozen references make this a deterministic compiler contract,
    # independent of the calling account's enabled Common guide preferences.
    source_catalog = {
        "version": "methodology-catalog-v2",
        "status": "selected",
        "mode": "mathematical",
        "branch": None,
        "selection_key": "fixture-mathematics-guides",
        "sources": [
            {
                "id": "proof",
                "tier": "discipline",
                "title": "Mathematics proof methods",
                "url": "https://example.org/proof",
                "notes": "Check induction, boundary cases, and counterexamples.",
                "project_type_id": "mathematical",
            },
            {
                "id": "irrelevant",
                "tier": "discipline",
                "title": "Unrelated writing style",
                "url": "https://example.org/irrelevant-writing",
                "notes": "Decorative text presentation without research methodology.",
                "project_type_id": "mathematical",
            },
        ],
    }
    calls: list[str] = []
    role_requests: list[str] = []
    selection: list[str] = []
    omitted_urls: list[str] = []

    async def provider(request: httpx.Request) -> httpx.Response:
        payload = json.loads(request.content)
        name = payload["text"]["format"]["name"]
        calls.append(name)
        if name == "research_reference_compilation":
            if compiler_rejection:
                return httpx.Response(400, json={"error": {"message": "Compiler unavailable"}})
            assert payload["store"] is False
            sources = json.loads(payload["input"])["uninspected_methodology_sources"]
            assert len(sources) >= 2
            selection[:] = [sources[0]["id"]]
            omitted_urls[:] = [source["url"] for source in sources[1:]]
            result = {
                "guidance": "Check the proposed recurrence against base cases and counterexamples.",
                "selected_source_ids": selection,
                "omitted_source_ids": [source["id"] for source in sources[1:]],
                "rationale": "Only the first methodological reference is relevant.",
            }
        elif name in {"research_investigator", "research_skeptic"}:
            body = json.dumps(payload)
            role_requests.append(body)
            result = (
                fixture.investigation(1)
                if name == "research_investigator"
                else fixture.skeptic(1, "stop", "no_progress")
            )
        else:
            raise AssertionError(f"Unexpected provider request: {name}")
        return httpx.Response(200, json=fixture.provider_response(result))

    with (
        patch.dict(os.environ, {"SIGMA_REFERENCE_COMPILATION_ENABLED": "true"}),
        patch.object(research_sessions, "auth_context", new=AsyncMock(return_value=credential)),
        patch.object(research_sessions, "configuration", new=AsyncMock(return_value=config)),
        patch.object(research_sessions, "select_method_sources", return_value=source_catalog),
        patch(
            "sigma.research_sessions.httpx.AsyncClient",
            side_effect=lambda **kwargs: fixture.REAL_CLIENT(
                transport=httpx.MockTransport(provider), **kwargs
            ),
        ),
    ):
        started = await research_sessions.start_session(
            str(path),
            strategy.id,
            str(uuid4()),
            view.project.id,
            credential["identity"],
            expected_limits=limits,
            strategy_ids=strategy_ids,
        )
        finished = await fixture.wait_for(path, started["id"])

    assert finished["status"] in {"ended", "completed"}, finished.get("message")
    assert calls.count("research_reference_compilation") == 1, calls
    assert calls.count("research_investigator") == len(strategy_ids), calls
    assert calls.count("research_skeptic") == len(strategy_ids), calls
    assert calls[0] == "research_reference_compilation", calls
    assert finished["calls_used"] == 2 * len(strategy_ids)
    assert len(finished["steps"]) == 2 * len(strategy_ids)
    assert {step["strategy_id"] for step in finished["steps"]} == set(strategy_ids)
    assert {step["role"] for step in finished["steps"]} == {"investigator", "skeptic"}
    saved = research_sessions._read(str(path), started["id"])
    stage = saved["reference_compilation"]
    assert stage["status"] == ("fallback" if compiler_rejection else "completed"), stage
    assert stage["source_sha256"] == saved["research_method_sources"]["sha256"]
    assert stage["status"] != "pending"
    if not compiler_rejection:
        assert stage["selected_source_ids"] == selection
        assert stage["omitted_source_ids"]
        assert stage["guidance_sha256"]
        assert stage["token_usage"]["input_tokens"] == 120
        assert stage["token_usage"]["output_tokens"] == 80
    assert saved["research_method_sources"]["sha256"] == stage["source_sha256"]
    assert len(saved["research_method_sources"]["sources"]) >= 2
    assert len(role_requests) == 2 * len(strategy_ids)
    assert len(saved["artifacts"]) == len(strategy_ids)
    for request in role_requests:
        if compiler_rejection:
            assert "Mathematics proof methods" in request
            assert "Check induction, boundary cases" in request
        else:
            assert stage["guidance"] in request
            assert all(url not in request for url in omitted_urls), omitted_urls
    if not compiler_rejection:
        assert saved["outcome"]["source_material"]["compilation"]["guidance"] == stage["guidance"]
        assert (
            sum(
                1
                for event in saved["events"]
                if event["kind"] == "references.compilation.completed"
            )
            == 1
        )
    ledger = saved.get("hard_budget_ledger")
    if isinstance(ledger, dict):
        assert len(ledger["calls"]) == 1 + 2 * len(strategy_ids), ledger["calls"]
        assert all(item["status"] in {"settled", "rejected"} for item in ledger["calls"])


def verify_compilation_preserves_first_turn_funding() -> None:
    """Optional reference work may not consume the first research turn's budget."""
    session = {
        "mode": "api_key",
        "cloud_sponsored": True,
        "strategy_runs": [{"strategy_id": "test", "status": "queued"}],
        "estimated_cost_usd": 0.0,
        "estimated_cost_reserved_usd": 0.0,
        "maximum_estimated_cost_usd": None,
    }

    def quote(_record, _context, _role, *, estimate=False):
        return 0.08 if estimate else 0.50

    with (
        patch.object(research_sessions, "_portfolio_context", return_value={}),
        patch.object(research_sessions, "_reserve_cost", side_effect=quote),
        patch.object(
            research_sessions.cloud_research,
            "snapshot",
            return_value={"remaining_usd": 0.12, "global_remaining_usd": 2.0},
        ) as funding,
    ):
        # The compiler itself could be funded for $0.06, but an Investigator
        # would then be denied because only $0.06 would remain.
        assert not research_sessions._optional_reference_compilation_headroom(session, 0.06, 0.12)
        funding.return_value = {"remaining_usd": 0.30, "global_remaining_usd": 0.55}
        # User allowance is sufficient, but maximum global model liability
        # would crowd out the next Investigator reservation.
        assert not research_sessions._optional_reference_compilation_headroom(session, 0.06, 0.12)
        funding.return_value = {"remaining_usd": 0.30, "global_remaining_usd": 1.0}
        assert research_sessions._optional_reference_compilation_headroom(session, 0.06, 0.12)
    api = {**session, "cloud_sponsored": False, "maximum_estimated_cost_usd": 0.55}
    with (
        patch.object(research_sessions, "_portfolio_context", return_value={}),
        patch.object(research_sessions, "_reserve_cost", side_effect=quote),
    ):
        # API-key sessions must retain the full provider liability estimate.
        assert not research_sessions._optional_reference_compilation_headroom(api, 0.06, 0.12)
        api["maximum_estimated_cost_usd"] = 1.00
        assert research_sessions._optional_reference_compilation_headroom(api, 0.06, 0.12)


def verify_hard_budget_compiler_does_not_steal_first_turn() -> None:
    """Compiler preflight must account for full output cost and call slots."""
    from sigma.research_budget import new_ledger

    record = {
        "mode": "api_key",
        "cloud_sponsored": False,
        "model": "gpt-6.1-sol",
        "strategy_runs": [{"strategy_id": "test", "status": "queued"}],
        "maximum_estimated_cost_usd": None,
    }
    ledger = new_ledger(
        call_limit=2,
        input_token_limit=100_000,
        output_tokens_per_call=4000,
        cost_limit_usd=1.33,
        input_price_per_million=2.5,
        output_price_per_million=10.0,
    )
    record["hard_budget_ledger"] = ledger
    with (
        patch.object(research_sessions, "_portfolio_context", return_value={}),
        patch.object(research_sessions, "_role_request_payload", return_value={"input": "test"}),
        patch.object(research_sessions, "_reserve_cost", return_value=0.1),
    ):
        # One Investigator fits, but a 4K compiler call would exhaust the
        # cost needed for the Investigator's mandatory 128K ceiling.
        assert not research_sessions._optional_reference_compilation_headroom(
            record,
            0.06,
            0.12,
            compiler_request_body=b"x" * 512,
            compiler_output_bound=4000,
        )
        assert ledger["calls"] == []
        ledger["cost_limit_usd"] = 2.0
        assert research_sessions._optional_reference_compilation_headroom(
            record,
            0.06,
            0.12,
            compiler_request_body=b"x" * 512,
            compiler_output_bound=4000,
        )
        ledger["call_limit"] = 1
        assert not research_sessions._optional_reference_compilation_headroom(
            record,
            0.06,
            0.12,
            compiler_request_body=b"x" * 512,
            compiler_output_bound=4000,
        )
        assert ledger["calls"] == []


async def main() -> None:
    verify_compilation_preserves_first_turn_funding()
    verify_hard_budget_compiler_does_not_steal_first_turn()
    with TemporaryDirectory() as temporary:
        root = Path(temporary)
        await verify_compilation(root / "compiled.sigma")
        await verify_compilation(root / "multi.sigma", multiple_strategies=True)
        await verify_compilation(root / "fallback.sigma", compiler_rejection=True)
    print("PASS: durable reference compilation, multi-strategy reuse, fallback and metering")


if __name__ == "__main__":
    asyncio.run(main())
