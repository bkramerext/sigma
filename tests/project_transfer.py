"""V4 project interchange: directory runtime, one zstd artifact archive."""

from __future__ import annotations

import base64
import hashlib
import io
import json
import tarfile
from pathlib import Path
from tempfile import TemporaryDirectory
from unittest.mock import patch

from sigma import (
    project_bundle,
    project_diagnostic_bundle,
    project_evidence,
    project_transfer,
    research_supplied_evidence,
)
from sigma.project_bundle import BundleError
from sigma.projects import initialize_project, inspect_project
from sigma.zstd_codec import compress


def _expect_failure(call) -> None:
    try:
        call()
    except BundleError:
        return
    raise AssertionError("Unsafe or unsupported bundle was accepted")


def test_single_archive_roundtrip() -> None:
    with TemporaryDirectory() as temporary:
        root = Path(temporary)
        origin = root / "original.sigma"
        initialize_project(origin, "Original", "What follows from the premises?")
        link = project_evidence.add_link(str(origin), "https://example.org/report")
        pdf = b"%PDF-1.7 fake test source"
        with patch.object(
            project_evidence, "_extract", return_value=(2, "[PDF page 1]\nPremise A", False)
        ):
            attached = project_evidence.add_evidence(str(origin), "source.pdf", pdf)
            compiled_pdf = research_supplied_evidence.compile_entry(
                str(origin),
                {
                    "id": "uploaded-pdf:" + attached["id"],
                    "sha256": attached["sha256"],
                    "filename": attached["filename"],
                },
                "11111111-1111-4111-8111-111111111111",
            )
        with patch.object(
            research_supplied_evidence,
            "_fetch_url",
            return_value=(b"Linked premise B", "text/plain", link["url"]),
        ):
            compiled = research_supplied_evidence.compile_entry(
                str(origin),
                {"id": "uploaded-link:" + link["id"], "url": link["url"]},
                "11111111-1111-4111-8111-111111111111",
            )
        assert compiled["status"] == "retrieved"
        paper_dir = origin / "artifacts" / "generated_papers"
        paper_dir.mkdir(parents=True)
        (paper_dir / "example.tex").write_text("Generated paper TeX", encoding="utf-8")
        stored = project_transfer.export_project(origin)
        payload = json.loads(stored)
        assert payload["version"] == 4
        assert payload["artifacts"]["encoding"] == "tar+zstd+base64"
        assert set(payload) == {"format", "version", "files", "artifacts"}
        assert not any(key.startswith("artifacts/") for key in payload["files"])
        assert payload["files"]["project.json"]["source_material_links"][0]["id"] == link["id"]
        members = project_transfer.decode_bundle(payload)
        assert members[f"artifacts/source_material/{attached['id']}.pdf"] == pdf
        assert members[compiled_pdf["snapshot_path"]] == pdf
        assert members[compiled["snapshot_path"] + ".bin"] == b"Linked premise B"
        assert members["artifacts/generated_papers/example.tex"] == b"Generated paper TeX"
        new = root / "imported.sigma"
        project_transfer.import_project(payload, new)
        assert new.is_dir()
        assert inspect_project(new).project.id != inspect_project(origin).project.id
        assert (
            new / "artifacts" / "generated_papers" / "example.tex"
        ).read_text() == "Generated paper TeX"
        assert project_evidence.get_pdf(str(new), attached["id"])[1] == pdf
        assert (new / compiled_pdf["snapshot_path"]).read_bytes() == pdf
        assert (new / (compiled["snapshot_path"] + ".bin")).read_bytes() == b"Linked premise B"
        restored_sources = project_evidence.list_evidence(str(new))
        assert [row["kind"] for row in restored_sources] == ["file", "link"]
        assert restored_sources[0]["id"] == attached["id"]
        assert restored_sources[0]["filename"] == attached["filename"]
        assert restored_sources[1]["id"] == link["id"]
        assert restored_sources[1]["url"] == link["url"]
        _expect_failure(lambda: project_transfer.decode_bundle({**payload, "version": 3}))


