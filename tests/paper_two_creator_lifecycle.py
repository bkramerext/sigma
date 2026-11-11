"""Two authenticated creators: HTTP Paper queue, reconnect, Stop/Resume and real PDFs.

Run in an isolated interpreter with no paid inference. The production API,
persistent storage, paper authoring/TeX pipeline and PDF reader stay real.
Only OIDC identity resolution and inference responses are deterministic.
"""

from __future__ import annotations

import asyncio
import hashlib
import json
import os
import shutil
from pathlib import Path
from tempfile import TemporaryDirectory
from unittest.mock import patch
from uuid import uuid4

import httpx
import pypdfium2


async def _wait_for(check, *, attempts: int = 250) -> None:
    for _ in range(attempts):
        if await check():
            return
        await asyncio.sleep(0.02)
    raise AssertionError("Paper lifecycle did not reach the expected persisted state")


async def _serve_disconnected(app, body: dict, headers: dict[str, str], entered: asyncio.Event):
    """Submit through HTTP, then disconnect only the SSE browser, not its job."""
    incoming: asyncio.Queue[dict] = asyncio.Queue()
    await incoming.put(
        {"type": "http.request", "body": json.dumps(body).encode(), "more_body": False}
    )
    outgoing: list[dict] = []

    async def send(message: dict) -> None:
        outgoing.append(message)

    scope = {
        "type": "http",
        "asgi": {"version": "3.0"},
        "http_version": "1.1",
        "method": "POST",
        "scheme": "http",
        "path": "/api/projects/papers",
        "raw_path": b"/api/projects/papers",
        "query_string": b"",
        "root_path": "",
        "headers": [
            (key.lower().encode(), value.encode())
            for key, value in {
                "host": "testserver",
                "content-type": "application/json",
                **headers,
            }.items()
        ],
        "server": ("testserver", 80),
        "client": ("127.0.0.1", 1234),
    }
    serving = asyncio.create_task(app(scope, incoming.get, send))
    try:
        await asyncio.wait_for(entered.wait(), timeout=10)

        async def stream_started() -> bool:
            return any(item.get("type") == "http.response.start" for item in outgoing)

        await _wait_for(stream_started)
        assert (
            next(item["status"] for item in outgoing if item["type"] == "http.response.start")
            == 200
        )
        await incoming.put({"type": "http.disconnect"})
        await asyncio.wait_for(serving, timeout=5)
    finally:
        if not serving.done():
            serving.cancel()
            await asyncio.gather(serving, return_exceptions=True)


def _completed(response: httpx.Response) -> dict:
    assert response.status_code == 200, response.text
    events = [
        json.loads(line[6:]) for line in response.text.splitlines() if line.startswith("data: ")
    ]
    errors = [event for event in events if event.get("type") == "error"]
    assert not errors, errors
    complete = [event for event in events if event.get("type") == "complete"]
    assert len(complete) == 1, events[-5:]
    return complete[0]["result"]


