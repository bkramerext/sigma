"""Rendered connection, sponsorship, and Home dialog checks for T313."""

import json
import os
from pathlib import Path
from urllib.parse import urlparse

from playwright.sync_api import expect, sync_playwright

UI_URL = os.environ.get("SIGMA_BROWSER_BASE_URL", "http://127.0.0.1:5173")
FIXTURE_URL = os.environ.get("SIGMA_BROWSER_FIXTURE_URL", "http://127.0.0.1:8026")
SCENARIO = {"name": "disconnected"}
EMAIL = "private@example.test"
EVIDENCE = Path("docs/evaluations/t313/evidence")


def status_payload() -> dict:
    if SCENARIO["name"] != "sponsored":
        return {
            "target": "local",
            "enabled": False,
            "ready": True,
            "authenticated": False,
            "user": None,
            "account": None,
            "admin_contact_email": None,
        }
    return {
        "target": "hosted",
        "enabled": True,
        "ready": True,
        "authenticated": True,
        "user": {"email": "fixture-admin@example.test", "role": "admin"},
        "account": {
            "identity": {"email": "fixture-admin@example.test", "verified": True},
            "access": {"status": "active", "role": "admin"},
            "workspace": {"available": True, "id": "fixture"},
            "model_access": {"mode": "sponsored", "connection": "connected"},
            "sponsorship": {"eligible": True, "forced": True},
        },
        "admin_contact_email": None,
    }


def ai_payload() -> dict:
    connected = SCENARIO["name"] == "connected"
    return {
        "mode": "chatgpt",
        "status": "connected" if connected else "disconnected",
        "label": "ChatGPT connected" if connected else "Connect to ChatGPT",
        "guidance": "ChatGPT connection fixture.",
        "checked_at": "2026-10-28T12:00:00Z" if connected else None,
        "ttl_seconds": 60,
        "account_label": EMAIL if connected else None,
        "active_account": "fixture-account" if connected else None,
        "accounts": [],
    }


def handle_api(route) -> None:
    path = urlparse(route.request.url).path
    if path == "/api/cloud-auth/status":
        payload = status_payload()
    elif path == "/api/ai/connection":
        payload = ai_payload()
    elif path == "/api/cloud-research/connection":
        payload = {"status": "connected", "guidance": "SIGMA sponsored provider connected."}
    else:
        route.fulfill(response=route.fetch(url=route.request.url.replace(UI_URL, FIXTURE_URL)))
        return
    route.fulfill(status=200, content_type="application/json", body=json.dumps(payload))


with sync_playwright() as playwright:
    EVIDENCE.mkdir(parents=True, exist_ok=True)
    browser = playwright.chromium.launch(
        executable_path=os.environ.get(
            "SIGMA_BROWSER_EXECUTABLE",
            "/Applications/Google Chrome.app/Contents/MacOS/Google Chrome",
        ),
        headless=True,
    )
    page = browser.new_page(viewport={"width": 1440, "height": 900})
    page.route("**/api/**", handle_api)

    page.goto(UI_URL, wait_until="domcontentloaded")
    connection = page.locator(".api-connection > summary")
    expect(connection.get_by_role("status")).to_have_text("Connect to ChatGPT")
    expect(connection.locator(".connection-disconnected")).to_be_visible()
    expect(page.locator(".sample-type-group")).to_have_count(9)
    for width, height in ((1440, 900), (390, 844), (320, 740)):
        page.set_viewport_size({"width": width, "height": height})
        page.evaluate("window.scrollTo(0, 0)")
        page.wait_for_timeout(150)
        assert page.evaluate("document.documentElement.scrollWidth <= innerWidth")
        if width < 900:
            expect(page.locator(".home-slogan")).to_be_hidden()
        page.screenshot(path=str(EVIDENCE / f"home-disconnected-{width}.png"))

    SCENARIO["name"] = "connected"
    page.goto(UI_URL, wait_until="domcontentloaded")
    connection = page.locator(".api-connection > summary")
    expect(connection.get_by_role("status")).to_have_text("ChatGPT connected")
    connection.hover()
    tooltip = page.get_by_role(
        "tooltip", name="ChatGPT is connected. Click to return to sponsorship."
    )
    expect(tooltip).to_be_visible()
    assert EMAIL not in (connection.get_attribute("data-tooltip") or "")
    assert connection.get_attribute("title") is None

    SCENARIO["name"] = "sponsored"
    page.goto(UI_URL, wait_until="domcontentloaded")
    connection = page.locator(".api-connection > summary")
    expect(connection.get_by_role("status")).to_have_text("Sponsored ChatGPT")
    expect(connection.locator(".connection-connected")).to_be_visible()
    expect(connection.get_by_role("button", name="Sponsored allowance details")).to_contain_text(
        "Unlimited"
    )
    for width, height in ((1440, 900), (390, 844), (320, 740)):
        page.set_viewport_size({"width": width, "height": height})
        page.evaluate("window.scrollTo(0, 0)")
        page.wait_for_timeout(150)
        assert page.evaluate("document.documentElement.scrollWidth <= innerWidth")
        page.screenshot(path=str(EVIDENCE / f"home-sponsored-{width}.png"))

    page.set_viewport_size({"width": 390, "height": 844})
    page.get_by_role("button", name="New", exact=True).click()
    dialog = page.get_by_role("dialog", name="New Project")
    expect(dialog).to_be_visible()
    expect(dialog.get_by_label("Project name")).to_be_focused()
    assert page.evaluate("document.documentElement.scrollWidth <= innerWidth")
    dialog.screenshot(path=str(EVIDENCE / "new-project-dialog-390.png"))
    page.keyboard.press("Escape")
    expect(dialog).to_be_hidden()
    browser.close()

print(
    "PASS disconnected, connected and sponsored status; Home and New Project at 1440px, 390px and 320px"
)
