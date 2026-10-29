"""Regression checks for the append-only diagnostic session log."""

from __future__ import annotations

import json
import os
import subprocess
import sys
import tempfile
import threading
import time
from concurrent.futures import ThreadPoolExecutor
from pathlib import Path
from types import SimpleNamespace
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
    session_log.flush()
    target = session_log.log_path(str(project_file), session["project_id"], session["id"])
    session_log.append(
        str(project_file),
        session,
        {
            "type": "provider_failure",
            "message": "Bearer supersecret api_key=othersecret sk-0123456789abcdefghijklmnop",
        },
    )
    session_log.flush()
    all_bytes = target.read_bytes()
    assert b"supersecret" not in all_bytes and b"othersecret" not in all_bytes
    assert b"sk-0123456789abcdefghijklmnop" not in all_bytes
    original = target.read_bytes()
    events, _offset = session_log._frames(target)
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
    assert restart.stdout.strip() == "2"
    with target.open("ab") as stream:
        stream.write(b"\n<!-- SIGMA_EVENT 55 -->\n{truncated")
    recovered, recovered_offset = session_log._frames(target, repair=True)
    assert recovered == events
    assert recovered_offset == len(target.read_bytes())
    assert target.read_bytes().startswith(original)
    interrupted = target.read_bytes()
    restart_partial = subprocess.run(
        [
            sys.executable,
            "-c",
            "from sigma.session_log import _frames; from pathlib import Path; import sys; p=Path(sys.argv[1]); print(len(_frames(p, repair=True)[0]))",
            str(target),
        ],
        cwd=Path(__file__).resolve().parents[1],
        env=os.environ.copy(),
        capture_output=True,
        text=True,
        check=True,
    )
    assert restart_partial.stdout.strip() == "2"
    assert target.read_bytes() == interrupted
    torn_bytes = target.read_bytes()[len(original) :]
    session_log.append(str(project_file), session, {"type": "event", "message": "after recovery"})
    session_log.flush()
    final_bytes = target.read_bytes()
    assert final_bytes.startswith(original + torn_bytes)
    recovered_again, _ = session_log._frames(target)
    assert [row.get("message") for row in recovered_again if row["type"] == "event"] == [
        "after recovery"
    ]


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
    session_log.flush()
    target = session_log.log_path(str(project_file), session["project_id"], session["id"])
    before = target.read_bytes()
    session_log.append(str(project_file), session, {"type": "event", "message": "later"})
    session_log.flush()
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
        title = "Why do Xenopus tadpoles temporarily lose tail regeneration?"
        claim = "The evidence suggests Xenopus tadpoles can regenerate a tail after injury."
        first_name = session_log.subject_name_from_context(
            title,
            title,
            claim,
        )
        assert first_name == "Xenopus Tadpoles"
        session_log.record_ai_name(str(project_file), first_project, title, title, claim)
        session_log.flush()
        assert session_log._short_name(project_file, first_project) == "Xenopus Tadpoles"
        session_log.record_ai_name(
            str(project_file),
            first_project,
            title,
            title,
            "Xenopus tadpoles temporarily lose tail regeneration during early development.",
        )
        session_log.flush()
        assert session_log._short_name(project_file, first_project) == "Xenopus Tadpoles"
        assert (
            session_log.subject_name_from_context(
                "Does the harmonic series converge?",
                "Does the harmonic series converge?",
                "Evidence suggests that the harmonic series diverges.",
            )
            == "Harmonic Series"
        )
        assert (
            session_log.subject_name_from_context(
                "How can neighborhood libraries reduce social isolation for older adults?",
                "How can neighborhood libraries reduce social isolation for older adults?",
                "Results indicate neighborhood libraries can reduce isolation among older adults.",
            )
            == "Neighborhood Libraries"
        )
        assert (
            session_log.fallback_project_name(
                "Why do Xenopus tadpoles temporarily lose tail regeneration?"
            )
            == "Xenopus Tadpoles"
        )
        assert (
            session_log.fallback_project_name("Does the harmonic series converge?")
            == "Harmonic Series"
        )
        assert (
            session_log.fallback_project_name(
                "How can neighborhood libraries reduce social isolation for older adults?"
            )
            == "Neighborhood Libraries"
        )
        assert (
            session_log.subject_name_from_context(
                "Does the harmonic series converge?",
                "",
                "Evidence suggests the claim is unsupported.",
            )
            is None
        )
        assert session_log._short_name(project_file, second_project) == "Research Project"
        for project_id, session_id, name in (
            (first_project, first_session, "Xenopus Tadpoles"),
            (first_project, second_session, "Xenopus Tadpoles"),
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
        session_log.flush()
        assert session_log._short_name(project_file, first_project) == first_name
        session_log.delete_session(str(project_file), first_project, first_session)
        session_log.flush()
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
        session_log.flush()


def test_slow_storage_does_not_block_research_caller_and_keeps_order(tmp_path: Path):
    tmp_path.mkdir(parents=True, exist_ok=True)
    project_file = tmp_path / "project.json"
    project_file.touch()
    entered = threading.Event()
    release = threading.Event()
    original_append = session_log._append_frame

    def slow_append(path, value):
        if value.get("type") == "event":
            entered.set()
            release.wait(timeout=3)
        original_append(path, value)

    with (
        patch.object(session_log, "_root", lambda _: tmp_path / "slow-logs"),
        patch.object(session_log, "_append_frame", side_effect=slow_append),
    ):
        session = {
            "project_id": "a12ca401-2210-4c88-8fe6-84a33b1e5eea",
            "id": "d0231c99-5425-4a20-8ff2-fc52c1800b8c",
            "session_number": 1,
        }
        start = time.monotonic()
        session_log.append(str(project_file), session, {"type": "event", "message": "first"})
        assert time.monotonic() - start < 0.15
        assert entered.wait(timeout=1)
        session_log.append(str(project_file), session, {"type": "event", "message": "second"})
        release.set()
        session_log.flush()
        target = session_log.log_path(str(project_file), session["project_id"], session["id"])
        events, _ = session_log._frames(target)
        assert [item["message"] for item in events if item["type"] == "event"] == [
            "first",
            "second",
        ]


def test_delayed_session_a_write_does_not_block_session_b_read(tmp_path: Path):
    tmp_path.mkdir(parents=True, exist_ok=True)
    project_file = tmp_path / "project.json"
    project_file.touch()
    root = tmp_path / "logs"
    entered_a, written_b, release_a = threading.Event(), threading.Event(), threading.Event()
    original_append = session_log._append_frame
    project_id = "a12ca401-2210-4c88-8fe6-84a33b1e5eea"
    session_a = "d0231c99-5425-4a20-8ff2-fc52c1800b8c"
    session_b = "e0231c99-5425-4a20-8ff2-fc52c1800b8c"

    def delayed(path, value):
        if value.get("message") == "slow A":
            entered_a.set()
            assert release_a.wait(3)
        original_append(path, value)
        if value.get("message") == "ready B":
            written_b.set()

    view = SimpleNamespace(
        project=SimpleNamespace(
            id=project_id, title="Session Isolation", problem="Session isolation"
        )
    )
    with (
        patch.object(session_log, "_root", lambda _: root),
        patch.object(session_log, "_append_frame", side_effect=delayed),
        patch.object(session_log, "inspect_project", return_value=view),
        patch.object(session_log, "project_path", return_value=project_file),
        patch(
            "sigma.research_sessions.get_session",
            side_effect=lambda _path, sid: {"id": sid, "session_number": 2, "status": "running"},
        ),
    ):
        session_log.append(
            str(project_file),
            {"project_id": project_id, "id": session_a, "session_number": 1},
            {"type": "event", "message": "slow A"},
        )
        assert entered_a.wait(1)
        session_log.append(
            str(project_file),
            {"project_id": project_id, "id": session_b, "session_number": 2},
            {"type": "event", "message": "ready B"},
        )
        assert written_b.wait(1)
        start = time.monotonic()
        data = session_log.read(str(project_file), session_b)
        assert time.monotonic() - start < 0.5
        assert [event["message"] for event in data["events"] if event.get("type") == "event"] == [
            "ready B"
        ]
        assert not release_a.is_set()
        release_a.set()
        session_log.flush()


def test_project_deletion_waits_for_read_and_cleans_logs(tmp_path: Path):
    tmp_path.mkdir(parents=True, exist_ok=True)
    project_file = tmp_path / "project.json"
    project_file.touch()
    root = tmp_path / "logs"
    project_id = "a12ca401-2210-4c88-8fe6-84a33b1e5eea"
    session_id = "d0231c99-5425-4a20-8ff2-fc52c1800b8c"
    session = {"project_id": project_id, "id": session_id, "session_number": 1}
    view = SimpleNamespace(
        project=SimpleNamespace(id=project_id, title="Read Delete", problem="Read Delete")
    )
    with patch.object(session_log, "_root", lambda _: root):
        session_log.append(str(project_file), session, {"type": "event", "message": "saved"})
        session_log.flush()
    entered, release = threading.Event(), threading.Event()
    original_frames = session_log._frames

    def delayed_frames(*args, **kwargs):
        entered.set()
        assert release.wait(3)
        return original_frames(*args, **kwargs)

    with (
        patch.object(session_log, "_root", lambda _: root),
        patch.object(session_log, "_frames", side_effect=delayed_frames),
        patch.object(session_log, "inspect_project", return_value=view),
        patch.object(session_log, "project_path", return_value=project_file),
        patch("sigma.research_sessions.get_session", return_value=session),
        ThreadPoolExecutor(max_workers=2) as pool,
    ):
        reader = pool.submit(session_log.read, str(project_file), session_id)
        assert entered.wait(1)
        deletion = pool.submit(session_log.delete_project, project_id, project_file)
        time.sleep(0.05)
        assert not deletion.done()
        release.set()
        assert reader.result(timeout=2)["events"]
        deletion.result(timeout=2)
    assert not (root / project_id).exists()


def main() -> None:
    with tempfile.TemporaryDirectory(prefix="sigma-session-log-") as directory:
        root = Path(directory)
        test_session_log_frames_preserve_multiline_content_and_recover_tail(root / "roundtrip")
        test_session_log_concurrent_appends_are_serialized_and_append_only(root / "parallel")
        test_session_log_event_json_is_valid_for_multiline_and_markdown(root)
        test_session_log_short_name_is_stable_and_delete_scoped(root / "lifecycle")
        test_session_log_failure_is_best_effort(root / "failure")
        test_slow_storage_does_not_block_research_caller_and_keeps_order(root / "slow")
        test_delayed_session_a_write_does_not_block_session_b_read(root / "isolated-read")
        test_project_deletion_waits_for_read_and_cleans_logs(root / "delete-race")
    print("Session log append, concurrency, redaction and recovery scenarios passed.")


if __name__ == "__main__":
    main()
