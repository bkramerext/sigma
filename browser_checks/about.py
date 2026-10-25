"""Real-Chrome About dialog checks from Home and Project at desktop/mobile sizes."""

import os
import re

from playwright.sync_api import expect, sync_playwright

fixture_url = os.environ.get("SIGMA_BROWSER_FIXTURE_URL", "http://127.0.0.1:8026")
ui_url = os.environ.get("SIGMA_BROWSER_BASE_URL", "http://127.0.0.1:5193")
screenshots = os.environ.get("SIGMA_ABOUT_SCREENSHOT_DIR", "/tmp")
api_requests = []

with sync_playwright() as playwright:
    browser = playwright.chromium.launch(
        executable_path=os.environ.get(
            "SIGMA_BROWSER_EXECUTABLE",
            "/Applications/Google Chrome.app/Contents/MacOS/Google Chrome",
        ),
        headless=True,
        args=["--disable-web-security"],
    )
    context = browser.new_context(viewport={"width": 1440, "height": 900}, reduced_motion="reduce")
    page = context.new_page()
    page.on(
        "request",
        lambda request: api_requests.append(request.url) if "/api/" in request.url else None,
    )
    page.route(
        "**/api/**",
        lambda route: route.continue_(url=route.request.url.replace(ui_url, fixture_url)),
    )

    def about_button():
        button = page.locator("button.home-about-button, button.about-action").first
        expect(button).to_be_visible()
        assert button.get_attribute("aria-haspopup") == "dialog"
        return button

    def open_about(click_position=None):
        button = about_button()
        before = len(api_requests)
        button.click(position=click_position)
        dialog = page.get_by_role("dialog", name="About SIGMA")
        expect(dialog).to_be_visible()
        expect(dialog.locator(".about-terms")).to_have_text(
            "Strategies propose. Sessions investigate. Outcomes answer. Reports communicate."
        )
        expect(dialog.get_by_role("button", name="Close", exact=True)).to_be_focused()
        assert len(api_requests) == before, "Opening About made an API request"
        assert dialog.evaluate("element => element.matches(':modal')")
        assert_flow(dialog)
        return button, dialog

    def assert_dialog_fits(viewport_width):
        box = page.locator("dialog.about-dialog").bounding_box()
        assert box is not None
        assert box["x"] >= 0 and box["x"] + box["width"] <= viewport_width
        assert box["width"] <= viewport_width
        assert page.locator("dialog.about-dialog .entry-dialog-header").is_visible()
        assert page.locator("dialog.about-dialog .about-dialog-content").evaluate(
            "element => element.scrollWidth <= element.clientWidth + 1"
        )

    def assert_flow(dialog):
        expect(dialog.locator(".about-architecture")).to_be_visible()
        expect(dialog.locator(".about-flow-project")).to_contain_text("Research Project")
        expect(dialog.locator(".about-strategy-group-heading")).to_contain_text(
            "Persistent Strategies"
        )
        expect(dialog.locator(".about-strategy-card")).to_have_count(3)
        expect(dialog.locator(".about-session-heading")).to_contain_text("Research Session")
        expect(dialog.locator(".about-flow-evidence")).to_contain_text("Outcomes & Saved Evidence")
        expect(dialog.locator("details")).to_have_count(1)

    def assert_interactions(dialog):
        toggle = dialog.locator(".about-session-toggle")
        expect(toggle).to_have_attribute("aria-label", "Explore multi-agent research")
        expect(toggle).to_have_attribute("aria-controls", "about-session-details")
        expect(toggle).to_have_attribute("aria-expanded", "false")
        dialog.locator('[data-about-info-node="session"]').hover()
        page.wait_for_timeout(200)
        expect(dialog.get_by_role("tooltip")).to_have_count(0)
        toggle.hover()
        page.wait_for_timeout(350)
        expect(dialog.get_by_role("tooltip")).to_have_count(0)

        project_region = dialog.locator('[data-about-info-node="project"]')
        project_region.hover()
        page.wait_for_timeout(200)
        expect(dialog.get_by_role("tooltip")).to_have_count(0)
        page.wait_for_timeout(350)
        tip = dialog.get_by_role("tooltip")
        expect(tip).to_contain_text("overarching research question")
        tip_box = tip.bounding_box()
        dialog_box = dialog.bounding_box()
        assert tip_box and dialog_box
        assert tip_box["x"] >= dialog_box["x"]
        assert tip_box["x"] + tip_box["width"] <= dialog_box["x"] + dialog_box["width"]
        page.mouse.move(4, 4)
        help_button = dialog.get_by_role("button", name="Explain Research Project")
        help_button.focus()
        expect(tip).to_contain_text("overarching research question")
        page.keyboard.press("Escape")
        expect(dialog).to_be_visible()
        expect(dialog.get_by_role("tooltip")).to_have_count(0)
        toggle.focus()
        page.keyboard.press("Enter")
        expect(toggle).to_have_attribute("aria-expanded", "true")
        details = dialog.locator("#about-session-details")
        expect(
            details.get_by_role("heading", name="How multi-agent research works")
        ).to_be_visible()
        expect(details.locator(".about-agent-turn")).to_have_count(3)
        expect(details.locator(".about-agent-turn").nth(0)).to_contain_text("01 · INVESTIGATE")
        expect(details.locator(".about-agent-turn").nth(1)).to_contain_text("02 · CHALLENGE")
        expect(details.locator(".about-agent-turn").nth(2)).to_contain_text("03 · REVISIT")
        expect(details.locator(".about-agent-feedback")).to_contain_text(
            "repeat within session limits"
        )
        expect(details.locator(".about-orchestration-band")).to_contain_text(
            "enforces call and cycle limits"
        )
        expect(details.locator(".about-history-chapter")).to_contain_text("persistent strategies")
        expect(details.locator(".about-history-chapter")).to_contain_text("peer strategy")
        expect(details.locator(".about-history-flow")).to_contain_text("Subsequent sessions")
        expect(details.locator(".about-tool-band")).to_contain_text(
            "Python or SageMath when available"
        )
        expect(details.locator(".about-integrity-note")).to_contain_text(
            "neither independently verifies a proof"
        )
        expect(details.locator(".about-agent-feedback")).to_contain_text(
            "Critique changes what comes next"
        )
        assert_dialog_fits(page.viewport_size["width"])
        revisit_help = details.locator(
            '[data-about-info-node="investigatorFollowup"] .about-diagram-help'
        )
        revisit_help.focus()
        expect(dialog.get_by_role("tooltip")).to_contain_text("revise, retract, test, or narrow")
        page.keyboard.press("Escape")
        expect(dialog.get_by_role("tooltip")).to_have_count(0)
        details.locator('[data-about-info-node="workingEvidence"] .about-diagram-help').focus()
        expect(dialog.get_by_role("tooltip")).to_contain_text("selected into bounded role contexts")
        toggle.evaluate("element => element.click()")
        expect(toggle).to_have_attribute("aria-expanded", "false")
        expect(toggle).to_be_focused()
        page.keyboard.press("Space")
        expect(toggle).to_have_attribute("aria-expanded", "true")
        assert dialog.evaluate("e => e.scrollHeight > e.clientHeight")
        dialog.evaluate("e => e.scrollTop = e.scrollHeight")
        assert dialog.evaluate("e => e.scrollTop + e.clientHeight >= e.scrollHeight - 1")
        expect(dialog.locator(".about-flow-evidence")).to_be_visible()

    page.goto(ui_url)
    expect(page.get_by_role("tab", name="Samples", exact=True)).to_be_visible()
    page.wait_for_load_state("networkidle")
    page.get_by_role("tab", name="Recent", exact=True).click()
    expect(page.get_by_role("tab", name="Recent", exact=True)).to_have_attribute(
        "aria-selected", "true"
    )

    button, dialog = open_about()
    assert_dialog_fits(1440)
    page.keyboard.press("Tab")
    expect(dialog.get_by_role("button", name="Explain Research Project")).to_be_focused()
    page.keyboard.press("Escape")
    expect(dialog).to_be_visible()
    expect(dialog.get_by_role("tooltip")).to_have_count(0)
    dialog.screenshot(path=f"{screenshots}/sigma-t46-about-home-desktop.png")
    assert_interactions(dialog)
    dialog.evaluate("element => element.scrollTop = 0")
    dialog.screenshot(path=f"{screenshots}/sigma-about-polish-expanded-desktop.png")
    page.keyboard.press("Escape")
    expect(dialog).not_to_be_visible()
    expect(button).to_be_focused()
    expect(page.get_by_role("tab", name="Recent", exact=True)).to_have_attribute(
        "aria-selected", "true"
    )

    page.get_by_role("tab", name="Samples", exact=True).click()
    page.get_by_role("tabpanel", name="Samples", exact=True).get_by_role(
        "button", name="Open Counting Constrained Binary Strings"
    ).click()
    expect(
        page.get_by_role("heading", name=re.compile(r"Counting Constrained Binary Strings"))
    ).to_be_visible()
    project_url = page.url
    project_header = page.locator(".project-art-header")
    project_controls = project_header.locator(".header-controls")
    about_header = project_controls.locator(".about-action")
    difficulty_header = project_controls.locator(".project-difficulty-badge")
    expect(about_header).to_have_text("About")
    about_desktop_box = about_header.bounding_box()
    difficulty_desktop_box = difficulty_header.bounding_box()
    assert about_desktop_box and difficulty_desktop_box
    assert about_desktop_box["y"] >= difficulty_desktop_box["y"] + difficulty_desktop_box["height"]
    page.screenshot(path=f"{screenshots}/sigma-about-polish-project-header-desktop.png")
    button, dialog = open_about()
    assert_dialog_fits(1440)
    dialog.screenshot(path=f"{screenshots}/sigma-t46-about-project-desktop.png")
    dialog.get_by_role("button", name="Close", exact=True).click()
    expect(dialog).not_to_be_visible()
    expect(button).to_be_focused()
    assert page.url == project_url, "Closing About changed the project route"
    expect(
        page.get_by_role("heading", name=re.compile(r"Counting Constrained Binary Strings"))
    ).to_be_visible()

    page.set_viewport_size({"width": 390, "height": 844})
    project_header = page.locator(".project-art-header")
    project_controls = project_header.locator(".header-controls")
    project_difficulty = project_controls.locator(".project-difficulty-badge")
    about_box = about_button().bounding_box()
    controls_box = project_controls.bounding_box()
    difficulty_box = project_difficulty.bounding_box()
    assert about_box is not None and controls_box is not None and difficulty_box is not None
    expect(about_button()).to_have_text("About")
    assert about_box["width"] >= 44 and about_box["height"] >= 44, about_box
    assert about_box["x"] >= controls_box["x"]
    assert about_box["x"] + about_box["width"] <= controls_box["x"] + controls_box["width"]
    assert about_box["y"] >= difficulty_box["y"] + difficulty_box["height"]
    pseudo_display = about_button().evaluate(
        "element => getComputedStyle(element, '::before').display"
    )
    assert pseudo_display == "none", pseudo_display
    about_button().evaluate("element => element.blur()")
    page.screenshot(path=f"{screenshots}/sigma-about-polish-project-header-mobile.png")
    page.screenshot(path=f"{screenshots}/sigma-t46-about-project-header-mobile.png")
    button, dialog = open_about(click_position={"x": 2, "y": 22})
    assert_dialog_fits(390)
    dialog.screenshot(path=f"{screenshots}/sigma-t46-about-project-mobile.png")
    page.keyboard.press("Escape")
    expect(dialog).not_to_be_visible()
    expect(button).to_be_focused()
    assert page.url == project_url

    page.get_by_role("button", name="Back to home", exact=True).click()
    expect(page.get_by_role("tab", name="Samples", exact=True)).to_be_visible()
    selected_home_tab = page.locator('[role="tab"][aria-selected="true"]').get_attribute("id")
    button, dialog = open_about()
    assert_dialog_fits(390)
    assert_interactions(dialog)
    dialog.evaluate("element => element.scrollTop = 0")
    dialog.screenshot(path=f"{screenshots}/sigma-about-polish-expanded-mobile.png")
    dialog.screenshot(path=f"{screenshots}/sigma-t46-about-home-mobile.png")
    page.keyboard.press("Escape")
    expect(dialog).not_to_be_visible()
    expect(button).to_be_focused()
    assert (
        page.locator('[role="tab"][aria-selected="true"]').get_attribute("id") == selected_home_tab
    )
    page.set_viewport_size({"width": 320, "height": 740})
    button, dialog = open_about()
    assert_dialog_fits(320)
    assert_interactions(dialog)
    dialog.evaluate("element => element.scrollTop = 0")
    dialog.screenshot(path=f"{screenshots}/sigma-about-polish-mobile-320.png")
    dialog.get_by_role("button", name="Close", exact=True).click()
    expect(dialog).not_to_be_visible()
    expect(button).to_be_focused()

    for width, height, suffix in [
        (1440, 1800, "desktop"),
        (390, 2800, "mobile-390"),
        (320, 3200, "mobile-320"),
    ]:
        page.set_viewport_size({"width": width, "height": height})
        button, dialog = open_about()
        assert_dialog_fits(width)
        dialog.screenshot(path=f"{screenshots}/about-multiagent-collapsed-{suffix}.png")
        toggle = dialog.locator(".about-session-toggle")
        toggle.click()
        expect(toggle).to_have_attribute("aria-expanded", "true")
        assert_dialog_fits(width)
        dialog.screenshot(path=f"{screenshots}/about-multiagent-expanded-{suffix}.png")
        dialog.locator(".about-session-detail").screenshot(
            path=f"{screenshots}/about-multiagent-chapter-{suffix}.png"
        )
        dialog.get_by_role("button", name="Close", exact=True).click()
        expect(dialog).not_to_be_visible()
        expect(button).to_be_focused()

    touch = browser.new_context(
        viewport={"width": 390, "height": 844}, is_mobile=True, has_touch=True
    )
    touch_page = touch.new_page()
    touch_page.route(
        "**/api/**",
        lambda route: route.continue_(url=route.request.url.replace(ui_url, fixture_url)),
    )
    touch_page.goto(ui_url)
    opener = touch_page.locator("button.home-about-button")
    opener.tap()
    touch_dialog = touch_page.get_by_role("dialog", name="About SIGMA")
    expect(touch_dialog).to_be_visible()
    touch_page.get_by_role("button", name="Explain Research Project").tap()
    expect(touch_dialog.get_by_role("tooltip")).to_contain_text("overarching research question")
    touch_dialog.get_by_role("button", name="Explore multi-agent research").tap()
    expect(
        touch_dialog.get_by_role("region", name="How multi-agent research works")
    ).to_be_visible()
    touch_dialog.get_by_role("button", name="Close", exact=True).tap()
    expect(touch_dialog).not_to_be_visible()
    expect(opener).to_be_focused()
    touch.close()
    browser.close()

print(
    "PASS About dialog in real Chrome at 1440px, 390px and 320px, from Home and Project; "
    "flow hierarchy, hover/focus/touch help, critique loop, dialog scrolling, modal keyboard "
    "behavior, focus restoration, route/tab preservation and mobile Project hit area"
)
