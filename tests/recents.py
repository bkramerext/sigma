"""A11 stock catalog, persistent direct opens, and genuine four-item recents."""

import json
import os
import subprocess
from pathlib import Path
from tempfile import TemporaryDirectory
from unittest.mock import patch

from fastapi.testclient import TestClient

from sigma.api import app
from sigma.investigations import (
    ROOT,
    InvestigationError,
    create_investigation,
    create_strategy,
    inspect_investigation,
    open_investigation,
)
from sigma.recents import home_investigations, recent_investigations, state_directory
from sigma.stock import open_stock_investigation, stock_investigations


def check(root: Path, base: Path) -> None:
    sources = {path: path.read_bytes() for path in (ROOT / "examples").glob("*/investigation.json")}
    catalog = stock_investigations()["investigations"]
    assert len(catalog) >= 2
    assert {entry["title"] for entry in catalog} >= {
        "Nonconsecutive Subset Sums Modulo 3",
        "Did Jesus Use Cannabis?",
    }
    assert {entry["investigation_type"] for entry in catalog} >= {"default", "mathematical"}
    assert catalog[-1]["title"] == "Did Jesus Use Cannabis?"
    assert home_investigations()["investigations"] == [] and not list(root.iterdir())

    expanded = base / "extra-examples"
    expanded.mkdir()
    for number in range(6):
        location = expanded / f"sample-{number}"
        location.mkdir()
        (location / "investigation.json").write_bytes(next(iter(sources.values())))
    with patch("sigma.stock.EXAMPLES", expanded):
        assert len(stock_investigations()["investigations"]) == 6
    assert not list(root.iterdir())

    selected = next(item for item in catalog if item["investigation_type"] == "mathematical")
    source_path = ROOT / "examples" / selected["id"] / "investigation.json"
    first = open_stock_investigation(selected["id"])
    assert first.path == str(root / f"{selected['id']}.sigma")
    assert first.investigation.id == json.loads(sources[source_path])["id"]
    assert Path(first.path, "investigation.json").read_bytes() == sources[source_path]
    assert open_stock_investigation(selected["id"]) == first
    assert len(list(root.iterdir())) == 1
    assert recent_investigations()["investigations"] == []
    edited = create_strategy(first.path, "My addition", "Investigate this case")
    reopened = open_stock_investigation(selected["id"])
    assert reopened.investigation == edited.investigation
    assert (
        stock_investigations()["investigations"][0]["strategy_count"]
        == selected["strategy_count"] + 1
    )
    assert recent_investigations()["investigations"] == []
    assert Path(first.path, "investigation.json").read_bytes() != sources[source_path]

    other = open_stock_investigation(catalog[-1]["id"])
    assert other.path != first.path and other.investigation.id != first.investigation.id
    assert len(list(root.iterdir())) == 2 and recent_investigations()["investigations"] == []
    try:
        open_stock_investigation("../../unknown")
        raise AssertionError("An unknown stock identifier was accepted")
    except InvestigationError:
        pass

    collision = root / f"{selected['id']}.sigma"
    moved = root / "saved-stock.sigma"
    collision.rename(moved)
    impostor = create_investigation(selected["id"], "Different research")
    assert impostor.path == str(collision)
    try:
        open_stock_investigation(selected["id"])
        raise AssertionError("A different investigation was opened as stock")
    except InvestigationError as error:
        assert "different investigation occupies" in str(error)
    assert inspect_investigation(collision).investigation == impostor.investigation
    collision.rename(root / "saved-impostor.sigma")
    moved.rename(collision)
    assert open_stock_investigation(selected["id"]).investigation == edited.investigation

    created = [create_investigation(f"User investigation {i}", "Own research") for i in range(5)]
    actual = [entry["id"] for entry in recent_investigations()["investigations"]]
    expected = [view.investigation.id for view in reversed(created)] + [impostor.investigation.id]
    assert actual == expected, (actual, expected)
    open_investigation(created[0].path)
    assert recent_investigations()["investigations"][0]["id"] == created[0].investigation.id
    assert len(recent_investigations()["investigations"]) == 6
    open_investigation(first.path)
    assert all(
        entry["id"] != first.investigation.id for entry in recent_investigations()["investigations"]
    )

    with TestClient(app) as api:
        before = (state_directory() / "recents.json").read_bytes()
        assert len(api.get("/api/investigations/recent").json()["investigations"]) == 6
        assert (state_directory() / "recents.json").read_bytes() == before
        assert (
            api.get("/api/investigations/stock").json()["investigations"]
            == stock_investigations()["investigations"]
        )
        response = api.post("/api/investigations/stock/open", json={"stock_id": selected["id"]})
        assert response.status_code == 200
        assert response.json()["path"] == first.path
        assert len(list(root.glob(f"{selected['id']}.sigma"))) == 1
        assert (
            api.post("/api/investigations/stock/open", json={"stock_id": "unknown"}).status_code
            == 400
        )
        assert (
            api.post(
                "/api/investigations/stock/copy", json={"stock_id": selected["id"]}
            ).status_code
            == 404
        )
        assert (
            api.post(
                "/api/investigations/recent/forget",
                json={"investigation_id": created[0].investigation.id},
            ).status_code
            == 200
        )
    command = subprocess.run(
        [str(ROOT / "sigma"), "create", "--title", "CLI recent", "--problem", "Own work"],
        capture_output=True,
        text=True,
        check=True,
    )
    assert (
        recent_investigations()["investigations"][0]["id"]
        == json.loads(command.stdout)["investigation"]["id"]
    )

    # Old automatic example entries disappear from Recents without deleting research.
    index_path = state_directory() / "recents.json"
    index = json.loads(index_path.read_text())
    index["entries"] = [
        {
            "id": first.investigation.id,
            "path": first.path,
            "accessed_at": None,
            "included_example": True,
        },
        *index["entries"][:3],
    ]
    index_path.write_text(json.dumps(index))
    assert all(not entry["included_example"] for entry in home_investigations()["investigations"])
    assert len(recent_investigations()["investigations"]) == 3
    assert inspect_investigation(first.path).investigation == edited.investigation
    assert all(path.read_bytes() == original for path, original in sources.items())
    print(
        "PASS unlimited stock discovery, stable direct opens and retained edits, collision safety, source immutability, no stock recents, API/CLI and six-item LRU"
    )


def main() -> None:
    with TemporaryDirectory() as temporary:
        base = Path(temporary)
        root = base / "investigations"
        root.mkdir()
        root = root.resolve()
        with patch.dict(
            os.environ, {"SIGMA_PROJECTS_ROOT": str(root), "SIGMA_STATE_DIR": str(base / "state")}
        ):
            check(root, base)


if __name__ == "__main__":
    main()
