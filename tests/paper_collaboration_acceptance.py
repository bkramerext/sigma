"""Authenticated two-creator Paper acceptance with a deterministic provider and real TeX.

The test app is exclusively the test-only Google-principal shim. Nothing in this
module patches _save, get_pdf, _compile_pdf, or the PDF reader. Run in a backend
image with Tectonic installed to exercise the complete TeX -> PDF path.
"""

from __future__ import annotations

import asyncio
import hashlib
import json
import logging
import os
import shutil
from pathlib import Path
from tempfile import TemporaryDirectory
from unittest.mock import patch
from uuid import uuid4

import httpx
import pypdfium2


def authored_draft(papers, source: str, creator: str):
    """A tiny but valid, attributable manuscript with no live references."""
    return papers.PaperDraft.model_validate(
        {
            "title": f"Independent Paper by {creator}",
            "abstract": (
                "A deterministic publication tests separately preserved evidence, "
                "creator attribution, and the original research question."
            ),
            "abstract_claim_ids": ["C1"],
            "problem_framing": ["The original project requests an independent publication."],
            "problem_framing_claim_ids": ["C1"],
            "methods": ["We use the exact archived project question as our only source."],
            "methods_claim_ids": ["C1"],
            "claims": [
                {
                    "id": "C1",
                    "statement": "The frozen snapshot contains the original research question.",
                    "status": "established",
                    "evidence_refs": [source],
                    "reasoning": "The project source is preserved as a frozen snapshot.",
                }
            ],
            "sections": [
                {
                    "heading": "Independent preservation",
                    "paragraphs": [
                        (
                            f"This fixture is independently authored for {creator}. "
                            "It verifies the preserved snapshot rather than claiming a new theorem."
                        )
                    ],
                    "claim_ids": ["C1"],
                }
            ],
            "limitations": ["No scientific inference is claimed by this fixture."],
            "open_obligations": ["Scientific review remains outside this persistence test."],
            "conclusions": ["The frozen project question remains independently readable."],
            "conclusion_claim_ids": ["C1"],
            "validation_warnings": ["Deterministic provider-free acceptance fixture."],
        }
    )


