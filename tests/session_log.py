"""Regression checks for the append-only diagnostic session log."""

from __future__ import annotations

import asyncio
import hashlib
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


def test_readable_markdown_pairs_provider_traffic_and_keeps_canonical_json(tmp_path: Path):
    target = tmp_path / "readable.md"
    target.write_text("# Project, Session 4\n", encoding="utf-8")
    request = {
        "seq": 1,
        "type": "provider_request",
        "timestamp": "2026-10-29T12:00:00+00:00",
        "request_id": "call-4",
        "role": "investigator",
        "round": 2,
        "turn": 4,
        "provider": "fixture",
        "model": "fixture-model",
        "request": {
            "instructions": "Investigate the saved project.\nKeep multiline context.\n<!-- SIGMA_JSON 1 -->",
            "input": [{"role": "user", "content": "Explain $x_4$."}],
        },
    }
    response = {
        "seq": 2,
        "type": "provider_response",
        "timestamp": "2026-10-29T12:00:01+00:00",
        "request_id": "call-4",
        "role": "investigator",
        "duration_seconds": 1.2,
        "response_wire": "raw-wire-content-" * 1000,
        "estimated_cost_usd": 0.001,
        "usage": {"input_tokens": 12, "output_tokens": 8},
        "response": {
            "output": [
                {
                    "type": "message",
                    "content": [
                        {
                            "type": "output_text",
                            "text": json.dumps(
                                {
                                    "claim": "The recurrence is:\n\n\\[\na_n = a_{n-1}+1",
                                    "method": "Test the boundary. A raw $ total is $5.",
                                }
                            ),
                        }
                    ],
                }
            ]
        },
    }
    session_log._append_frame(target, request, session_log._event_markdown(request, []))
    session_log._append_frame(target, response, session_log._event_markdown(response, [request]))
    events, _ = session_log._frames(target)
    assert events == [request, response]
    source = target.read_text(encoding="utf-8")
    assert "<!-- SIGMA_JSON 1 -->" not in source
    assert "&lt;!-- SIGMA_JSON 1 -->" in source
    assert source.count("Request + response") == 1
    assert "#### Actual request" in source and "#### Provider response" in source
    assert "## Canonical" not in source
    assert "Canonical structured event data (JSON)" in source
    assert '```json\n{\n  "seq": 1' in source
    assert "\\\\[" in source  # The unterminated legacy opener is literal-safe.
    assert "raw-wire-content-" in source
    exported = session_log.markdown_export(events, {"number": 4}, "Project Name")
    assert exported.startswith("# Project Name, Session 4")
    assert exported.count("Request + response") == 1
    assert "## Canonical event records" in exported
    assert "The recurrence is:\n\n$$" in exported and "$a_n" not in exported
    assert r"raw \$ total is \$5" in exported
    assert "raw-wire-content-" not in exported
    assert "17000 characters retained" in exported
    assert max(map(len, exported.splitlines())) < 1000


def test_legacy_and_markdown_frames_can_be_read_from_the_same_append_only_file(tmp_path: Path):
    target = tmp_path / "mixed.md"
    target.write_text("# Existing log\n", encoding="utf-8")
    legacy = {"seq": 1, "type": "session_event", "message": "legacy frame"}
    current = {"seq": 2, "type": "session_event", "message": "readable frame"}
    session_log._append_frame(target, legacy)
    session_log._append_frame(target, current, session_log._event_markdown(current, [legacy]))
    events, _ = session_log._frames(target)
    assert events == [legacy, current]


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

    def slow_append(path, value, markdown=""):
        if value.get("type") == "event":
            entered.set()
            release.wait(timeout=3)
        original_append(path, value, markdown)

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

    def delayed(path, value, markdown=""):
        if value.get("message") == "slow A":
            entered_a.set()
            assert release_a.wait(3)
        original_append(path, value, markdown)
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


def test_session_log_filename_short_name_fallback_and_sanitization() -> None:
    assert (
        session_log.export_filename("Xenopus Tadpoles", "Very Long Project Title", 12)
        == "Xenopus_Tadpoles.session_12.md"
    )
    assert (
        session_log.export_filename(None, "Warp Drive Design", 3)
        == "Warp_Drive_Design.session_3.md"
    )
    assert (
        session_log.export_filename("", "Nonconsecutive Subset Sums", 54)
        == "Nonconsecutive_Subset_Sums.session_54.md"
    )
    assert (
        session_log.export_filename(r"../COM1:\\bad?/..", "Ignored", 2) == "COM1_bad.session_2.md"
    )
    assert session_log.export_filename("CON", "Ignored", 1) == "CON_project.session_1.md"
    assert session_log.export_filename("Étude / 数学", "Ignored", 9) == "Étude_数学.session_9.md"
    assert session_log.export_filename("..//", "??", 7) == "project.session_7.md"


