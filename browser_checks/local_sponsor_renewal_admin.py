"""Verify local administrators can start the designated sponsor auth flow."""

import json
import os

from playwright.sync_api import expect, sync_playwright

URL = os.environ.get("SIGMA_BROWSER_BASE_URL", "http://127.0.0.1:5173")
BOOTSTRAP = "admin@example.org"
status = {
    "target": "local",
    "enabled": True,
    "ready": True,
    "authenticated": True,
    "user": {"email": BOOTSTRAP, "role": "admin"},
    "admin_contact_email": BOOTSTRAP,
    "account": {
        "identity": {"email": BOOTSTRAP, "verified": True},
        "access": {"status": "active", "role": "admin"},
        "workspace": {"available": True, "id": "admin-workspace"},
        "model_access": {"mode": "personal", "connection": "disconnected"},
        "sponsorship": {"eligible": True},
    },
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
            ai_requests: list[str] = []
            page.on(
                "request",
                lambda request: (
                    ai_requests.append(request.url) if "/api/ai/" in request.url else None
                ),
            )

            def unauthorized(route):
                route.fulfill(
                    status=401,
                    content_type="application/json",
                    body='{"detail":"Authentication required."}',
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

            def sponsor_begin(route):
                route.fulfill(
                    status=503,
                    content_type="application/json",
                    body='{"detail":"Sponsor route fixture reached."}',
                )

            page.route("**/api/ai/sponsor-auth/begin", sponsor_begin)

            def select_mode(route):
                assert route.request.post_data_json == {"mode": "sponsored"}
                route.fulfill(
                    status=200,
                    content_type="application/json",
                    body='{"mode":"sponsored"}',
                )

            page.route("**/api/ai/mode", select_mode)
            page.goto(URL, wait_until="networkidle")
            page.get_by_role("link", name="Administrator settings").click()
            dialog = page.get_by_role("dialog", name="Administrator Settings")
            expect(dialog).to_be_visible()
            expect(
                dialog.get_by_role("heading", name="Designated sponsor connection")
            ).to_be_visible()
            expect(dialog.get_by_text("zetacontinuation@gmail.com")).to_be_visible()
            with page.expect_response("**/api/ai/sponsor-auth/begin") as response_info:
                dialog.get_by_role("button", name="Renew sponsor ChatGPT connection").click()
            assert response_info.value.status == 503
            expect(
                dialog.locator(".admin-sponsor-connection").get_by_text(
                    "Sponsor route fixture reached."
                )
            ).to_be_visible()
            assert any("/api/ai/sponsor-auth/begin" in url for url in ai_requests)
            assert not any("/api/ai/auth/begin" in url for url in ai_requests)
            with page.expect_request("**/api/ai/mode") as mode_request:
                dialog.get_by_role("button", name="Select sponsored mode").click()
            assert mode_request.value.post_data_json == {"mode": "sponsored"}
            print(
                "PASS local Admin Settings separates sponsor renewal and explicit sponsored-mode selection"
            )
        finally:
            browser.close()


if __name__ == "__main__":
    main()
