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
    elif path == "/api/projects/samples":
        route.fulfill(
            status=200, content_type="application/json", body=json.dumps({"projects": []})
        )
    elif path == "/api/projects/recent":
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
        route.fulfill(
            status=422,
            content_type="application/json",
            body=json.dumps({"error": "Captured request; no project was created."}),
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
    page.get_by_role("button", name="New", exact=True).click()
    dialog = page.get_by_role("dialog", name="New Project")
    expect(dialog).to_be_visible()
    dialog.get_by_label("Project name").fill("Create Contract Regression")
    dialog.get_by_label("Research problem").fill("Check the project creation API contract.")
    create = dialog.get_by_role("button", name="Create", exact=True)
    expect(create).to_be_enabled()
    create.click()
    expect(dialog.get_by_role("alert")).to_have_text(
        "Captured request; no project was created."
    )
    assert len(create_payloads) == 1, create_payloads
    payload = create_payloads[0]
    assert set(payload) == {
        "title",
        "problem",
        "investigation_type",
        "ai_model",
        "reasoning_effort",
        "difficulty",
    }, payload
    assert "show_advanced_outcome_details" not in payload, payload
    browser.close()

print("PASS real Chrome project creation sends only fields accepted by the create API.")
