"""Provider-free regression tests for account-scoped progress emails."""

from pathlib import Path
from tempfile import TemporaryDirectory
from unittest.mock import patch

from sigma import cloud_auth, progress_notifications


def main() -> None:
    first = cloud_auth.Principal("google-subject-a", "first@example.org", "member")
    second = cloud_auth.Principal("google-subject-b", "second@example.org", "member")
    with TemporaryDirectory() as root:
        database = Path(root) / "access.sqlite3"
        cloud_auth._initialize(database)
        cfg = cloud_auth.Config(
            enabled=True, client_id=None, client_secret=None,
            origin="http://localhost:5173",
            admin_contact_email=None, database=database, error=None, local=True,
        )
        sent: list[tuple[str, str, str]] = []

        def deliver(message, *, recipients, reply_to=None):
            assert reply_to is None
            sent.append((recipients[0], message["Subject"], message.get_content()))

        with (
            patch("sigma.cloud_auth.config", return_value=cfg),
            patch("sigma.progress_notifications._configured", return_value=True),
            patch("sigma.mail_transport.send_message", side_effect=deliver),
        ):
            assert progress_notifications.preference(first) == {
                "enabled": False, "available": True
            }
            assert progress_notifications.preference(second)["enabled"] is False
            assert progress_notifications.update_preference(first, True)["enabled"] is True
            # Opening another project still uses the same signed-in subject.
            assert progress_notifications.preference(first)["enabled"] is True
            assert progress_notifications.preference(second)["enabled"] is False
            assert progress_notifications.eligible_session_event({"status": "ended"}) == "session_finished"
            assert progress_notifications.eligible_session_event({"status": "completed"}) == "session_finished"
            assert progress_notifications.eligible_session_event({"status": "failed"}) == "session_failed"
            assert progress_notifications.eligible_session_event({
                "status": "paused", "message": "Paused · provider usage limit"
            }) == "session_paused"
            assert progress_notifications.eligible_session_event({
                "status": "paused", "message": "Paused by user. A request may still finish."
            }) is None
            assert progress_notifications.eligible_session_event({
                "status": "paused", "message": "Simulated research paused. No provider was called."
            }) is None
            for invalid in ("true", 1, None):
                try:
                    progress_notifications.update_preference(first, invalid)
                except ValueError:
                    pass
                else:
                    raise AssertionError("Non-boolean opt-in accepted")

            session = progress_notifications.deep_link(
                cfg.origin, "/tmp/my project.sigma", session_id="session-123"
            )
            assert session.startswith("http://localhost:5173/project?")
            assert "path=%2Ftmp%2Fmy+project.sigma" in session
            assert "reveal_session=session-123" in session
            hosted = progress_notifications.deep_link(
                "https://sigma.example.org", "/srv/project.sigma", paper_id="paper-123"
            )
            assert "reveal_paper=paper-123" in hosted
            assert hosted.startswith("https://sigma.example.org/project?")
            for event, expected in (
                ("session_finished", "Session 3 completed"),
                ("session_failed", "Session 3 failed"),
                ("session_paused", "Session 3 paused"),
                ("paper_finished", "Paper 3 generated"),
                ("paper_failed", "Paper 3 failed"),
                ("paper_paused", "Paper 3 paused"),
            ):
                msg = progress_notifications.message_for(event, "Project Alpha", 3, hosted)
                assert expected in msg["Subject"]
                assert "View " in msg.get_content()
                assert hosted in msg.get_content()

            options = dict(
                event_id="session:123:ended:2026-11-06T00:00:00Z",
                project_title="Project Alpha", number=3,
                path="/tmp/my project.sigma", session_id="session-123",
            )
            progress_notifications.dispatch(first, "session_finished", **options)
            progress_notifications.dispatch(first, "session_finished", **options)
            assert len(sent) == 1
            assert sent[0][0] == "first@example.org"
            assert "Session 3 completed" in sent[0][1]
            assert "reveal_session=session-123" in sent[0][2]
            # A browser belonging to a different identity cannot inherit the opt-in.
            progress_notifications.dispatch(
                second, "session_finished", **{**options, "event_id": "session:other"}
            )
            assert len(sent) == 1

            with patch("sigma.mail_transport.send_message", side_effect=RuntimeError("offline")):
                progress_notifications.dispatch(
                    first, "paper_paused",
                    event_id="paper:failure-attempt", project_title="Project Alpha",
                    number=4, path="/tmp/my project.sigma", paper_id="draft",
                )
            with cloud_auth._db(cfg) as db:
                state = db.execute(
                    "SELECT state FROM progress_email_dispatches WHERE state='unknown'"
                ).fetchone()
                assert state is not None
            progress_notifications.dispatch(
                first, "paper_paused",
                event_id="paper:failure-attempt", project_title="Project Alpha",
                number=4, path="/tmp/my project.sigma", paper_id="draft",
            )
            assert len(sent) == 1
            assert progress_notifications.update_preference(first, False)["enabled"] is False
            progress_notifications.dispatch(
                first, "session_failed",
                event_id="session:after-opt-out", project_title="Project Alpha",
                number=4, path="/tmp/my project.sigma", session_id="session-456",
            )
            assert len(sent) == 1
        with patch("sigma.cloud_auth.config", return_value=cfg):
            assert progress_notifications.preference(None) == {
                "enabled": False, "available": False
            }
            try:
                progress_notifications.update_preference(
                    cloud_auth.Principal("guest", "guest@example.org", "guest"), True
                )
            except ValueError:
                pass
            else:
                raise AssertionError("Guest preferences accepted")
    print("PASS user-scoped progress email opt-in, six templates, links and deduplication")


if __name__ == "__main__":
    main()