def test_multiframe_artifact_archive_is_lossless_and_bounded() -> None:
    # Use tiny frames so the test exercises the >256 MiB TAR code path
    # without allocating a large fixture. All actual member size limits stay
    # enforced by the production codec.
    artifacts = {
        "artifacts/source_material/a.txt": bytes(range(256)) * 128,
        "artifacts/generated_papers/b.tex": b"sample paper" * 2700,
    }
    with patch.object(project_transfer, "MAX_ARCHIVE_FRAME_BYTES", 2048):
        encoded = project_transfer._archive(artifacts)
        assert encoded["uncompressed_size"] > 2048
        assert project_transfer._unarchive(encoded) == artifacts

        packed = base64.b64decode(encoded["data"])
        extra = {
            **encoded,
            "data": base64.b64encode(packed + compress(b"surprise")).decode("ascii"),
        }
        _expect_failure(lambda: project_transfer._unarchive(extra))
        missing_final_frame = {
            **encoded,
            "data": base64.b64encode(packed[:-20]).decode("ascii"),
        }
        _expect_failure(lambda: project_transfer._unarchive(missing_final_frame))


def test_total_size_includes_metadata_and_artifacts() -> None:
    members = {
        "project.json": b'{"schema_version": 13}',
        "notes.txt": b"x" * 8192,
        "artifacts/source_material/premise.txt": b"y" * 4096,
    }
    bundle = project_transfer.make_bundle(members)
    # Each section fits below the limit; their combined size does not.
    with patch.object(project_transfer, "MAX_BUNDLE_BYTES", 11000):
        _expect_failure(lambda: project_transfer.make_bundle(members))
        _expect_failure(lambda: project_transfer.decode_bundle(bundle))


def test_rejects_traversal_in_archive() -> None:
    with TemporaryDirectory() as temporary:
        origin = Path(temporary) / "original.sigma"
        initialize_project(origin, "Original", "A research problem")
        payload = json.loads(project_transfer.export_project(origin))
        stream = io.BytesIO()
        with tarfile.open(fileobj=stream, mode="w") as archive:
            item = tarfile.TarInfo("artifacts/../../outside.txt")
            item.size = 4
            archive.addfile(item, io.BytesIO(b"evil"))
        raw = stream.getvalue()
        payload["artifacts"] = {
            "encoding": project_transfer.ARCHIVE_ENCODING,
            "uncompressed_size": len(raw),
            "sha256": hashlib.sha256(raw).hexdigest(),
            "data": base64.b64encode(compress(raw)).decode("ascii"),
        }
        _expect_failure(lambda: project_transfer.decode_bundle(payload))


