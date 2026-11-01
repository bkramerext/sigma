"""Real Chrome checks for issue #441's workflow, persistence, and responsive layout."""

import json
import os
from pathlib import Path
from urllib.parse import urlsplit

from playwright.sync_api import expect, sync_playwright

URL = os.environ.get("SIGMA_BROWSER_BASE_URL", "http://127.0.0.1:5196")
EVIDENCE = Path("docs/evaluations/issue441")


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
            expect(sections.nth(0).locator("summary")).to_have_text("Research Process")
            workflow = dialog.locator('[data-about-section="workflow"]')
            expect(workflow).to_have_attribute("open", "")
            expect(dialog.locator(".about-workflow-stage")).to_have_count(6)
            expect(dialog.locator(".about-workflow")).to_contain_text("Current Understanding")
            expect(dialog.locator(".about-workflow")).to_contain_text(
                "Export research records and reports without a paper."
            )
            expect(dialog.locator(".about-workflow")).to_contain_text(
                "For a draft, review claims, evidence, citations, and limits before PDF or TeX export."
            )
            for stage in dialog.locator(".about-workflow-stage").all():
                expect(stage.locator(".about-workflow-notes li")).to_have_count(2)
            # Native details/summary disclosures must operate with both standard keyboard keys.
            workflow_summary = workflow.locator("summary")
            workflow_summary.focus()
            page.keyboard.press("Enter")
            expect(workflow).not_to_have_attribute("open", "")
            page.wait_for_function(
                "JSON.parse(localStorage.getItem('sigma.aboutDisclosureState.v1')).workflow === false"
            )
            page.keyboard.press("Space")
            expect(workflow).to_have_attribute("open", "")
            expect(workflow_summary).to_be_focused()
            page.wait_for_function(
                "JSON.parse(localStorage.getItem('sigma.aboutDisclosureState.v1')).workflow === true"
            )
            architecture = dialog.locator('[data-about-section="architecture"]')
            architecture_summary = architecture.locator("summary")
            architecture_summary.focus()
            page.keyboard.press("Space")
            expect(architecture).to_have_attribute("open", "")
            page.keyboard.press("Enter")
            expect(architecture).not_to_have_attribute("open", "")
            assert dialog.locator(".about-workflow").evaluate(
                "e => { const stages=[...e.querySelectorAll('.about-workflow-stage')]; const boxes=stages.map(li=>li.querySelector('.about-workflow-step').getBoundingClientRect()); const pitches=boxes.slice(1).map((b,i)=>b.top-boxes[i].top); const lineErrors=stages.slice(0,-1).map((li,i)=>{ const r=li.getBoundingClientRect(), n=li.querySelector('.about-workflow-number').getBoundingClientRect(), next=boxes[i+1], c=getComputedStyle(li,'::after'), left=parseFloat(c.left), top=parseFloat(c.top), bottom=parseFloat(c.bottom), width=parseFloat(c.width); return {start:Math.abs(r.top+top-(n.bottom)), end:Math.abs(r.bottom-bottom-next.top), x:Math.abs(r.left+left+width/2-(n.left+n.width/2))}; }); return boxes.every((b,i)=>stages[i].querySelector('.about-workflow-notes').getBoundingClientRect().left>b.left) && Math.max(...pitches)-Math.min(...pitches)<1.5 && lineErrors.every(x=>x.start<1.5&&x.end<1.5&&x.x<1.5); }"
            ), (
                "Desktop boxes must be evenly pitched, explanatory bullets aligned, and connectors flush with circle and next box"
            )
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
            workflow = dialog.locator('[data-about-section="workflow"]')
            workflow.locator("summary").click()
            for width, screenshot_top, screenshot_bottom in (
                (390, "about-workflow-mobile.png", "about-workflow-mobile-bottom.png"),
                (320, "about-workflow-mobile-320.png", "about-workflow-mobile-320-bottom.png"),
            ):
                page.set_viewport_size({"width": width, "height": 844 if width == 390 else 740})
                expect(workflow).to_have_attribute("open", "")
                expect(workflow.locator(".about-workflow-stage")).to_have_count(6)
                assert workflow.evaluate(
                    "e => [...e.querySelectorAll('.about-workflow-stage')].every(li => { const step = li.querySelector('.about-workflow-step').getBoundingClientRect(); const notes = li.querySelector('.about-workflow-notes').getBoundingClientRect(); return notes.top >= step.bottom && notes.left >= step.left; })"
                ), (width, "Narrow layout must place each stage's notes below its box")
                assert dialog.evaluate("e => e.scrollWidth <= e.clientWidth + 1"), (
                    width,
                    "Narrow About dialog must not overflow horizontally",
                )
                mobile_geometry = workflow.evaluate(
                    "e => { const stages=[...e.querySelectorAll('.about-workflow-stage')], boxes=stages.map(li=>li.querySelector('.about-workflow-step').getBoundingClientRect()), pitches=boxes.slice(1).map((b,i)=>b.top-boxes[i].top), lines=stages.slice(0,-1).map((li,i)=>{const r=li.getBoundingClientRect(),n=li.querySelector('.about-workflow-number').getBoundingClientRect(),next=boxes[i+1],c=getComputedStyle(li,'::after');return {start:Math.abs(r.top+parseFloat(c.top)-n.bottom),end:Math.abs(r.bottom-parseFloat(c.bottom)-next.top),x:Math.abs(r.left+parseFloat(c.left)+parseFloat(c.width)/2-(n.left+n.width/2))}}); return {pitches, lines, notes:stages.map(li=>({bottom:li.querySelector('.about-workflow-notes').getBoundingClientRect().bottom,rowBottom:li.getBoundingClientRect().bottom}))}; }"
                )
                assert (
                    max(mobile_geometry["pitches"]) - min(mobile_geometry["pitches"]) < 1.5
                    and all(
                        line[axis] < 1.5
                        for line in mobile_geometry["lines"]
                        for axis in ("start", "end", "x")
                    )
                    and all(
                        note["bottom"] <= note["rowBottom"] + 1 for note in mobile_geometry["notes"]
                    )
                ), (
                    width,
                    mobile_geometry,
                )
                assert workflow.evaluate(
                    "e => [...e.querySelectorAll('.about-workflow-notes li')].every(li => { const s = getComputedStyle(li); return li.clientWidth > 0 && li.clientHeight > 0 && li.scrollWidth <= li.clientWidth + 1 && li.scrollHeight <= li.clientHeight + 1 && !['hidden', 'clip'].includes(s.overflowX) && !['hidden', 'clip'].includes(s.overflowY) && (!s.webkitLineClamp || s.webkitLineClamp === 'none'); })"
                ), (
                    width,
                    "Workflow explanatory text must wrap fully without clipping or line clamping",
                )
                dialog.evaluate("e => { e.scrollTop = 0; }")
                page.screenshot(path=str(EVIDENCE / screenshot_top))
                final_stage = workflow.locator(".about-workflow-stage").last
                final_stage.evaluate("e => e.scrollIntoView({block: 'end', behavior: 'instant'})")
                expect(final_stage).to_be_in_viewport()
                page.screenshot(path=str(EVIDENCE / screenshot_bottom))
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
                "PASS #441 Research Process, exact two bullets per stage, uniform box pitch, flush connector geometry, desktop/mobile layout, and persistent disclosure state; architecture diagram preserved."
            )
        finally:
            browser.close()


if __name__ == "__main__":
    main()
