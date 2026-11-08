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
# Each revision must use its own historical fixture helpers as well as its
# own production code. Mixing candidate tests with old backend APIs breaks
# before parity can examine scheduling behavior.
sys.path.insert(0, str(Path(__file__).resolve().parent))
sys.path.insert(0, str(code_root / "src"))
sys.path.insert(0, str(code_root / "tests"))

import httpx
import research_sessions as fixture

from sigma import research_sessions

try:
    from sigma import project_types
except ImportError:
    # The historical baseline predates Project Types.
    project_types = None


# Parity isolates scheduler behavior. The application intentionally enables
# references for new users, unlike the old revision, so pin both comparisons
# to the same historical reference preference baseline.
def parity_reference_defaults():
    if project_types is None:
        return {"common": {}}
    return {
        "common": {
            field: [ref["url"] for ref in refs]
            for field, refs in project_types.curated_common_references().items()
        }
    }


if project_types is not None:
    project_types._default_reference_preferences = parity_reference_defaults
from sigma.projects import ProjectError, create_strategy, set_strategy_enabled

UUID_RE = re.compile(
    r"\b[0-9a-f]{8}-[0-9a-f]{4}-[0-9a-f]{4}-[0-9a-f]{4}-[0-9a-f]{12}\b",
    re.IGNORECASE,
)
TIMESTAMP_RE = re.compile(r"20\d\d-\d\d-\d\dT\d\d:\d\d:\d\d(?:\.\d+)?(?:Z|\+00:00)?")
ROLE_ORDER = {"research_investigator": 0, "research_skeptic": 1}
MODE = sys.argv[3] if len(sys.argv) > 3 else "legacy-v1"
assert MODE in {"legacy-v1", "parallel-v1", "paired-v2", "paired-v2-resume"}, MODE


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
        paired = MODE.startswith("paired-v2")
        third = None
        if paired:
            third = create_strategy(
                path, "Disabled independent peer", "Never dispatch this excluded strategy."
            ).project.strategies[-1]
            set_strategy_enabled(str(path), third.id, False)
            limits = {
                **research_sessions.NEW_DEFAULT_LIMITS,
                "research_rounds": 2,
                "turns_per_round": 2,
                "model_calls": 8,
            }
            pair_slots, expected_calls = 4, 16
        else:
            limits = {**research_sessions.DEFAULT_LIMITS, "research_rounds": 3, "model_calls": 12}
            pair_slots, expected_calls = 3, 12
        limits = research_sessions.save_limits(str(path), limits)
        requests = []
        pause_requested = asyncio.Event()
        pause_once = False

        async def configuration_gate(*_args, **_kwargs):
            nonlocal pause_once
            if (
                MODE == "paired-v2-resume"
                and not pause_once
                and any(
                    len(row.get("artifacts", [])) >= 2 for row in research_sessions._all(str(path))
                )
            ):
                pause_once = True
                pause_requested.set()
                # A synthetic preflight pause; stop cancels the worker without
                # losing committed evidence or consuming provider capacity.
                await asyncio.Event().wait()
            return config

        first_investigator_active = False
        fast_skeptic_overlap = False
        parallel_skeptic_entered = asyncio.Event()

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
                    if MODE in {"parallel-v1", "paired-v2", "paired-v2-resume"}:
                        # Wait for the independent Skeptic rather than relying on
                        # a short wall-clock sleep under variable CI load.
                        # A genuinely serialized scheduler still times out.
                        await asyncio.wait_for(parallel_skeptic_entered.wait(), timeout=8)
                    else:
                        await asyncio.sleep(0.08)
                finally:
                    first_investigator_active = False
            elif title == second.title and cycle == 1 and role == "research_skeptic":
                fast_skeptic_overlap |= first_investigator_active
                parallel_skeptic_entered.set()
                await asyncio.sleep(0.002)
            else:
                await asyncio.sleep(0.002)

            if role == "research_investigator":
                answer = fixture.investigation(cycle)
                answer["claim"] = f"{title} finding at round {cycle}."
            else:
                answer = fixture.skeptic(
                    cycle,
                    "stop" if cycle == pair_slots else "revise",
                    "productive_conclusion" if cycle == pair_slots else "recoverable_objection",
                )
                answer["next_question"] = (
                    "Test peer evidence on the next round." if cycle < pair_slots else ""
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
            patch.object(
                research_sessions,
                "configuration",
                new=configuration_gate
                if MODE == "paired-v2-resume"
                else AsyncMock(return_value=config),
            ),
            patch.object(research_sessions, "execution_capabilities", return_value=[]),
            patch(
                "sigma.research_sessions.httpx.AsyncClient",
                side_effect=lambda **kw: fixture.REAL_CLIENT(
                    transport=httpx.MockTransport(handler), **kw
                ),
            ),
        ):
            if paired:
                assert third is not None
                try:
                    await research_sessions.start_session(
                        str(path),
                        first.id,
                        str(uuid4()),
                        view.project.id,
                        credential["identity"],
                        expected_limits=limits,
                        strategy_ids=[first.id, third.id],
                    )
                except ProjectError as exc:
                    assert "Disabled strategies" in str(exc), str(exc)
                else:
                    raise AssertionError("Disabled strategy entered a version-2 session")
            started = await research_sessions.start_session(
                str(path),
                first.id,
                str(uuid4()),
                view.project.id,
                credential["identity"],
                expected_limits=limits,
                strategy_ids=[first.id, second.id],
            )
            if MODE == "paired-v2-resume":
                await asyncio.wait_for(pause_requested.wait(), timeout=8)
                before_stop = research_sessions._read(str(path), started["id"])
                committed = {artifact["id"] for artifact in before_stop["artifacts"]}
                assert len(committed) >= 2
                stopped = await research_sessions.control_session(str(path), started["id"], "stop")
                assert stopped["status"] in {"stopped", "paused"}, stopped.get("message")
                assert committed <= {
                    artifact["id"]
                    for artifact in research_sessions._read(str(path), started["id"])["artifacts"]
                }
                resumed = await research_sessions.control_session(
                    str(path), started["id"], "resume"
                )
                assert resumed["status"] in {"queued", "running"}, resumed.get("message")
            final = await asyncio.wait_for(fixture.wait_for(path, started["id"]), timeout=20)

        assert final["status"] == "ended", final.get("message")
        assert final["calls_used"] == expected_calls, final.get("message")
        assert len(requests) == expected_calls
        assert len(final["artifacts"]) == expected_calls // 2
        stored = research_sessions._read(str(path), started["id"])
        assert stored["call_limit"] == expected_calls
        assert stored["cycle_limit"] == pair_slots
        assert len(stored["steps"]) == expected_calls
        for title in (first.title, second.title):
            observed = [(cycle, role) for name, cycle, role, _ in requests if name == title]
            assert observed == [
                (cycle, role)
                for cycle in range(1, pair_slots + 1)
                for role in ("research_investigator", "research_skeptic")
            ], (title, observed)
        if paired:
            assert stored["scheduler_version"] == 2
            assert stored["research_round_limit"] == 2
            assert stored["turns_per_round"] == 2
            assert len(stored["strategy_ids"]) == 2
            assert third is not None and third.id not in stored["strategy_ids"]
            for row in [*stored["steps"], *stored["artifacts"]]:
                slot = row.get("strategy_cycle", row.get("cycle"))
                assert 1 <= slot <= 4
                assert (row["research_round"], row["paired_turn_in_round"]) == (
                    (slot - 1) // 2 + 1,
                    (slot - 1) % 2 + 1,
                ), row
            assert all(
                row.get("strategy_id") != third.id
                for row in [*stored["steps"], *stored["artifacts"]]
            )
            assert any(
                context["other_strategy_evidence"]
                for _, _, _, payload in requests
                for context in [payload["input"]]
            ), "Paired scheduler lost cross-strategy evidence"
            assert any(
                context.get("peer_handoffs")
                for _, _, _, payload in requests
                for context in [payload["input"]]
            ), "Paired scheduler lost cross-strategy handoff"
            assert stored.get("termination_reason_code") in {
                "round_limit_reached",
                "protocol_complete",
                "productive_conclusion",
            }, stored.get("termination_reason_code")
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
            "scheduler_mode": MODE,
            "counts": {
                "calls": stored["calls_used"],
                "artifacts": len(stored["artifacts"]),
                "pair_slots": stored["cycle_limit"],
                "enabled_strategies": len(stored["strategy_ids"]),
                "resumed": MODE == "paired-v2-resume",
            },
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
        f"Wrote {sys.argv[2]} ({MODE}); provider requests: "
        f"{len(output['semantic']['provider_requests'])}; "
        f"fast-Skeptic/slow-Investigator overlap: {output['diagnostic_overlap']}"
    )
