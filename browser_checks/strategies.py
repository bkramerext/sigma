"""Real Chrome checks against an explicitly identified, no-network provider fixture."""

import json
import os
from pathlib import Path
from tempfile import mkdtemp
from urllib.parse import quote

from playwright.sync_api import expect, sync_playwright

from sigma.projects import create_strategy, initialize_project

path = str(Path(mkdtemp(prefix="sigma-a7-check-")) / "research.sigma")
initialize_project(
    path,
    "Research directions",
    "Compare approaches to a bounded mathematical question. Evidence and finite tests are not proofs.",
    "mathematical",
)
for title, approach in [
    (
        "Explicit formula and test-function approach",
        "Seek constraints on off-line zeros through transformed explicit-formula identities.\nCheck convergence and boundary terms before drawing conclusions.",
    ),
    ("Operator construction", "Explore spectral structure and test an operator domain."),
    ("Positivity formulation", "Investigate positivity requirements and incomplete arguments."),
    ("Integral transforms", "Test whether representations yield new inequalities."),
]:
    create_strategy(path, title, approach)
state = Path(path) / "project.json"
with sync_playwright() as p:
    browser = p.chromium.launch(
        executable_path=os.environ.get(
            "SIGMA_BROWSER_EXECUTABLE",
            "/Applications/Google Chrome.app/Contents/MacOS/Google Chrome",
        ),
        headless=True,
    )
    context = browser.new_context(viewport={"width": 1672, "height": 941}, has_touch=True)
    page = context.new_page()
    errors = []
    page.on("pageerror", lambda error: errors.append(str(error)))
    # Only this test browser uses the explicitly identified isolated provider fixture.
    page.route(
        "**/api/**",
        lambda route: route.fulfill(
            response=route.fetch(url=route.request.url.replace("127.0.0.1:5173", "127.0.0.1:8001"))
        ),
    )
    page.goto("http://127.0.0.1:5173/project?path=" + quote(path))
    expect(page.get_by_role("heading", name="Research directions", exact=True)).to_be_visible()
    rows = page.locator(".strategy-row")
    assert rows.count() == 4
    intro = page.locator(".project-intro")
    new_strategy = page.get_by_role("button", name="New Strategy", exact=True)
    heading_box = page.get_by_role("heading", name="Strategies", exact=True).bounding_box()
    button_box = new_strategy.bounding_box()
    intro_box = intro.bounding_box()
    content_box = page.locator(".workspace-content").bounding_box()
    assert heading_box and button_box and intro_box and content_box
    assert button_box["y"] >= intro_box["y"] + intro_box["height"]
    assert abs(button_box["y"] - heading_box["y"]) < 20
    assert (
        abs(
            button_box["x"]
            + button_box["width"]
            + 44
            - (content_box["x"] + content_box["width"] - 40)
        )
        < 2
    )
    divider = page.get_by_role("separator", name="Resize project description")
    objective_box = page.locator(".objective").bounding_box()
    divider_box = divider.bounding_box()
    assert objective_box and divider_box
    assert 0 <= divider_box["y"] - (objective_box["y"] + objective_box["height"]) <= 16
    sidebar = page.get_by_role("navigation", name="Project navigation")
    expanded_width = sidebar.bounding_box()["width"]
    page.get_by_role("button", name="Collapse sidebar").click()
    expect(page.get_by_role("button", name="Expand sidebar")).to_be_visible()
    assert sidebar.bounding_box()["width"] < expanded_width / 2
    assert page.get_by_role("link", name="Strategies").is_visible()
    assert page.evaluate("document.documentElement.scrollWidth <= innerWidth")
    page.screenshot(path="/tmp/sigma-project-sidebar-collapsed-1672.png", full_page=True)
    page.get_by_role("button", name="Expand sidebar").click()
    assert abs(sidebar.bounding_box()["width"] - expanded_width) < 2
    page.locator(".objective").evaluate(
        "e => { e.dataset.original = e.textContent; e.textContent = (e.textContent + ' ').repeat(100); }"
    )
    assert intro.evaluate("e => e.scrollHeight > e.clientHeight")
    assert page.evaluate("document.documentElement.scrollWidth <= innerWidth")
    intro.evaluate("e => e.scrollTop = e.scrollHeight")
    assert intro.evaluate("e => e.scrollTop > 0")
    page.screenshot(path="/tmp/sigma-strategies-long-description-1672.png", full_page=True)
    page.set_viewport_size({"width": 390, "height": 844})
    assert intro.evaluate("e => e.scrollHeight > e.clientHeight")
    assert page.evaluate("document.documentElement.scrollWidth <= innerWidth")
    page.screenshot(path="/tmp/sigma-strategies-long-description-390.png", full_page=True)
    page.set_viewport_size({"width": 1672, "height": 941})
    page.locator(".objective").evaluate("e => e.textContent = e.dataset.original")
    intro.evaluate("e => e.scrollTop = 0")
    resizer = divider
    resizer.focus()
    original_height = intro.bounding_box()["height"]
    resizer.press("ArrowDown")
    assert intro.bounding_box()["height"] >= original_height + 20
    resizer.press("Home")
    assert abs(intro.bounding_box()["height"] - 120) < 2
    grip = resizer.bounding_box()
    page.mouse.move(grip["x"] + grip["width"] / 2, grip["y"] + grip["height"] / 2)
    page.mouse.down()
    page.mouse.move(grip["x"] + grip["width"] / 2, grip["y"] + grip["height"] / 2 + 80)
    page.mouse.up()
    assert intro.bounding_box()["height"] >= 195
    resizer.press("End")
    assert int(resizer.get_attribute("aria-valuenow")) == int(
        resizer.get_attribute("aria-valuemax")
    )
    page.reload()
    expect(page.get_by_role("heading", name="Research directions", exact=True)).to_be_visible()
    assert page.get_by_text("Strategy pool", exact=True).count() == 0
    assert page.get_by_role("button", name="Promote", exact=True).count() == 0
    assert page.get_by_role("button", name="Demote", exact=True).count() == 0
    page.screenshot(path="/tmp/sigma-a7-workspace-1672.png", full_page=True)
    split = page.get_by_label("New Strategy options", exact=True)
    split.click()
    expect(page.get_by_role("button", name="Write manually", exact=True)).to_be_visible()
    page.screenshot(path="/tmp/sigma-a7-split-1672.png", full_page=True)
    split.press("Escape")
    expect(split).to_be_focused()
    commands = page.get_by_label(
        "Commands for Explicit formula and test-function approach", exact=True
    )
    commands.click()
    other_commands = page.get_by_label("Commands for Operator construction", exact=True)
    other_commands.focus()
    other_commands.press("Enter")
    assert page.locator(".strategy-commands[open]").count() == 1
    page.get_by_role("heading", name="Strategies", exact=True).click()
    assert page.locator(".strategy-commands[open]").count() == 0
    commands.focus()
    commands.press("Enter")
    commands.press("Escape")
    expect(commands).to_be_focused()
    commands.click()
    panel = page.locator(".strategy-commands[open] .command-panel")
    panel.get_by_text("Actions", exact=True).click()
    page.screenshot(path="/tmp/sigma-a7-actions-1672.png", full_page=True)
    panel.get_by_role("button", name="Change stage", exact=True).click()
    dialog = page.get_by_role("dialog")
    expect(dialog.get_by_label("Manually tracked stage")).to_be_focused()
    snapshot = state.read_bytes()
    dialog.press("Escape")
    expect(commands).to_be_focused()
    assert state.read_bytes() == snapshot
    commands.click()
    panel.get_by_role("button", name="Change stage", exact=True).click()
    dialog.get_by_label("Manually tracked stage").select_option("ready")
    dialog.get_by_role("button", name="Save changes", exact=True).click()
    expect(rows.first.locator(".stage-label")).to_have_text("Ready to explore")
    rows.first.locator(".strategy-detail > summary").click()
    expect(rows.first.locator(".strategy-approach")).to_contain_text("boundary terms")
    assert (
        rows.first.locator(".strategy-expand-arrow").evaluate("e => getComputedStyle(e).transform")
        != "none"
    )
    page.screenshot(path="/tmp/sigma-a7-detail-1672.png", full_page=True)
    rows.first.locator(".strategy-detail > summary").click()
    # Keyboard preview, cancel and persist; storage stays unchanged before drop.
    before = state.read_bytes()
    first_id = rows.first.get_attribute("data-strategy-id")
    grip = page.get_by_role(
        "button", name="Reorder Explicit formula and test-function approach", exact=True
    )
    grip.focus()
    grip.press("Space")
    grip.press("ArrowDown")
    assert state.read_bytes() == before
    expect(rows.nth(1)).to_have_attribute("data-strategy-id", first_id)
    grip.press("Escape")
    expect(rows.first).to_have_attribute("data-strategy-id", first_id)
    grip.press("Space")
    grip.press("ArrowDown")
    grip.press("Enter")
    expect(page.locator(".strategy-list")).to_have_attribute("aria-busy", "false")
    assert json.loads(state.read_bytes())["active_order"][1] == first_id
    page.reload()
    expect(rows.nth(1)).to_have_attribute("data-strategy-id", first_id)
    # Failed order save reverts preview.
    page.route(
        "**/api/projects/strategies/reorder",
        lambda route: route.fulfill(
            status=400, content_type="application/json", body='{"error":"Injected reorder failure"}'
        ),
    )
    grip.focus()
    grip.press("Space")
    grip.press("ArrowDown")
    grip.press("Enter")
    expect(page.get_by_role("alert")).to_have_text("Injected reorder failure")
    expect(rows.nth(1)).to_have_attribute("data-strategy-id", first_id)
    page.unroute("**/api/projects/strategies/reorder")
    # Touch is a real Chrome touch sequence, through pointer capture on the grip.
    page.set_viewport_size({"width": 390, "height": 844})
    grip.scroll_into_view_if_needed()
    rows.nth(2).scroll_into_view_if_needed()
    source = grip.bounding_box()
    target = rows.nth(2).bounding_box()
    cdp = context.new_cdp_session(page)
    x = source["x"] + source["width"] / 2
    y = source["y"] + source["height"] / 2
    cdp.send("Input.dispatchTouchEvent", {"type": "touchStart", "touchPoints": [{"x": x, "y": y}]})
    cdp.send(
        "Input.dispatchTouchEvent",
        {"type": "touchMove", "touchPoints": [{"x": x, "y": target["y"] + target["height"] / 2}]},
    )
    expect(rows.nth(2)).to_have_attribute("data-strategy-id", first_id)
    page.screenshot(path="/tmp/sigma-a7-touch-lift-390.png", full_page=True)
    cdp.send("Input.dispatchTouchEvent", {"type": "touchEnd", "touchPoints": []})
    expect(page.locator(".strategy-list")).to_have_attribute("aria-busy", "false")
    assert json.loads(state.read_bytes())["active_order"][2] == first_id
    page.reload()
    expect(rows.nth(2)).to_have_attribute("data-strategy-id", first_id)
    unchanged = state.read_bytes()
    grip.scroll_into_view_if_needed()
    source = grip.bounding_box()
    cdp.send(
        "Input.dispatchTouchEvent",
        {"type": "touchStart", "touchPoints": [{"x": source["x"] + 10, "y": source["y"] + 10}]},
    )
    cdp.send("Input.dispatchTouchEvent", {"type": "touchCancel", "touchPoints": []})
    expect(grip).to_have_attribute("aria-pressed", "false")
    assert state.read_bytes() == unchanged
    # Pointer drag desktop.
    page.set_viewport_size({"width": 1672, "height": 941})
    source = grip.bounding_box()
    target = rows.first.bounding_box()
    page.mouse.move(source["x"] + 10, source["y"] + 10)
    page.mouse.down()
    page.mouse.move(source["x"] + 10, target["y"] + target["height"] / 2, steps=8)
    page.mouse.up()
    expect(rows.first).to_have_attribute("data-strategy-id", first_id)
    expect(page.locator(".strategy-list")).to_have_attribute("aria-busy", "false")
    # Responsive controls, detail full text and menu. All screenshots use real temporary research.
    for w, h in [(1672, 941), (768, 1024), (390, 844), (320, 844)]:
        page.set_viewport_size({"width": w, "height": h})
        page.evaluate("scrollTo(0,0)")
        assert page.evaluate("document.documentElement.scrollWidth <= innerWidth")
        page.screenshot(path=f"/tmp/sigma-a7-workspace-{w}.png", full_page=True)
    # Manual creation remains usable; menu exclusivity and edit/remove are real.
    page.get_by_role("button", name="New Strategy", exact=True).click()
    page.get_by_label("Title", exact=True).fill("Manual browser idea")
    page.get_by_label("Hypothesis / approach", exact=True).fill(
        "A complete approach.\nRetain all details."
    )
    page.get_by_role("button", name="Save strategy", exact=True).click()
    expect(page.get_by_role("heading", name="Manual browser idea", exact=True)).to_be_focused()
    page.get_by_label("Commands for Manual browser idea", exact=True).click()
    assert page.locator(".strategy-commands[open]").count() == 1
    panel = page.locator(".strategy-commands[open] .command-panel")
    panel.get_by_text("Actions", exact=True).click()
    panel.get_by_role("button", name="Edit", exact=True).click()
    dialog.get_by_label("Name", exact=True).fill("Edited manual idea")
    dialog.get_by_role("button", name="Save changes", exact=True).click()
    expect(page.get_by_role("heading", name="Edited manual idea", exact=True)).to_be_focused()
    page.get_by_label("Commands for Edited manual idea", exact=True).click()
    panel = page.locator(".strategy-commands[open] .command-panel")
    panel.get_by_role("button", name="Remove", exact=True).click()
    dialog.get_by_role("button", name="Remove strategy", exact=True).click()
    expect(page.get_by_role("heading", name="Strategies", exact=True)).to_be_focused()
    assert rows.count() == 4
    # AI fixture: disclosure, no auto-call/save, explicit error then draft review/cancel/retry.
    split.click()
    page.get_by_role("button", name="Generate with AI", exact=True).click()
    expect(
        dialog.get_by_role("textbox", name="Starting point (optional)", exact=True)
    ).to_be_focused()
    expect(dialog.get_by_role("button", name="Generate draft", exact=True)).to_be_enabled()
    before = state.read_bytes()
    dialog.get_by_role("textbox", name="Starting point (optional)", exact=True).fill(
        "error-fixture"
    )
    dialog.get_by_role("button", name="Generate draft", exact=True).click()
    expect(dialog.get_by_role("alert")).to_contain_text("HTTP 500")
    assert state.read_bytes() == before
    dialog.get_by_role("textbox", name="Starting point (optional)", exact=True).fill("")
    dialog.get_by_role("button", name="Generate draft", exact=True).click()
    expect(dialog.get_by_label("Title", exact=True)).to_have_value("Moment matrix obstruction")
    expect(dialog.locator(".agentic-activity")).to_contain_text("Candidate proposed")
    expect(dialog.locator(".agentic-activity")).to_contain_text("distinct")
    assert state.read_bytes() == before
    for w in [1672, 390, 320]:
        page.set_viewport_size({"width": w, "height": 941 if w == 1672 else 844})
        assert dialog.evaluate("(d)=>d.scrollWidth<=d.clientWidth")
        page.screenshot(path=f"/tmp/sigma-a7-ai-review-{w}.png", full_page=True)
    dialog.get_by_label("Title", exact=True).fill("Human revised moment idea")
    page.route(
        "**/api/projects/strategies",
        lambda route: route.fulfill(
            status=400,
            content_type="application/json",
            body='{"error":"Injected acceptance failure"}',
        ),
    )
    dialog.get_by_role("button", name="Save strategy", exact=True).click()
    expect(dialog.get_by_role("alert")).to_have_text("Injected acceptance failure")
    expect(dialog.get_by_label("Title", exact=True)).to_have_value("Human revised moment idea")
    assert state.read_bytes() == before
    page.unroute("**/api/projects/strategies")
    dialog.get_by_role("button", name="Save strategy", exact=True).click()
    expect(
        page.get_by_role("heading", name="Human revised moment idea", exact=True)
    ).to_be_focused()
    raw = json.loads(state.read_bytes())
    assert raw["strategies"][-1]["provenance"] == {
        "provider": "openai",
        "model": "gpt-6.1-sol",
        "reasoning_effort": "high",
    }
    assert raw["strategies"][-1]["stage"] == "draft"
    # Cancelling an in-flight request leaves files unchanged and restores focus.
    split.click()
    page.get_by_role("button", name="Generate with AI", exact=True).click()
    dialog.get_by_role("textbox", name="Starting point (optional)", exact=True).fill(
        "timeout-fixture"
    )
    before = state.read_bytes()
    dialog.get_by_role("button", name="Generate draft", exact=True).click()
    expect(dialog.get_by_role("button", name="Generating…", exact=True)).to_be_disabled()
    dialog.get_by_role("button", name="Cancel request", exact=True).click()
    expect(dialog).to_contain_text("Request cancelled locally")
    expect(
        dialog.get_by_role("textbox", name="Starting point (optional)", exact=True)
    ).to_have_value("timeout-fixture")
    dialog.get_by_role("button", name="Cancel", exact=True).click()
    expect(page.get_by_role("button", name="New Strategy", exact=True)).to_be_focused()
    assert state.read_bytes() == before
    page.emulate_media(reduced_motion="reduce")
    assert rows.first.evaluate("e => getComputedStyle(e).transitionDuration") == "0s"
    assert not errors, errors
    page.unroute_all(behavior="ignoreErrors")
    browser.close()
print(
    "PASS real Chrome: compact/details/menu/stage/manual CRUD, keyboard/pointer/touch reorder and rollback, persisted reload, AI fixture review/accept/error/cancel, responsive screens; no JS errors"
)