def test_saved_reference_diagnostics_and_markdown_export() -> None:
    excerpt = "A frozen exact methodology excerpt for scientific inquiry."
    digest = hashlib.sha256(excerpt.encode("utf-8")).hexdigest()
    snapshot = {
        "sha256": "frozen-source-checksum",
        "sources": [
            {
                "id": "one",
                "title": "Methodology One",
                "url": "https://example.org/one",
                "retrieval": {
                    "status": "retrieved",
                    "excerpt": excerpt,
                    "excerpt_sha256": digest,
                    "content_sha256": "original-document-hash",
                },
            },
            {
                "id": "two",
                "title": "Methodology Two",
                "url": "https://example.org/two",
                "retrieval": {"status": "unavailable", "reason": "http_403", "excerpt": None},
            },
            {
                "id": "three",
                "title": "Methodology Three",
                "url": "https://example.org/three",
                "retrieval": {
                    "status": "retrieved",
                    "excerpt": excerpt,
                    "excerpt_sha256": "tampered-hash",
                    "content_sha256": "saved-document-hash",
                },
            },
        ],
    }
    record = {
        "research_method_sources": snapshot,
        "reference_compilation": {
            "status": "fallback",
            "source_sha256": "frozen-source-checksum",
            "reason": "Compiler rejected after bounded attempts.",
            "attempts": [
                {
                    "number": 1,
                    "status": "rejected",
                    "provider_http_status": 429,
                    "provider_error_code": "rate_limit_exceeded",
                    "retry_decision": "retry",
                    "usage_status": "rejected",
                },
                {
                    "number": 2,
                    "status": "not_dispatched",
                    "retry_decision": "budget_exhausted",
                    "usage_status": "not_dispatched",
                },
            ],
        },
        "calls_used": 1,
        "strategy_ids": ["one"],
    }
    summary = session_log.reference_preparation_summary(record)
    assert summary["selected_count"] == 3
    assert summary["verified_count"] == 1
    assert summary["references"][0]["excerpt_integrity"] is True
    assert summary["references"][1]["http_status"] == 403
    assert summary["references"][1]["retrieval_status"] == "unavailable"
    assert summary["references"][2]["excerpt_integrity"] is False
    assert summary["compiler"]["status"] == "fallback"
    assert summary["compiler"]["attempt_count"] == 1
    assert summary["compiler"]["attempts"][1]["status"] == "not_dispatched"
    assert summary["compiler"]["retrieved_excerpts_used"] == "unknown/not recorded"
    assert "fallback" in summary["guidance_disposition"]
    exported = session_log.markdown_export(
        [{"seq": 1, "type": "session_event", "message": "call ongoing"}],
        {"number": 12},
        "Project",
        summary,
    )
    assert "## Research-reference preparation" in exported
    assert "Methodology Two — https://example.org/two" in exported
    assert "HTTP: 403" in exported
    assert "Compilation degraded" in exported
    assert "unknown/not recorded" in exported
    assert "## Canonical event records" in exported
    assert session_log.reference_preparation_summary({})["selected_count"] is None
    assert excerpt not in exported  # No full frozen excerpts duplicated in downloads.
    record["reference_compilation"] = {
        "status": "completed",
        "source_sha256": "frozen-source-checksum",
        "attempts": [{"number": 1, "status": "completed", "retry_decision": "completed"}],
    }
    completed = session_log.reference_preparation_summary(record)
    assert completed["compiler"]["attempt_count"] == 1
    assert "Compiled guidance available" in completed["guidance_disposition"]
    assert "unknown/not recorded" in completed["guidance_disposition"]
    record["reference_compilation"]["status"] = "pending"
    pending = session_log.reference_preparation_summary(record)
    assert pending["compiler"]["status"] == "pending"
    assert "pending" in pending["guidance_disposition"]


