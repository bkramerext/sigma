"""Deterministic checks for saved-research Q/A and citation integrity."""

from __future__ import annotations

import asyncio
import json
import os
import subprocess
import sys
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


def check_api_task_lifecycle(path: Path, project_id: str, binding: dict[str, str]) -> None:
    async def scenario() -> None:
        api._research_qa_tasks.clear()
        started = asyncio.Event()
        release = asyncio.Event()
        calls = 0

        async def slow_answer(*_args):
            nonlocal calls
            calls += 1
            started.set()
            await release.wait()
            return {"qa_id": "f" * 32}

        body = api.ResearchQARequest(
            path=str(path),
            expected_project_id=project_id,
            expected_binding=binding["identity"],
            request_id="a" * 32,
            question="A reconnect question",
        )
        key = (os.path.realpath(path), body.request_id)
        with (
            patch.object(
                api, "require_cloud_inference_binding", new=lambda *_args: asyncio.sleep(0)
            ),
            patch.object(api.research_qa, "answer", new=slow_answer),
        ):
            disconnected = asyncio.create_task(api.research_qa_answer(body))
            await started.wait()
            disconnected.cancel()
            try:
                await disconnected
            except asyncio.CancelledError:
                pass
            assert key in api._research_qa_tasks
            reconnected = asyncio.create_task(api.research_qa_answer(body))
            await asyncio.sleep(0)
            assert calls == 1
            release.set()
            assert await reconnected == {"qa_id": "f" * 32}
            await asyncio.sleep(0)
            assert key not in api._research_qa_tasks

            failed_calls = 0

            async def fail_once_then_report_pending(*_args):
                nonlocal failed_calls
                failed_calls += 1
                if failed_calls == 1:
                    raise RuntimeError("provider response interrupted")
                raise ProjectError("request may already have reached provider")

            with patch.object(api.research_qa, "answer", new=fail_once_then_report_pending):
                failed_body = body.model_copy(update={"request_id": "b" * 32})
                failed_key = (os.path.realpath(path), failed_body.request_id)
                try:
                    await api.research_qa_answer(failed_body)
                except RuntimeError:
                    pass
                else:
                    raise AssertionError("Provider failure should propagate to its request")
                await asyncio.sleep(0)
                assert failed_key not in api._research_qa_tasks
                try:
                    await api.research_qa_answer(failed_body)
                except ProjectError as exc:
                    assert "already have reached" in str(exc)
                else:
                    raise AssertionError(
                        "Reconnect after failure should report the pending request"
                    )
                assert failed_calls == 2
                await asyncio.sleep(0)
                assert failed_key not in api._research_qa_tasks

    asyncio.run(scenario())


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
            check_api_task_lifecycle(path, before.project.id, credential)
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
            child_environment = os.environ.copy()
            child_environment["PYTHONPATH"] = os.pathsep.join(
                [
                    str(Path(__file__).resolve().parents[1] / "src"),
                    child_environment.get("PYTHONPATH", ""),
                ]
            )
            restarted = subprocess.run(
                [
                    sys.executable,
                    "-c",
                    "import sys; from sigma.research_qa import list_answers; assert any(row['qa_id'] == sys.argv[1] for row in list_answers(sys.argv[2]))",
                    first["qa_id"],
                    str(path),
                ],
                cwd=Path(__file__).resolve().parents[1],
                env=child_environment,
                check=False,
                capture_output=True,
                text=True,
            )
            assert restarted.returncode == 0, restarted.stderr
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

            failure_calls = 0

            async def interrupted(_input, *_args, **_kwargs):
                nonlocal failure_calls
                failure_calls += 1
                raise RuntimeError("provider interrupted after dispatch")

            with patch.object(research_qa.papers, "_provider_structured", new=interrupted):
                try:
                    asyncio.run(
                        research_qa.answer(
                            str(path),
                            "Question with interrupted request",
                            before.project.id,
                            credential["identity"],
                            "e" * 32,
                        )
                    )
                except RuntimeError as exc:
                    assert "interrupted" in str(exc)
                else:
                    raise AssertionError("Interrupted provider call must be reported")
                try:
                    asyncio.run(
                        research_qa.answer(
                            str(path),
                            "Question with interrupted request",
                            before.project.id,
                            credential["identity"],
                            "e" * 32,
                        )
                    )
                except ProjectError as exc:
                    assert "may already have reached" in str(exc)
                else:
                    raise AssertionError("An interrupted request must not repeat provider work")
            assert failure_calls == 1

            async def concurrent_delete_and_answer():
                started_provider = asyncio.Event()
                release_provider = asyncio.Event()

                async def blocked_provider(*_args, **_kwargs):
                    started_provider.set()
                    await release_provider.wait()
                    return research_qa.AnswerDraft(
                        answer="A second answer remains saved.", source_refs=[f"session:{s2}"]
                    ), "{}"

                with patch.object(research_qa.papers, "_provider_structured", new=blocked_provider):
                    task = asyncio.create_task(
                        research_qa.answer(
                            str(path),
                            "A concurrent question",
                            before.project.id,
                            credential["identity"],
                            "d" * 32,
                        )
                    )
                    await started_provider.wait()
                    research_qa.delete_answer(str(path), first["qa_id"])
                    release_provider.set()
                    return await task

            concurrent = asyncio.run(concurrent_delete_and_answer())
            remaining_ids = {row["qa_id"] for row in research_qa.list_answers(str(path))}
            assert remaining_ids == {inconclusive["qa_id"], concurrent["qa_id"]}

            archive_path = path / "artifacts" / "research-qa" / "records.json"
            valid_archive = archive_path.read_bytes()
            malformed = json.loads(valid_archive)
            malformed["records"][0]["sources"][0]["source_id"] = "session:https://forged.invalid"
            archive_path.write_text(json.dumps(malformed), encoding="utf-8")
            malformed_bundle = Path(temporary) / "malformed.json"
            import_bundle(json.loads(export_complete_project(path)), malformed_bundle)
            try:
                research_qa.list_answers(str(malformed_bundle))
            except ProjectError as exc:
                assert "invalid citation" in str(exc)
            else:
                raise AssertionError("Imported malformed Q/A citations must fail safely")
            archive_path.write_bytes(valid_archive)

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
            research_qa.delete_answer(str(path), inconclusive["qa_id"])
            assert [row["qa_id"] for row in research_qa.list_answers(str(path))] == [
                concurrent["qa_id"]
            ]
        print(
            "Research Q/A: validated citations, idempotent retry, safe browser rendering, durable save/remove, and no project mutation passed."
        )


if __name__ == "__main__":
    main()
