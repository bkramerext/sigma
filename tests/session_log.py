"""Regression checks for the append-only diagnostic session log."""

from __future__ import annotations

import json
import os
import subprocess
import sys
import tempfile
from concurrent.futures import ThreadPoolExecutor
from pathlib import Path
from unittest.mock import patch

from sigma import session_log


def test_session_log_frames_preserve_multiline_content_and_recover_tail(tmp_path: Path):
    tmp_path.mkdir(parents=True, exist_ok=True)
    project_file = tmp_path / "project.json"
    project_file.touch()
    root = tmp_path / "logs"
    with (
        patch.object(session_log, "_root", lambda _: root),
        patch.object(session_log, "project_path", lambda _: project_file),
    ):
        _verify_round_trip_and_recovery(project_file)


def _verify_round_trip_and_recovery(project_file: Path) -> None:
    session = {
        "project_id": "a12ca401-2210-4c88-8fe6-84a33b1e5eea",
        "id": "d0231c99-5425-4a20-8ff2-fc52c1800b8c",
        "session_number": 1,
        "project_title": "Xenopus Tadpoles",
    }
    content = "Heading\n```python\nprint('nested')\n```\n## Another heading"
    session_log.append(
        str(project_file),
        session,
        {
            "type": "provider_request",
            "request_id": "call-1",
            "request": {"input": content, "Authorization": "Bearer secret"},
        },
    )
    target = session_log.log_path(str(project_file), session["project_id"], session["id"])
    original = target.read_bytes()
    events, offset = session_log._frames(target)
    assert events[0]["request"]["input"] == content
    assert events[0]["request"]["Authorization"] == "[REDACTED]"
    restart = subprocess.run(
        [
            sys.executable,
            "-c",
            "from sigma.session_log import _frames; import sys; print(len(_frames(__import__('pathlib').Path(sys.argv[1]))[0]))",
            str(target),
        ],
        cwd=Path(__file__).resolve().parents[1],
        env=os.environ.copy(),
        capture_output=True,
        text=True,
        check=True,
    )
    assert restart.stdout.strip() == "1"
    with target.open("ab") as stream:
        stream.write(b"\n<!-- SIGMA_EVENT 55 -->\n{truncated")
    recovered, recovered_offset = session_log._frames(target, repair=True)
    assert recovered == events
    assert recovered_offset == offset
    assert target.read_bytes() == original


def test_session_log_concurrent_appends_are_serialized_and_append_only(tmp_path: Path):
    tmp_path.mkdir(parents=True, exist_ok=True)
    project_file = tmp_path / "project.json"
    project_file.touch()
    with (
        patch.object(session_log, "_root", lambda _: tmp_path / "logs"),
        patch.object(session_log, "project_path", lambda _: project_file),
    ):
        _verify_concurrent_appends(project_file)


def _verify_concurrent_appends(project_file: Path) -> None:
    session = {
        "project_id": "a12ca401-2210-4c88-8fe6-84a33b1e5eea",
        "id": "d0231c99-5425-4a20-8ff2-fc52c1800b8c",
        "session_number": 3,
        "project_title": "Maximum Regions Formed by Lines",
    }
    with ThreadPoolExecutor(max_workers=8) as pool:
        list(
            pool.map(
                lambda i: session_log.append(
                    str(project_file), session, {"type": "event", "message": f"event-{i}"}
                ),
                range(24),
            )
        )
    target = session_log.log_path(str(project_file), session["project_id"], session["id"])
    before = target.read_bytes()
    session_log.append(str(project_file), session, {"type": "event", "message": "later"})
    after = target.read_bytes()
    assert after.startswith(before)
    events, _ = session_log._frames(target)
    assert [event["seq"] for event in events] == list(range(1, 26))
    assert {event["message"] for event in events[:-1]} == {f"event-{i}" for i in range(24)}
    prior_offset = len(before)
    incremental, cursor = session_log._frames(target, start_offset=prior_offset)
    assert [event["message"] for event in incremental] == ["later"]
    assert cursor == len(after)


