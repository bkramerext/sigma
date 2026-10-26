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
    print("Project bundle round-trip and safety checks passed")


if __name__ == "__main__":
    main()