async def exercise(app, api, papers, cloud_auth, cloud_workspaces, project_collaboration) -> None:
    entered_n = asyncio.Event()
    release_n = asyncio.Event()
    provider_creators: list[str] = []
    scoring_ids: list[str] = []
    # The first Z publication compile fails after a durable author draft.
    # A subsequent explicit Resume must not dispatch a second authoring call.
    real_compile_pdf = papers._compile_pdf
    injected_compile_failure = False
    real_compilations = 0

    def compile_fixture(tex, **kwargs):
        nonlocal injected_compile_failure, real_compilations
        principal = cloud_auth.current_principal()
        if (
            principal is not None
            and principal.email == "z@example.test"
            and not injected_compile_failure
        ):
            injected_compile_failure = True
            raise RuntimeError("Deterministic final TeX compilation outage")
        output = real_compile_pdf(tex, **kwargs)
        real_compilations += 1
        return output

    binding = "fixture:two-creator-pdf"
    config = {
        "available": True,
        "binding": binding,
        "model": "gpt-6.1-sol",
        "reasoning_effort": "medium",
    }

    async def allow_binding(*_args, **_kwargs):
        return None

    async def credential():
        return {"identity": binding, "mode": "api_key", "token": "offline-fixture"}

    async def configuration(**_kwargs):
        return dict(config)

    async def provider(package, *_args, **_kwargs):
        principal = cloud_auth.current_principal()
        assert principal is not None
        creator = principal.email
        provider_creators.append(creator)
        if creator == "n@example.test":
            entered_n.set()
            await release_n.wait()
        else:
            # FIFO must serialize the *whole* previous Paper, including
            # TeX/PDF persistence, not merely the provider phase.
            published = papers.list_papers(path)
            assert len(published) == 1, published
            assert published[0]["created_by"] == "n@example.test"
        source = next(item["id"] for item in package["sources"] if item["kind"] == "project")
        return authored_draft(papers, source, creator), config["model"]

    async def proofread(tex, _work, **_kwargs):
        return tex, {
            "status": "complete",
            "corrections": [],
            "provider_calls_attempted": 0,
            "elapsed_seconds": 0,
            "original_sha256": hashlib.sha256(tex.encode()).hexdigest(),
            "final_sha256": hashlib.sha256(tex.encode()).hexdigest(),
        }

    async def scoring(path, paper_id, *_args):
        assert papers.get_pdf(path, paper_id).startswith(b"%PDF-")
        # The artifact belongs to its immutable reserved creator BEFORE
        # optional scoring or a detached SSE callback can run.
        run_id = papers._paper_run_id.get()
        principal = cloud_auth.current_principal()
        assert run_id and principal
        reservation = project_collaboration.execution_run(path, "paper", run_id, operator=True)
        assert reservation is not None
        assert reservation["artifact_id"] == paper_id
        assert reservation["creator_email"] == principal.email
        assert reservation["status"] == "complete"
        record = papers.get_paper(path, paper_id, include_tex=False)
        assert record["paper_version"] == reservation["number"]
        assert record["created_by"] == principal.email
        scoring_ids.append(paper_id)
        return {"paper_id": paper_id}

    transport = httpx.ASGITransport(app=app)
    with (
        patch.object(api, "require_cloud_inference_binding", new=allow_binding),
        patch.object(api, "auth_context", new=credential),
        patch.object(papers, "auth_context", new=credential),
        patch.object(papers, "configuration", new=configuration),
        patch.object(papers, "_provider", new=provider),
        patch.object(papers, "_proofread_tex", new=proofread),
        patch.object(papers, "_compile_pdf", new=compile_fixture),
        patch("sigma.paper_scores.score_paper", new=scoring),
    ):
        async with (
            httpx.AsyncClient(
                transport=transport,
                base_url="http://testserver",
                headers={"X-Test-Subject": "google-n", "X-Test-Email": "n@example.test"},
            ) as n,
            httpx.AsyncClient(
                transport=httpx.ASGITransport(app=app),
                base_url="http://testserver",
                headers={"X-Test-Subject": "google-z", "X-Test-Email": "z@example.test"},
            ) as z,
        ):
            created = await n.post(
                "/api/projects/create",
                json={
                    "title": "Shared Paper lifecycle",
                    "problem": "Can the exact original research question be preserved?",
                    "investigation_type": "mathematical",
                },
            )
            assert created.status_code == 201, created.text
            path = created.json()["path"]
            project_id = created.json()["project"]["id"]
            original = await n.get("/api/projects/inspect", params={"path": path})
            assert original.status_code == 200, original.text
            project = original.json()["project"]
            keys = (
                "title",
                "problem",
                "investigation_type",
                "ai_model",
                "reasoning_effort",
                "difficulty",
                "show_advanced_outcome_details",
            )
            settings = {key: project[key] for key in keys if key in project}
            revision = await n.get("/api/projects/collaboration", params={"path": path})
            assert revision.status_code == 200, revision.text
            expected_revision = revision.json()["revision"]
            assert type(expected_revision) is int
            shared = await n.post(
                "/api/projects/update",
                json={
                    "path": path,
                    **settings,
                    "expected": settings,
                    "expected_revision": expected_revision,
                    "collaborators": ["z@example.test"],
                },
            )
            assert shared.status_code == 200, shared.text
            reopened_by_z = await z.get("/api/projects/inspect", params={"path": path})
            assert reopened_by_z.status_code == 200, reopened_by_z.text
            assert reopened_by_z.json()["project"]["id"] == project_id

            preflight = await n.get(
                "/api/projects/papers/preflight",
                params={
                    "path": path,
                    "expected_project_id": project_id,
                    "expected_binding": binding,
                    "mode": "api_key",
                    "model": config["model"],
                    "reasoning_effort": "medium",
                },
            )
            assert preflight.status_code == 200, preflight.text
            digest = preflight.json()["snapshot_sha256"]
            runs = {"n@example.test": uuid4().hex, "z@example.test": uuid4().hex}
            request_data = {
                "path": path,
                "expected_project_id": project_id,
                "expected_binding": binding,
                "expected_snapshot_sha256": digest,
                "include_diagrams": False,
            }

            # This is a real ASGI HTTP request, with the same authenticated
            # middleware as subsequent polling. A disconnected subscriber is
            # not the owner of its separately retained generation task.
            receive_queue: asyncio.Queue[dict] = asyncio.Queue()
            await receive_queue.put(
                {
                    "type": "http.request",
                    "body": json.dumps({**request_data, "run_id": runs["n@example.test"]}).encode(),
                    "more_body": False,
                }
            )
            messages: list[dict] = []

            async def send(message):
                messages.append(message)

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
                    (b"host", b"testserver"),
                    (b"content-type", b"application/json"),
                    (b"x-test-subject", b"google-n"),
                    (b"x-test-email", b"n@example.test"),
                ],
                "server": ("testserver", 80),
                "client": ("127.0.0.1", 1234),
            }
            serving = asyncio.create_task(app(scope, receive_queue.get, send))
            await asyncio.wait_for(entered_n.wait(), timeout=15)
            assert any(msg["type"] == "http.response.start" for msg in messages)
            await receive_queue.put({"type": "http.disconnect"})
            await asyncio.wait_for(serving, timeout=10)

            z_body = {**request_data, "run_id": runs["z@example.test"]}
            first_z_request = asyncio.create_task(z.post("/api/projects/papers", json=z_body))
            for _ in range(300):
                status = await z.get(
                    "/api/projects/papers/progress",
                    params={"path": path, "run_id": runs["z@example.test"]},
                )
                if (
                    status.status_code == 200
                    and status.json()["progress"]
                    and (status.json()["progress"]["status"] == "queued")
                ):
                    break
                await asyncio.sleep(0.01)
            else:
                raise AssertionError("Z never received a separate FIFO queue receipt")
            assert provider_creators == ["n@example.test"]
            n_status = await n.get(
                "/api/projects/papers/progress",
                params={"path": path, "run_id": runs["n@example.test"]},
            )
            assert n_status.status_code == 200
            assert n_status.json()["progress"]["status"] == "active"
            listing = await n.get("/api/projects/papers", params={"path": path})
            assert listing.status_code == 200, listing.text
            reservations = {entry["run_id"]: entry for entry in listing.json()["runs"]}
            assert set(reservations) == set(runs.values())
            assert (
                reservations[runs["n@example.test"]]["number"] + 1
                == (reservations[runs["z@example.test"]]["number"])
            )
            assert reservations[runs["n@example.test"]]["creator_email"] == "n@example.test"
            assert reservations[runs["z@example.test"]]["creator_email"] == "z@example.test"

            # Cross-creator Stop cannot affect either queued or active work.
            def cancel_body(run_id):
                return {
                    "path": path,
                    "expected_project_id": project_id,
                    "expected_binding": binding,
                    "run_id": run_id,
                }

            denied_z = await z.post(
                "/api/projects/papers/cancel", json=cancel_body(runs["n@example.test"])
            )
            denied_n = await n.post(
                "/api/projects/papers/cancel", json=cancel_body(runs["z@example.test"])
            )
            assert denied_z.status_code in (400, 403, 404, 409), denied_z.text
            assert denied_n.status_code in (400, 403, 404, 409), denied_n.text
            assert provider_creators == ["n@example.test"]
            # Replaying another creator's run ID cannot hijack admission.
            for requester, foreign in (
                (n, runs["z@example.test"]),
                (z, runs["n@example.test"]),
            ):
                denied = await requester.post(
                    "/api/projects/papers",
                    json={**request_data, "run_id": foreign},
                )
                assert denied.status_code in (400, 403, 404, 409), denied.text
            assert provider_creators == ["n@example.test"]

            # These are authenticated, server-enforced creator controls.
            foreign_discard = await z.post(
                "/api/projects/papers/discard",
                json={**cancel_body(runs["n@example.test"]), "confirm_discard": True},
            )
            foreign_restart = await n.post(
                "/api/projects/papers/restart",
                json={
                    **cancel_body(runs["z@example.test"]),
                    "expected_snapshot_sha256": digest,
                    "confirm_restart": True,
                },
            )
            foreign_preflight = await z.get(
                "/api/projects/papers/preflight",
                params={
                    **cancel_body(runs["n@example.test"]),
                    "run_id": runs["n@example.test"],
                },
            )
            for denial in (foreign_discard, foreign_restart):
                assert denial.status_code in (400, 403, 404, 409), denial.text
            # Preflight only reads the shared frozen checkpoint. Every
            # collaborator may inspect it before deciding to resume.
            assert foreign_preflight.status_code == 200, foreign_preflight.text
            assert foreign_preflight.json()["checkpoint_exists"] is True
            assert provider_creators == ["n@example.test"]

            # Z stops only its own queued receipt, then independently resumes
            # the *same* admitted ID/number without dispatching a provider call.
            stopped = await z.post(
                "/api/projects/papers/cancel", json=cancel_body(runs["z@example.test"])
            )
            assert stopped.status_code == 200 and stopped.json()["cancelled"] is True
            first_response = await asyncio.wait_for(first_z_request, timeout=10)
            assert first_response.status_code == 200
            assert '"type": "error"' in first_response.text or '"type":"error"' in (
                first_response.text
            )
            assert provider_creators == ["n@example.test"]
            resumed_z = asyncio.create_task(z.post("/api/projects/papers", json=z_body))
            for _ in range(300):
                state = await z.get(
                    "/api/projects/papers/progress",
                    params={"path": path, "run_id": runs["z@example.test"]},
                )
                if (
                    state.status_code == 200
                    and state.json()["progress"]
                    and (state.json()["progress"]["status"] == "queued")
                ):
                    break
                await asyncio.sleep(0.01)
            else:
                raise AssertionError("Resumed Z run never reentered FIFO queue")
            release_n.set()
            # Expected fault injection must not litter successful CI logs.
            # Assert the exact failure was recorded; any unrelated errors
            # remain test failures rather than being silently ignored.
            with patch.object(logging.getLogger("sigma.lifecycle"), "error") as captured:
                first_resume_result = await asyncio.wait_for(resumed_z, timeout=180)
            assert len(captured.call_args_list) == 1, captured.call_args_list
            expected_error = captured.call_args_list[0].args
            assert expected_error[0].startswith("paper.exception "), expected_error
            assert expected_error[3] == "ProjectError", expected_error
            assert first_resume_result.status_code == 200, first_resume_result.text
            assert (
                '"type": "error"' in first_resume_result.text
                or '"type":"error"' in first_resume_result.text
            ), first_resume_result.text[-1000:]
            assert injected_compile_failure
            assert provider_creators == ["n@example.test", "z@example.test"]
            # Recover the accepted Z author draft, rather than repeating an
            # uncertain paid request after a compiler-only failure.
            z_principal = cloud_auth.Principal("google-z", "z@example.test", "member")
            workspace_token = cloud_workspaces.bind(z_principal)
            principal_token = cloud_auth._CURRENT_PRINCIPAL.set(z_principal)
            try:
                with papers.paper_run_scope(runs["z@example.test"]):
                    checkpoint = papers._load_work(path)
                assert checkpoint is not None
                assert checkpoint.get("one_shot_draft")
                assert checkpoint["provider_calls"] == 1
            finally:
                cloud_auth._CURRENT_PRINCIPAL.reset(principal_token)
                cloud_workspaces.reset(workspace_token)
            z_result = await z.post("/api/projects/papers", json=z_body)
            assert z_result.status_code == 200, z_result.text
            assert '"type": "complete"' in z_result.text or '"type":"complete"' in z_result.text
            assert provider_creators == ["n@example.test", "z@example.test"]

            for _ in range(300):
                listed = await n.get("/api/projects/papers", params={"path": path})
                rows = {item["run_id"]: item for item in listed.json()["runs"]}
                if all(rows[run]["status"] == "complete" for run in runs.values()):
                    break
                await asyncio.sleep(0.02)
            else:
                raise AssertionError("Both original runs did not finish as published Papers")

            assert provider_creators == ["n@example.test", "z@example.test"]
            assert len(scoring_ids) == 2 and len(set(scoring_ids)) == 2
            assert real_compilations >= 2, real_compilations
            paper_ids = [rows[run]["paper_id"] for run in runs.values()]
            assert len(set(paper_ids)) == 2 and all(paper_ids)
            saved_papers = listed.json()["papers"]
            assert {p["paper_id"] for p in saved_papers} == set(paper_ids)
            pdf_hashes = set()
            for creator, run_id in runs.items():
                row = rows[run_id]
                assert row["creator_email"] == creator
                assert row["artifact_id"] == row["paper_id"]
                assert row["status"] == "complete"
                assert row["progress"]["stage"] == "complete"
                assert row["number"] == next(
                    item["paper_version"]
                    for item in saved_papers
                    if item["paper_id"] == row["paper_id"]
                )
                record_response = await z.get(
                    f"/api/projects/papers/{row['paper_id']}", params={"path": path}
                )
                assert record_response.status_code == 200, record_response.text
                record = record_response.json()
                assert record["created_by"] == creator
                assert record["paper_version"] == row["number"]
                assert record["generation"]["progress_run_id"] == run_id
                assert record["snapshot_sha256"] == digest
                assert record["pdf_available"] is True
                pdf_response = await n.get(
                    f"/api/projects/papers/{row['paper_id']}/pdf",
                    params={"path": path},
                )
                assert pdf_response.status_code == 200, pdf_response.text[:200]
                assert pdf_response.headers["content-type"] == "application/pdf"
                assert f"-v{row['number']}.pdf" in pdf_response.headers["content-disposition"]
                pdf_bytes = pdf_response.content
                assert pdf_bytes.startswith(b"%PDF-") and len(pdf_bytes) > 1000
                assert hashlib.sha256(pdf_bytes).hexdigest() == record["pdf_sha256"]
                pdf_hashes.add(record["pdf_sha256"])
                document = pypdfium2.PdfDocument(pdf_bytes)
                assert len(document) > 0
                text = " ".join(
                    document[index].get_textpage().get_text_range()
                    for index in range(len(document))
                )
                assert "Independent Paper" in text
                assert creator in text
                with patch.object(papers, "_provider", side_effect=AssertionError("replayed")):
                    # A completed Paper cannot silently spend again on a reused run ID.
                    duplicate = await (n if creator == "n@example.test" else z).post(
                        "/api/projects/papers", json={**request_data, "run_id": run_id}
                    )
                assert duplicate.status_code in (400, 403, 409), duplicate.text
            assert len(pdf_hashes) == 2
            assert not papers._paper_waiters
            assert not papers._generating_paper_projects


