"""Real-Chrome acceptance for issue #279's guest invitation pill flow."""

import json
import os

from playwright.sync_api import expect, sync_playwright

BASE_URL = os.environ.get("SIGMA_BROWSER_BASE_URL", "http://127.0.0.1:5173")


def guest_status(route):
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


with sync_playwright() as playwright:
    browser = playwright.chromium.launch(
        executable_path=os.environ.get(
            "SIGMA_BROWSER_EXECUTABLE",
            "/Applications/Google Chrome.app/Contents/MacOS/Google Chrome",
        ),
        headless=True,
    )
    page = browser.new_page(viewport={"width": 1280, "height": 850})
    posts: list[dict] = []
    page.route("**/api/cloud-auth/status", guest_status)

    def denied_identity(route):
        route.fulfill(
            status=200,
            content_type="application/json",
            body=json.dumps(
                {
                    "email": "visitor@example.org",
                    "invitation_status": "notified" if len(posts) > 1 else None,
                }
            ),
        )

    page.route(
        "**/api/cloud-auth/denied",
        denied_identity,
    )
    page.goto(BASE_URL, wait_until="networkidle")
    expect(page.get_by_role("heading", name="Projects")).to_be_visible()
    invite_pill = page.get_by_role("button", name="Invite me!")
    invite_pill.click()
    guest_invite_dialog = page.get_by_role("dialog", name="Request an invitation")
    expect(guest_invite_dialog).to_be_visible()
    expect(
        guest_invite_dialog.get_by_text(
            "Sign in with Google so SIGMA can verify your account before recording an invitation request."
        )
    ).to_be_visible()
    expect(
        guest_invite_dialog.get_by_role("link", name="Sign in with Google to continue")
    ).to_have_attribute("href", "/api/cloud-auth/login?invite=1")
    guest_invite_dialog.get_by_role("button", name="Close").click()
    expect(page.get_by_role("link", name="Sign in with Google")).to_have_attribute(
        "href", "/api/cloud-auth/login"
    )
    page.set_viewport_size({"width": 390, "height": 844})
    assert page.evaluate("document.documentElement.scrollWidth <= window.innerWidth")

    def invitation_response(route):
        posts.append({"method": route.request.method, "body": route.request.post_data_json})
        if len(posts) == 1:
            route.fulfill(
                status=503,
                content_type="application/json",
                body='{"detail":"Your request could not be sent. Please try again later."}',
            )
        else:
            route.fulfill(
                status=200,
                content_type="application/json",
                body='{"status":"notified"}',
            )

    page.route("**/api/cloud-auth/invitation-request", invitation_response)
    page.goto(f"{BASE_URL}/?access=denied&invite=1", wait_until="networkidle")
    dialog = page.get_by_role("dialog", name="Request an invitation")
    expect(dialog).to_be_visible()
    expect(dialog.get_by_text("visitor@example.org")).to_be_visible()
    expect(dialog.get_by_role("link", name="proposed privacy notice, version 1")).to_have_attribute(
        "href", "/privacy"
    )
    invite_button = dialog.get_by_role("button", name="Invite me")
    invite_button.focus()
    expect(invite_button).to_be_focused()
    invite_button.press("Enter")
    expect(dialog.locator(".google-invitation-actions [role='alert']")).to_contain_text(
        "Your request could not be sent. Please try again later."
    )
    expect(dialog.get_by_role("button", name="Invite me")).to_be_enabled()
    dialog.get_by_role("button", name="Invite me").click()
    expect(
        dialog.get_by_text(
            "Glad you're interested! Your request has been sent along to the right person!",
            exact=True,
        )
    ).to_be_visible()
    expect(page.get_by_role("button", name="Invite me!")).to_have_count(0)
    assert posts == [
        {"method": "POST", "body": {}},
        {"method": "POST", "body": {}},
    ]
    page.reload(wait_until="networkidle")
    refreshed_dialog = page.get_by_role("dialog", name="Request an invitation")
    expect(refreshed_dialog).to_be_visible()
    expect(
        refreshed_dialog.get_by_text(
            "Glad you're interested! Your request has been sent along to the right person!",
            exact=True,
        )
    ).to_be_visible()
    expect(page.get_by_role("button", name="Invite me")).to_have_count(0)
    page.set_viewport_size({"width": 1280, "height": 850})
    assert page.evaluate("document.documentElement.scrollWidth <= window.innerWidth")

    member_page = browser.new_page(viewport={"width": 1280, "height": 850})
    allowance = {"remaining_usd": 1.0}
    member_page.route(
        "**/api/cloud-auth/status",
        lambda route: route.fulfill(
            status=200,
            content_type="application/json",
            body=json.dumps(
                {
                    "enabled": True,
                    "ready": True,
                    "authenticated": True,
                    "user": {"email": "member@example.org", "role": "member"},
                    "admin_contact_email": "zetacontinuation@gmail.com",
                    "target": "hosted",
                }
            ),
        ),
    )
    member_page.route(
        "**/api/cloud-research/budget",
        lambda route: route.fulfill(
            status=200,
            content_type="application/json",
            body=json.dumps(
                {
                    "allowance_usd": 1,
                    "estimated_usage_usd": 1 - allowance["remaining_usd"],
                    "held_usd": 0,
                    "reserved_and_estimated_usd": 1 - allowance["remaining_usd"],
                    "remaining_usd": allowance["remaining_usd"],
                    "unknown_provider_attempts": 0,
                }
            ),
        ),
    )
    member_page.goto(BASE_URL, wait_until="networkidle")
    expect(member_page.get_by_role("button", name="Invite me!")).to_have_count(0)
    expect(member_page.get_by_role("button", name="Sign out of Google")).to_be_visible()
    expect(member_page.get_by_role("button", name="Reload me!")).to_have_count(0)
    allowance["remaining_usd"] = 0
    member_page.evaluate("window.dispatchEvent(new Event('focus'))")
    reload_button = member_page.get_by_role("button", name="Reload me!")
    expect(reload_button).to_be_visible()
    expect(reload_button.locator("xpath=..")).to_have_class("home-header-actions")
    with member_page.expect_navigation(wait_until="domcontentloaded"):
        reload_button.click()
    expect(member_page.get_by_role("button", name="Reload me!")).to_be_visible()
    member_page.set_viewport_size({"width": 390, "height": 844})
    expect(member_page.get_by_role("button", name="Reload me!")).to_be_visible()
    assert member_page.evaluate("document.documentElement.scrollWidth <= window.innerWidth")
    browser.close()

print(
    "PASS issue #279 real Chrome desktop/mobile invitation, retry/reload persistence, zero-allowance Reload me!, and member access"
)