def test_private_diagnostic_roundtrip() -> None:
    from uuid import uuid4

    from sigma import session_log

    with TemporaryDirectory() as temporary:
        root = Path(temporary)
        origin = root / "original.sigma"
        initialize_project(origin, "Original", "A synthetic research problem")
        project_id = inspect_project(origin).project.id
        session_id = str(uuid4())
        sessions = origin / "research-sessions"
        sessions.mkdir(exist_ok=True)
        (sessions / f"{session_id}.json").write_text(
            json.dumps(
                {
                    "id": session_id,
                    "project_id": project_id,
                    "project_path": str(origin),
                    "session_number": 1,
                    "status": "stopped",
                    "steps": [
                        {
                            "id": "synthetic-step",
                            "provider_input_audit": {"status": "prepared_before_dispatch"},
                            "context_manifest": {"sources": []},
                        }
                    ],
                    "strategy_assessments": [],
                    "interventions": [],
                    "cost_status": "unavailable",
                }
            )
        )
        log = session_log.log_path(str(origin), project_id, session_id)
        log.parent.parent.mkdir(mode=0o700)
        log.parent.mkdir(mode=0o700)
        session_log._ensure(log, project_id, session_id, 1)
        session_log._append_frame(
            log,
            {
                "type": "provider_request",
                "seq": 1,
                "request_id": "synthetic-request",
                "request": {
                    "input": json.dumps(
                        {"premise": "Synthetic research premise", "token": "unsafe-test-token"}
                    ),
                    "headers": {"Authorization": "unsafe-synthetic-secret"},
                },
                "authorization": "unsafe-synthetic-secret",
            },
        )
        session_log._append_frame(
            log,
            {
                "type": "provider_failure",
                "seq": 3,
                "request_id": "synthetic-request",
                "status": "timeout",
                "elapsed_seconds": 1.5,
                "response_wire": "opaque unsafe-wire-secret",
            },
        )
        ordinary = json.loads(project_transfer.export_project(origin))
        assert "diagnostics" not in ordinary
        diagnostic = json.loads(project_transfer.export_project(origin, diagnostics=True))
        archive = diagnostic["diagnostics"]
        assert archive["private"] is True
        assert len(archive["blobs"]) == 1
        members = project_transfer.decode_bundle(diagnostic)
        passive = {
            name: data
            for name, data in members.items()
            if name.startswith(project_diagnostic_bundle.PREFIX)
        }
        assert len(passive) == 1
        raw = next(iter(passive.values()))
        snapshot = json.loads(raw)
        assert snapshot["source_session_id"] == session_id
        assert json.loads(snapshot["events"][0]["request"]["input"]) == {
            "premise": "Synthetic research premise"
        }
        assert b"unsafe-test-token" not in raw
        assert b"unsafe-wire-secret" not in raw
        assert "opaque_wire_omitted" in snapshot["events"][1]["omissions"]
        assert snapshot["events"][1]["elapsed_seconds"] == 1.5
        assert b"unsafe-synthetic-secret" not in raw
        assert snapshot["events"][1]["request_id"] == "synthetic-request"
        assert snapshot["availability"] == "partial"
        assert snapshot["coverage"] == "best_effort_not_complete"
        assert snapshot["saved_evidence"]["request_audits"] == 1
        assert snapshot["saved_evidence"]["context_manifests"] == 1
        assert snapshot["saved_evidence"]["strategy_assessments"] == 0
        imported = root / "imported.sigma"
        project_transfer.import_project(diagnostic, imported)
        assert "diagnostics" not in json.loads(project_transfer.export_project(imported))
        legacy_out = json.loads(project_bundle.encode(imported))
        assert not any(name.startswith("diagnostics/") for name in legacy_out["files"])
        injected = {
            **legacy_out,
            "files": {**legacy_out["files"], next(iter(passive)): raw.decode()},
        }
        _expect_failure(lambda: project_transfer.decode_bundle(injected))
        _expect_failure(
            lambda: project_bundle.import_bundle(injected, root / "legacy-injection.json")
        )
        _expect_failure(
            lambda: project_bundle.import_independent_bundle(
                injected, root / "independent-injection.json"
            )
        )
        invalid = {
            **ordinary,
            "files": {**ordinary["files"], "diagnostics/invalid.bin": "private"},
        }
        _expect_failure(lambda: project_transfer.decode_bundle(invalid))
        again = json.loads(project_transfer.export_project(imported, diagnostics=True))
        assert again["diagnostics"]["blobs"] == archive["blobs"]
        passive_file = next((imported / "diagnostics").rglob("*.bin"))
        assert passive_file.stat().st_mode & 0o777 == 0o600
        passive_file.chmod(0o644)
        try:
            _expect_failure(lambda: project_transfer.export_project(imported, diagnostics=True))
            assert "diagnostics" not in json.loads(project_transfer.export_project(imported))
        finally:
            passive_file.chmod(0o600)
        assert session_id not in again["diagnostics"]["sessions"]
        assert len(again["diagnostics"]["sessions"]) == 1
        assert not (root / ".sigma-session-logs" / inspect_project(imported).project.id).exists()
        imported_session_id = next(iter(again["diagnostics"]["sessions"]))
        stored_record = json.loads(
            (imported / "research-sessions" / f"{imported_session_id}.json").read_text()
        )
        assert stored_record["steps"][0]["context_manifest"] == {"sources": []}
        assert (
            stored_record["steps"][0]["provider_input_audit"]["status"]
            == "prepared_before_dispatch"
        )
        assert stored_record["status"] == "stopped"
        preserved = root / "preserved.sigma"
        project_transfer.import_project(
            diagnostic, preserved, independent=False, preserve_identity=True
        )
        assert inspect_project(preserved).project.id == project_id
        preserved_export = json.loads(project_transfer.export_project(preserved, diagnostics=True))
        assert project_transfer.decode_bundle(preserved_export)
        assert preserved_export["diagnostics"]["blobs"] == archive["blobs"]

        digest = next(iter(archive["blobs"]))
        entry = archive["blobs"][digest]
        corrupted = {**archive, "blobs": {digest: {**entry, "size": 999999999}}}
        _expect_failure(
            lambda: project_transfer.decode_bundle({**diagnostic, "diagnostics": corrupted})
        )
        _expect_failure(
            lambda: project_transfer.decode_bundle(
                {
                    **diagnostic,
                    "diagnostics": {**archive, "sessions": {str(uuid4()): [digest]}},
                }
            )
        )
        tampered = {**archive, "blobs": {"0" * 64: entry}, "sessions": {session_id: ["0" * 64]}}
        _expect_failure(
            lambda: project_transfer.decode_bundle({**diagnostic, "diagnostics": tampered})
        )
        with patch.object(project_diagnostic_bundle, "MAX_DIAGNOSTIC_BYTES", 10):
            _expect_failure(lambda: project_transfer.decode_bundle(diagnostic))
        # Torn trailing record is distinguishable from a clean retained log.
        with log.open("ab") as stream:
            stream.write(b"\n<!-- SIGMA_EVENT 100 -->\n{")
        torn = json.loads(project_transfer.export_project(origin, diagnostics=True))
        torn_members = project_transfer.decode_bundle(torn)
        torn_snapshot = next(
            json.loads(data)
            for name, data in torn_members.items()
            if name.startswith(project_diagnostic_bundle.PREFIX)
        )
        assert torn_snapshot["availability"] == "partial"
        print(
            f"Diagnostic synthetic snapshot: {len(raw)} bytes uncompressed, "
            f"{len(json.dumps(archive))} bytes encoded archive."
        )