async def _exercise() -> None:
    import cloud_workspace_test_app
    from papers_part1 import draft

    from sigma import (
        cloud_auth,
        cloud_workspaces,
        openai_connection,
        paper_scores,
        paper_writing_sources,
        papers,
        project_collaboration,
    )

    principals = {
        name: cloud_auth.Principal(f"paper-{name}", f"{name}@example.test", "member")
        for name in ("n", "z")
    }
    for principal in principals.values():
        cloud_auth._persist_user_state(cloud_auth.config(), principal)
        cloud_auth.set_model_access(principal.subject, "sponsored")

    async def binding(principal: cloud_auth.Principal) -> str:
        token = cloud_workspaces.bind(principal)
        try:
            return (await openai_connection.auth_context())["identity"]
        finally:
            cloud_workspaces.reset(token)

    bindings = {name: await binding(user) for name, user in principals.items()}
    headers = {
        name: {"X-Test-Subject": user.subject, "X-Test-Email": user.email}
        for name, user in principals.items()
    }
    first_entered = asyncio.Event()
    release_first = asyncio.Event()
    second_entered = asyncio.Event()
    authoring_order: list[str] = []
    simultaneous_authors = 0
    peak_authors = 0
    scored_before_return: list[str] = []

    async def author(package, _account, config, *_args):
        nonlocal simultaneous_authors, peak_authors
        principal = cloud_auth.current_principal()
        assert principal is not None
        name = principal.subject.removeprefix("paper-")
        simultaneous_authors += 1
        peak_authors = max(peak_authors, simultaneous_authors)
        authoring_order.append(name)
        try:
            if name == "n":
                first_entered.set()
                await asyncio.wait_for(release_first.wait(), timeout=60)
            else:
                # The global generation slot must cover ALL of N's PDF
                # compilation/finalization, not just N's provider call.
                published = papers.list_papers(package_path)
                assert len(published) == 1, published
                assert published[0]["created_by"] == principals["n"].email
                second_entered.set()
            ref = next(source["id"] for source in package["sources"] if source["kind"] == "project")
            value = draft(ref)
            return value.model_copy(
                update={"title": f"Independent Paper by {name.upper()} collaborator"}
            ), config["model"]
        finally:
            simultaneous_authors -= 1

    async def proofread(_payload, _account, config, *, schema_name, response_model, **_kw):
        assert schema_name == "sigma_tex_proofread_patches", schema_name
        return response_model.model_validate({"corrections": []}), config["model"]

    async def score_fixture(path, paper_id, *_args, **_kwargs):
        # Regression for the former detached-SSE publication attribution:
        # the creator MUST already be in the durable reservation ledger
        # before scoring starts, while this provider task is still active.
        principal = cloud_auth.current_principal()
        assert principal is not None
        reservations = project_collaboration.list_execution_runs(path, "paper")
        committed = [row for row in reservations if row["artifact_id"] == paper_id]
        assert len(committed) == 1, reservations
        assert committed[0]["creator_email"] == principal.email
        assert committed[0]["status"] == "complete"
        scored_before_return.append(committed[0]["run_id"])
        return {"status": "fixture-scoring-complete"}

    async def select_no_external_sources(*_args):
        # The test does not fetch external writing guidance or spend on
        # publication-reference compilation; only TeX/PDF remains real.
        return [], "no-external-fixture-sources"

    config = {
        "available": True,
        "model": "gpt-6-luna",
        "reasoning_effort": "high",
    }
    real_compile = papers._compile_pdf
    fail_first_z_compile = True
    z_compile_calls = 0
    real_compilations = 0

    def compile_fixture(*args, **kwargs):
        # The first Z TeX invocation is the preliminary proofreading
        # inspection; fail the SECOND invocation, which is the publication
        # compile after the authored draft and proofreader are checkpointed.
        # Without this discriminator the injected fault would be swallowed
        # by proofreading and the recovery test would give a false positive.
        nonlocal fail_first_z_compile, z_compile_calls, real_compilations
        principal = cloud_auth.current_principal()
        if principal is not None and principal.subject == "paper-z":
            z_compile_calls += 1
            if z_compile_calls == 2 and fail_first_z_compile:
                fail_first_z_compile = False
                raise RuntimeError("Fixture: final TeX compilation failed before PDF publication")
        output = real_compile(*args, **kwargs)
        real_compilations += 1
        return output

    app = cloud_workspace_test_app.app
    async with (
        httpx.AsyncClient(
            transport=httpx.ASGITransport(app=app),
            base_url="http://testserver",
            headers=headers["n"],
            timeout=90,
        ) as n,
        httpx.AsyncClient(
            transport=httpx.ASGITransport(app=app),
            base_url="http://testserver",
            headers=headers["z"],
            timeout=90,
        ) as z,
    ):
        created = await n.post(
            "/api/projects/create",
            json={
                "title": "Two collaborator publication acceptance",
                "problem": "What is recorded in this saved question?",
                "investigation_type": "mathematical",
            },
        )
        assert created.status_code == 201, created.text
        path = created.json()["path"]
        package_path = path
        project_id = created.json()["project"]["id"]
        inspected = await n.get("/api/projects/inspect", params={"path": path})
        assert inspected.status_code == 200, inspected.text
        project = inspected.json()["project"]
        keys = (
            "title",
            "problem",
            "investigation_type",
            "ai_model",
            "reasoning_effort",
            "difficulty",
            "show_advanced_outcome_details",
        )
        settings = {key: project[key] for key in keys}
        shared = await n.post(
            "/api/projects/update",
            json={
                "path": path,
                **settings,
                "expected": settings,
                "collaborators": [principals["z"].email],
            },
        )
        assert shared.status_code == 200, shared.text
        collaborator_view = await z.get("/api/projects/inspect", params={"path": path})
        assert collaborator_view.status_code == 200, collaborator_view.text
        assert collaborator_view.json()["project"]["id"] == project_id

        # Both clients refer to the same ORIGINAL project and frozen snapshot.
        token = cloud_workspaces.bind(principals["n"])
        principal_token = cloud_auth._CURRENT_PRINCIPAL.set(principals["n"])
        try:
            snapshot = papers._snapshot(path)[1]
        finally:
            cloud_auth._CURRENT_PRINCIPAL.reset(principal_token)
            cloud_workspaces.reset(token)
        run_ids = {"n": uuid4().hex, "z": uuid4().hex}
        bodies = {
            name: {
                "path": path,
                "run_id": run_ids[name],
                "expected_project_id": project_id,
                "expected_binding": bindings[name],
                "expected_snapshot_sha256": snapshot,
                "include_diagrams": False,
            }
            for name in ("n", "z")
        }
        with (
            patch.object(papers, "configuration", return_value=config),
            patch.object(papers, "_provider", new=author),
            patch.object(papers, "_provider_structured", new=proofread),
            patch.object(paper_writing_sources, "select", new=select_no_external_sources),
            patch.object(papers, "_compile_pdf", new=compile_fixture),
            patch.object(paper_scores, "score_paper", new=score_fixture),
        ):
            try:
                # N's stream disappears. Its independent generation must remain alive.
                await _serve_disconnected(app, bodies["n"], headers["n"], first_entered)
                active = await n.get("/api/projects/papers/progress", params={"path": path})
                assert active.status_code == 200, active.text
                assert any(item["run_id"] == run_ids["n"] for item in active.json()["runs"]), (
                    active.json()
                )

                z_pending = asyncio.create_task(z.post("/api/projects/papers", json=bodies["z"]))

                async def z_is_queued() -> bool:
                    response = await n.get("/api/projects/papers/progress", params={"path": path})
                    assert response.status_code == 200, response.text
                    return any(
                        item["run_id"] == run_ids["z"] and item["status"] == "queued"
                        for item in response.json()["runs"]
                    )

                await _wait_for(z_is_queued)
                assert not second_entered.is_set(), "FIFO queue admitted Z while N still active"
                # Reconnecting as either collaborator may READ both runs;
                # one viewer cannot change the other's task or checkpoint.
                for client in (n, z):
                    for name, run_id in run_ids.items():
                        observed = await client.get(
                            "/api/projects/papers/progress",
                            params={"path": path, "run_id": run_id},
                        )
                        assert observed.status_code == 200, observed.text
                        assert observed.json()["progress"]["status"] == (
                            "active" if name == "n" else "queued"
                        ), observed.json()
                receipt = await n.get("/api/projects/papers", params={"path": path})
                assert receipt.status_code == 200, receipt.text
                reserved = {item["run_id"]: item for item in receipt.json()["runs"]}
                assert reserved[run_ids["n"]]["number"] == 1, reserved
                assert reserved[run_ids["z"]]["number"] == 2, reserved
                assert reserved[run_ids["n"]]["creator_email"] == principals["n"].email
                assert reserved[run_ids["z"]]["creator_email"] == principals["z"].email

                # Both directions are forbidden: owning the project does not
                # own the run. Also reject replaying the other's run ID at the
                # generation API, before it can mutate a saved checkpoint.
                for actor, target in ((n, "z"), (z, "n")):
                    name = "n" if actor is n else "z"
                    attempt = await actor.post(
                        "/api/projects/papers",
                        json={**bodies[name], "run_id": run_ids[target]},
                    )
                    assert attempt.status_code == 400, attempt.text
                    assert "original execution creator" in attempt.text
                for actor, target in ((n, "z"), (z, "n")):
                    denied = await actor.post(
                        "/api/projects/papers/cancel",
                        json={
                            "path": path,
                            "run_id": run_ids[target],
                            "expected_project_id": project_id,
                            "expected_binding": bindings["n" if actor is n else "z"],
                        },
                    )
                    assert denied.status_code == 400, denied.text
                    assert "original execution creator" in denied.text

                cancelled = await z.post(
                    "/api/projects/papers/cancel",
                    json={
                        "path": path,
                        "run_id": run_ids["z"],
                        "expected_project_id": project_id,
                        "expected_binding": bindings["z"],
                    },
                )
                assert cancelled.status_code == 200, cancelled.text
                assert cancelled.json()["cancelled"] is True
                stopped = await asyncio.wait_for(z_pending, timeout=10)
                assert '"type": "error"' in stopped.text or '"type":"error"' in stopped.text
                assert not second_entered.is_set()
                assert not release_first.is_set()
                assert peak_authors == 1
                # Same creator may Resume the exact cancelled run and number.
                z_resumed = asyncio.create_task(z.post("/api/projects/papers", json=bodies["z"]))
                await _wait_for(z_is_queued)
                assert not second_entered.is_set()
                release_first.set()
                failed_compilation = await asyncio.wait_for(z_resumed, timeout=90)
                assert failed_compilation.status_code == 200, failed_compilation.text
                assert '"type": "error"' in failed_compilation.text or (
                    '"type":"error"' in failed_compilation.text
                )
                assert not fail_first_z_compile
                assert z_compile_calls == 2, z_compile_calls
                still_only_n = await n.get("/api/projects/papers", params={"path": path})
                assert still_only_n.status_code == 200, still_only_n.text
                assert len(still_only_n.json()["papers"]) == 1, still_only_n.text
                # Preserve and reuse Z's authoring checkpoint. Resume must
                # compile the draft without another author/provider call.
                token = cloud_workspaces.bind(principals["z"])
                principal_token = cloud_auth._CURRENT_PRINCIPAL.set(principals["z"])
                try:
                    with papers.paper_run_scope(run_ids["z"]):
                        checkpoint = papers._load_work(path)
                    assert checkpoint is not None
                    assert checkpoint["one_shot_draft"]
                    assert checkpoint["provider_calls"] == 1
                finally:
                    cloud_auth._CURRENT_PRINCIPAL.reset(principal_token)
                    cloud_workspaces.reset(token)
                assert authoring_order == ["n", "z"], authoring_order
                z_finished = _completed(await z.post("/api/projects/papers", json=bodies["z"]))
            finally:
                release_first.set()

        assert authoring_order == ["n", "z"], authoring_order
        assert peak_authors == 1
        assert second_entered.is_set()
        assert z_compile_calls >= 3
        assert real_compilations >= 4, real_compilations
        assert set(scored_before_return) == set(run_ids.values()), scored_before_return
        listing = await n.get("/api/projects/papers", params={"path": path})
        assert listing.status_code == 200, listing.text
        saved = listing.json()["papers"]
        assert len(saved) == 2, saved
        pdf_by_run: dict[str, bytes] = {}
        for item in saved:
            paper_id = item["paper_id"]
            metadata_response = await z.get(
                f"/api/projects/papers/{paper_id}", params={"path": path}
            )
            assert metadata_response.status_code == 200, metadata_response.text
            metadata = metadata_response.json()
            run_id = metadata["generation"]["progress_run_id"]
            assert run_id in set(run_ids.values()), run_id
            expected_name = next(name for name, value in run_ids.items() if value == run_id)
            assert metadata["created_by"] == principals[expected_name].email
            assert metadata["paper_version"] == (1 if expected_name == "n" else 2)
            assert metadata["snapshot_sha256"] == snapshot
            assert metadata["pdf_available"] is True
            pdf_response = await z.get(
                f"/api/projects/papers/{paper_id}/pdf", params={"path": path}
            )
            assert pdf_response.status_code == 200, pdf_response.text[:200]
            assert pdf_response.headers["content-type"] == "application/pdf"
            pdf = pdf_response.content
            assert pdf.startswith(b"%PDF-") and len(pdf) > 5_000
            assert hashlib.sha256(pdf).hexdigest() == metadata["pdf_sha256"]
            document = pypdfium2.PdfDocument(pdf)
            assert len(document) >= 1
            extracted = " ".join(
                document[index].get_textpage().get_text_range() for index in range(len(document))
            )
            assert f"Independent Paper by {expected_name.upper()} collaborator" in " ".join(
                extracted.split()
            ), extracted[:500]
            assert run_id not in pdf_by_run
            pdf_by_run[run_id] = pdf

        assert set(pdf_by_run) == set(run_ids.values())
        assert pdf_by_run[run_ids["n"]] != pdf_by_run[run_ids["z"]]
        assert z_finished["paper_id"] in {item["paper_id"] for item in saved}
        assert z_finished["paper_id"] == next(
            item["paper_id"] for item in saved if item["created_by"] == principals["z"].email
        )
        for actor in (n, z):
            completed = await actor.get("/api/projects/papers", params={"path": path})
            rows = {item["run_id"]: item for item in completed.json()["runs"]}
            for name, run_id in run_ids.items():
                assert rows[run_id]["status"] == "complete", rows
                assert rows[run_id]["creator_email"] == principals[name].email
                assert rows[run_id]["artifact_id"] in {paper["paper_id"] for paper in saved}
        # A reconnect or a changed viewer cannot re-assign either published run.
        assert len({paper["paper_id"] for paper in saved}) == 2
        print(
            "PASS #769: authenticated N/Z, FIFO, Stop/Resume, reconnect, "
            "saved checkpoint reuse and two compiled readable PDFs"
        )


