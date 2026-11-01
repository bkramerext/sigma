"""Unified project type catalog, isolation, validation and image service boundaries."""

import asyncio
import base64
import io
import os
from pathlib import Path
from tempfile import TemporaryDirectory
from unittest.mock import AsyncMock, patch
from uuid import uuid4

import test_environment as _test_environment  # noqa: F401
from fastapi.testclient import TestClient
from PIL import Image

from sigma import project_type_icons, project_types, research_sessions
from sigma.api import app
from sigma.projects import ProjectError, create_project, create_strategy, inspect_project


def main() -> None:
    builtins = project_types.builtin_types()
    ids = {item.id for item in builtins}
    assert len(ids) == 12 and "other" not in ids and "literature" in ids
    assert next(item for item in builtins if item.id == "literature").icon["key"] == "literature"
    assert [item.id for item in builtins if (item.behavior or {}).get("lean")] == ["mathematical"]

    png = io.BytesIO()
    Image.new("RGBA", (128, 128), (214, 163, 111, 255)).save(png, format="PNG")
    icon = {
        "kind": "data",
        "data_uri": "data:image/png;base64," + base64.b64encode(png.getvalue()).decode(),
    }
    with TemporaryDirectory() as directory:
        root = Path(directory)
        first = root / "first"
        second = root / "second"
        first.mkdir()
        second.mkdir()
        with patch.dict(os.environ, {"SIGMA_PROJECTS_ROOT": str(first)}):
            created = project_types.save_type(
                {
                    "name": "Field Notes",
                    "scope": "Field research",
                    "icon": icon,
                    "description": "Saved locally",
                    "based_on": "literature",
                    "research_standards_references": [],
                    "publication_standards_references": [],
                }
            )
            assert created.user_defined and created.origin == "literature"
            stored = project_types._store_path()
            assert stored.stat().st_mode & 0o777 == 0o600
            assert project_types.get_type(created.id) == created
            try:
                project_types.save_type({"name": "field notes", "scope": "duplicate", "icon": icon})
            except ProjectError:
                pass
            else:
                raise AssertionError("case-insensitive duplicate name accepted")
            try:
                project_types.save_type(
                    {
                        "name": "Bad URL",
                        "scope": "Research",
                        "icon": icon,
                        "research_standards_references": ["javascript:alert(1)"],
                    }
                )
            except ProjectError:
                pass
            else:
                raise AssertionError("unsafe reference URL accepted")
            snapshot = created.record()
            assert project_types.safe_project_snapshot(snapshot)
            normalized = project_types.normalize_project_snapshot(snapshot, created.id)
            assert normalized is not None and normalized["name"] == "Field Notes"
            project_types.remove_type(created.id)
            assert project_types.get_type(created.id) is None
        with patch.dict(os.environ, {"SIGMA_PROJECTS_ROOT": str(second)}):
            assert project_types.custom_types() == []

    with TemporaryDirectory() as directory:
        root = Path(directory).resolve()
        with patch.dict(os.environ, {"SIGMA_PROJECTS_ROOT": str(root)}), TestClient(app) as client:
            catalog = client.get("/api/project-types")
            assert catalog.status_code == 200
            custom_record = {
                "id": "browser-test-literature-derived",
                "name": "Independent Literature",
                "scope": "Independent literary study",
                "description": "Copied from a built-in type once.",
                "based_on": "literature",
                "origin": "literature",
                "user_defined": True,
                "icon": next(
                    item for item in catalog.json()["project_types"] if item["id"] == "literature"
                )["icon"],
                "research_standards_references": [],
                "publication_standards_references": [],
                "behavior": {},
            }
            saved = client.put(
                "/api/project-types",
                json={
                    "project_types": [custom_record],
                    "expected_revision": catalog.json()["revision"],
                },
            )
            assert saved.status_code == 200, saved.text
            project = create_project(
                "Deleted type fixture", "Retain the saved project context", custom_record["id"]
            )
            strategy = create_strategy(
                project.path, "Read", "Inspect the saved sources."
            ).project.strategies[0]
            usage = client.get(f"/api/project-types/{custom_record['id']}/usage")
            assert usage.json()["project_count"] == 1
            deleted = client.request(
                "DELETE",
                f"/api/project-types/{custom_record['id']}",
                json={
                    "confirm": True,
                    "expected_project_count": 1,
                    "expected_revision": saved.json()["revision"],
                },
            )
            assert deleted.status_code == 200, deleted.text
            persisted = inspect_project(project.path).project
            assert persisted.investigation_type == custom_record["id"]
            assert persisted.project_type_snapshot is not None
            assert persisted.project_type_snapshot["scope"] == custom_record["scope"]
            try:
                research_sessions.mock_session(project.path, strategy.id, str(uuid4()), "completed")
            except ProjectError as exc:
                assert "unavailable" in str(exc)
            else:
                raise AssertionError("deleted custom type silently started a session")
            session = research_sessions.mock_session(
                project.path, strategy.id, str(uuid4()), "completed", True
            )
            assert session["project_type_snapshot"] is not None
            assert session["project_type_snapshot"]["name"] == custom_record["name"]
            assert session["use_saved_project_type_settings"] is True
            assert research_sessions._saved_project_type_context(session) == {
                "name": custom_record["name"],
                "scope": custom_record["scope"],
                "description": custom_record["description"],
                "behavior": {},
            }

    async def generation_check() -> None:
        with patch.dict(os.environ, {"SIGMA_PROJECT_TYPE_IMAGE_GENERATION_ENABLED": ""}):
            try:
                await project_type_icons.generate("x", "y", "z")
            except ProjectError as exc:
                assert "disabled" in str(exc)
            else:
                raise AssertionError("image endpoint must be disabled by default")
        with (
            patch.dict(os.environ, {"SIGMA_PROJECT_TYPE_IMAGE_GENERATION_ENABLED": "1"}),
            patch.object(
                project_type_icons.openai_connection,
                "auth_context",
                new=AsyncMock(
                    return_value={"status": "connected", "mode": "api_key", "token": "test-only"}
                ),
            ),
            patch.object(project_type_icons.httpx.AsyncClient, "post", new=AsyncMock()) as post,
        ):
            response = type(
                "Response", (), {"content": b"{}", "is_success": False, "status_code": 503}
            )()
            post.return_value = response
            try:
                await project_type_icons.generate("x", "y", "z")
            except ProjectError as exc:
                assert "unchanged" in str(exc)
            else:
                raise AssertionError("provider error must retain prior icon")
            post.assert_awaited_once()
            assert post.await_args is not None
            payload = post.await_args.kwargs["json"]
            assert payload["images"][0]["image_url"].startswith("data:image/png;base64,")
            assert payload["model"] == "gpt-image-2.5-sunburst"

    asyncio.run(generation_check())
    print(
        "PASS canonical types, API persistence/isolation, delete snapshot/start gate, validation and mocked image provider boundary"
    )


if __name__ == "__main__":
    main()
