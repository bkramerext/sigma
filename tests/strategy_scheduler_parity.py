"""Cross-revision research-semantics snapshot, used against real main and PR code.

All responses are synthetic. This runner is intentionally outside the ordinary
unit-test suite because CI must execute it with two *different* source trees.
"""

from __future__ import annotations

import asyncio
import json
import re
import sys
from pathlib import Path
from tempfile import TemporaryDirectory
from unittest.mock import AsyncMock, patch
from uuid import uuid4

# Usage: python tests/strategy_scheduler_parity.py CODE_ROOT OUTPUT.json
code_root = Path(sys.argv[1]).resolve()
sys.path.insert(0, str(code_root / "src"))
sys.path.insert(0, str(Path(__file__).resolve().parent))

import httpx
import research_sessions as fixture

from sigma import research_sessions
from sigma.projects import create_strategy

UUID_RE = re.compile(
    r"\b[0-9a-f]{8}-[0-9a-f]{4}-[0-9a-f]{4}-[0-9a-f]{4}-[0-9a-f]{12}\b",
    re.IGNORECASE,
)
TIMESTAMP_RE = re.compile(r"20\d\d-\d\d-\d\dT\d\d:\d\d:\d\d(?:\.\d+)?(?:Z|\+00:00)?")
ROLE_ORDER = {"research_investigator": 0, "research_skeptic": 1}


def canonicalize(value, names: dict[str, str]):
    # Name all known IDs by their durable referents. Other opaque UUIDs are
    # alpha-renamed in deterministic *sorted semantic input* order below.
    unknown: dict[str, str] = {}
    obligation_names: dict[str, str] = {}
    short_obligation_names: dict[str, str] = {}

    def index_obligation_ids(obj):
        # Stable obligation source text and references must be preserved. Its
        # current 64-character ID also hashes per-execution ephemeral step IDs,
        # so alpha-rename that opaque ID only, including every later reference.
        if isinstance(obj, dict):
            candidate = obj.get("obligation_id")
            if isinstance(candidate, str) and re.fullmatch(r"[0-9a-f]{64}", candidate):
                obligation_names.setdefault(
                    candidate, f"<obligation-id-{len(obligation_names) + 1}>"
                )
            # Continuity-v2 assigns compact oN IDs when an obligation is
            # first saved. Parallel branches may commit in a different order;
            # alpha-rename the *identifier* by its first canonical occurrence,
            # retaining all of its subsequent references and substantive text.
            elif isinstance(candidate, str) and re.fullmatch(r"o[1-9][0-9]*", candidate):
                short_obligation_names.setdefault(
                    candidate, f"<short-obligation-id-{len(short_obligation_names) + 1}>"
                )
            for key in sorted(obj):
                index_obligation_ids(obj[key])
        elif isinstance(obj, list):
            for item in obj:
                index_obligation_ids(item)

    index_obligation_ids(value)
    names = {**names, **obligation_names}

    def walk(obj):
        if isinstance(obj, dict):
            return {key: walk(item) for key, item in sorted(obj.items())}
        if isinstance(obj, list):
            return [walk(item) for item in obj]
        if not isinstance(obj, str):
            return obj
        # Exact-value replacement avoids changing ordinary prose containing
        # an oN substring; references to the same ID remain tied together.
        if obj in short_obligation_names:
            return short_obligation_names[obj]
        for identifier, label in sorted(names.items(), key=lambda row: -len(row[0])):
            obj = obj.replace(identifier, label)
        obj = TIMESTAMP_RE.sub("<timestamp>", obj)
        return UUID_RE.sub(
            lambda match: unknown.setdefault(match.group(0), f"<opaque-id-{len(unknown) + 1}>"),
            obj,
        )

    return walk(value)


