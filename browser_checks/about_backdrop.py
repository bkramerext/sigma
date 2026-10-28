"""Real Chrome check that clicking outside About closes it and restores focus."""

import os

from playwright.sync_api import expect, sync_playwright

UI = os.environ.get("SIGMA_BROWSER_BASE_URL", "http://127.0.0.1:5187").rstrip("/")

with sync_playwright() as playwright:
    browser = playwright.chromium.launch(
        executable_path=os.environ.get(
            "SIGMA_BROWSER_EXECUTABLE",
            "/Applications/Google Chrome.app/Contents/MacOS/Google Chrome",
        ),
        headless=True,
    )
    page = browser.new_page(viewport={"width": 1280, "height": 800})
    page.route(
        "**/api/**",
        lambda route: route.fulfill(
            status=200,
            content_type="application/json",
            body='{"enabled":false,"ready":true,"authenticated":true,"projects":[],"accounts":[],"status":"disconnected"}',
        ),
    )
    page.goto(UI + "/")
    opener = page.get_by_role("button", name="About SIGMA", exact=True)
    opener.click()
    dialog = page.get_by_role("dialog", name="About SIGMA")
    expect(dialog).to_be_visible()
    page.mouse.click(1, 1)
    expect(dialog).to_have_count(0)
    expect(opener).to_be_focused()
    browser.close()

print("PASS real Chrome About backdrop click closes the dialog and restores focus.")
