"""Two-subject production API isolation, restart, revocation, and restore test."""

import asyncio
import os
import shutil
import socket
import subprocess
import sys
import time
from datetime import UTC, datetime
from pathlib import Path
from tempfile import TemporaryDirectory
from uuid import uuid4

import httpx


def storage_root_for_test(root: Path) -> Path:
    if os.environ.get("SIGMA_T100_PERSISTENT_DISK") == "1":
        disk = root / "persistent-disk"
        disk.mkdir(mode=0o700, exist_ok=True)
        return disk
    return root


def workspaces_root_for_test(root: Path) -> Path:
    return storage_root_for_test(root) / "workspaces"


def free_port() -> int:
    with socket.socket() as listener:
        listener.bind(("127.0.0.1", 0))
        return int(listener.getsockname()[1])


class Server:
    def __init__(self, root: Path):
        self.root = root
        self.port = free_port()
        self.url = f"http://127.0.0.1:{self.port}"
        self.log = (root / f"server-{self.port}.log").open("wb")
        environment = os.environ.copy()
        environment.update(
            {
                "SIGMA_CLOUD_AUTH_ENABLED": "true",
                "SIGMA_CLOUD_WORKSPACES_ROOT": str(root / "workspaces"),
                "SIGMA_PROJECTS_ROOT": str(root / "local-projects"),
                "SIGMA_STATE_DIR": str(root / "shared-local-state"),
            }
        )
        if os.environ.get("SIGMA_T100_PERSISTENT_DISK") == "1":
            persistent_root = storage_root_for_test(root)
            environment.update(
                {
                    "SIGMA_STORAGE_BACKEND": "persistent_disk",
                    "SIGMA_STORAGE_ROOT": str(persistent_root),
                    "SIGMA_CLOUD_WORKSPACES_ROOT": str(persistent_root / "workspaces"),
                    "GOOGLE_OIDC_CLIENT_ID": "fixture.apps.googleusercontent.com",
                    "GOOGLE_OIDC_CLIENT_SECRET": "fixture-secret",
                    "SIGMA_CLOUD_PUBLIC_ORIGIN": "https://sigma.test",
                    "SIGMA_CLOUD_ADMIN_CONTACT_EMAIL": "admin@example.test",
                }
            )
        test_path = os.pathsep.join(
            (str(Path(__file__).parent), str(Path(__file__).parents[1] / "src"))
        )
        environment["PYTHONPATH"] = test_path + os.pathsep + environment.get("PYTHONPATH", "")
        self.process = subprocess.Popen(
            [
                sys.executable,
                "-m",
                "uvicorn",
                "cloud_workspace_test_app:app",
                "--host",
                "127.0.0.1",
                "--port",
                str(self.port),
                "--log-level",
                "error",
            ],
            cwd=Path(__file__).parents[1],
            env=environment,
            stdout=self.log,
            stderr=subprocess.STDOUT,
        )
        deadline = time.monotonic() + 15
        while time.monotonic() < deadline:
            if self.process.poll() is not None:
                break
            try:
                response = httpx.get(f"{self.url}/api/ui-instance", timeout=0.25)
                if response.status_code == 200:
                    return
            except httpx.HTTPError:
                time.sleep(0.05)
        output = (root / f"server-{self.port}.log").read_text(errors="replace")
        self.stop()
        raise AssertionError(f"API test server failed to start:\n{output}")

    def stop(self) -> None:
        if self.process.poll() is None:
            self.process.terminate()
            try:
                self.process.wait(timeout=10)
            except subprocess.TimeoutExpired:
                self.process.kill()
                self.process.wait(timeout=5)
        self.log.close()


def identity(subject: str, *, email: str | None = None, role: str = "member") -> dict[str, str]:
    return {
        "X-Test-Subject": subject,
        # The OIDC subject is opaque and intentionally not the user email.
        # Attribution may persist a verified email; the subject must stay hashed.
        "X-Test-Email": email or f"account-{subject.rsplit('-', 1)[-1]}@example.test",
        "X-Test-Role": role,
    }


def expect_hidden(response: httpx.Response) -> None:
    assert response.status_code == 404, (response.status_code, response.text)
    assert response.json() == {"error": "Project not found or access denied."}, response.text


def request(client: httpx.Client, method: str, path: str, **kwargs) -> httpx.Response:
    response = client.request(method, path, **kwargs)
    assert response.status_code < 500, (method, path, response.status_code, response.text)
    return response


def check_proposal_cancellation_scope() -> None:
    """A guessed cancellation UUID in B cannot cancel A's in-flight proposal."""
    from sigma import cloud_workspaces, proposals

    async def exercise_cancel_scope() -> None:
        request_id = str(uuid4())
        task = asyncio.create_task(asyncio.Event().wait())
        first = cloud_workspaces.Workspace("a" * 32, "a" * 64, Path("/workspace-a"))
        second = cloud_workspaces.Workspace("b" * 32, "b" * 64, Path("/workspace-b"))
        token = cloud_workspaces._CURRENT.set(first)
        proposals.register_request(request_id, task)
        cloud_workspaces.reset(token)
        try:
            token = cloud_workspaces._CURRENT.set(second)
            try:
                assert not await proposals.cancel_request(request_id)
                assert not task.cancelled()
            finally:
                cloud_workspaces.reset(token)
            token = cloud_workspaces._CURRENT.set(first)
            try:
                assert await proposals.cancel_request(request_id)
                assert task.cancelling()
                proposals.unregister_request(request_id, task)
            finally:
                cloud_workspaces.reset(token)
        finally:
            task.cancel()
            await asyncio.gather(task, return_exceptions=True)

    asyncio.run(exercise_cancel_scope())


