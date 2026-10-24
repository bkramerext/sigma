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
UI_ORIGIN = os.environ.get("SIGMA_HEADER_UI_ORIGIN", "http://127.0.0.1:5173").rstrip("/")
API_ORIGIN = os.environ.get("SIGMA_HEADER_API_ORIGIN", "http://127.0.0.1:8001").rstrip("/")

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
            response=route.fetch(
                url=route.request.url.replace(UI_ORIGIN, API_ORIGIN),
                headers={**route.request.headers, "origin": "http://127.0.0.1:5173"},
            )
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
    page.goto(UI_ORIGIN + "/")
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

    created = page.request.post(
        API_ORIGIN + "/api/projects/create",
        data={"title": TITLE, "problem": "Check whether a long header title remains readable."},
    )
    assert created.status == 201
    path = created.json()["path"]
    page.goto(f"{UI_ORIGIN}/project?{urlencode({'path': path})}")
    header = page.locator(".project-art-header")
    title = header.locator(".project-header-title")
    expect(title).to_have_text(TITLE)
    assert header.locator(".expansion").count() == 0
    expect(page.get_by_role("heading", name=TITLE)).to_be_visible()
    art = header.locator(".project-header-art img")
    assert art.evaluate("e => [e.naturalWidth, e.naturalHeight]") == [1774, 887]
    assert art.get_attribute("src") == "/sigma-project-header.png"
    close = header.get_by_role("button", name="Back to home", exact=True)
    controls = header.locator(".header-controls")
    model_control = controls.get_by_role("button", name=re.compile("^Model"))
    thinking_control = controls.get_by_role("button", name=re.compile("^Thinking level"))
    difficulty_control = controls.get_by_role("button", name=re.compile("^Project difficulty"))
    google_signin = controls.locator(".project-google-signin")
    expect(model_control).to_have_text("Model · Sol $$")
    expect(thinking_control).to_have_text("Thinking · High")
    expect(difficulty_control).to_have_text("Difficulty · Medium")
    expect(google_signin).to_contain_text("Google Sign-in")
    expect(google_signin).to_contain_text("Coming soon")
    expect(google_signin).to_be_disabled()
    expect(google_signin).to_have_attribute(
        "aria-label", "Google sign-in is unavailable in this local workspace."
    )
    assert google_signin.locator(".connection-dot").count() == 1
    assert (
        google_signin.locator(".connection-dot").evaluate(
            "e => getComputedStyle(e).backgroundColor"
        )
        == "rgb(127, 140, 150)"
    )
    assert google_signin.evaluate("e => e.matches('button')")
    auth_requests: list[str] = []
    page.on("request", lambda request: auth_requests.append(request.url) if "/api/cloud-auth/login" in request.url else None)
    google_signin.click(force=True)
    assert not auth_requests
    assert "not actual research session charges" in header.locator(".sr-only").inner_text()
    grid = controls.bounding_box()
    model_box = model_control.bounding_box()
    thinking_box = thinking_control.bounding_box()
    google_box = google_signin.bounding_box()
    pill = header.locator(".api-connection > summary")
    chatgpt_box = pill.bounding_box()
    assert grid and model_box and thinking_box and google_box and chatgpt_box
    assert model_box["y"] < thinking_box["y"] and google_box["y"] < chatgpt_box["y"]
    assert model_box["x"] < google_box["x"] and thinking_box["x"] < chatgpt_box["x"]
    assert grid["x"] + grid["width"] <= 1280
    assert grid["x"] >= 1280 * 0.55
    expect(header.locator(".project-controls-message")).to_have_count(0)
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
    # Navigation kept the previous physical pointer coordinates, which can land
    # over a different pill in the newly rendered project header. Leave that
    # target first so the delayed tooltip check observes a fresh hover.
    page.mouse.move(0, 0)
    expect(page.get_by_role("tooltip")).to_have_count(0)
    model_control.hover()
    page.wait_for_timeout(450)
    expect(page.get_by_role("tooltip")).to_contain_text("The selected model is Sol $$.")
    model_control.click()
    expect(model_control).to_have_text("Model · Luna $")
    expect(page.get_by_role("tooltip")).to_have_count(0)
    model_control.click()
    upgrade_prompt = page.get_by_role("group", name="Confirm switch to Astra")
    expect(upgrade_prompt).to_be_visible()
    expect(upgrade_prompt).to_contain_text(
        "Astra has a higher relative published API token cost tier ($$$ versus $)."
    )
    expect(page.get_by_role("tooltip")).to_have_count(0)
    difficulty_control.hover()
    expect(page.get_by_role("tooltip")).to_have_count(0)
    expect(upgrade_prompt.get_by_role("button", name="Confirm", exact=True)).to_be_focused()
    assert (
        upgrade_prompt.get_by_role("button", name="Confirm", exact=True).evaluate(
            "e => getComputedStyle(e).textDecorationLine"
        )
        == "underline"
    )
    assert (
        upgrade_prompt.get_by_role("button", name="Cancel", exact=True).evaluate(
            "e => getComputedStyle(e).textDecorationLine"
        )
        == "underline"
    )
    prompt_box = upgrade_prompt.bounding_box()
    model_before_prompt = model_control.bounding_box()
    assert prompt_box and model_before_prompt
    assert prompt_box["y"] >= model_before_prompt["y"] + model_before_prompt["height"]
    assert abs(prompt_box["x"] - model_before_prompt["x"]) < 250
    upgrade_prompt.get_by_role("button", name="Cancel", exact=True).click()
    expect(upgrade_prompt).to_be_hidden()
    expect(model_control).to_have_text("Model · Luna $")
    assert len(update_requests) == 1 and update_requests[0]["ai_model"] == "gpt-6-luna"
    page.mouse.move(0, 0)
    model_control.hover()
    expect(page.get_by_role("tooltip")).to_contain_text("The selected model is Luna $")
    model_control.click()
    upgrade_prompt = page.get_by_role("group", name="Confirm switch to Astra")
    expect(upgrade_prompt).to_be_visible()
    upgrade_prompt.get_by_role("button", name="Confirm", exact=True).click()
    expect(model_control).to_have_text("Model · Astra $$$")
    expect(thinking_control).to_have_text("Thinking · Medium")
    thinking_control.focus()
    page.keyboard.press("Enter")
    expect(thinking_control).to_have_text("Thinking · Low")
    model_control.focus()
    page.keyboard.press("Enter")
    expect(model_control).to_have_text("Model · Sol $$")
    expect(page.locator(".project-model-confirm-popover")).to_have_count(0)
    difficulty_control.click()
    expect(difficulty_control).to_have_text("Difficulty · Hard")
    difficulty_control.click()
    expect(difficulty_control).to_have_text("Difficulty · Easy")
    difficulty_control.click()
    expect(difficulty_control).to_have_text("Difficulty · Medium")
    persisted = page.request.get(
        API_ORIGIN + "/api/projects/inspect", params={"path": path}
    ).json()["project"]
    assert persisted["ai_model"] == "gpt-6.1-sol" and persisted["reasoning_effort"] == "low"
    assert persisted["difficulty"] == "medium"
    assert len(update_requests) == 7
    assert (
        update_requests[0]["ai_model"] == "gpt-6-luna"
        and update_requests[0]["reasoning_effort"] == "high"
    )
    assert (
        update_requests[1]["ai_model"] == "gpt-6-astra"
        and update_requests[1]["reasoning_effort"] == "medium"
    )
    assert (
        update_requests[2]["ai_model"] == "gpt-6-astra"
        and update_requests[2]["reasoning_effort"] == "low"
    )
    assert (
        update_requests[3]["ai_model"] == "gpt-6.1-sol"
        and update_requests[3]["reasoning_effort"] == "low"
    )
    assert [request["difficulty"] for request in update_requests[4:]] == ["hard", "easy", "medium"]
    assert not any(url.split("?", 1)[0].endswith("/api/ai/mode") for url in observed_urls)
    google_signin.dispatch_event("click")
    assert not any("/api/cloud-auth/login" in url for url in observed_urls)
    page.reload()
    model_control = page.locator(".project-art-header .project-model-pill")
    thinking_control = page.locator(".project-art-header .project-thinking-pill")
    expect(model_control).to_have_text("Model · Sol $$")
    expect(thinking_control).to_have_text("Thinking · Low")
    assert close.locator("svg").count() == 1
    assert header.get_by_text("Close project", exact=True).count() == 0
    connection = page.request.get(API_ORIGIN + "/api/ai/connection").json()
    if connection.get("status") == "connected":
        connected_label = (
            "ChatGPT connected"
            if connection.get("mode") == "chatgpt" and connection.get("active_account")
            else "OpenAI API connected"
        )
        expect(pill.locator('[role="status"]')).to_have_text(connected_label)
        assert "connection-connected" in pill.locator(".connection-dot").get_attribute("class")
    else:
        assert pill.locator('[role="status"]').inner_text() in {
            "ChatGPT sign-in · Checking AI…",
            "ChatGPT sign-in · AI status unavailable",
            f"ChatGPT sign-in · {connection.get('label', 'Connect AI')}",
        }
    assert model_control.evaluate("e => getComputedStyle(e).textAlign") == "center"
    assert model_control.evaluate("e => getComputedStyle(e).alignItems") == "center"
    assert model_control.evaluate("e => getComputedStyle(e).justifyContent") == "center"
    assert model_control.evaluate(
        "e => [...e.children].every(child => getComputedStyle(child).marginLeft === '0px')"
    )
    close.hover()
    assert close.evaluate("e => getComputedStyle(e).cursor") == "pointer"
    page.mouse.move(0, 0)
    pill.hover()
    page.wait_for_timeout(200)
    assert pill.evaluate("e => getComputedStyle(e).backgroundColor") != "rgba(0, 0, 0, 0)"
    pill.focus()
    page.keyboard.press("Enter")
    connection_dialog = page.get_by_role("dialog", name="AI connection settings")
    expect(connection_dialog).to_be_visible()
    expect(connection_dialog.get_by_role("button", name="Retry connection")).to_be_visible()
    assert connection_dialog.get_by_role("button").count() > 1
    assert connection_dialog.locator("button").evaluate_all(
        "items => items.some(e => /Continue with ChatGPT|Disconnect|Use ChatGPT plan|Connect another account/.test(e.innerText))"
    )
    page.keyboard.press("Escape")
    expect(header.locator(".api-connection")).not_to_have_attribute("open", "")
    pill.focus()
    assert pill.evaluate("e => getComputedStyle(e).outlineStyle") == "solid"

    for width, height in ((1280, 800), (1100, 800), (700, 900), (390, 844), (320, 700)):
        page.set_viewport_size({"width": width, "height": height})
        expect(title).to_have_text(TITLE)
        assert title.evaluate("e => getComputedStyle(e).whiteSpace") == "normal"
        assert title.evaluate("e => getComputedStyle(e).overflow") == "visible"
        assert page.evaluate("document.documentElement.scrollWidth <= innerWidth"), (
            width,
            page.evaluate(
                "[document.documentElement.scrollWidth, innerWidth, ...[...document.querySelectorAll('.project-art-header *')].filter(e => e.getBoundingClientRect().right > innerWidth).map(e => [e.className || e.tagName, e.getBoundingClientRect().x, e.getBoundingClientRect().width, e.getBoundingClientRect().right])]"
            ),
        )
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
        assert abs(art_box["x"]) < 1 and abs(art_box["y"] - 5) < 1
        assert abs(art_box["width"] / art_box["height"] - 2) < 0.01
        assert abs(art_frame["height"] / art_box["height"] - 0.64) < 0.02
        assert art_frame["y"] + art_frame["height"] <= workspace_box["y"] + 1
        assert title_box["x"] + title_box["width"] <= width + 1
        assert controls_box["x"] >= 0 and controls_box["x"] + controls_box["width"] <= width + 1
        assert (
            model_control.bounding_box()
            and thinking_control.bounding_box()
            and google_signin.bounding_box()
        )
        model_box = model_control.bounding_box()
        thinking_box = thinking_control.bounding_box()
        google_box = google_signin.bounding_box()
        chatgpt_box = pill.bounding_box()
        assert model_box and thinking_box and google_box and chatgpt_box
        assert model_box["y"] < thinking_box["y"] and google_box["y"] < chatgpt_box["y"]
        assert model_box["x"] < google_box["x"] and thinking_box["x"] < chatgpt_box["x"]
        page.screenshot(path=f"/tmp/sigma-a23-model-controls-{width}.png", full_page=True)
        if width >= 1100:
            assert workspace_box["y"] <= 140, (
                width,
                workspace_box,
                header.bounding_box(),
                controls_box,
            )
            assert title_box["x"] >= art_box["x"] + art_box["width"] - 1
            assert controls_box["x"] >= title_box["x"] + title_box["width"] - 1
        else:
            assert controls_box["y"] > close_box["y"]
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
        "PASS 2x2 project header controls, model/effort reconciliation, functional ChatGPT disclosure, Google placeholder, keyboard, persistence, responsive layout and no overflow"
    )
