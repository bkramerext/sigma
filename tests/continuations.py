"""Approval, negative evidence, frozen dispatch, stale/oversize refusal. Offline."""

import asyncio
import json
import os
from copy import deepcopy
from pathlib import Path
from tempfile import TemporaryDirectory
from unittest.mock import AsyncMock, patch

import httpx
import research_sessions as helpers

from sigma import continuations as c
from sigma import research_sessions as engine
from sigma.projects import ProjectError, edit_strategy
from sigma.research_sessions import _agent_context, read_session_snapshot
from sigma.samples import open_sample_project


def rejected(action, message):
    try:
        action()
    except ProjectError as exc:
        assert message in str(exc), str(exc)
    else:
        raise AssertionError("Expected explicit refusal")


async def review_contract(context):
    credential = {"mode": "api_key", "identity": "fixture-account", "token": "fixture-token"}
    record = {
        "model": "gpt-6.1-sol",
        "reasoning_effort": "high",
        "mode": "api_key",
        "identity_hash": engine._digest(credential["identity"]),
        "output_token_limit": 12000,
    }
    reviews = [
        {
            "artifact_id": row["artifact_id"],
            "uptake": "considered",
            "treatment": "negative_constraint" if row["mandatory"] else "unverified_input",
            "rationale": "Retain exact saved evidence with its original local scope.",
            "next_test": "",
        }
        for row in context["approved_continuation"]["sources"]
    ]
    variants = [
        ([], False),
        (reviews, True),
        (reviews + [reviews[0]], False),
        ([{**reviews[0], "uptake": "deferred"}] + reviews[1:], False),
        ([{**reviews[0], "treatment": "unverified_input"}] + reviews[1:], False),
        ([{**reviews[0], "uptake": "changed_plan", "next_test": ""}] + reviews[1:], False),
        (
            [{**reviews[0], "artifact_id": "00000000-0000-0000-0000-000000000000"}] + reviews[1:],
            False,
        ),
    ]
    real_client = httpx.AsyncClient
    for value, expected in variants:
        output = helpers.investigation(1)
        output["continuation_reviews"] = value

        async def handler(request, response_output=output):
            return httpx.Response(200, json=helpers.provider_response(response_output))

        with (
            patch.object(engine, "auth_context", new=AsyncMock(return_value=credential)),
            patch.object(
                engine.httpx,
                "AsyncClient",
                side_effect=lambda **kw: real_client(transport=httpx.MockTransport(handler), **kw),
            ),
        ):
            try:
                await engine._call(record, "investigator", context)
            except ProjectError:
                assert not expected
            else:
                assert expected


def main():
    with TemporaryDirectory() as tmp, patch.dict(os.environ, {"SIGMA_PROJECTS_ROOT": tmp}):
        view = open_sample_project("nonconsecutive-subset-sums")
        path = view.path
        parent = view.project.strategies[0]
        records, missing = read_session_snapshot(path)
        assert not missing and len(records) == 5
        original = {s["id"]: deepcopy(s) for s in records}
        preview = c.proposal(path, parent.id)
        mandatory = [s["artifact_id"] for s in preview["sources"] if s["mandatory"]]
        assert "1cc6ec50-87c0-46f4-b1dd-a82857d74f9e" in mandatory
        gap = "516c2288-3458-40b2-9e02-87a918c35a3a"
        approval = c.Approval(
            parent_strategy_id=parent.id,
            title="Exact boundary continuation",
            question="Check the exact three-phase boundary vectors, leaving asymptotics open.",
            source_artifact_ids=mandatory + [gap],
            preview_digest=preview["preview_digest"],
        )
        rejected(
            lambda: c.approve(path, approval.model_copy(update={"source_artifact_ids": [gap]})),
            "mandatory",
        )
        rejected(
            lambda: c.approve(
                path,
                approval.model_copy(
                    update={
                        "source_artifact_ids": mandatory + ["00000000-0000-0000-0000-000000000000"]
                    }
                ),
            ),
            "available",
        )
        with patch.object(c, "MAX_PACKET_BYTES", 100):
            rejected(lambda: c.approve(path, approval), "64 KB")
        created = c.approve(path, approval)
        new = created.project.strategies[-1]
        assert new.id != parent.id and created.project.strategies[0] == parent
        packets = c.approved_packets(path, [new.id])
        packet = packets[new.id]
        (Path(path) / "research-sessions" / "sequence.json").write_text(
            json.dumps({"project_id": view.project.id, "next": 6})
        )
        assert packet["question"] == new.approach
        # Real context builder receives cross-strategy originals and exact IDs.
        context = _agent_context(
            {
                "id": "context-test",
                "project_path": path,
                "project_id": view.project.id,
                "strategy_id": new.id,
                "strategy_title": new.title,
                "strategy_text": new.approach,
                "problem": view.project.problem,
                "current_question": new.approach,
                "artifacts": [],
                "steps": [],
                "prior_session_findings": [],
                "prior_session_failures": [],
                "approved_continuations": packets,
            },
            "investigator",
            1,
        )
        assert context["approved_continuation"] == packet
        assert set(context["prior_session_artifact_ids"]) == set(mandatory + [gap])
        assert len({s["source"]["strategy_id"] for s in packet["sources"]}) == 2
        asyncio.run(review_contract(context))
        fresh_records, _ = read_session_snapshot(path)
        assert {s["id"]: s for s in fresh_records} == original
        file = Path(path) / "continuations" / f"{new.id}.json"
        saved = file.read_bytes()
        file.write_text("{}")
        rejected(lambda: c.approved_packets(path), "invalid")
        file.write_bytes(saved)
        edit_strategy(
            path, new.id, new.title, "Different question after approval; this must fail closed."
        )
        rejected(lambda: c.approved_packets(path, [new.id]), "edited")
        # Stale preview after a new strategy changes the project portfolio? Parent
        # alone unchanged is okay; saved session changes must invalidate preview.
        changed = deepcopy(records[0])
        changed["artifacts"][0]["method"] += " Updated source."
        from sigma.research_sessions import _save

        _save(path, changed)
        rejected(lambda: c.approve(path, approval), "changed")
    print(
        "PASS continuation approval, mandatory refutation, foreign IDs, overflow, frozen cross-strategy dispatch, archive preservation, corrupt/edited approval and stale preview"
    )


if __name__ == "__main__":
    main()
