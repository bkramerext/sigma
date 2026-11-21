"""Local Lean directory acceptance: large-tree semantics without external network."""

from pathlib import Path
from tempfile import TemporaryDirectory
from types import SimpleNamespace
from unittest.mock import AsyncMock, patch

from fastapi.testclient import TestClient

from sigma import lean_explorer_discovery, lean_explorer_local
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
            "theorem arithmeticBridge : True := trivial\n"
            "theorem thetaLiftBound : True := trivial\n",
            encoding="utf-8",
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
                str(project), lambda dirs, files, current: updates.append((dirs, files, current))
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
            listing = client.get("/api/explorelean/local-files", params={"query": "Bridge"})
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
                json={"source_mode": "local", "section_id": "theta-slopes"},
            )
            assert dossier.status_code == 201, dossier.text
            identifier = dossier.json()["id"]
            assert dossier.json()["section_title"] == "Theta-lift chains, divisibility and slopes"
            for declaration_path, declaration_name in (
                ("src/Statements.lean", "RiemannZetaZerosOnLine"),
                ("src/Proofs/Bridge.lean", "arithmeticBridge"),
            ):
                selected_scope = client.post(
                    f"/api/explorelean/dossiers/{identifier}/scope",
                    json={
                        "source_mode": "local",
                        "formal_path": declaration_path,
                        "declaration": declaration_name,
                    },
                )
                assert selected_scope.status_code == 200, selected_scope.text
            assert len(selected_scope.json()["scope"]) == 2

            # No user-selected source paths: discover the section from the indexed
            # root, recover a real candidate, and persist its exact source hash.
            proposed = lean_explorer_discovery.discover("theta-slopes")
            assert proposed["complete"] is True
            assert proposed["scanned_files"] == 3
            assert proposed["index_type"].startswith("lexical")
            assert any(item["name"] == "thetaLiftBound" for item in proposed["candidates"])
            auto = client.post(
                "/api/explorelean/discover",
                json={
                    "source_mode": "local",
                    "section_id": "theta-slopes",
                    "dossier_id": identifier,
                },
            )
            assert auto.status_code == 200, auto.text
            assert '"type": "complete"' in auto.text
            recovered = client.get(f"/api/explorelean/dossiers/{identifier}").json()
            assert recovered["discovery"]["scanned_files"] == 3
            assert recovered["discovery"]["complete"] is True
            auto_scope = [item for item in recovered["scope"] if item["name"] == "thetaLiftBound"]
            assert len(auto_scope) == 1
            assert auto_scope[0]["selection_origin"] == "automatic_lexical_candidate"
            assert auto_scope[0]["sha256"]
            assert "not elaborated" in recovered["discovery"]["index_type"]
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
            # A mathematical section spans different files and directories.
            bridge = client.post(
                f"/api/explorelean/dossiers/{identifier}/notes",
                json={
                    "source_mode": "local",
                    "formal_path": "src/Proofs/Bridge.lean",
                    "declaration": "arithmeticBridge",
                    "text": "Study the arithmetic argument supporting the theta lift.",
                },
            )
            assert bridge.status_code == 201, bridge.text
            assert bridge.json()["source"]["path"] == "src/Proofs/Bridge.lean"
            assert len(client.get(f"/api/explorelean/dossiers/{identifier}").json()["entries"]) == 2
            export = client.get(f"/api/explorelean/dossiers/{identifier}/markdown")
            assert export.status_code == 200
            assert "Local source: src/Statements.lean" in export.text
            assert "Check this statement" in export.text

            # A single Explore request traverses all bounded batches, saving a
            # checkpoint after each pass instead of requiring repeated clicks.
            continued = client.post(
                "/api/explorelean/dossiers",
                json={"source_mode": "local", "section_id": "theta-slopes"},
            )
            assert continued.status_code == 201
            continued_id = continued.json()["id"]
            with patch("sigma.lean_explorer_discovery.MAX_SCAN_FILES", 1):
                frame = client.post(
                    "/api/explorelean/discover",
                    json={
                        "source_mode": "local",
                        "section_id": "theta-slopes",
                        "dossier_id": continued_id,
                    },
                )
                assert frame.status_code == 200, frame.text
                assert frame.text.count('"type": "stage"') >= 3
                assert frame.text.count('"type": "complete"') == 1
                record = client.get(f"/api/explorelean/dossiers/{continued_id}").json()
                assert record["discovery"]["next_offset"] == 3
                assert record["discovery"]["scanned_files"] == 3
                assert record["discovery"]["complete"] is True
                assert any(item["name"] == "thetaLiftBound" for item in record["scope"])

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


