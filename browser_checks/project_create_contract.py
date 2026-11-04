"""Real Chrome regression: project creation omits the edit-only outcome preference."""

import json
import os
from urllib.parse import urlsplit

from playwright.sync_api import expect, sync_playwright

UI_URL = os.environ.get("SIGMA_BROWSER_BASE_URL", "http://127.0.0.1:5193")
create_payloads = []
save_as_payloads = []
saved_entries = []


def api_fixture(route):
    path = urlsplit(route.request.url).path
    if path == "/api/cloud-auth/status":
        body = {
            "enabled": False,
            "ready": True,
            "authenticated": False,
            "user": None,
            "target": "local",
            "local_setup_missing": [],
        }
        route.fulfill(status=200, content_type="application/json", body=json.dumps(body))
    elif path == "/api/ai/connection":
        body = {
            "mode": "api_key",
            "status": "connected",
            "label": "OpenAI API · key billing",
            "accounts": [],
            "active_account": None,
        }
        route.fulfill(status=200, content_type="application/json", body=json.dumps(body))
    elif path == "/api/ai/models":
        body = {
            "models": [
                {
                    "id": "gpt-6.1-sol",
                    "label": "GPT-6.1-Sol",
                    "description": "Fixture model",
                    "efforts": ["high"],
                    "relative_cost": "$$",
                    "availability": "available",
                }
            ],
            "default_model": "gpt-6.1-sol",
            "default_effort": "high",
            "message": "Browser fixture; no provider call is made.",
        }
        route.fulfill(status=200, content_type="application/json", body=json.dumps(body))
    elif path in {"/api/projects/samples", "/api/projects/recent"}:
        entries = saved_entries if path.endswith("/recent") else []
        route.fulfill(
            status=200, content_type="application/json", body=json.dumps({"projects": entries})
        )
    elif path == "/api/projects/destination":
        body = {
            "root": "/tmp/sigma-project-create-contract",
            "path": "/tmp/sigma-project-create-contract/create-contract.sigma",
            "exists": False,
        }
        route.fulfill(status=200, content_type="application/json", body=json.dumps(body))
    elif path == "/api/projects/save-as":
        payload = json.loads(route.request.post_data or "{}")
        save_as_payloads.append(payload)
        route.fulfill(
            status=201,
            content_type="application/json",
            body=json.dumps(
                {
                    "path": "/tmp/sigma-project-create-contract/copied-project.json",
                    "project": {
                        "id": "8dcb585d-4094-4a52-bca2-bcc40b366606",
                        "title": payload["title"],
                        "problem": "Original research problem",
                        "schema_version": 11,
                        "ai_model": "gpt-6.1-sol",
                        "reasoning_effort": "high",
                        "difficulty": "medium",
                        "show_advanced_outcome_details": False,
                        "investigation_type": "literature",
                        "events": [],
                        "strategies": [],
                        "active_order": [],
                    },
                }
            ),
        )
    elif path == "/api/projects/create":
        create_payloads.append(json.loads(route.request.post_data or "{}"))
        request = create_payloads[-1]
        route.fulfill(
            status=201,
            content_type="application/json",
            body=json.dumps(
                {
                    "path": "/tmp/sigma-project-create-contract/create-contract.sigma",
                    "project": {
                        "id": "create-contract",
                        "title": request["title"],
                        "problem": request["problem"],
                        "schema_version": 9,
                        "ai_model": request["ai_model"],
                        "reasoning_effort": request["reasoning_effort"],
                        "difficulty": request["difficulty"],
                        "show_advanced_outcome_details": request["show_advanced_outcome_details"],
                        "investigation_type": request["investigation_type"],
                        "events": [],
                        "strategies": [],
                        "active_order": [],
                    },
                }
            ),
        )
    else:
        route.fulfill(status=200, content_type="application/json", body="{}")


