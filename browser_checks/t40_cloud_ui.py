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
            google = page.get_by_role("link", name="Sign in with Google")
            expect(google).to_have_text("Sign in with Google")
            expect(google).to_have_attribute("href", "/api/cloud-auth/login")
            about_home = page.locator(".home-topline .home-about-button")
            about_home_box = about_home.bounding_box()
            google_home_box = google.bounding_box()
            assert about_home_box and google_home_box
            assert about_home_box["x"] + about_home_box["width"] <= google_home_box["x"]
            expect(page.locator(".home-topline .api-connection > summary")).to_be_visible()
            expect(page.locator(".home-topline .api-connection > summary")).to_have_text(
                "Connect to ChatGPT"
            )
            expect(page.locator(".home-topline .api-connection > summary")).to_have_attribute(
                "aria-disabled", "true"
            )
            page.locator(".home-topline .api-connection > summary").click()
            expect(page.locator(".connection-details")).to_have_count(0)
            expect(page.locator(".home-page .home-art-credit")).to_contain_text(
                "Brian Kramer& OpenAI Models"
            )
            expect(page.locator(".home-page .home-art-credit time")).to_have_count(0)
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
            for width, height in (
                (1440, 900),
                (700, 850),
                (600, 850),
                (520, 844),
                (390, 844),
                (360, 740),
                (320, 700),
            ):
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
                prompt_box = page.locator(".home-cloud-prompt").bounding_box()
                assert prompt_box is not None and prompt_box["width"] <= 430, prompt_box
                assert abs(prompt_box["x"] - prompt_box["y"]) <= 1, prompt_box
                about_box = about_home.bounding_box()
                google_box = google.bounding_box()
                chatgpt_box = page.locator(".home-topline .api-connection > summary").bounding_box()
                assert about_box and google_box and chatgpt_box
                assert about_box["x"] + about_box["width"] <= google_box["x"], (
                    width, about_box, google_box
                )
                for pill_box in (about_box, google_box, chatgpt_box):
                    overlaps = (
                        prompt_box["x"] < pill_box["x"] + pill_box["width"]
                        and prompt_box["x"] + prompt_box["width"] > pill_box["x"]
                        and prompt_box["y"] < pill_box["y"] + pill_box["height"]
                        and prompt_box["y"] + prompt_box["height"] > pill_box["y"]
                    )
                    assert not overlaps, (width, prompt_box, pill_box)
                page.screenshot(path=f"/tmp/sigma-t43-signin-{width}.png", full_page=True)
                expect(page.locator(".google-connection-details")).to_have_count(0)
            page.set_viewport_size({"width": 1440, "height": 900})
            google.click()
            expect(page.get_by_text("OAuth fixture route")).to_be_visible()
            expect(page.get_by_role("dialog")).to_have_count(0)

            # Admin status is supplied by deterministic API fixture only.
            status.update(authenticated=True, user={"email": BOOTSTRAP, "role": "admin"})
            page.goto(URL, wait_until="networkidle")
            expect(page.get_by_role("link", name="Administrator Settings")).to_be_visible()
            expect(page.locator(".home-topline .project-google-signin")).to_have_text(
                "Google account connected"
            )
            expect(page.locator(".home-topline .project-google-signin .connection-dot")).to_have_css(
                "background-color", "rgb(117, 177, 140)"
            )
            assert page.locator(".home-topline .project-google-signin .connection-dot").evaluate(
                "e => getComputedStyle(e).animationName"
            ) == "none"
            expect(page.get_by_text(BOOTSTRAP, exact=True)).to_have_count(0)
            # The Home account pills keep the same padding and height through
            # the former 700px breakpoint, sit over the artwork, and remain
            # above (rather than on top of) the Projects area.
            for width, height in ((1440, 900), (800, 800), (700, 800), (600, 800), (520, 800), (390, 844), (360, 740)):
                page.set_viewport_size({"width": width, "height": height})
                google_home = page.locator(".home-topline .project-google-signin")
                chatgpt_home = page.locator(".home-topline .api-connection > summary")
                google_box = google_home.bounding_box()
                chatgpt_box = chatgpt_home.bounding_box()
                projects_box = page.locator(".home-projects").bounding_box()
                assert google_box and chatgpt_box and projects_box, width
                assert abs(google_box["height"] - 34) <= 1, (width, google_box)
                assert abs(chatgpt_box["height"] - 34) <= 1, (width, chatgpt_box)
                assert google_box["x"] >= 0 and chatgpt_box["x"] >= 0, (width, google_box, chatgpt_box)
                assert google_box["x"] + google_box["width"] <= width, (width, google_box)
                assert chatgpt_box["x"] + chatgpt_box["width"] <= width, (width, chatgpt_box)
                assert chatgpt_box["y"] - (google_box["y"] + google_box["height"]) >= 8, (
                    width, google_box, chatgpt_box
                )
                assert projects_box["y"] >= max(
                    google_box["y"] + google_box["height"],
                    chatgpt_box["y"] + chatgpt_box["height"],
                ) - 1, (width, projects_box, google_box, chatgpt_box)
                admin_link = page.locator(".administrator-settings-link")
                if admin_link.count():
                    about_admin = page.locator(".home-about-button")
                    admin_box = admin_link.bounding_box()
                    about_admin_box = about_admin.bounding_box()
                    assert admin_box and about_admin_box
                    assert about_admin_box["x"] + about_admin_box["width"] <= google_box["x"], (
                        width, about_admin_box, google_box
                    )
                    assert admin_box["y"] - (about_admin_box["y"] + about_admin_box["height"]) >= 8, (
                        width, about_admin_box, admin_box
                    )
                    for pill_box in (google_box, chatgpt_box):
                        overlaps = (
                            admin_box["x"] < pill_box["x"] + pill_box["width"]
                            and admin_box["x"] + admin_box["width"] > pill_box["x"]
                            and admin_box["y"] < pill_box["y"] + pill_box["height"]
                            and admin_box["y"] + admin_box["height"] > pill_box["y"]
                        )
                        assert not overlaps, (width, admin_box, pill_box)
                    assert projects_box["y"] >= admin_box["y"] + admin_box["height"] - 1, (
                        width, admin_box, projects_box
                    )
                assert page.evaluate("document.documentElement.scrollWidth <= innerWidth"), width
                google_styles = google_home.evaluate(
                    "e => { const s = getComputedStyle(e); return [s.padding, s.fontSize, s.minHeight, s.gap]; }"
                )
                chatgpt_styles = chatgpt_home.evaluate(
                    "e => { const s = getComputedStyle(e); return [s.padding, s.fontSize, s.minHeight, s.gap]; }"
                )
                assert google_styles == chatgpt_styles, (width, google_styles, chatgpt_styles)
                if width in (700, 600, 390):
                    page.screenshot(path=f"/tmp/sigma-t40-home-header-{width}.png", full_page=True)
            page.set_viewport_size({"width": 1440, "height": 900})
            page.locator(".home-topline .project-google-signin").click()
            account = page.get_by_role("dialog", name="Google account")
            expect(account.get_by_text(BOOTSTRAP, exact=True)).to_be_visible()
            expect(account.get_by_role("button", name="Use another Google account")).to_have_count(0)
            expect(account.get_by_role("heading", name="Connect your Google account")).to_have_count(0)
            email = account.locator(".google-account-email")
            initial_width = account.evaluate("e => e.getBoundingClientRect().width")
            assert account.evaluate("e => getComputedStyle(e).padding") == "12px"
            assert email.evaluate("e => getComputedStyle(e).color") == "rgb(240, 204, 160)"
            assert email.evaluate("e => getComputedStyle(e).fontSize") == "15px"
            email.evaluate("e => { e.textContent = 'alexandria.long.research.account@example-domain.test'; }")
            expanded_width = account.evaluate("e => e.getBoundingClientRect().width")
            assert expanded_width > initial_width and expanded_width <= 360, (
                initial_width,
                expanded_width,
            )
            assert email.evaluate("e => e.scrollWidth <= e.clientWidth")
            expect(account.get_by_role("button", name="Sign out", exact=True)).to_be_visible()
            page.keyboard.press("Escape")
            expect(page.locator(".home-topline .project-google-signin")).to_be_focused()

            page.get_by_role("link", name="Administrator Settings").click()
            dialog = page.get_by_role("dialog", name="Administrator Settings")
            expect(dialog).to_be_visible()
            expect(dialog.get_by_role("tab", name="Access Management")).to_be_visible()
            expect(dialog.get_by_role("tab", name="Account usage")).to_be_visible()
            expect(dialog.get_by_text("Local SIGMA access rules")).to_have_count(0)
            expect(dialog.get_by_text("Built-in administrator: " + BOOTSTRAP)).to_be_visible()
            expect(dialog.get_by_role("heading", name="Authorized users")).to_be_visible()
            dialog_box = dialog.bounding_box()
            assert dialog_box
            assert abs(dialog_box["width"] - 705) <= 1, dialog_box
            access_tab = dialog.get_by_role("tab", name="Access Management")
            usage_tab = dialog.get_by_role("tab", name="Account usage")
            access_tab.focus()
            page.keyboard.press("ArrowRight")
            expect(usage_tab).to_have_attribute("aria-selected", "true")
            expect(usage_tab).to_be_focused()
            usage_box = dialog.bounding_box()
            assert usage_box and all(abs(dialog_box[key] - usage_box[key]) <= 1 for key in ("x", "y", "width", "height")), (dialog_box, usage_box)
            page.keyboard.press("ArrowLeft")
            expect(access_tab).to_have_attribute("aria-selected", "true")
            expect(access_tab).to_be_focused()
            access_box = dialog.bounding_box()
            assert access_box and all(abs(dialog_box[key] - access_box[key]) <= 1 for key in ("x", "y", "width", "height")), (dialog_box, access_box)
            expect(dialog.get_by_role("tab", name="Account usage")).to_have_attribute(
                "aria-selected", "false"
            )
            expect(dialog.locator(".admin-usage-table")).to_be_hidden()
            for heading in ("Email / Domain", "Role", "ChatGPT Allowance", "Actions"):
                expect(dialog.get_by_role("columnheader", name=heading)).to_be_visible()
            ordered = dialog.locator(".admin-grants-table tbody tr:not(.admin-add-row)")
            assert ordered.evaluate_all(
                "rows => { const values = rows.map(row => row.querySelector('th').innerText.split('\\n')[0]); return values.length === 2 && values.every((value, index) => index === 0 || values[index - 1].localeCompare(value, undefined, {sensitivity: 'base'}) <= 0); }"
            )
            grants_table = dialog.locator(".admin-grants-table")
            table_before_new = grants_table.bounding_box()
            dialog.locator(".admin-grants-table").get_by_role(
                "button", name="New", exact=True
            ).click()
            add_panel = page.get_by_role("group", name="Add authorized user")
            expect(add_panel).to_be_visible()
            expect(add_panel).to_be_in_viewport()
            expect(add_panel.get_by_role("heading", name="New Email or Domain")).to_be_visible()
            page.screenshot(path="/tmp/sigma-t40-admin-add-overlay.png", full_page=True)
            table_during_new = grants_table.bounding_box()
            parent_box = dialog.bounding_box()
            panel_box = add_panel.bounding_box()
            assert table_before_new and table_during_new and all(abs(table_before_new[key] - table_during_new[key]) <= 1 for key in ("x", "y", "width", "height")), (table_before_new, table_during_new)
            assert parent_box and panel_box and parent_box["x"] <= panel_box["x"] and parent_box["y"] <= panel_box["y"] and panel_box["x"] + panel_box["width"] <= parent_box["x"] + parent_box["width"] and panel_box["y"] + panel_box["height"] <= parent_box["y"] + parent_box["height"], (parent_box, panel_box)
            assert abs((panel_box["x"] + panel_box["width"] / 2) - (parent_box["x"] + parent_box["width"] / 2)) <= 1, (parent_box, panel_box)
            assert abs((panel_box["y"] + panel_box["height"] / 2) - (parent_box["y"] + parent_box["height"] / 2)) <= 1, (parent_box, panel_box)
            add_panel.get_by_label("New email address").fill("reviewer@example.org")
            add_panel.get_by_label("New ChatGPT allowance").fill("4.50")
            add_box = add_panel.get_by_role("button", name="Add", exact=True).bounding_box()
            cancel_box = add_panel.get_by_role("button", name="Cancel", exact=True).bounding_box()
            assert add_box and cancel_box
            assert abs(cancel_box["x"] - add_box["x"]) <= 2, (add_box, cancel_box)
            assert cancel_box["y"] >= add_box["y"] + add_box["height"] - 1, (
                add_box,
                cancel_box,
            )
            assert not any(request.startswith("POST ") and "/grants" in request for request in admin_requests)
            add_panel.get_by_role("button", name="Cancel", exact=True).click()
            expect(page.get_by_role("group", name="Add authorized user")).to_have_count(0)
            expect(dialog.locator(".admin-add-row").get_by_role("button", name="New")).to_be_focused()
            assert not any(request.startswith("POST ") and "/grants" in request for request in admin_requests)
            dialog.locator(".admin-grants-table").get_by_role(
                "button", name="New", exact=True
            ).click()
            add_panel = page.get_by_role("group", name="Add authorized user")
            expect(add_panel.get_by_label("New email address")).to_have_value("")
            expect(add_panel.get_by_label("New ChatGPT allowance")).to_have_value("")
            add_panel.get_by_label("New email address").fill("reviewer@example.org")
            add_panel.get_by_label("New ChatGPT allowance").fill("4.50")
            add_panel.get_by_role("button", name="Add", exact=True).click()
            added = dialog.locator(".admin-grants-table tbody tr").filter(
                has_text="reviewer@example.org"
            )
            expect(added).to_be_visible()
            expect(dialog.get_by_text("Authorization added.", exact=True)).to_have_count(0)
            added.get_by_label("Role for reviewer@example.org").select_option("admin")
            added.get_by_label("ChatGPT allowance for reviewer@example.org").fill("5.25")
            dialog.get_by_role("button", name="Save Updates").click()
            expect(dialog.get_by_role("button", name="Save Updates")).to_have_count(0)
            table_before_remove = grants_table.bounding_box()
            added.get_by_role("button", name="Remove", exact=True).click()
            removal = page.get_by_role("group", name="Confirm remove access for reviewer@example.org")
            expect(removal).to_contain_text("Recorded usage will be retained.")
            expect(removal).to_be_in_viewport()
            page.screenshot(path="/tmp/sigma-t40-admin-remove-overlay.png", full_page=True)
            assert removal.evaluate("e => e.closest('tr') === null")
            table_during_remove = grants_table.bounding_box()
            assert table_before_remove and table_during_remove and all(abs(table_before_remove[key] - table_during_remove[key]) <= 1 for key in ("x", "y", "width", "height")), (table_before_remove, table_during_remove)
            page.mouse.move(0, 0)
            assert added.get_by_role("button", name="Remove", exact=True).evaluate(
                "e => getComputedStyle(e).color"
            ) == "rgb(240, 204, 160)"
            removal.get_by_role("button", name="Cancel", exact=True).click()
            expect(page.get_by_role("group", name="Confirm remove access for reviewer@example.org")).to_have_count(0)
            assert not any(request.startswith("DELETE ") for request in admin_requests)
            added.get_by_role("button", name="Remove", exact=True).click()
            page.get_by_role("group", name="Confirm remove access for reviewer@example.org").get_by_role(
                "button", name="Confirm", exact=True
            ).click()
            expect(dialog.get_by_text("reviewer@example.org", exact=True)).to_have_count(0)
            expect(dialog.get_by_text("Removed access for reviewer@example.org.", exact=True)).to_have_count(0)
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
            assert new_row.locator("td").count() == 4
            assert new_row.locator("td").nth(3).get_by_role(
                "button", name="New", exact=True
            ).is_visible()
            assert new_row.locator("td").nth(0).inner_text() == ""
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
                parent_before = dialog.bounding_box()
                table_before = dialog.locator(".admin-grants-table").bounding_box()
                dialog.locator(".admin-add-row").get_by_role("button", name="New").click()
                add_panel = page.get_by_role("group", name="Add authorized user")
                expect(add_panel).to_be_in_viewport()
                table_after = dialog.locator(".admin-grants-table").bounding_box()
                parent_after = dialog.bounding_box()
                assert table_before and table_after and all(abs(table_before[key] - table_after[key]) <= 1 for key in ("y", "width", "height")), (width, table_before, table_after)
                assert parent_before and parent_after and all(abs(parent_before[key] - parent_after[key]) <= 1 for key in ("x", "y", "width", "height")), (width, parent_before, parent_after)
                parent_box = dialog.bounding_box()
                panel_box = add_panel.bounding_box()
                assert parent_box and panel_box and parent_box["x"] <= panel_box["x"] and parent_box["y"] <= panel_box["y"] and panel_box["x"] + panel_box["width"] <= parent_box["x"] + parent_box["width"] and panel_box["y"] + panel_box["height"] <= parent_box["y"] + parent_box["height"], (width, parent_box, panel_box)
                expect(add_panel.get_by_role("heading", name="New Email or Domain")).to_be_visible()
                assert abs((panel_box["x"] + panel_box["width"] / 2) - (parent_box["x"] + parent_box["width"] / 2)) <= 1, (width, parent_box, panel_box)
                assert abs((panel_box["y"] + panel_box["height"] / 2) - (parent_box["y"] + parent_box["height"] / 2)) <= 1, (width, parent_box, panel_box)
                if width == 390:
                    page.screenshot(path="/tmp/sigma-t40-admin-add-overlay-390.png", full_page=True)
                add_panel.get_by_role("button", name="Cancel", exact=True).click()
                expect(page.get_by_role("group", name="Add authorized user")).to_have_count(0)
                access_box = dialog.bounding_box()
                assert access_box
                dialog.get_by_role("tab", name="Account usage").click()
                usage_box = dialog.bounding_box()
                assert usage_box and all(abs(access_box[key] - usage_box[key]) <= 1 for key in ("x", "y", "width", "height")), (width, access_box, usage_box)
                dialog.get_by_role("tab", name="Access Management").click()
                restored_box = dialog.bounding_box()
                assert restored_box and all(abs(access_box[key] - restored_box[key]) <= 1 for key in ("x", "y", "width", "height")), (width, access_box, restored_box)
                page.screenshot(path=f"/tmp/sigma-t40-admin-dialog-{width}.png", full_page=True)
                dialog.get_by_role("button", name="Close", exact=True).click()

            # An authenticated ordinary member never sees the admin link.
            status.update(user={"email": "member@example.org", "role": "member"})
            member = browser.new_page(viewport={"width": 390, "height": 844})
            member.route("**/api/**", forward)
            member.route("**/api/cloud-auth/status", cloud_status)
            member.goto(URL, wait_until="networkidle")
            expect(member.locator(".home-topline .project-google-signin")).to_have_text(
                "Google account connected"
            )
            expect(member.get_by_role("link", name="Administrator Settings")).to_have_count(0)
            expect(member.get_by_text("member@example.org", exact=True)).to_have_count(0)
            assert not errors, errors
            assert admin_requests and all("127.0.0.1" in request for request in admin_requests)
            print(
                "T40 Chrome: deterministic signed-out/admin/member states, account dialog, admin Add/Cancel/edit/save/Remove, artwork credit and desktop/mobile layouts PASS"
            )
        finally:
            browser.close()


if __name__ == "__main__":
    main()
