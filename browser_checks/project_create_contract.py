"""Real Chrome regression: project creation omits the edit-only outcome preference."""

import json
import os
from urllib.parse import urlsplit

from playwright.sync_api import expect, sync_playwright

UI_URL = os.environ.get("SIGMA_BROWSER_BASE_URL", "http://127.0.0.1:5193")
create_payloads = []


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
        route.fulfill(
            status=200, content_type="application/json", body=json.dumps({"projects": []})
        )
    elif path == "/api/projects/destination":
        body = {
            "root": "/tmp/sigma-project-create-contract",
            "path": "/tmp/sigma-project-create-contract/create-contract.sigma",
            "exists": False,
        }
        route.fulfill(status=200, content_type="application/json", body=json.dumps(body))
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
    dialog.get_by_label("Show advanced Outcome details").check()
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
    assert payload["show_advanced_outcome_details"] is True, payload
    page.wait_for_function(
        "JSON.parse(localStorage.getItem('sigma.newProjectValues') || '{}').title === 'Create Contract Regression'"
    )
    saved = page.evaluate("JSON.parse(localStorage.getItem('sigma.newProjectValues'))")
    assert saved["investigation_type"] == "mathematical", saved
    assert saved["difficulty"] == "hard", saved
    assert saved["show_advanced_outcome_details"] is True, saved
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
    expect(dialog.get_by_label("Show advanced Outcome details")).to_be_checked()
    browser.close()

print("PASS real Chrome default local AI connection and project creation Outcome preference.")
