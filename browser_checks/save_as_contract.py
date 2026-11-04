"""Real Chrome Save As acceptance, independent of New Project options."""

import json
import os
from urllib.parse import urlsplit

from playwright.sync_api import expect, sync_playwright

UI_URL = os.environ.get("SIGMA_BROWSER_BASE_URL", "http://127.0.0.1:5173")
save_requests: list[dict] = []
saved = [
    {
        "id": f"00000000-0000-4000-8000-00000000000{number}",
        "path": f"/tmp/sigma-save-as/crucible-v{number}.json",
        "title": f"The Crucible v{number}",
        "investigation_type": "literature",
        "strategy_count": 3,
        "paper_count": 0,
        "best_paper_score": None,
        "difficulty": "medium",
        "research_running": False,
        "available": True,
        "pinned": False,
        "included_example": False,
        "error": None,
    }
    for number in (3, 4)
]


def fixture(route):
    path = urlsplit(route.request.url).path
    if path == "/api/cloud-auth/status":
        result = {
            "enabled": False,
            "ready": True,
            "authenticated": False,
            "user": None,
            "target": "local",
            "local_setup_missing": [],
        }
    elif path == "/api/ai/connection":
        result = {"mode": "api_key", "status": "connected", "accounts": []}
    elif path == "/api/ai/models":
        result = {
            "models": [
                {
                    "id": "gpt-6.1-sol",
                    "label": "GPT-6.1-Sol",
                    "efforts": ["high"],
                    "relative_cost": "$$",
                    "availability": "available",
                }
            ],
            "default_model": "gpt-6.1-sol",
            "default_effort": "high",
        }
    elif path == "/api/projects/recent":
        result = {"projects": saved}
    elif path == "/api/projects/samples":
        result = {"projects": []}
    elif path == "/api/projects/save-as":
        request = json.loads(route.request.post_data or "{}")
        save_requests.append(request)
        result = {
            "path": "/tmp/sigma-save-as/new-project.json",
            "project": {
                "id": "8dcb585d-4094-4a52-bca2-bcc40b366606",
                "title": request["title"],
                "problem": "Existing research",
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
        route.fulfill(status=201, content_type="application/json", body=json.dumps(result))
        return
    else:
        result = {}
    route.fulfill(status=200, content_type="application/json", body=json.dumps(result))


with sync_playwright() as playwright:
    browser = playwright.chromium.launch(
        executable_path=os.environ.get("SIGMA_BROWSER_EXECUTABLE"),
        headless=True,
    )
    page = browser.new_page(viewport={"width": 1280, "height": 900})
    page.route("**/api/**", fixture)

    def row_for_v4():
        page.goto(UI_URL)
        page.get_by_role("tab", name="Saved").click()
        group = page.locator(".recent-type-group").first
        expect(group).to_be_visible()
        if group.get_attribute("open") is None:
            group.locator("summary").click()
        row = page.locator(".recent-entry").filter(
            has=page.get_by_role("button", name="The Crucible v4", exact=True)
        )
        expect(row).to_be_visible()
        return row

    row = row_for_v4()
    actions = row.locator(".recent-meta-row button").evaluate_all(
        "(nodes) => nodes.map(node => node.getAttribute('aria-label'))"
    )
    assert actions == [
        "Just show this version of the project",
        "Save project with a new name",
        "Remove this project",
    ], actions
    copy = row.get_by_role("button", name="Save project with a new name")
    expect(copy).to_have_attribute("title", "Save project with a new name")
    copy.click()
    dialog = page.get_by_role("dialog", name="Save Project As")
    expect(dialog).to_be_visible()
    expect(dialog.get_by_label("New project name")).to_have_value("The Crucible v5")
    dialog.get_by_role("button", name="Cancel").click()
    expect(dialog).not_to_be_visible()
    assert save_requests == []

    saved[1]["pinned"] = True
    row = row_for_v4()
    row.get_by_role("button", name="Save project with a new name").click()
    dialog = page.get_by_role("dialog", name="Save Project As")
    expect(dialog.get_by_text("The new copy will open immediately", exact=False)).to_be_visible()
    dialog.get_by_role("button", name="Cancel").click()
    assert save_requests == []

    saved[1]["pinned"] = False
    row = row_for_v4()
    row.get_by_role("button", name="Save project with a new name").click()
    dialog = page.get_by_role("dialog", name="Save Project As")
    dialog.get_by_label("New project name").fill("Crucible alternative research")
    dialog.get_by_role("button", name="Save", exact=True).click()
    page.wait_for_function("window.location.pathname === '/project'")
    assert save_requests == [
        {
            "path": "/tmp/sigma-save-as/crucible-v4.json",
            "title": "Crucible alternative research",
        }
    ], save_requests
    browser.close()

print("PASS Chrome Save As icon, order, dialog, pinned warning, Cancel and Save.")
