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
            }
            _save(created.path, record)
            assert _read(created.path, session_id) == record
            assert _all(created.path) == [record]
            assert read_session_snapshot(created.path) == ([record], 0)
            from sigma.research_sessions import (
                _allocate_session_number, get_limits, save_limits, DEFAULT_LIMITS,
            )
            assert get_limits(created.path) == dict(DEFAULT_LIMITS)
            assert _allocate_session_number(created.path, []) == 1
            assert _allocate_session_number(created.path, []) == 2
            # Two concurrent allocators must never issue the same session number.
            from concurrent.futures import ThreadPoolExecutor

            with ThreadPoolExecutor(max_workers=6) as executor:
                numbers = list(executor.map(
                    lambda _: _allocate_session_number(created.path, []), range(24)
                ))
            assert sorted(numbers) == list(range(3, 27))
            assert json.loads(read_file(created.path, "research-sessions/sequence.json"))[
                "next_session_number"
            ] == 27
            assert save_limits(created.path, dict(DEFAULT_LIMITS)) == dict(DEFAULT_LIMITS)
            assert get_limits(created.path) == dict(DEFAULT_LIMITS)
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
                "artifacts/trace.bin", "evidence/source.txt",
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
