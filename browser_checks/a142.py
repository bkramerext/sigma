"""A14.2 real-browser Σ conversion failure, dismiss, and explicit retry check."""

import re
from urllib.parse import urlencode

from playwright.sync_api import expect, sync_playwright

conversion_calls = 0

with sync_playwright() as playwright:
    browser = playwright.chromium.launch(
        executable_path="/Applications/Google Chrome.app/Contents/MacOS/Google Chrome",
        headless=True,
    )
    page = browser.new_page(viewport={"width": 1440, "height": 900})
    page_errors = []
    page.on("pageerror", lambda error: page_errors.append(str(error)))
    page.add_init_script("""
      const originalFetch = window.fetch.bind(window);
      window.fetch = (input, init) => String(input).includes('/api/projects/proposals/config')
        ? new Promise(resolve => setTimeout(() => resolve(originalFetch(input, init)), 700))
        : originalFetch(input, init);
    """)

    def api_route(route):
        global conversion_calls
        request = route.request
        if request.url.endswith("/api/projects/text/convert"):
            conversion_calls += 1
            if conversion_calls == 1:
                route.fulfill(
                    status=400,
                    content_type="application/json",
                    body='{"error":"ChatGPT-plan response was not valid JSON or SSE"}',
                )
                return
        fixture_url = request.url.replace("127.0.0.1:5173", "127.0.0.1:8002")
        route.fulfill(response=route.fetch(url=fixture_url))

    page.route("**/api/**", api_route)
    page.goto("http://127.0.0.1:5173")
    samples_tab = page.get_by_role("tab", name="Samples")
    if samples_tab.get_attribute("aria-selected") != "true":
        samples_tab.click()
    panel = page.get_by_role("tabpanel", name="Samples")
    panel.get_by_role("button", name="Open Nonconsecutive Subset Sums Modulo 3").click()
    expect(
        page.get_by_role(
            "heading", name=re.compile(r"Nonconsecutive Subset Sums Modulo 3 \(copy(?: \d+)?\)")
        )
    ).to_be_visible()

    render = page.get_by_role("button", name="Render research problem as Markdown")
    expect(render).to_have_attribute("title", "Convert to markdown")
    tooltip = page.get_by_role("tooltip")
    render.hover()
    expect(tooltip).to_have_text("Convert to markdown")
    expect(tooltip).to_be_visible()
    source_node = page.locator(".project-intro .objective")
    expect(source_node).to_be_visible()
    source_before = source_node.inner_text()
    path = page.evaluate("new URL(location.href).searchParams.get('path')")
    text_url = "http://127.0.0.1:8002/api/projects/text?" + urlencode(
        {"path": path, "scope": "project"}
    )
    before = page.request.get(text_url).json()
    assert before["source_format"] == "plain" and before["markdown"] is None

    render.click()
    expect(render).to_have_attribute("title", "Converting to markdown")
    expect(tooltip).to_have_text("Converting to markdown")
    expect(tooltip).to_be_visible()
    toast = page.locator(".request-toast")
    expect(toast).to_have_count(1)
    expect(toast).to_contain_text("ChatGPT-plan response was not valid JSON or SSE")
    expect(page.get_by_role("button", name="Dismiss request error")).to_be_visible()
    expect(render).to_have_attribute("aria-pressed", "false")
    expect(page.locator(".project-intro .rendered-text")).to_have_count(0)
    expect(page.locator(".project-intro .objective")).to_have_text(source_before)
    after_failure = page.request.get(text_url).json()
    assert after_failure["source_digest"] == before["source_digest"]
    assert after_failure["markdown"] is None

    page.get_by_role("button", name="Dismiss request error").click()
    expect(toast).to_have_count(0)
    page.get_by_role("button", name="Render research problem as Markdown").click()
    expect(page.locator(".project-intro .rendered-text")).to_be_visible()
    rendered_toggle = page.get_by_role("button", name="Show plain research problem")
    expect(rendered_toggle).to_have_attribute("title", "Show plain text")
    rendered_toggle.hover()
    expect(tooltip).to_have_text("Show plain text")
    expect(tooltip).to_be_visible()
    assert conversion_calls == 2
    after_retry = page.request.get(text_url).json()
    assert after_retry["source_digest"] == before["source_digest"]
    assert after_retry["markdown"]["current"] is True
    assert after_retry["markdown"]["body"]
    assert not page_errors, page_errors
    page.screenshot(path="/tmp/sigma-a142-conversion-1440.png", full_page=True)
    browser.close()

print(
    "PASS real Chrome: exact Σ tooltip, one dismissible failure, plain-source retention, no failed artifact, and explicit successful retry"
)
