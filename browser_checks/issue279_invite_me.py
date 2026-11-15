"""Real-Chrome acceptance for issue #279's guest invitation pill flow."""

import json
import os
import re
from urllib.parse import urlsplit

from playwright.sync_api import expect, sync_playwright

BASE_URL = os.environ.get("SIGMA_BROWSER_BASE_URL", "http://127.0.0.1:5173")


posts: list[dict] = []


def guest_status(route):
    route.fulfill(
        status=200,
        content_type="application/json",
        body=json.dumps(
            {
                "enabled": True,
                "ready": True,
                "authenticated": True,
                "user": {"email": "new-user@example.org", "role": "guest"},
                "account": {
                    "identity": {"email": "new-user@example.org", "verified": True},
                    "access": {"status": "uninvited", "role": "guest"},
                    "workspace": {"available": True, "id": "guest-fixture"},
                    "model_access": {"mode": "sponsored", "connection": "unavailable"},
                    "sponsorship": {"eligible": False, "forced": False},
                    "invitation_welcome_pending": False,
                    "invitation_status": "pending" if posts else None,
                },
                "admin_contact_email": "zetacontinuation@gmail.com",
                "target": "local",
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
    page.route("**/api/cloud-auth/status**", guest_status)

    def invitation_response(route):
        posts.append({"method": route.request.method, "body": route.request.post_data_json})
        # The durable request is accepted even when its admin email cannot be
        # delivered; the UI must acknowledge the saved request instead of
        # asking the user to repeat an action that already succeeded.
        route.fulfill(
            status=200,
            content_type="application/json",
            body='{"status":"pending","duplicate":false}',
        )

    def guest_api(route):
        path = urlsplit(route.request.url).path
        if path == "/api/cloud-auth/status":
            guest_status(route)
        elif path == "/api/cloud-auth/invitation-request":
            invitation_response(route)
        elif path in {"/api/projects/recent", "/api/projects/samples"}:
            route.fulfill(status=200, content_type="application/json", body='{"projects":[]}')
        elif path == "/api/ai/connection":
            route.fulfill(
                status=200,
                content_type="application/json",
                body=json.dumps(
                    {
                        "mode": "chatgpt",
                        "status": "disconnected",
                        "label": "Connect to ChatGPT",
                        "accounts": [],
                        "active_account": None,
                    }
                ),
            )
        else:
            route.fulfill(status=200, content_type="application/json", body="{}")

    page.unroute("**/api/cloud-auth/status**", guest_status)
    page.route("**/api/**", guest_api)
    page.goto(BASE_URL, wait_until="networkidle")
    expect(page.get_by_role("heading", name="Projects")).to_be_visible()
    expect(page.get_by_role("button", name="Sign out of Google")).to_be_visible()
    invite_pill = page.get_by_role("button", name="Invite me!")
    expect(invite_pill).to_be_visible()
    invite_pill.click()
    dialog = page.get_by_role("dialog", name="Request an invitation")
    expect(dialog).to_be_visible()
    expect(dialog.get_by_role("link", name="Privacy Notice")).to_have_attribute(
        "href", re.compile(r"^/privacy")
    )
    dialog.get_by_role("button", name="Invite me").click()
    expect(dialog.locator("[role='status']")).to_contain_text(
        "Your invitation request is recorded and awaiting administrator review."
    )
    expect(dialog.locator("[role='alert']")).to_have_count(0)
    expect(page.get_by_role("button", name="Invite me!")).to_have_count(0)
    assert posts == [{"method": "POST", "body": {}}]
    page.reload(wait_until="networkidle")
    status = page.evaluate("async () => (await (await fetch('/api/cloud-auth/status')).json())")
    assert status["account"]["invitation_status"] == "pending", status
    expect(page.get_by_role("button", name="Invite me!")).to_have_count(0)
    page.set_viewport_size({"width": 1280, "height": 850})
    assert page.evaluate("document.documentElement.scrollWidth <= window.innerWidth")

    member_page = browser.new_page(viewport={"width": 1280, "height": 850})
    allowance = {"remaining_usd": 1.0}
    reload_posts: list[dict] = []
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
                    "account": {
                        "model_access": {"mode": "sponsored", "connection": "connected"},
                        "sponsorship": {"eligible": True, "forced": False},
                    },
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
    member_page.route(
        "**/api/cloud-auth/welcome",
        lambda route: route.fulfill(
            status=200, content_type="application/json", body='{"seen":true}'
        ),
    )
    member_page.route(
        "**/api/cloud-auth/invitation-request",
        lambda route: (
            reload_posts.append(route.request.post_data_json)
            or route.fulfill(
                status=200,
                content_type="application/json",
                body='{"status":"notified","duplicate":false}',
            )
        ),
    )
    member_page.goto(BASE_URL, wait_until="networkidle")
    member_welcome = member_page.locator("#invitation-welcome-dialog")
    if member_welcome.count() and member_welcome.is_visible():
        member_welcome.get_by_role("button", name="Let's get started").click()
        expect(member_welcome).to_have_count(0)
    expect(member_page.get_by_role("button", name="Invite me!")).to_have_count(0)
    expect(member_page.get_by_role("button", name="Sign out of Google")).to_be_visible()
    expect(member_page.get_by_role("button", name="Reload me!")).to_have_count(0)
    allowance["remaining_usd"] = 0.05
    member_page.evaluate("window.dispatchEvent(new Event('focus'))")
    expect(member_page.locator(".sponsored-allowance-inline")).to_have_text("0.05")
    expect(member_page.get_by_role("button", name="Reload me!")).to_have_count(0)
    allowance["remaining_usd"] = 0.04
    member_page.evaluate("window.dispatchEvent(new Event('focus'))")
    expect(member_page.locator(".sponsored-allowance-inline")).to_have_text("0.04")
    reload_button = member_page.get_by_role("button", name="Reload me!")
    expect(reload_button).to_be_visible()
    expect(reload_button.locator("xpath=..")).to_have_class("identity-pill-stack")
    reload_button.click()
    expect(member_page.get_by_text("Reload requested", exact=True)).to_be_visible()
    assert reload_posts == [{"request_type": "reload"}]
    member_page.set_viewport_size({"width": 390, "height": 844})
    expect(member_page.get_by_text("Reload requested", exact=True)).to_be_visible()
    assert member_page.evaluate("document.documentElement.scrollWidth <= window.innerWidth")
    browser.close()

print(
    "PASS issue #279 real Chrome invitation, saved-request acknowledgement, reload persistence, Reload me! threshold below $0.05, and member access"
)
