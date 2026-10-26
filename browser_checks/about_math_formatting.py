"""Real Chrome check for About's AI-assisted mathematical text description."""

import json
import os
from urllib.parse import urlsplit

from playwright.sync_api import expect, sync_playwright

UI_URL = os.environ.get("SIGMA_BROWSER_BASE_URL", "http://127.0.0.1:5193")


def app_fixture(route):
    path = urlsplit(route.request.url).path
    if path == "/api/cloud-auth/status":
        payload = {
            "enabled": False,
            "ready": True,
            "authenticated": False,
            "user": None,
            "target": "local",
            "local_setup_missing": [],
        }
    elif path in {"/api/projects/recent", "/api/projects/samples"}:
        payload = {"projects": []}
    elif path == "/api/ai/connection":
        payload = {
            "mode": "chatgpt",
            "status": "disconnected",
            "label": "Connect AI",
            "guidance": "Manual research is always available.",
            "checked_at": None,
            "ttl_seconds": 60,
            "accounts": [],
            "active_account": None,
        }
    else:
        payload = {}
    route.fulfill(status=200, content_type="application/json", body=json.dumps(payload))


with sync_playwright() as playwright:
    browser = playwright.chromium.launch(
        executable_path=os.environ.get(
            "SIGMA_BROWSER_EXECUTABLE",
            "/Applications/Google Chrome.app/Contents/MacOS/Google Chrome",
        ),
        headless=True,
    )
    page = browser.new_page(viewport={"width": 1440, "height": 900})
    page.route("**/api/**", app_fixture)
    page.goto(UI_URL)
    opener = page.get_by_role("button", name="About", exact=True)
    expect(opener).to_be_visible()
    opener.click()
    dialog = page.get_by_role("dialog", name="About SIGMA")
    expect(dialog).to_be_visible()
    features = dialog.locator("details").filter(has=page.get_by_text("Key Features", exact=True))
    features.locator("summary").click()
    expect(features.get_by_role("heading", name="Readable Mathematical Text")).to_be_visible()
    expect(features).to_contain_text(
        "AI can reformat plain-text project descriptions and saved Conclusions as Markdown with typeset equations."
    )
    expect(features).to_contain_text("formatted mathematics still needs review")
    for width, height in ((1440, 900), (390, 844), (320, 740)):
        page.set_viewport_size({"width": width, "height": height})
        expect(dialog).to_be_visible()
        assert dialog.evaluate("element => element.scrollWidth <= element.clientWidth"), width
        page.screenshot(path=f"/tmp/sigma-about-math-{width}.png")
    browser.close()

print("PASS real Chrome About feature copy and layout at desktop and narrow mobile widths.")
