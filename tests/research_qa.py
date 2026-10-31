"""Deterministic checks for saved-research Q/A and citation integrity."""

from __future__ import annotations

import asyncio
import json
from pathlib import Path
from tempfile import TemporaryDirectory
from unittest.mock import patch

from sigma import api, research_qa
from sigma.project_bundle import import_bundle
from sigma.projects import (
    ProjectError,
    export_complete_project,
    initialize_project,
    inspect_project,
)


def main() -> None:
    with TemporaryDirectory() as temporary:
        path = Path(temporary) / "qa.sigma"
        before = initialize_project(path, "Q/A fixture", "Explain the saved research results")
        s1 = "11111111-1111-4111-8111-111111111111"
        s2 = "22222222-2222-4222-8222-222222222222"
        package = {
            "project_id": before.project.id,
            "sources": [
                {
                    "id": f"session:{s1}",
                    "kind": "session",
                    "data": {
                        "session_number": 1,
                        "status": "completed",
                        "outcome": {
                            "label": "promising",
                            "summary": "Initial evidence favored the approach.",
                        },
                    },
                },
                {
                    "id": f"artifact:{s1}:aaaaaaaa-aaaa-4aaa-8aaa-aaaaaaaaaaaa",
                    "kind": "artifact",
                    "data": {
                        "session_number": 1,
                        "text": "Initial result; further tests are needed.",
                    },
                },
                {
                    "id": f"session:{s2}",
                    "kind": "session",
                    "data": {
                        "session_number": 2,
                        "status": "completed",
                        "outcome": {
                            "label": "uncertain",
                            "summary": "A later skeptic found contradictory limitations.",
                        },
                    },
                },
            ],
        }
        credential = {"identity": "chatgpt:fixture", "mode": "chatgpt", "token": "fixture"}
        config = {"available": True, "model": "fixture-model", "reasoning_effort": "medium"}
        live_export = {
            "research_sessions": [
                {
                    "id": s1,
                    "session_number": 1,
                    "artifacts": [{"id": "aaaaaaaa-aaaa-4aaa-8aaa-aaaaaaaaaaaa"}],
                },
                {"id": s2, "session_number": 2, "artifacts": []},
            ]
        }
        calls = 0
        forged = False
        unsupported = False

        async def structured(_input, *_args, **kwargs):
            nonlocal calls
            calls += 1
            if forged:
                return research_qa.AnswerDraft(
                    answer="A forged answer.",
                    source_refs=["session:99999999-9999-4999-8999-999999999999"],
                ), "{}"
            if unsupported:
                return research_qa.AnswerDraft(
                    answer="The saved sessions do not answer that question; the available evidence is inconclusive.",
                    source_refs=[f"session:{s2}"],
                ), "{}"
            return research_qa.AnswerDraft(
                answer="<script>alert(1)</script> The initial result looked promising, but a later skeptic found limitations, so the outcome remains uncertain.",
                source_refs=[f"session:{s1}", f"session:{s2}"],
            ), "{}"

        with (
            patch.object(
                research_qa, "auth_context", new=lambda: asyncio.sleep(0, result=credential)
            ),
            patch.object(
                research_qa, "configuration", new=lambda **_kwargs: asyncio.sleep(0, result=config)
            ),
            patch.object(research_qa.papers, "_snapshot", return_value=(package, "a" * 64)),
            patch.object(research_qa.papers, "_provider_structured", new=structured),
            patch.object(api, "export_project_view", return_value=live_export),
        ):
            first = asyncio.run(
                research_qa.answer(
                    str(path),
                    "What did the research find?",
                    before.project.id,
                    credential["identity"],
                    "a" * 32,
                )
            )
            repeated = asyncio.run(
                research_qa.answer(
                    str(path),
                    "What did the research find?",
                    before.project.id,
                    credential["identity"],
                    "a" * 32,
                )
            )
            assert first["qa_id"] == repeated["qa_id"] and calls == 1
            assert [row["session_number"] for row in first["sources"]] == [1, 2]
            assert len(research_qa.list_answers(str(path))) == 1
            assert "<script>" not in research_qa.standalone_html(str(path), first["qa_id"])
            assert "&lt;script&gt;" in research_qa.standalone_html(str(path), first["qa_id"])
            assert f"reveal_session={s1}" in research_qa.standalone_html(str(path), first["qa_id"])
            portable = Path(temporary) / "portable.json"
            import_bundle(json.loads(export_complete_project(path)), portable)
            assert research_qa.list_answers(str(portable))[0]["qa_id"] == first["qa_id"]
            unsupported = True
            inconclusive = asyncio.run(
                research_qa.answer(
                    str(path),
                    "Can this saved approach treat every unsaved condition?",
                    before.project.id,
                    credential["identity"],
                    "c" * 32,
                )
            )
            assert "do not answer" in inconclusive["answer"]
            assert inconclusive["sources"][0]["session_number"] == 2
            assert calls == 2
            with patch.object(
                api,
                "export_project_view",
                return_value={
                    "research_sessions": [{"id": s2, "session_number": 2, "artifacts": []}]
                },
            ):
                reopened = research_qa.get_answer(str(path), first["qa_id"])
                assert reopened["sources"][0]["source_id"] == f"session:{s1}"
                assert not reopened["sources"][0]["navigation_available"]
            forged = True
            try:
                asyncio.run(
                    research_qa.answer(
                        str(path),
                        "<script>alert(1)</script>",
                        before.project.id,
                        credential["identity"],
                        "b" * 32,
                    )
                )
            except ProjectError as exc:
                assert "citation" in str(exc)
            else:
                raise AssertionError("Forged citation must be rejected")
            assert len(research_qa.list_answers(str(path))) == 2
            assert inspect_project(path).project == before.project, (
                "Q/A must not mutate research or project settings"
            )
            research_qa.delete_answer(str(path), first["qa_id"])
            assert [row["qa_id"] for row in research_qa.list_answers(str(path))] == [
                inconclusive["qa_id"]
            ]
        print(
            "Research Q/A: validated citations, idempotent retry, safe browser rendering, durable save/remove, and no project mutation passed."
        )


if __name__ == "__main__":
    main()
