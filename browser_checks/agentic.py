"""Real Chrome A14 stock-project path against the isolated provider fixture."""

import json
import os
from pathlib import Path

from playwright.sync_api import expect, sync_playwright

source = Path("examples/counting-constrained-binary-strings/project.json")
original = source.read_bytes()
with sync_playwright() as playwright:
    browser = playwright.chromium.launch(
        executable_path=os.environ.get(
            "SIGMA_BROWSER_EXECUTABLE",
            "/Applications/Google Chrome.app/Contents/MacOS/Google Chrome",
        ),
        headless=True,
    )
    context = browser.new_context(viewport={"width": 1440, "height": 900})
    page = context.new_page()
    errors = []
    page.on("pageerror", lambda error: errors.append(str(error)))
    page.route(
        "**/api/**",
        lambda route: route.fulfill(
            response=route.fetch(url=route.request.url.replace("127.0.0.1:5173", "127.0.0.1:8001"))
        ),
    )
    page.goto("http://127.0.0.1:5173")
    panel = page.get_by_role("tabpanel", name="Stock Projects")
    panel.get_by_role("button", name="Open Counting Constrained Binary Strings").click()
    expect(
        page.get_by_role("heading", name="Counting Constrained Binary Strings", exact=True)
    ).to_be_visible()
    expect(page.locator(".strategy-row")).to_have_count(0)
    path = page.evaluate("new URL(location.href).searchParams.get('path')")
    state = Path(path) / "project.json"
    before = state.read_bytes()
    assert before == original

    def open_generate():
        page.get_by_label("New Strategy options", exact=True).click()
        page.get_by_role("button", name="Generate with AI", exact=True).click()
        return page.get_by_role("dialog", name="Generate a strategy")

    dialog = open_generate()
    expect(dialog.get_by_label("Starting point (optional)")).to_have_value("")
    dialog.get_by_role("button", name="Generate draft", exact=True).click()
    expect(dialog.locator(".agentic-activity li").first).to_contain_text("Candidate proposed")
    expect(dialog.get_by_label("Title", exact=True)).to_have_value("Terminal-symbol recurrence")
    assert state.read_bytes() == before
    ledger = dialog.locator(".agentic-activity > ol > li").all_text_contents()
    assert ledger[0] == "Candidate proposed" and ledger[1].startswith("The proposed mechanism")
    assert ledger[-1].startswith("Distinct candidate")
    page.emulate_media(reduced_motion="reduce")
    assert dialog.locator(".agentic-filament").count() == 0
    page.screenshot(path="/tmp/sigma-a14-review-1440.png", full_page=True)
    page.set_viewport_size({"width": 390, "height": 844})
    assert dialog.evaluate("e => e.scrollWidth <= e.clientWidth")
    page.screenshot(path="/tmp/sigma-a14-review-390.png", full_page=True)
    page.set_viewport_size({"width": 1440, "height": 900})
    dialog.get_by_role("button", name="Cancel", exact=True).click()
    expect(page.locator(".strategy-row")).to_have_count(0)
    assert state.read_bytes() == before

    dialog = open_generate()
    dialog.get_by_role("button", name="Generate draft", exact=True).click()
    expect(dialog.get_by_label("Title", exact=True)).to_have_value("Terminal-symbol recurrence")
    dialog.get_by_label("Title", exact=True).fill("Human accepted recurrence")
    dialog.get_by_role("button", name="Save strategy", exact=True).click()
    expect(page.locator(".strategy-row")).to_have_count(1)
    saved = json.loads(state.read_bytes())
    assert saved["strategies"][0]["provenance"]["model"] == "gpt-6.1-sol"
    page.reload()
    expect(page.locator(".strategy-row")).to_have_count(1)
    dialog = open_generate()
    dialog.get_by_role("button", name="Generate draft", exact=True).click()
    expect(dialog.get_by_label("Title", exact=True)).to_have_value("Position-shift subset count")
    expect(dialog.locator(".agentic-review")).to_contain_text("different counting mechanism")
    assert json.loads(state.read_bytes()) == saved
    dialog.get_by_role("button", name="Cancel", exact=True).click()
    dialog = open_generate()
    dialog.get_by_label("Starting point (optional)").fill("timeout-fixture")
    dialog.get_by_role("button", name="Generate draft", exact=True).click()
    expect(dialog.get_by_role("button", name="Cancel request", exact=True)).to_be_visible()
    dialog.get_by_role("button", name="Cancel request", exact=True).click()
    expect(dialog.get_by_text("Request cancelled locally", exact=False)).to_be_visible()
    assert json.loads(state.read_bytes()) == saved
    assert source.read_bytes() == original
    assert not errors, errors
    print(
        "PASS real Chrome: zero-pool stock run, truthful progress, unsaved cancel, explicit save/reopen, second distinct mechanism, immutable source"
    )
    page.unroute_all(behavior="ignoreErrors")
    browser.close()
