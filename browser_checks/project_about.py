"""Real Chrome checks that the workspace About action opens and closes accessibly."""

import os

from playwright.sync_api import expect, sync_playwright

BASE_URL = os.environ.get("SIGMA_BROWSER_BASE_URL", "http://127.0.0.1:5173").rstrip("/")
FIXTURE_URL = os.environ.get("SIGMA_BROWSER_FIXTURE_URL", "http://127.0.0.1:8026").rstrip("/")

with sync_playwright() as playwright:
    browser = playwright.chromium.launch(
        executable_path=os.environ.get(
            "SIGMA_BROWSER_EXECUTABLE",
            "/Applications/Google Chrome.app/Contents/MacOS/Google Chrome",
        ),
        headless=True,
    )
    page = browser.new_page(viewport={"width": 1440, "height": 900})
    page_errors: list[str] = []
    api_requests: list[str] = []
    page.on("pageerror", lambda error: page_errors.append(str(error)))
    page.on(
        "request",
        lambda request: api_requests.append(request.url) if "/api/" in request.url else None,
    )
    page.route(
        "**/api/**",
        lambda route: route.continue_(url=route.request.url.replace(BASE_URL, FIXTURE_URL)),
    )

    page.goto(BASE_URL)
    samples = page.get_by_role("tab", name="Samples", exact=True)
    expect(samples).to_be_visible()
    page.get_by_role("tabpanel", name="Samples", exact=True).get_by_role(
        "button", name="Open Counting Constrained Binary Strings", exact=True
    ).click()
    expect(page.get_by_role("heading", name="Counting Constrained Binary Strings")).to_be_visible()
    project_url = page.url
    about_button = page.get_by_role("button", name="About SIGMA", exact=True)

    for width, height in ((1440, 900), (390, 844)):
        page.set_viewport_size({"width": width, "height": height})
        requests_before = len(api_requests)
        about_button.click()
        dialog = page.get_by_role("dialog", name="About SIGMA")
        expect(dialog).to_be_visible()
        expect(dialog.locator(".about-intro")).to_contain_text("research workbench")
        expect(dialog.locator(".about-terms")).to_have_text(
            "Strategies set direction. Sessions investigate. Outcomes assess. Reports communicate."
        )
        assert len(api_requests) == requests_before, "Opening About made an API request"
        assert dialog.evaluate("element => element.matches(':modal')")
        box = dialog.bounding_box()
        assert box and box["x"] >= 0 and box["x"] + box["width"] <= width, (width, box)
        page.keyboard.press("Escape")
        expect(dialog).not_to_be_visible()
        expect(about_button).to_be_focused()
        assert page.url == project_url

    assert not page_errors, page_errors
    browser.close()

print(
    "PASS Project About opens from the workspace at 1440px and 390px, makes no API request, and restores focus on Escape."
)
