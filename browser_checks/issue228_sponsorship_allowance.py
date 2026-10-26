"""Real-Chrome visual checks for issue #228's admin allowance column."""

import json
import os

from playwright.sync_api import expect, sync_playwright

URL = os.environ.get("SIGMA_BROWSER_BASE_URL", "http://127.0.0.1:5173")
BOOTSTRAP = "owner@example.org"
status = {
    "target": "local",
    "enabled": True,
    "ready": True,
    "authenticated": True,
    "user": {"email": BOOTSTRAP, "role": "admin"},
    "admin_contact_email": None,
}
grant = {
    "kind": "email",
    "value": "reviewer@example.org",
    "role": "member",
    "active": 1,
    "allowance_usd": 2.0,
    "effective_allowance_usd": 2.0,
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

            def unauthorized(route):
                route.fulfill(
                    status=401,
                    content_type="application/json",
                    body='{"error":"Authentication required."}',
                )

            page.route("**/api/**", unauthorized)
            page.route(
                "**/api/cloud-auth/status",
                lambda route: route.fulfill(
                    status=200,
                    content_type="application/json",
                    body=json.dumps(status),
                ),
            )
            page.route(
                "**/api/cloud-auth/admin/grants",
                lambda route: route.fulfill(
                    status=200,
                    content_type="application/json",
                    body=json.dumps(
                        {
                            "bootstrap_admin": BOOTSTRAP,
                            "grants": [grant],
                            "sessions": [],
                        }
                    ),
                ),
            )
            page.route(
                "**/api/cloud-auth/admin/invitation-requests",
                lambda route: route.fulfill(
                    status=200,
                    content_type="application/json",
                    body='{"requests": []}',
                ),
            )

            page.goto(URL, wait_until="networkidle")
            expect(page.locator(".administrator-settings-link")).to_be_visible()
            for width, height in ((1440, 900), (390, 844)):
                page.set_viewport_size({"width": width, "height": height})
                page.locator(".administrator-settings-link").click()
                dialog = page.get_by_role("dialog", name="Administrator Settings")
                expect(dialog).to_be_visible()
                heading = dialog.get_by_role(
                    "columnheader", name="Sponsorship Allowance", exact=True
                )
                expect(heading).to_be_visible()
                expect(
                    dialog.get_by_role("columnheader", name="ChatGPT Allowance", exact=True)
                ).to_have_count(0)
                cell = dialog.locator(".admin-allowance-cell")
                label = cell.locator(".admin-allowance-input")
                expect(label.locator("input")).to_be_visible()
                expect(cell.locator("small")).to_have_text("Effective $2.00")
                heading_box = heading.bounding_box()
                label_box = label.bounding_box()
                effective_box = cell.locator("small").bounding_box()
                assert heading_box and label_box and effective_box
                center = heading_box["x"] + heading_box["width"] / 2
                assert abs(center - (label_box["x"] + label_box["width"] / 2)) <= 1
                assert abs(center - (effective_box["x"] + effective_box["width"] / 2)) <= 1
                table_scroll = dialog.locator(".admin-table-scroll:has(.admin-grants-table)")
                assert table_scroll.evaluate("node => node.scrollWidth >= node.clientWidth")
                if width == 390:
                    assert table_scroll.evaluate("node => node.scrollWidth > node.clientWidth")
                page.screenshot(path=f"/tmp/sigma-issue228-admin-{width}.png", full_page=True)
                dialog.get_by_role("button", name="Close", exact=True).click()
            assert page.evaluate("document.documentElement.scrollWidth <= innerWidth")
            print("PASS issue #228 Sponsorship Allowance alignment at 1440px and 390px")
        finally:
            browser.close()


if __name__ == "__main__":
    main()
