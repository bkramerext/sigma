"""Regression coverage for published-paper recovery and activity propagation."""

from __future__ import annotations

from types import SimpleNamespace
from unittest import TestCase
from unittest.mock import patch
from uuid import uuid4

from sigma import papers, project_collaboration, recents, research_qa, research_sessions


class PublishedPaperProjectionTests(TestCase):
    def setUp(self) -> None:
        self.path = "/tmp/sigma-paper-projection"
        self.run_id = uuid4().hex
        self.paper_id = uuid4().hex
        self.author = "author@example.test"
        self.reservation = {
            "run_id": self.run_id,
            "number": 12,
            "creator_email": self.author,
            "runner_email": self.author,
            "model": "fixture-model",
            "thinking": "low",
            "status": "reserved",
            "artifact_id": None,
        }

    def test_interrupted_scoring_with_saved_pdf_is_a_published_paper(self) -> None:
        progress = {
            "status": "failed",
            "stage": "scoring",
            "paper_id": self.paper_id,
            "failure_reason": "Scoring provider disconnected",
        }
        saved = {
            "pdf_available": True,
            "pdf_sha256": "a" * 64,
            "paper_version": 12,
            "created_by": self.author,
        }
        with (
            patch.object(
                project_collaboration, "list_execution_runs", return_value=[self.reservation]
            ),
            patch.object(
                project_collaboration, "collaborator_identity", return_value=self.author
            ),
            patch.object(project_collaboration, "is_project_owner", return_value=True),
            patch.object(papers, "progress_status", return_value=progress),
            patch.object(papers, "needs_preflight_on_open", return_value=False),
            patch.object(papers, "get_paper", return_value=saved),
        ):
            run = papers.run_progress_list(self.path)[0]
        self.assertEqual(run["paper_id"], self.paper_id)
        self.assertEqual(run["status"], "complete")
        self.assertEqual(run["progress"]["stage"], "complete")
        self.assertNotIn("failure_reason", run["progress"])
        self.assertFalse(run["can_resume"])

    def test_old_pdf_checkpoint_recovers_without_ledger_attribution(self) -> None:
        progress = {"status": "failed", "stage": "compile"}
        saved = {
            "pdf_available": True,
            "pdf_sha256": "a" * 64,
            "paper_version": 12,
            "created_by": self.author,
        }
        work = {
            "published_paper_id": self.paper_id,
            "published_pdf_sha256": "a" * 64,
        }
        with (
            patch.object(
                project_collaboration, "list_execution_runs", return_value=[self.reservation]
            ),
            patch.object(
                project_collaboration, "collaborator_identity", return_value=self.author
            ),
            patch.object(project_collaboration, "is_project_owner", return_value=True),
            patch.object(papers, "progress_status", return_value=progress),
            patch.object(papers, "needs_preflight_on_open", return_value=False),
            patch.object(papers, "_load_work", return_value=work),
            patch.object(papers, "get_paper", return_value=saved),
        ):
            run = papers.run_progress_list(self.path)[0]
        self.assertEqual(run["paper_id"], self.paper_id)
        self.assertEqual(run["status"], "complete")

    def test_no_false_publication_without_matching_pdf(self) -> None:
        progress = {"status": "failed", "stage": "scoring", "paper_id": self.paper_id}
        saved = {
            "pdf_available": False,
            "paper_version": 12,
            "created_by": self.author,
        }
        with (
            patch.object(
                project_collaboration, "list_execution_runs", return_value=[self.reservation]
            ),
            patch.object(
                project_collaboration, "collaborator_identity", return_value=self.author
            ),
            patch.object(project_collaboration, "is_project_owner", return_value=True),
            patch.object(papers, "progress_status", return_value=progress),
            patch.object(papers, "needs_preflight_on_open", return_value=False),
            patch.object(papers, "get_paper", return_value=saved),
        ):
            run = papers.run_progress_list(self.path)[0]
        self.assertIsNone(run["paper_id"])
        self.assertEqual(run["status"], "failed")
        self.assertTrue(run["can_resume"])


class ActivityProjectionTests(TestCase):
    def test_active_paper_reaches_project_title_despite_stale_legacy_hint(self) -> None:
        run = {
            "run_id": uuid4().hex,
            "number": 18,
            "status": "active",
            "creator_email": "author@example.test",
            "model": "fixture-model",
            "thinking": "low",
            "progress": {"status": "active", "stage": "writing"},
        }
        project = SimpleNamespace(
            id="test-project",
            ai_model="fixture-model",
            reasoning_effort="low",
        )
        with (
            patch.object(papers, "activity_status", return_value=None),
            patch.object(papers, "run_progress_list", return_value=[run]),
            patch.object(research_sessions, "has_active_session", return_value=False),
            patch.object(research_qa, "list_pending_answers", return_value=[]),
            patch.object(
                project_collaboration,
                "summary",
                return_value={"artifact_authors": {}},
            ),
        ):
            result = recents.project_activity_runs("/tmp/test", project=project)
        self.assertEqual(len(result), 1)
        self.assertEqual(result[0]["kind"], "paper")
        self.assertEqual(result[0]["status"], "active")
        self.assertEqual(result[0]["number"], 18)
