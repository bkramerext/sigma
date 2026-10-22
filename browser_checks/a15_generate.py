"""Real Chrome A15 single-request strategy path against the isolated fixture."""

import json
import os
import re
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
    generation_requests = []
    page.on("pageerror", lambda error: errors.append(str(error)))
    page.on(
        "request",
        lambda request: (
            generation_requests.append(request.url)
            if request.url.endswith("/api/projects/proposals")
            else None
        ),
    )
    page.route(
        "**/api/**",
        lambda route: route.fulfill(
            response=route.fetch(url=route.request.url.replace("127.0.0.1:5173", "127.0.0.1:8002"))
        ),
    )
    page.goto("http://127.0.0.1:5173")
    page.get_by_role("tab", name="Stock", exact=True).click()
    panel = page.get_by_role("tabpanel", name="Stock", exact=True)
    panel.get_by_role("button", name="Open Counting Constrained Binary Strings").click()
    expect(
        page.get_by_role("heading", name=re.compile(r"Counting Constrained Binary Strings \(copy"))
    ).to_be_visible()
    expect(page.locator(".strategy-row")).to_have_count(0)
    path = page.evaluate("new URL(location.href).searchParams.get('path')")
    state = Path(path) / "project.json"
    before = state.read_bytes()
    assert json.loads(before)["strategies"] == []

    def open_generate():
        page.get_by_role("button", name="Generate", exact=True).click()
        return page.locator(".inline-proposal")

    dialog = open_generate()
    expect(dialog.get_by_label("Starting point (optional)")).to_have_value("")
    dialog.get_by_role("button", name="Generate", exact=True).click()
    expect(dialog.get_by_label("Title", exact=True)).to_have_value("Terminal-symbol recurrence")
    expect(dialog).to_contain_text("not independently reviewed or verified")
    assert dialog.locator(".agentic-activity").count() == 0
    assert len(generation_requests) == 1
    assert state.read_bytes() == before
    page.screenshot(path="/tmp/sigma-a15-review-1440.png", full_page=True)
    page.set_viewport_size({"width": 390, "height": 844})
    assert dialog.evaluate("e => e.scrollWidth <= e.clientWidth")
    page.screenshot(path="/tmp/sigma-a15-review-390.png", full_page=True)
    page.set_viewport_size({"width": 1440, "height": 900})
    dialog.get_by_role("button", name="Cancel", exact=True).click()
    expect(page.locator(".strategy-row")).to_have_count(0)
    assert state.read_bytes() == before
    dialog = open_generate()
    dialog.get_by_label("Starting point (optional)").fill("error-fixture")
    dialog.get_by_role("button", name="Generate", exact=True).click()
    expect(dialog.locator('[role="alert"]')).to_contain_text("HTTP 500")
    expect(page.locator(".request-toast")).to_have_count(1)
    expect(page.locator(".strategy-row")).to_have_count(0)
    assert state.read_bytes() == before
    page.get_by_role("button", name="Dismiss request error").click()
    expect(page.locator(".request-toast")).to_have_count(0)
    dialog.get_by_role("button", name="Cancel", exact=True).click()

    dialog = open_generate()
    dialog.get_by_label("Starting point (optional)").fill("timeout-fixture")
    dialog.get_by_role("button", name="Generate", exact=True).click()
    expect(dialog.get_by_role("button", name="Cancel request", exact=True)).to_be_visible()
    dialog.get_by_role("button", name="Cancel request", exact=True).click()
    expect(dialog.locator('[role="alert"]')).to_contain_text("Request cancelled")
    assert state.read_bytes() == before
    dialog.get_by_role("button", name="Cancel", exact=True).click()
    # Playwright's forwarding route can outlive the browser-side abort briefly;
    # the fixture completes its bounded delay before the next request starts.
    page.wait_for_timeout(2200)

    dialog = open_generate()
    dialog.get_by_role("button", name="Generate", exact=True).click()
    expect(dialog.get_by_label("Title", exact=True)).to_have_value("Terminal-symbol recurrence")
    dialog.get_by_label("Title", exact=True).fill("Human accepted recurrence")
    dialog.get_by_role("button", name="Save strategy", exact=True).click()
    expect(page.locator(".strategy-row")).to_have_count(1)
    saved = json.loads(state.read_bytes())
    assert saved["strategies"][0]["title"] == "Human accepted recurrence"
    assert saved["strategies"][0]["provenance"]["provider"] == "openai"
    assert len(generation_requests) == 4
    page.reload()
    expect(page.locator(".strategy-row")).to_have_count(1)

    dialog = open_generate()
    dialog.get_by_role("button", name="Generate", exact=True).click()
    expect(dialog.get_by_label("Title", exact=True)).to_have_value("Position-shift subset count")
    assert len(generation_requests) == 5
    assert json.loads(state.read_bytes()) == saved
    dialog.get_by_role("button", name="Cancel", exact=True).click()
    expect(page.locator(".strategy-row")).to_have_count(1)
    assert source.read_bytes() == original
    assert not errors, errors
    print(
        "PASS real Chrome A15: one bounded request, zero-strategy empty-seed draft, accurate single-call disclosure, cancel without mutation, explicit save/reopen, different existing-context proposal, immutable stock source"
    )
    page.unroute_all(behavior="ignoreErrors")
    browser.close()