def test_recorder_coverage_and_cross_mapping() -> None:
    from uuid import uuid4

    from sigma import session_log

    with TemporaryDirectory() as temporary:
        root = Path(temporary)
        origin = root / "coverage.sigma"
        initialize_project(origin, "Coverage", "Synthetic research")
        project_id = inspect_project(origin).project.id
        sessions = origin / "research-sessions"
        sessions.mkdir(exist_ok=True)
        first, missing = str(uuid4()), str(uuid4())
        for number, session_id in enumerate((first, missing), 1):
            record = {
                "project_id": project_id,
                "id": session_id,
                "project_path": str(origin),
                "session_number": number,
                "status": "stopped",
                "steps": [],
            }
            (sessions / f"{session_id}.json").write_text(json.dumps(record))
        log_context = {"project_id": project_id, "id": first, "session_number": 1}
        for request_id in ("attempt-one", "attempt-two"):
            session_log.append(
                str(origin),
                log_context,
                {
                    "type": "provider_request",
                    "role": "investigator",
                    "request_id": request_id,
                    "request": {
                        "model": "mock-model",
                        "input": [
                            {
                                "role": "user",
                                "content": json.dumps(
                                    {
                                        "context_manifest": {"sources": []},
                                        "token": "synthetic-private-token",
                                    }
                                ),
                            }
                        ],
                    },
                },
            )
            session_log.append(
                str(origin),
                log_context,
                {
                    "type": "provider_failure",
                    "role": "investigator",
                    "request_id": request_id,
                    "status": "timeout",
                    "elapsed_seconds": 0.2,
                },
            )
        session_log.flush()
        payload = json.loads(project_transfer.export_project(origin, diagnostics=True))
        archive = payload["diagnostics"]
        members = project_transfer.decode_bundle(payload)
        snapshots = {
            json.loads(raw)["source_session_id"]: json.loads(raw)
            for name, raw in members.items()
            if name.startswith(project_diagnostic_bundle.PREFIX)
        }
        assert snapshots[first]["availability"] == "retained"
        assert snapshots[missing]["availability"] == "unavailable"
        assert snapshots[missing]["saved_evidence"]["request_audits"] == 0
        events = snapshots[first]["events"]
        assert [event["seq"] for event in events] == [1, 2, 3, 4]
        assert [event["request_id"] for event in events] == [
            "attempt-one",
            "attempt-one",
            "attempt-two",
            "attempt-two",
        ]
        context = json.loads(events[0]["request"]["input"][0]["content"])
        assert context == {"context_manifest": {"sources": []}}
        swapped = {
            **archive,
            "sessions": {
                first: archive["sessions"][missing],
                missing: archive["sessions"][first],
            },
        }
        _expect_failure(lambda: project_transfer.decode_bundle({**payload, "diagnostics": swapped}))
        foreign = {**snapshots[first], "source_project_id": str(uuid4())}
        foreign_raw = project_diagnostic_bundle._json(foreign)
        foreign_digest = hashlib.sha256(foreign_raw).hexdigest()
        duplicated = project_diagnostic_bundle.encode(
            {
                f"{project_diagnostic_bundle.PREFIX}{current}/{foreign_digest}.bin": foreign_raw
                for current in (first, missing)
            }
        )
        _expect_failure(
            lambda: project_transfer.decode_bundle({**payload, "diagnostics": duplicated})
        )
        malformed = {**foreign, "source_session_id": "not-a-uuid"}
        malformed_raw = project_diagnostic_bundle._json(malformed)
        malformed_digest = hashlib.sha256(malformed_raw).hexdigest()
        _expect_failure(
            lambda: project_diagnostic_bundle.encode(
                {f"{project_diagnostic_bundle.PREFIX}{first}/{malformed_digest}.bin": malformed_raw}
            )
        )
        empty_mapping = {
            **archive,
            "sessions": {**archive["sessions"], missing: []},
        }
        _expect_failure(
            lambda: project_transfer.decode_bundle({**payload, "diagnostics": empty_mapping})
        )
        log = session_log.log_path(str(origin), project_id, first)
        session_log._append_frame(
            log,
            {"type": "retention_limit", "seq": 5, "message": "Synthetic retention marker"},
        )
        retained = project_transfer.decode_bundle(
            json.loads(project_transfer.export_project(origin, diagnostics=True))
        )
        snapshot = next(
            json.loads(raw)
            for name, raw in retained.items()
            if name.startswith(f"{project_diagnostic_bundle.PREFIX}{first}/")
        )
        assert snapshot["availability"] == "partial"
        assert snapshot["events"][-1]["type"] == "retention_limit"


