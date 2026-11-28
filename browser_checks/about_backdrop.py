"""Real Chrome About backdrop, focus and research architecture checks."""

import os

from playwright.sync_api import expect, sync_playwright

UI = os.environ.get("SIGMA_BROWSER_BASE_URL", "http://127.0.0.1:5187").rstrip("/")
SCREENSHOTS = os.environ.get("SIGMA_ABOUT_SCREENSHOT_DIR", "/tmp")

with sync_playwright() as playwright:
    browser = playwright.chromium.launch(
        executable_path=os.environ.get(
            "SIGMA_BROWSER_EXECUTABLE",
            "/Applications/Google Chrome.app/Contents/MacOS/Google Chrome",
        ),
        headless=True,
    )
    page = browser.new_page(viewport={"width": 1280, "height": 800})
    page.route(
        "**/api/**",
        lambda route: route.fulfill(
            status=200,
            content_type="application/json",
            body='{"enabled":false,"ready":true,"authenticated":true,"projects":[],"accounts":[],"status":"disconnected"}',
        ),
    )
    page.goto(UI + "/")
    opener = page.get_by_role("button", name="About SIGMA", exact=True)
    opener.click()
    dialog = page.get_by_role("dialog", name="About SIGMA")
    expect(dialog).to_be_visible()
    page.mouse.click(1, 1)
    expect(dialog).to_have_count(0)
    expect(opener).to_be_focused()

    for width, height in ((1440, 960), (390, 844), (320, 740)):
        page.set_viewport_size({"width": width, "height": height})
        opener.click()
        expect(dialog).to_be_visible()
        overview = dialog.locator('[data-about-section="researchArchitecture"]')
        expect(overview.locator("summary")).to_have_text("Research Information Architecture")
        expect(dialog.locator('[data-about-section="architecture"] summary')).to_have_text(
            "Multi-Agent Research Process"
        )
        expect(overview).not_to_have_attribute("open", "")
        overview.locator("summary").click()
        diagram = overview.get_by_role("img", name="Research information architecture and evidence flow")
        expect(diagram).to_be_visible()
        expect(diagram.locator("desc")).to_contain_text(
            "Their contributions return to the persistent record for possible later inquiry."
        )
        for label in (
            "Persistent Research",
            "Context Selection",
            "Bounded Research Session",
            "Investigator",
            "Skeptic",
            "Supervisor (optional)",
            "Current Understanding",
            "Research Paper",
            "Research Q/A",
            "ELI5",
            "Research Perspectives",
            "Save contributions",
        ):
            expect(diagram.locator("text").filter(has_text=label)).to_have_count(1)
        context_card = diagram.locator("g").filter(
            has=page.locator("text", has_text="Context Selection")
        )
        record_card = diagram.locator("g").filter(
            has=page.locator("text", has_text="Persistent Research")
        )
        assert float(context_card.locator("rect").get_attribute("x")) < float(
            record_card.locator("rect").get_attribute("x")
        )
        # These routes connect the record, context, participants, and grouped perspectives.
        for route in (
            "M258 175 H214",
            "M119 235 V270.5",
            "M93 498 V462.5",
            "M148 462.5 V498",
            "M214 428.5 H231 V218 H258",
            "M367 235 V270.5",
        ):
            expect(diagram.locator(f'path[d="{route}"][marker-end]')).to_have_count(1)
        perspectives = diagram.locator('[data-about-perspectives="true"]')
        expect(perspectives.locator("path[marker-end]")).to_have_count(0)
        expect(diagram.locator("path[marker-end]")).to_have_count(9)
        for label in ("Current Understanding", "Research Q/A", "Research Paper", "ELI5"):
            expect(perspectives.locator("text").filter(has_text=label)).to_have_count(1)
        expect(perspectives.locator('g[aria-hidden="true"]')).to_have_count(1)
        expect(overview).to_contain_text("not a new database or a collection of verified truths")
        expect(overview).to_contain_text("omitted evidence is not resolved or verified")
        expect(overview.locator("figcaption")).to_contain_text("not a prescribed execution sequence")
        expect(overview.locator("figcaption")).to_contain_text("architectural direction")
        expect(overview).to_contain_text("not unbounded autonomous self-direction")
        expect(overview).to_contain_text("subject to human review")
        expect(overview.locator("button, a, input")).to_have_count(0)
        expect(dialog.locator(".about-provenance-disclosure summary")).to_have_text(
            "Vision for Investigation Provenance"
        )
        scrollport = overview.locator(".about-provenance-diagram-scroll")
        expect(scrollport).to_have_attribute("tabindex", "0")
        metrics = scrollport.evaluate("e => ({scroll: e.scrollWidth, client: e.clientWidth})")
        if width > 600:
            assert metrics["scroll"] <= metrics["client"] + 1, metrics
        else:
            assert metrics["scroll"] > metrics["client"], metrics
        assert dialog.evaluate("e => e.scrollWidth <= e.clientWidth + 1"), width
        assert page.evaluate("document.documentElement.scrollWidth <= innerWidth"), width
        scrollport.screenshot(path=f"{SCREENSHOTS}/sigma-about-research-architecture-{width}.png")
        overview.locator("summary").click()
        expect(overview).not_to_have_attribute("open", "")
        page.keyboard.press("Escape")
        expect(dialog).to_have_count(0)
        expect(opener).to_be_focused()

    browser.close()

print("PASS real Chrome About backdrop and research architecture at desktop and mobile widths.")