def test_session_log_download_route_content_and_name() -> None:
    from sigma import api

    record = {
        "events": [{"seq": 1, "type": "session_event", "message": "still recording"}],
        "session": {"number": 7, "status": "running"},
        "project_title": "A Long Project / Name",
        "saved_short_name": "Tadpole Research",
        "reference_preparation": session_log.reference_preparation_summary({}),
    }
    with patch.object(api.session_log, "read", return_value=record):
        active = api.research_session_log_download_view("test-session-id", "/fixture")
    assert 'filename="Tadpole_Research.session_7.md"' in active.headers["content-disposition"]
    assert active.media_type is not None and active.media_type.startswith("text/markdown")
    assert b"## Research-reference preparation" in active.body
    assert b"still recording" in active.body
    record["session"]["status"] = "completed"
    with patch.object(api.session_log, "read", return_value=record):
        completed = api.research_session_log_download_view("test-session-id", "/fixture")
    assert active.headers["content-disposition"] == completed.headers["content-disposition"]
    assert active.body != completed.body
    assert b"## Final saved session status" not in active.body
    assert b"## Final saved session status" in completed.body
    assert b"Status: completed" in completed.body
    assert b"still recording" in active.body and b"still recording" in completed.body
    record["saved_short_name"] = None
    with patch.object(api.session_log, "read", return_value=record):
        fallback = api.research_session_log_download_view("test-session-id", "/fixture")
    assert 'filename="A_Long_Project_Name.session_7.md"' in fallback.headers["content-disposition"]


def test_project_session_log_exports_latest_and_all() -> None:
    from io import BytesIO
    from zipfile import ZipFile

    from sigma import api

    older = "11000000-0000-4000-8000-000000000001"
    newer = "22000000-0000-4000-8000-000000000002"
    # The older session was resumed more recently; creation order still wins.
    sessions = [
        {"id": newer, "session_number": 9, "updated_at": "2026-11-18"},
        {"id": older, "session_number": 2, "updated_at": "2026-11-19"},
    ]
    records = {
        older: {
            "events": [{"seq": 1, "type": "session_event", "message": "older diagnostic"}],
            "session": {"number": 2, "status": "stopped"},
            "project_title": "Test",
            "saved_short_name": "Test",
            "reference_preparation": session_log.reference_preparation_summary({}),
        },
        newer: {
            "events": [{"seq": 1, "type": "session_event", "message": "newer diagnostic"}],
            "session": {"number": 9, "status": "completed"},
            "project_title": "Test",
            "saved_short_name": "Test",
            "reference_preparation": session_log.reference_preparation_summary({}),
        },
    }

    def read(_path: str, session_id: str, _after: int = 0) -> dict:
        return records[session_id]

    with (
        patch.object(api, "inspect_project"),
        patch.object(api.research_sessions, "list_sessions", return_value=sessions),
        patch.object(api.session_log, "read", side_effect=read),
        patch.object(api.project_diagnostics, "read", return_value=[]),
    ):
        latest = api.export_project_session_logs("/fixture", "latest")
        assert latest.media_type == "text/markdown; charset=utf-8"
        assert 'filename="Test.session_9.md"' in latest.headers["content-disposition"]
        assert b"newer diagnostic" in latest.body
        assert b"older diagnostic" not in latest.body

        all_logs = api.export_project_session_logs("/fixture", "all")
        assert all_logs.media_type == "application/zip"
        with ZipFile(BytesIO(all_logs.body)) as archive:
            names = archive.namelist()
            assert len(names) == 2
            assert len(set(names)) == 2
            assert all(name.endswith(".md") for name in names)
            assert any("older diagnostic" in archive.read(name).decode() for name in names)
            assert any("newer diagnostic" in archive.read(name).decode() for name in names)


def test_session_status_and_correlated_errors_match_export() -> None:
    from sigma import api

    session_id = "a12ca401-2210-4c88-8fe6-84a33b1e5eea"
    stop_reason = "Context limit: 256000 bytes; no provider call was made."
    record = {
        "events": [{"seq": 1, "type": "session_event", "message": stop_reason}],
        "session": {
            "id": session_id,
            "number": 3,
            "status": "stopped",
            "current_action": "Context assembly blocked",
            "termination_reason_code": "mandatory_context_exceeded",
            "reason": stop_reason,
        },
        "project_title": "Crucible",
        "saved_short_name": "Crucible",
        "reference_preparation": session_log.reference_preparation_summary({}),
    }
    diagnostics = [
        {
            "id": "a",
            "timestamp": "2026-11-03T00:00:00Z",
            "code": "context_limit",
            "message": stop_reason,
            "session_id": session_id,
        },
        {
            "id": "b",
            "timestamp": "2026-11-03T00:00:01Z",
            "code": "admission",
            "message": "Unrelated pre-session failure",
            "session_id": None,
        },
    ]
    with (
        patch.object(api.session_log, "read", return_value=record),
        patch.object(api.project_diagnostics, "read", return_value=diagnostics),
    ):
        exported = bytes(
            api.research_session_log_download_view(session_id, "/fixture").body
        ).decode()
    for piece in (
        "Status: stopped",
        "Context assembly blocked",
        "mandatory_context_exceeded",
        stop_reason,
        "## Exportable UI diagnostics",
        "context_limit",
    ):
        assert piece in exported, piece
    assert "Unrelated pre-session failure" not in exported


