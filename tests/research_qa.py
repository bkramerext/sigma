"""Deterministic checks for saved-research Q/A and citation integrity."""

from __future__ import annotations

import asyncio
import copy
import hashlib
import json
import os
import sqlite3
import subprocess
import sys
from contextvars import ContextVar
from dataclasses import asdict
from pathlib import Path
from tempfile import TemporaryDirectory
from typing import Any
from unittest.mock import patch

from sigma import api, project_collaboration as shared, research_qa
from sigma.cloud_auth import Principal
from sigma.cloud_workspaces import Workspace
from sigma.project_bundle import import_bundle
from sigma.projects import (
    ProjectError,
    project_settings,
    update_project,
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
        actor = ["n@example.org"]
        with (
            patch.object(
                api, "require_cloud_inference_binding", new=lambda *_args: asyncio.sleep(0)
            ),
            patch.object(api.research_qa, "answer", new=slow_answer),
            patch.object(
                api.project_collaboration,
                "collaborator_identity",
                side_effect=lambda _path: actor[0],
            ),
        ):
            disconnected = asyncio.create_task(api.research_qa_answer(body))
            await started.wait()
            disconnected.cancel()
            try:
                await disconnected
            except asyncio.CancelledError:
                pass
            assert key in api._research_qa_tasks
            conflicting = body.model_copy(update={"question": "A different question"})
            try:
                await api.research_qa_answer(conflicting)
            except ProjectError as exc:
                assert "different request parameters" in str(exc)
            else:
                raise AssertionError("A conflicting in-flight request ID must be rejected")
            assert calls == 1
            actor[0] = "z@example.org"
            try:
                await api.research_qa_answer(body)
            except ProjectError as exc:
                assert "different request parameters" in str(exc)
            else:
                raise AssertionError("A collaborator hijacked another's pending Q/A")
            actor[0] = "n@example.org"
            assert calls == 1
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


def check_creator_scoped_request_replay() -> None:
    """Saved/pending request IDs cannot be replayed under another creator."""
    request_id = "9" * 32
    question = "Can SIGMA prove this from saved evidence?"
    record = {
        "qa_id": "8" * 32,
        "request_id": request_id,
        "question": question,
        "author_email": "n@example.org",
    }
    assert (
        research_qa._request_record([record], request_id, question, creator="n@example.org")
        == record
    )
    try:
        research_qa._request_record([record], request_id, question, creator="z@example.org")
    except ProjectError as exc:
        assert "another collaborator" in str(exc)
    else:
        raise AssertionError("Saved Q/A request identity was reusable by another creator")
    digest = hashlib.sha256(question.encode()).hexdigest()
    pending = [
        {
            "request_id": request_id,
            "question_sha256": digest,
            "creator": "n@example.org",
        }
    ]
    try:
        research_qa._check_pending_request(pending, request_id, digest, creator="z@example.org")
    except ProjectError as exc:
        assert "another collaborator" in str(exc)
    else:
        raise AssertionError("A foreign pending Q/A reservation was reusable")


def check_two_creators_answer_same_project_concurrently() -> None:
    """N/Z provider calls overlap without crossing saved answers or attribution."""
    with TemporaryDirectory() as temporary:
        root = Path(temporary)
        path = root / "shared-qa.sigma"
        view = initialize_project(path, "Shared Q/A", "Test concurrent collaboration")
        source = "session:11111111-1111-4111-8111-111111111111"
        package = {
            "project_id": view.project.id,
            "sources": [
                {
                    "id": source,
                    "kind": "session",
                    "data": {
                        "session_number": 1,
                        "status": "completed",
                        "outcome": {"label": "uncertain", "summary": "Two agents disagreed."},
                    },
                },
            ],
        }
        identities = ("n@example.org", "z@example.org")
        user: ContextVar[str] = ContextVar("qa-test-user", default=identities[0])
        (root / "z-private").mkdir()
        principals = {
            email: Principal(subject=f"google-{i}", email=email, role="member")
            for i, email in enumerate(identities)
        }
        workspaces = {
            email: Workspace(
                workspace_id=f"workspace-{i}",
                subject_hash=f"subject-hash-{i}",
                path=root if i == 0 else root / "z-private",
                email=email,
                verified_subject=principals[email].subject,
            )
            for i, email in enumerate(identities)
        }

        def connect(_root: Path) -> sqlite3.Connection:
            db = sqlite3.connect(root / "collaboration.sqlite3", timeout=10, isolation_level=None)
            db.row_factory = sqlite3.Row
            db.execute("PRAGMA busy_timeout=10000")
            return db
        provider_started: set[str] = set()
        provider_calls = 0

        async def exercise() -> None:
            nonlocal provider_calls
            both_entered = asyncio.Event()
            allow_completion = asyncio.Event()

            async def provider(*_args, **_kwargs):
                nonlocal provider_calls
                identity = user.get()
                assert identity in identities
                provider_calls += 1
                provider_started.add(identity)
                if len(provider_started) == 2:
                    both_entered.set()
                await asyncio.wait_for(both_entered.wait(), timeout=5)
                await asyncio.wait_for(allow_completion.wait(), timeout=5)
                return (
                    research_qa.AnswerDraft(
                        answer=f"Saved research assessed by {identity}.",
                        source_refs=[source],
                    ),
                    "{}",
                )

            async def binding():
                return {"identity": "shared-sponsored-fixture", "mode": "chatgpt"}

            async def config(**_kwargs):
                return {
                    "available": True,
                    "model": "mock-no-provider-charges",
                    "reasoning_effort": "medium",
                }

            async def submit(identity: str, request_id: str):
                token = user.set(identity)
                try:
                    return await research_qa.answer(
                        str(path),
                        "What does the saved skeptic say?",
                        view.project.id,
                        "shared-sponsored-fixture",
                        request_id,
                    )
                finally:
                    user.reset(token)

            with (
                patch.object(research_qa, "auth_context", new=binding),
                patch.object(research_qa, "configuration", new=config),
                patch.object(
                    research_qa.papers,
                    "_snapshot",
                    side_effect=lambda _path: (copy.deepcopy(package), "a" * 64),
                ),
                patch.object(research_qa.papers, "_provider_structured", new=provider),
                patch(
                    "sigma.research_state.current_understanding",
                    return_value={"summary": "Independent saved context"},
                ),
                patch(
                    "sigma.project_collaboration.cloud_workspaces.current",
                    side_effect=lambda: workspaces[user.get()],
                ),
                patch(
                    "sigma.project_collaboration.cloud_auth.current_principal",
                    side_effect=lambda: principals[user.get()],
                ),
                patch(
                    "sigma.project_collaboration.cloud_workspaces.storage_root",
                    return_value=root,
                ),
                patch(
                    "sigma.project_collaboration.cloud_workspaces._connect",
                    side_effect=connect,
                ),
            ):
                shared.register_owner(view)
                shared.save_settings(
                    str(path), 0, [identities[1]], "gpt-6.1-sol", "high", view.project.title
                )
                assert shared.summary(str(path))["collaborators"] == [identities[1]]
                first_task = asyncio.create_task(submit(identities[0], "1" * 32))
                second_task = asyncio.create_task(submit(identities[1], "2" * 32))
                try:
                    await asyncio.wait_for(both_entered.wait(), timeout=5)
                    # Source work and shared project editing cannot wait for
                    # either outstanding provider call to release its lock.
                    modified = api.create_strategy_view(
                        api.CreateStrategyRequest(
                            path=str(path),
                            title="Edited while Q/A was running",
                            approach="Independent collaborator edit",
                        )
                    )
                    assert len(modified["project"]["strategies"]) == 1
                finally:
                    allow_completion.set()
                first, second = await asyncio.wait_for(
                    asyncio.gather(first_task, second_task), timeout=8
                )
                assert provider_started == set(identities)
                assert first["qa_id"] != second["qa_id"]
                assert first["created_by"] == identities[0]
                assert second["created_by"] == identities[1]
                assert first["sources"][0]["source_id"] == source
                assert second["sources"][0]["source_id"] == source
                assert len(research_qa.list_answers(str(path))) == 2
                assert len(inspect_project(path).project.strategies) == 1
                assert (
                    inspect_project(path).project.strategies[0].title
                    == "Edited while Q/A was running"
                )
                assert research_qa.list_pending_answers(str(path)) == []
                assert provider_calls == 2

                # An authenticated Z cannot replay N's completed request ID,
                # even when sharing the same paid provider binding and question.
                try:
                    await submit(identities[1], "1" * 32)
                except ProjectError as exc:
                    assert "another collaborator" in str(exc)
                else:
                    raise AssertionError("Z replayed N's Q/A request identity")
                assert provider_calls == 2
                assert len(research_qa.list_answers(str(path))) == 2

                # Revoke Z using the actual project settings mutation, not a
                # direct SQLite DELETE. Its active lease must not lock out N.
                token = user.set(identities[1])
                try:
                    lease = shared.acquire_lease(str(path), "Paper generation")
                    assert lease is not None
                finally:
                    user.reset(token)
                settings = project_settings(inspect_project(path).project)
                revision = shared.summary(str(path))["revision"]
                updated = update_project(
                    path,
                    settings.title,
                    settings.problem,
                    settings.investigation_type,
                    settings.ai_model,
                    settings.reasoning_effort,
                    asdict(settings),
                    difficulty=settings.difficulty,
                    desired_outcomes=settings.desired_outcomes,
                    paper_requirements=settings.paper_requirements,
                    expected_revision=revision,
                    collaborators=[],
                )
                assert updated.project.id == view.project.id
                assert shared.summary(str(path))["collaborators"] == []
                assert not shared.renew_lease(str(path), lease)
                token = user.set(identities[1])
                try:
                    try:
                        shared.reserve_execution_run(
                            str(path), "session", "3" * 32, 0, model="mock", thinking="low"
                        )
                    except ValueError as exc:
                        assert "access denied" in str(exc)
                    else:
                        raise AssertionError("Revoked collaborator admitted another run")
                finally:
                    user.reset(token)
                assert len(inspect_project(path).project.strategies) == 1

        asyncio.run(exercise())

        # A backend restart must recover both independently attributed answers
        # from durable archive storage, not from an in-memory request registry.
        fresh_process = subprocess.run(
            [
                sys.executable,
                "-c",
                (
                    "import sys; from sigma.research_qa import list_answers; "
                    "rows=list_answers(sys.argv[1]); "
                    "assert len(rows)==2; "
                    "assert {row['created_by'] for row in rows}"
                    "=={'n@example.org','z@example.org'}; "
                    "from sigma.projects import inspect_project; "
                    "assert len(inspect_project(sys.argv[1]).project.strategies)==1"
                ),
                str(path),
            ],
            cwd=Path(__file__).resolve().parents[1],
            check=False,
            capture_output=True,
            text=True,
            timeout=15,
        )
        assert fresh_process.returncode == 0, fresh_process.stderr


def check_bounded_shared_conversation() -> None:
    history: list[dict[str, Any]] = [
        {"question": f"Other background {i}", "answer": "Unrelated " * 2000} for i in range(45)
    ]
    history.append(
        {
            "question": "What does the skeptic say about the narrow passage?",
            "answer": "The prior answer was inconclusive; corroboration is required.",
            "source_refs": ["forged:untrusted"],
        }
    )
    selected = research_qa._prior_qa_context("Follow up on the narrow passage skeptic?", history)
    assert selected and len(selected) <= research_qa.MAX_PRIOR_QA_EXCHANGES
    assert any("narrow passage" in item["question"] for item in selected)
    assert all(set(item) == {"question", "answer"} for item in selected)
    assert len(json.dumps(selected).encode()) <= research_qa.MAX_PRIOR_QA_CONTEXT_BYTES + 60


def check_ask_activity_worker_liveness() -> None:
    """Pending billing reservations do not constitute live Q/A execution."""
    with TemporaryDirectory() as directory:
        project = Path(directory) / "qa-project"
        project.mkdir()
        request_id = "c" * 32
        with patch.object(research_qa, "project_path", return_value=project):
            assert research_qa.list_pending_answers(str(project)) == []
            with research_qa._ask_worker(str(project), request_id):
                assert research_qa.list_pending_answers(str(project)) == []
                research_qa._publish_ask_activity(
                    str(project),
                    request_id,
                    creator="n@example.com",
                    model="gpt-fixture",
                    thinking="low",
                )
                expected = [
                    {
                        "request_id": request_id,
                        "creator": "n@example.com",
                        "model": "gpt-fixture",
                        "thinking": "low",
                    }
                ]
                with patch.object(
                    research_qa,
                    "_load_archive",
                    side_effect=AssertionError("Activity must not load Q/A archive"),
                ):
                    assert research_qa.list_pending_answers(str(project)) == expected
                try:
                    with research_qa._ask_worker(str(project), request_id):
                        raise AssertionError("Same request cannot acquire two worker locks")
                except ProjectError as exc:
                    assert "already answering" in str(exc)
                # Failed contender must not remove the actual worker marker.
                assert research_qa.list_pending_answers(str(project)) == expected
            assert research_qa.list_pending_answers(str(project)) == []
            try:
                with research_qa._ask_worker(str(project), request_id):
                    research_qa._publish_ask_activity(
                        str(project),
                        request_id,
                        creator="n@example.com",
                        model="gpt-fixture",
                        thinking="high",
                    )
                    raise RuntimeError("Simulated provider failure")
            except RuntimeError:
                pass
            assert research_qa.list_pending_answers(str(project)) == []


def main() -> None:
    check_ask_activity_worker_liveness()
    check_creator_scoped_request_replay()
    check_two_creators_answer_same_project_concurrently()
    check_bounded_shared_conversation()
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
        captured_inputs: list[dict] = []
        forged = False
        unsupported = False

        async def structured(_input, *_args, **kwargs):
            nonlocal calls
            calls += 1
            captured_inputs.append(_input)
            if forged:
                bogus = "session:99999999-9999-4999-8999-999999999999"
                refs = [f"session:{s1}", bogus, f"session:{s1}"] if forged == "mixed" else [bogus]
                return research_qa.AnswerDraft(
                    answer="The available record suggests a limited conclusion.",
                    source_refs=refs,
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
            assert first["created_by"] == "Local user"
            assert first["generation"]["model"] == "fixture-model"
            assert first["generation"]["reasoning_effort"] == "medium"
            assert [row["session_number"] for row in first["sources"]] == [1, 2]
            assert len(research_qa.list_answers(str(path))) == 1
            assert captured_inputs[0]["prior_qa"] == []
            followup = asyncio.run(
                research_qa.answer(
                    str(path),
                    "What limitations did the skeptic identify in that result?",
                    before.project.id,
                    credential["identity"],
                    "d" * 32,
                )
            )
            assert len(captured_inputs) == 2
            assert captured_inputs[1]["prior_qa"] == [
                {"question": first["question"], "answer": first["answer"][:900]}
            ]
            assert all(source["source_id"].startswith("session:") for source in followup["sources"])
            research_qa.delete_answer(str(path), followup["qa_id"])
            assert len(research_qa.list_answers(str(path))) == 1
            from sigma.text_views import digest

            original = research_qa.saved_answer_text(str(path), first["qa_id"])
            assert original["markdown_answer"] is None
            derived = research_qa.store_markdown_answer(
                str(path),
                first["qa_id"],
                digest(original["answer"]),
                "## Formatted answer\n\nMath: $R(n)$",
                {"provider": "openai", "model": "test-model", "reasoning_effort": "low"},
                [],
            )
            assert derived["plain"]["body"] == original["answer"]
            assert derived["markdown"]["body"].startswith("## Formatted answer")
            assert (
                research_qa.saved_answer_text(str(path), first["qa_id"])["markdown_answer"]
                == derived["markdown"]["body"]
            )
            cached = research_qa.store_markdown_answer(
                str(path),
                first["qa_id"],
                digest(original["answer"]),
                "Unexpected duplicate conversion",
                {"provider": "openai", "model": "test-model", "reasoning_effort": "low"},
                [],
            )
            assert cached["markdown"]["body"] == derived["markdown"]["body"]
            assert research_qa.get_answer(str(path), first["qa_id"])["answer"] == original["answer"]
            markdown = research_qa.markdown_document(
                research_qa.get_answer(str(path), first["qa_id"])
            )
            assert (
                "<script>alert(1)</script>" in markdown
            )  # Rendered by the safe React Markdown renderer.
            assert f"reveal_session={s1}" in markdown
            assert "Created: " in markdown and " UTC" in markdown
            assert "Model: " in markdown and " · " in markdown and " thinking" in markdown
            assert "Generation duration:" not in markdown
            assert "Research version:" not in markdown
            assert "Thinking level:" not in markdown
            assert (
                "## Question" in markdown and "## Answer" in markdown and "## Sources" in markdown
            )
            qa_archive_path = path / "artifacts" / "research-qa" / "records.json"
            archive_bytes = qa_archive_path.read_bytes()
            assert research_qa.archive_available(str(path))
            qa_archive_path.unlink()
            assert not research_qa.archive_available(str(path))
            assert research_qa.list_answers(str(path)) == []
            qa_archive_path.write_bytes(archive_bytes)
            qa_archive_path.write_bytes(b"{unreadable")
            try:
                research_qa.list_answers(str(path))
            except ProjectError as exc:
                assert "unreadable" in str(exc)
            else:
                raise AssertionError("An unreadable archive must not appear empty")
            assert qa_archive_path.read_bytes() == b"{unreadable"
            qa_archive_path.write_bytes(archive_bytes)
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
            portable_script = r"""
import asyncio
import sys
from sigma import papers, research_qa

project_path, project_id = sys.argv[1:3]
source_id = "session:11111111-1111-4111-8111-111111111111"
package = {"project_id": project_id, "sources": [{"id": source_id, "kind": "session", "data": {"session_number": 1, "status": "completed", "outcome": {"label": "supported", "summary": "The saved result supports this limited claim."}}}]}
papers._snapshot = lambda _path: (package, "e" * 64)

async def auth_context():
    return {"identity": "portable-test", "mode": "chatgpt"}

async def configuration(**_kwargs):
    return {"available": True, "model": "mock", "reasoning_effort": "low"}

async def provider(input_value, *_args, **_kwargs):
    await asyncio.sleep(0.05)
    return research_qa.AnswerDraft(answer="Portable answer saved.", source_refs=[input_value["sources"][0]["id"]]), "{}"

research_qa.auth_context = auth_context
research_qa.configuration = configuration
papers._provider_structured = provider
before = research_qa.list_answers(project_path)

async def exercise():
    generated = await asyncio.gather(*[
        research_qa.answer(project_path, f"Portable concurrent question {index}", project_id, "portable-test", f"{index:032x}")
        for index in (1, 2)
    ])
    listed = research_qa.list_answers(project_path)
    assert len(listed) == len(before) + 2
    assert {row["qa_id"] for row in generated}.issubset({row["qa_id"] for row in listed})
    research_qa.delete_answer(project_path, generated[0]["qa_id"])
    remaining = research_qa.list_answers(project_path)
    assert len(remaining) == len(before) + 1
    assert generated[1]["qa_id"] in {row["qa_id"] for row in remaining}

asyncio.run(exercise())
print("portable Q/A concurrent save/list/remove passed")
"""
            portable_result = subprocess.run(
                [sys.executable, "-c", portable_script, str(portable), before.project.id],
                cwd=Path(__file__).resolve().parents[1],
                env=child_environment,
                check=False,
                capture_output=True,
                text=True,
                timeout=15,
            )
            assert portable_result.returncode == 0, portable_result.stderr
            assert "portable Q/A concurrent save/list/remove passed" in portable_result.stdout
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
            assert calls == 3
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

            records, pending = research_qa._load_archive(str(path))
            pending.extend(
                {"request_id": f"{index + 0x100:032x}", "question_sha256": "0" * 64}
                for index in range(research_qa.MAX_RECORDS)
            )
            research_qa._save(str(path), records, pending)

            async def answer_after_many_failed_markers(*_args, **_kwargs):
                return research_qa.AnswerDraft(
                    answer="Failed request markers do not use answer slots.",
                    source_refs=[f"session:{s2}"],
                ), "{}"

            with patch.object(
                research_qa.papers,
                "_provider_structured",
                new=answer_after_many_failed_markers,
            ):
                capacity_retry = asyncio.run(
                    research_qa.answer(
                        str(path),
                        "A fresh request after many failures",
                        before.project.id,
                        credential["identity"],
                        "f" * 32,
                    )
                )
            assert capacity_retry["answer"] == "Failed request markers do not use answer slots."
            assert len(research_qa.list_answers(str(path))) <= research_qa.MAX_RECORDS
            _records_after_retry, pending_after_retry = research_qa._load_archive(str(path))
            assert len(pending_after_retry) == research_qa.MAX_RECORDS + 1

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
            assert remaining_ids == {
                inconclusive["qa_id"],
                capacity_retry["qa_id"],
                concurrent["qa_id"],
            }

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

            # Provider citation errors are not a reason to discard a useful answer.
            # Mixed refs keep only the exact frozen source, deduplicated.
            forged = "mixed"
            partial = asyncio.run(
                research_qa.answer(
                    str(path),
                    "Question with some invalid citations",
                    before.project.id,
                    credential["identity"],
                    "b" * 32,
                )
            )
            assert [ref["source_id"] for ref in partial["sources"]] == [f"session:{s1}"]
            assert partial["answer"] == "The available record suggests a limited conclusion."
            # An entirely invented citation list is omitted, never made clickable.
            forged = "only"
            uncited = asyncio.run(
                research_qa.answer(
                    str(path),
                    "Question with no valid citations",
                    before.project.id,
                    credential["identity"],
                    "3" * 32,
                )
            )
            assert uncited["sources"] == []
            assert "No validated citations were returned." in research_qa.markdown_document(uncited)
            research_qa.delete_answer(str(path), partial["qa_id"])
            research_qa.delete_answer(str(path), uncited["qa_id"])
            forged = False
            assert len(research_qa.list_answers(str(path))) == 3
            assert inspect_project(path).project == before.project, (
                "Q/A must not mutate research or project settings"
            )
            research_qa.delete_answer(str(path), inconclusive["qa_id"])
            assert [row["qa_id"] for row in research_qa.list_answers(str(path))] == [
                concurrent["qa_id"],
                capacity_retry["qa_id"],
            ]

            archive_at_storage_limit = archive_path.read_bytes()
            provider_calls_at_storage_limit = 0

            async def provider_must_not_run(*_args, **_kwargs):
                nonlocal provider_calls_at_storage_limit
                provider_calls_at_storage_limit += 1
                raise AssertionError(
                    "Provider must not run after the archive size bound is reached"
                )

            with (
                patch.object(research_qa.papers, "_provider_structured", new=provider_must_not_run),
                patch.object(research_qa, "MAX_ARCHIVE_BYTES", len(archive_at_storage_limit)),
            ):
                try:
                    asyncio.run(
                        research_qa.answer(
                            str(path),
                            "Request after bounded archive storage is full",
                            before.project.id,
                            credential["identity"],
                            "9" * 32,
                        )
                    )
                except ProjectError as exc:
                    assert "storage limit" in str(exc)
                else:
                    raise AssertionError("A full archive must fail closed")
            assert provider_calls_at_storage_limit == 0
            assert archive_path.read_bytes() == archive_at_storage_limit
        qa_project_id = "project-fixture"
        session_id = "session-fixture"
        strategy_id = "strategy-fixture"
        artifact_id = "artifact-fixture"
        refs = [
            f"project:{qa_project_id}",
            f"strategy:{strategy_id}",
            f"session:{session_id}",
            f"artifact:{session_id}:{artifact_id}",
            f"current-understanding:{qa_project_id}",
        ]
        evidence = [
            {"id": refs[0], "kind": "project", "data": {"title": "Prime project"}},
            {"id": refs[1], "kind": "strategy", "data": {"title": "Modular approach"}},
            {"id": refs[2], "kind": "session", "data": {"session_number": 8}},
            {"id": refs[3], "kind": "artifact", "data": {"sequence": 3}},
            {
                "id": refs[4],
                "kind": "current_understanding",
                "data": {
                    "findings": [
                        {
                            "source": {
                                "project_id": qa_project_id,
                                "session_id": session_id,
                                "session_number": 8,
                            }
                        }
                    ]
                },
            },
        ]
        record = {
            "qa_id": "1" * 32,
            "project_id": qa_project_id,
            "question": "Why?",
            "answer": "A **short** answer.",
            "sources": [
                {
                    "source_id": ref,
                    "kind": row["kind"],
                    "session_number": 8 if row["kind"] in {"session", "artifact"} else None,
                }
                for ref, row in zip(refs, evidence, strict=True)
            ],
            "evidence_snapshot": evidence,
            "snapshot_sha256": "a" * 64,
            "created_at": "2026-01-01T00:00:00+00:00",
            "generation": {
                "model": "fixture",
                "reasoning_effort": "low",
                "generation_elapsed_seconds": 1,
            },
        }
        context = {
            "path": "/tmp/project.sigma",
            "project": {
                "id": qa_project_id,
                "title": "Prime project",
                "strategies": [{"id": strategy_id, "title": "Modular approach"}],
            },
            "sessions": {
                session_id: {
                    "id": session_id,
                    "session_number": 8,
                    "artifacts": [{"id": artifact_id, "sequence": 3}],
                }
            },
        }
        enriched = research_qa._with_navigation(record, context)
        labels = [source["label"] for source in enriched["sources"]]
        assert labels == [
            "Project · Prime project",
            "Strategy · Modular approach",
            "Session #8",
            "Session #8 · Artifact 3",
            "Session #8",
        ]
        assert all(
            source["navigation_available"] and source["navigation_url"].startswith("/project?")
            for source in enriched["sources"]
        )
        assert "reveal_understanding=1" in enriched["sources"][0]["navigation_url"]
        assert "reveal_strategy=strategy-fixture" in enriched["sources"][1]["navigation_url"]
        assert "reveal_artifact=artifact-fixture" in enriched["sources"][3]["navigation_url"]
        assert "reveal_session=session-fixture" in enriched["sources"][4]["navigation_url"]
        doc = research_qa.markdown_document(enriched)
        assert "[Project · Prime project]" in doc and "[Strategy · Modular approach]" in doc
        assert "Session #unknown" not in doc and "Research version:" not in doc
        missing = research_qa._with_navigation(
            record,
            {
                "path": "/tmp/project.sigma",
                "project": {"id": qa_project_id, "title": "Prime project", "strategies": []},
                "sessions": {},
            },
        )
        assert (
            missing["sources"][1]["label"] == "Strategy · Modular approach"
            and not missing["sources"][1]["navigation_available"]
        )
        assert (
            missing["sources"][3]["label"].startswith("Session #8 · Artifact")
            and not missing["sources"][3]["navigation_available"]
        )
        assert missing["sources"][1]["navigation_unavailable_reason"]
        assert missing["sources"][3]["navigation_unavailable_reason"]
        assert missing["sources"][4]["label"] == "Current Understanding"
        assert "reveal_understanding=1" in missing["sources"][4]["navigation_url"]
        print(
            "Research Q/A: validated citations, idempotent retry, safe browser rendering, durable save/remove, and no project mutation passed."
        )


if __name__ == "__main__":
    main()
