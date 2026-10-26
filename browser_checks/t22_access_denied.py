"""Real Chrome checks for cloud Home access and unrestricted local Home."""

import json
import os
from pathlib import Path
from urllib.parse import parse_qs, urlsplit

from playwright.sync_api import expect, sync_playwright

BASE_URL = os.environ.get("SIGMA_BROWSER_BASE_URL", "http://127.0.0.1:5173")
DEMO_AUDIT = json.loads(
    (Path(__file__).resolve().parents[1] / "cloud-demo/handshake-demo-audit.json").read_text(
        encoding="utf-8"
    )
)
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
    page.on(
        "request",
        lambda request: requested_api.append(request.url) if "/api/" in request.url else None,
    )

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
                    "admin_contact_email": "zetacontinuation@gmail.com",
                }
            ),
        )

    page.route("**/api/cloud-auth/status", status)
    guest_page = browser.new_page(viewport={"width": 1280, "height": 850})
    guest_page.route("**/api/cloud-auth/status", status)
    guest_page.goto(BASE_URL, wait_until="networkidle")
    expect(guest_page.get_by_role("link", name="Explore Demo")).to_have_attribute("href", "/demo")
    expect(guest_page.get_by_role("heading", name="Sign in to access projects")).to_be_visible()
    page.route(
        "**/api/cloud-auth/denied",
        lambda route: route.fulfill(
            status=200, content_type="application/json", body='{"email":"visitor@example.org"}'
        ),
    )
    page.route(
        "**/api/cloud-auth/login",
        lambda route: route.fulfill(status=200, body="Fresh Google account selection started"),
    )
    page.goto(f"{BASE_URL}/?access=denied", wait_until="networkidle")
    expect(page.get_by_role("heading", name="Access not yet granted")).to_be_visible()
    expect(
        page.get_by_text("Your Google account is valid, but it has not been invited to SIGMA.")
    ).to_be_visible()
    expect(page.get_by_text("visitor@example.org")).to_be_visible()
    expect(page.get_by_role("heading", name="Projects")).to_have_count(0)

    demo = page.get_by_role("link", name="Explore Demo")
    expect(demo).to_have_attribute("href", "/demo?access=denied")
    invite = page.get_by_role("link", name="Request Invitation")
    parts = urlsplit(invite.get_attribute("href") or "")
    assert parts.scheme == "mailto" and parts.path == "zetacontinuation@gmail.com"
    request_fields = parse_qs(parts.query)
    assert request_fields["subject"] == ["SIGMA invitation request"]
    assert "visitor@example.org" in request_fields["body"][0]
    switch = page.get_by_role("link", name="Use Another Account")
    expect(switch).to_have_attribute("href", "/api/cloud-auth/login")
    for width, height in ((1280, 850), (390, 844)):
        page.set_viewport_size({"width": width, "height": height})
        assert page.evaluate("document.documentElement.scrollWidth <= window.innerWidth")
    page.screenshot(path="/tmp/sigma-t22-access-not-granted-mobile.png", full_page=True)
    switch.click()
    expect(page.get_by_text("Fresh Google account selection started")).to_be_visible()

    demo_page = browser.new_page(viewport={"width": 1280, "height": 850})
    demo_page.route("**/api/cloud-auth/status", status)
    demo_page.route(
        "**/api/cloud-auth/denied",
        lambda route: route.fulfill(
            status=200, content_type="application/json", body='{"email":"visitor@example.org"}'
        ),
    )
    demo_page.route(
        "**/api/cloud-demo/",
        lambda route: route.fulfill(
            status=200, content_type="application/json", body=json.dumps(DEMO_AUDIT)
        ),
    )
    demo_page.goto(f"{BASE_URL}/?access=denied", wait_until="networkidle")
    demo_page.get_by_role("link", name="Explore Demo").click()
    demo_page.wait_for_url("**/demo?access=denied")
    expect(
        demo_page.get_by_role("heading", name="Explore a SIGMA research project")
    ).to_be_visible()
    expect(demo_page.get_by_role("heading", name="Counting Pairwise Handshakes")).to_be_visible()
    assert not [url for url in requested_api if "/api/projects/" in url]
    assert not [url for url in requested_api if "/api/ai/" in url]

    for width, height in ((1280, 850), (390, 844)):
        demo_page.set_viewport_size({"width": width, "height": height})
        assert demo_page.evaluate("document.documentElement.scrollWidth <= window.innerWidth")

    local_page = browser.new_page(viewport={"width": 1280, "height": 850})
    local_page.route(
        "**/api/cloud-auth/status",
        lambda route: route.fulfill(
            status=200,
            content_type="application/json",
            body='{"enabled":false,"ready":true,"authenticated":false,"user":null,"admin_contact_email":null}',
        ),
    )
    local_page.goto(BASE_URL, wait_until="networkidle")
    expect(local_page.locator(".home-projects")).to_be_visible()
    expect(local_page.get_by_role("button", name="New")).to_be_visible()
    expect(local_page.get_by_text("Google Sign-in", exact=True)).to_have_count(0)
    expect(local_page.get_by_role("link", name="Sign in with Google")).to_have_count(0)

    admin_page = browser.new_page(viewport={"width": 1280, "height": 850})
    admin_page.route(
        "**/api/**",
        lambda route: route.fulfill(
            status=200,
            content_type="application/json",
            body='{"projects":[],"models":[],"samples":[]}',
        ),
    )
    admin_page.route(
        "**/api/cloud-auth/status",
        lambda route: route.fulfill(
            status=200,
            content_type="application/json",
            body=json.dumps(
                {
                    "enabled": True,
                    "ready": True,
                    "authenticated": True,
                    "user": {"email": "admin@example.org", "role": "admin"},
                    "admin_contact_email": "zetacontinuation@gmail.com",
                }
            ),
        ),
    )
    admin_page.route(
        "**/api/cloud-auth/admin/grants",
        lambda route: route.fulfill(
            status=200,
            content_type="application/json",
            body=json.dumps(
                {
                    "grants": [],
                    "sessions": [
                        {"email": "admin@example.org", "role": "admin", "expires_at": 1_800_000_000}
                    ],
                    "bootstrap_admin": "admin@example.org",
                }
            ),
        ),
    )
    admin_page.goto(BASE_URL, wait_until="networkidle")
    expect(admin_page.locator(".home-topline .cloud-home-user")).to_be_visible()
    expect(admin_page.get_by_text("admin@example.org", exact=True).first).to_be_visible()
    expect(admin_page.locator(".project-google-placeholder")).to_have_count(0)
    admin_page.get_by_role("button", name="Access Management").click()
    expect(admin_page.get_by_role("heading", name="Accounts and sessions")).to_be_visible()
    expect(admin_page.get_by_text("admin@example.org", exact=True).last).to_be_visible()
    expect(admin_page.get_by_text("admin · session expires")).to_be_visible()

    browser.close()

print(
    "PASS real Chrome denied account Home, verified-email invitation draft, account switch, Demo handoff, unrestricted local Home, and administrator session summary"
)