def test_flat_turn_settings_convert_legacy_rounds_without_relabeling() -> None:
    from sigma import research_sessions

    # Global default applies to new Sessions only; legacy snapshots stay intact.
    assert research_sessions._session_configuration(None)["turn_limit"] == 20
    assert research_sessions._session_configuration({})["turn_limit"] == 20
    legacy = research_sessions._session_configuration({"research_rounds": 3, "turns_per_round": 3})
    assert legacy["turn_limit"] == 9
    assert not legacy["unlimited_turns"]
    assert research_sessions._session_configuration({"turn_limit": 17})["turn_limit"] == 17
    assert research_sessions._session_configuration(
        {"single_round_unlimited_turns": True, "research_rounds": 1, "turns_per_round": 4}
    )["unlimited_turns"]
    # Existing saved slot numbers remain the canonical history; a flat turn
    # presentation does not alter the old schedule divisor.
    saved = {"scheduler_version": 2, "turns_per_round": 3}
    assert research_sessions._paired_round_position(saved, 7) == (3, 1)
    assert research_sessions._paired_round_position(saved, 9) == (3, 3)


def test_user_turn_default_migration_and_validation(root: Path) -> None:
    from sigma import global_research_settings, research_sessions
    from sigma.projects import ProjectError

    target = root / "global-turn-settings.json"
    with patch.object(global_research_settings, "_path", return_value=target):
        assert global_research_settings.load_config()["default_turn_limit"] == 20
        legacy = global_research_settings._defaults()
        legacy.pop("default_turn_limit")
        legacy["limits"].update(research_rounds=3, turns_per_round=4, model_calls=24)
        target.write_text(json.dumps({"version": 1, **legacy}), encoding="utf-8")
        target.chmod(0o600)
        assert global_research_settings.load_config()["default_turn_limit"] == 12
        saved = global_research_settings.save_config(
            {"default_turn_limit": 3}, flat_limits=True
        )
        assert saved["default_turn_limit"] == 3
        persisted = json.loads(target.read_text(encoding="utf-8"))
        assert persisted["version"] == 2
        assert not {"research_rounds", "turns_per_round", "scheduler_version", "model_calls"} & set(
            persisted["limits"]
        )
        assert global_research_settings.load_config()["default_turn_limit"] == 3
        for invalid in (0, 1201, True, "3"):
            try:
                global_research_settings.save_config({"default_turn_limit": invalid}, flat_limits=True)
            except ProjectError:
                pass
            else:
                raise AssertionError("Invalid turn default was accepted")
        assert global_research_settings.load_config()["default_turn_limit"] == 3

    # Flat session admission is independent of the old global protocol.
    stored = {**research_sessions.NEW_DEFAULT_LIMITS, "research_rounds": 5, "model_calls": 30}
    result = research_sessions._session_start_limits(
        stored, research_sessions.NEW_DEFAULT_LIMITS, flat=True
    )
    assert result["scheduler_version"] == 2
    assert result["research_rounds"] == result["turns_per_round"] == 1
    assert result["model_calls"] == 2
    assert result["session_duration_minutes"] == stored["session_duration_minutes"]


def test_complete_transcript_export_groups_turns_newest_first() -> None:
    events = [
        {
            "seq": 1,
            "timestamp": "2026-11-18T01:00:00Z",
            "type": "provider_request",
            "request_id": "a",
            "role": "investigator",
            "round": 1,
            "strategy_id": "alpha",
        },
        {
            "seq": 2,
            "timestamp": "2026-11-18T01:00:01Z",
            "type": "provider_response",
            "request_id": "a",
            "response": {"output_text": "First argument"},
        },
        {
            "seq": 3,
            "timestamp": "2026-11-18T01:00:02Z",
            "type": "provider_request",
            "request_id": "b",
            "role": "skeptic",
            "round": 2,
            "strategy_id": "alpha",
        },
        {
            "seq": 4,
            "timestamp": "2026-11-18T01:00:03Z",
            "type": "provider_response",
            "request_id": "b",
            "response": {"output_text": "Second argument"},
        },
        {
            "seq": 5,
            "timestamp": "2026-11-18T01:00:04Z",
            "type": "retention_limit",
            "message": "Earlier diagnostics were omitted",
        },
    ]
    exported = session_log.transcript_markdown_export(events, [], {"number": 7}, "Research")
    assert exported.index("## Turn 2") < exported.index("## Turn 1")
    assert "Second argument" in exported
    assert "First argument" in exported
    assert "Earlier diagnostics were omitted" in exported


