"""Real Chromium acceptance for collaboration layout, staged edits and failure feedback.

The deterministic provider fixture isolates UI behavior and simulates owner
data. See collaboration_local_accounts.py for real two-profile ACL and revision
checks against the local authenticated backend.
"""

from __future__ import annotations

import os
from urllib.parse import quote
from uuid import uuid4

from playwright.sync_api import expect, sync_playwright

BASE = os.environ.get("SIGMA_BROWSER_BASE_URL", "http://127.0.0.1:5173").rstrip("/")
FIXTURE = os.environ.get("SIGMA_BROWSER_FIXTURE_URL", "http://127.0.0.1:8026").rstrip("/")


def main() -> None:
    with sync_playwright() as playwright:
        browser = playwright.chromium.launch(
            executable_path=os.environ.get(
                "SIGMA_BROWSER_EXECUTABLE",
                "/Applications/Google Chrome.app/Contents/MacOS/Google Chrome",
            ),
            headless=True,
        )
        page = browser.new_page(viewport={"width": 1440, "height": 930})
        errors: list[str] = []
        page.on("pageerror", lambda error: errors.append(str(error)))

        def proxy(route):
            route.fulfill(
                response=route.fetch(
                    url=route.request.url.replace(BASE, FIXTURE),
                    headers={**route.request.headers, "origin": BASE},
                )
            )

        page.route("**/api/**", proxy)
        # Presence is a long-lived stream; it is not relevant to this UI fixture.
        page.route(
            "**/api/projects/research-presence?*",
            lambda route: route.fulfill(status=204, body=""),
        )
        page.goto(BASE)
        created = page.evaluate(
            """async title => {
              const response = await fetch('/api/projects/create', {
                method:'POST', headers:{'Content-Type':'application/json'},
                body:JSON.stringify({
                  title, problem:'Verify collaboration Project Settings without real mail.',
                  investigation_type:'mathematical'
                })
              });
              return {status:response.status, body:await response.json()};
            }""",
            "Collaboration browser " + uuid4().hex[:8],
        )
        assert created["status"] == 201, created
        path = created["body"]["path"]
        page.goto(BASE + "/project?path=" + quote(path, safe=""))
        settings = page.get_by_role("button", name="Project settings", exact=True)
        expect(settings).to_be_visible()
        settings.click()
        dialog = page.get_by_role("dialog", name="Project Settings")
        expect(dialog).to_be_visible()

        # Unauthenticated fixture: explain that Google identity is required
        # locally or hosted, not that collaboration is hosted-only.
        expect(
            dialog.get_by_text("Collaboration requires individual Google sign-ins", exact=False)
        ).to_be_visible()
        expect(dialog.get_by_role("region", name="Collaborators")).to_have_count(0)
        expect(dialog.get_by_role("combobox", name="Research category")).to_be_visible()
        expect(dialog.get_by_label("Difficulty")).to_be_visible()
        page.keyboard.press("Escape")
        expect(dialog).not_to_be_visible()

        shared = {
            "owner": "owner@example.org",
            "collaborators": ["alice@example.net"],
            "removable_collaborators": ["alice@example.net"],
            "revision": 7,
            "model": "gpt-6.1-sol",
            "thinking": "high",
            "lease": None,
            "shared": True,
            "failed_notifications": 1,
        }
        page.route(
            "**/api/projects/collaboration?*",
            lambda route: route.fulfill(status=200, json=shared),
        )
        page.route(
            "**/api/ai/models",
            lambda route: route.fulfill(
                status=200,
                json={
                    "models": [
                        {
                            "id": "gpt-6.1-sol",
                            "label": "Sol",
                            "efforts": ["low", "medium", "high"],
                        }
                    ]
                },
            ),
        )
        retries: list[object] = []
        page.route(
            "**/api/projects/collaboration/notifications/retry",
            lambda route: (
                retries.append(route.request.post_data_json),
                route.fulfill(status=200, json={"requeued": 1}),
            ),
        )
        updates: list[dict] = []

        def update(route):
            payload = route.request.post_data_json
            updates.append(payload)
            if len(updates) > 1:
                route.fulfill(
                    status=409,
                    json={
                        "error": "Project was saved by other@example.net. "
                        "Reopen it and redo your changes."
                    },
                )
                return
            shared["revision"] += 1
            shared["collaborators"] = payload["collaborators"]
            shared["removable_collaborators"] = payload["collaborators"]
            created["body"]["project"].update(
                {
                    "ai_model": payload["ai_model"],
                    "reasoning_effort": payload["reasoning_effort"],
                    "difficulty": payload["difficulty"],
                    "investigation_type": payload["investigation_type"],
                }
            )
            route.fulfill(status=200, json=created["body"])

        page.route("**/api/projects/update", update)
        settings.click()
        dialog = page.get_by_role("dialog", name="Project Settings")
        expect(dialog.get_by_role("region", name="Collaborators")).to_be_visible()
        expect(dialog.get_by_text("owner@example.org")).to_be_visible()
        expect(dialog.get_by_text("Owner", exact=True)).to_be_visible()
        assert dialog.get_by_role("button", name="Remove owner@example.org").count() == 0

        # Classification, aligned model/thinking pair, then collaborators.
        classification = dialog.locator(".settings-classification-row")
        category = dialog.get_by_role("combobox", name="Research category")
        difficulty = dialog.get_by_label("Difficulty")
        collaborators = dialog.get_by_role("region", name="Collaborators")
        model_row = dialog.locator(".settings-model-row")
        assert model_row.locator("select").count() == 0, "Model/Thinking must use SIGMA dropdowns"
        model_picker = model_row.get_by_role("combobox", name="Model")
        thinking_picker = model_row.get_by_role("combobox", name="Thinking")
        expect(model_picker).to_be_visible()
        expect(thinking_picker).to_be_visible()
        model_picker.click()
        expect(dialog.get_by_role("listbox", name="Model")).to_be_visible()
        page.keyboard.press("Escape")
        thinking_picker.click()
        expect(dialog.get_by_role("listbox", name="Thinking")).to_be_visible()
        page.keyboard.press("Escape")
        for width in (1440, 390):
            page.set_viewport_size({"width": width, "height": 930 if width == 1440 else 844})
            cat_box = category.bounding_box()
            diff_box = difficulty.bounding_box()
            collab_box = collaborators.bounding_box()
            assert (
                collaborators.evaluate("element => getComputedStyle(element).borderTopWidth")
                == "1px"
            )
            model_box = model_row.bounding_box()
            assert cat_box and diff_box and collab_box and model_box
            assert abs(cat_box["y"] - diff_box["y"]) < 4, (width, cat_box, diff_box)
            assert cat_box["x"] + cat_box["width"] <= diff_box["x"] + 1
            assert model_box["y"] >= (
                classification.bounding_box()["y"] + category.bounding_box()["height"]
            )
            assert collab_box["y"] >= model_box["y"] + model_box["height"] - 1
            assert dialog.evaluate("element => element.scrollWidth <= element.clientWidth")
            assert page.evaluate("document.documentElement.scrollWidth <= innerWidth")
            page.screenshot(path=f"/tmp/sigma-collaboration-settings-{width}.png")
        page.set_viewport_size({"width": 1440, "height": 930})

        # Retry is explicit; it does not touch staged project membership.
        expect(dialog.get_by_text("1 collaboration email could not be delivered.")).to_be_visible()
        dialog.get_by_role("button", name="Retry emails").click()
        expect(dialog.get_by_role("button", name="Retry emails")).to_have_count(0)
        assert len(retries) == 1

        dialog.get_by_role("button", name="Add collaborator").click()
        editor = dialog.get_by_label("New collaborator email")
        editor.fill("brian@gmail.com")
        editor.press("Tab")
        assert editor.count() == 0, "Blur should finish a valid collaborator entry"
        assert dialog.get_by_role("button", name="Add", exact=True).count() == 0
        assert dialog.get_by_role("button", name="Cancel", exact=True).count() == 0
        expect(dialog.get_by_text("brian@gmail.com")).to_be_visible()
        dialog.get_by_role("button", name="Remove alice@example.net").click()
        expect(dialog.get_by_text("alice@example.net")).to_have_count(0)
        expect(dialog.get_by_role("button", name="Save", exact=True)).to_have_count(0)
        for _ in range(50):
            if len(updates) >= 1:
                break
            page.wait_for_timeout(100)
        assert len(updates) == 1, updates
        assert updates[0]["collaborators"] == ["brian@gmail.com"], updates
        assert updates[0]["expected_revision"] == 7, updates
        expect(dialog).to_be_visible()
        dialog.get_by_role("button", name="Close Project Settings").click()
        expect(dialog).not_to_be_visible()

        settings.click()
        dialog = page.get_by_role("dialog", name="Project Settings")
        expect(dialog.get_by_role("button", name="Remove brian@gmail.com")).to_be_visible()
        dialog.get_by_role("button", name="Remove brian@gmail.com").click()
        expect(dialog.locator(".error")).to_contain_text("saved by other@example.net")
        expect(dialog.get_by_role("button", name="Save", exact=True)).to_have_count(0)
        page.keyboard.press("Escape")

        assert not errors, errors
        browser.close()

    print(
        "PASS collaboration controls, local sign-in guidance, 1440/390px layout, "
        "automatic Save, notification retry and stale-editor refusal"
    )


if __name__ == "__main__":
    main()
