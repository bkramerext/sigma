"""Executable round-trip and rejection checks for project bundles."""

import base64
import json
import tempfile
from pathlib import Path

from sigma.project_bundle import BundleError, delete_file, download_bytes, encode, import_bundle, list_files, migrate, read_bundle, read_file, restore, snapshot, transform_file, update_files, write_file


def main() -> None:
    with tempfile.TemporaryDirectory() as directory:
        root = Path(directory)
        source = root / "example.sigma"
        source.mkdir()
        (source / "project.json").write_text('{"schema_version": 9, "id": "example"}')
        (source / "research-sessions").mkdir()
        (source / "research-sessions" / "session.json").write_bytes(b'{"status":"complete"}')
        (source / "artifacts").mkdir()
        (source / "artifacts" / "evidence.bin").write_bytes(bytes(range(256)))
        bundle = snapshot(source)
        assert json.loads(encode(source)) == bundle
        migrated = root / "portable.json"
        assert migrate(source, migrated) == migrated
        assert json.loads(migrated.read_text()) == bundle
        assert (source / "project.json").exists(), "Migration removed original project"
        try:
            migrate(source, migrated)
        except BundleError:
            pass
        else:
            raise AssertionError("Migration replaced an existing JSON file")
        assert json.loads(migrated.read_text()) == bundle
        original_project = read_file(migrated, "project.json")
        original_evidence = read_file(migrated, "artifacts/evidence.bin")
        write_file(migrated, "research-sessions/session.json", b'{"status":"revised"}')
        assert read_file(migrated, "research-sessions/session.json") == b'{"status":"revised"}'
        assert read_file(migrated, "project.json") == original_project
        assert read_file(migrated, "artifacts/evidence.bin") == original_evidence
        assert (source / "research-sessions" / "session.json").read_bytes() == b'{"status":"complete"}'
        try:
            write_file(migrated, "../escape", b"unsafe")
        except BundleError:
            pass
        else:
            raise AssertionError("Unsafe member path accepted")
        assert not (root / "escape").exists()
        assert "artifacts/evidence.bin" in list_files(migrated)
        write_file(migrated, "artifacts/transient.bin", b"temporary")
        assert "artifacts/transient.bin" in list_files(migrated)
        delete_file(migrated, "artifacts/transient.bin")
        assert "artifacts/transient.bin" not in list_files(migrated)
        assert read_file(migrated, "artifacts/evidence.bin") == original_evidence
        update_files(migrated, {
            "research-sessions/second.json": b'{"status":"complete"}',
            "artifacts/new-evidence.bin": b"binary\\x00data",
            "research-sessions/session.json": None,
        })
        assert "research-sessions/session.json" not in list_files(migrated)
        assert read_file(migrated, "research-sessions/second.json") == b'{"status":"complete"}'
        assert read_file(migrated, "artifacts/new-evidence.bin") == b"binary\\x00data"
        assert read_file(migrated, "project.json") == original_project
        transformed = transform_file(
            migrated, "research-sessions/second.json",
            lambda previous: previous.replace(b"complete", b"reviewed"),
        )
        assert transformed == b'{"status":"reviewed"}'
        assert read_file(migrated, "research-sessions/second.json") == transformed
        assert read_file(migrated, "artifacts/evidence.bin") == original_evidence
        try:
            delete_file(migrated, "project.json")
        except BundleError:
            pass
        else:
            raise AssertionError("Deleted mandatory project document")

        destination = root / "restored.sigma"
        restore(bundle, destination)
        for relative in ("project.json", "research-sessions/session.json", "artifacts/evidence.bin"):
            assert (destination / relative).read_bytes() == (source / relative).read_bytes()
        try:
            restore(bundle, destination)
        except BundleError:
            pass
        else:
            raise AssertionError("Existing destination was overwritten")
        corrupted = {**bundle, "files": {**bundle["files"], "../escape": "YQ=="}}
        try:
            restore(corrupted, root / "bad.sigma")
        except BundleError:
            pass
        else:
            raise AssertionError("Unsafe path accepted")
        assert not (root / "bad.sigma").exists()
        invalid_source = root / "invalid.sigma"
        invalid_source.mkdir()
        (invalid_source / "project.json").write_text('{"not_a_project":true}')
        try:
            migrate(invalid_source, root / "invalid.json")
        except BundleError:
            pass
        else:
            raise AssertionError("Migrated invalid project document")
        assert not (root / "invalid.json").exists()
        corrupted_schema = {
            **bundle,
            "files": {
                **bundle["files"],
                "project.json": "eyJzY2hlbWFfdmVyc2lvbiI6dHJ1ZX0=",
            },
        }
        try:
            restore(corrupted_schema, root / "bad-schema.sigma")
        except BundleError:
            pass
        else:
            raise AssertionError("Boolean schema version accepted")
        assert not (root / "bad-schema.sigma").exists()
        # Ten regression checks for the portable project interchange boundary.
        assert read_bundle(migrated)["format"] == bundle["format"]
        assert json.loads(download_bytes(migrated)) == read_bundle(migrated)
        assert read_bundle(migrated)["files"]["artifacts/evidence.bin"] == base64.b64encode(original_evidence).decode("ascii")
        imported = root / "imported.json"
        assert import_bundle(read_bundle(migrated), imported) == imported
        assert read_bundle(imported) == read_bundle(migrated)
        assert read_file(imported, "research-sessions/second.json") == b'{"status":"reviewed"}'
        assert read_file(imported, "artifacts/evidence.bin") == original_evidence
        try:
            import_bundle(read_bundle(migrated), imported)
        except BundleError:
            pass
        else:
            raise AssertionError("Import overwrote an existing project")
        assert read_bundle(imported) == read_bundle(migrated)
        try:
            import_bundle({**bundle, "files": {**bundle["files"], "../escape": "YQ=="}}, root / "unsafe.json")
        except BundleError:
            pass
        else:
            raise AssertionError("Import accepted a traversal path")
        assert not (root / "unsafe.json").exists()
        try:
            import_bundle(bundle, root / "not-json.sigma")
        except BundleError:
            pass
        else:
            raise AssertionError("Import accepted a non-JSON destination")
        assert not (root / "not-json.sigma").exists()
        try:
            read_bundle(source / "project.json")
        except BundleError:
            pass
        else:
            raise AssertionError("Legacy document misidentified as complete bundle")
        try:
            import_bundle({**bundle, "version": True}, root / "bad-version.json")
        except BundleError:
            pass
        else:
            raise AssertionError("Boolean bundle version accepted")
        assert not (root / "bad-version.json").exists()
        symlink_source = root / "symlink.sigma"
        symlink_source.mkdir()
        (symlink_source / "project.json").write_text('{"schema_version":9}')
        (symlink_source / "outside").symlink_to(root / "restored.sigma", target_is_directory=True)
        try:
            snapshot(symlink_source)
        except BundleError:
            pass
        else:
            raise AssertionError("Symlink directory was followed or silently omitted")
    # Exercise the four public project-layer entry points with isolated storage.
    import os
    from unittest.mock import patch
    from sigma.projects import (
        ProjectError, create_json_project, export_complete_project,
        inspect_project, list_json_projects, migrate_project,
    )

    with tempfile.TemporaryDirectory() as directory:
        root = Path(directory)
        with patch.dict(os.environ, {"SIGMA_PROJECTS_ROOT": str(root),
                                     "SIGMA_STATE_DIR": str(root / "state")}):
            # The application root and Recent index are private and separate.
            (root / "state").mkdir(mode=0o700)
            created = create_json_project("Portable Experiment", "Investigate an example")
            assert Path(created.path).is_file()
            assert Path(created.path).suffix == ".json"
            assert inspect_project(created.path).project == created.project
            # Execution records and binary outputs are stored as bundle members;
            # only transient liveness locks use the private sidecar directory.
            from sigma.python_sandbox import (
                _execution_directory, _save_record, get_execution,
                get_execution_artifact, list_executions,
            )
            from uuid import uuid4
            execution_id = str(uuid4())
            execution = {
                "id": execution_id, "project_id": created.project.id,
                "created_at": "2026-10-26T12:00:00+00:00",
                "status": "running", "runtime": "python",
                "session_id": str(uuid4()), "strategy_id": "strategy-1", "cycle": 1,
                "source": "print('portable')",
            }
            runtime_directory = _execution_directory(created.path)
            _save_record(runtime_directory, execution)
            try:
                _save_record(runtime_directory, execution)
            except ProjectError as exc:
                assert "already reserved" in str(exc)
            else:
                raise AssertionError("Execution identifier collision was accepted")
            # An orphaned reservation is reported as interrupted, not rerun.
            assert get_execution(created.path, execution_id)["status"] == "interrupted"
            assert list_executions(created.path)[0]["status"] == "interrupted"
            duplicate = {
                **execution, "id": str(uuid4()),
            }
            try:
                _save_record(runtime_directory, duplicate)
            except ProjectError as exc:
                assert "already reserved" in str(exc)
            else:
                raise AssertionError("Duplicate execution reservation was accepted")
            final_execution = {**execution, "status": "completed"}
            try:
                _save_record(runtime_directory, execution, finalizing=True)
            except ProjectError as exc:
                assert "terminal status" in str(exc)
            else:
                raise AssertionError("Running execution was finalized")
            _save_record(
                runtime_directory, final_execution,
                (("result.bin", "application/octet-stream", bytes(range(128))),),
                finalizing=True,
            )
            saved_execution = get_execution(created.path, execution_id)
            assert saved_execution["status"] == "completed"
            try:
                get_execution(created.path, execution_id.upper())
            except ProjectError:
                pass
            else:
                raise AssertionError("Noncanonical execution identifier was accepted")
            try:
                _save_record(runtime_directory, {**execution, "id": str(uuid4()),
                             "project_id": "foreign-project"})
            except ProjectError:
                pass
            else:
                raise AssertionError("Foreign project execution was accepted")

            # Finalization failures cannot destroy the original reservation.
            wrong_id = str(uuid4())
            try:
                _save_record(runtime_directory, {**execution, "id": wrong_id,
                             "status": "completed"}, finalizing=True)
            except ProjectError:
                pass
            else:
                raise AssertionError("Unreserved execution was finalized")
            assert f"research-executions/{wrong_id}.json" not in list_files(created.path)
            assert {item["id"] for item in list_executions(created.path)} == {execution_id, extra_id}
            contents, media_type = get_execution_artifact(created.path, execution_id, "result.bin")
            assert contents == bytes(range(128))
            assert media_type == "application/octet-stream"
            assert f"research-executions/{execution_id}.json" in list_files(created.path)
            assert f"research-executions/{execution_id}.artifacts/result.bin" in list_files(created.path)
            # Duplicate output filenames and invalid finalizations must leave
            # the committed execution and its binary output unchanged.
            extra_id = str(uuid4())
            extra = {**execution, "id": extra_id, "source": "print('other')"}
            _save_record(runtime_directory, extra)
            try:
                _save_record(
                    runtime_directory, {**extra, "status": "completed"},
                    (("same.bin", "application/octet-stream", b"a"),
                     ("same.bin", "application/octet-stream", b"b")),
                    finalizing=True,
                )
            except ProjectError:
                pass
            else:
                raise AssertionError("Duplicate output filenames were accepted")
            assert get_execution(created.path, extra_id)["status"] == "interrupted"
            assert not any(
                name.startswith(f"research-executions/{extra_id}.artifacts/")
                for name in list_files(created.path)
            )
            assert get_execution_artifact(created.path, execution_id, "result.bin")[0] == bytes(range(128))
            # A complete export/import preserves executable evidence exactly.
            imported = root / "imported-execution.json"
            import_bundle(json.loads(export_complete_project(created.path)), imported)
            assert get_execution(imported, execution_id)["status"] == "completed"
            assert get_execution_artifact(imported, execution_id, "result.bin") == (
                bytes(range(128)), "application/octet-stream"
            )
            assert {item["id"] for item in list_executions(imported)} == {execution_id, extra_id}
            # Tampered binary evidence is rejected even when metadata survives.
            write_file(imported, f"research-executions/{execution_id}.artifacts/result.bin",
                       b"tampered")
            try:
                get_execution_artifact(imported, execution_id, "result.bin")
            except ProjectError:
                pass
            else:
                raise AssertionError("Corrupted imported execution artifact was accepted")
            assert created.project.id in {item.project.id for item in list_json_projects()}
            assert json.loads(export_complete_project(created.path)) == read_bundle(created.path)
            try:
                create_json_project("Portable Experiment", "Another experiment")
            except ProjectError:
                pass
            else:
                raise AssertionError("Duplicate JSON project was created")
            legacy = root / "legacy.sigma"
            legacy.mkdir()
            (legacy / "project.json").write_bytes(
                read_file(created.path, "project.json")
            )
            (legacy / "research-sessions").mkdir()
            (legacy / "research-sessions" / "result.json").write_bytes(b'{"done":true}')
            (legacy / "artifacts").mkdir()
            (legacy / "artifacts" / "binary.dat").write_bytes(bytes(range(256)))
            migrated = migrate_project(legacy)
            assert Path(migrated.path).suffix == ".json"
            assert migrated.project == created.project
            assert (legacy / "project.json").exists()
            assert read_file(migrated.path, "research-sessions/result.json") == b'{"done":true}'
            assert read_file(migrated.path, "artifacts/binary.dat") == bytes(range(256))
            assert json.loads(export_complete_project(legacy)) == read_bundle(migrated.path)
            try:
                migrate_project(legacy)
            except ProjectError:
                pass
            else:
                raise AssertionError("Migration overwrote existing destination")
            assert Path(migrated.path).is_file()
            # Research session records use the same authoritative JSON file.
            from uuid import uuid4
            from sigma.research_sessions import _save, _read, _all, read_session_snapshot

            session_id = str(uuid4())
            record = {
                "id": session_id,
                "project_id": created.project.id,
                "project_path": created.path,
                "created_at": "2026-01-01T00:00:00+00:00",
                "status": "paused",
                "session_number": 1,
            }
            _save(created.path, record)
            assert _read(created.path, session_id) == record
            # JSON session writes reject foreign ownership and invalid IDs.
            for invalid in (
                dict(record, project_id=str(uuid4())),
                dict(record, project_path=str(root / "foreign.json")),
                dict(record, id="../not-a-uuid"),
                dict(record, session_number=0),
                dict(record, session_number=True),
                dict(record, status=None),
            ):
                try:
                    _save(created.path, invalid)
                except ProjectError:
                    pass
                else:
                    raise AssertionError("Invalid session record was saved")
            assert _read(created.path, session_id) == record
            try:
                _save(created.path, dict(record, project_path=str(root / "other.json")))
            except ProjectError:
                pass
            else:
                raise AssertionError("Session project path was changed")
            # Existing session identity is immutable even if a caller attempts
            # to overwrite the same UUID with a different session number.
            try:
                _save(created.path, dict(record, session_number=99))
            except ProjectError:
                pass
            else:
                raise AssertionError("Session identity was overwritten")
            assert _all(created.path) == [record]
            assert read_session_snapshot(created.path) == ([record], 0)
            imported_session_path = root / "imported-session.json"
            import_bundle(json.loads(export_complete_project(created.path)), imported_session_path)
            imported_session = _read(str(imported_session_path), session_id)
            assert imported_session["project_path"] == str(imported_session_path.resolve())
            assert imported_session["project_id"] == created.project.id
            assert read_session_snapshot(str(imported_session_path))[1] == 0
            # Reject a bundle whose session filename and embedded ID disagree.
            malformed_bundle = json.loads(export_complete_project(created.path))
            bad_session = dict(record, id=str(uuid4()))
            malformed_bundle["files"][f"research-sessions/{session_id}.json"] = (
                base64.b64encode(json.dumps(bad_session).encode()).decode("ascii")
            )
            rejected_path = root / "rejected-session.json"
            try:
                import_bundle(malformed_bundle, rejected_path)
            except BundleError:
                pass
            else:
                raise AssertionError("Import accepted mismatched research session identity")
            assert not rejected_path.exists()
            # An unrelated foreign record must never influence session allocation.
            from sigma.project_bundle import write_file
            foreign_id = str(uuid4())
            write_file(created.path, f"research-sessions/{foreign_id}.json",
                       json.dumps(dict(record, id=foreign_id,
                                       project_id=str(uuid4()),
                                       session_number=100000)).encode())
            assert read_session_snapshot(created.path)[1] == 1
            from sigma.project_bundle import delete_file
            delete_file(created.path, f"research-sessions/{foreign_id}.json")
            from sigma.research_sessions import _worker_lock_path
            assert _worker_lock_path(created.path, session_id).parent == Path(created.path).parent
            assert not (Path(created.path) / "research-sessions").exists()
            wrong = dict(record, project_id=str(uuid4()))
            from sigma.project_bundle import write_file
            write_file(created.path, f"research-sessions/{session_id}.json",
                       json.dumps(wrong).encode())
            try:
                _read(created.path, session_id)
            except ProjectError:
                pass
            else:
                raise AssertionError("Foreign session was accepted")
            write_file(created.path, f"research-sessions/{session_id}.json",
                       json.dumps(record).encode())
            from sigma.research_sessions import (
                _allocate_session_number, get_limits, save_limits, DEFAULT_LIMITS,
            )
            assert get_limits(created.path) == dict(DEFAULT_LIMITS)
            # Existing malformed limits must never be mistaken for missing defaults.
            from sigma.project_bundle import write_file
            write_file(created.path, "research-sessions/limits.json", b"{invalid")
            try:
                get_limits(created.path)
            except ProjectError:
                pass
            else:
                raise AssertionError("Corrupt limits were silently reset")
            from sigma.project_bundle import delete_file
            delete_file(created.path, "research-sessions/limits.json")
            assert _allocate_session_number(created.path, []) == 2
            assert _allocate_session_number(created.path, []) == 3
            # Two concurrent allocators must never issue the same session number.
            from concurrent.futures import ThreadPoolExecutor

            with ThreadPoolExecutor(max_workers=6) as executor:
                numbers = list(executor.map(
                    lambda _: _allocate_session_number(created.path, []), range(24)
                ))
            assert sorted(numbers) == list(range(4, 28))
            assert json.loads(read_file(created.path, "research-sessions/sequence.json"))[
                "next_session_number"
            ] == 28
            assert save_limits(created.path, dict(DEFAULT_LIMITS)) == dict(DEFAULT_LIMITS)
            assert get_limits(created.path) == dict(DEFAULT_LIMITS)
            # Limits writes preserve unrelated session and artifact members.
            before_session = read_file(created.path, f"research-sessions/{session_id}.json")
            save_limits(created.path, dict(DEFAULT_LIMITS))
            assert read_file(created.path, f"research-sessions/{session_id}.json") == before_session
            assert read_file(created.path, "artifacts/trace.bin") == bytes(range(256))
            from sigma.research_sessions import _snapshot
            from sigma.project_bundle import transform_members

            view, guard = _snapshot(created.path)
            assert view.project.id == created.project.id
            assert isinstance(guard, str) and guard
            transform_members(created.path, lambda members: {
                "artifacts/proof.bin": bytes(range(256)),
                "evidence/notes.txt": b"independent evidence",
            })
            assert read_file(created.path, "artifacts/proof.bin") == bytes(range(256))
            assert read_file(created.path, "evidence/notes.txt") == b"independent evidence"
            from sigma.projects import save_project_artifacts, read_project_artifact

            save_project_artifacts(created.path, {
                "artifacts/report.html": b"<html>report</html>",
                "evidence/raw.bin": bytes(range(256)),
            })
            assert read_project_artifact(created.path, "artifacts/report.html") == b"<html>report</html>"
            assert read_project_artifact(created.path, "evidence/raw.bin") == bytes(range(256))
            try:
                save_project_artifacts(created.path, {"project.json": b"tamper"})
            except ProjectError:
                pass
            else:
                raise AssertionError("Artifact API allowed project overwrite")
            try:
                transform_members(created.path, lambda members: {
                    "artifacts/should-not-exist.bin": b"bad",
                    "project.json": None,
                })
            except BundleError:
                pass
            else:
                raise AssertionError("Invalid bundle transaction succeeded")
            assert "artifacts/should-not-exist.bin" not in list_files(created.path)
            # All-or-nothing evidence transaction: invalid second member
            # must not publish the first member.
            try:
                update_files(created.path, {
                    "evidence/partial.txt": b"must roll back",
                    "../escape.txt": b"invalid",
                })
            except BundleError:
                pass
            else:
                raise AssertionError("Unsafe evidence transaction succeeded")
            assert "evidence/partial.txt" not in list_files(created.path)
            # Transaction callback failures must leave the published file unchanged.
            from sigma.project_bundle import transform_members

            before = Path(created.path).read_bytes()

            def reject_transaction(members):
                raise ProjectError("simulated evidence validation failure")

            try:
                transform_members(created.path, reject_transaction)
            except ProjectError:
                pass
            else:
                raise AssertionError("Failed transaction unexpectedly committed")
            assert Path(created.path).read_bytes() == before
            assert read_file(created.path, f"research-sessions/{session_id}.json")
            assert json.loads(export_complete_project(created.path))["files"][
                f"research-sessions/{session_id}.json"
            ]
            # Complete format: edits, deletion and atomic multi-member changes
            # survive export and re-import with exact binary bytes.
            update_files(created.path, {
                "research-sessions/one.json": b'{"turn":1}',
                "artifacts/trace.bin": bytes(range(256)),
                "evidence/source.txt": b"source evidence",
            })
            assert set(list_files(created.path)) == {
                "project.json", f"research-sessions/{session_id}.json", "research-sessions/one.json",
                "artifacts/proof.bin", "evidence/notes.txt",
                "artifacts/report.html", "evidence/raw.bin",
                "artifacts/trace.bin", "evidence/source.txt",
                "research-sessions/sequence.json", "research-sessions/limits.json",
            }
            exported = json.loads(export_complete_project(created.path))
            assert exported["format"] == "sigma.project.bundle"
            assert exported["version"] == 1
            imported_path = root / "copy.json"
            import_bundle(exported, imported_path)
            assert read_bundle(imported_path) == exported
            assert read_file(imported_path, "artifacts/trace.bin") == bytes(range(256))
            assert read_file(imported_path, "evidence/source.txt") == b"source evidence"
            delete_file(created.path, "evidence/source.txt")
            assert "evidence/source.txt" not in list_files(created.path)
            assert "evidence/source.txt" in list_files(imported_path)
            # Simulate durable lifecycle transitions without provider calls.
            # Terminal sessions can be removed without touching the sequence.
            from sigma.research_sessions import remove_session

            lifecycle_id = str(uuid4())
            lifecycle = {
                "id": lifecycle_id,
                "project_id": created.project.id,
                "project_path": created.path,
                "created_at": "2026-01-01T00:00:00+00:00",
                "updated_at": "2026-01-01T00:00:00+00:00",
                "session_number": 28,
                "status": "queued",
            }
            for status in ("queued", "running", "paused", "running", "completed"):
                lifecycle["status"] = status
                _save(created.path, lifecycle)
                assert _read(created.path, lifecycle_id)["status"] == status
                assert any(item["id"] == lifecycle_id for item in read_session_snapshot(created.path)[0])
            removed = remove_session(
                created.path, lifecycle_id, lifecycle["updated_at"]
            )
            assert removed["removed"] and removed["session_number"] == 28
            assert f"research-sessions/{lifecycle_id}.json" not in list_files(created.path)
            assert _allocate_session_number(created.path, []) == 28
            # A nonterminal session must not be deleted, and a completed
            # session must reject stale optimistic-concurrency timestamps.
            lifecycle["status"] = "paused"
            _save(created.path, lifecycle)
            try:
                remove_session(created.path, lifecycle_id, lifecycle["updated_at"])
            except ProjectError:
                pass
            else:
                raise AssertionError("Paused session was removed")
            lifecycle["status"] = "completed"
            _save(created.path, lifecycle)
            try:
                remove_session(created.path, lifecycle_id, "stale-timestamp")
            except ProjectError:
                pass
            else:
                raise AssertionError("Stale session removal succeeded")
            assert _read(created.path, lifecycle_id)["status"] == "completed"
            # Creation uses the normal project schema and preserves options.
            customized = create_json_project(
                "Custom JSON", "Research with options",
                difficulty="hard", show_advanced_outcome_details=True,
            )
            assert customized.project.difficulty.value == "hard"
            assert customized.project.show_advanced_outcome_details is True
            assert read_bundle(customized.path)["files"]["project.json"]
            assert {item.project.id for item in list_json_projects()} >= {
                created.project.id, customized.project.id,
            }
    print("Project bundle round-trip and safety checks passed")


if __name__ == "__main__":
    main()