def test_diagnostic_resource_budget() -> None:
    import tracemalloc
    from uuid import uuid4

    project_id, session_id = str(uuid4()), str(uuid4())
    members = {
        "project.json": json.dumps({"schema_version": 13, "id": project_id}).encode(),
        f"research-sessions/{session_id}.json": json.dumps(
            {"project_id": project_id, "id": session_id}
        ).encode(),
    }
    snapshot = project_diagnostic_bundle._json(
        {
            "source_project_id": project_id,
            "source_session_id": session_id,
            "availability": "retained",
            "coverage": "best_effort_not_complete",
            "saved_evidence": {
                "steps": None,
                "request_audits": None,
                "context_manifests": None,
                "strategy_assessments": None,
                "interventions": None,
                "cost_status": None,
            },
            "events": [
                {
                    "type": "provider_request",
                    "seq": 1,
                    "request": {"instructions": "A synthetic research premise. " * 35000},
                }
            ],
        }
    )
    digest = hashlib.sha256(snapshot).hexdigest()
    path = f"{project_diagnostic_bundle.PREFIX}{session_id}/{digest}.bin"
    tracemalloc.start()
    try:
        archive = project_diagnostic_bundle.encode({path: snapshot})
        assert project_diagnostic_bundle.decode(archive, members, budget=len(snapshot)) == {
            path: snapshot
        }
        _, peak = tracemalloc.get_traced_memory()
    finally:
        tracemalloc.stop()
    assert len(json.dumps(archive)) < len(snapshot)
    _expect_failure(
        lambda: project_diagnostic_bundle.decode(archive, members, budget=len(snapshot) - 1)
    )
    payload = project_transfer.make_bundle(members)
    payload["diagnostics"] = archive
    with patch.object(
        project_transfer,
        "MAX_BUNDLE_BYTES",
        sum(
            map(len, project_transfer.decode_bundle(project_transfer.make_bundle(members)).values())
        )
        + len(snapshot)
        - 1,
    ):
        _expect_failure(lambda: project_transfer.decode_bundle(payload))
    print(
        f"Diagnostic stress: raw={len(snapshot)}, encoded={len(json.dumps(archive))}, "
        f"Python allocation peak={peak} bytes (excludes preexisting payload and native allocations)"
    )


