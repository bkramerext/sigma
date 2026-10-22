"""Real Chrome: Samples/Recent Home tabs, direct sample opens, and responsive layout."""

import os
import re
from pathlib import Path

from playwright.sync_api import expect, sync_playwright

SOURCE = Path("samples/nonconsecutive-subset-sums/project.json")
original = SOURCE.read_bytes()

with sync_playwright() as playwright:
    browser = playwright.chromium.launch(
        executable_path=os.environ.get(
            "SIGMA_BROWSER_EXECUTABLE",
            "/Applications/Google Chrome.app/Contents/MacOS/Google Chrome",
        ),
        headless=True,
    )
    page = browser.new_page(viewport={"width": 1280, "height": 720})
    errors: list[str] = []
    page.on("pageerror", lambda error: errors.append(str(error)))

    def forward(route):
        route.fulfill(
            response=route.fetch(url=route.request.url.replace("127.0.0.1:5173", "127.0.0.1:8001"))
        )

    page.route("**/api/**", forward)
    page.goto("http://127.0.0.1:5173/")
    samples_tab = page.get_by_role("tab", name="Samples", exact=True)
    recent_tab = page.get_by_role("tab", name="Recent", exact=True)
    assert page.get_by_role("tab").all_text_contents() == ["Samples", "Recent"]
    expect(samples_tab).to_have_attribute("aria-selected", "true")
    samples_panel = page.get_by_role("tabpanel", name="Samples")
    expect(samples_panel.get_by_text("Nonconsecutive Subset Sums Modulo 3")).to_be_visible()
    expect(samples_panel.get_by_text("Did Jesus Use Cannabis?")).to_be_visible()
    assert (
        samples_panel.locator(".sample-open strong").all_text_contents()[-1]
        == "Did Jesus Use Cannabis?"
    )
    assert "Stock" not in page.locator("body").inner_text()
    assert samples_panel.get_by_text("Shipped template").count() == 0
    row = samples_panel.locator(".sample-open").first
    base_color = row.evaluate("e=>getComputedStyle(e).backgroundColor")
    row.hover()
    assert row.evaluate("e=>getComputedStyle(e).backgroundColor") != base_color

    samples_tab.focus()
    page.keyboard.press("ArrowRight")
    expect(recent_tab).to_be_focused()
    recent_panel = page.get_by_role("tabpanel", name="Recent")
    expect(recent_panel.get_by_text("No recent projects yet.", exact=False)).to_be_visible()
    page.keyboard.press("ArrowLeft")
    expect(samples_tab).to_be_focused()

    samples_panel.get_by_role("button", name="Open Nonconsecutive Subset Sums Modulo 3").click()
    expect(
        page.get_by_role(
            "heading", name=re.compile(r"Nonconsecutive Subset Sums Modulo 3 \(copy(?: \d+)?\)")
        )
    ).to_be_visible()
    assert page.get_by_role("dialog").count() == 0
    expect(page.locator(".strategy-row")).to_have_count(3)
    path = page.evaluate("new URL(location.href).searchParams.get('path')")
    assert Path(path, "project.json").read_bytes() != original
    saved = page.request.post(
        "http://127.0.0.1:8001/api/projects/strategies",
        data={"path": path, "title": "Browser sample addition", "approach": "Keep this strategy"},
    )
    assert saved.status == 201
    page.get_by_role("button", name="Close project").click()
    recent_tab.click()
    expect(
        recent_panel.get_by_text(re.compile(r"Nonconsecutive Subset Sums Modulo 3 \(copy\)"))
    ).to_be_visible()

    for width, height in ((1280, 720), (390, 844), (320, 700)):
        page.set_viewport_size({"width": width, "height": height})
        samples_tab.click()
        expect(samples_panel.get_by_text("Did Jesus Use Cannabis?")).to_be_visible()
        assert page.evaluate("document.documentElement.scrollWidth <= innerWidth")
        page.screenshot(path=f"/tmp/sigma-samples-{width}.png", full_page=True)

    assert SOURCE.read_bytes() == original
    assert not errors, errors
    browser.close()
    print(
        "PASS Chrome Samples/Recent tabs, Samples default, keyboard access, direct open, recent copy, immutable source, and responsive layout"
    )
