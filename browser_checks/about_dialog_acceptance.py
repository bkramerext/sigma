"""Real Chrome acceptance for the Home About dialog, including narrow and touch layouts."""
import json
import os
from urllib.parse import urlsplit

from playwright.sync_api import expect, sync_playwright

URL = os.environ.get("SIGMA_BROWSER_BASE_URL", "http://127.0.0.1:5196")


def main() -> None:
    with sync_playwright() as playwright:
        browser = playwright.chromium.launch(
            executable_path=os.environ.get("SIGMA_BROWSER_EXECUTABLE", "/Applications/Google Chrome.app/Contents/MacOS/Google Chrome"),
            headless=True,
        )
        try:
            context = browser.new_context(viewport={"width": 1440, "height": 960})
            page = context.new_page()
            errors: list[str] = []
            page.on("pageerror", lambda error: errors.append(str(error)))

            def home_data(route):
                path = urlsplit(route.request.url).path
                if path == "/api/projects/recent":
                    route.fulfill(status=200, content_type="application/json", body=json.dumps({"projects": []}))
                elif path == "/api/ai/connection":
                    route.fulfill(status=200, content_type="application/json", body=json.dumps({"mode": "chatgpt", "status": "disconnected", "label": "Connect AI", "guidance": "Manual research is always available.", "checked_at": None, "ttl_seconds": 60, "accounts": [], "active_account": None}))
                else:
                    route.continue_()

            page.route("**/api/**", home_data)
            page.goto(URL)
            expect(page.get_by_role("heading", name="Projects")).to_be_visible()
            opener = page.get_by_role("button", name="About")
            for width, height in ((1440, 960), (390, 844), (320, 740)):
                page.set_viewport_size({"width": width, "height": height})
                credit = page.locator(".home-art-credit")
                expect(credit).to_be_visible()
                assert credit.evaluate("e => getComputedStyle(e).textTransform") == "capitalize"
                opener.click()
                dialog = page.get_by_role("dialog", name="About SIGMA")
                expect(dialog).to_be_visible()
                page.screenshot(path=f"/tmp/sigma-about-collapsed-{width}.png", full_page=False)
                expect(dialog.locator(".about-intro")).to_be_visible()
                expect(dialog.locator(".about-terms")).to_be_visible()
                expect(dialog.locator("details")).to_have_count(2)
                for label in ("Key Features", "How SIGMA Works: Multi-Agentic Research"):
                    region = dialog.locator("details").filter(has=page.locator("summary", has_text=label))
                    expect(region).to_have_count(1)
                    expect(region).not_to_have_attribute("open", "")
                    region.locator("summary").click()
                    expect(region).to_have_attribute("open", "")
                expect(dialog.locator(".about-intro")).to_contain_text("research workbench for exploring answers")
                expect(dialog.locator(".about-terms")).to_have_text("Strategies set direction. Sessions investigate. Outcomes assess. Reports communicate.")
                for title in ("Multi-Strategy Exploration", "Multiple Research Agents", "Research History", "Experimental LaTeX Paper Generation"):
                    expect(dialog.get_by_role("heading", name=title, exact=True)).to_be_visible()
                expect(dialog.locator(".about-build-commit")).to_contain_text(__import__("re").compile(r"Build [0-9a-f]{7}"))
                expect(dialog.locator(".about-session-toggle")).to_have_attribute("aria-expanded", "false")
                session_toggle = dialog.locator(".about-session-toggle")
                session_toggle.click()
                expect(session_toggle).to_have_attribute("aria-expanded", "true")
                details = dialog.locator("#about-session-details")
                expect(details.get_by_text("Session Orchestration")).to_be_visible()
                expect(details.get_by_text("Investigator", exact=True)).to_be_visible()
                expect(details.get_by_text("Skeptic", exact=True)).to_be_visible()
                expect(details.get_by_text("Coordinator Decision")).to_be_visible()
                # Help affordances are separate from expansion controls.
                strategy_a = dialog.locator('[data-about-info-node="strategyA"]')
                strategy_a.hover()
                tip = dialog.get_by_role("tooltip")
                expect(tip).to_contain_text("objective is bounded")
                tipbox = tip.bounding_box()
                assert tipbox and tipbox["x"] >= 0 and tipbox["x"] + tipbox["width"] <= width, (width, tipbox)
                page.keyboard.press("Escape")
                expect(dialog.get_by_role("tooltip")).to_have_count(0)
                help_button = dialog.get_by_role("button", name="Explain Research Project")
                help_button.focus()
                expect(dialog.get_by_role("tooltip")).to_contain_text("central research question")
                page.keyboard.press("Escape")
                expect(dialog).to_be_visible()
                page.screenshot(path=f"/tmp/sigma-about-expanded-{width}.png", full_page=False)
                assert dialog.evaluate("e => e.scrollWidth <= e.clientWidth"), (width, "dialog overflow")
                assert page.evaluate("document.documentElement.scrollWidth <= innerWidth"), (width, "page overflow")
                page.get_by_role("button", name="Close", exact=True).click()
                expect(dialog).to_have_count(0)
                expect(opener).to_be_focused()
            assert not errors, errors

            touch = browser.new_context(viewport={"width": 390, "height": 844}, is_mobile=True, has_touch=True)
            touch_page = touch.new_page()
            touch_page.route("**/api/**", home_data)
            touch_page.goto(URL)
            touch_page.get_by_role("button", name="About").tap()
            dialog = touch_page.get_by_role("dialog", name="About SIGMA")
            arch = dialog.locator("details").filter(has=touch_page.locator("summary", has_text="How SIGMA Works"))
            arch.locator("summary").tap()
            button = dialog.get_by_role("button", name="Explain Research Project")
            button.tap()
            expect(dialog.get_by_role("tooltip")).to_contain_text("central research question")
            touch_page.keyboard.press("Escape")
            expect(dialog.get_by_role("tooltip")).to_have_count(0)
            await_closed = touch_page.get_by_role("button", name="Close", exact=True)
            await_closed.tap()
            expect(dialog).to_have_count(0)
            touch.close()
            print("About dialog Chrome acceptance passed at 1440, 390 and 320px; touch help interaction passed at 390px.")
        finally:
            browser.close()


if __name__ == "__main__":
    main()