def test_diagnostic_mixed_entropy_budget() -> None:
    import random
    import resource
    import tracemalloc
    from uuid import uuid4

    rng = random.Random(928)
    project_id = str(uuid4())
    members = {"project.json": json.dumps({"schema_version": 13, "id": project_id}).encode()}
    passive = {}
    for _ in range(3):
        session_id = str(uuid4())
        members[f"research-sessions/{session_id}.json"] = json.dumps(
            {"project_id": project_id, "id": session_id}
        ).encode()
        # Repeated scientific prose plus deterministic high-entropy mock result.
        # No actual user or provider bytes are used.
        text = "Synthetic scientific reasoning. " * 4000
        result = base64.b64encode(rng.randbytes(160_000)).decode()
        snapshot = project_diagnostic_bundle._json(
            {
                "source_project_id": project_id,
                "source_session_id": session_id,
                "availability": "retained",
                "coverage": "best_effort_not_complete",
                "saved_evidence": {
                    "steps": None,
                    "request_audits": None,
                    "context_manifests": None,
                    "strategy_assessments": None,
                    "interventions": None,
                    "cost_status": None,
                },
                "events": [
                    {
                        "type": "provider_request",
                        "seq": 1,
                        "request_id": "synthetic",
                        "request": {"input": text},
                    },
                    {
                        "type": "provider_response",
                        "seq": 2,
                        "request_id": "synthetic",
                        "response": {
                            "output": [
                                {
                                    "type": "message",
                                    "content": [{"type": "output_text", "text": result}],
                                }
                            ],
                        },
                    },
                ],
            }
        )
        digest = hashlib.sha256(snapshot).hexdigest()
        passive[f"{project_diagnostic_bundle.PREFIX}{session_id}/{digest}.bin"] = snapshot
    raw_bytes = sum(map(len, passive.values()))
    rss_before = resource.getrusage(resource.RUSAGE_SELF).ru_maxrss
    tracemalloc.start()
    try:
        archive = project_diagnostic_bundle.encode(passive)
        assert project_diagnostic_bundle.decode(archive, members, budget=raw_bytes) == passive
        _, peak = tracemalloc.get_traced_memory()
    finally:
        tracemalloc.stop()
    rss_after = resource.getrusage(resource.RUSAGE_SELF).ru_maxrss
    encoded_bytes = len(json.dumps(archive).encode())
    assert encoded_bytes < raw_bytes
    assert encoded_bytes > raw_bytes // 4
    # Reject before entering the compressed-member decoder.
    with patch.object(project_bundle, "_decode", side_effect=AssertionError("decode entered")):
        _expect_failure(
            lambda: project_diagnostic_bundle.decode(archive, members, budget=raw_bytes - 1)
        )
    print(
        f"Diagnostic mixed entropy: 3 snapshots, raw={raw_bytes}, encoded={encoded_bytes}, "
        f"Python allocation peak={peak}; process RSS high-water before/after="
        f"{rss_before}/{rss_after} (KiB on Linux, bytes on macOS)"
    )


