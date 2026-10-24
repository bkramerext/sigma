"""Real Chrome checks for local Google placeholder and T22 cloud identity controls."""

import json
import os
from urllib.parse import urlencode
from uuid import uuid4

from playwright.sync_api import expect, sync_playwright

UI = os.environ.get("SIGMA_T23_UI_ORIGIN", "http://127.0.0.1:5173").rstrip("/")
API = os.environ.get("SIGMA_T23_API_ORIGIN", "http://127.0.0.1:8001").rstrip("/")
cloud_status = {
    "enabled": True,
    "ready": True,
    "authenticated": False,
    "user": None,
    "admin_contact_email": None,
}
login_attempts: list[str] = []

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
            status=200,
            content_type="application/json",
            body=json.dumps(cloud_status),
        ),
    )
    page.route(
        "**/api/cloud-research/budget",
        lambda route: route.fulfill(
            status=200,
            content_type="application/json",
            headers={"Cache-Control": "no-store"},
            body=json.dumps(
                {
                    "allowance_usd": 2.0,
                    "estimated_usage_usd": 2.0,
                    "held_usd": 0.0,
                    "reserved_and_estimated_usd": 2.0,
                    "remaining_usd": 0.0,
                    "unknown_provider_attempts": 0,
                }
            ),
        ),
    )

    def begin_login(route):
        login_attempts.append(route.request.url)
        route.fulfill(
            status=200, body="Local Google OAuth route reached; no external sign-in started."
        )

    def sign_out(route):
        cloud_status.update(authenticated=False, user=None)
        route.fulfill(status=200, body="{}")

    page.route("**/api/cloud-auth/login", begin_login)
    page.route("**/api/cloud-auth/logout", sign_out)

    # A signed-out cloud workspace retains the working Google login route.
    page.goto(UI + "/", wait_until="networkidle")
    continue_google = page.get_by_role("link", name="Continue with Google", exact=True)
    expect(continue_google).to_have_attribute("href", "/api/cloud-auth/login")
    continue_google.click()
    expect(page.get_by_text("Local Google OAuth route reached", exact=False)).to_be_visible()
    assert len(login_attempts) == 1

    # Use the authenticated cloud context to exercise the project-header account state.
    cloud_status.update(
        authenticated=True,
        user={"email": "reviewer@example.org", "role": "member"},
    )
    created = page.request.post(
        API + "/api/projects/create",
        data={
            "title": f"T23.1 cloud Google sign-in browser check {uuid4().hex[:8]}",
            "problem": "Header control acceptance.",
        },
    )
    assert created.status == 201, created.text()
    path = created.json()["path"]
    page.goto(UI + "/project?" + urlencode({"path": path}), wait_until="networkidle")
    header = page.locator(".project-art-header")
    controls = header.locator(".header-controls")
    cloud_identity = controls.locator(".cloud-home-controls.compact")
    expect(cloud_identity).to_be_visible()
    expect(cloud_identity).to_contain_text("reviewer@example.org")
    expect(cloud_identity.get_by_role("button", name="Sign out", exact=True)).to_be_visible()
    expect(controls.locator(".project-google-signin")).to_have_count(0)
    model = controls.locator(".project-model-pill")
    thinking = controls.locator(".project-thinking-pill")
    difficulty = controls.locator(".project-difficulty-badge")
    chatgpt = controls.locator(".project-chatgpt-signin > summary")
    expect(model).to_be_visible()
    expect(thinking).to_be_visible()
    expect(difficulty).to_be_visible()
    expect(chatgpt).to_be_visible()

    for width, height in ((1280, 800), (390, 844), (320, 700)):
        page.set_viewport_size({"width": width, "height": height})
        assert page.evaluate("document.documentElement.scrollWidth <= innerWidth"), (
            width,
            page.evaluate(
                "[document.documentElement.scrollWidth, innerWidth, ...[...document.querySelectorAll('.project-art-header *')].filter(e => e.getBoundingClientRect().right > innerWidth).map(e => [e.className || e.tagName, e.getBoundingClientRect().x, e.getBoundingClientRect().width, e.getBoundingClientRect().right])]"
            ),
        )
        google_box = cloud_identity.bounding_box()
        chatgpt_box = chatgpt.bounding_box()
        model_box = model.bounding_box()
        thinking_box = thinking.bounding_box()
        assert google_box and chatgpt_box and model_box and thinking_box
        assert google_box["y"] < chatgpt_box["y"], (width, google_box, chatgpt_box)
        assert model_box["y"] < thinking_box["y"], (width, model_box, thinking_box)
        if width == 1280:
            assert google_box["x"] > model_box["x"]
            assert chatgpt_box["x"] > thinking_box["x"]
        page.screenshot(path=f"/tmp/sigma-t23.1-cloud-header-{width}.png", full_page=True)

    cloud_identity.get_by_role("button", name="Sign out", exact=True).click()
    expect(page).to_have_url(UI + "/")
    expect(page.get_by_role("link", name="Continue with Google", exact=True)).to_be_visible()
    assert not cloud_status["authenticated"]

    # Exhaustion is visible to the owner while saved projects remain available.
    cloud_status.update(
        authenticated=True,
        user={"email": "reviewer@example.org", "role": "member"},
    )
    page.goto(UI + "/", wait_until="networkidle")
    budget = page.get_by_role("region", name="Cloud research budget")
    expect(budget).to_contain_text("$0.00 remaining of $2.00")
    expect(budget).to_contain_text("allowance is exhausted")
    expect(page.get_by_role("button", name="New", exact=True)).to_be_enabled()
    page.get_by_role("tab", name="Recent").click()
    created_title = created.json()["project"]["title"]
    project_group = page.locator(".recent-type-group").filter(has_text=created_title)
    project_group.locator("summary").click()
    saved_project = page.get_by_role("button", name=created_title, exact=True)
    expect(saved_project).to_be_visible()
    saved_project.click()
    expect(page.locator(".project-art-header")).to_be_visible()

    # Access Management exposes effective policy plus persisted owner balances,
    # and an administrator can edit an individual rule allowance in place.
    grants_snapshot = {
        "bootstrap_admin": "admin@example.org",
        "grants": [
            {
                "kind": "domain",
                "value": "example.org",
                "role": "member",
                "active": 1,
                "allowance_usd": 5.0,
                "effective_allowance_usd": 5.0,
            },
            {
                "kind": "email",
                "value": "reviewer@example.org",
                "role": "member",
                "active": 1,
                "allowance_usd": None,
                "effective_allowance_usd": 5.0,
            },
        ],
        "sessions": [
            {
                "email": "reviewer@example.org",
                "role": "member",
                "authorized": True,
                "status": "active",
                "expires_at": 2_000_000_000,
                "allowance_usd": 5.0,
                "spending": {
                    "estimated_usage_usd": 0.75,
                    "held_usd": 0.25,
                    "reserved_and_estimated_usd": 1.0,
                    "remaining_usd": 4.0,
                },
            }
        ],
    }

    def grants_route(route):
        if route.request.method == "PUT":
            assert route.request.post_data_json == {"allowance_usd": 3.5}
            grants_snapshot["grants"][1]["allowance_usd"] = 3.5
            grants_snapshot["grants"][1]["effective_allowance_usd"] = 3.5
            grants_snapshot["sessions"][0]["allowance_usd"] = 3.5
        route.fulfill(status=200, content_type="application/json", body=json.dumps(grants_snapshot))

    page.route("**/api/cloud-auth/admin/grants", grants_route)
    page.route("**/api/cloud-auth/admin/grants/**", grants_route)
    cloud_status.update(
        authenticated=True,
        user={"email": "admin@example.org", "role": "admin"},
    )
    page.goto(UI + "/", wait_until="networkidle")
    page.get_by_role("button", name="Access Management", exact=True).click()
    dialog = page.get_by_role("dialog", name="Access Management")
    expect(dialog).to_contain_text("estimated $0.75")
    expect(dialog).to_contain_text("held $0.25")
    expect(dialog).to_contain_text("remaining $4.00")
    expect(dialog).to_contain_text("Domain allowances apply separately to each person")
    researcher_row = dialog.locator("li").filter(has_text="reviewer@example.org").last
    researcher_row.get_by_role("spinbutton", name="Allowance for reviewer@example.org").fill("3.5")
    researcher_row.get_by_role("button", name="Save allowance").click()
    expect(dialog).to_contain_text("effective allowance $3.50")
    assert not errors, errors
    browser.close()

print(
    "PASS real Chrome cloud Google login route, signed-in project identity, sign-out transition, "
    "desktop/mobile header placement, exhaustion with saved-project access, and no horizontal overflow; external Google OAuth was not invoked"
)
