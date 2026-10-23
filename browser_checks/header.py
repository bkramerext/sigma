"""Project header title, back navigation and connection disclosure."""

import json
import os
import re
from urllib.parse import urlencode
from uuid import uuid4

from playwright.sync_api import expect, sync_playwright

TITLE = f"Header model controls {uuid4().hex[:8]}"
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
    available_models = [
        {
            "id": "gpt-6.1-sol",
            "label": "Sol · Balanced ($$)",
            "description": "Balanced",
            "efforts": ["low", "medium", "high", "xhigh"],
            "relative_cost": "$$",
            "availability": "available",
        },
        {
            "id": "gpt-6-astra",
            "label": "Astra · Advanced ($$$)",
            "description": "Advanced",
            "efforts": ["low", "medium"],
            "relative_cost": "$$$",
            "availability": "available",
        },
        {
            "id": "gpt-6-luna",
            "label": "Luna · Economy ($)",
            "description": "Economy",
            "efforts": ["low", "medium", "high", "xhigh"],
            "relative_cost": "$",
            "availability": "available",
        },
    ]
    page.route(
        "**/api/ai/models",
        lambda route: route.fulfill(
            json={
                "models": available_models,
                "default_model": "gpt-6.1-sol",
                "default_effort": "high",
                "default_verified": True,
                "message": "fixture catalog",
            }
        ),
    )
    page.goto("http://127.0.0.1:5173/")
    expect(page.locator(".home-slogan")).to_be_visible()
    home_actions = page.locator(".home-projects-heading")
    home_open = home_actions.get_by_role("button", name="Open", exact=True)
    home_new = home_actions.get_by_role("button", name="New", exact=True)
    assert home_open.evaluate(STYLE) == home_new.evaluate(STYLE)
    home_open.evaluate("e => e.disabled = true")
    expect(home_open).to_be_disabled()
    home_open.evaluate("e => e.disabled = false")
    home_open.hover()
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
    title = header.locator(".project-header-title")
    expect(title).to_have_text(TITLE)
    assert header.locator(".expansion").count() == 0
    expect(page.get_by_role("heading", name=TITLE)).to_be_visible()
    art = header.locator(".project-header-art img")
    assert art.evaluate("e => [e.naturalWidth, e.naturalHeight]") == [1774, 887]
    assert art.get_attribute("src") == "/sigma-project-header.png"
    close = header.get_by_role("button", name="Back to home", exact=True)
    controls = header.locator(".project-header-controls")
    model_control = controls.get_by_role("button", name=re.compile("^Model"))
    thinking_control = controls.get_by_role("button", name=re.compile("^Thinking level"))
    expect(model_control).to_have_text("Sol $$")
    expect(thinking_control).to_have_text("Thinking · High")
    auth_placeholder = controls.get_by_role("status")
    expect(auth_placeholder).to_have_text("Sign in")
    assert "not actual research session charges" in controls.locator(".sr-only").inner_text()
    update_requests: list[dict] = []
    observed_urls: list[str] = []
    page.on("request", lambda request: observed_urls.append(request.url))
    page.on(
        "request",
        lambda request: (
            update_requests.append(json.loads(request.post_data))
            if request.url.endswith("/api/projects/update") and request.post_data
            else None
        ),
    )
    model_control.focus()
    page.keyboard.press("Enter")
    expect(model_control).to_have_text("Luna $")
    thinking_control.focus()
    page.keyboard.press("Enter")
    expect(thinking_control).to_have_text("Thinking · Extra high")
    persisted = page.request.get(
        "http://127.0.0.1:8001/api/projects/inspect", params={"path": path}
    ).json()["project"]
    assert persisted["ai_model"] == "gpt-6-luna" and persisted["reasoning_effort"] == "xhigh"
    assert len(update_requests) == 2
    assert (
        update_requests[0]["ai_model"] == "gpt-6-luna"
        and update_requests[0]["reasoning_effort"] == "high"
    )
    assert (
        update_requests[1]["ai_model"] == "gpt-6-luna"
        and update_requests[1]["reasoning_effort"] == "xhigh"
    )
    assert not any("/api/ai/mode" in url for url in observed_urls)
    pill = header.locator(".api-connection > summary")
    assert close.locator("svg").count() == 1
    assert header.get_by_text("Close project", exact=True).count() == 0
    assert pill.evaluate(PILL) == home_pill_style
    assert pill.locator('[role="status"]').inner_text() == home_label
    assert pill.locator(".connection-dot").get_attribute("class") == home_dot
    close.hover()
    assert close.evaluate("e => getComputedStyle(e).cursor") == "pointer"
    page.mouse.move(0, 0)
    pill.hover()
    page.wait_for_timeout(200)
    assert pill.evaluate(PILL) == home_pill_hover
    pill.click()
    connection_dialog = page.get_by_role("dialog", name="AI connection settings")
    expect(connection_dialog).to_be_visible()
    expect(
        connection_dialog.get_by_role("button", name="Retry connection")
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
        art_frame = header.locator(".project-header-art").bounding_box()
        workspace_box = page.locator(".workspace-layout").bounding_box()
        title_box = title.bounding_box()
        close_box = close.bounding_box()
        pill_box = pill.bounding_box()
        controls_box = controls.bounding_box()
        assert (
            art_box
            and art_frame
            and workspace_box
            and title_box
            and close_box
            and pill_box
            and controls_box
        )
        assert abs(art_box["x"]) < 1 and abs(art_box["y"]) < 1
        assert abs(art_box["width"] / art_box["height"] - 2) < 0.01
        assert abs(art_frame["height"] / art_box["height"] - 0.64) < 0.02
        assert art_frame["y"] + art_frame["height"] <= workspace_box["y"] + 1
        assert title_box["x"] + title_box["width"] <= width + 1
        assert controls_box["x"] >= 0 and controls_box["x"] + controls_box["width"] <= width + 1
        assert controls_box["y"] > title_box["y"]
        page.screenshot(path=f"/tmp/sigma-a23-model-controls-{width}.png", full_page=True)
        if width >= 1100:
            assert workspace_box["y"] <= 130
            assert title_box["x"] >= art_box["x"] + art_box["width"] - 1
            assert close_box["x"] + close_box["width"] <= pill_box["x"] + 1
        else:
            assert close_box["y"] <= pill_box["y"] + 1
        page.screenshot(path=f"/tmp/sigma-a13-header-{width}.png", full_page=True)

    close.evaluate("e => e.disabled = true")
    expect(close).to_be_disabled()
    assert close.evaluate("e => getComputedStyle(e).cursor") == "wait"
    close.evaluate("e => e.disabled = false")
    close.focus()
    page.keyboard.press("Enter")
    expect(page.locator(".home-slogan")).to_be_visible()
    assert page.locator(".home-topline .api-connection > summary").evaluate(PILL) != []
    assert not errors, errors
    browser.close()
    print(
        "PASS full header title and back arrow at 1280/1100/700/390/320px, AI pill style, disclosure, focus, close, no overflow or page errors"
    )