def test_bounded_log_observation() -> None:
    from sigma import session_log

    with TemporaryDirectory() as temporary:
        target = Path(temporary) / "fixture.md"
        legacy = json.dumps({"type": "provider_request", "seq": 1}).encode()
        target.write_bytes(
            b"Header\n<!-- SIGMA_EVENT "
            + str(len(legacy)).encode()
            + b" -->\n"
            + legacy
            + b"\n<!-- END_SIGMA_EVENT -->\n"
        )
        target.chmod(0o600)
        session_log._append_frame(
            target,
            {"type": "provider_failure", "seq": 2},
            "Synthetic failure",
        )
        original = target.read_bytes()
        observation = project_diagnostic_bundle._observe_log(target, len(original) + 100)
        assert observation is not None
        raw, changed = observation
        assert raw == original and not changed
        assert session_log._parse_frames(raw) == session_log._frames(target)[0]
        assert [event["seq"] for event in session_log._parse_frames(raw)] == [1, 2]
        with target.open("ab") as stream:
            stream.write(b"\n<!-- SIGMA_EVENT 999 -->\n{")
        observation = project_diagnostic_bundle._observe_log(target, len(original) + 100)
        assert observation is not None
        torn, changed = observation
        assert not changed
        assert len(session_log._parse_frames(torn)) == 2
        assert torn.count(b"\n<!-- SIGMA_EVENT ") == 3
        target.write_bytes(original)
        _expect_failure(lambda: project_diagnostic_bundle._observe_log(target, len(original) - 1))

        real_fstat = project_diagnostic_bundle.os.fstat
        calls = 0

        def grow_after_open(fd: int):
            nonlocal calls
            calls += 1
            info = real_fstat(fd)
            if calls == 1:
                with target.open("ab") as stream:
                    stream.write(b"\nnew data")
            return info

        with patch.object(project_diagnostic_bundle.os, "fstat", side_effect=grow_after_open):
            observation = project_diagnostic_bundle._observe_log(target, len(original) + 100)
        assert observation is not None
        observed, partial = observation
        assert observed == original and partial
        target.write_bytes(original)
        calls = 0

        def replace_after_open(fd: int):
            nonlocal calls
            calls += 1
            info = real_fstat(fd)
            if calls == 1:
                target.rename(target.with_suffix(".old"))
                target.write_bytes(b"Replacement")
                target.chmod(0o600)
            return info

        with patch.object(project_diagnostic_bundle.os, "fstat", side_effect=replace_after_open):
            _expect_failure(
                lambda: project_diagnostic_bundle._observe_log(target, len(original) + 100)
            )
        target.unlink()
        target.symlink_to(target.with_suffix(".old"))
        _expect_failure(lambda: project_diagnostic_bundle._observe_log(target, len(original) + 100))


if __name__ == "__main__":
    test_single_archive_roundtrip()
    test_multiframe_artifact_archive_is_lossless_and_bounded()
    test_total_size_includes_metadata_and_artifacts()
    test_rejects_traversal_in_archive()
    test_private_diagnostic_roundtrip()
    test_recorder_coverage_and_cross_mapping()
    test_diagnostic_resource_budget()
    test_diagnostic_mixed_entropy_budget()
    test_bounded_log_observation()
    print("PASS v4 artifact archive, source links, restored files and unsafe path rejection.")
