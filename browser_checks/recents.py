"""A11 real Chrome: Home tabs, direct stock opens and responsive copper controls."""

import os
from pathlib import Path

from playwright.sync_api import expect, sync_playwright

SOURCE = Path("examples/nonconsecutive-subset-sums/investigation.json")
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
    page.set_default_timeout(10000)
    errors: list[str] = []
    page.on("pageerror", lambda error: errors.append(str(error)))

    def forward(route):
        route.fulfill(
            response=route.fetch(url=route.request.url.replace("127.0.0.1:5173", "127.0.0.1:8001"))
        )

    page.route("**/api/**", forward)
    page.goto("http://127.0.0.1:5173/")
    recent_tab = page.get_by_role("tab", name="Recent Investigations")
    stock_tab = page.get_by_role("tab", name="Stock Investigations")
    assert page.get_by_role("tab").all_text_contents() == ["Stock Investigations", "Recent Investigations"]
    expect(stock_tab).to_have_attribute("aria-selected", "true")
    assert page.get_by_role("heading", name="Recent Investigations").count() == 0
    assert page.get_by_role("heading", name="Stock Investigations").count() == 0
    assert page.locator(".home-hero h1").evaluate("e=>getComputedStyle(e).userSelect") == "none"
    assert page.request.get("http://127.0.0.1:8001/api/investigations/recent").json()["investigations"] == []
    assert abs(page.locator(".home-slogan").bounding_box()["x"]) < 1
    assert page.locator(".home-hero").bounding_box()["x"] > 20
    open_action = page.locator(".home-entry-actions").get_by_role("button", name="Open Investigation")
    new_action = page.locator(".home-entry-actions").get_by_role("button", name="New Investigation")
    button_style = "e => { const s = getComputedStyle(e); return [s.backgroundColor, s.backgroundImage, s.color, s.borderColor] }"
    assert open_action.evaluate(button_style) == new_action.evaluate(button_style)
    assert page.locator(".home-hero h1").evaluate("e => getComputedStyle(e).color") == open_action.evaluate("e => getComputedStyle(e).color")
    selected_style = stock_tab.evaluate("e => { const s = getComputedStyle(e); return [s.backgroundImage, s.color, s.borderColor] }")
    for action in (open_action, new_action):
        action.hover()
        assert action.evaluate("e => { const s = getComputedStyle(e); return [s.backgroundImage, s.color, s.borderColor] }") == selected_style
    pill = page.locator(".home-topline .api-connection summary")
    base_pill = pill.evaluate("e=>getComputedStyle(e).backgroundColor")
    pill.hover()
    page.wait_for_timeout(200)
    assert pill.evaluate("e=>getComputedStyle(e).backgroundColor") != base_pill

    stock_tab.focus()
    page.keyboard.press("ArrowRight")
    expect(recent_tab).to_be_focused()
    expect(page.get_by_text("No recent investigations yet.", exact=False)).to_be_visible()
    page.keyboard.press("ArrowLeft")
    expect(stock_tab).to_be_focused()
    stock_panel = page.get_by_role("tabpanel", name="Stock Investigations")
    expect(stock_panel.get_by_text("Nonconsecutive Subset Sums Modulo 3")).to_be_visible()
    expect(stock_panel.get_by_text("Did Jesus Use Cannabis?")).to_be_visible()
    assert stock_panel.locator(".stock-open strong").all_text_contents()[-1] == "Did Jesus Use Cannabis?"
    assert stock_panel.get_by_text("Shipped template").count() == 0
    stock_panel.locator(".stock-open").first.hover()
    assert stock_panel.locator(".stock-open").first.evaluate("e=>getComputedStyle(e).backgroundColor") != "rgba(0, 0, 0, 0)"
    stock_panel.get_by_role("button", name="Open Nonconsecutive Subset Sums Modulo 3").click()
    expect(page.get_by_role("heading", name="Strategies", exact=True)).to_be_visible()
    assert page.get_by_role("dialog").count() == 0
    expect(page.locator(".strategy-row")).to_have_count(3)
    stock_path = page.evaluate("new URL(location.href).searchParams.get('path')")
    assert stock_path.endswith("/nonconsecutive-subset-sums.sigma")
    assert Path(stock_path, "investigation.json").read_bytes() == original
    saved = page.request.post("http://127.0.0.1:8001/api/investigations/strategies", data={"path": stock_path, "title": "Browser stock addition", "approach": "Keep this strategy"})
    assert saved.status == 201
    close_button = page.get_by_role("button", name="Close investigation")
    assert close_button.evaluate("e=>getComputedStyle(e).borderRadius") == "50%"
    base_close = close_button.evaluate("e=>getComputedStyle(e).backgroundColor")
    close_button.hover()
    assert close_button.evaluate("e=>getComputedStyle(e).backgroundColor") != base_close
    page.screenshot(path="/tmp/sigma-a11-workspace-pill.png", full_page=True)
    close_button.click()
    expect(stock_tab).to_have_attribute("aria-selected", "true")
    recent_tab.click()
    recent_panel = page.get_by_role("tabpanel", name="Recent Investigations")
    expect(recent_panel.get_by_text("No recent investigations yet.", exact=False)).to_be_visible()
    assert page.request.get("http://127.0.0.1:8001/api/investigations/recent").json()["investigations"] == []

    stock_tab.click()
    expect(stock_panel.get_by_text("4 strategies")).to_be_visible()
    stock_panel.get_by_role("button", name="Open Nonconsecutive Subset Sums Modulo 3").click()
    expect(page.get_by_role("heading", name="Strategies", exact=True)).to_be_visible()
    expect(page.locator(".strategy-row")).to_have_count(4)
    assert page.evaluate("new URL(location.href).searchParams.get('path')") == stock_path
    page.get_by_role("button", name="Close investigation").click()
    assert page.request.get("http://127.0.0.1:8001/api/investigations/recent").json()["investigations"] == []

    created = page.request.post("http://127.0.0.1:8001/api/investigations/create", data={"title": "Browser recent", "problem": "Own research"})
    assert created.status == 201
    listing = page.request.get("http://127.0.0.1:8001/api/investigations/recent").json()["investigations"]
    assert len(listing) == 1 and listing[0]["id"] == created.json()["investigation"]["id"]
    page.goto("http://127.0.0.1:5173/")
    recent_tab.click()
    expect(recent_panel.get_by_text("Browser recent")).to_be_visible()
    assert recent_panel.locator(".recent-open small").first.evaluate("e=>getComputedStyle(e).fontWeight") == "400"

    # Losing the investigation path must preserve an actionable unavailable recent.
    missing = Path(listing[0]["path"])
    missing.rename(missing.with_name(missing.name + ".moved"))
    page.goto("http://127.0.0.1:5173/")
    recent_tab.click()
    recent_panel = page.get_by_role("tabpanel", name="Recent Investigations")
    expect(recent_panel.get_by_text("Unavailable or changed identity.", exact=False)).to_be_visible()
    expect(recent_panel.locator(".recent-open").first).to_be_disabled()
    recent_panel.locator(".recent-forget").first.click()
    expect(recent_panel.locator(".recent-open")).to_have_count(0)

    for width, height in ((1280, 720), (390, 844), (320, 700)):
        page.set_viewport_size({"width": width, "height": height})
        stock_tab.click()
        expect(stock_panel.get_by_text("Did Jesus Use Cannabis?")).to_be_visible()
        assert page.evaluate("document.documentElement.scrollWidth <= innerWidth")
        page.screenshot(path=f"/tmp/sigma-a11-stock-{width}.png", full_page=True)
        stock_panel.get_by_role("button", name="Open Did Jesus Use Cannabis?").click()
        expect(page.get_by_role("heading", name="Strategies", exact=True)).to_be_visible()
        assert page.get_by_role("dialog").count() == 0
        assert page.evaluate("document.documentElement.scrollWidth <= innerWidth")
        page.screenshot(path=f"/tmp/sigma-a11-workspace-{width}.png", full_page=True)
        page.get_by_role("button", name="Close investigation").click()
        expect(stock_panel).to_be_visible()
    assert SOURCE.read_bytes() == original
    page.set_viewport_size({"width": 1280, "height": 800})
    page.get_by_role("button", name="New Investigation", exact=True).click()
    new_dialog = page.get_by_role("dialog", name="New Investigation")
    expect(new_dialog).to_be_visible()
    assert new_dialog.locator(".settings-body").evaluate("e=>e.scrollHeight<=e.clientHeight")
    page.screenshot(path="/tmp/sigma-a11-new-investigation-1280.png", full_page=True)
    new_dialog.get_by_role("button", name="Cancel").click()
    assert not errors, errors
    browser.close()
    print("PASS Chrome Home tabs, keyboard, stable direct stock opens with retained edits and no dialog/recents, responsive layout, source immutability and no page errors")
