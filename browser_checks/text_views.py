"""A15 real Chrome Plain/Markdown/Rendered checks with a mock provider only."""

import os
from pathlib import Path

from playwright.sync_api import expect, sync_playwright

source = Path("examples/nonconsecutive-subset-sums/investigation.json")
original = source.read_bytes()
with sync_playwright() as playwright:
    browser = playwright.chromium.launch(
        executable_path=os.environ.get(
            "SIGMA_BROWSER_EXECUTABLE",
            "/Applications/Google Chrome.app/Contents/MacOS/Google Chrome",
        ),
        headless=True,
    )
    page = browser.new_page(viewport={"width": 1440, "height": 900})
    errors = []
    conversions = []
    page.on("pageerror", lambda error: errors.append(str(error)))
    page.on(
        "request",
        lambda request: (
            conversions.append(request.url)
            if request.url.endswith("/api/investigations/text/convert")
            else None
        ),
    )
    page.route(
        "**/api/**",
        lambda route: route.fulfill(
            response=route.fetch(url=route.request.url.replace("127.0.0.1:5173", "127.0.0.1:8001"))
        ),
    )
    page.goto("http://127.0.0.1:5173")
    panel = page.get_by_role("tabpanel", name="Stock Investigations")
    panel.get_by_role("button", name="Open Nonconsecutive Subset Sums Modulo 3").click()
    expect(
        page.get_by_role("heading", name="Nonconsecutive Subset Sums Modulo 3", exact=True)
    ).to_be_visible()
    assert (
        page.get_by_role("heading", name="Nonconsecutive Subset Sums Modulo 3", exact=True).count()
        == 1
    )
    expect(page.locator(".investigation-eyebrow")).to_have_text("Investigation description")
    assert page.locator(".investigation-intro .edit-investigation-button").count() == 0
    path = page.evaluate("new URL(location.href).searchParams.get('path')")
    state = Path(path) / "investigation.json"
    before = state.read_bytes()
    view = page.get_by_role("combobox", name="View research problem")
    expect(view).to_have_value("plain")
    expect(page.get_by_role("button", name="Edit Plain description")).to_contain_text("a_n/F_{n+2}")
    page.get_by_role("button", name="Edit Plain description").focus()
    page.get_by_role("button", name="Edit Plain description").press("Enter")
    plain_editor = page.get_by_label("Edit Plain source")
    expect(plain_editor).to_be_focused()
    plain_editor.fill("Unsaved direct edit")
    plain_editor.press("Escape")
    expect(page.get_by_role("button", name="Edit Plain description")).to_be_focused()
    assert state.read_bytes() == before
    assert not conversions and state.read_bytes() == before
    page.route(
        "**/api/investigations/text/convert",
        lambda route: route.fulfill(
            status=503,
            content_type="application/json",
            body='{"error":"Mock provider unavailable"}',
        ),
    )
    view.select_option("markdown")
    expect(page.get_by_role("alert")).to_contain_text("Mock provider unavailable")
    assert state.read_bytes() == before
    page.unroute("**/api/investigations/text/convert")
    page.get_by_role("button", name="Retry conversion").click()
    expect(page.get_by_role("status").filter(has_text="Converting to Markdown")).to_be_visible()
    expect(page.locator(".investigation-intro pre.literal-markdown")).to_contain_text(r"$n \ge 0$")
    expect(page.locator(".investigation-intro pre.literal-markdown")).to_contain_text(
        r"\frac{a_n}{F_{n+2}}"
    )
    assert state.read_bytes() == before
    assert (Path(path) / "text-representations.json").is_file()
    count = len(conversions)
    view.select_option("rendered")
    expect(page.locator(".investigation-intro .rendered-text .katex").first).to_be_visible()
    assert page.locator(".investigation-intro .rendered-text .katex-html").count() > 0
    page.get_by_role("button", name="Edit Markdown description").press("Enter")
    expect(view).to_have_value("markdown")
    expect(page.get_by_label("Edit Markdown source")).to_be_focused()
    page.get_by_label("Edit Markdown source").press("Escape")
    expect(view).to_have_value("rendered")
    view.select_option("plain")
    expect(page.get_by_role("button", name="Edit Plain description")).to_contain_text("n >= 0")
    view.select_option("rendered")
    assert len(conversions) == count
    page.screenshot(path="/tmp/sigma-a15-rendered-1440.png", full_page=True)
    page.set_viewport_size({"width": 390, "height": 844})
    assert page.evaluate("document.documentElement.scrollWidth <= innerWidth")
    page.screenshot(path="/tmp/sigma-a15-rendered-390.png", full_page=True)
    page.set_viewport_size({"width": 1440, "height": 900})
    page.locator(".strategy-row").first.locator(".strategy-detail > summary").click()
    strategy_view = page.get_by_role("combobox", name="View strategy approach").first
    expect(strategy_view).to_have_value("plain")
    strategy_view.select_option("markdown")
    expect(page.locator(".strategy-row").first.locator("pre.literal-markdown")).to_be_visible()
    page.locator(".strategy-row").first.get_by_role("button", name="Edit Markdown").click()
    strategy_editor = page.get_by_label("Edit Markdown source").first
    strategy_editor.fill(strategy_editor.input_value() + "\n\nCheck $a_n$.\n\n$$\na_n = 1 + n\n$$")
    page.locator(".strategy-row").first.get_by_role("button", name="Save text").click()
    expect(
        page.locator(".strategy-row").first.locator(".rendered-text .katex").first
    ).to_be_visible()
    expect(page.locator(".strategy-row").first.locator(".katex-display")).to_be_visible()
    strategy_view.select_option("markdown")
    expect(page.locator(".strategy-row").first.locator("pre.literal-markdown")).to_contain_text(
        "a_n = 1 + n"
    )
    assert source.read_bytes() == original
    count = len(conversions)
    view.select_option("markdown")
    page.get_by_role("button", name="Edit Markdown description").click()
    editor = page.get_by_label("Edit Markdown source")
    editor.fill(editor.input_value() + "\n\nAdditional human-authored condition.")
    page.get_by_role("button", name="Save text").click()
    expect(view).to_have_value("rendered")
    view.select_option("markdown")
    expect(page.locator(".investigation-intro pre.literal-markdown")).to_contain_text(
        "Additional human-authored condition"
    )
    page.route(
        "**/api/investigations/text/convert",
        lambda route: route.fulfill(
            status=503,
            content_type="application/json",
            body='{"error":"Mock provider unavailable"}',
        ),
    )
    view.select_option("plain")
    expect(page.get_by_text("Out of date", exact=True).first).to_be_visible()
    expect(page.get_by_role("button", name="Retry conversion")).to_be_visible()
    page.unroute("**/api/investigations/text/convert")
    page.get_by_role("button", name="Retry conversion").click()
    expect(page.get_by_role("button", name="Edit Plain description")).to_contain_text(
        "Additional human-authored condition"
    )
    assert len(conversions) == count + 2
    assert source.read_bytes() == original
    page.reload()
    expect(page.locator(".investigation-intro .rendered-text .katex").first).to_be_visible()
    view.select_option("plain")
    expect(page.get_by_role("button", name="Edit Plain description")).to_contain_text(
        "Additional human-authored condition"
    )
    assert len(conversions) == count + 2
    view.select_option("markdown")
    page.get_by_role("button", name="Edit Markdown description").click()
    editor = page.get_by_label("Edit Markdown source")
    editor.fill(
        editor.input_value()
        + "\n\n<script>window.sigmaUnsafe = true</script>"
        + "\n![external](https://example.com/tracker.png)"
    )
    page.get_by_role("button", name="Save text").click()
    expect(page.locator(".investigation-intro .rendered-text")).to_be_visible()
    assert page.evaluate("window.sigmaUnsafe === undefined")
    assert page.locator(".investigation-intro .rendered-text img").count() == 0
    title = page.get_by_role(
        "button", name="Edit investigation title: Nonconsecutive Subset Sums Modulo 3"
    )
    title.press("Enter")
    title_input = page.get_by_role("textbox", name="Investigation title")
    expect(title_input).to_be_focused()
    title_input.fill("Discard this title")
    title_input.press("Escape")
    expect(title).to_be_focused()
    page.set_viewport_size({"width": 390, "height": 844})
    title.click()
    title_input.fill("A revised title in a narrow investigation header")
    assert page.evaluate("document.documentElement.scrollWidth <= innerWidth")
    page.screenshot(path="/tmp/sigma-a15-title-edit-390.png", full_page=True)
    title_input.press("Escape")
    page.set_viewport_size({"width": 1440, "height": 900})
    title.click()
    title_input.fill("A15 revised investigation title")
    page.route(
        "**/api/investigations/update",
        lambda route: route.fulfill(
            status=409, content_type="application/json", body='{"error":"Mock title conflict"}'
        ),
    )
    page.locator(".investigation-title-actions").get_by_role("button", name="Save").click()
    expect(page.get_by_role("alert")).to_contain_text("Mock title conflict")
    expect(title_input).to_have_value("A15 revised investigation title")
    page.unroute("**/api/investigations/update")
    page.locator(".investigation-title-actions").get_by_role("button", name="Save").click()
    expect(
        page.get_by_role("heading", name="A15 revised investigation title", exact=True)
    ).to_be_visible()
    expect(page.get_by_role("button", name="Investigation Settings")).to_be_visible()
    page.get_by_role("button", name="Collapse sidebar").click()
    page.get_by_role("button", name="Close investigation").click()
    expect(page.get_by_text("Current Investigation", exact=True)).to_be_visible()
    expect(page.get_by_role("heading", name="Switch to a new investigation")).to_be_visible()
    page.locator(".home-current button").click()
    expect(
        page.get_by_role("heading", name="A15 revised investigation title", exact=True)
    ).to_be_visible()
    expect(page.get_by_role("button", name="Expand sidebar")).to_be_visible()
    view.select_option("plain")
    page.get_by_role("button", name="Edit Plain description").click()
    plain_editor = page.get_by_label("Edit Plain source")
    plain_editor.fill(plain_editor.input_value() + "\n\nA human Plain note.")
    page.locator(".investigation-intro").get_by_role("button", name="Save text").click()
    expect(page.get_by_role("button", name="Edit Plain description")).to_contain_text("A human Plain note.")
    assert source.read_bytes() == original
    assert not errors, errors
    page.unroute_all(behavior="ignoreErrors")
    browser.close()
    print(
        "PASS real Chrome: automatic two-way conversion, inline title/description edits, literal and rendered math, durable cache, stale retry, safe rendering, navigation and responsive layouts"
    )