def _completed_pair_step(role: str, cycle: int) -> dict:
    return {
        "id": f"{role}-{cycle}",
        "role": role,
        "cycle": cycle,
        "strategy_id": "strategy-a",
        "status": "completed",
    }


def _extended_session_record() -> dict:
    """Small scheduler_v2 checkpoint after one completed Investigator/Skeptic pair."""
    return {
        "status": "completed",
        "settings_extended": True,
        "scheduler_version": 2,
        "cycle_limit": 2,
        "call_limit": 4,
        "calls_used": 2,
        "strategy_runs": [
            {
                "strategy_id": "strategy-a",
                "status": "ended",
                "cycle": 1,
                "pending_investigation": None,
            }
        ],
        "steps": [
            _completed_pair_step("investigator", 1),
            _completed_pair_step("skeptic", 1),
        ],
    }


def test_extended_completed_session_plans_new_slots_without_replaying_history() -> None:
    from sigma import research_sessions

    saved = _extended_session_record()
    plan, error = research_sessions._protocol_completion_recovery_plan(saved)
    assert error is None, error
    assert plan is not None
    assert plan["completed_turns"] == 2
    assert plan["required_calls"] == 2
    assert plan["branches"] == [
        {
            "strategy_id": "strategy-a",
            "role": "investigator",
            "cycle": 2,
            "recovery_context": plan["branches"][0]["recovery_context"],
        }
    ]
    assert plan["branches"][0]["recovery_context"]["new_request"] is True
    assert saved["steps"] == [
        _completed_pair_step("investigator", 1),
        _completed_pair_step("skeptic", 1),
    ]
    # No extension marker means a completed Session must stay completed.
    saved["settings_extended"] = False
    rejected, reason = research_sessions._protocol_completion_recovery_plan(saved)
    assert rejected is None
    assert reason


def test_extension_preserves_partial_pair_and_refuses_duplicate_accepted_steps() -> None:
    from sigma import research_sessions

    saved = _extended_session_record()
    saved["steps"].append(_completed_pair_step("investigator", 2))
    saved["strategy_runs"][0]["cycle"] = 1
    saved["strategy_runs"][0]["pending_investigation"] = {"claim": "Pending review"}
    plan, error = research_sessions._protocol_completion_recovery_plan(saved)
    assert error is None, error
    assert plan is not None and plan["required_calls"] == 1
    assert plan["branches"][0]["role"] == "skeptic"
    assert plan["branches"][0]["cycle"] == 2
    saved["steps"].append(_completed_pair_step("investigator", 2))
    rejected, reason = research_sessions._protocol_completion_recovery_plan(saved)
    assert rejected is None
    assert isinstance(reason, str) and "duplicate" in reason.lower()


def test_unlimited_turn_growth_does_not_extend_finished_branches() -> None:
    from sigma import research_sessions

    record = {
        "session_settings": {"unlimited_turns": True},
        "scheduler_version": 2,
        "cycle_limit": 2,
        "call_ceiling_cycles": 2,
        "call_limit": 6,
        "supervisor_ceiling_calls": 2,
        "total_token_limit": 1000000,
        "output_token_limit": 256,
        "model": "gpt-6",
        "turns_are_flat": True,
        "strategy_runs": [{"strategy_id": "strategy-a", "status": "queued", "cycle": 1}],
    }
    assert research_sessions._grow_unlimited_session_turns(record)
    assert record["cycle_limit"] == 3
    assert record["call_limit"] == 9
    assert record["supervisor_ceiling_calls"] == 3
    assert record["turns_per_round"] == 3
    assert not research_sessions._grow_unlimited_session_turns(record)
    record["strategy_runs"][0]["status"] = "ended"
    record["strategy_runs"][0]["cycle"] = 3
    assert not research_sessions._grow_unlimited_session_turns(record)
    assert record["call_limit"] == 9


def test_brainstorm_second_participant_has_constructive_guidance() -> None:
    from sigma import research_sessions

    ordinary = research_sessions._role_instructions("skeptic", {"session_settings": {}})
    brainstorm = research_sessions._role_instructions(
        "skeptic", {"session_settings": {"brainstorm_mode": True}}
    )
    assert "co-investigator with independent intellectual" not in ordinary
    assert "co-investigator with independent intellectual" in brainstorm
    assert "required evidence-review schema" in brainstorm


