"""Chrome acceptance for T43.1; OAuth and provider actions are never invoked live.

The first browser context uses the actual local cloud-auth status endpoint. Its
Google setup state is not intercepted. Other UI data is deterministic so legacy
project categories and connected-account popup states can be exercised safely.
"""

import json
import os
from urllib.parse import urlsplit

from playwright.sync_api import expect, sync_playwright

URL = os.environ.get("SIGMA_BROWSER_BASE_URL", "http://127.0.0.1:5190")
API = os.environ.get("SIGMA_BROWSER_API_URL", "http://127.0.0.1:8014")

recent = {
    "projects": [
        {
            "id": "legacy-invalid-type",
            "path": "projects/legacy-invalid-type.sigma",
            "title": "Legacy project with an unmapped category",
            "investigation_type": "obsolete_domain",
            "strategy_count": 2,
            "difficulty": "medium",
            "available": True,
            "error": None,
        },
        {
            "id": "biology-review",
            "path": "projects/biology-review.sigma",
            "title": "Biology review",
            "investigation_type": "biology",
            "strategy_count": 1,
            "difficulty": "easy",
            "available": True,
            "error": None,
        },
    ]
}

connected = {
    "mode": "chatgpt",
    "status": "connected",
    "label": "Connected",
    "guidance": "Using ChatGPT plan allowance or credits. Account permission is checked; inference and remaining usage are not verified.",
    "checked_at": "2026-10-23T12:00:00Z",
    "ttl_seconds": 60,
    "account_label": "reviewer@gmail.com",
    "active_account": "account-1",
    "accounts": [
        {"id": "account-1", "label": "reviewer@gmail.com"},
        {"id": "account-2", "label": "second@gmail.com"},
    ],
}