def check_large_single_file_end_to_end() -> None:
    """One click: large local module -> candidates -> model -> dossier -> paper handoff.

    The model and project destination are mocked; actual source scanning, the
    SSE endpoints, provenance checks and saved dossier are exercised.
    """
    with TemporaryDirectory() as temp:
        base = Path(temp)
        root = base / "lean-root"
        target = (
            root / "src" / "Development" / "AbelianVarietyTheory"
            / "Definitions" / "AutomorphicMembership" / "ExistsSameData.lean"
        )
        target.parent.mkdir(parents=True)
        parts = ["import Mathlib", "namespace AutomorphicMembership"]
        for index in range(10):
            parts.append(f"theorem automorphicBridge{index} : True := by trivial")
            parts.extend(
                "-- Substantial explanatory Lean source context. "
                + "A local automorphic bridge is being studied. " * 4
                for _ in range(55)
            )
        parts.append("end AutomorphicMembership")
        text = "\n".join(parts) + "\n"
        assert len(text.encode()) > 70_000
        target.write_text(text, encoding="utf-8")
        relative = target.relative_to(root).as_posix()
        state_root = base / "state"
        state_root.mkdir()
        with (
            patch("sigma.lean_explorer_local.state_directory", return_value=state_root),
            patch("sigma.lean_explorer_dossiers.state_directory", return_value=state_root),
            patch("sigma.lean_explorer_local.require_local", return_value=None),
            patch("sigma.api._require_local_lean_request", return_value=None),
        ):
            manifest = lean_explorer_local.configure(str(root))
            assert manifest["file_count"] == 1
            client = TestClient(app)
            created = client.post(
                "/api/explorelean/dossiers",
                json={"source_mode": "local", "section_id": "automorphic-foundation"},
            )
            assert created.status_code == 201, created.text
            identifier = created.json()["id"]
            discovered = client.post(
                "/api/explorelean/discover",
                json={
                    "source_mode": "local",
                    "section_id": "automorphic-foundation",
                    "dossier_id": identifier,
                    "single_file_trial": True,
                },
            )
            assert discovered.status_code == 200, discovered.text
            assert '"type": "complete"' in discovered.text
            result = client.get(f"/api/explorelean/dossiers/{identifier}").json()
            assert result["discovery"]["single_file_trial"] is True
            assert result["discovery"]["selected_file"] == relative
            assert result["discovery"]["selected_file_bytes"] == len(text.encode())
            assert result["discovery"]["scanned_files"] == 1
            assert result["discovery"]["complete"] is True
            assert len(result["scope"]) == 3
            assert all(item["path"] == relative for item in result["scope"])
            assert all(item["sha256"] for item in result["scope"])
            assert all(
                item["selection_origin"] == "automatic_lexical_candidate"
                for item in result["scope"]
            )
            first = result["scope"][0]
            config = {
                "available": True,
                "models": [{"id": "test-model", "efforts": ["medium"]}],
            }
            response = AsyncMock(
                return_value=(
                    "# A human-readable examination of automorphic bridges\n\n"
                    "The supplied source contains three selected declarations. "
                    "No formal dependency or complete RH proof is established."
                )
            )
            with (
                patch("sigma.api.chat.configuration", new=AsyncMock(return_value=config)),
                patch("sigma.api.chat.respond", new=response),
            ):
                analyzed = client.post(
                    "/api/explorelean/analyze",
                    json={
                        "formal_path": first["path"],
                        "declaration": first["name"],
                        "source_mode": "local",
                        "include_guide": False,
                        "include_announcement": False,
                        "model": "test-model",
                        "reasoning_effort": "medium",
                        "objective": "Produce sourced mathematical exposition",
                        "dossier_id": identifier,
                    },
                )
            assert analyzed.status_code == 200, analyzed.text
            assert '"saved": true' in analyzed.text
            input_text = response.call_args.kwargs["repeated_text"]
            assert len(input_text) < 48_000
            assert all(item["name"] in input_text for item in result["scope"])
            dossier = client.get(f"/api/explorelean/dossiers/{identifier}").json()
            assert len(dossier["entries"]) == 1
            assert "human-readable" in dossier["entries"][0]["text"]
            assert dossier["entries"][0]["source"]["sha256"] == first["sha256"]

            fake_project = SimpleNamespace(
                path="/tmp/lean-large-trial.sigma",
                project=SimpleNamespace(id="large-lean-trial"),
            )
            with (
                patch("sigma.api._limit_anonymous_demo_projects"),
                patch(
                    "sigma.global_research_settings.load_config",
                    return_value={"ai_model": "test-model", "reasoning_effort": "medium"},
                ),
                patch("sigma.projects.create_project", return_value=fake_project) as create,
                patch("sigma.project_collaboration.register_owner"),
            ):
                handoff = client.post(
                    f"/api/explorelean/dossiers/{identifier}/paper-project",
                    json={"source_mode": "local"},
                )
            assert handoff.status_code == 200, handoff.text
            assert handoff.json()["project_id"] == "large-lean-trial"
            context = create.call_args.args[-1]
            assert len(context) <= 20_000
            assert relative in context
            assert "Paper-context excerpt truncated: True" in context
            assert "A human-readable examination" in context
            exported = client.get(f"/api/explorelean/dossiers/{identifier}/markdown")
            assert exported.status_code == 200
            assert "A human-readable examination" in exported.text
            assert "automorphicBridge" in exported.text
            lean_explorer_local._cached_modules.cache_clear()


if __name__ == "__main__":
    check_large_single_file_end_to_end()
    check_local_directory()
    print("Local Lean directory acceptance passed.")
