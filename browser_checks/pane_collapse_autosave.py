"""Browser regression: Project/Strategies collapse commits valid edits and preserves invalid drafts.

Runs under the Model availability fixture (:8001 API, :5173 Vite), without AI calls.
"""

import os
from urllib.parse import urlencode
from uuid import uuid4

from playwright.sync_api import expect, sync_playwright

UI = "http://127.0.0.1:5173"
API = "http://127.0.0.1:8001"


def main():
    with sync_playwright() as playwright:
        browser = playwright.chromium.launch(
            executable_path=os.environ.get(
                "SIGMA_BROWSER_EXECUTABLE", playwright.chromium.executable_path
            ),
            headless=True,
        )
        page = browser.new_page(viewport={"width": 1440, "height": 930})
        page.set_default_timeout(15000)
        errors = []
        page.on("pageerror", lambda error: errors.append(str(error)))
        description_writes = []
        strategy_writes = []
        fail = {"description": False, "strategy": False}

        def forward(route):
            route.fulfill(
                response=route.fetch(
                    url=route.request.url.replace(UI, API),
                    headers={**route.request.headers, "origin": UI},
                )
            )

        def intercepted_save(route, key, writes):
            if route.request.method == "POST":
                writes.append(route.request.post_data_json)
                if fail[key]:
                    fail[key] = False
                    route.fulfill(
                        status=409,
                        json={"error": "A collaborator changed this draft. Retry the save."},
                    )
                    return
            forward(route)

        page.route("**/api/**", forward)
        page.route(
            "**/api/cloud-auth/status",
            lambda route: route.fulfill(
                json={
                    "target": "local",
                    "enabled": True,
                    "ready": True,
                    "authenticated": True,
                    "user": {"email": "pane-autosave@example.org", "role": "admin"},
                    "admin_contact_email": None,
                }
            ),
        )
        page.route(
            "**/api/projects/description",
            lambda route: intercepted_save(route, "description", description_writes),
        )
        page.route(
            "**/api/projects/strategies",
            lambda route: intercepted_save(route, "strategy", strategy_writes),
        )

        created = page.request.post(
            API + "/api/projects/create",
            data={
                "title": "Pane collapse " + uuid4().hex[:8],
                "problem": "Preserve all authored edits through collapse.",
            },
        )
        assert created.status == 201, created.text()
        path = created.json()["path"]
        page.goto(UI + "/project?" + urlencode({"path": path}))

        project = page.locator("#project-pane-heading .workspace-section-disclosure")
        strategies = page.locator("#pool-heading .workspace-section-disclosure")
        edit_project = page.get_by_role("button", name="Edit project fields")
        expect(project).to_have_attribute("aria-expanded", "true")

        # Valid Project edit uses exactly the ordinary save endpoint.
        edit_project.click()
        problem = page.get_by_role("textbox", name="Research Problem")
        problem.fill("A saved problem after collapsing the Project pane.")
        project.click()
        expect(project).to_have_attribute("aria-expanded", "false")
        expect(edit_project).to_be_enabled()
        assert len(description_writes) == 1, description_writes
        project.click()
        expect(page.locator("#project-pane-content")).to_contain_text(
            "A saved problem after collapsing the Project pane."
        )

        # Invalid Project edits must not be hidden or dropped.
        edit_project.click()
        problem = page.get_by_role("textbox", name="Research Problem")
        problem.fill("")
        project.click()
        expect(project).to_have_attribute("aria-expanded", "true")
        expect(page.locator("#sigma-project-description-form [role=alert]")).to_contain_text(
            "Project title and Research Problem are required."
        )
        assert len(description_writes) == 1
        problem.fill("An updated problem after validation.")
        fail["description"] = True
        project.click()
        expect(project).to_have_attribute("aria-expanded", "true")
        expect(page.locator("#sigma-project-description-form [role=alert]")).to_contain_text(
            "A collaborator changed this draft."
        )
        assert len(description_writes) == 2
        project.click()
        expect(project).to_have_attribute("aria-expanded", "false")
        assert len(description_writes) == 3
        project.click()
        expect(page.locator("#project-pane-content")).to_contain_text(
            "An updated problem after validation."
        )

        # Untouched New strategy exits the editing mode without creating anything.
        new = page.get_by_role("button", name="New strategy", exact=True)
        new.click()
        expect(page.locator(".strategy-form")).to_be_visible()
        strategies.click()
        expect(strategies).to_have_attribute("aria-expanded", "false")
        expect(page.locator(".strategy-form")).to_have_count(0)
        expect(new).to_be_enabled()
        assert not strategy_writes

        # An incomplete draft must remain expanded with its values intact.
        strategies.click()
        new.click()
        page.get_by_role("textbox", name="Title", exact=True).fill("Auto-collapse strategy")
        strategies.click()
        expect(strategies).to_have_attribute("aria-expanded", "true")
        expect(page.locator(".strategy-form [role=alert]")).to_contain_text(
            "Enter both a strategy title and a hypothesis / approach"
        )
        assert not strategy_writes

        # Complete the draft; collapse saves and releases all editing locks.
        page.get_by_role("textbox", name="Hypothesis / approach").fill(
            "Test a deterministic finite construction before drawing conclusions."
        )
        strategies.click()
        expect(strategies).to_have_attribute("aria-expanded", "false")
        expect(new).to_be_enabled()
        assert len(strategy_writes) == 1
        strategies.click()
        expect(page.locator(".strategy-row")).to_have_count(1)
        expect(page.locator(".strategy-row")).to_contain_text("Auto-collapse strategy")

        # A rejected create leaves the editor open, ready to retry collapse.
        new.click()
        page.get_by_role("textbox", name="Title", exact=True).fill("Retry strategy")
        page.get_by_role("textbox", name="Hypothesis / approach").fill(
            "Retain the approach through a transient failed save."
        )
        fail["strategy"] = True
        strategies.click()
        expect(strategies).to_have_attribute("aria-expanded", "true")
        expect(page.locator(".strategy-form [role=alert]")).to_contain_text(
            "A collaborator changed this draft."
        )
        assert len(strategy_writes) == 2
        strategies.click()
        expect(strategies).to_have_attribute("aria-expanded", "false")
        assert len(strategy_writes) == 3
        strategies.click()
        expect(page.locator(".strategy-row")).to_have_count(2)

        # Existing strategy's combined title/approach editor also commits on collapse.
        edit_strategy = page.get_by_role(
            "button", name="Edit strategy title and approach: Auto-collapse strategy"
        )
        edit_strategy.click()
        page.get_by_role("textbox", name="Strategy title").fill("Renamed on collapse")
        approach = page.locator('textarea[id^="text-editor-strategy-"]')
        expect(approach).to_be_visible()
        approach.fill("A revised approach saved with the strategy title.")
        strategies.click()
        expect(strategies).to_have_attribute("aria-expanded", "false")
        expect(new).to_be_enabled()
        strategies.click()
        expect(page.locator(".strategy-row")).to_contain_text("Renamed on collapse")
        expect(page.locator(".strategy-approach")).to_contain_text(
            "A revised approach saved with the strategy title."
        )

        assert not errors, errors
        browser.close()
    print("PASS Project and Strategies autosave/cancel/validation/failure collapse flows")


if __name__ == "__main__":
    main()