async def snapshot():
    with TemporaryDirectory(prefix="sigma-parity-") as directory:
        path = Path(directory) / "research.sigma"
        view, first, credential, config = await fixture.setup(path)
        second = create_strategy(
            path, "Independent peer", "Derive a complementary invariant."
        ).project.strategies[-1]
        limits = {**research_sessions.DEFAULT_LIMITS, "research_rounds": 3, "model_calls": 12}
        research_sessions.save_limits(str(path), limits)
        requests = []
        first_investigator_active = False
        fast_skeptic_overlap = False

        async def handler(request):
            nonlocal first_investigator_active, fast_skeptic_overlap
            payload = json.loads(request.content)
            context = json.loads(payload["input"])
            role = payload["text"]["format"]["name"]
            title = context["strategy"]["title"]
            cycle = context["cycle"]
            assert role in ROLE_ORDER
            requests.append((title, cycle, role, {**payload, "input": context}))
            if title == first.title and cycle == 1 and role == "research_investigator":
                first_investigator_active = True
                try:
                    await asyncio.sleep(0.08)
                finally:
                    first_investigator_active = False
            elif title == second.title and cycle == 1 and role == "research_skeptic":
                fast_skeptic_overlap |= first_investigator_active
                await asyncio.sleep(0.002)
            else:
                await asyncio.sleep(0.002)

            if role == "research_investigator":
                answer = fixture.investigation(cycle)
                answer["claim"] = f"{title} finding at round {cycle}."
            else:
                answer = fixture.skeptic(
                    cycle,
                    "stop" if cycle == 3 else "revise",
                    "productive_conclusion" if cycle == 3 else "recoverable_objection",
                )
                answer["next_question"] = (
                    "Test peer evidence on the next round." if cycle < 3 else ""
                )
                if title == first.title and cycle == 2:
                    peers = context["other_strategy_evidence"]
                    assert peers, "Cross-strategy evidence was lost."
                    answer["cross_strategy_relations"] = [
                        {
                            "strategy_id": second.id,
                            "artifact_id": peers[-1]["artifact_id"],
                            "relation": "contradicts",
                            "rationale": "Compare the independent invariant's assumptions before transfer.",
                        }
                    ]
                if context.get("peer_handoffs"):
                    answer["peer_handoff_reviews"] = [
                        {
                            "handoff_id": item["handoff_id"],
                            "disposition": "reject",
                            "assumption_comparison": "Independent assumptions not yet established equivalent.",
                            "rationale": "Do not transfer without validating the domain.",
                        }
                        for item in context["peer_handoffs"]
                    ]
            return httpx.Response(200, json=fixture.provider_response(answer))

        with (
            patch.object(research_sessions, "auth_context", new=AsyncMock(return_value=credential)),
            patch.object(research_sessions, "configuration", new=AsyncMock(return_value=config)),
            patch.object(research_sessions, "execution_capabilities", return_value=[]),
            patch(
                "sigma.research_sessions.httpx.AsyncClient",
                side_effect=lambda **kw: fixture.REAL_CLIENT(
                    transport=httpx.MockTransport(handler), **kw
                ),
            ),
        ):
            started = await research_sessions.start_session(
                str(path),
                first.id,
                str(uuid4()),
                view.project.id,
                credential["identity"],
                expected_limits=limits,
                strategy_ids=[first.id, second.id],
            )
            final = await asyncio.wait_for(fixture.wait_for(path, started["id"]), timeout=12)

        assert final["status"] == "ended", final.get("message")
        assert final["calls_used"] == 12, final.get("message")
        assert len(requests) == 12
        assert len(final["artifacts"]) == 6
        titles = {first.id: first.title, second.id: second.title}
        names = {
            first.id: "<strategy-1>",
            second.id: "<strategy-2>",
            view.project.id: "<project>",
            started["id"]: "<session>",
            str(path): "<project-path>",
        }
        for item in final["artifacts"]:
            names[item["id"]] = f"<artifact-{titles[item['strategy_id']]}-{item['strategy_cycle']}>"
        for item in final["steps"]:
            names[item["id"]] = (
                f"<step-{titles[item['strategy_id']]}-{item['cycle']}-{item['role']}>"
            )
        # Compare the actual serialized provider inputs, including instructions,
        # prompt context, obligations, peer evidence, and schema. Sort only the
        # *arrival order*, not arrays inside a request.
        ordered_requests = sorted(
            requests, key=lambda item: (item[0], item[1], ROLE_ORDER[item[2]])
        )
        request_data = [
            {"title": title, "cycle": cycle, "role": role, "payload": payload}
            for title, cycle, role, payload in ordered_requests
        ]
        artifacts = [
            {
                "strategy": titles[item["strategy_id"]],
                "round": item["strategy_cycle"],
                "claim": item["claim_or_question"],
                "method": item["method"],
                "objections": item["objections"],
                "decision": item["coordinator_decision"],
                "next_question": item["next_question"],
                "objective_review": item["objective_review"],
                "peer_handoffs": item.get("peer_handoffs_prompted", []),
            }
            for item in sorted(
                final["artifacts"],
                key=lambda item: (titles[item["strategy_id"]], item["strategy_cycle"]),
            )
        ]
        branches = [
            {
                "strategy": titles[item["strategy_id"]],
                "status": item["status"],
                "round": item["cycle"],
                "calls": item["calls_used"],
                "decision": item.get("last_decision"),
                "next_question": item.get("current_question"),
            }
            for item in final["strategy_runs"]
        ]
        return {
            "semantic": canonicalize(
                {
                    "provider_requests": request_data,
                    "artifacts": artifacts,
                    "branches": branches,
                    "assessment": final["outcome"]["assessment"],
                },
                names,
            ),
            "diagnostic_overlap": fast_skeptic_overlap,
        }


if __name__ == "__main__":
    # Renaming is valid only for consistent IDs, never for changed substance or
    # a reference silently pointing at a different obligation.
    baseline = {
        "obligations": [
            {"obligation_id": "o2", "claim": "First proof obligation"},
            {"obligation_id": "o1", "claim": "Second proof obligation"},
        ],
        "referenced_obligation": "o2",
    }
    reordered = {
        "obligations": [
            {"obligation_id": "o1", "claim": "First proof obligation"},
            {"obligation_id": "o2", "claim": "Second proof obligation"},
        ],
        "referenced_obligation": "o1",
    }
    assert canonicalize(baseline, {}) == canonicalize(reordered, {})
    assert canonicalize(baseline, {}) != canonicalize(
        {**reordered, "referenced_obligation": "o2"}, {}
    )
    changed_claim = json.loads(json.dumps(reordered))
    changed_claim["obligations"][0]["claim"] = "Changed proof obligation"
    assert canonicalize(baseline, {}) != canonicalize(changed_claim, {})
    output = asyncio.run(snapshot())
    Path(sys.argv[2]).write_text(json.dumps(output, sort_keys=True, indent=2) + "\n")
    print(
        f"Wrote {sys.argv[2]}; provider requests: "
        f"{len(output['semantic']['provider_requests'])}; "
        f"fast-Skeptic/slow-Investigator overlap: {output['diagnostic_overlap']}"
    )
