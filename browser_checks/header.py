"""A13: project header title, shared copper controls and connection disclosure."""

import os
from urllib.parse import urlencode

from playwright.sync_api import expect, sync_playwright

TITLE = "Nonconsecutive Subset Sums Modulo 3 Copy for Independent Analysis and Verification"
STYLE = "e => { const s = getComputedStyle(e); return [s.color, s.backgroundColor, s.backgroundImage, s.borderColor, s.textShadow, s.boxShadow] }"
PILL = "e => { const s = getComputedStyle(e); return [s.color, s.backgroundColor, s.borderColor, s.borderRadius, s.padding, s.boxShadow, s.fontSize, s.minHeight] }"

with sync_playwright() as playwright:
    browser = playwright.chromium.launch(
        executable_path=os.environ.get(
            "SIGMA_BROWSER_EXECUTABLE",
            "/Applications/Google Chrome.app/Contents/MacOS/Google Chrome",
        ),
        headless=True,
    )
    page = browser.new_page(viewport={"width": 1280, "height": 800})
    page.set_default_timeout(10000)
    errors: list[str] = []
    page.on("pageerror", lambda error: errors.append(str(error)))

    def forward(route):
        route.fulfill(
            response=route.fetch(url=route.request.url.replace("127.0.0.1:5173", "127.0.0.1:8001"))
        )

    page.route("**/api/**", forward)
    page.goto("http://127.0.0.1:5173/")
    expect(page.locator(".home-slogan")).to_be_visible()
    home_open = page.locator(".home-entry-actions").get_by_role("button", name="Open Project")
    home_new = page.locator(".home-entry-actions").get_by_role("button", name="New Project")
    assert home_open.evaluate(STYLE) == home_new.evaluate(STYLE)
    home_style = home_open.evaluate(STYLE)
    home_open.evaluate("e => e.disabled = true")
    home_disabled = home_open.evaluate(STYLE)
    expect(home_open).to_be_disabled()
    home_open.evaluate("e => e.disabled = false")
    home_open.hover()
    home_hover = home_open.evaluate(STYLE)
    page.mouse.move(0, 0)
    home_pill = page.locator(".home-topline .api-connection > summary")
    expect(home_pill).to_be_visible()
    home_pill_style = home_pill.evaluate(PILL)
    home_label = home_pill.locator('[role="status"]').inner_text()
    home_dot = home_pill.locator(".connection-dot").get_attribute("class")
    home_pill.hover()
    page.wait_for_timeout(200)
    home_pill_hover = home_pill.evaluate(PILL)

    created = page.request.post(
        "http://127.0.0.1:8001/api/projects/create",
        data={"title": TITLE, "problem": "Check whether a long header title remains readable."},
    )
    assert created.status == 201
    path = created.json()["path"]
    page.goto(f"http://127.0.0.1:5173/project?{urlencode({'path': path})}")
    header = page.locator(".project-art-header")
    title = header.locator(".current-project")
    expect(title).to_have_text(TITLE)
    assert header.locator(".expansion").count() == 0
    expect(page.get_by_role("heading", name=TITLE)).to_be_visible()
    art = header.locator(".project-header-art img")
    assert art.evaluate("e => [e.naturalWidth, e.naturalHeight]") == [1774, 887]
    assert art.get_attribute("src") == "/sigma-project-header.png"
    close = header.get_by_role("button", name="Close project")
    pill = header.locator(".api-connection > summary")
    assert close.evaluate(STYLE) == home_style
    assert pill.evaluate(PILL) == home_pill_style
    assert pill.locator('[role="status"]').inner_text() == home_label
    assert pill.locator(".connection-dot").get_attribute("class") == home_dot
    close.hover()
    assert close.evaluate(STYLE) == home_hover
    page.mouse.move(0, 0)
    pill.hover()
    page.wait_for_timeout(200)
    assert pill.evaluate(PILL) == home_pill_hover
    pill.click()
    expect(header.locator(".connection-details")).to_be_visible()
    expect(
        header.locator(".connection-details").get_by_role("button", name="Retry connection")
    ).to_be_visible()
    page.keyboard.press("Escape")
    expect(header.locator(".api-connection")).not_to_have_attribute("open", "")
    pill.focus()
    assert pill.evaluate("e => getComputedStyle(e).outlineStyle") == "solid"

    for width, height in ((1280, 800), (1100, 800), (700, 900), (390, 844), (320, 700)):
        page.set_viewport_size({"width": width, "height": height})
        expect(title).to_have_text(TITLE)
        assert title.evaluate("e => getComputedStyle(e).whiteSpace") == "normal"
        assert title.evaluate("e => getComputedStyle(e).overflow") == "visible"
        assert page.evaluate("document.documentElement.scrollWidth <= innerWidth")
        art_box = art.bounding_box()
        title_box = title.bounding_box()
        close_box = close.bounding_box()
        pill_box = pill.bounding_box()
        assert art_box and title_box and close_box and pill_box
        assert abs(art_box["x"]) < 1 and abs(art_box["y"]) < 1
        assert abs(art_box["width"] / art_box["height"] - 2) < 0.01
        assert title_box["x"] + title_box["width"] <= width + 1
        if width >= 1100:
            assert title_box["x"] >= art_box["x"] + art_box["width"] - 1
            assert close_box["x"] + close_box["width"] <= pill_box["x"] + 1
        else:
            assert close_box["y"] <= pill_box["y"] + 1
        page.screenshot(path=f"/tmp/sigma-a13-header-{width}.png", full_page=True)

    close.evaluate("e => e.disabled = true")
    expect(close).to_be_disabled()
    assert close.evaluate(STYLE) == home_disabled
    close.evaluate("e => e.disabled = false")
    close.focus()
    page.keyboard.press("Enter")
    expect(page.locator(".home-slogan")).to_be_visible()
    assert page.locator(".home-topline .api-connection > summary").evaluate(PILL) != []
    assert not errors, errors
    browser.close()
    print(
        "PASS A13 full header title at 1280/1100/700/390/320px, shared copper button and AI pill styles, disclosure, focus, close, no overflow or page errors"
    )