def main() -> None:
    if shutil.which(os.environ.get("SIGMA_TECTONIC", "tectonic")) is None:
        if os.environ.get("SIGMA_REQUIRE_REAL_PAPER_PDF") == "1":
            raise AssertionError("Real Paper acceptance requires installed Tectonic")
        print("SKIP real Paper PDF acceptance: Tectonic not installed")
        return
    with TemporaryDirectory(prefix="sigma-paper-two-actor-") as temp:
        root = Path(temp)
        root.chmod(0o700)
        for name in ("workspaces", "local-projects", "local-state"):
            (root / name).mkdir(mode=0o700)
        environment = {
            "SIGMA_CLOUD_AUTH_ENABLED": "true",
            "SIGMA_REFERENCE_COMPILATION_ENABLED": "false",
            "GOOGLE_OIDC_CLIENT_ID": "fixture.apps.googleusercontent.com",
            "GOOGLE_OIDC_CLIENT_SECRET": "fixture-secret",
            "SIGMA_CLOUD_PUBLIC_ORIGIN": "https://sigma.test",
            "SIGMA_CLOUD_ADMIN_CONTACT_EMAIL": "admin@example.test",
            "SIGMA_CLOUD_AUTH_HOME": str(root / "auth"),
            "SIGMA_CLOUD_WORKSPACES_ROOT": str(root / "workspaces"),
            "SIGMA_PROJECTS_ROOT": str(root / "local-projects"),
            "SIGMA_STATE_DIR": os.environ.get(
                "SIGMA_TEST_SHARED_TECTONIC_STATE", str(root / "local-state")
            ),
            "SIGMA_CLOUD_OPENAI_API_KEY": "fake-server-credential",
            "SIGMA_CLOUD_INFERENCE_PROVIDER": "api_key",
            "SIGMA_CLOUD_GLOBAL_SPEND_CEILING_USD": "1.00",
            "SIGMA_CLOUD_USER_SPEND_CEILING_USD": "1.00",
        }
        with patch.dict(os.environ, environment):
            from cloud_workspace_test_app import app

            from sigma import api, cloud_auth, cloud_workspaces, papers, project_collaboration

            asyncio.run(
                exercise(app, api, papers, cloud_auth, cloud_workspaces, project_collaboration)
            )
    print("PASS: two authenticated creators, queue/Stop/Resume/disconnect, two real PDFs")


if __name__ == "__main__":
    main()
