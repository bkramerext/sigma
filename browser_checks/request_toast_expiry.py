"""Real-Chrome checks for request-toast expiry, exit motion and responsive layout."""

import json
import os
import time
from urllib.parse import urlsplit

from playwright.sync_api import expect, sync_playwright

UI_URL = os.environ.get("SIGMA_BROWSER_BASE_URL", "http://127.0.0.1:5173")
CHROME = os.environ.get(
    "SIGMA_BROWSER_EXECUTABLE", "/Applications/Google Chrome.app/Contents/MacOS/Google Chrome"
)


with sync_playwright() as playwright:
    browser = playwright.chromium.launch(executable_path=CHROME, headless=True)
    context = browser.new_context(viewport={"width": 1440, "height": 900})
    page = context.new_page()
    page.clock.install()
    page.route(
        "**/api/cloud-auth/status",
        lambda route: route.fulfill(
            status=200,
            content_type="application/json",
            body=json.dumps(
                {
                    "enabled": False,
                    "ready": True,
                    "authenticated": False,
                    "user": None,
                    "target": "local",
                    "local_setup_missing": [],
                }
            ),
        ),
    )
    page.route(
        "**/api/toast-expiry-fixture**",
        lambda route: route.fulfill(
            status=503,
            content_type="application/json",
            body=json.dumps({"error": urlsplit(route.request.url).query or "fixture failure"}),
        ),
    )
    page.goto(UI_URL)

    def fail(label: str) -> None:
        page.evaluate(
            "label => fetch('/api/toast-expiry-fixture?' + encodeURIComponent(label))",
            label,
        )

    first = page.locator(".request-toast").filter(has_text="first")
    fail("first")
    expect(first).to_be_visible()
    page.clock.fast_forward(59_000)
    expect(first).to_have_attribute("data-phase", "visible")
    page.clock.fast_forward(1_000)
    expect(first).to_have_attribute("data-phase", "exiting")
    time.sleep(0.04)
    style = first.evaluate(
        "el => ({transform: getComputedStyle(el).transform, y: new DOMMatrixReadOnly(getComputedStyle(el).transform).m42, transition: getComputedStyle(el).transitionDuration})"
    )
    assert style["transition"] == "0.32s, 0.32s" or "0.32s" in style["transition"], style
    assert style["y"] > 0, style
    time.sleep(0.36)
    expect(first).to_have_count(0)

    fail("remaining")
    fail("dismissed")
    remaining = page.locator(".request-toast").filter(has_text="remaining")
    dismissed = page.locator(".request-toast").filter(has_text="dismissed")
    expect(remaining).to_be_visible()
    expect(dismissed).to_be_visible()
    before_top = remaining.evaluate("el => el.getBoundingClientRect().top")
    dismissed.get_by_role("button", name="Dismiss request error").click()
    expect(dismissed).to_have_attribute("data-phase", "exiting")
    time.sleep(0.36)
    expect(dismissed).to_have_count(0)
    after_top = remaining.evaluate("el => el.getBoundingClientRect().top")
    assert after_top > before_top, {"before": before_top, "after": after_top}

    page.set_viewport_size({"width": 390, "height": 844})
    fail("mobile")
    mobile = page.locator(".request-toast").filter(has_text="mobile")
    expect(mobile).to_be_visible()
    assert mobile.evaluate("el => el.getBoundingClientRect().width") <= 360
    assert page.evaluate("document.documentElement.scrollWidth <= innerWidth")
    page.emulate_media(reduced_motion="reduce")
    page.clock.fast_forward(60_000)
    expect(mobile).to_have_count(0)
    browser.close()

print(
    "PASS real Chrome toast timeout, exit/reflow, manual dismiss, reduced motion and mobile layout"
)
