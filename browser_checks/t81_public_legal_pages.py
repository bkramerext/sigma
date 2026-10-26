"""Real Chrome acceptance for public T81 legal pages and About privacy access."""

import os

from playwright.sync_api import expect, sync_playwright

URL = os.environ.get("SIGMA_BROWSER_BASE_URL", "http://127.0.0.1:5173")


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
            page = browser.new_page()
            api_requests: list[str] = []
            page.on(
                "request",
                lambda request: (
                    api_requests.append(request.url) if "/api/" in request.url else None
                ),
            )

            for path, heading in (
                ("/privacy", "SIGMA Privacy Notice"),
                ("/tos", "Terms of Service"),
            ):
                for navigation in (page.goto, page.reload):
                    if navigation == page.goto:
                        navigation(f"{URL}{path}")
                    else:
                        navigation()
                    expect(page.get_by_role("heading", name=heading, exact=True)).to_be_visible()
                    expect(page.get_by_role("status")).to_contain_text("awaiting")
                    assert not [url for url in api_requests if "/api/cloud-auth/" in url], (
                        api_requests
                    )

            page.goto(URL)
            opener = page.get_by_role("button", name="About")
            expect(opener).to_be_visible()
            opener.click()
            dialog = page.get_by_role("dialog", name="About SIGMA")
            expect(dialog).to_be_visible()
            expect(dialog.get_by_role("link", name="Privacy", exact=True)).to_have_attribute(
                "href", "/privacy"
            )
            assert page.locator('a[href="/tos"]').count() == 0
            assert page.locator('a[href*="/tos"]').count() == 0
        finally:
            browser.close()

    print(
        "PASS signed-out direct /privacy and /tos navigation/refresh; draft labels; About Privacy link; no /tos app links"
    )


if __name__ == "__main__":
    main()
