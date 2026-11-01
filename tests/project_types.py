"""Unified project type catalog, transactional persistence and session safeguards."""

import asyncio
import base64
import os
from io import BytesIO
from pathlib import Path
from tempfile import TemporaryDirectory
from unittest.mock import AsyncMock, patch
from uuid import uuid4

import test_environment as _test_environment  # noqa: F401
from fastapi.testclient import TestClient
import httpx
from PIL import Image

from sigma import project_type_icons, project_types, research_sessions
from sigma.api import app
from sigma.projects import (
    ProjectError,
    create_project,
    create_strategy,
    initialize_project,
    inspect_project,
)


def check_icon_generation_mock() -> None:
    # The actual SIGMA PNG style asset is sent as image input. This test never
    # uses an API credential or makes a paid call.
    image = BytesIO()
    Image.new("RGBA", (32, 32), (219, 160, 103, 255)).save(image, format="PNG")
    encoded = base64.b64encode(image.getvalue()).decode("ascii")

    class FakeClient:
        def __init__(self, **_kwargs):
            pass

        async def __aenter__(self):
            return self

        async def __aexit__(self, *_args):
            return None

        async def post(self, url, *, headers, data, files):
            assert url.endswith("/images/edits")
            assert headers["Authorization"] == "Bearer test-not-real"
            assert data["model"].startswith("gpt-image-")
            assert data["background"] == "transparent"
            assert "Marine biology" in data["prompt"]
            name, reference, mime = files["image"]
            assert name.endswith(".png") and mime == "image/png"
            assert reference == project_type_icons.STYLE_REFERENCE.read_bytes()
            return httpx.Response(200, json={"data": [{"b64_json": encoded}]})

    with (
        patch("sigma.cloud_workspaces.enabled", return_value=False),
        patch.object(
            project_type_icons, "auth_context",
            new=AsyncMock(return_value={
                "mode": "api_key", "status": "connected", "identity": "api_key", "token": "test-not-real",
            }),
        ),
        patch.object(project_type_icons.httpx, "AsyncClient", FakeClient),
        patch.object(
            project_type_icons, "provider_endpoint",
            return_value="https://example.invalid/v1/images/edits",
        ),
    ):
        icon = asyncio.run(
            project_type_icons.generate_icon("Marine biology", "Oceans and cells")
        )
    assert icon["kind"] == "data"
    assert icon["data_uri"].startswith("data:image/png;base64,")