def test_supervisor_response_validation_and_process_guidance() -> None:
    from sigma import research_sessions, session_supervisor
    from sigma.projects import ProjectError

    answer = {
        "dimensions": {
            "objective_alignment": 4.0,
            "originality": 3.0,
            "substantive_advancement": 2.5,
            "evidence_validation": 1.0,
            "research_health": 5.0,
        },
        "assessment": "The agents have clarified their own assumptions.",
        "action": "nudge",
        "recipient": "ai_2",
        "guidance": "State the uncertainty in your own argument.",
        "breakthrough_candidate": False,
        "breakthrough_detail": "",
    }
    assert session_supervisor.parse_assessment(json.dumps(answer)) == answer
    bad_scores = dict(answer)
    bad_scores["dimensions"] = {**answer["dimensions"], "evidence_validation": 11.0}
    try:
        session_supervisor.parse_assessment(json.dumps(bad_scores))
    except ProjectError:
        pass
    else:
        raise AssertionError("An out-of-range dimension score was accepted")
    assert "State the uncertainty" in research_sessions._role_instructions(
        "skeptic",
        {
            "session_settings": {"supervisor_mode": "light"},
            "supervisor_guidance": answer["guidance"],
        },
    )
    assert "State the uncertainty" not in research_sessions._role_instructions(
        "investigator", {"session_settings": {"supervisor_mode": "none"}}
    )
    answer["recipient"] = None
    try:
        session_supervisor.parse_assessment(json.dumps(answer))
    except ProjectError:
        pass
    else:
        raise AssertionError("A non-addressed supervisor nudge was accepted")


def test_supervisor_usage_is_authoritative_and_uncertain_cost_is_retained() -> None:
    from sigma import research_sessions

    record = {
        "status": "running",
        "steps": [
            {
                "status": "completed",
                "token_usage": {"input_tokens": 20, "output_tokens": 7},
            }
        ],
        "supervisor_reviews": [
            {
                "status": "completed",
                "token_usage": {"input_tokens": 13, "output_tokens": 5},
            }
        ],
    }
    research_sessions._refresh_token_accounting(record)
    assert record["tokens_used"] == 45
    assert record["token_usage_status"] == "complete"
    record["supervisor_reviews"].append(
        {
            "status": "interrupted",
            "attempt_status": "unknown",
        }
    )
    research_sessions._refresh_token_accounting(record)
    assert record["tokens_used"] == 45
    assert record["token_usage_status"] == "partial"


def test_abandoned_supervisor_reservation_preserves_full_liability() -> None:
    from sigma import research_budget
    from sigma.research_budget import BudgetExceeded

    ledger = research_budget.new_ledger(
        call_limit=3,
        input_token_limit=30000,
        output_tokens_per_call=100,
        cost_limit_usd=10.0,
        input_price_per_million=1.0,
        output_price_per_million=10.0,
    )
    original = research_budget.reserve_before_dispatch(
        ledger, call_id="supervisor", request_body=b"process review"
    )
    original["purpose"] = "supervisor"
    research_budget.mark_unknown(ledger, call_id="supervisor")
    held_cost = original["cost_bound_usd"]
    research_budget.authorize_supervisor_recovery_after_unknown(ledger, call_id="supervisor")
    assert ledger["blocked_reason"] is None
    assert original["status"] == "unknown_supervisor_abandoned"
    assert original["cost_bound_usd"] == held_cost
    assert original["input_token_bound"] > 0
    second = research_budget.reserve_before_dispatch(
        ledger, call_id="research", request_body=b"next original role"
    )
    research_budget.mark_unknown(ledger, call_id="research")
    assert second["status"] == "unknown"
    try:
        research_budget.authorize_supervisor_recovery_after_unknown(ledger, call_id="research")
    except BudgetExceeded:
        pass
    else:
        raise AssertionError("An unrelated uncertain role call was cleared")


def test_pending_supervisor_reviews_only_run_once_after_resume() -> None:
    from sigma import research_sessions

    calls = []
    record = {
        "status": "running",
        "session_settings": {"supervisor_mode": "light"},
        "steps": [
            {**_completed_pair_step("investigator", 1), "output": {"claim": "A"}},
            {**_completed_pair_step("skeptic", 1), "output": {"response": "B"}},
        ],
        "supervisor_reviews": [],
    }

    async def fake_supervisor(_session_id, _path, strategy_id, cycle, _lock):
        calls.append((strategy_id, cycle))
        record["supervisor_reviews"].append(
            {
                "pair_key": f"{strategy_id}:{cycle}",
                "status": "completed",
            }
        )

    async def run():
        with (
            patch.object(research_sessions, "_read", return_value=record),
            patch.object(research_sessions, "_portfolio_supervisor_call", fake_supervisor),
        ):
            lock = asyncio.Lock()
            await research_sessions._supervise_completed_pairs("session", "fake", lock)
            await research_sessions._supervise_completed_pairs("session", "fake", lock)

    asyncio.run(run())
    assert calls == [("strategy-a", 1)]


