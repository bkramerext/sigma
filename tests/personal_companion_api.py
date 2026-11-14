"""HTTP contract tests for the Personal companion prototype."""

import os
from types import SimpleNamespace
from unittest import TestCase, main
from unittest.mock import patch

from fastapi import FastAPI, Request
from fastapi.testclient import TestClient

from sigma import cloud_auth
from sigma import personal_companion_bridge as bridge
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
        self.model = patch.object(cloud_auth, "model_access_for_subject", return_value="personal")
        self.model.start()
        self.addCleanup(self.model.stop)

        app = FastAPI()

        @app.middleware("http")
        async def identity_fixture(request: Request, call_next):
            subject = request.headers.get("x-fixture-identity")
            if subject:
                request.state.cloud_principal = cloud_auth.Principal(
                    subject, f"{subject}@example.test", "member"
                )
            return await call_next(request)

        app.include_router(router)
        self.client = TestClient(app)
        self.addCleanup(self.client.close)

    def test_pairing_and_isolation(self):
        user_a = {"x-fixture-identity": "user-A"}
        user_b = {"x-fixture-identity": "user-B"}
        self.assertEqual(self.client.post("/api/personal-companion/pair").status_code, 403)

        pair = self.client.post("/api/personal-companion/pair", headers=user_a)
        self.assertEqual(pair.status_code, 200, pair.text)
        code = pair.json()["code"]
        redeemed = self.client.post("/api/personal-companion/worker/redeem", json={"code": code})
        self.assertEqual(redeemed.status_code, 200, redeemed.text)
        worker = {"Authorization": "Bearer " + redeemed.json()["token"]}
        again = self.client.post("/api/personal-companion/worker/redeem", json={"code": code})
        self.assertEqual(again.status_code, 403)
        heartbeat = self.client.post(
            "/api/personal-companion/worker/heartbeat",
            headers=worker,
            json={"ready": True, "label": "Chosen account"},
        )
        self.assertEqual(heartbeat.status_code, 200)
        state_a = self.client.get("/api/personal-companion/status", headers=user_a).json()
        state_b = self.client.get("/api/personal-companion/status", headers=user_b).json()
        self.assertTrue(state_a["ready"])
        self.assertFalse(state_b["ready"])

        submit = self.client.post(
            "/api/personal-companion/test", headers=user_a, json={"prompt": "One short test"}
        )
        self.assertEqual(submit.status_code, 200, submit.text)
        job_id = submit.json()["job_id"]
        hidden = self.client.get(f"/api/personal-companion/test/{job_id}", headers=user_b)
        self.assertEqual(hidden.status_code, 404)
        next_job = self.client.post(
            "/api/personal-companion/worker/next", headers=worker, json={}
        ).json()["job"]
        self.assertEqual(next_job["job_id"], job_id)
        repeat = self.client.post(
            "/api/personal-companion/worker/next", headers=worker, json={}
        ).json()
        self.assertIsNone(repeat["job"])
        completed = self.client.post(
            "/api/personal-companion/worker/complete",
            headers=worker,
            json={"job_id": job_id, "result": "Answer", "model": "gpt-6-luna"},
        )
        self.assertEqual(completed.status_code, 200, completed.text)
        saved = self.client.get(f"/api/personal-companion/test/{job_id}", headers=user_a)
        self.assertEqual(saved.json()["response"], "Answer")

    def test_rejects_unpaired_sponsored_and_disabled(self):
        no_token = self.client.post("/api/personal-companion/worker/next", json={})
        self.assertEqual(no_token.status_code, 401)
        with patch.object(cloud_auth, "model_access_for_subject", return_value="sponsored"):
            sponsored = self.client.post(
                "/api/personal-companion/pair", headers={"x-fixture-identity": "user-A"}
            )
            self.assertEqual(sponsored.status_code, 409)
        with patch.dict(os.environ, {"SIGMA_PERSONAL_COMPANION_ENABLED": "false"}):
            disabled = self.client.get(
                "/api/personal-companion/status", headers={"x-fixture-identity": "user-A"}
            )
            self.assertEqual(disabled.status_code, 404)


if __name__ == "__main__":
    main()
