"""HTTP contract checks for the isolated prototype companion endpoints.

These are provider-free and use a fixture identity middleware. They verify
identity isolation at the application handler layer, not the Google OIDC flow.
"""
import os
from types import SimpleNamespace
from unittest import TestCase, main
from unittest.mock import patch

from fastapi import FastAPI, Request
from fastapi.testclient import TestClient

from sigma import cloud_auth, personal_companion_bridge as bridge
from sigma.personal_companion_api import router


class CompanionApiTests(TestCase):
    def setUp(self):
        self.flags = patch.dict(os.environ, {"SIGMA_PERSONAL_COMPANION_ENABLED": "true"})
        self.flags.start()
        self.addCleanup(self.flags.stop)
        bridge.clear_for_tests()
        self.addCleanup(bridge.clear_for_tests)
        self.config = patch.object(
            cloud_auth, "config", return_value=SimpleNamespace(enabled=True, error=None)
        )
        self.config.start()
        self.addCleanup(self.config.stop)
        self.model = patch.object(
            cloud_auth, "model_access_for_subject", return_value="personal"
        )
        self.model.start()
        self.addCleanup(self.model.stop)

        app = FastAPI()

        @app.middleware("http")
        async def fixture_identity(request: Request, call_next):
            subject = request.headers.get("x-fixture-identity")
            if subject:
                request.state.cloud_principal = cloud_auth.Principal(
                    subject, f"{subject}@example.test", "member"
                )
            return await call_next(request)

        app.include_router(router)
        self.client = TestClient(app)
        self.addCleanup(self.client.close)

    def test_pairing_and_job_isolation(self):
        headers_a = {"x-fixture-identity": "user-A"}
        headers_b = {"x-fixture-identity": "user-B"}
        self.assertEqual(self.client.post("/api/personal-companion/pair").status_code, 403)
        pairing = self.client.post("/api/personal-companion/pair", headers=headers_a)
        self.assertEqual(pairing.status_code, 200, pairing.text)
        code = pairing.json()["code"]
        paired = self.client.post("/api/personal-companion/worker/redeem", json={"code": code})
        self.assertEqual(paired.status_code, 200, paired.text)
        token = paired.json()["token"]
        self.assertEqual(
            self.client.post("/api/personal-companion/worker/redeem", json={"code": code}).status_code,
            403,
        )
        worker = {"Authorization": f"Bearer {token}"}
        self.assertEqual(
            self.client.post("/api/personal-companion/worker/heartbeat",
                             headers=worker, json={"ready": True, "label": "Chosen account"}).status_code,
            200,
        )
        self.assertTrue(self.client.get("/api/personal-companion/status", headers=headers_a).json()["ready"])
        self.assertFalse(self.client.get("/api/personal-companion/status", headers=headers_b).json()["ready"])
        submit = self.client.post("/api/personal-companion/test",
                                  headers=headers_a, json={"prompt": "One small test"})
        self.assertEqual(submit.status_code, 200, submit.text)
        job_id = submit.json()["job_id"]
        self.assertEqual(self.client.get(f"/api/personal-companion/test/{job_id}",
                                        headers=headers_b).status_code, 404)
        claimed = self.client.post("/api/personal-companion/worker/next", headers=worker, json={})
        self.assertEqual(claimed.json()["job"]["job_id"], job_id)
        self.assertIsNone(self.client.post(
            "/api/personal-companion/worker/next", headers=worker, json={}
        ).json()["job"])
        complete = self.client.post("/api/personal-companion/worker/complete", headers=worker,
                                    json={"job_id": job_id, "result": "Answer", "model": "gpt-6-luna"})
        self.assertEqual(complete.status_code, 200, complete.text)
        self.assertEqual(self.client.get(f"/api/personal-companion/test/{job_id}",
                                         headers=headers_a).json()["response"], "Answer")

    def test_authentication_and_provider_constraints(self):
        self.assertEqual(self.client.post(
            "/api/personal-companion/worker/next", json={}
        ).status_code, 401)
        with patch.object(cloud_auth, "model_access_for_subject", return_value="sponsored"):
            response = self.client.post(
                "/api/personal-companion/pair", headers={"x-fixture-identity": "user-A"}
            )
            self.assertEqual(response.status_code, 409)
        with patch.dict(os.environ, {"SIGMA_PERSONAL_COMPANION_ENABLED": "false"}):
            response = self.client.get(
                "/api/personal-companion/status", headers={"x-fixture-identity": "user-A"}
            )
            self.assertEqual(response.status_code, 404)


if __name__ == "__main__":
    main()