def main() -> None:
    check_icon_generation_mock()
    builtins = project_types.builtin_types()
    ids = {item.id for item in builtins}
    assert len(ids) == 12 and "other" not in ids and "literature" in ids
    literature = next(item for item in builtins if item.id == "literature")
    assert literature.icon["key"] == "literature"
    assert [item.id for item in builtins if (item.behavior or {}).get("lean")] == ["mathematical"]

    with TemporaryDirectory() as directory:
        root = Path(directory).resolve()
        first = root / "first"
        second = root / "second"
        first.mkdir()
        second.mkdir()
        with patch.dict(os.environ, {"SIGMA_PROJECTS_ROOT": str(first)}):
            created = project_types.save_type(
                {
                    "name": "Field Notes",
                    "scope": "Field research",
                    "icon": _placeholder(),
                    "description": "Saved locally",
                    "based_on": "literature",
                    "research_standards_references": [],
                    "publication_standards_references": [],
                }
            )
            assert created.user_defined and created.origin == "literature"
            assert "description" not in created.record()
            assert project_types._store_path().stat().st_mode & 0o777 == 0o600
            assert project_types.get_type(created.id) == created
            assert project_types.safe_project_snapshot(created.record())
            normalized_snapshot = project_types.normalize_project_snapshot(
                created.record(), created.id
            )
            assert normalized_snapshot is not None
            assert normalized_snapshot["name"] == "Field Notes"
            assert "description" not in normalized_snapshot
            for invalid in (
                {"name": "field notes", "scope": "duplicate", "icon": _placeholder()},
                {
                    "name": "Bad URL",
                    "scope": "Research",
                    "icon": _placeholder(),
                    "research_standards_references": ["javascript:alert(1)"],
                },
                *[
                    {
                        "name": f"Bad URL {index}",
                        "scope": "Research",
                        "icon": _placeholder(),
                        "research_standards_references": [url],
                    }
                    for index, url in enumerate(
                        (
                            "https://example.com:invalid/path",
                            "https://[broken/path",
                            "https://example.com:99999/",
                        ),
                        start=1,
                    )
                ],
            ):
                try:
                    project_types.save_type(invalid)
                except ProjectError:
                    pass
                else:
                    raise AssertionError("invalid custom project type was accepted")
        with patch.dict(os.environ, {"SIGMA_PROJECTS_ROOT": str(second)}):
            assert project_types.custom_types() == []

    with TemporaryDirectory() as directory:
        root = Path(directory).resolve()
        with patch.dict(os.environ, {"SIGMA_PROJECTS_ROOT": str(root)}), TestClient(app) as client:
            catalog = client.get("/api/project-types")
            assert catalog.status_code == 200
            revision = catalog.json()["revision"]
            placeholder = _placeholder()
            for bad_url in (
                "https://example.com:invalid/path",
                "https://[broken/path",
                "https://example.com:99999/",
            ):
                invalid = _record("bad-reference", "Bad reference", "Research", placeholder)
                invalid["research_standards_references"] = [bad_url]
                response = client.put(
                    "/api/project-types",
                    json={"project_types": [invalid], "expected_revision": revision},
                )
                assert response.status_code == 400, (bad_url, response.status_code, response.text)
                assert client.get("/api/project-types").json()["revision"] == revision
                assert project_types.custom_types() == []
            # References are normalized on Save: blanks and equivalent URLs
            # vanish, while a case-sensitive path remains distinct.
            clean = _record("ref-cleanup", "Reference Cleanup", "Testing URLs", placeholder)
            clean["research_standards_references"] = [
                " ",
                "HTTP://EXAMPLE.ORG:80/style.html",
                "http://example.org/style.html",
                "http://example.org/STYLE.html",
                "",
            ]
            clean["publication_standards_references"] = [
                "https://example.com:443/guide",
                "https://EXAMPLE.COM/guide",
                "   ",
            ]
            clean_response = client.put(
                "/api/project-types",
                json={"project_types": [clean], "expected_revision": revision},
            )
            assert clean_response.status_code == 200, clean_response.text
            cleaned = next(
                item for item in clean_response.json()["project_types"]
                if item["id"] == "ref-cleanup"
            )
            assert cleaned["research_standards_references"] == [
                "http://example.org/style.html",
                "http://example.org/STYLE.html",
            ]
            assert cleaned["publication_standards_references"] == [
                "https://example.com/guide",
            ]
            revision = clean_response.json()["revision"]
            clear_response = client.put(
                "/api/project-types",
                json={
                    "project_types": [],
                    "expected_revision": revision,
                    "confirmed_removals": {"ref-cleanup": 0},
                },
            )
            assert clear_response.status_code == 200, clear_response.text
            revision = clear_response.json()["revision"]

            parent = _record("draft-parent", "Draft parent", "Copied scope", placeholder)
            child = _record(
                "draft-child",
                "Derived child",
                "Independent copied scope",
                placeholder,
                "draft-parent",
            )
            saved = client.put(
                "/api/project-types",
                json={
                    "project_types": [parent, child],
                    "expected_revision": revision,
                },
            )
            assert saved.status_code == 200, saved.text
            assert len(saved.json()["project_types"]) == 2

            # Cross-draft based_on is a provenance hint only: the saved fields are independent.
            child_saved = next(
                item for item in saved.json()["project_types"] if item["id"] == "draft-child"
            )
            assert child_saved["based_on"] == "draft-parent"
            assert child_saved["scope"] == "Independent copied scope"
            parent["scope"] = "Parent later changed"
            edited = client.put(
                "/api/project-types",
                json={
                    "project_types": [parent, child_saved],
                    "expected_revision": saved.json()["revision"],
                },
            )
            assert edited.status_code == 200, edited.text
            assert (
                next(
                    item for item in edited.json()["project_types"] if item["id"] == "draft-child"
                )["scope"]
                == "Independent copied scope"
            )

            # Stale catalog revisions reject the whole Save, including staged removals.
            stale = client.get("/api/project-types").json()
            other = _record("concurrent", "Concurrent", "Concurrent edit", placeholder)
            changed = client.put(
                "/api/project-types",
                json={
                    "project_types": [parent, child_saved, other],
                    "expected_revision": stale["revision"],
                },
            )
            assert changed.status_code == 200, changed.text
            conflict = client.put(
                "/api/project-types",
                json={
                    "project_types": [child_saved],
                    "expected_revision": stale["revision"],
                    "confirmed_removals": {"draft-parent": 0},
                },
            )
            assert (
                conflict.status_code == 400 and project_types.get_type("draft-parent") is not None
            )

            # A change in project usage after confirmation also rejects the atomic Save.
            child_project = create_project(
                "Saved child", "Retain its copied context", "draft-child"
            )
            child_usage = client.get("/api/project-types/draft-child/usage").json()["project_count"]
            assert child_usage == 1
            stale_usage = client.put(
                "/api/project-types",
                json={
                    "project_types": [parent, other],
                    "expected_revision": changed.json()["revision"],
                    "confirmed_removals": {"draft-child": 0},
                },
            )
            assert (
                stale_usage.status_code == 400 and project_types.get_type("draft-child") is not None
            )

            # Deleting the original leaves the derived type intact, including after edit/reopen.
            remove_parent = client.put(
                "/api/project-types",
                json={
                    "project_types": [child_saved, other],
                    "expected_revision": changed.json()["revision"],
                    "confirmed_removals": {"draft-parent": 0},
                },
            )
            assert remove_parent.status_code == 200, remove_parent.text
            assert project_types.get_type("draft-parent") is None
            retained_child = project_types.get_type("draft-child")
            assert retained_child is not None and retained_child.based_on == "draft-parent"
            assert retained_child.scope == "Independent copied scope"
            reopen = client.get("/api/project-types").json()
            edit_after_origin_delete = client.put(
                "/api/project-types",
                json={
                    "project_types": [retained_child.record(), other],
                    "expected_revision": reopen["revision"],
                },
            )
            assert edit_after_origin_delete.status_code == 200, edit_after_origin_delete.text

            # Delete with confirmed usage, preserve project identity/snapshot, then explicitly continue.
            usage = client.get("/api/project-types/draft-child/usage").json()["project_count"]
            assert usage == 1
            latest = client.get("/api/project-types").json()
            deleted = client.put(
                "/api/project-types",
                json={
                    "project_types": [other],
                    "expected_revision": latest["revision"],
                    "confirmed_removals": {"draft-child": usage},
                },
            )
            assert deleted.status_code == 200, deleted.text
            persisted = inspect_project(child_project.path).project
            assert persisted.investigation_type == "draft-child"
            assert persisted.project_type_snapshot is not None
            assert persisted.project_type_snapshot["scope"] == "Independent copied scope"
            strategy = create_strategy(
                child_project.path, "Read", "Inspect saved sources."
            ).project.strategies[0]
            try:
                research_sessions.mock_session(
                    child_project.path, strategy.id, str(uuid4()), "completed"
                )
            except ProjectError as exc:
                assert "unavailable" in str(exc)
            else:
                raise AssertionError("deleted project type silently started a session")
            session = research_sessions.mock_session(
                child_project.path, strategy.id, str(uuid4()), "completed", True
            )
            assert session["use_saved_project_type_settings"] is True
            assert session["project_type_snapshot"]["name"] == "Derived child"
            assert research_sessions._saved_project_type_context(session) == {
                "name": "Derived child",
                "scope": "Independent copied scope",
                "description": "",
                "behavior": {},
            }

            # Old default projects without a snapshot remain readable but cannot start silently.
            legacy = initialize_project(
                root / "legacy-default.sigma", "Legacy default", "Old saved work"
            )
            legacy_strategy = create_strategy(
                legacy.path, "Legacy", "Keep old work safe."
            ).project.strategies[0]
            assert inspect_project(legacy.path).project.project_type_snapshot is None
            try:
                research_sessions.mock_session(
                    legacy.path, legacy_strategy.id, str(uuid4()), "completed", True
                )
            except ProjectError as exc:
                assert "safe saved settings" in str(exc)
            else:
                raise AssertionError(
                    "legacy default without snapshot bypassed the missing-type safeguard"
                )

            # The image service is intentionally absent from this PR; a fresh account needs no setup.
            assert (
                client.post("/api/project-types/icon", json={"name": "x", "scope": "y"}).status_code
                == 405
            )
    print(
        "PASS catalog, placeholder creation without AI, owner isolation, draft bases, transactional removal, snapshots, legacy safeguard and explicit session continuation"
    )


def _placeholder() -> dict[str, object]:
    return project_types.placeholder_icon()


def _record(
    identifier: str, name: str, scope: str, icon: dict[str, object], based_on: str | None = None
) -> dict[str, object]:
    return {
        "id": identifier,
        "name": name,
        "scope": scope,
        "description": "",
        "based_on": based_on,
        "origin": based_on,
        "user_defined": True,
        "icon": icon,
        "research_standards_references": [],
        "publication_standards_references": [],
        "behavior": {},
    }


if __name__ == "__main__":
    main()