def test_session_log_event_json_is_valid_for_multiline_and_markdown(tmp_path: Path):
    target = tmp_path / "trace.md"
    target.write_text("# Trace\n", encoding="utf-8")
    event = {"seq": 1, "type": "response", "response": "# heading\n```\nbody\n```"}
    session_log._append_frame(target, event)
    parsed, _ = session_log._frames(target)
    assert parsed == [json.loads(json.dumps(event))]


def test_session_log_short_name_is_stable_and_delete_scoped(tmp_path: Path):
    tmp_path.mkdir(parents=True, exist_ok=True)
    project_file = tmp_path / "project.json"
    project_file.touch()
    with (
        patch.object(session_log, "_root", lambda _: tmp_path / "logs"),
        patch.object(session_log, "project_path", lambda _: project_file),
    ):
        first_project = "a12ca401-2210-4c88-8fe6-84a33b1e5eea"
        second_project = "b12ca401-2210-4c88-8fe6-84a33b1e5eea"
        first_session = "d0231c99-5425-4a20-8ff2-fc52c1800b8c"
        second_session = "e0231c99-5425-4a20-8ff2-fc52c1800b8c"
        session_log._short_name(project_file, first_project, "Xenopus Tadpoles Regeneration")
        assert (
            session_log._short_name(project_file, first_project, "Renamed Project")
            == "Xenopus Tadpoles Regeneration"
        )
        assert (
            session_log._short_name(
                project_file,
                "c12ca401-2210-4c88-8fe6-84a33b1e5eea",
                "Why Do Xenopus Tadpoles Temporarily Lose Tail Regeneration",
            )
            == "Xenopus Tadpoles Tail Regeneration"
        )
        assert (
            session_log._short_name(project_file, second_project, "Line Arrangement")
            == "Line Arrangement"
        )
        for project_id, session_id, name in (
            (first_project, first_session, "Xenopus Tadpoles Regeneration"),
            (first_project, second_session, "Xenopus Tadpoles Regeneration"),
            (second_project, "f0231c99-5425-4a20-8ff2-fc52c1800b8c", "Line Arrangement"),
        ):
            session_log.append(
                str(project_file),
                {
                    "project_id": project_id,
                    "id": session_id,
                    "session_number": 1,
                    "project_title": name,
                },
                {"type": "session_event", "message": "started"},
            )
        session_log.delete_session(str(project_file), first_project, first_session)
        assert not session_log.log_path(str(project_file), first_project, first_session).exists()
        session_log.delete_project(first_project, project_file)
        assert not (tmp_path / "logs" / first_project).exists()
        assert session_log.log_path(
            str(project_file), second_project, "f0231c99-5425-4a20-8ff2-fc52c1800b8c"
        ).exists()


def test_session_log_failure_is_best_effort(tmp_path: Path):
    tmp_path.mkdir(parents=True, exist_ok=True)
    project_file = tmp_path / "project.json"
    project_file.touch()
    with (
        patch.object(session_log, "_root", lambda _: tmp_path / "logs"),
        patch.object(session_log, "project_path", lambda _: project_file),
        patch.object(session_log, "_append_frame", side_effect=OSError("disk unavailable")),
    ):
        session_log.append(
            str(project_file),
            {
                "project_id": "a12ca401-2210-4c88-8fe6-84a33b1e5eea",
                "id": "d0231c99-5425-4a20-8ff2-fc52c1800b8c",
                "session_number": 1,
                "project_title": "Fixture",
            },
            {"type": "session_event", "message": "research must continue"},
        )


def main() -> None:
    with tempfile.TemporaryDirectory(prefix="sigma-session-log-") as directory:
        root = Path(directory)
        test_session_log_frames_preserve_multiline_content_and_recover_tail(root / "roundtrip")
        test_session_log_concurrent_appends_are_serialized_and_append_only(root / "parallel")
        test_session_log_event_json_is_valid_for_multiline_and_markdown(root)
        test_session_log_short_name_is_stable_and_delete_scoped(root / "lifecycle")
        test_session_log_failure_is_best_effort(root / "failure")
    print("Session log append, concurrency, redaction and recovery scenarios passed.")


if __name__ == "__main__":
    main()