def project_document_bytes(path: str | Path) -> bytes:
    """Read the authoritative project document from legacy or bundled storage."""
    target = Path(path)
    if target.suffix == ".json":
        from sigma.project_bundle import read_file

        return read_file(target, "project.json")
    return (target / "project.json").read_bytes()


def exercise(root: Path) -> tuple[str, str, str, str, str, str, str]:
    server = Server(root)
    try:
        with (
            httpx.Client(base_url=server.url, headers=identity("subject-a")) as user_a,
            httpx.Client(base_url=server.url, headers=identity("subject-b")) as user_b,
            httpx.Client(
                base_url=server.url, headers=identity("subject-admin", role="admin")
            ) as admin,
        ):
            # The first authorized project-list request provisions two empty,
            # independent roots; it does not seed the existing local project.
            a_empty = request(user_a, "GET", "/api/projects/recent").json()["projects"]
            b_empty = request(user_b, "GET", "/api/projects/recent").json()["projects"]
            assert a_empty == [] and b_empty == []
            workspaces = workspaces_root_for_test(root)
            database = workspaces / "workspaces.sqlite3"
            import sqlite3

            with sqlite3.connect(database) as db:
                rows = db.execute(
                    "SELECT subject_hash,workspace_id FROM workspaces ORDER BY workspace_id"
                ).fetchall()
            assert len(rows) == 2 and rows[0][0] != rows[1][0]
            workspace_a, workspace_b = (workspaces / row[1] for row in rows)
            assert workspace_a != workspace_b
            assert list(workspace_a.iterdir()) and list(workspace_b.iterdir())
            assert not any(path.suffix == ".sigma" for path in workspace_a.iterdir())
            assert not any(path.suffix == ".sigma" for path in workspace_b.iterdir())

            # Project types belong to the authenticated workspace, never a
            # shared catalog or path selected by the request.
            a_catalog = request(user_a, "GET", "/api/project-types").json()
            b_catalog = request(user_b, "GET", "/api/project-types").json()
            private_type = {
                "id": "workspace-a-custom",
                "name": "Workspace A custom",
                "scope": "A only",
                "description": "",
                "based_on": "literature",
                "origin": None,
                "user_defined": True,
                "icon": a_catalog["icons"]["placeholder"],
                "research_standards_references": [],
                "publication_standards_references": [],
                "behavior": {},
            }
            saved_types = request(
                user_a,
                "PUT",
                "/api/project-types",
                json={
                    "project_types": [private_type],
                    "expected_revision": a_catalog["revision"],
                },
            )
            assert saved_types.status_code == 200, saved_types.text
            assert all(item["id"] != private_type["id"] for item in b_catalog["project_types"])
            denied_delete = request(
                user_b,
                "DELETE",
                f"/api/project-types/{private_type['id']}",
                json={
                    "confirm": True,
                    "expected_project_count": 0,
                    "expected_revision": b_catalog["revision"],
                },
            )
            assert denied_delete.status_code == 400
            assert all(
                item["id"] != private_type["id"]
                for item in request(user_b, "GET", "/api/project-types").json()["project_types"]
            )

            # Account A deliberately enables the two curated Common URLs in
            # each category; B retains defaults and disables only Math publication.
            common = a_catalog["common_references"]
            a_pref = request(
                user_a,
                "PUT",
                "/api/project-types",
                json={
                    "project_types": [private_type],
                    "expected_revision": saved_types.json()["revision"],
                    "reference_preferences": {},
                },
            )
            assert a_pref.status_code == 200, a_pref.text
            math_publication = next(
                row for row in b_catalog["project_types"] if row["id"] == "mathematical"
            )["publication_standards_references"][0]["url"]
            b_pref = request(
                user_b,
                "PUT",
                "/api/project-types",
                json={
                    "project_types": [],
                    "expected_revision": b_catalog["revision"],
                    "reference_preferences": {
                        "common": {
                            field: [ref["url"] for ref in common[field]]
                            for field in (
                                "research_standards_references",
                                "publication_standards_references",
                            )
                        },
                        "mathematical": {"publication_standards_references": [math_publication]},
                    },
                },
            )
            assert b_pref.status_code == 200, b_pref.text
            assert (
                request(user_a, "GET", "/api/project-types").json()["reference_preferences"] == {}
            )
            assert request(user_b, "GET", "/api/project-types").json()["reference_preferences"][
                "mathematical"
            ] == {"publication_standards_references": [math_publication]}

            local_project = root / "local-projects" / "local-only.sigma"
            assert (local_project / "project.json").is_file()
            hidden_local = request(
                user_a,
                "GET",
                "/api/projects/inspect",
                params={"path": str(local_project)},
            )
            expect_hidden(hidden_local)

            a_created = request(
                user_a,
                "POST",
                "/api/projects/create",
                json={
                    "title": "Workspace A project",
                    "problem": "A private question",
                    "investigation_type": private_type["id"],
                },
            )
            b_created = request(
                user_b,
                "POST",
                "/api/projects/create",
                json={"title": "Workspace B project", "problem": "B private question"},
            )
            assert a_created.status_code == 201 and b_created.status_code == 201
            a_project = a_created.json()
            b_project = b_created.json()
            a_path, b_path = a_project["path"], b_project["path"]
            a_id, b_id = a_project["project"]["id"], b_project["project"]["id"]
            # The derived Literature project type freezes 2 Common + 1
            # discipline source for research and publication under A.
            for field in ("research_standards_references", "publication_standards_references"):
                actual = a_project["project"]["project_type_snapshot"][field]
                curated = {row["url"] for row in common[field]} | {
                    next(row for row in a_catalog["project_types"] if row["id"] == "literature")[
                        field
                    ][0]["url"]
                }
                assert len(actual) == len(curated) == 3
                assert {row["url"] for row in actual} == curated
            assert a_id != b_id and Path(a_path).parent != Path(b_path).parent
            from sigma import papers

            paper_id = uuid4().hex
            paper_pdf = b"%PDF-1.4\n% T100 deterministic persistence fixture\n%%EOF\n"
            papers._save(
                a_path,
                {
                    "paper_id": paper_id,
                    "project_id": a_id,
                    "created_at": datetime.now(UTC).isoformat(),
                    "snapshot_sha256": "a" * 64,
                    "draft": {
                        "title": "T100 private paper fixture",
                        "abstract": "Saved text",
                        "problem_framing": [],
                        "methods": [],
                        "sections": [],
                        "claims": [],
                        "limitations": [],
                        "open_obligations": [],
                        "conclusions": [],
                    },
                    "validation_warnings": [],
                    "generation": {},
                    "source": {"fixture": "deterministic storage-only source"},
                },
                paper_pdf,
            )
            listed_papers = request(user_a, "GET", "/api/projects/papers", params={"path": a_path})
            assert listed_papers.status_code == 200
            assert listed_papers.json()["papers"][0]["pdf_available"] is True
            paper_record = request(
                user_a, "GET", f"/api/projects/papers/{paper_id}", params={"path": a_path}
            )
            assert paper_record.status_code == 200
            assert paper_record.json()["source"]["fixture"] == "deterministic storage-only source"
            paper_download = request(
                user_a,
                "GET",
                f"/api/projects/papers/{paper_id}/pdf",
                params={"path": a_path},
            )
            assert paper_download.content == paper_pdf
            assert "attachment" in paper_download.headers["content-disposition"]
            inline_download = request(
                user_a,
                "GET",
                f"/api/projects/papers/{paper_id}/pdf",
                params={"path": a_path, "open_in_browser": "true"},
            )
            assert inline_download.content == paper_pdf
            assert "inline" in inline_download.headers["content-disposition"]
            paper_text = request(
                user_a, "GET", f"/api/projects/papers/{paper_id}/txt", params={"path": a_path}
            )
            assert paper_text.status_code == 200 and "Saved text" in paper_text.text
            assert "text/plain" in paper_text.headers["content-type"]
            assert "attachment" in paper_text.headers["content-disposition"]
            expect_hidden(
                request(
                    user_b,
                    "GET",
                    f"/api/projects/papers/{paper_id}/pdf",
                    params={"path": a_path},
                )
            )
            expect_hidden(
                request(
                    user_b,
                    "DELETE",
                    f"/api/projects/papers/{paper_id}",
                    params={"path": a_path},
                )
            )
            assert (
                papers.get_paper(a_path, paper_id)["draft"]["title"] == "T100 private paper fixture"
            )
            deleted = request(
                user_a,
                "DELETE",
                f"/api/projects/papers/{paper_id}",
                params={"path": a_path},
            )
            assert deleted.status_code == 200 and deleted.json()["deleted"] == paper_id
            assert len(papers.list_papers(a_path)) == 0
            assert Path(a_path).exists()
            papers._save(
                a_path,
                {
                    "paper_id": paper_id,
                    "project_id": a_id,
                    "created_at": datetime.now(UTC).isoformat(),
                    "snapshot_sha256": "a" * 64,
                    "draft": {
                        "title": "T100 private paper fixture",
                        "abstract": "Saved text",
                        "problem_framing": [],
                        "methods": [],
                        "sections": [],
                        "claims": [],
                        "limitations": [],
                        "open_obligations": [],
                        "conclusions": [],
                    },
                    "validation_warnings": [],
                    "generation": {},
                    "source": {"fixture": "deterministic storage-only source"},
                },
                paper_pdf,
            )
            inference_body = {
                "path": a_path,
                "seed": "Generate a short proposal",
                "expected_binding": "unused-in-cloud-mode",
                "expected_project_id": a_id,
            }
            for endpoint, body in (
                ("/api/projects/proposals", inference_body),
                ("/api/projects/proposals/agentic", inference_body),
                (
                    "/api/projects/papers",
                    {
                        "path": a_path,
                        "expected_binding": "unused",
                        "expected_project_id": a_id,
                        "expected_snapshot_sha256": "0" * 64,
                    },
                ),
                (
                    "/api/projects/text/convert",
                    {
                        "path": a_path,
                        "scope": "problem",
                        "target": "plain_text",
                        "expected_digest": "0" * 64,
                    },
                ),
            ):
                blocked = request(user_a, "POST", endpoint, json=body)
                assert blocked.status_code == 403, (endpoint, blocked.status_code, blocked.text)

            # Subjects, not mutable emails or administrator roles, determine
            # ownership. Email changes retain the same workspace; an admin is
            # otherwise just another private workspace.
            changed_email = httpx.Client(
                base_url=server.url,
                headers=identity("subject-a", email="changed@example.test"),
            )
            try:
                assert (
                    request(changed_email, "GET", "/api/projects/recent").json()["projects"][0][
                        "id"
                    ]
                    == a_id
                )
            finally:
                changed_email.close()
            assert request(admin, "GET", "/api/projects/recent").json()["projects"] == []
            assert (
                request(user_a, "GET", "/api/projects/recent").json()["projects"][0]["id"] == a_id
            )
            assert (
                request(user_b, "GET", "/api/projects/recent").json()["projects"][0]["id"] == b_id
            )

            b_strategy = request(
                user_b,
                "POST",
                "/api/projects/strategies",
                json={"path": b_path, "title": "B strategy", "approach": "B only"},
            )
            assert b_strategy.status_code == 201
            strategy_id = b_strategy.json()["project"]["strategies"][0]["id"]
            b_project_before_denials = project_document_bytes(b_path)

            # Actual execution service writes the record and binary artifact to
            # the owning project; the test runtime is deterministic and local.
            execution_response = request(
                user_b,
                "POST",
                "/api/projects/research-executions",
                json={"path": b_path, "source": "print('evidence')"},
            )
            assert execution_response.status_code == 201, execution_response.text
            execution_id = execution_response.json()["id"]
            failed_execution = request(
                user_b,
                "POST",
                "/api/projects/research-executions",
                json={"path": b_path, "source": "# deterministic failure"},
            )
            assert failed_execution.status_code == 201, failed_execution.text
            failed_execution_id = failed_execution.json()["id"]
            assert failed_execution.json()["status"] == "failed"
            assert failed_execution.json()["stderr"] == "fixture failure\n"
            artifact = request(
                user_b,
                "GET",
                f"/api/projects/research-executions/{execution_id}/artifacts/evidence.txt",
                params={"path": b_path},
            )
            assert artifact.content == b"persistent private artifact\n"
            execution_files_before_denials = {
                path.name: path.read_bytes()
                for path in (Path(b_path) / "research-executions").glob("*.json")
            }

            plain_export = user_b.get("/api/projects/export", params={"path": b_path})
            assert plain_export.status_code == 200, plain_export.text
            assert "diagnostics" not in plain_export.json()
            private_export = user_b.get(
                "/api/projects/export", params={"path": b_path, "diagnostics": True}
            )
            assert private_export.status_code == 200, private_export.text
            assert private_export.json()["diagnostics"]["private"] is True

            cross_reads = [
                user_a.get("/api/projects/inspect", params={"path": b_path}),
                user_a.post("/api/projects/open", json={"path": b_path}),
                user_a.get("/api/projects/strategies", params={"path": b_path}),
                user_a.get("/api/projects/export", params={"path": b_path}),
                user_a.get("/api/projects/export", params={"path": b_path, "diagnostics": True}),
                user_a.get("/api/projects/export/report", params={"path": b_path}),
                user_a.get("/api/projects/research-sessions", params={"path": b_path}),
                user_a.get(
                    "/api/projects/research-sessions/00000000000040008000000000000000",
                    params={"path": b_path},
                ),
                user_a.get("/api/projects/research-executions", params={"path": b_path}),
                user_a.get(
                    f"/api/projects/research-executions/{execution_id}", params={"path": b_path}
                ),
                user_a.get(
                    f"/api/projects/research-executions/{failed_execution_id}",
                    params={"path": b_path},
                ),
                user_a.get(
                    f"/api/projects/research-executions/{execution_id}/artifacts/evidence.txt",
                    params={"path": b_path},
                ),
                user_a.get("/api/projects/papers", params={"path": b_path}),
                user_a.get("/api/projects/events", params={"path": b_path}),
                user_a.get("/api/projects/text", params={"path": b_path, "scope": "project"}),
                user_a.get("/api/projects/proposals/config", params={"path": b_path}),
                user_a.get("/api/projects/proposals/agentic/runs", params={"path": b_path}),
                user_a.get(
                    "/api/projects/papers/00000000000040008000000000000000/pdf",
                    params={"path": b_path},
                ),
            ]
            assert all(response.status_code == 404 for response in cross_reads), [
                (response.status_code, response.text) for response in cross_reads
            ]
            for response in cross_reads:
                assert response.json() == {"error": "Project not found or access denied."}

            # A guessed user B project ID is scoped to user A's Recent index;
            # forgetting it cannot remove or reveal user B's entry.
            assert (
                request(
                    user_a,
                    "POST",
                    "/api/projects/recent/forget",
                    json={"project_id": b_id},
                ).status_code
                == 200
            )
            assert (
                request(user_b, "GET", "/api/projects/recent").json()["projects"][0]["id"] == b_id
            )

            cross_write = request(
                user_a,
                "POST",
                "/api/projects/strategies",
                json={"path": b_path, "title": "Injected", "approach": "No"},
            )
            expect_hidden(cross_write)
            # A rejected direct reference must not mutate the victim project,
            # even when the caller guesses an existing strategy ID.
            assert project_document_bytes(b_path) == b_project_before_denials
            denied_strategy_remove = request(
                user_a,
                "POST",
                "/api/projects/strategies/remove",
                json={"path": b_path, "strategy_id": strategy_id},
            )
            expect_hidden(denied_strategy_remove)
            # Exercise additional mutation families with a guessed victim path.
            # They must fail at project ownership before validating caller data,
            # starting a sandbox, or changing project/evidence bytes.
            denied_mutations = [
                user_a.post(
                    "/api/projects/update",
                    json={
                        "path": b_path,
                        "title": "Hijacked title",
                        "problem": "Hijacked question",
                        "investigation_type": "default",
                        "ai_model": "gpt-6.1-sol",
                        "reasoning_effort": "high",
                        "difficulty": "medium",
                        "expected": {
                            "title": "Workspace B project",
                            "problem": "B private question",
                            "investigation_type": "default",
                            "ai_model": "gpt-6.1-sol",
                            "reasoning_effort": "high",
                            "difficulty": "medium",
                        },
                    },
                ),
                user_a.post(
                    "/api/projects/text/source",
                    json={
                        "path": b_path,
                        "scope": "project",
                        "body": "cross-account injected source",
                        "format": "markdown",
                        "expected_digest": "0" * 64,
                    },
                ),
                user_a.post(
                    "/api/projects/research-executions",
                    json={"path": b_path, "source": "open('/etc/passwd').read()"},
                ),
            ]
            for denied in denied_mutations:
                expect_hidden(denied)
            assert project_document_bytes(b_path) == b_project_before_denials
            assert {
                path.name: path.read_bytes()
                for path in (Path(b_path) / "research-executions").glob("*.json")
            } == execution_files_before_denials
            assert not (Path(b_path) / "text-sources").exists()
            owner_strategy = request(
                user_b, "GET", "/api/projects/strategies", params={"path": b_path}
            )
            assert owner_strategy.status_code == 200
            assert owner_strategy.json()["strategies"][0]["id"] == strategy_id
            limits = request(
                user_a,
                "PUT",
                "/api/projects/research-limits",
                json={
                    "path": b_path,
                    "research_rounds": 1,
                    "model_calls": 2,
                    "session_duration_minutes": 1,
                    "output_tokens_per_call": 256,
                    "maximum_estimated_cost_usd": None,
                },
            )
            expect_hidden(limits)
            remove_cross = request(
                user_a,
                "POST",
                "/api/projects/strategies/remove",
                json={"path": b_path, "strategy_id": strategy_id},
            )
            expect_hidden(remove_cross)

            traversal = str(
                Path(a_path).parent / ".." / Path(b_path).parent.name / Path(b_path).name
            )
            expect_hidden(
                request(user_a, "GET", "/api/projects/inspect", params={"path": traversal})
            )
            symlink = Path(a_path).parent / "copied-path.sigma"
            symlink.symlink_to(Path(b_path), target_is_directory=True)
            expect_hidden(
                request(user_a, "GET", "/api/projects/inspect", params={"path": str(symlink)})
            )
            parent_link = Path(a_path).parent / "linked"
            parent_link.symlink_to(Path(b_path).parent, target_is_directory=True)
            expect_hidden(
                request(
                    user_a,
                    "GET",
                    "/api/projects/inspect",
                    params={"path": str(parent_link / Path(b_path).name)},
                )
            )

            # A forged request with no validated principal fails closed.
            unauthenticated = httpx.get(f"{server.url}/api/projects/recent", timeout=5)
            assert unauthenticated.status_code == 401, unauthenticated.text
            revoked = httpx.get(
                f"{server.url}/api/projects/recent",
                headers={**identity("subject-a"), "X-Test-Revoked": "true"},
                timeout=5,
            )
            assert revoked.status_code == 401
            assert bool(project_document_bytes(a_path))
            assert (
                request(user_a, "GET", "/api/projects/recent").json()["projects"][0]["id"] == a_id
            )

            db_bytes = (workspaces / "workspaces.sqlite3").read_bytes()
            assert b"subject-a" not in db_bytes and b"subject-b" not in db_bytes
            assert stat_mode(workspaces) == 0o700
            assert stat_mode(Path(a_path).parent) == 0o700
            assert stat_mode(workspaces / "workspaces.sqlite3") == 0o600
            return a_id, b_id, execution_id, b_path, a_path, paper_id, private_type["id"]
    finally:
        server.stop()