def main() -> None:
    with sync_playwright() as playwright:
        browser = playwright.chromium.launch(
            executable_path=os.environ.get(
                "SIGMA_BROWSER_EXECUTABLE",
                "/Applications/Google Chrome.app/Contents/MacOS/Google Chrome",
            ),
            headless=True,
        )
        try:
            page = browser.new_page(viewport={"width": 1440, "height": 900})
            errors: list[str] = []
            page.on("pageerror", lambda error: errors.append(str(error)))

            def deterministic_home_data(route):
                path = urlsplit(route.request.url).path
                if path == "/api/projects/recent":
                    route.fulfill(
                        status=200, content_type="application/json", body=json.dumps(recent)
                    )
                elif path == "/api/ai/connection":
                    route.fulfill(
                        status=200,
                        content_type="application/json",
                        body=json.dumps(
                            {
                                "mode": "chatgpt",
                                "status": "disconnected",
                                "label": "Connect AI",
                                "guidance": "Manual research is always available.",
                                "checked_at": None,
                                "ttl_seconds": 60,
                                "accounts": [],
                                "active_account": None,
                            }
                        ),
                    )
                else:
                    route.continue_()

            page.route("**/api/**", deterministic_home_data)
            page.goto(URL)
            expect(page.get_by_role("heading", name="Projects")).to_be_visible()
            status_response = page.request.get(API + "/api/cloud-auth/status")
            assert status_response.ok
            real_status = status_response.json()
            assert real_status["enabled"] is False, real_status
            assert "SIGMA_CLOUD_BOOTSTRAP_ADMIN_EMAIL" in real_status["local_setup_missing"], (
                real_status
            )

            google = page.locator(".home-topline .project-google-signin")
            expect(google).to_be_enabled()
            expect(google).to_have_text("Google sign-in setup required")
            expect(google).to_have_attribute("aria-label", "Google sign-in setup required")
            expect(google).to_have_attribute("data-tooltip-disabled", "")
            expect(google).not_to_have_attribute("data-tooltip")
            google.click()
            setup = page.get_by_role("dialog", name="Google sign-in setup required")
            expect(setup).to_be_visible()
            expect(setup.locator(".google-setup-missing code")).to_contain_text(
                "SIGMA_CLOUD_BOOTSTRAP_ADMIN_EMAIL"
            )
            expect(setup.get_by_role("link", name="Continue with Google")).to_have_count(0)
            expect(setup).to_contain_text("source ~/.bashrc")
            page.keyboard.press("Escape")
            expect(setup).to_have_count(0)
            expect(google).to_be_focused()
            expect(page.get_by_role("tooltip")).to_have_count(0)

            for width, height in ((1440, 900), (390, 844)):
                page.set_viewport_size({"width": width, "height": height})
                google.hover()
                page.wait_for_timeout(750)
                expect(page.get_by_role("tooltip")).to_have_count(0)
                google.click()
                setup = page.get_by_role("dialog", name="Google sign-in setup required")
                expect(setup).to_be_visible()
                setup_box = setup.bounding_box()
                assert setup_box is not None
                assert setup_box["x"] >= 0 and setup_box["x"] + setup_box["width"] <= width, (
                    width,
                    setup_box,
                )
                page.screenshot(path=f"/tmp/sigma-t43-1-google-setup-{width}.png", full_page=True)
                page.keyboard.press("Escape")
                credit = page.locator(".home-art-credit")
                expect(credit).to_have_text("By Brian Kramer, ChatGPT & CodexOctober 2026")
                box = credit.bounding_box()
                assert box is not None
                assert abs(width - (box["x"] + box["width"]) - 5) <= 1, (width, box)
                assert abs(height - (box["y"] + box["height"]) - 5) <= 1, (height, box)
                assert credit.evaluate("e => getComputedStyle(e).fontVariant") == "normal"
                page.screenshot(path=f"/tmp/sigma-t43-1-home-{width}.png", full_page=True)

            page.get_by_role("tab", name="Recent", exact=True).click()
            groups = page.locator("#recent-panel .recent-type-group")
            expect(groups).to_have_count(2)
            expect(page.locator("#recent-panel")).to_contain_text("Other")
            expect(page.locator("#recent-panel")).to_contain_text("Biology")
            expect(page.locator("#recent-panel")).not_to_contain_text("Unavailable")
            page.screenshot(path="/tmp/sigma-t43-1-recent-1440.png", full_page=True)
            page.set_viewport_size({"width": 390, "height": 844})
            for group in groups.all():
                box = group.locator("summary").bounding_box()
                assert box is not None and box["x"] >= 0 and box["x"] + box["width"] <= 390, (box,)
            page.screenshot(path="/tmp/sigma-t43-1-recent-390.png", full_page=True)
            page.get_by_role("tab", name="Samples", exact=True).click()

            # Deterministic signed-in view for the ChatGPT Connected popover.
            popup_page = browser.new_page(viewport={"width": 390, "height": 844})
            popup_errors: list[str] = []
            popup_page.on("pageerror", lambda error: popup_errors.append(str(error)))

            def connected_data(route):
                path = urlsplit(route.request.url).path
                if path == "/api/cloud-auth/status":
                    route.fulfill(
                        status=200,
                        content_type="application/json",
                        body=json.dumps(
                            {
                                "target": "local",
                                "enabled": True,
                                "ready": True,
                                "authenticated": True,
                                "user": {"email": "reviewer@gmail.com", "role": "member"},
                                "admin_contact_email": None,
                                "local_setup_missing": [],
                            }
                        ),
                    )
                elif path == "/api/ai/connection":
                    route.fulfill(
                        status=200, content_type="application/json", body=json.dumps(connected)
                    )
                elif path == "/api/projects/recent":
                    route.fulfill(
                        status=200, content_type="application/json", body='{"projects":[]}'
                    )
                else:
                    route.continue_()

            popup_page.route("**/api/**", connected_data)
            popup_page.goto(URL)
            trigger = popup_page.locator(".home-topline .project-chatgpt-signin summary")
            expect(trigger).to_contain_text("ChatGPT connected")
            expect(trigger).to_have_attribute("data-tooltip-disabled", "")
            expect(trigger).not_to_have_attribute("title")
            expect(trigger).not_to_have_attribute("data-tooltip")
            assert "connection-active" not in trigger.locator(".connection-dot").get_attribute("class")
            trigger.hover()
            popup_page.wait_for_timeout(750)
            expect(popup_page.get_by_role("tooltip")).to_have_count(0)
            trigger.click()
            dialog = popup_page.get_by_role("dialog", name="AI connection settings")
            expect(dialog).to_be_visible()
            expect(dialog.get_by_text("Using ChatGPT plan", exact=True)).to_have_count(0)
            expect(dialog).to_contain_text("plan allowance or credits")
            expect(dialog).to_contain_text("remaining usage are not verified")
            expect(dialog.get_by_label("Switch ChatGPT account")).to_have_count(0)
            expect(dialog.locator("select")).to_have_count(0)
            for action in (
                "Manage usage",
                "Disconnect",
                "Connect another account",
                "Retry connection",
            ):
                item = dialog.get_by_role(
                    "link" if action == "Manage usage" else "button", name=action
                )
                expect(item).to_be_visible()
                expect(item).to_have_class("connection-text-action")
            dialog.get_by_text("API key option").click()
            api_key = dialog.get_by_role("button", name="Separately billed API Key")
            expect(api_key).to_be_visible()
            expect(api_key).to_have_class("connection-text-action")
            popup_page.screenshot(path="/tmp/sigma-t43-1-connected-popup-390.png", full_page=True)
            popup_page.keyboard.press("Escape")

            # Keep the sign-in attempt local and deterministic; verify Cancel sign-in styling.
            disconnected_page = browser.new_page(viewport={"width": 1280, "height": 800})
            disconnected_page.route(
                "**/api/cloud-auth/status",
                lambda route: route.fulfill(
                    status=200,
                    content_type="application/json",
                    body=json.dumps(
                        {
                            "target": "local",
                            "enabled": True,
                            "ready": True,
                            "authenticated": True,
                            "user": {"email": "reviewer@gmail.com", "role": "member"},
                            "admin_contact_email": None,
                        }
                    ),
                ),
            )
            disconnected_page.route(
                "**/api/ai/connection**",
                lambda route: route.fulfill(
                    status=200,
                    content_type="application/json",
                    body=json.dumps(
                        {
                            "mode": "chatgpt",
                            "status": "disconnected",
                            "label": "Connect AI",
                            "guidance": "Manual research is always available.",
                            "checked_at": None,
                            "ttl_seconds": 60,
                            "accounts": [],
                            "active_account": None,
                        }
                    ),
                ),
            )
            disconnected_page.route(
                "**/api/ai/auth/begin",
                lambda route: route.fulfill(
                    status=200,
                    content_type="application/json",
                    body='{"id":"fixture-attempt","authorization_url":"/api/ai/auth/open/fixture-attempt"}',
                ),
            )
            disconnected_page.route(
                "**/api/ai/auth/attempt/fixture-attempt",
                lambda route: route.fulfill(
                    status=200, content_type="application/json", body='{"status":"connecting"}'
                ),
            )
            disconnected_page.route(
                "**/api/ai/auth/open/fixture-attempt",
                lambda route: route.fulfill(status=200, body="Fixture handoff"),
            )
            disconnected_page.route(
                "**/api/ai/auth/cancel/fixture-attempt",
                lambda route: route.fulfill(status=204, body=""),
            )
            disconnected_page.goto(URL)
            disconnected_page.locator(".home-topline .project-chatgpt-signin summary").click()
            disconnected_dialog = disconnected_page.get_by_role(
                "dialog", name="AI connection settings"
            )
            disconnected_dialog.get_by_role("button", name="Continue with ChatGPT").click()
            cancel = disconnected_dialog.get_by_role("button", name="Cancel sign-in")
            expect(cancel).to_be_visible()
            expect(cancel).to_have_class("connection-text-action")
            cancel.click()

            assert not errors, errors
            assert not popup_errors, popup_errors
            print(
                "PASS T43.1 Chrome: real disabled local auth diagnosis, responsive setup/credits, "
                "legacy Recent category recovery, connected ChatGPT actions, and cancel styling"
            )
        finally:
            browser.close()


if __name__ == "__main__":
    main()
