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
                    if path == "/privacy":
                        expect(
                            page.get_by_text("Prepared October 26, 2026 · Version 1.0", exact=True)
                        ).to_be_visible()
                    else:
                        expect(
                            page.get_by_text("No terms except to discover something interesting, wonderous, or pioneering.", exact=True)
                        ).to_be_visible()
                    assert not [url for url in api_requests if "/api/cloud-auth/" in url], (
                        api_requests
                    )

            page.goto(f"{URL}/tos")
            terms = page.locator(".terms-of-service-card")
            copy = terms.locator(".terms-of-service-copy > p")
            expect(copy).to_have_count(2)
            sizes = copy.evaluate_all(
                "nodes => nodes.map(node => parseFloat(getComputedStyle(node).fontSize))"
            )
            assert sizes[0] == sizes[1] and sizes[0] >= 19, sizes
            assert copy.nth(1).evaluate(
                "node => getComputedStyle(node).fontStyle"
            ) == "italic"
            # Clicking within the card keeps it open. Clicking its backdrop
            # returns home just like the explicit Close action.
            copy.first.click()
            expect(page.get_by_role("heading", name="Terms of Service")).to_be_visible()
            shell_box = page.locator(".cloud-auth-shell").bounding_box()
            assert shell_box
            page.mouse.click(shell_box["x"] + 6, shell_box["y"] + 6)
            expect(page).to_have_url(URL + "/")

            page.goto(URL)
            welcome = page.get_by_role("dialog", name="Welcome to SIGMA!")
            if welcome.is_visible():
                welcome.get_by_role("button", name="Let's get started").click()
            opener = page.get_by_role("button", name="About SIGMA", exact=True)
            expect(opener).to_be_visible()
            opener.click()
            dialog = page.get_by_role("dialog", name="About SIGMA")
            expect(dialog).to_be_visible()
            expect(dialog.get_by_role("link", name="Privacy Notice", exact=True)).to_have_attribute(
                "href", "/privacy?return_to=%2F&return_dialog=about"
            )
            expect(
                dialog.get_by_role("link", name="Terms of Service", exact=True)
            ).to_have_attribute("href", "/tos")
            marker = dialog.locator(".about-disclosure > summary").first
            expect(marker).to_be_visible()
            marker_style = marker.evaluate(
                "element => { const marker = getComputedStyle(element, '::before'); "
                "return {borderRadius: marker.borderRadius, borderTopStyle: marker.borderTopStyle, "
                "borderRightStyle: marker.borderRightStyle}; }"
            )
            assert marker_style == {
                "borderRadius": "0px",
                "borderTopStyle": "solid",
                "borderRightStyle": "solid",
            }, marker_style
        finally:
            browser.close()

    print(
        "PASS public legal pages, Welcome-sized Terms text, backdrop close and About links"
    )


if __name__ == "__main__":
    main()
