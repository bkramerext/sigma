"""API-level authorization and path validation for saved Research Q/A."""

from __future__ import annotations

import os
from pathlib import Path
from tempfile import TemporaryDirectory
from unittest.mock import patch
from uuid import uuid4


def main() -> None:
    with TemporaryDirectory(prefix="sigma-research-qa-security-") as temporary:
        root = Path(temporary)
        root.chmod(0o700)
        for name in ("auth", "workspaces", "local-projects", "state"):
            (root / name).mkdir(mode=0o700)
        environment = {
            "SIGMA_CLOUD_AUTH_ENABLED": "true",
            "SIGMA_CLOUD_AUTH_LOCAL": "false",
            "GOOGLE_OIDC_CLIENT_ID": "fixture.apps.googleusercontent.com",
            "GOOGLE_OIDC_CLIENT_SECRET": "fixture-secret",
            "SIGMA_CLOUD_PUBLIC_ORIGIN": "https://sigma.test",
            "SIGMA_CLOUD_ADMIN_CONTACT_EMAIL": "admin@example.test",
            "SIGMA_CLOUD_AUTH_HOME": str(root / "auth"),
            "SIGMA_CLOUD_WORKSPACES_ROOT": str(root / "workspaces"),
            "SIGMA_PROJECTS_ROOT": str(root / "local-projects"),
            "SIGMA_STATE_DIR": str(root / "state"),
            "SIGMA_CLOUD_OPENAI_API_KEY": "fixture-provider-key",
            "SIGMA_CLOUD_INFERENCE_PROVIDER": "api_key",
        }
        with patch.dict(os.environ, environment, clear=False):
            import cloud_workspace_test_app
            from fastapi.testclient import TestClient

            from sigma import cloud_auth, cloud_workspaces, research_qa

            client = TestClient(cloud_workspace_test_app.app)
            user_a = {"x-test-subject": "qa-user-a"}
            user_b = {"x-test-subject": "qa-user-b"}
            created_a = client.post(
                "/api/projects/create",
                headers=user_a,
                json={"title": "Private A", "problem": "A research question"},
            )
            created_b = client.post(
                "/api/projects/create",
                headers=user_b,
                json={"title": "Private B", "problem": "B research question"},
            )
            assert created_a.status_code == created_b.status_code == 201
            a_project = created_a.json()
            b_project = created_b.json()
            a_path = a_project["path"]
            b_path = b_project["path"]
            project_id = b_project["project"]["id"]
            qa_id = uuid4().hex
            request_id = uuid4().hex
            record = {
                "qa_id": qa_id,
                "request_id": request_id,
                "project_id": project_id,
                "question": "B private question",
                "answer": "B private answer",
                "sources": [],
                "snapshot_sha256": "a" * 64,
                "evidence_snapshot": [],
                "created_at": "2026-10-31T00:00:00+00:00",
                "generation": {
                    "model": "fixture-model",
                    "reasoning_effort": "medium",
                    "mode": "api_key",
                    "generation_elapsed_seconds": 1,
                },
            }
            principal_b = cloud_auth.Principal("qa-user-b", "b@example.test", "member")
            token = cloud_workspaces.bind(principal_b)
            try:
                research_qa._save(b_path, [record])
                workspace_b = cloud_workspaces.current()
                assert workspace_b is not None
                link = workspace_b.path / "linked-project.sigma"
                link.symlink_to(Path(b_path), target_is_directory=True)
            finally:
                cloud_workspaces.reset(token)

            assert (
                client.get(
                    "/api/projects/research-qa", headers=user_b, params={"path": b_path}
                ).json()["answers"][0]["answer"]
                == "B private answer"
            )

            provider_calls = 0

            async def provider(*_args, **_kwargs):
                nonlocal provider_calls
                provider_calls += 1
                raise AssertionError("Unauthorized Q/A must not call the provider")

            generation = {
                "path": b_path,
                "expected_project_id": project_id,
                "expected_binding": "forged-connection",
                "request_id": uuid4().hex,
                "question": "Do not generate this",
            }
            unauthorized = [
                client.get("/api/projects/research-qa", params={"path": b_path}),
                client.get(f"/api/projects/research-qa/{qa_id}", params={"path": b_path}),
                client.delete(f"/api/projects/research-qa/{qa_id}", params={"path": b_path}),
                client.get(f"/api/projects/research-qa/{qa_id}/browser", params={"path": b_path}),
                client.post("/api/projects/research-qa", json=generation),
            ]
            assert [response.status_code for response in unauthorized] == [401] * 5

            with patch.object(research_qa.papers, "_provider_structured", new=provider):
                cross_user = [
                    client.get(
                        "/api/projects/research-qa", headers=user_a, params={"path": b_path}
                    ),
                    client.get(
                        f"/api/projects/research-qa/{qa_id}",
                        headers=user_a,
                        params={"path": b_path},
                    ),
                    client.delete(
                        f"/api/projects/research-qa/{qa_id}",
                        headers=user_a,
                        params={"path": b_path},
                    ),
                    client.get(
                        f"/api/projects/research-qa/{qa_id}/browser",
                        headers=user_a,
                        params={"path": b_path},
                    ),
                    client.post(
                        "/api/projects/research-qa",
                        headers=user_a,
                        json={**generation, "expected_project_id": a_project["project"]["id"]},
                    ),
                ]
                assert all(response.status_code in {400, 404} for response in cross_user)

                traversal = str(
                    Path(b_path).parent / ".." / Path(a_path).parent.name / Path(a_path).name
                )
                traversal_response = client.get(
                    "/api/projects/research-qa", headers=user_b, params={"path": traversal}
                )
                symlink_response = client.get(
                    "/api/projects/research-qa",
                    headers=user_b,
                    params={"path": str(link)},
                )
                assert traversal_response.status_code in {400, 404}
                assert symlink_response.status_code == 404

                forged_project = client.post(
                    "/api/projects/research-qa",
                    headers=user_b,
                    json={**generation, "expected_project_id": "forged-project"},
                )
                forged_binding = client.post(
                    "/api/projects/research-qa",
                    headers=user_b,
                    json={**generation, "expected_binding": "forged-connection"},
                )
                assert forged_project.status_code == 404
                assert forged_binding.status_code == 403

                oversized = client.post(
                    "/api/projects/research-qa",
                    headers=user_b,
                    json={**generation, "question": "x" * 4001},
                )
                assert oversized.status_code == 422

                for operation in ("get", "delete", "browser"):
                    response = (
                        client.get(
                            f"/api/projects/research-qa/not-a-valid-id{('/browser' if operation == 'browser' else '')}",
                            headers=user_b,
                            params={"path": b_path},
                        )
                        if operation in {"get", "browser"}
                        else client.delete(
                            "/api/projects/research-qa/not-a-valid-id",
                            headers=user_b,
                            params={"path": b_path},
                        )
                    )
                    assert response.status_code == 400
                assert provider_calls == 0

            owner_view = client.get(
                f"/api/projects/research-qa/{qa_id}",
                headers=user_b,
                params={"path": b_path},
            )
            assert owner_view.status_code == 200
            assert owner_view.json()["answer"] == "B private answer"
            assert (
                client.delete(
                    f"/api/projects/research-qa/{qa_id}",
                    headers=user_b,
                    params={"path": b_path},
                ).status_code
                == 200
            )
            assert (
                client.get(
                    "/api/projects/research-qa", headers=user_b, params={"path": b_path}
                ).json()["answers"]
                == []
            )
            client.close()

    print(
        "Research Q/A API security: unauthenticated/cross-user access, traversal/symlink paths, forged project/connection IDs, invalid IDs and oversized questions passed without provider calls."
    )


if __name__ == "__main__":
    main()
