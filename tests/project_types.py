"""Unified project type catalog, transactional persistence and session safeguards."""

import os
from pathlib import Path
from tempfile import TemporaryDirectory
from unittest.mock import patch
from uuid import uuid4

import test_environment as _test_environment  # noqa: F401
from fastapi.testclient import TestClient

from sigma import project_types, research_sessions
from sigma.api import app
from sigma.projects import (
    ProjectError,
    create_project,
    create_strategy,
    initialize_project,
    inspect_project,
)


def main() -> None:
    builtins = project_types.builtin_types()
    ids = {item.id for item in builtins}
    assert len(ids) == 12 and "other" not in ids and "literature" in ids
    literature = next(item for item in builtins if item.id == "literature")
    assert literature.icon["key"] == "literature"
    assert [item.id for item in builtins if (item.behavior or {}).get("lean")] == ["mathematical"]

    # Curated catalog entries stay immutable; shared guides are disabled by
    # default per user while subject-specific references remain enabled.
    common = project_types.common_references()
    assert len(common["research_standards_references"]) == 2
    assert len(common["publication_standards_references"]) == 2
    # Four shared references and one research/publication pair for each
    # of twelve disciplines: 28 distinct, titled, secure-source references.
    all_standards = [
        *(ref for field in project_types.REFERENCE_FIELDS for ref in common[field]),
        *(
            ref
            for item in builtins
            for field in project_types.REFERENCE_FIELDS
            for ref in getattr(item, field)
        ),
    ]
    assert len(all_standards) == 4 + 2 * len(builtins)
    assert len({ref["url"] for ref in all_standards}) == len(all_standards)
    assert all(ref["name"].strip() and ref["url"].startswith("https://") for ref in all_standards)
    builtins_by_id = {item.id: item for item in builtins}
    # Every discipline contributes a curated pair beyond the shared guidance.
    assert {
        ref["url"]
        for item in builtins
        for field in project_types.REFERENCE_FIELDS
        for ref in getattr(item, field)
    }.isdisjoint({ref["url"] for field in project_types.REFERENCE_FIELDS for ref in common[field]})
    builtins_by_id = {item.id: item for item in builtins}
    # Regression checks for the compact methodology guides: no textbooks or
    # oversized handbooks, and no dead Army War College/Buffalo URLs.
    assert builtins_by_id["chemistry"].research_standards_references[0]["url"] == (
        "https://www.chemistry.ucla.edu/undergraduate/undergraduate-research/"
        "research-proposal-guidelines/"
    )
    assert builtins_by_id["mathematical"].research_standards_references[0]["url"] == (
        "https://dummit.cos.northeastern.edu/teaching_fa19_1365/1365_problemsolving"
    )
    assert (
        builtins_by_id["military"]
        .publication_standards_references[0]["url"]
        .endswith("/VDF%20Decision%20Paper.pdf")
    )
    # Plain, substantive HTML is acceptable along with compact PDFs and Markdown;
    # do not require PDF-only links when the source itself has a clean text body.
    for identifier, item in builtins_by_id.items():
        assert len(item.research_standards_references) == 1, identifier
        assert len(item.publication_standards_references) == 1, identifier
        effective = project_types.get_type(identifier)
        assert effective is not None
        for field in project_types.REFERENCE_FIELDS:
            own = getattr(item, field)
            assert all(ref["name"].strip() and ref["url"].startswith("https://") for ref in own)
            inherited = getattr(effective, field)
            assert len(inherited) == 1, (identifier, field)
            assert {ref["url"] for ref in own} == {ref["url"] for ref in inherited}

    with TemporaryDirectory() as directory:
        root = Path(directory).resolve()
        with patch.dict(os.environ, {"SIGMA_PROJECTS_ROOT": str(root)}), TestClient(app) as client:
            before = client.get("/api/project-types").json()
            assert before["common_references"] == common
            assert "builtin_references" not in before
            default_disabled = before["reference_preferences"]
            assert default_disabled == {
                "common": {field: [ref["url"] for ref in refs] for field, refs in common.items()}
            }
            assert project_types.common_research_references() == ()
            # Invalid preferences may not change curated catalog definitions.
            rejected = client.put(
                "/api/project-types",
                json={
                    "project_types": [],
                    "expected_revision": before["revision"],
                    "reference_preferences": {
                        "common": {
                            "hidden_research": [common["research_standards_references"][0]["url"]]
                        }
                    },
                },
            )
            assert rejected.status_code == 400, rejected.text
            assert client.get("/api/project-types").json()["revision"] == before["revision"]
            assert client.get("/api/project-types").json()["common_references"] == common

            # One shared research reference enabled; the other shared references
            # remain off. Turn off mathematical research reference independently.
            math_ref = builtins_by_id["mathematical"].research_standards_references[0]["url"]
            custom_preferences = {
                "common": {
                    "research_standards_references": [
                        common["research_standards_references"][1]["url"]
                    ],
                    "publication_standards_references": [
                        ref["url"] for ref in common["publication_standards_references"]
                    ],
                },
                "mathematical": {"research_standards_references": [math_ref]},
            }
            updated = client.put(
                "/api/project-types",
                json={
                    "project_types": [],
                    "expected_revision": before["revision"],
                    "reference_preferences": custom_preferences,
                },
            )
            assert updated.status_code == 200, updated.text
            assert (
                client.get("/api/project-types").json()["reference_preferences"]
                == custom_preferences
            )
            enabled_math = project_types.get_type("mathematical")
            assert enabled_math is not None
            assert {ref["url"] for ref in enabled_math.research_standards_references} == {
                common["research_standards_references"][0]["url"]
            }
            # Other disciplines keep their own guides and no publication common references.
            enabled_physics = project_types.get_type("physics")
            assert enabled_physics is not None
            assert len(enabled_physics.research_standards_references) == 2
            assert len(enabled_physics.publication_standards_references) == 1
            from sigma import research_method_sources

            methods, _ = research_method_sources._effective_sources("mathematical")
            assert {ref["url"] for ref in methods} == {
                common["research_standards_references"][0]["url"]
            }
            # Saving unrelated custom types through an older API client must
            # preserve saved reference choices rather than silently resetting them.
            revision = updated.json()["revision"]
            older = client.put(
                "/api/project-types",
                json={"project_types": [], "expected_revision": revision},
            )
            assert older.status_code == 200, older.text
            assert project_types.reference_preferences() == custom_preferences

            # Restore defaults so remaining catalog tests run in their
            # original subject-only configuration.
            restored = client.put(
                "/api/project-types",
                json={
                    "project_types": [],
                    "expected_revision": older.json()["revision"],
                    "reference_preferences": default_disabled,
                },
            )
            assert restored.status_code == 200, restored.text
            restored_type = project_types.get_type("mathematical")
            assert restored_type is not None
            assert len(restored_type.research_standards_references) == 1

    from sigma.reference_titles import _TitleParser, resolve_title

    parsed_title = _TitleParser()
    parsed_title.feed(
        '<html><head><title>Fallback</title><meta property="og:title" '
        'content="Preferred &amp; Tested"></head></html>'
    )
    assert parsed_title.og_title == "Preferred & Tested"
    assert resolve_title("http://127.0.0.1/secret") is None
    assert resolve_title("file:///etc/passwd") is None

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
            assert (
                next(item for item in project_types.custom_types() if item.id == created.id)
                == created
            )
            resolved = project_types.get_type(created.id)
            assert resolved is not None and resolved.icon["key"] == "literature"
            assert project_types.safe_project_snapshot(created.record())
            normalized_snapshot = project_types.normalize_project_snapshot(
                created.record(), created.id
            )
            assert normalized_snapshot is not None
            assert normalized_snapshot["name"] == "Field Notes"
            assert "description" not in normalized_snapshot
            # Preferences are isolated to the currently selected user workspace.
            assert project_types.common_research_references() == ()
            project_types.replace_custom_types(
                [created.record()],
                expected_revision=project_types.catalog_revision(),
                reference_preferences_update={},
            )
            assert len(project_types.common_research_references()) == 2
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
            assert project_types.common_research_references() == ()
            assert (
                project_types.reference_preferences()
                == project_types._default_reference_preferences()
            )

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
                item
                for item in clean_response.json()["project_types"]
                if item["id"] == "ref-cleanup"
            )
            assert [item["url"] for item in cleaned["research_standards_references"]] == [
                "http://example.org/style.html",
                "http://example.org/STYLE.html",
            ]
            assert cleaned["publication_standards_references"] == [
                {"name": "https://example.com/guide", "url": "https://example.com/guide"},
            ]
            # Named records survive normalization; old URL strings stay readable.
            assert all(
                reference["name"] == reference["url"]
                for reference in cleaned["research_standards_references"]
            )
            named = _record("named-reference", "Named Reference", "Named tests", placeholder)
            named["research_standards_references"] = [
                {"name": "A Human-Readable Title", "url": "https://example.org/a-paper"}
            ]
            named_response = client.put(
                "/api/project-types",
                json={
                    "project_types": [clean, named],
                    "expected_revision": clean_response.json()["revision"],
                },
            )
            assert named_response.status_code == 200, named_response.text
            saved_named = next(
                item
                for item in named_response.json()["project_types"]
                if item["id"] == "named-reference"
            )
            assert saved_named["research_standards_references"] == [
                {"name": "A Human-Readable Title", "url": "https://example.org/a-paper"}
            ]
            revision = named_response.json()["revision"]
            clear_response = client.put(
                "/api/project-types",
                json={
                    "project_types": [],
                    "expected_revision": revision,
                    "confirmed_removals": {"ref-cleanup": 0, "named-reference": 0},
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
