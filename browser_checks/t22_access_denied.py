"""Real Chrome smoke for denied cloud identities and the parent T22 Demo handoff."""

import json
import os
from urllib.parse import parse_qs, urlsplit

from playwright.sync_api import expect, sync_playwright

BASE_URL = os.environ.get("SIGMA_BROWSER_BASE_URL", "http://127.0.0.1:5173")
requested_api: list[str] = []

with sync_playwright() as playwright:
    browser = playwright.chromium.launch(
        executable_path=os.environ.get(
            "SIGMA_BROWSER_EXECUTABLE",
            "/Applications/Google Chrome.app/Contents/MacOS/Google Chrome",
        ),
        headless=True,
    )
    page = browser.new_page(viewport={"width": 1280, "height": 850})
    page.on("request", lambda request: requested_api.append(request.url) if "/api/" in request.url else None)

    def status(route):
        route.fulfill(
            status=200,
            content_type="application/json",
            body=json.dumps(
                {
                    "enabled": True,
                    "ready": True,
                    "authenticated": False,
                    "user": None,
                    "admin_contact_email": "access@example.org",
                }
            ),
        )

    page.route("**/api/cloud-auth/status", status)
    page.goto(f"{BASE_URL}/?access=denied", wait_until="networkidle")
    expect(page.get_by_role("heading", name="Access not yet granted")).to_be_visible()
    expect(page.get_by_text("Your Google account is valid, but it has not been invited to SIGMA.")).to_be_visible()

    demo = page.get_by_role("link", name="Explore Demo")
    expect(demo).to_have_attribute("href", "/demo")
    invite = page.get_by_role("link", name="Request Invitation")
    parts = urlsplit(invite.get_attribute("href") or "")
    assert parts.scheme == "mailto" and parts.path == "access@example.org"
    request_fields = parse_qs(parts.query)
    assert request_fields["subject"] == ["SIGMA invitation request"]
    assert "I signed in to SIGMA with my Google account" in request_fields["body"][0]
    switch = page.get_by_role("link", name="Use Another Account")
    expect(switch).to_have_attribute("href", "/api/cloud-auth/login")

    for width, height in ((1280, 850), (390, 844)):
        page.set_viewport_size({"width": width, "height": height})
        assert page.evaluate("document.documentElement.scrollWidth <= window.innerWidth")
    page.screenshot(path="/tmp/sigma-t22-access-not-granted-mobile.png", full_page=True)
    demo.click()
    page.wait_for_url("**/demo")
    expect(page.get_by_role("heading", name="SIGMA Demo")).to_be_visible()
    expect(page.get_by_text("not provisioned as a private workspace")).to_be_visible()
    assert not [url for url in requested_api if "/api/projects/" in url]
    assert not [url for url in requested_api if "/api/ai/" in url]
    browser.close()

print("PASS real Chrome unauthorized screen, prefilled invitation draft, account switch link, and no-workspace T22 Demo handoff")
