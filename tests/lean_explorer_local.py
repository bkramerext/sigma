"""Local Lean directory acceptance: large-tree semantics without external network."""

from pathlib import Path
from tempfile import TemporaryDirectory
from unittest.mock import patch

from fastapi.testclient import TestClient

from sigma import lean_explorer_local
from sigma.api import app
from sigma.projects import ProjectError


def check_local_directory() -> None:
    with TemporaryDirectory() as temp:
        base = Path(temp)
        project = base / "extracted-lean"
        (project / "src" / "Proofs").mkdir(parents=True)
        (project / "Mathlib" / "Analysis").mkdir(parents=True)
        (project / ".lake" / "packages" / "mathlib").mkdir(parents=True)
        (project / "src" / "Statements.lean").write_text(
            "import Mathlib\ndef RiemannZetaZerosOnLine : Prop := True\n",
            encoding="utf-8",
        )
        (project / "src" / "Proofs" / "Bridge.lean").write_text(
            "theorem arithmeticBridge : True := trivial\n", encoding="utf-8"
        )
        (project / "Mathlib" / "Analysis" / "Prelude.lean").write_text(
            "lemma localFixture : True := trivial\n", encoding="utf-8"
        )
        (project / ".lake" / "packages" / "mathlib" / "Ignored.lean").write_text(
            "def ignored : Nat := 0\n", encoding="utf-8"
        )
        outside = base / "private.lean"
        outside.write_text("def secret : Nat := 999\n", encoding="utf-8")
        (project / "src" / "Forbidden.lean").symlink_to(outside)
        (project / "src" / "Linked").symlink_to(base, target_is_directory=True)
        state_root = base / "state"
        state_root.mkdir()

        with (
            patch("sigma.lean_explorer_local.state_directory", return_value=state_root),
            patch("sigma.lean_explorer_local.require_local", return_value=None),
            patch("sigma.api._require_local_lean_request", return_value=None),
        ):
            updates: list[tuple[int, int, str]] = []
            manifest = lean_explorer_local.configure(
                str(project), lambda dirs, files, current: updates.append(
                    (dirs, files, current)
                )
            )
            assert manifest["file_count"] == 3
            assert updates[-1][1] == 3
            files = lean_explorer_local.list_files("src/", 0, 10)
            assert files["total_files"] == 3
            assert files["total_matches"] == 2
            assert files["files"] == [
                "src/Proofs/Bridge.lean",
                "src/Statements.lean",
            ]
            payload, relative, revision, url = lean_explorer_local.read_module(
                "src/Statements.lean"
            )
            assert b"RiemannZetaZerosOnLine" in payload
            assert "src/Statements.lean" in relative
            assert revision.startswith("local:")
            assert url == ""

            for invalid in ("../private.lean", "/etc/passwd", "src/Forbidden.lean"):
                try:
                    lean_explorer_local.read_module(invalid)
                except ProjectError:
                    pass
                else:
                    raise AssertionError(f"Unsafe local Lean file accepted: {invalid}")

            client = TestClient(app)
            scan = client.post(
                "/api/explorelean/local-index",
                json={"directory": str(project)},
            )
            assert scan.status_code == 200, scan.text
            assert '"type": "complete"' in scan.text
            assert '"file_count": 3' in scan.text
            status = client.get("/api/explorelean/local-status")
            assert status.status_code == 200
            assert status.json()["source"]["file_count"] == 3
            listing = client.get(
                "/api/explorelean/local-files", params={"query": "Bridge"}
            )
            assert listing.status_code == 200
            assert listing.json()["files"] == ["src/Proofs/Bridge.lean"]

            declaration = client.get(
                "/api/explorelean/declaration",
                params={
                    "path": "src/Statements.lean",
                    "name": "RiemannZetaZerosOnLine",
                    "source_mode": "local",
                },
            )
            assert declaration.status_code == 200, declaration.text
            assert declaration.json()["commit"].startswith("local:")
            dossier = client.post(
                "/api/explorelean/dossiers",
                json={"source_mode": "local"},
            )
            assert dossier.status_code == 201, dossier.text
            identifier = dossier.json()["id"]
            note = client.post(
                f"/api/explorelean/dossiers/{identifier}/notes",
                json={
                    "source_mode": "local",
                    "formal_path": "src/Statements.lean",
                    "declaration": "RiemannZetaZerosOnLine",
                    "text": "Check this statement against the formalized goal.",
                },
            )
            assert note.status_code == 201, note.text
            assert note.json()["source"]["commit"] == revision
            export = client.get(
                f"/api/explorelean/dossiers/{identifier}/markdown"
            )
            assert export.status_code == 200
            assert "Local source: src/Statements.lean" in export.text
            assert "Check this statement" in export.text

            # A working directory is mutable; a changed file gets a new hash.
            before = declaration.json()["sha256"]
            (project / "src" / "Statements.lean").write_text(
                "def RiemannZetaZerosOnLine : Prop := False\n", encoding="utf-8"
            )
            after = client.get(
                "/api/explorelean/declaration",
                params={
                    "path": "src/Statements.lean",
                    "name": "RiemannZetaZerosOnLine",
                    "source_mode": "local",
                },
            )
            assert after.status_code == 200
            assert after.json()["sha256"] != before
            lean_explorer_local._cached_modules.cache_clear()


if __name__ == "__main__":
    check_local_directory()
    print("Local Lean directory acceptance passed.")
