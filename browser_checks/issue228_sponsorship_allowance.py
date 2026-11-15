"""Rendered regression check for the admin sponsorship allowance column."""

import json
import os
from pathlib import Path
from urllib.parse import urlparse

from playwright.sync_api import expect, sync_playwright

URL = os.environ.get("SIGMA_BROWSER_BASE_URL", "http://127.0.0.1:5173")
API_URL = os.environ.get("SIGMA_BROWSER_FIXTURE_URL", "http://127.0.0.1:8026")
EXPECTED_TOOLTIP = os.environ.get(
    "SIGMA_EXPECT_CONNECTION_TOOLTIP",
    "ChatGPT is connected. Click to return to sponsorship.",
)
BOOTSTRAP = "owner@example.org"
GRANTS = [
    {
        "kind": "email",
        "value": "reviewer@example.org",
        "role": "member",
        "active": 1,
        "updated_at": 0,
        "allowance_usd": 2.0,
        "effective_allowance_usd": 2.0,
    },
    {
        "kind": "email",
        "value": "unlimited@example.org",
        "role": "admin",
        "active": 1,
        "updated_at": 0,
        "allowance_usd": None,
        "effective_allowance_usd": None,
    },
    {
        "kind": "email",
        "value": "large@example.org",
        "role": "member",
        "active": 1,
        "updated_at": 0,
        "allowance_usd": 15.0,
        "effective_allowance_usd": 15.0,
    },
]


def fulfill_api(route) -> None:
    path = urlparse(route.request.url).path
    payloads = {
        "/api/cloud-auth/status": {
            "target": "local",
            "enabled": True,
            "ready": True,
            "authenticated": True,
            "user": {"email": BOOTSTRAP, "role": "admin"},
            "account": {
                "identity": {"email": BOOTSTRAP, "verified": True},
                "access": {"status": "active", "role": "admin"},
                "workspace": {"available": True, "id": "fixture"},
                "model_access": {"mode": "personal", "connection": "connected"},
                "sponsorship": {"eligible": False},
            },
            "admin_contact_email": None,
        },
        "/api/cloud-auth/admin/grants": {
            "bootstrap_admin": BOOTSTRAP,
            "grants": GRANTS,
            "sessions": [],
        },
        "/api/cloud-auth/admin/invitation-requests": {"requests": []},
        "/api/cloud-auth/admin/feedback": {"feedback": []},
        "/api/ai/connection": {
            "mode": "chatgpt",
            "status": "connected",
            "label": "ChatGPT connected",
            "guidance": "ChatGPT is connected.",
            "checked_at": "2026-10-28T12:00:00Z",
            "ttl_seconds": 60,
            "account_label": "private@example.test",
            "active_account": "fixture-account",
            "accounts": [],
        },
    }
    payload = payloads.get(path)
    if payload is None:
        route.fulfill(response=route.fetch(url=route.request.url.replace(URL, API_URL)))
        return
    route.fulfill(status=200, content_type="application/json", body=json.dumps(payload))


def center_x(locator) -> float:
    box = locator.bounding_box()
    assert box, f"missing box for {locator}"
    return box["x"] + box["width"] / 2


def main() -> None:
    evidence = Path("docs/evaluations/t313/evidence")
    evidence.mkdir(parents=True, exist_ok=True)
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
            page.route("**/api/**", fulfill_api)
            page.goto(URL, wait_until="domcontentloaded")
            expect(page.locator(".administrator-settings-link")).to_be_visible()
            connection = page.locator(".api-connection > summary")
            expect(connection.get_by_role("status")).to_have_text("ChatGPT connected")
            tooltip_text = connection.get_attribute("data-tooltip") or ""
            assert tooltip_text == EXPECTED_TOOLTIP, tooltip_text
            assert connection.get_attribute("title") is None
            connection.hover()
            tooltip = page.get_by_role("tooltip", name=EXPECTED_TOOLTIP)
            expect(tooltip).to_be_visible()
            page.screenshot(
                path=str(
                    evidence
                    / (
                        "home-connection-before.png"
                        if "private@example.test" in EXPECTED_TOOLTIP
                        else "home-connection-after.png"
                    )
                ),
                full_page=True,
            )
            page.mouse.move(1, 1)
            for width, height, suffix in (
                (1440, 900, "1440"),
                (390, 844, "390"),
            ):
                page.set_viewport_size({"width": width, "height": height})
                page.locator(".administrator-settings-link").click()
                dialog = page.get_by_role("dialog", name="Administrator Settings")
                expect(dialog).to_be_visible()
                heading = dialog.get_by_role(
                    "columnheader", name="Sponsorship allowance", exact=True
                )
                expect(heading).to_be_visible()
                cells = dialog.locator(".admin-allowance-cell")
                expect(cells).to_have_count(3)
                page.screenshot(
                    path=str(
                        evidence
                        / f"admin-allowance-{('before' if 'private@example.test' in EXPECTED_TOOLTIP else 'after')}-{suffix}.png"
                    ),
                    full_page=True,
                )
                for row, value in zip(
                    ("reviewer@example.org", "unlimited@example.org", "large@example.org"),
                    ("$2.00", "Unlimited", "$15.00"),
                    strict=True,
                ):
                    entry = dialog.get_by_role("row", name=row)
                    cell = entry.locator(".admin-allowance-cell")
                    rendered_value = (
                        cell.get_by_text(value, exact=True)
                        if value == "Unlimited"
                        else cell.locator(".admin-allowance-input")
                    )
                    expect(rendered_value).to_be_visible()
                    assert abs(center_x(heading) - center_x(rendered_value)) <= 1, (
                        row,
                        value,
                        center_x(heading),
                        center_x(rendered_value),
                    )
                    if value != "Unlimited":
                        amount = "2.00" if value == "$2.00" else "15.00"
                        expect(cell.locator("small")).to_have_text(f"Effective ${amount}")
                        assert abs(center_x(heading) - center_x(cell.locator("small"))) <= 1
                scroll = dialog.locator(".admin-table-scroll:has(.admin-grants-table)")
                if width == 390:
                    assert scroll.evaluate("node => node.scrollWidth > node.clientWidth")
                assert page.evaluate("document.documentElement.scrollWidth <= innerWidth")
                dialog.get_by_role("button", name="Close", exact=True).click()
            print("PASS Sponsorship allowance alignment at 1440px and 390px")
        finally:
            browser.close()


if __name__ == "__main__":
    main()
