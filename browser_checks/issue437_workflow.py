"""Real Chrome checks for issue #437's workflow, persistence, and responsive layout."""

import json
import os
from pathlib import Path
from urllib.parse import urlsplit

from playwright.sync_api import expect, sync_playwright

URL = os.environ.get("SIGMA_BROWSER_BASE_URL", "http://127.0.0.1:5196")
EVIDENCE = Path("docs/evaluations/issue437")


def main() -> None:
    EVIDENCE.mkdir(parents=True, exist_ok=True)
    with sync_playwright() as playwright:
        browser = playwright.chromium.launch(
            executable_path=os.environ.get(
                "SIGMA_BROWSER_EXECUTABLE",
                "/Applications/Google Chrome.app/Contents/MacOS/Google Chrome",
            ),
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
                    route.fulfill(
                        status=200,
                        content_type="application/json",
                        body=json.dumps({"projects": []}),
                    )
                elif path == "/api/ai/connection":
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
                else:
                    route.continue_()

            page.route("**/api/**", home_data)
            page.goto(URL)
            expect(page.get_by_role("heading", name="Projects")).to_be_visible()
            welcome = page.locator("#invitation-welcome-dialog")
            if welcome.count() and welcome.is_visible():
                welcome.get_by_role("button", name="Let's get started").click()
            opener = page.get_by_role("button", name="About")
            opener.click()
            dialog = page.get_by_role("dialog", name="About SIGMA")
            expect(dialog).to_be_visible()
            sections = dialog.locator(".about-dialog-content > details")
            feedback = dialog.locator('[data-about-section="feedback"]')
            has_feedback_section = feedback.count() == 1
            expect(sections).to_have_count(4 + int(has_feedback_section))
            expect(sections.nth(0).locator("summary")).to_have_text("How SIGMA works")
            workflow = dialog.locator('[data-about-section="workflow"]')
            expect(workflow).to_have_attribute("open", "")
            expect(dialog.locator(".about-workflow-stage")).to_have_count(6)
            expect(dialog.locator(".about-workflow")).to_contain_text("Current Understanding")
            expect(dialog.locator(".about-workflow")).to_contain_text(
                "You choose whether and where to share or publish."
            )
            assert dialog.locator(".about-workflow").evaluate(
                "e => [...e.querySelectorAll('.about-workflow-stage')].every(li => { const step = li.querySelector('.about-workflow-step').getBoundingClientRect(); const notes = li.querySelector('.about-workflow-notes').getBoundingClientRect(); return step.left < notes.left && Math.abs(step.top + step.height / 2 - (notes.top + notes.height / 2)) < 35; })"
            ), "Desktop stage boxes and explanatory bullets must align in two columns"
            assert dialog.evaluate("e => e.scrollWidth <= e.clientWidth + 1")
            page.screenshot(path=str(EVIDENCE / "about-workflow-desktop.png"), full_page=True)

            # First-visit defaults and saved choices across dialog teardown/reopen.
            features = dialog.locator('[data-about-section="features"]')
            architecture = dialog.locator('[data-about-section="architecture"]')
            provenance = dialog.locator('[data-about-section="provenance"]')
            expect(features).not_to_have_attribute("open", "")
            expect(architecture).not_to_have_attribute("open", "")
            expect(provenance).not_to_have_attribute("open", "")
            features.locator("summary").click()
            architecture.locator("summary").click()
            if has_feedback_section:
                expect(feedback).not_to_have_attribute("open", "")
                feedback.locator("summary").click()
            workflow.locator("summary").click()
            page.wait_for_function(
                "JSON.parse(localStorage.getItem('sigma.aboutDisclosureState.v1')).workflow === false"
            )
            page.get_by_role("button", name="Close").click()
            expect(dialog).not_to_be_visible()
            opener.click()
            expect(workflow).not_to_have_attribute("open", "")
            expect(features).to_have_attribute("open", "")
            expect(architecture).to_have_attribute("open", "")
            expect(provenance).not_to_have_attribute("open", "")
            if has_feedback_section:
                expect(feedback).to_have_attribute("open", "")
            page.reload()
            opener = page.get_by_role("button", name="About")
            opener.click()
            dialog = page.get_by_role("dialog", name="About SIGMA")
            expect(dialog.locator('[data-about-section="workflow"]')).not_to_have_attribute(
                "open", ""
            )
            expect(dialog.locator('[data-about-section="features"]')).to_have_attribute("open", "")
            expect(dialog.locator('[data-about-section="architecture"]')).to_have_attribute(
                "open", ""
            )
            if has_feedback_section:
                expect(dialog.locator('[data-about-section="feedback"]')).to_have_attribute(
                    "open", ""
                )
            expect(dialog.locator('[data-about-section="provenance"]')).not_to_have_attribute(
                "open", ""
            )

            # Narrow layout stacks each set of bullets below its own stage box.
            page.set_viewport_size({"width": 390, "height": 844})
            workflow = dialog.locator('[data-about-section="workflow"]')
            workflow.locator("summary").click()
            expect(workflow.locator(".about-workflow-stage")).to_have_count(6)
            assert workflow.evaluate(
                "e => [...e.querySelectorAll('.about-workflow-stage')].every(li => { const step = li.querySelector('.about-workflow-step').getBoundingClientRect(); const notes = li.querySelector('.about-workflow-notes').getBoundingClientRect(); return notes.top >= step.bottom && notes.left >= step.left; })"
            ), "Narrow layout must place each stage's notes below its box"
            assert dialog.evaluate("e => e.scrollWidth <= e.clientWidth + 1"), (
                "Narrow About dialog must not overflow horizontally"
            )
            page.screenshot(path=str(EVIDENCE / "about-workflow-mobile.png"), full_page=True)
            expect(dialog.locator(".about-architecture")).to_be_attached()
            page.get_by_role("button", name="Close").click()
            page.evaluate(
                "localStorage.setItem('sigma.aboutDisclosureState.v1', JSON.stringify({retired: true, workflow: 'open', features: 'closed'}))"
            )
            page.reload()
            page.get_by_role("button", name="About").click()
            fallback = page.get_by_role("dialog", name="About SIGMA")
            expect(fallback.locator('[data-about-section="workflow"]')).to_have_attribute(
                "open", ""
            )
            expect(fallback.locator('[data-about-section="features"]')).not_to_have_attribute(
                "open", ""
            )
            assert not errors, errors
            print(
                "PASS #437 workflow diagram, desktop/mobile layout, first-visit defaults, close/reopen and reload persistence; preserved architecture diagram."
            )
        finally:
            browser.close()


if __name__ == "__main__":
    main()