with sync_playwright() as playwright:
    browser = playwright.chromium.launch(
        executable_path=os.environ.get(
            "SIGMA_BROWSER_EXECUTABLE",
            "/Applications/Google Chrome.app/Contents/MacOS/Google Chrome",
        ),
        headless=True,
    )
    page = browser.new_page(viewport={"width": 1280, "height": 900})
    page.route("**/api/**", api_fixture)
    page.goto(UI_URL)
    connection = page.locator(".project-chatgpt-signin > summary")
    expect(connection).to_have_attribute("aria-disabled", "false")
    credits = page.locator(".home-art-credit > span")
    expect(credits.nth(0)).to_have_text("Brian Kramer &")
    expect(credits.nth(1)).to_have_text("OpenAI Models")
    assert (
        page.locator(".home-art-credit").evaluate("el => getComputedStyle(el).textTransform")
        == "uppercase"
    )
    desktop_edges = page.locator(".home-projects").evaluate(
        "el => ({top: el.getBoundingClientRect().top, left: el.getBoundingClientRect().left})"
    )
    assert abs(desktop_edges["top"] - desktop_edges["left"]) < 1, desktop_edges
    page.screenshot(path="/tmp/sigma-home-projects-desktop.png")
    page.set_viewport_size({"width": 390, "height": 844})
    mobile_edges = page.locator(".home-projects").evaluate(
        "el => ({top: getComputedStyle(el).marginTop, left: getComputedStyle(el).marginLeft, width: el.getBoundingClientRect().width})"
    )
    assert mobile_edges["top"] == mobile_edges["left"], mobile_edges
    assert page.evaluate("document.documentElement.scrollWidth <= innerWidth")
    page.screenshot(path="/tmp/sigma-home-projects-mobile.png")
    page.set_viewport_size({"width": 1280, "height": 900})
    page.get_by_role("button", name="New", exact=True).click()
    dialog = page.get_by_role("dialog", name="New Project")
    expect(dialog).to_be_visible()
    dialog.get_by_label("Project name").fill("Create Contract Regression")
    dialog.get_by_label("Research problem").fill("Check the project creation API contract.")
    dialog.get_by_role("combobox", name="Research category").click()
    dialog.get_by_role("option", name="Mathematics").click()
    dialog.get_by_label("Difficulty").select_option("hard")
    create = dialog.get_by_role("button", name="Create", exact=True)
    expect(create).to_be_enabled()
    create.click()
    assert len(create_payloads) == 1, create_payloads
    payload = create_payloads[0]
    assert set(payload) == {
        "title",
        "problem",
        "investigation_type",
        "ai_model",
        "reasoning_effort",
        "difficulty",
        "show_advanced_outcome_details",
    }, payload
    assert payload["show_advanced_outcome_details"] is False, payload
    page.wait_for_function(
        "JSON.parse(localStorage.getItem('sigma.newProjectValues') || '{}').title === 'Create Contract Regression'"
    )
    saved = page.evaluate("JSON.parse(localStorage.getItem('sigma.newProjectValues'))")
    assert saved["investigation_type"] == "mathematical", saved
    assert saved["difficulty"] == "hard", saved
    assert saved["problem"] == "Check the project creation API contract.", saved
    # Reload Home and verify the last successfully created values initialize the next form.
    page.goto(UI_URL)
    page.get_by_role("button", name="New", exact=True).click()
    dialog = page.get_by_role("dialog", name="New Project")
    expect(dialog.get_by_label("Project name")).to_have_value("Create Contract Regression")
    expect(dialog.get_by_label("Research problem")).to_have_value(
        "Check the project creation API contract."
    )
    expect(dialog.get_by_role("combobox", name="Research category")).to_contain_text("Mathematics")
    expect(dialog.get_by_label("Difficulty")).to_have_value("hard")
    # Saved Projects places Save As immediately after Pin, and the dialog
    # presents the next version name without affecting the original.
    saved_entries.extend(
        [
            {
                "id": f"00000000-0000-4000-8000-00000000000{n}",
                "path": f"/tmp/sigma-project-create-contract/crucible-v{n}.json",
                "title": f"The Crucible v{n}",
                "investigation_type": "literature",
                "strategy_count": 3,
                "paper_count": 0,
                "best_paper_score": None,
                "difficulty": "medium",
                "research_running": False,
                "available": True,
                "pinned": False,
                "error": None,
            }
            for n in (3, 4)
        ]
    )
    page.goto(UI_URL)
    page.get_by_role("tab", name="Saved").click()
    group = page.locator(".recent-type-group").first
    expect(group).to_be_visible()
    if group.get_attribute("open") is None:
        group.locator("summary").click()
    row = page.locator(".recent-entry").filter(
        has=page.get_by_role("button", name="The Crucible v4")
    )
    expect(row).to_be_visible()
    actions = row.locator(".recent-meta-row button").evaluate_all(
        "(nodes) => nodes.map(node => node.getAttribute('aria-label'))"
    )
    assert actions == [
        "Just show this version of the project",
        "Save project with a new name",
        "Remove this project",
    ], actions
    row.get_by_role("button", name="Save project with a new name").click()
    save_as = page.get_by_role("dialog", name="Save Project As")
    expect(save_as).to_be_visible()
    expect(save_as.get_by_label("New project name")).to_have_value("The Crucible v5")
    save_as.get_by_role("button", name="Cancel").click()
    expect(save_as).not_to_be_visible()
    assert not save_as_payloads

    # Saving a pinned sibling must explain the existing one-visible-version
    # presentation rule rather than silently leaving a hidden new project.
    saved_entries[-1]["pinned"] = True
    page.goto(UI_URL)
    page.get_by_role("tab", name="Saved").click()
    group = page.locator(".recent-type-group").first
    if group.get_attribute("open") is None:
        group.locator("summary").click()
    row = page.locator(".recent-entry").filter(
        has=page.get_by_role("button", name="The Crucible v4")
    )
    row.get_by_role("button", name="Save project with a new name").click()
    save_as = page.get_by_role("dialog", name="Save Project As")
    expect(save_as.get_by_text("The new copy will open immediately", exact=False)).to_be_visible()
    save_as.get_by_role("button", name="Cancel").click()
    saved_entries[-1]["pinned"] = False
    page.goto(UI_URL)
    page.get_by_role("tab", name="Saved").click()
    group = page.locator(".recent-type-group").first
    if group.get_attribute("open") is None:
        group.locator("summary").click()
    row = page.locator(".recent-entry").filter(
        has=page.get_by_role("button", name="The Crucible v4")
    )
    row.get_by_role("button", name="Save project with a new name").click()
    save_as = page.get_by_role("dialog", name="Save Project As")
    save_as.get_by_label("New project name").fill("The Crucible alternate history")
    save_as.get_by_role("button", name="Save", exact=True).click()
    page.wait_for_function("window.location.pathname === '/project'")
    assert save_as_payloads == [
        {
            "path": "/tmp/sigma-project-create-contract/crucible-v4.json",
            "title": "The Crucible alternate history",
        }
    ], save_as_payloads
    browser.close()

print("PASS real Chrome project creation, Save As action/dialog and new-name copy.")
