"""Real Chrome acceptance for the Home About dialog, including narrow and touch layouts."""

import json
import os
from urllib.parse import urlsplit

from playwright.sync_api import expect, sync_playwright

URL = os.environ.get("SIGMA_BROWSER_BASE_URL", "http://127.0.0.1:5196")


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
                expect(welcome).to_have_count(0)
            opener = page.get_by_role("button", name="About")
            for width, height in ((1440, 960), (390, 844), (320, 740)):
                page.set_viewport_size({"width": width, "height": height})
                credit = page.locator(".home-art-credit")
                expect(credit).to_be_visible()
                assert credit.evaluate("e => getComputedStyle(e).textTransform") == "none"
                opener.click()
                dialog = page.get_by_role("dialog", name="About SIGMA")
                expect(dialog).to_be_visible()
                page.screenshot(path=f"/tmp/sigma-about-collapsed-{width}.png", full_page=False)
                expect(dialog.locator(".about-intro")).to_be_visible()
                expect(dialog.get_by_role("navigation", name="Legal information")).to_be_visible()
                region = dialog.locator(".about-dialog-content > details").filter(
                    has=page.locator("summary", has_text="Key Features")
                )
                expect(region).to_have_count(1)
                expect(region).not_to_have_attribute("open", "")
                region.locator("summary").click()
                expect(region).to_have_attribute("open", "")
                architecture = dialog.locator(".about-architecture-disclosure")
                architecture.locator("summary").click()
                expect(architecture).to_have_attribute("open", "")
                expect(dialog.locator("#about-architecture-details")).to_be_visible()
                provenance = dialog.locator(".about-provenance-disclosure")
                expect(provenance).not_to_have_attribute("open", "")
                provenance.locator("summary").click()
                expect(provenance).to_have_attribute("open", "")
                expect(dialog.locator("#about-provenance-details")).to_be_visible()
                diagram = provenance.locator("svg.about-provenance-diagram")
                expect(diagram).to_be_visible()
                expect(diagram.locator("marker")).to_have_count(5)
                assert diagram.locator("path[marker-end]").count() >= 11
                expect(provenance).to_contain_text("The investigation is the enduring artifact.")
                expect(provenance).to_contain_text("Understanding")
                expect(provenance).to_contain_text("Published TeX")
                expect(provenance).to_contain_text("Beyond a linear LLM conversation.")
                expect(provenance).to_contain_text("Prompt → Response → Prompt → Response")
                expect(provenance).to_contain_text("A branching, revisitable research record")
                scrollport = provenance.locator(".about-provenance-diagram-scroll")
                scroll_metrics = scrollport.evaluate(
                    "e => ({scroll: e.scrollWidth, client: e.clientWidth})"
                )
                if width > 600:
                    assert scroll_metrics["scroll"] <= scroll_metrics["client"] + 1, (
                        width,
                        "Desktop provenance diagram must fit without scrolling",
                        scroll_metrics,
                    )
                else:
                    assert scroll_metrics["scroll"] > scroll_metrics["client"], (
                        width,
                        "Narrow-screen provenance diagram remains scrollable for legibility",
                        scroll_metrics,
                    )
                assert dialog.evaluate("e => e.scrollWidth <= e.clientWidth + 1"), (
                    width,
                    "About dialog must not overflow horizontally",
                )
                provenance.locator("summary").click()
                expect(provenance).not_to_have_attribute("open", "")
                expect(dialog.get_by_role("navigation", name="Legal information")).to_contain_text(
                    "Terms of Service"
                )
                expect(dialog.locator(".about-intro")).to_contain_text(
                    "research workbench for exploring answers"
                )
                for title in (
                    "Multi-Strategy Exploration",
                    "Multiple Research Agents",
                    "Research History",
                    "Experimental LaTeX Paper Generation",
                ):
                    expect(dialog.get_by_role("heading", name=title, exact=True)).to_be_visible()
                expect(dialog.locator(".about-build-commit")).to_contain_text(
                    __import__("re").compile(r"Build [0-9a-f]{7}")
                )
                expect(dialog.locator(".about-session-toggle")).to_have_attribute(
                    "aria-expanded", "false"
                )
                session_toggle = dialog.locator(".about-session-toggle")
                expect(session_toggle).to_have_text("Show")
                expect(session_toggle).to_have_count(1)
                details = dialog.locator("#about-session-details")
                expect(details).to_be_hidden()
                expect(details.locator(".about-exploration-space")).to_be_hidden()
                expect(details.locator(".about-shared-budget")).to_be_hidden()
                expect(
                    dialog.locator(".about-session-frame > .about-exploration-space")
                ).to_have_count(0)
                expect(dialog.locator(".about-session-frame > .about-shared-budget")).to_have_count(
                    0
                )
                session_toggle.hover()
                agent_toggle_style = session_toggle.evaluate(
                    "e => ({background: getComputedStyle(e).backgroundImage, text: getComputedStyle(e).color})"
                )
                assert (
                    "50, 117, 164" in agent_toggle_style["background"]
                    and agent_toggle_style["text"] == "rgb(255, 255, 255)"
                ), (width, agent_toggle_style)
                arrow_box = dialog.locator(".about-agent-review-arrow").bounding_box()
                button_box = session_toggle.bounding_box()
                assert arrow_box and button_box and arrow_box["width"] > button_box["width"], (
                    width,
                    arrow_box,
                    button_box,
                )
                assert (
                    button_box["x"] < arrow_box["x"] + arrow_box["width"]
                    and button_box["x"] + button_box["width"] > arrow_box["x"]
                ), (width, arrow_box, button_box)
                session_toggle.click()
                expect(session_toggle).to_have_attribute("aria-expanded", "true")
                expect(session_toggle).to_have_text("Hide")
                details = dialog.locator("#about-session-details")
                expect(details.locator(".about-multi-agent-intro")).to_contain_text("one strategy")
                expect(details.locator(".about-multi-agent-intro")).to_contain_text(
                    "instead of ending after the first answer"
                )
                expect(dialog.locator(".about-strategy-parallel-note")).to_contain_text(
                    "Press Play"
                )
                strategy_rounds = dialog.locator(".about-strategy-round")
                expect(strategy_rounds).to_have_count(3)
                for i in range(3):
                    expect(strategy_rounds.nth(i)).to_contain_text("Investigator")
                    expect(strategy_rounds.nth(i)).to_contain_text("Skeptic")
                expect(details.locator(".about-shared-budget")).to_be_visible()
                expect(details.locator(".about-shared-budget")).to_contain_text("Why repeat?")
                expect(details.locator(".about-exploration-space")).to_be_visible()
                expect(details.locator(".about-exploration-row")).to_have_count(3)
                expect(details.locator(".about-exploration-round")).to_have_count(9)
                expect(details.locator(".about-exploration-space")).to_contain_text(
                    "maximum number of turns for the whole session"
                )
                expect(dialog.locator(".about-evidence-report-note")).to_contain_text(
                    "Export the research or write a report"
                )
                expect(
                    details.get_by_role("heading", name="How an idea grows over six agent turns")
                ).to_be_visible()
                expect(details.locator(".about-agent-round")).to_have_count(3)
                expect(details.locator(".about-agent-turn")).to_have_count(6)
                expect(details.locator(".about-agent-round-pair")).to_have_count(3)
                expect(details.locator(".about-agent-round-heading")).to_have_count(3)
                expect(details.locator(".about-round-definition")).to_contain_text(
                    "One research round"
                )
                expect(details.locator(".about-round-definition")).to_contain_text("One agent turn")
                expect(details.locator(".about-agent-instantiation h5")).to_have_text(
                    "One strategy · Three rounds · Six turns"
                )
                for turn in range(1, 7):
                    expect(details.locator(".about-turn-number").nth(turn - 1)).to_have_text(
                        f"TURN {turn}"
                    )
                for round_number in range(1, 4):
                    expect(
                        details.locator(".about-agent-round-heading").nth(round_number - 1)
                    ).to_contain_text(f"Round {round_number}")
                expect(dialog.locator(".about-session-exploration-example")).to_contain_text(
                    "9 possible rounds, or 18 agent turns"
                )
                expect(dialog.locator(".about-session-exploration-example")).to_contain_text(
                    "12-turn limit"
                )
                expect(dialog.locator(".about-session-exploration-example")).to_contain_text(
                    "at most 6 complete rounds"
                )
                expect(
                    details.locator(
                        ".about-agent-turn .about-diagram-node-title", has_text="Investigator"
                    )
                ).to_have_count(3)
                expect(
                    details.locator(
                        ".about-agent-turn .about-diagram-node-title", has_text="Skeptic"
                    )
                ).to_have_count(3)
                expect(details.locator(".about-agent-return")).to_have_count(2)
                expect(details.locator(".about-agent-return").nth(0)).to_contain_text(
                    "feedback shapes the next attempt"
                )
                expect(details.locator(".about-agent-return svg path")).to_have_count(2)
                expect(details.locator(".about-agent-instantiation-note")).to_contain_text(
                    "arguments, challenges, and results for review"
                )
                expect(details.locator(".about-multiple-sessions-note")).to_contain_text(
                    "revisit a strategy with new evidence"
                )
                expect(details.locator(".about-multiple-sessions-note")).to_contain_text(
                    "compare what changed"
                )
                expect(details.get_by_text("Coordinator", exact=False)).to_have_count(0)
                expanded_style = details.evaluate(
                    "e => ({background: getComputedStyle(e).backgroundImage, border: getComputedStyle(e).borderColor})"
                )
                assert (
                    "20, 43, 61" in expanded_style["background"]
                    and expanded_style["border"] == "rgb(76, 131, 168)"
                ), (width, expanded_style)
                page.screenshot(
                    path=f"/tmp/sigma-about-agents-expanded-{width}.png", full_page=False
                )
                session_toggle.click()
                expect(session_toggle).to_have_attribute("aria-expanded", "false")
                expect(session_toggle).to_have_text("Show")
                expect(details).to_be_hidden()
                expect(details.locator(".about-exploration-space")).to_be_hidden()
                # Help affordances are separate from expansion controls.
                strategy_a = dialog.locator('[data-about-info-node="strategyA"]')
                page.mouse.move(5, 5)
                page.wait_for_timeout(160)
                strategy_a.scroll_into_view_if_needed()
                page.wait_for_timeout(220)
                strategy_node = strategy_a.locator(".about-strategy-node")
                strategy_a.hover()
                expect(dialog.get_by_role("tooltip")).to_be_visible()
                before_hover = strategy_node.bounding_box()
                hover_style = strategy_node.evaluate(
                    "e => ({background: getComputedStyle(e).backgroundImage, title: getComputedStyle(e.querySelector('.about-diagram-node-title')).color, subtitle: getComputedStyle(e.querySelector('.about-diagram-node-subtitle')).color})"
                )
                assert hover_style["background"] != "none", (width, hover_style)
                assert (
                    hover_style["title"] == "rgb(240, 201, 153)"
                    and hover_style["subtitle"] == "rgb(185, 194, 204)"
                ), (width, hover_style)
                tip = dialog.get_by_role("tooltip")
                expect(tip).to_be_visible()
                assert "objective is bounded" in tip.inner_text(), (width, tip.inner_text())
                tipbox = tip.bounding_box()
                assert tipbox and tipbox["x"] >= 0 and tipbox["x"] + tipbox["width"] <= width, (
                    width,
                    tipbox,
                )
                dialog_box = dialog.bounding_box()
                assert (
                    dialog_box
                    and tipbox["y"] >= dialog_box["y"]
                    and tipbox["y"] + tipbox["height"] <= dialog_box["y"] + dialog_box["height"]
                ), (width, dialog_box, tipbox)
                after_hover = strategy_node.bounding_box()
                assert after_hover and abs(before_hover["y"] - after_hover["y"]) < 1, (
                    width,
                    before_hover,
                    after_hover,
                    dialog.evaluate("e => e.scrollTop"),
                    page.evaluate("scrollY"),
                    tipbox,
                )
                page.screenshot(path=f"/tmp/sigma-about-hover-popup-{width}.png")
                page.keyboard.press("Escape")
                expect(dialog.get_by_role("tooltip")).to_have_count(0)
                architecture.locator("summary").focus()
                help_button = dialog.get_by_role("button", name="Explain Research Project")
                help_button.focus()
                expect(dialog.get_by_role("tooltip")).to_contain_text("central research question")
                page.keyboard.press("Escape")
                expect(dialog).to_be_visible()
                page.screenshot(path=f"/tmp/sigma-about-expanded-{width}.png", full_page=False)
                assert dialog.evaluate("e => e.scrollWidth <= e.clientWidth"), (
                    width,
                    "dialog overflow",
                )
                assert page.evaluate("document.documentElement.scrollWidth <= innerWidth"), (
                    width,
                    "page overflow",
                )
                page.mouse.click(1, 1)
                expect(dialog).to_have_count(0)
                expect(opener).to_be_focused()
                opener.click()
                dialog = page.get_by_role("dialog", name="About SIGMA")
                expect(dialog).to_be_visible()
                page.get_by_role("button", name="Close", exact=True).click()
                expect(dialog).to_have_count(0)
                expect(opener).to_be_focused()
            assert not errors, errors

            touch = browser.new_context(
                viewport={"width": 390, "height": 844}, is_mobile=True, has_touch=True
            )
            touch_page = touch.new_page()
            touch_page.route("**/api/**", home_data)
            touch_page.goto(URL, wait_until="networkidle")
            touch_welcome = touch_page.locator("#invitation-welcome-dialog")
            if touch_welcome.count() and touch_welcome.is_visible():
                touch_welcome.get_by_role("button", name="Let's get started").tap()
                expect(touch_welcome).to_have_count(0)
            touch_page.get_by_role("button", name="About").tap()
            dialog = touch_page.get_by_role("dialog", name="About SIGMA")
            arch = dialog.locator(".about-architecture-disclosure")
            arch.locator("summary").tap()
            expect(arch.locator("#about-architecture-details")).to_be_visible()
            dialog.locator(".about-session-toggle").tap()
            expect(dialog.locator("#about-session-details")).to_be_visible()
            button = dialog.get_by_role("button", name="Explain Research Project")
            button.tap()
            expect(dialog.get_by_role("tooltip")).to_contain_text("central research question")
            touch_page.keyboard.press("Escape")
            expect(dialog.get_by_role("tooltip")).to_have_count(0)
            await_closed = touch_page.get_by_role("button", name="Close", exact=True)
            await_closed.tap()
            expect(dialog).to_have_count(0)
            touch.close()
            print(
                "About dialog Chrome acceptance passed at 1440, 390 and 320px; touch help interaction passed at 390px."
            )
        finally:
            browser.close()


if __name__ == "__main__":
    main()
