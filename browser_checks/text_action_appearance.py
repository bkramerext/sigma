"""Chromium regression for text-like buttons inheriting filled-button styling.

Runs against the isolated browser fixture; no Google sign-in or AI request.
Tests rendered About legal controls and Home invitation retry after a failed POST.
"""

import os

from playwright.sync_api import expect, sync_playwright

URL = os.environ.get("SIGMA_BROWSER_BASE_URL", "http://127.0.0.1:5173").rstrip("/")


def computed_action_style(locator):
    return locator.evaluate(
        """element => {
            const style = getComputedStyle(element);
            return {
                background: style.backgroundColor,
                backgroundImage: style.backgroundImage,
                borderWidth: style.borderTopWidth,
                paddingLeft: style.paddingLeft,
                paddingRight: style.paddingRight,
                shadow: style.boxShadow,
                decoration: style.textDecorationLine,
                color: style.color
            };
        }"""
    )


def assert_link_appearance(locator, *, color):
    style = computed_action_style(locator)
    assert style["background"] == "rgba(0, 0, 0, 0)", style
    assert style["backgroundImage"] == "none", style
    assert style["borderWidth"] == "0px", style
    assert style["paddingLeft"] == style["paddingRight"] == "0px", style
    assert style["shadow"] == "none", style
    assert "underline" in style["decoration"], style
    assert style["color"] == color, style


def main():
    with sync_playwright() as playwright:
        browser = playwright.chromium.launch(
            executable_path=os.environ.get(
                "SIGMA_BROWSER_EXECUTABLE", playwright.chromium.executable_path
            ),
            headless=True,
        )
        page = browser.new_page(viewport={"width": 1440, "height": 900})
        page_errors = []
        page.on("pageerror", lambda error: page_errors.append(str(error)))

        # A real guest Home state makes the retry control appear after a
        # deterministic failed invitation request.
        page.route(
            "**/api/cloud-auth/status",
            lambda route: route.fulfill(
                json={
                    "target": "local",
                    "enabled": True,
                    "ready": True,
                    "authenticated": True,
                    "user": {"email": "guest@example.org", "role": "guest"},
                    "account": {
                        "identity": {"email": "guest@example.org", "verified": True},
                        "access": {"status": "guest", "role": "guest"},
                        "workspace": {"available": True, "id": "guest"},
                        "model_access": {
                            "mode": "personal",
                            "connection": "disconnected",
                        },
                        "sponsorship": {"eligible": False},
                        "invitation_status": None,
                    },
                    "admin_contact_email": None,
                }
            ),
        )
        attempts = []

        def rejected_invitation(route):
            attempts.append(route.request.method)
            route.fulfill(
                status=503,
                json={"detail": "Temporary invitation request failure."},
            )

        page.route("**/api/cloud-auth/invitation-request", rejected_invitation)
        page.goto(URL)
        expect(page.get_by_role("heading", name="Projects")).to_be_visible()
        welcome = page.locator("#invitation-welcome-dialog")
        if welcome.count() and welcome.is_visible():
            welcome.get_by_role("button", name="Explore as guest").click()
            expect(welcome).not_to_be_visible()

        page.get_by_role("button", name="About SIGMA").click()
        about = page.get_by_role("dialog", name="About SIGMA")
        expect(about).to_be_visible()
        for name in ("Privacy Notice", "Terms of Service"):
            legal = about.get_by_role("button", name=name, exact=True)
            expect(legal).to_be_visible()
            assert_link_appearance(legal, color="rgb(237, 195, 141)")
            legal.hover()
            assert_link_appearance(legal, color="rgb(255, 224, 181)")
            page.mouse.move(0, 0)
            legal.focus()
            assert_link_appearance(legal, color="rgb(237, 195, 141)")
        about.get_by_role("button", name="Privacy Notice", exact=True).click()
        expect(page.get_by_role("dialog", name="SIGMA Privacy Notice")).to_be_visible()
        page.get_by_role("button", name="Close privacy notice").click()
        expect(about).to_be_visible()
        about.get_by_role("button", name="Terms of Service", exact=True).click()
        expect(page.get_by_role("dialog", name="Terms of Service")).to_be_visible()
        page.get_by_role("button", name="Close terms of service").click()
        expect(about).to_be_visible()
        page.get_by_role("button", name="Close About SIGMA").click()

        invite = page.get_by_role("button", name="Invite me!", exact=True)
        expect(invite).to_be_visible()
        invite.click()
        expect(page.get_by_role("alert")).to_contain_text("Temporary invitation request failure.")
        retry = page.get_by_role("button", name="Try again", exact=True)
        expect(retry).to_be_visible()
        assert_link_appearance(retry, color="rgb(224, 196, 160)")
        retry.hover()
        assert_link_appearance(retry, color="rgb(224, 196, 160)")
        retry.click()
        expect(retry).to_be_visible()
        assert attempts == ["POST", "POST"], attempts

        assert not page_errors, page_errors
        browser.close()
    print("PASS About legal buttons and Home invitation retry have transparent link styling")


if __name__ == "__main__":
    main()
