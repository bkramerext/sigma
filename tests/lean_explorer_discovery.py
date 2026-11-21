"""Automatic Lean evidence discovery from only a local source root."""

from pathlib import Path
from tempfile import TemporaryDirectory
from unittest.mock import patch

from fastapi.testclient import TestClient

from sigma import lean_explorer_discovery, lean_explorer_local
from sigma.api import app


def check_auto_discovery() -> None:
    with TemporaryDirectory() as temporary:
        base = Path(temporary)
        tree = base / "lean"
        (tree / "Formal" / "Deep").mkdir(parents=True)
        (tree / "Other").mkdir()
        (tree / ".lake" / "packages").mkdir(parents=True)
        (tree / "Formal" / "Deep" / "Field.lean").write_text(
            "import Mathlib\n"
            "theorem automorphicPeriod : True := trivial\n"
            "theorem characterAverage : True := trivial\n",
            encoding="utf-8",
        )
        (tree / "Other" / "Representations.lean").write_text(
            "def GaloisRepresentation : Prop := True\n"
            "theorem fieldCompatibility : True := trivial\n",
            encoding="utf-8",
        )
        (tree / "Main.lean").write_text(
            "def RiemannZetaZerosOnLine : Prop := True\n"
            "theorem analyticPrimeSum : True := trivial\n",
            encoding="utf-8",
        )
        (tree / ".lake" / "packages" / "Hidden.lean").write_text(
            "theorem automorphicPeriodHidden : True := trivial\n",
            encoding="utf-8",
        )
        state = base / "state"
        state.mkdir()
        with (
            patch("sigma.lean_explorer_local.state_directory", return_value=state),
            patch("sigma.lean_explorer_dossiers.state_directory", return_value=state),
            patch("sigma.lean_explorer_local.require_local"),
            patch("sigma.api._require_local_lean_request"),
        ):
            manifest = lean_explorer_local.configure(str(tree))
            assert manifest["file_count"] == 3
            updates: list[tuple[int, int, int, str]] = []
            found = lean_explorer_discovery.discover(
                "automorphic-foundation",
                lambda files, total, size, current: updates.append(
                    (files, total, size, current)
                ),
            )
            assert found["complete"] is True
            assert found["files_scanned"] == 3
            assert updates[-1][0:2] == (3, 3)
            assert found["source_root_id"] == manifest["root_id"]
            assert found["candidates"]
            names = {candidate["name"] for candidate in found["candidates"]}
            assert "automorphicPeriod" in names
            assert "GaloisRepresentation" in names
            assert all("Hidden" not in candidate["path"] for candidate in found["candidates"])
            assert all(candidate["sha256"] for candidate in found["candidates"])
            assert all(
                candidate["status"] == "lexical_candidate_not_dependency"
                for candidate in found["candidates"]
            )

            client = TestClient(app)
            dossier = client.post(
                "/api/explorelean/dossiers",
                json={"source_mode": "local", "section_id": "automorphic-foundation"},
            )
            assert dossier.status_code == 201, dossier.text
            identifier = dossier.json()["id"]
            discovery = client.post(
                f"/api/explorelean/dossiers/{identifier}/discover",
                json={"section_id": "automorphic-foundation"},
            )
            assert discovery.status_code == 200, discovery.text
            assert '"type": "progress"' in discovery.text
            assert '"type": "complete"' in discovery.text
            updated = client.get(f"/api/explorelean/dossiers/{identifier}")
            assert updated.status_code == 200
            record = updated.json()
            assert record["discovery"]["complete"] is True
            assert len(record["scope"]) >= 2
            assert all(
                src["selection_origin"] == "automatic_lexical_discovery"
                for src in record["scope"]
            )
            assert all(
                src["path"] in {candidate["path"] for candidate in found["candidates"]}
                for src in record["scope"]
            )
            second = client.post(
                f"/api/explorelean/dossiers/{identifier}/discover",
                json={"section_id": "automorphic-foundation"},
            )
            assert second.status_code == 200
            assert len(
                client.get(f"/api/explorelean/dossiers/{identifier}").json()["scope"]
            ) == len(record["scope"])
            wrong_section = client.post(
                f"/api/explorelean/dossiers/{identifier}/discover",
                json={"section_id": "reflection"},
            )
            assert wrong_section.status_code == 422

            (tree / "Other" / "Representations.lean").write_text(
                "def GaloisRepresentation : Prop := False\n",
                encoding="utf-8",
            )
            stale = client.post(
                f"/api/explorelean/dossiers/{identifier}/paper-project",
                json={"source_mode": "local"},
            )
            # Existing scope hashes prevent making a paper from mutated source.
            assert stale.status_code >= 400
            lean_explorer_local._cached_modules.cache_clear()


if __name__ == "__main__":
    check_auto_discovery()
    print("Automatic Lean evidence discovery passed.")
