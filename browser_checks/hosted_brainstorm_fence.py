"""Hosted Brainstorm stays hidden and direct browser routes fail closed."""

import json
import os

from playwright.sync_api import expect, sync_playwright

ORIGIN = os.environ.get("SIGMA_CHAT_UI_ORIGIN", "http://127.0.0.1:5173").rstrip("/")
CHROMIUM = os.environ.get("SIGMA_BROWSER_EXECUTABLE")

with sync_playwright() as playwright:
    browser = playwright.chromium.launch(executable_path=CHROMIUM, headless=True)
    page = browser.new_page()

    def hosted_api(route):
        if route.request.url.endswith("/api/cloud-auth/status"):
            route.fulfill(
                status=200,
                content_type="application/json",
                body=json.dumps(
                    {
                        "enabled": True,
                        "ready": True,
                        "authenticated": False,
                        "user": None,
                        "target": "hosted",
                        "admin_contact_email": None,
                    }
                ),
            )
        else:
            route.fulfill(status=404, content_type="application/json", body='{"error":"fixture"}')

    page.route("**/api/**", hosted_api)
    page.goto(ORIGIN + "/", wait_until="domcontentloaded")
    expect(page.get_by_role("button", name="Brainstorm", exact=True)).to_have_count(0)

    for path in ("/brainstorm", "/chat"):
        page.goto(ORIGIN + path, wait_until="domcontentloaded")
        expect(page.get_by_role("status")).to_have_text(
            "This page is available when running SIGMA locally."
        )
        expect(page.locator(".chat-page")).to_have_count(0)
        expect(page.get_by_role("link", name="Return to SIGMA")).to_be_visible()

    browser.close()
print("PASS hosted Home and direct Brainstorm routes remain inaccessible")