def stat_mode(path: Path) -> int:
    import stat

    return stat.S_IMODE(path.stat().st_mode)


def check_private_diagnostic_api(
    owner: httpx.Client, other: httpx.Client, source: str, source_id: str
) -> None:
    """Exercise actual authenticated transfer and Save As with nonempty history."""
    import base64
    import hashlib
    import json
    import zlib

    from sigma import project_bundle, project_diagnostic_bundle, project_transfer, session_log

    source_path = Path(source)
    session_id, step_id = str(uuid4()), str(uuid4())
    strategy = request(owner, "GET", "/api/projects/strategies", params={"path": source}).json()[
        "strategies"
    ][0]
    context = {"context_manifest": {"sources": [{"status": "retrieved"}]}}
    body = {
        "model": "fixture-model",
        "input": json.dumps(context),
        "instructions": "Synthetic research only.",
        "store": False,
    }
    body_bytes = json.dumps(body, separators=(",", ":")).encode()
    audit = {
        "version": 1,
        "kind": "exact_provider_request_body",
        "status": "prepared_before_dispatch",
        "headers_included": False,
        "encoding": "zlib+base64-json",
        "request_body_sha256": hashlib.sha256(body_bytes).hexdigest(),
        "request_body_bytes": len(body_bytes),
        "request_body_compressed": base64.b64encode(zlib.compress(body_bytes)).decode(),
    }
    record = {
        "schema_version": 1,
        "id": session_id,
        "project_id": source_id,
        "project_path": source,
        "session_number": 1,
        "strategy_id": strategy["id"],
        "strategy_title": strategy["title"],
        "status": "stopped",
        "model": "fixture-model",
        "mode": "mock",
        "reasoning_effort": "low",
        "calls_used": 1,
        "call_limit": 2,
        "cycle": 1,
        "cycle_limit": 1,
        "artifacts": [],
        "events": [],
        "strategy_assessments": [],
        "interventions": [{"id": str(uuid4()), "text": "Check the saved premise."}],
        "supervisor_reviews": [
            {
                "status": "completed",
                "token_usage": {"input_tokens": 13, "output_tokens": 5},
            }
        ],
        "cost_status": "available",
        "steps": [
            {
                "id": step_id,
                "role": "investigator",
                "status": "completed",
                "strategy_id": strategy["id"],
                "provider_input_audit": audit,
                "context_manifest": context["context_manifest"],
                "token_usage": {"input_tokens": 40, "output_tokens": 12, "total_tokens": 52},
                "estimated_cost_usd": 0.001,
            }
        ],
    }
    sessions = source_path / "research-sessions"
    sessions.mkdir(exist_ok=True)
    checkpoint = sessions / f"{session_id}.json"
    checkpoint.write_text(json.dumps(record))
    before_checkpoint = checkpoint.read_bytes()

    log_context = {"project_id": source_id, "id": session_id, "session_number": 1}
    response = {
        "id": "synthetic-response",
        "status": "completed",
        "output": [
            {
                "type": "message",
                "role": "assistant",
                "content": [{"type": "output_text", "text": "Synthetic finding."}],
            }
        ],
        "usage": {"input_tokens": 40, "output_tokens": 12, "total_tokens": 52},
        "metadata": {"token": "synthetic-transport-secret"},
    }
    for event in (
        {
            "type": "provider_request",
            "request_id": "fixture-attempt",
            "step_id": step_id,
            "role": "investigator",
            "request": {**body, "headers": {"Authorization": "Bearer synthetic-header"}},
        },
        {
            "type": "provider_response",
            "request_id": "fixture-attempt",
            "step_id": step_id,
            "response": response,
            "response_wire": json.dumps(response),
            "usage": response["usage"],
            "estimated_cost_usd": 0.001,
        },
        {
            "type": "provider_failure",
            "request_id": "fixture-retry",
            "status": "timeout",
            "elapsed_seconds": 0.5,
        },
        {
            "type": "session_event",
            "event_kind": "supervisor.review",
            "role": "supervisor",
            "message": "Check the evidence.",
        },
    ):
        session_log.append(source, log_context, event)
    session_log.flush()
    log_root = source_path.parent / ".sigma-session-logs"
    source_log = log_root / source_id / f"{session_id}.md"
    before_log = source_log.read_bytes()

    for endpoint in ("/api/projects/export", "/api/projects/download"):
        expect_hidden(request(other, "GET", endpoint, params={"path": source, "diagnostics": True}))
        ordinary = request(owner, "GET", endpoint, params={"path": source}).json()
        assert "diagnostics" not in ordinary
    diagnostic = request(
        owner, "GET", "/api/projects/download", params={"path": source, "diagnostics": True}
    ).json()
    archive = diagnostic["diagnostics"]
    assert len(archive["blobs"]) == 1
    digest = archive["sessions"][session_id][0]
    decoded = project_transfer.decode_bundle(diagnostic)
    raw = decoded[f"{project_diagnostic_bundle.PREFIX}{session_id}/{digest}.bin"]
    snapshot = json.loads(raw)
    assert snapshot["availability"] == "retained"
    assert snapshot["saved_evidence"]["request_audits"] == 1
    assert snapshot["saved_evidence"]["interventions"] == 1
    assert snapshot["events"][0]["request"] == body
    assert snapshot["events"][1]["usage"] == response["usage"]
    assert snapshot["events"][1]["response"]["output"] == response["output"]
    assert snapshot["events"][2]["elapsed_seconds"] == 0.5
    assert snapshot["events"][3]["role"] == "supervisor"
    assert "security_or_schema_projection" in snapshot["events"][1]["omissions"]
    assert b"synthetic-header" not in raw and b"synthetic-transport-secret" not in raw
    assert checkpoint.read_bytes() == before_checkpoint
    assert source_log.read_bytes() == before_log

    # Public API rejects malformed reserved namespaces and duplicate mappings.
    malformed = {
        **ordinary,
        "files": {**ordinary["files"], "diagnostics/not-a-snapshot.bin": "invalid"},
    }
    rejected = request(owner, "POST", "/api/projects/import", json={"bundle": malformed})
    assert rejected.status_code == 400, rejected.text
    duplicate = {
        **diagnostic,
        "diagnostics": {**archive, "sessions": {session_id: [digest, digest]}},
    }
    rejected = request(owner, "POST", "/api/projects/import", json={"bundle": duplicate})
    assert rejected.status_code == 400, rejected.text
    imported = request(owner, "POST", "/api/projects/import", json={"bundle": diagnostic})
    assert imported.status_code == 201, imported.text
    imported_view = imported.json()
    target = imported_view["path"]
    target_id = imported_view["project"]["id"]
    assert target_id != source_id
    target_path = Path(target)
    assert not (log_root / target_id).exists()
    for endpoint in ("/api/projects/export", "/api/projects/download"):
        plain = request(owner, "GET", endpoint, params={"path": target}).json()
        assert "diagnostics" not in plain and not any(
            name.startswith("diagnostics/") for name in plain["files"]
        )
        expect_hidden(request(other, "GET", endpoint, params={"path": target, "diagnostics": True}))
    again = request(
        owner, "GET", "/api/projects/export", params={"path": target, "diagnostics": True}
    ).json()
    assert again["diagnostics"]["blobs"] == archive["blobs"]
    target_session = next(iter(again["diagnostics"]["sessions"]))
    assert target_session != session_id
    stored = target_path / "research-sessions" / f"{target_session}.json"
    restored = json.loads(stored.read_text())
    assert restored["status"] == "stopped" and restored["project_id"] == target_id
    assert restored["steps"][0]["provider_input_audit"] == audit
    assert restored["steps"][0]["context_manifest"] == context["context_manifest"]
    assert restored["interventions"] == record["interventions"]
    assert restored["supervisor_reviews"] == record["supervisor_reviews"]
    assert restored["steps"][0]["token_usage"] == record["steps"][0]["token_usage"]
    passive = target_path / f"{project_diagnostic_bundle.PREFIX}{target_session}/{digest}.bin"
    assert passive.read_bytes() == raw
    assert stat_mode(passive) == 0o600
    assert stat_mode(passive.parent) == 0o700
    assert stat_mode(passive.parent.parent) == 0o700
    assert stat_mode(target_path / "diagnostics") == 0o700
    assert not (log_root / target_id).exists(), "Passive export hydrated a live log"
    for path, identifier in ((source, session_id), (target, target_session)):
        saved_session = request(
            owner, "GET", f"/api/projects/research-sessions/{identifier}", params={"path": path}
        )
        assert saved_session.status_code == 200, saved_session.text
        saved = saved_session.json()
        assert saved["status"] == "stopped"
        assert saved["steps"][0]["provider_input_audit"]["request_body"] == body
        assert (
            saved["steps"][0]["provider_input_audit"]["request_body_sha256"]
            == (audit["request_body_sha256"])
        )
        assert saved["tokens_used"] == 70
    assert not (log_root / target_id).exists()

    # A trusted internal snapshot is deliberately different from outward transfer.
    with TemporaryDirectory() as temporary:
        backup = Path(temporary) / "restored.sigma"
        project_bundle.restore(project_bundle.snapshot(target_path), backup)
        restored_passive = backup / passive.relative_to(target_path)
        assert restored_passive.read_bytes() == raw and stat_mode(restored_passive) == 0o600
        assert "diagnostics" not in json.loads(project_transfer.export_project(backup))

    # Ordinary historical v4 roundtrip does not attach private evidence.
    ordinary_import = request(owner, "POST", "/api/projects/import", json={"bundle": plain})
    assert ordinary_import.status_code == 201, ordinary_import.text
    ordinary_target = Path(ordinary_import.json()["path"])
    assert not (ordinary_target / "diagnostics").exists()

    # Actual new recorder events on the imported session can coexist with
    # passive history. Save As copies both, with distinct live identities.
    target_context = {"project_id": target_id, "id": target_session, "session_number": 1}
    session_log.append(
        target,
        target_context,
        {
            "type": "session_event",
            "event_kind": "stopped",
            "project_id": target_id,
            "session_id": target_session,
            "message": "New local synthetic history.",
        },
    )
    session_log.flush()
    target_log = log_root / target_id / f"{target_session}.md"
    target_log_before = target_log.read_bytes()
    copied = request(
        owner, "POST", "/api/projects/save-as", json={"path": target, "title": "Diagnostic copy"}
    )
    assert copied.status_code == 201, copied.text
    copied_view = copied.json()
    copy_path = Path(copied_view["path"])
    copy_id = copied_view["project"]["id"]
    copied_export = request(
        owner,
        "GET",
        "/api/projects/export",
        params={"path": str(copy_path), "diagnostics": True},
    ).json()
    copied_archive = copied_export["diagnostics"]
    copy_session_id = next(iter(copied_archive["sessions"]))
    copy_session = copy_path / "research-sessions" / f"{copy_session_id}.json"
    assert copy_session_id not in {session_id, target_session}
    assert copy_id not in {source_id, target_id}
    assert digest in copied_archive["sessions"][copy_session_id]
    assert copied_archive["blobs"][digest] == archive["blobs"][digest]
    copy_log = log_root / copy_id / f"{copy_session_id}.md"
    cloned, _ = session_log._frames(copy_log)
    assert cloned[0]["project_id"] == copy_id and cloned[0]["session_id"] == copy_session_id
    assert cloned[0]["message"] == "New local synthetic history."
    assert json.loads(copy_session.read_text())["steps"][0]["provider_input_audit"] == audit
    assert target_log.read_bytes() == target_log_before
    assert passive.read_bytes() == raw and source_log.read_bytes() == before_log
    plain_copy = request(
        owner, "GET", "/api/projects/download", params={"path": str(copy_path)}
    ).json()
    assert "diagnostics" not in plain_copy
    expect_hidden(request(other, "GET", "/api/projects/download", params={"path": str(copy_path)}))
    print("PASS authenticated nonempty diagnostic transfer, private backup and Save As")


