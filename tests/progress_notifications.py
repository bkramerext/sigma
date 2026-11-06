"""Provider-free account isolation, durable outbox and message regression checks."""

from __future__ import annotations

import sqlite3
import time
from pathlib import Path
from tempfile import TemporaryDirectory
from typing import Any, cast
from unittest.mock import patch

from sigma import cloud_auth, progress_notifications


def _insert_user(cfg: cloud_auth.Config, principal: cloud_auth.Principal) -> None:
    with cloud_auth._db(cfg) as db:
        db.execute(
            """INSERT INTO user_state(
                subject,email,role,access_active,workspace_id,
                sponsorship_eligible,model_access,updated_at
            ) VALUES (?,?,?,1,NULL,0,'personal',?)""",
            (principal.subject, principal.email, principal.role, int(time.time())),
        )


def _event_state(cfg: cloud_auth.Config, event_id: str) -> sqlite3.Row:
    import hashlib

    digest = hashlib.sha256(event_id.encode("utf-8")).hexdigest()
    with cloud_auth._db(cfg) as db:
        row = db.execute(
            "SELECT state,attempts,retry_after FROM progress_email_dispatches WHERE event_hash=?",
            (digest,),
        ).fetchone()
    assert row is not None
    return row


def main() -> None:
    # SMTP credentials alone must never enable progress mail.
    with patch("sigma.cloud_auth.email_env", return_value=None):
        assert progress_notifications._configured() is False
    with patch("sigma.cloud_auth.email_env", return_value="/tmp/gmail-token.json"):
        assert progress_notifications._configured() is True

    first = cloud_auth.Principal("google-subject-a", "first@example.org", "member")
    second = cloud_auth.Principal("google-subject-b", "second@example.org", "member")
    origin = "http://localhost:5173"
    with TemporaryDirectory() as root:
        database = Path(root) / "access.sqlite3"
        cloud_auth._initialize(database)
        cfg = cloud_auth.Config(
            enabled=True,
            client_id=None,
            client_secret=None,
            origin=origin,
            admin_contact_email=None,
            database=database,
            error=None,
            local=True,
        )
        sent: list[tuple[str, str, str]] = []

        def deliver(message: Any, *, recipients: list[str], reply_to: str | None = None) -> None:
            assert reply_to is None
            sent.append((recipients[0], str(message["Subject"]), str(message.get_content())))

        with (
            patch("sigma.cloud_auth.config", return_value=cfg),
            patch("sigma.progress_notifications._configured", return_value=True),
            patch("sigma.mail_transport.send_message", side_effect=deliver),
        ):
            _insert_user(cfg, first)
            _insert_user(cfg, second)
            assert progress_notifications.preference(first) == {"enabled": False, "available": True}
            assert progress_notifications.preference(second)["enabled"] is False
            assert progress_notifications.update_preference(first, True)["enabled"]
            assert progress_notifications.preference(second)["enabled"] is False
            assert progress_notifications.preference(first)["enabled"] is True
            assert (
                progress_notifications.eligible_session_event({"status": "ended"})
                == "session_finished"
            )
            assert (
                progress_notifications.eligible_session_event({"status": "completed"})
                == "session_finished"
            )
            assert (
                progress_notifications.eligible_session_event({"status": "failed"})
                == "session_failed"
            )
            assert (
                progress_notifications.eligible_session_event(
                    {"status": "paused", "message": "Paused · provider usage limit"}
                )
                == "session_paused"
            )
            assert (
                progress_notifications.eligible_session_event(
                    {"status": "paused", "message": "Paused by user. A request may still finish."}
                )
                is None
            )

            for invalid in ("true", 1, None):
                try:
                    progress_notifications.update_preference(first, cast(Any, invalid))
                except ValueError:
                    pass
                else:
                    raise AssertionError("Non-boolean opt-in accepted")

            session = progress_notifications.deep_link(
                origin, "/tmp/my project.sigma", session_id="session-123"
            )
            assert "path=%2Ftmp%2Fmy+project.sigma" in session
            assert "reveal_session=session-123" in session
            hosted = progress_notifications.deep_link(
                "https://sigma.example.org", "/srv/project.sigma", paper_id="paper-123"
            )
            assert hosted.startswith("https://sigma.example.org/project?")
            assert "reveal_paper=paper-123" in hosted
            signed_out_return = "/project?path=%2Ftmp%2Fmy+project.sigma&reveal_session=session-123"
            assert cloud_auth._safe_login_return_to(signed_out_return) == signed_out_return
            assert "resume_play" not in (
                cloud_auth._safe_login_return_to(signed_out_return + "&resume_play=1") or ""
            )
            assert (
                cloud_auth._safe_login_return_to(
                    "/project?path=%2Ftmp%2Fmy+project.sigma&reveal_paper=draft"
                )
                is not None
            )
            cases: tuple[tuple[progress_notifications.Event, str], ...] = (
                ("session_finished", "Session 3 completed"),
                ("session_failed", "Session 3 failed"),
                ("session_paused", "Session 3 paused"),
                ("paper_finished", "Paper 3 generated"),
                ("paper_failed", "Paper 3 failed"),
                ("paper_paused", "Paper 3 paused"),
            )
            for event, expected in cases:
                msg = progress_notifications.message_for(event, "Project Alpha", 3, hosted)
                assert expected in str(msg["Subject"])
                assert "View " in msg.get_content()
                assert hosted in msg.get_content()

            incomplete = progress_notifications.message_for(
                "session_finished", "Project Alpha", 3, session, incomplete=True
            )
            assert "finished" in str(incomplete["Subject"])
            assert "completed successfully" not in incomplete.get_content()

            # Bind once. A different viewer must not take over the original job.
            progress_notifications.bind_job(first, "session:123")
            progress_notifications.bind_job(second, "session:123")
            progress_notifications.enqueue(
                "session:123",
                "session_finished",
                event_id="event:one",
                project_title="Project Alpha",
                number=3,
                path="/tmp/my project.sigma",
                session_id="session-123",
            )
            progress_notifications.enqueue(
                "session:123",
                "session_finished",
                event_id="event:one",
                project_title="Project Alpha",
                number=3,
                path="/tmp/my project.sigma",
                session_id="session-123",
            )
            progress_notifications._deliver_pending()
            progress_notifications._deliver_pending()
            assert len(sent) == 1
            assert sent[0][0] == first.email
            assert "reveal_session=session-123" in sent[0][2]
            assert _event_state(cfg, "event:one")["state"] == "sent"

            # A known pre-delivery SMTP failure is retried from persisted rows.
            progress_notifications.bind_job(first, "paper:retry")
            progress_notifications.enqueue(
                "paper:retry",
                "paper_paused",
                event_id="event:retry",
                project_title="Project Alpha",
                number=4,
                path="/tmp/my project.sigma",
                paper_id="draft",
            )
            assert _event_state(cfg, "event:retry")["retry_after"] > int(time.time())
            with cloud_auth._db(cfg) as db:
                db.execute(
                    "UPDATE progress_email_dispatches SET retry_after=0 WHERE event='paper_paused'"
                )
            with patch(
                "sigma.mail_transport.send_message",
                side_effect=cloud_auth.SMTPDeliveryError("not delivered", state="failed"),
            ):
                progress_notifications._deliver_pending()
            assert _event_state(cfg, "event:retry")["state"] == "pending"
            with cloud_auth._db(cfg) as db:
                db.execute(
                    "UPDATE progress_email_dispatches SET retry_after=0 WHERE state='pending'"
                )
            # Simulates process restart: pending state is on disk, not in a task.
            progress_notifications._deliver_pending()
            assert _event_state(cfg, "event:retry")["state"] == "sent"
            assert len(sent) == 2

            # An ambiguous provider response is never automatically replayed.
            progress_notifications.enqueue(
                "paper:retry",
                "paper_failed",
                event_id="event:unknown",
                project_title="Project Alpha",
                number=4,
                path="/tmp/my project.sigma",
                paper_id="draft",
            )
            with patch("sigma.mail_transport.send_message", side_effect=RuntimeError("unknown")):
                progress_notifications._deliver_pending()
            assert _event_state(cfg, "event:unknown")["state"] == "unknown"
            progress_notifications._deliver_pending()
            assert len(sent) == 2

            # Signed-in account scope is independent of what a second user prefers.
            progress_notifications.bind_job(second, "other-job")
            progress_notifications.enqueue(
                "other-job",
                "session_failed",
                event_id="other-event",
                project_title="Project Alpha",
                number=5,
                path="/tmp/my project.sigma",
                session_id="session-456",
            )
            with cloud_auth._db(cfg) as db:
                row = db.execute(
                    "SELECT COUNT(*) AS total FROM progress_email_dispatches WHERE event='session_failed'"
                ).fetchone()
            assert row is not None and row["total"] == 0
            # A delayed pause that recovered before mail delivery is noise.
            progress_notifications.enqueue(
                "session:123",
                "session_paused",
                event_id="event:recovered",
                project_title="Project Alpha",
                number=3,
                path="/tmp/my project.sigma",
                session_id="session-123",
            )
            with cloud_auth._db(cfg) as db:
                db.execute(
                    "UPDATE progress_email_dispatches SET retry_after=0 "
                    "WHERE event_hash=?",
                    (__import__("hashlib").sha256(b"event:recovered").hexdigest(),),
                )
            with patch(
                "sigma.progress_notifications._pause_still_actionable", return_value=False
            ):
                progress_notifications._deliver_pending()
            assert _event_state(cfg, "event:recovered")["state"] == "cancelled"
            assert len(sent) == 2

            # Opt-out before a queued send suppresses the existing event too.
            progress_notifications.enqueue(
                "session:123",
                "session_paused",
                event_id="event:optout",
                project_title="Project Alpha",
                number=3,
                path="/tmp/my project.sigma",
                session_id="session-123",
            )
            progress_notifications.update_preference(first, False)
            with cloud_auth._db(cfg) as db:
                db.execute(
                    "UPDATE progress_email_dispatches SET retry_after=0 "
                    "WHERE state='pending'"
                )
            progress_notifications._deliver_pending()
            assert _event_state(cfg, "event:optout")["state"] == "cancelled"
            assert len(sent) == 2

        with patch("sigma.cloud_auth.config", return_value=cfg):
            assert progress_notifications.preference(None) == {"enabled": False, "available": False}
            try:
                progress_notifications.update_preference(
                    cloud_auth.Principal("guest", "guest@example.org", "guest"), True
                )
            except ValueError:
                pass
            else:
                raise AssertionError("Guest preferences accepted")
    print("PASS progress email account isolation, six events, links, restart and delivery states")


if __name__ == "__main__":
    main()
