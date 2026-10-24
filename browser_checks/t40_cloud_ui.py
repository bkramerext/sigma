"""Deterministic identity fixtures exercising T40 Home and admin UI in Chrome.

Start the normal local UI (no identity flags), then run this check. Auth API
responses are intercepted in this test process; no simulated admin mode exists
in SIGMA or its CLI.
"""

import json
import os
from urllib.parse import unquote

from playwright.sync_api import expect, sync_playwright

URL = os.environ.get("SIGMA_BROWSER_BASE_URL", "http://127.0.0.1:5173")
API = os.environ.get("SIGMA_BROWSER_API_URL", "http://127.0.0.1:8000")
BOOTSTRAP = "owner@gmail.com"
grants = [
    {
        "kind": "email",
        "value": BOOTSTRAP,
        "role": "admin",
        "active": 1,
        "allowance_usd": 2.0,
        "effective_allowance_usd": 2.0,
    },
    {
        "kind": "domain",
        "value": "reviewers.example",
        "role": "member",
        "active": 1,
        "allowance_usd": 3.0,
        "effective_allowance_usd": 3.0,
    },
]
status = {
    "target": "local",
    "enabled": True,
    "ready": True,
    "authenticated": False,
    "user": None,
    "admin_contact_email": None,
}
admin_requests: list[str] = []


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

            def forward(route):
                route.fulfill(
                    response=route.fetch(
                        url=route.request.url.replace(URL, API),
                        headers={**route.request.headers, "origin": "http://127.0.0.1:5173"},
                    )
                )

            def cloud_status(route):
                route.fulfill(status=200, content_type="application/json", body=json.dumps(status))

            def ai_connection(route):
                if not status["authenticated"]:
                    route.fulfill(
                        status=401,
                        content_type="application/json",
                        body='{"error":"Authentication required."}',
                    )
                else:
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

            def admin_api(route):
                admin_requests.append(route.request.method + " " + route.request.url)
                path = route.request.url.split("/api/cloud-auth/admin/")[-1]
                if path == "grants" and route.request.method == "GET":
                    route.fulfill(
                        status=200,
                        content_type="application/json",
                        body=json.dumps(
                            {
                                "bootstrap_admin": BOOTSTRAP,
                                "grants": grants,
                                "sessions": [
                                    {
                                        "email": BOOTSTRAP,
                                        "status": "active",
                                        "role": "admin",
                                        "allowance_usd": 2.0,
                                        "spending": {
                                            "estimated_usage_usd": 0.25,
                                            "held_usd": 0.10,
                                            "remaining_usd": 1.65,
                                        },
                                    },
                                ],
                            }
                        ),
                    )
                elif path == "grants" and route.request.method == "POST":
                    item = json.loads(route.request.post_data or "{}")
                    grants.append(
                        {
                            **item,
                            "active": 1,
                            "effective_allowance_usd": item["allowance_usd"] or 2.0,
                        }
                    )
                    route.fulfill(status=201, content_type="application/json", body="{}")
                elif path == "grants/updates" and route.request.method == "PUT":
                    for update in json.loads(route.request.post_data or "{}")["updates"]:
                        for grant in grants:
                            if (
                                grant["kind"] == update["kind"]
                                and grant["value"] == update["value"]
                            ):
                                grant.update(
                                    update, effective_allowance_usd=update["allowance_usd"]
                                )
                    route.fulfill(status=200, content_type="application/json", body="{}")
                elif path.startswith("grants/") and route.request.method == "DELETE":
                    kind, value = path.removeprefix("grants/").split("/", 1)
                    value = unquote(value)
                    for grant in grants:
                        if grant["kind"] == kind and grant["value"] == value:
                            grant["active"] = 0
                    route.fulfill(status=200, content_type="application/json", body="{}")
                else:
                    route.fulfill(
                        status=404, content_type="application/json", body='{"error":"Not found"}'
                    )

            page.route("**/api/**", forward)
            page.route("**/api/cloud-auth/status", cloud_status)
            page.route("**/api/cloud-auth/admin/**", admin_api)
            page.route(
                "**/api/cloud-auth/login",
                lambda route: route.fulfill(status=200, body="OAuth fixture route"),
            )
            page.route(
                "**/api/cloud-auth/logout", lambda route: route.fulfill(status=200, body="{}")
            )
            page.route("**/api/ai/connection*", ai_connection)
            page.route(
                "**/api/projects/inspect*",
                lambda route: route.fulfill(
                    status=401,
                    content_type="application/json",
                    body='{"error":"Authentication required."}',
                ),
            )

            # Unauthenticated Home retains its existing projects and pills, with
            # no route to admin functions and no automatic external OAuth call.
            page.goto(URL, wait_until="networkidle")
            expect(
                page.get_by_role(
                    "heading", name="Sign in with approved Gmail account to access projects."
                )
            ).to_be_visible()
            expect(page.locator(".request-toast")).to_have_count(0)
            expect(page.get_by_role("link", name="Administrator Settings")).to_have_count(0)
            google = page.get_by_role("button", name="Open Google sign-in")
            expect(google).to_contain_text("Google sign-in")
            assert "Sign in" not in google.inner_text()
            expect(page.locator(".home-topline .api-connection > summary")).to_be_visible()
            expect(page.locator(".home-topline .api-connection > summary")).to_contain_text(
                "Google sign-in required"
            )
            expect(page.locator(".home-topline .api-connection > summary")).to_have_attribute(
                "aria-disabled", "true"
            )
            page.locator(".home-topline .api-connection > summary").click()
            expect(page.locator(".connection-details")).to_have_count(0)
            expect(page.locator(".home-page .home-art-credit")).to_contain_text(
                "By Brian Kramer, ChatGPT & Codex"
            )
            assert (
                page.locator(".home-page .home-art-credit").evaluate(
                    "element => getComputedStyle(element).color"
                )
                == "rgb(214, 161, 110)"
            )
            assert page.get_by_role("link", name="Explore Demo").count() == 0
            assert page.get_by_text("owner@gmail.com", exact=True).count() == 0
            page.evaluate("fetch('/api/projects/inspect?path=projects%2Frh.sigma')")
            expect(
                page.locator(".request-toast").filter(has_text="Authentication required.")
            ).to_be_visible()
            page.get_by_role("button", name="Dismiss request error").click()
            for width, height in ((1440, 900), (390, 844)):
                page.set_viewport_size({"width": width, "height": height})
                expect(
                    page.get_by_role(
                        "heading",
                        name="Sign in with approved Gmail account to access projects.",
                    )
                ).to_be_visible()
                assert page.evaluate("document.documentElement.scrollWidth <= innerWidth")
                font_size = page.locator(".home-cloud-prompt h1").evaluate(
                    "element => parseFloat(getComputedStyle(element).fontSize)"
                )
                assert font_size <= 24, (width, font_size)
                page.screenshot(path=f"/tmp/sigma-t43-signin-{width}.png", full_page=True)
                google.click()
                google_panel = page.locator(".google-connection-details")
                expect(google_panel).to_be_visible()
                assert (
                    google_panel.evaluate("element => getComputedStyle(element).position")
                    == "fixed"
                )
                assert google_panel.evaluate(
                    "element => { const r = element.getBoundingClientRect(); return r.left >= 0 && r.right <= innerWidth; }"
                )
                page.keyboard.press("Escape")
                expect(google).to_be_focused()
            page.set_viewport_size({"width": 1440, "height": 900})
            google.click()
            account = page.get_by_role("dialog", name="Connect your Google account")
            expect(account).to_be_visible()
            assert account.evaluate("element => getComputedStyle(element).position") == "fixed"
            assert account.evaluate("element => element.getBoundingClientRect().width") <= 300
            expect(account.get_by_text("Local SIGMA", exact=True)).to_be_visible()
            page.keyboard.press("Escape")
            expect(google).to_be_focused()
            google.click()
            account = page.get_by_role("dialog", name="Connect your Google account")
            account.get_by_role("link", name="Continue with Google").click()
            expect(page.get_by_text("OAuth fixture route")).to_be_visible()

            # Admin status is supplied by deterministic API fixture only.
            status.update(authenticated=True, user={"email": BOOTSTRAP, "role": "admin"})
            page.goto(URL, wait_until="networkidle")
            expect(page.get_by_role("link", name="Administrator Settings")).to_be_visible()
            expect(page.locator(".home-topline .project-google-signin")).to_contain_text(
                "Signed in"
            )
            expect(page.get_by_text(BOOTSTRAP, exact=True)).to_have_count(0)
            page.locator(".home-topline .project-google-signin").click()
            account = page.get_by_role("dialog", name="Connect your Google account")
            expect(account.get_by_text(BOOTSTRAP, exact=True)).to_be_visible()
            expect(account.get_by_role("button", name="Sign out", exact=True)).to_be_visible()
            page.keyboard.press("Escape")
            expect(page.locator(".home-topline .project-google-signin")).to_be_focused()

            page.get_by_role("link", name="Administrator Settings").click()
            dialog = page.get_by_role("dialog", name="Administrator Settings")
            expect(dialog).to_be_visible()
            expect(dialog.get_by_role("tab", name="Access Management")).to_be_visible()
            expect(dialog.get_by_role("tab", name="Account usage")).to_be_visible()
            expect(dialog.get_by_text("Local SIGMA access rules")).to_be_visible()
            expect(dialog.get_by_text("Built-in administrator: " + BOOTSTRAP)).to_be_visible()
            expect(dialog.get_by_role("heading", name="Authorized users")).to_be_visible()
            access_tab = dialog.get_by_role("tab", name="Access Management")
            usage_tab = dialog.get_by_role("tab", name="Account usage")
            access_tab.focus()
            page.keyboard.press("ArrowRight")
            expect(usage_tab).to_have_attribute("aria-selected", "true")
            expect(usage_tab).to_be_focused()
            page.keyboard.press("ArrowLeft")
            expect(access_tab).to_have_attribute("aria-selected", "true")
            expect(access_tab).to_be_focused()
            expect(dialog.get_by_role("tab", name="Account usage")).to_have_attribute(
                "aria-selected", "false"
            )
            expect(dialog.locator(".admin-usage-table")).to_be_hidden()
            expect(dialog.get_by_role("button", name="Cancel")).to_have_count(0)
            for heading in ("Email / Domain", "Role", "ChatGPT Allowance", "Actions"):
                expect(dialog.get_by_role("columnheader", name=heading)).to_be_visible()
            ordered = dialog.locator(".admin-grants-table tbody tr:not(.admin-add-row)")
            assert ordered.evaluate_all(
                "rows => { const values = rows.map(row => row.querySelector('th').innerText.split('\\n')[0]); return values.length === 2 && values.every((value, index) => index === 0 || values[index - 1].localeCompare(value, undefined, {sensitivity: 'base'}) <= 0); }"
            )
            dialog.locator(".admin-grants-table").get_by_role(
                "button", name="New", exact=True
            ).click()
            row = dialog.locator(".admin-new-entry-row")
            row.get_by_label("New email address").fill("reviewer@example.org")
            row.get_by_label("New ChatGPT allowance").fill("4.50")
            row.get_by_role("button", name="Add", exact=True).click()
            added = dialog.locator(".admin-grants-table tbody tr").filter(
                has_text="reviewer@example.org"
            )
            expect(added).to_be_visible()
            added.get_by_label("Role for reviewer@example.org").select_option("admin")
            added.get_by_label("ChatGPT allowance for reviewer@example.org").fill("5.25")
            dialog.get_by_role("button", name="Save Updates").click()
            expect(dialog.get_by_role("button", name="Save Updates")).to_have_count(0)
            page.once("dialog", lambda confirm: confirm.accept())
            added.get_by_role("button", name="Revoke", exact=True).click()
            expect(added).to_contain_text("Revoked")
            dialog.get_by_role("tab", name="Account usage").click()
            expect(dialog.locator(".admin-usage-table")).to_be_visible()
            expect(dialog.locator(".admin-usage-table")).to_contain_text(BOOTSTRAP)
            expect(dialog.locator(".admin-grants-table")).to_be_hidden()
            dialog.get_by_role("tab", name="Access Management").click()
            expect(dialog.get_by_role("button", name="New", exact=True)).to_be_visible()
            dialog.get_by_role("button", name="Close", exact=True).click()

            grants.clear()
            page.get_by_role("link", name="Administrator Settings").click()
            dialog = page.get_by_role("dialog", name="Administrator Settings")
            expect(dialog.locator(".admin-empty-row")).to_contain_text(
                "No authorization entries yet."
            )
            new_row = dialog.locator(".admin-add-row")
            expect(new_row.get_by_role("button", name="New", exact=True)).to_be_visible()
            assert new_row.locator("th").evaluate(
                "cell => cell === cell.parentElement.firstElementChild"
            )
            dialog.get_by_role("button", name="Close", exact=True).click()

            for width, height in ((1440, 900), (390, 844)):
                page.set_viewport_size({"width": width, "height": height})
                assert page.evaluate("document.documentElement.scrollWidth <= innerWidth"), width
                google_box = page.locator(".home-topline .project-google-signin").bounding_box()
                chatgpt_box = page.locator(".home-topline .api-connection > summary").bounding_box()
                assert google_box and chatgpt_box
                assert abs(google_box["height"] - chatgpt_box["height"]) <= 1, (
                    width,
                    google_box,
                    chatgpt_box,
                )
                page.screenshot(path=f"/tmp/sigma-t40-admin-home-{width}.png", full_page=True)
                page.get_by_role("link", name="Administrator Settings").click()
                dialog = page.get_by_role("dialog", name="Administrator Settings")
                expect(dialog).to_be_visible()
                expect(dialog.locator(".admin-table-scroll").first).to_be_visible()
                page.screenshot(path=f"/tmp/sigma-t40-admin-dialog-{width}.png", full_page=True)
                dialog.get_by_role("button", name="Close", exact=True).click()

            # An authenticated ordinary member never sees the admin link.
            status.update(user={"email": "member@example.org", "role": "member"})
            member = browser.new_page(viewport={"width": 390, "height": 844})
            member.route("**/api/**", forward)
            member.route("**/api/cloud-auth/status", cloud_status)
            member.goto(URL, wait_until="networkidle")
            expect(member.locator(".home-topline .project-google-signin")).to_contain_text(
                "Signed in"
            )
            expect(member.get_by_role("link", name="Administrator Settings")).to_have_count(0)
            expect(member.get_by_text("member@example.org", exact=True)).to_have_count(0)
            assert not errors, errors
            assert admin_requests and all("127.0.0.1" in request for request in admin_requests)
            print(
                "T40 Chrome: deterministic signed-out/admin/member states, account dialog, admin Add/edit/save/Revoke, artwork credit and desktop/mobile layouts PASS"
            )
        finally:
            browser.close()


if __name__ == "__main__":
    main()