def main() -> None:
    check_proposal_cancellation_scope()
    with TemporaryDirectory(prefix="sigma-cloud-workspaces-") as temporary:
        root = Path(temporary)
        os.chmod(root, 0o700)
        local_root = root / "local-projects"
        local_root.mkdir(mode=0o700)
        (local_root / "local-only.sigma").mkdir(mode=0o700)
        (local_root / "local-only.sigma" / "project.json").write_text(
            "legacy local project sentinel", encoding="utf-8"
        )

        first_a, first_b, execution_id, b_path, a_path, paper_id, private_type_id = exercise(root)
        # Restart the real uvicorn process, then prove the same subject mapping,
        # recent index, session-independent execution record and bytes persist.
        restarted = Server(root)
        try:
            for subject, expected_id in (("subject-a", first_a), ("subject-b", first_b)):
                with httpx.Client(base_url=restarted.url, headers=identity(subject)) as client:
                    projects = request(client, "GET", "/api/projects/recent").json()["projects"]
                    assert [item["id"] for item in projects] == [expected_id]
            with httpx.Client(base_url=restarted.url, headers=identity("subject-b")) as user_b:
                saved = request(
                    user_b,
                    "GET",
                    f"/api/projects/research-executions/{execution_id}/artifacts/evidence.txt",
                    params={"path": b_path},
                )
                assert saved.content == b"persistent private artifact\n"
                assert all(
                    item["id"] != private_type_id
                    for item in request(user_b, "GET", "/api/project-types").json()["project_types"]
                )
                assert (
                    "mathematical"
                    in request(user_b, "GET", "/api/project-types").json()["reference_preferences"]
                )
            with httpx.Client(base_url=restarted.url, headers=identity("subject-a")) as user_a:
                paper = request(
                    user_a,
                    "GET",
                    f"/api/projects/papers/{paper_id}/pdf",
                    params={"path": a_path},
                )
                assert paper.content.startswith(b"%PDF-1.4") and paper.content.endswith(b"%%EOF\n")
                reloaded_types = request(user_a, "GET", "/api/project-types").json()[
                    "project_types"
                ]
                assert any(item["id"] == private_type_id for item in reloaded_types)
                reloaded_project = request(
                    user_a, "GET", "/api/projects/inspect", params={"path": a_path}
                ).json()
                assert reloaded_project["project"]["project_type_snapshot"]["id"] == private_type_id
                assert (
                    request(user_a, "GET", "/api/project-types").json()["reference_preferences"]
                    == {}
                )
                assert (
                    len(
                        reloaded_project["project"]["project_type_snapshot"][
                            "research_standards_references"
                        ]
                    )
                    == 3
                )
                assert (
                    len(
                        reloaded_project["project"]["project_type_snapshot"][
                            "publication_standards_references"
                        ]
                    )
                    == 3
                )
        finally:
            restarted.stop()

        # Documented backup/restore is an offline full-root copy with the service
        # stopped. Restore into a clean location and repeat tenant/artifact reads.
        backup = root / "backup-workspaces"
        restore = root / "restored-workspaces"
        workspaces_root = workspaces_root_for_test(root)
        shutil.copytree(workspaces_root, backup)
        shutil.copytree(backup, restore)
        workspaces_root.rename(workspaces_root.with_name("workspaces-original"))
        restore.rename(workspaces_root)
        restored = Server(root)
        try:
            for subject, expected_id in (("subject-a", first_a), ("subject-b", first_b)):
                with httpx.Client(base_url=restored.url, headers=identity(subject)) as client:
                    projects = request(client, "GET", "/api/projects/recent").json()["projects"]
                    assert [item["id"] for item in projects] == [expected_id]
            with httpx.Client(base_url=restored.url, headers=identity("subject-a")) as user_a:
                expect_hidden(
                    request(user_a, "GET", "/api/projects/inspect", params={"path": b_path})
                )
            with httpx.Client(base_url=restored.url, headers=identity("subject-b")) as user_b:
                response = request(
                    user_b,
                    "GET",
                    f"/api/projects/research-executions/{execution_id}/artifacts/evidence.txt",
                    params={"path": b_path},
                )
                assert response.content == b"persistent private artifact\n"
            with httpx.Client(base_url=restored.url, headers=identity("subject-a")) as user_a:
                paper = request(
                    user_a,
                    "GET",
                    f"/api/projects/papers/{paper_id}/pdf",
                    params={"path": a_path},
                )
                assert paper.content.startswith(b"%PDF-1.4") and paper.content.endswith(b"%%EOF\n")
            with (
                httpx.Client(base_url=restored.url, headers=identity("subject-a")) as user_a,
                httpx.Client(base_url=restored.url, headers=identity("subject-b")) as user_b,
            ):
                check_private_diagnostic_api(user_b, user_a, b_path, first_b)
        finally:
            restored.stop()

        print(
            "PASS two isolated workspaces; traversal/symlink/export/report/session/execution/artifact/paper access denied across owners; restart and backup/restore preserved owner mappings, paper source/PDF, execution artifacts and Recent indexes"
        )


if __name__ == "__main__":
    main()