def test_transcript_conversion_uses_server_saved_event_only() -> None:
    from sigma import text_conversion
    from sigma.projects import ProjectError

    with patch.object(
        session_log,
        "read",
        return_value={
            "events": [
                {
                    "seq": 5,
                    "type": "provider_response",
                    "response": {"output_text": "Claim: x_i is unverified."},
                }
            ]
        },
    ):
        assert (
            text_conversion._saved_transcript_text("saved", "session", "event.5")
            == "Claim: x_i is unverified."
        )
        try:
            text_conversion._saved_transcript_text("saved", "session", "event.6")
        except ProjectError:
            pass
        else:
            raise AssertionError("Unknown event was converted")
        try:
            text_conversion._saved_transcript_text("saved", "session", "../event.5")
        except ProjectError:
            pass
        else:
            raise AssertionError("Unallowlisted source path was accepted")


def test_running_session_settings_update_preserves_in_flight_slots() -> None:
    """Live edits keep accepted/in-flight work, and never obtain the idle-worker lock."""
    from contextlib import nullcontext
    from copy import deepcopy

    from sigma import projects, research_sessions
    from sigma.projects import ProjectError

    original = {
        "id": "active-fixture",
        "status": "running",
        "scheduler_version": 2,
        "cycle_limit": 2,
        "call_ceiling_cycles": 2,
        "supervisor_ceiling_calls": 2,
        "call_limit": 6,
        "total_token_limit": 1000000,
        "output_token_limit": 256,
        "model": "gpt-6-luna",
        "turns_are_flat": True,
        "turns_per_round": 2,
        "research_round_limit": 1,
        "session_settings": {
            "name": "",
            "brainstorm_mode": False,
            "supervisor_mode": "none",
            "unlimited_turns": False,
            "turn_limit": 2,
        },
        "strategy_runs": [{"strategy_id": "first", "status": "running", "cycle": 2}],
        "steps": [
            {
                "id": "accepted",
                "strategy_id": "first",
                "role": "skeptic",
                "cycle": 1,
                "status": "completed",
            },
            {
                "id": "in-flight",
                "strategy_id": "first",
                "role": "investigator",
                "cycle": 2,
                "status": "running",
            },
        ],
    }
    stored = {"record": deepcopy(original)}
    saves = []

    def read(_path, _session_id):
        return deepcopy(stored["record"])

    def save(_path, record):
        saves.append(deepcopy(record))
        stored["record"] = deepcopy(record)

    async def apply(settings):
        return await research_sessions.update_session_configuration(
            "/live.sigma", "active-fixture", settings
        )

    updated = {
        "name": "Active research",
        "brainstorm_mode": True,
        "supervisor_mode": "heavy",
        "unlimited_turns": False,
        "turn_limit": 3,
    }
    with (
        patch.object(research_sessions, "_read", side_effect=read),
        patch.object(research_sessions, "_save_unlocked", side_effect=save),
        patch.object(research_sessions, "_project_manager_lock", return_value=nullcontext()),
        patch.object(
            research_sessions,
            "_idle_worker_lock",
            side_effect=AssertionError("Live worker was fenced"),
        ),
        patch.object(
            research_sessions, "_recover", side_effect=AssertionError("Running call was recovered")
        ),
        patch.object(projects, "project_write_lock", return_value=nullcontext()),
        patch.object(research_sessions, "_event"),
        patch.object(research_sessions, "_public", side_effect=lambda record: deepcopy(record)),
    ):
        result = asyncio.run(apply(updated))
        assert result["session_settings"] == updated
        assert result["cycle_limit"] == 3
        assert result["call_limit"] == 9
        assert result["steps"] == original["steps"]
        assert result["strategy_runs"] == original["strategy_runs"]
        assert len(saves) == 1
        # A second live edit of name and steering must not reserve more calls.
        again = asyncio.run(apply({**updated, "name": "Renamed", "supervisor_mode": "light"}))
        assert again["session_settings"]["name"] == "Renamed"
        assert again["session_settings"]["supervisor_mode"] == "light"
        assert again["call_limit"] == 9
        assert again["steps"] == original["steps"]
        try:
            asyncio.run(apply({**updated, "turn_limit": 1}))
        except ProjectError as exc:
            assert "already executed" in str(exc)
        else:
            raise AssertionError("A live edit reduced the limit below an in-flight turn")
        assert len(saves) == 2