def main() -> None:
    if shutil.which("tectonic") is None:
        raise AssertionError("#769 PDF acceptance requires a locally installed Tectonic binary")
    with TemporaryDirectory(prefix="sigma-paper-collab-", dir=Path.cwd().parent) as temporary:
        root = Path(temporary)
        root.chmod(0o700)
        for name in ("workspaces", "local-projects", "local-state"):
            (root / name).mkdir(mode=0o700)
        environment = {
            "SIGMA_REFERENCE_COMPILATION_ENABLED": "false",
            "SIGMA_CLOUD_AUTH_ENABLED": "true",
            "GOOGLE_OIDC_CLIENT_ID": "fixture.apps.googleusercontent.com",
            "GOOGLE_OIDC_CLIENT_SECRET": "fixture-secret",
            "SIGMA_CLOUD_PUBLIC_ORIGIN": "https://sigma.test",
            "SIGMA_CLOUD_ADMIN_CONTACT_EMAIL": "admin@example.test",
            "SIGMA_CLOUD_AUTH_HOME": str(root / "auth"),
            "SIGMA_CLOUD_WORKSPACES_ROOT": str(root / "workspaces"),
            "SIGMA_PROJECTS_ROOT": str(root / "local-projects"),
            "SIGMA_STATE_DIR": str(root / "local-state"),
            "SIGMA_CLOUD_OPENAI_API_KEY": "fake-fixture-only",
            "SIGMA_CLOUD_INFERENCE_PROVIDER": "api_key",
        }
        with patch.dict(os.environ, environment):
            asyncio.run(_exercise())


if __name__ == "__main__":
    main()
