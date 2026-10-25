"""Real Chrome checks for local Google placeholder and T40 account controls."""

import json
import os
from urllib.parse import urlencode
from uuid import uuid4

from playwright.sync_api import expect, sync_playwright

UI = os.environ.get("SIGMA_T23_UI_ORIGIN", "http://127.0.0.1:5173").rstrip("/")
API = os.environ.get("SIGMA_T23_API_ORIGIN", "http://127.0.0.1:8001").rstrip("/")
status = {
    "target": "local",
    "enabled": True,
    "ready": True,
    "authenticated": False,
    "user": None,
    "admin_contact_email": None,
}
login_attempts: list[str] = []
budget = {
    "allowance_usd": 2.0,
    "estimated_usage_usd": 2.0,
    "held_usd": 0.0,
    "reserved_and_estimated_usd": 2.0,
    "remaining_usd": 0.0,
    "unknown_provider_attempts": 0,
}

with sync_playwright() as playwright:
    browser = playwright.chromium.launch(
        executable_path=os.environ.get(
            "SIGMA_BROWSER_EXECUTABLE",
            "/Applications/Google Chrome.app/Contents/MacOS/Google Chrome",
        ),
        headless=True,
    )
    page = browser.new_page(viewport={"width": 1280, "height": 800})
    errors: list[str] = []
    page.on("pageerror", lambda error: errors.append(str(error)))

    def forward(route):
        route.fulfill(
            response=route.fetch(
                url=route.request.url.replace(UI, API),
                headers={**route.request.headers, "origin": "http://127.0.0.1:5173"},
            )
        )

    page.route("**/api/**", forward)
    page.route(
        "**/api/cloud-auth/status",
        lambda route: route.fulfill(
            status=200, content_type="application/json", body=json.dumps(status)
        ),
    )
    page.route(
        "**/api/cloud-research/budget",
        lambda route: route.fulfill(
            status=200,
            content_type="application/json",
            headers={"Cache-Control": "no-store"},
            body=json.dumps(budget),
        ),
    )

    def begin_login(route):
        login_attempts.append(route.request.url)
        route.fulfill(status=200, body="Google OAuth fixture route; no external sign-in started.")

    def sign_out(route):
        status.update(authenticated=False, user=None)
        route.fulfill(status=200, body="{}")

    page.route("**/api/cloud-auth/login", begin_login)
    page.route("**/api/cloud-auth/logout", sign_out)

    # The real local sign-in control opens the established account dialog.
    page.goto(UI + "/", wait_until="networkidle")
    expect(page.get_by_role("heading", name="Sign in with approved Gmail account to access projects.")).to_be_visible()
    expect(page.get_by_role("link", name="Administrator Settings")).to_have_count(0)
    google = page.get_by_role("button", name="Sign in with Google")
    expect(google).to_have_text("Sign in with Google")
    google.click()
    account = page.get_by_role("dialog", name="Connect your Google account")
    expect(account.locator(".google-account-target")).to_have_count(0)
    account.get_by_role("link", name="Sign in with Google", exact=True).click()
    expect(page.get_by_text("Google OAuth fixture route", exact=False)).to_be_visible()
    assert len(login_attempts) == 1

    # A verified ordinary member sees identity only in the dialog; the project
    # header retains Model/Thinking/Difficulty and both account controls.
    status.update(authenticated=True, user={"email": "reviewer@example.org", "role": "member"})
    created = page.request.post(
        API + "/api/projects/create",
        data={
            "title": f"T23.1 cloud Google sign-in browser check {uuid4().hex[:8]}",
            "problem": "Header control acceptance.",
        },
    )
    assert created.status == 201, created.text()
    page.goto(UI + "/project?" + urlencode({"path": created.json()["path"]}), wait_until="networkidle")
    header = page.locator(".project-art-header")
    controls = header.locator(".header-controls")
    google = controls.locator(".project-google-signin")
    expect(google).to_be_enabled()
    expect(google).to_have_text("Google account connected")
    expect(google).not_to_contain_text("reviewer@example.org")
    model = controls.locator(".project-model-pill")
    thinking = controls.locator(".project-thinking-pill")
    difficulty = controls.locator(".project-difficulty-badge")
    chatgpt = controls.locator(".project-chatgpt-signin > summary")
    for control in (model, thinking, difficulty, google, chatgpt):
        expect(control).to_be_visible()
    for control in (google, chatgpt):
        expect(control).to_have_attribute("data-tooltip-disabled", "")
        expect(control).not_to_have_attribute("title")
        expect(control).not_to_have_attribute("data-tooltip")

    for width, height in ((1280, 800), (390, 844), (320, 700)):
        page.set_viewport_size({"width": width, "height": height})
        google_style = google.evaluate("e => { const s = getComputedStyle(e); return [s.minHeight, s.padding, s.gap, s.fontFamily, s.fontSize, s.lineHeight, s.borderRadius]; }")
        chatgpt_style = chatgpt.evaluate("e => { const s = getComputedStyle(e); return [s.minHeight, s.padding, s.gap, s.fontFamily, s.fontSize, s.lineHeight, s.borderRadius]; }")
        assert google_style == chatgpt_style, (width, google_style, chatgpt_style)
        assert "connection-active" not in google.locator(".connection-dot").get_attribute("class")
        assert "connection-active" not in chatgpt.locator(".connection-dot").get_attribute("class")
        assert page.evaluate("document.documentElement.scrollWidth <= innerWidth"), width
        page.screenshot(path=f"/tmp/sigma-t23.1-cloud-header-{width}.png", full_page=True)

    google.click()
    account = page.get_by_role("dialog", name="Google account")
    expect(account.get_by_text("reviewer@example.org", exact=True)).to_be_visible()
    expect(account.get_by_role("button", name="Use another Google account")).to_have_count(0)
    account.get_by_role("button", name="Sign out", exact=True).click()
    expect(page).to_have_url(UI + "/")
    expect(page.get_by_role("heading", name="Sign in with approved Gmail account to access projects.")).to_be_visible()
    assert not status["authenticated"]

    # Hosted funding is read-only, visible only inside the existing ChatGPT
    # connection dialog; Home contains no separate allowance box.
    status.update(
        target="hosted",
        authenticated=True,
        user={"email": "reviewer@example.org", "role": "member"},
    )
    page.goto(UI + "/", wait_until="networkidle")
    expect(page.get_by_role("region", name="Cloud research budget")).to_have_count(0)
    connection = page.locator(".home-topline .api-connection > summary")
    connection.click()
    details = page.get_by_role("dialog", name="AI connection settings")
    expect(details).to_contain_text("SIGMA service-funded inference")
    expect(details).to_contain_text("ChatGPT allowance")
    expect(details).to_contain_text("$0.00 remaining")
    expect(details).to_contain_text("allowance is exhausted")
    assert not errors, errors
    browser.close()

print(
    "PASS real Chrome local Google account dialog/login route, signed-in project identity, "
    "sign-out, responsive project header and hosted allowance only in the ChatGPT dialog; "
    "external Google OAuth was not invoked"
)