def test_live_settings_recheck_latest_checkpoint_before_persisting() -> None:
    """A different worker may checkpoint between the first read and the write lock."""
    from contextlib import nullcontext
    from copy import deepcopy

    from sigma import projects, research_sessions
    from sigma.projects import ProjectError

    base = {
        "id": "cross-process-fixture",
        "status": "running",
        "scheduler_version": 2,
        "cycle_limit": 3,
        "session_settings": {"turn_limit": 3},
        "strategy_runs": [{"strategy_id": "s", "status": "running", "cycle": 1}],
        "steps": [],
    }
    advanced = deepcopy(base)
    advanced["strategy_runs"][0]["cycle"] = 3
    advanced["steps"].append({"role": "investigator", "cycle": 3, "status": "running"})
    reads = iter([base, advanced])
    with (
        patch.object(research_sessions, "_read", side_effect=lambda *_: deepcopy(next(reads))),
        patch.object(research_sessions, "_project_manager_lock", return_value=nullcontext()),
        patch.object(projects, "project_write_lock", return_value=nullcontext()),
        patch.object(
            research_sessions, "_save_unlocked", side_effect=AssertionError("Stale write")
        ),
    ):
        try:
            asyncio.run(
                research_sessions.update_session_configuration(
                    "/live.sigma", "cross-process-fixture", {"turn_limit": 2}
                )
            )
        except ProjectError as exc:
            assert "already executed" in str(exc)
        else:
            raise AssertionError("The stale checkpoint was used for a live configuration edit")


def main() -> None:
    with tempfile.TemporaryDirectory(prefix="sigma-session-log-") as directory:
        root = Path(directory)
        test_session_log_frames_preserve_multiline_content_and_recover_tail(root / "roundtrip")
        test_session_log_concurrent_appends_are_serialized_and_append_only(root / "parallel")
        test_session_log_event_json_is_valid_for_multiline_and_markdown(root)
        test_readable_markdown_pairs_provider_traffic_and_keeps_canonical_json(root)
        test_legacy_and_markdown_frames_can_be_read_from_the_same_append_only_file(root)
        test_session_log_short_name_is_stable_and_delete_scoped(root / "lifecycle")
        test_session_log_failure_is_best_effort(root / "failure")
        test_slow_storage_does_not_block_research_caller_and_keeps_order(root / "slow")
        test_delayed_session_a_write_does_not_block_session_b_read(root / "isolated-read")
        test_project_deletion_waits_for_read_and_cleans_logs(root / "delete-race")
        test_session_log_filename_short_name_fallback_and_sanitization()
        test_saved_reference_diagnostics_and_markdown_export()
        test_session_log_download_route_content_and_name()
        test_project_session_log_exports_latest_and_all()
        test_session_status_and_correlated_errors_match_export()
        test_flat_turn_settings_convert_legacy_rounds_without_relabeling()
        test_user_turn_default_migration_and_validation(root)
        test_complete_transcript_export_groups_turns_newest_first()
        test_extended_completed_session_plans_new_slots_without_replaying_history()
        test_extension_preserves_partial_pair_and_refuses_duplicate_accepted_steps()
        test_unlimited_turn_growth_does_not_extend_finished_branches()
        test_brainstorm_second_participant_has_constructive_guidance()
        test_supervisor_response_validation_and_process_guidance()
        test_supervisor_usage_is_authoritative_and_uncertain_cost_is_retained()
        test_abandoned_supervisor_reservation_preserves_full_liability()
        test_pending_supervisor_reviews_only_run_once_after_resume()
        test_running_session_settings_update_preserves_in_flight_slots()
        test_live_settings_recheck_latest_checkpoint_before_persisting()
        test_transcript_conversion_uses_server_saved_event_only()
        from test_project_diagnostics import (
            test_client_report_and_copy_download_share_canonical_record,
            test_logging_failure_is_reported_without_breaking_admission,
            test_pre_session_rejection_persists_same_sanitized_error,
            test_project_errors_survive_reload_without_creating_sessions,
        )

        test_project_errors_survive_reload_without_creating_sessions(root / "diagnostics-project")
        test_client_report_and_copy_download_share_canonical_record(root / "diagnostics-client")
        test_logging_failure_is_reported_without_breaking_admission(root / "diagnostics-cap")
        test_pre_session_rejection_persists_same_sanitized_error(root / "diagnostics-admission")
    print(
        "Session log append, reference diagnostics, filenames, concurrency, redaction and recovery scenarios passed."
    )


if __name__ == "__main__":
    main()
