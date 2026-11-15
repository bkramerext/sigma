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
        button = page.get_by_role("button", name="About SIGMA", exact=True)
        expect(button).to_be_visible()
        expect(button).to_have_attribute("data-tooltip", "About SIGMA")
        return button

    def open_about(click_position=None):
        button = about_button()
        before = len(api_requests)
        button.focus()
        expect(page.locator("#sigma-ui-tooltip")).to_have_text("About SIGMA")
        button.click(position=click_position)
        dialog = page.get_by_role("dialog", name="About SIGMA")
        expect(dialog).to_be_visible()
        expect(dialog.locator("#about-message")).to_have_text(
            "Strategies propose. Sessions investigate. Outcomes answer. Reports communicate."
        )
        expect(dialog.get_by_role("button", name="Close", exact=True)).to_be_focused()
        assert len(api_requests) == before, "Opening About made an API request"
        assert dialog.evaluate("element => element.matches(':modal')")
        return button, dialog

    def assert_dialog_fits(viewport_width):
        box = page.locator("dialog.about-dialog").bounding_box()
        assert box is not None
        assert box["x"] >= 0 and box["x"] + box["width"] <= viewport_width
        assert box["width"] <= viewport_width
        assert page.locator("dialog.about-dialog .settings-header").is_visible()
        assert page.locator("dialog.about-dialog .about-body").evaluate(
            "element => element.scrollWidth <= element.clientWidth + 1"
        )

    page.goto(ui_url)
    expect(page.get_by_role("tab", name="Samples", exact=True)).to_be_visible()
    page.wait_for_load_state("networkidle")
    page.get_by_role("tab", name="Recent", exact=True).click()
    expect(page.get_by_role("tab", name="Recent", exact=True)).to_have_attribute(
        "aria-selected", "true"
    )

    button, dialog = open_about()
    assert_dialog_fits(1440)
    page.screenshot(path=f"{screenshots}/sigma-t46-about-home-desktop.png", full_page=True)
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
    button, dialog = open_about()
    assert_dialog_fits(1440)
    page.screenshot(path=f"{screenshots}/sigma-t46-about-project-desktop.png", full_page=True)
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
    assert about_box["width"] >= 44 and about_box["height"] >= 44, about_box
    assert about_box["x"] + about_box["width"] <= controls_box["x"] + controls_box["width"]
    assert difficulty_box["x"] + difficulty_box["width"] <= about_box["x"]
    assert (
        abs(
            (about_box["y"] + about_box["height"] / 2)
            - (difficulty_box["y"] + difficulty_box["height"] / 2)
        )
        <= 8
    ), "Mobile About action is not alongside the top-right header controls"
    compact_pill = about_button().evaluate("element => getComputedStyle(element, '::before').inset")
    assert compact_pill == "7px", compact_pill
    about_button().evaluate("element => element.blur()")
    page.screenshot(path=f"{screenshots}/sigma-t46-about-project-header-mobile.png")
    button, dialog = open_about(click_position={"x": 2, "y": 22})
    assert_dialog_fits(390)
    page.screenshot(path=f"{screenshots}/sigma-t46-about-project-mobile.png", full_page=True)
    page.keyboard.press("Escape")
    expect(dialog).not_to_be_visible()
    expect(button).to_be_focused()
    assert page.url == project_url

    page.get_by_role("button", name="Back to home", exact=True).click()
    expect(page.get_by_role("tab", name="Samples", exact=True)).to_be_visible()
    selected_home_tab = page.locator('[role="tab"][aria-selected="true"]').get_attribute("id")
    button, dialog = open_about()
    assert_dialog_fits(390)
    page.screenshot(path=f"{screenshots}/sigma-t46-about-home-mobile.png", full_page=True)
    dialog.get_by_role("button", name="Close", exact=True).click()
    expect(dialog).not_to_be_visible()
    expect(button).to_be_focused()
    assert (
        page.locator('[role="tab"][aria-selected="true"]').get_attribute("id") == selected_home_tab
    )
    browser.close()

print(
    "PASS About dialog from Home and Project at 1440px/390px; native modal semantics, "
    "exact tooltip/accessible label, no About API calls, Escape/Close focus restoration, "
    "route/tab state preservation, viewport fit, and 44px mobile Project hit area"
)
