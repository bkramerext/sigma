"""Real Chrome checks that the workspace About action opens and closes accessibly."""

import os
from pathlib import Path

from playwright.sync_api import expect, sync_playwright

BASE_URL = os.environ.get("SIGMA_BROWSER_BASE_URL", "http://127.0.0.1:5173").rstrip("/")
FIXTURE_URL = os.environ.get("SIGMA_BROWSER_FIXTURE_URL", "http://127.0.0.1:8026").rstrip("/")
EVIDENCE = Path("docs/evaluations/t313/evidence")

with sync_playwright() as playwright:
    EVIDENCE.mkdir(parents=True, exist_ok=True)
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

    def proxy(route):
        headers = dict(route.request.headers)
        headers["origin"] = "http://127.0.0.1:5173"
        response = route.fetch(
            url=route.request.url.replace(BASE_URL, FIXTURE_URL), headers=headers
        )
        route.fulfill(response=response)

    page.route("**/api/**", proxy)

    page.goto(BASE_URL)
    samples = page.get_by_role("tab", name="Samples", exact=True)
    expect(samples).to_be_visible()
    samples_panel = page.get_by_role("tabpanel", name="Samples", exact=True)
    samples_panel.locator(".sample-type-group").filter(has_text="Mathematics").locator(
        "summary"
    ).click()
    samples_panel.get_by_role(
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
        appearance = dialog.evaluate(
            "element => { const root = getComputedStyle(element); const heading = getComputedStyle(element.querySelector('h2')); const content = getComputedStyle(element.querySelector('.about-dialog-content')); return { background: root.backgroundColor, border: root.borderTopColor, borderWidth: root.borderTopWidth, radius: root.borderRadius, headingColor: heading.color, contentFont: content.fontFamily, contentColor: content.color }; }"
        )
        assert appearance == {
            "background": "rgb(7, 17, 30)",
            "border": "rgb(169, 101, 72)",
            "borderWidth": "1px",
            "radius": "8px",
            "headingColor": "rgb(229, 173, 143)",
            "contentFont": "Inter, ui-sans-serif, system-ui, sans-serif",
            "contentColor": "rgb(196, 206, 216)",
        }, (width, appearance)
        expect(dialog.locator(".about-intro")).to_contain_text("research workbench")
        expect(dialog.locator(".about-disclosure")).to_have_count(4)
        expect(dialog.get_by_role("link", name="Terms of Service", exact=True)).to_be_visible()
        assert len(api_requests) == requests_before, "Opening About made an API request"
        assert dialog.evaluate("element => element.matches(':modal')")
        box = dialog.bounding_box()
        assert box and box["x"] >= 0 and box["x"] + box["width"] <= width, (width, box)
        page.screenshot(path=str(EVIDENCE / f"project-about-{width}.png"))
        page.keyboard.press("Escape")
        expect(dialog).not_to_be_visible()
        expect(about_button).to_be_focused()
        assert page.url == project_url

    assert not page_errors, page_errors
    browser.close()

print(
    "PASS Project About opens from the workspace at 1440px and 390px, makes no API request, and restores focus on Escape."
)
