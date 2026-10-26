"""Executable round-trip and rejection checks for project bundles."""

import json
import tempfile
from pathlib import Path

from sigma.project_bundle import BundleError, encode, migrate, restore, snapshot


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
