"""Provider-free regression tests for the hosted Personal hotfix and Score visibility."""

from __future__ import annotations

import asyncio
import os
from types import SimpleNamespace
from unittest import TestCase, main
from unittest.mock import patch

from sigma import cloud_auth, papers, personal_browser, personal_inference, project_collaboration


class HostedPersonalHotfixTests(TestCase):
    def test_hosted_personal_requires_complete_explicit_configuration(self) -> None:
        configuration = SimpleNamespace(enabled=True, local=False, error=None)
        settings = {
            "SIGMA_PERSONAL_HOSTED_ENABLED": "1",
            "SIGMA_PERSONAL_SHARED_MODE": "1",
            "SIGMA_PERSONAL_BROWSER_LAB_ENABLED": "1",
            "SIGMA_PERSONAL_BROWSER_BROKER_SOCKET": "/run/sigma-personal-broker/broker.sock",
            "SIGMA_PERSONAL_BROWSER_GATEWAY_ROOT": "/run/sigma-personal-gateways",
            "SIGMA_AUTH_POC_RPC_SEED": "a" * 64,
        }
        with (
            patch.object(cloud_auth, "config", return_value=configuration),
            patch.dict(os.environ, settings, clear=True),
        ):
            self.assertTrue(cloud_auth.hosted_personal_enabled())
            for missing in settings:
                with self.subTest(missing=missing), patch.dict(os.environ, {missing: ""}):
                    self.assertFalse(cloud_auth.hosted_personal_enabled())
            with patch.dict(os.environ, {"SIGMA_AUTH_POC_RPC_SEED": "not-a-key"}):
                self.assertFalse(cloud_auth.hosted_personal_enabled())
            configuration.local = True
            self.assertFalse(cloud_auth.hosted_personal_enabled())

    def test_shared_verified_personal_is_not_synthetic_test_connection(self) -> None:
        # A real ChatGPT account is verified through /account, not the
        # synthetic /test-account endpoint. Confusing those signals made the
        # Personal pill take a test-mode branch instead of opening Disconnect,
        # preventing the switch back to Sponsored and a fresh connection.
        with (
            patch.dict(os.environ, {"SIGMA_PERSONAL_SHARED_MODE": "1"}),
            patch.object(personal_browser, "sign_in_preview_enabled", return_value=True),
            patch.object(personal_inference, "account") as account,
        ):
            verified = asyncio.run(personal_browser.test_account_verified(None))
        self.assertFalse(verified)
        account.assert_not_called()

    def test_completed_paper_does_not_hide_failed_scoring(self) -> None:
        path = "/tmp/sigma-hosted-personal-score-test.sigma"
        run_id = "f" * 32
        paper_id = "d" * 32
        row = {
            "run_id": run_id,
            "number": 2,
            "status": "complete",
            "artifact_id": paper_id,
            "creator_email": "author@example.test",
        }
        failure = "PDF generated; scoring did not finish. Use Score paper to retry."
        persisted = {
            "status": "complete",
            "stage": "complete",
            "paper_id": paper_id,
            "detail": failure,
        }
        with (
            patch.object(project_collaboration, "list_execution_runs", return_value=[row]),
            patch.object(
                project_collaboration, "collaborator_identity", return_value="author@example.test"
            ),
            patch.object(project_collaboration, "is_project_owner", return_value=True),
            patch.object(papers, "_read_progress_status", return_value=persisted) as status,
        ):
            result = papers.run_progress_list(path)
            self.assertEqual(result[0]["progress"]["detail"], failure)
            self.assertEqual(result[0]["progress"]["stage"], "complete")
            self.assertEqual(result[0]["status"], "complete")
            status.assert_called_once()
        with (
            patch.object(project_collaboration, "list_execution_runs", return_value=[row]),
            patch.object(
                project_collaboration, "collaborator_identity", return_value="author@example.test"
            ),
            patch.object(project_collaboration, "is_project_owner", return_value=True),
            patch.object(papers, "_read_progress_status", return_value=None),
        ):
            result = papers.run_progress_list(path)
            self.assertNotIn("detail", result[0]["progress"])

    def test_published_pdf_keeps_live_scoring_step_until_finalization(self) -> None:
        path = "/tmp/sigma-score-activity.sigma"
        run_id = "f" * 32
        paper_id = "d" * 32
        row = {
            "run_id": run_id,
            "number": 2,
            "status": "complete",
            "artifact_id": paper_id,
            "creator_email": "author@example.test",
        }
        key = f"{path}#paper:{run_id}"
        live = {"status": "running", "stage": "scoring", "run_id": run_id}
        with (
            patch.object(project_collaboration, "list_execution_runs", return_value=[row]),
            patch.object(
                project_collaboration, "collaborator_identity", return_value="author@example.test"
            ),
            patch.object(project_collaboration, "is_project_owner", return_value=True),
            patch.object(papers, "_read_progress_status", return_value=None),
            patch.dict(papers._active_progress, {key: live}),
        ):
            result = papers.run_progress_list(path)
        self.assertEqual(result[0]["status"], "active")
        self.assertEqual(result[0]["progress"]["stage"], "scoring")
        self.assertEqual(result[0]["progress"]["paper_id"], paper_id)


if __name__ == "__main__":
    main()
