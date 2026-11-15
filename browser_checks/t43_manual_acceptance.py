"""Real Chrome acceptance for T43's ChatGPT connection controls."""

import json
import os

from playwright.sync_api import expect, sync_playwright

URL = os.environ.get("SIGMA_BROWSER_BASE_URL", "http://127.0.0.1:5173").rstrip("/")
API = os.environ.get("SIGMA_BROWSER_API_URL", "http://127.0.0.1:8000").rstrip("/")


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
            page = browser.new_page(viewport={"width": 1280, "height": 800})
            errors: list[str] = []
            page.on("pageerror", lambda error: errors.append(str(error)))

            def forward(route):
                route.fulfill(
                    response=route.fetch(
                        url=route.request.url.replace(URL, API),
                        headers={**route.request.headers, "origin": "http://127.0.0.1:5173"},
                    )
                )

            def ai_connection(route):
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
                            "welcome_pending": False,
                        }
                    ),
                )

            page.route("**/api/**", forward)
            page.route("**/api/ai/connection*", ai_connection)
            page.goto(URL, wait_until="networkidle")
            summary = page.locator(".home-topline .api-connection > summary")
            expect(summary).to_be_visible()

            for width, height in ((1280, 800), (390, 844), (320, 844)):
                page.set_viewport_size({"width": width, "height": height})
                summary.click()
                panel = page.locator(".connection-details")
                expect(panel).to_be_visible()
                primary = panel.get_by_role("button", name="Continue with ChatGPT", exact=True)
                expect(primary).to_be_visible()
                assert primary.evaluate(
                    "element => { const s = getComputedStyle(element); return s.backgroundImage.includes('linear-gradient') && s.borderRadius === '5px' && s.color === 'rgb(30, 20, 9)'; }"
                )
                assert primary.evaluate("element => element.getBoundingClientRect().width") <= 280
                retry = panel.get_by_role("button", name="Retry connection", exact=True)
                expect(retry).to_have_class("connection-text-action")
                assert retry.evaluate(
                    "element => getComputedStyle(element).textDecorationLine.includes('underline')"
                )
                panel.get_by_text("API key option", exact=True).click()
                api_action = panel.get_by_role(
                    "button", name="Separately billed API Key", exact=True
                )
                expect(api_action).to_be_visible()
                expect(api_action).to_have_class("connection-text-action")
                assert api_action.evaluate(
                    "element => getComputedStyle(element).textDecorationLine.includes('underline')"
                )
                assert page.evaluate("document.documentElement.scrollWidth <= innerWidth"), width
                page.screenshot(path=f"/tmp/sigma-t43-chatgpt-{width}.png", full_page=True)
                page.keyboard.press("Escape")
                expect(summary).to_be_focused()

            assert not errors, errors

            hosted = browser.new_page(viewport={"width": 1280, "height": 800})
            hosted_errors: list[str] = []
            hosted.on("pageerror", lambda error: hosted_errors.append(str(error)))
            hosted.route("**/api/**", forward)
            hosted.route(
                "**/api/cloud-auth/status",
                lambda route: route.fulfill(
                    status=200,
                    content_type="application/json",
                    body=json.dumps(
                        {
                            "target": "hosted",
                            "enabled": True,
                            "ready": True,
                            "authenticated": True,
                            "user": {"email": "admin@example.test", "role": "admin"},
                            "admin_contact_email": "admin@example.test",
                        }
                    ),
                ),
            )
            hosted.route("**/api/ai/connection*", ai_connection)
            hosted.route(
                "**/api/cloud-research/budget",
                lambda route: route.fulfill(
                    status=200,
                    content_type="application/json",
                    body=json.dumps(
                        {
                            "allowance_usd": 2,
                            "estimated_usage_usd": 0,
                            "held_usd": 0,
                            "remaining_usd": 2,
                            "unknown_provider_attempts": 0,
                        }
                    ),
                ),
            )
            hosted.goto(URL, wait_until="networkidle")
            hosted_summary = hosted.locator(".home-topline .api-connection > summary")
            expect(hosted_summary).to_contain_text("ChatGPT · SIGMA service")
            hosted_summary.click()
            hosted_panel = hosted.locator(".connection-details")
            expect(hosted_panel).to_be_visible()
            expect(hosted_panel.get_by_text("SIGMA service-funded inference")).to_be_visible()
            expect(
                hosted_panel.get_by_role("button", name="Continue with ChatGPT", exact=True)
            ).to_have_count(0)
            expect(hosted_panel.get_by_text("API key option", exact=True)).to_have_count(0)
            hosted.keyboard.press("Escape")
            expect(hosted_summary).to_be_focused()
            assert not hosted_errors, hosted_errors
            print(
                "T43 Chrome: local copper ChatGPT action, underlined Retry/API Key actions, hosted service-only UI, anchored keyboard dismissal, and 1280/390/320px layouts PASS"
            )
        finally:
            browser.close()


if __name__ == "__main__":
    main()
