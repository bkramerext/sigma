"""Real-Chrome image load checks on Home and a Sample Project at two widths."""

import re

from playwright.sync_api import expect, sync_playwright

BASE_URL = "http://127.0.0.1:5173"
IMAGE_URL = re.compile(r"\.(?:png|jpe?g|gif|webp|svg|ico|avif)(?:$|[?#])", re.I)

with sync_playwright() as playwright:
    browser = playwright.chromium.launch(
        executable_path="/Applications/Google Chrome.app/Contents/MacOS/Google Chrome",
        headless=True,
    )
    page = browser.new_page(viewport={"width": 1440, "height": 900}, reduced_motion="reduce")
    image_failures = []
    page_errors = []
    page.on(
        "response",
        lambda response: image_failures.append((response.status, response.url))
        if IMAGE_URL.search(response.url) and response.status >= 400
        else None,
    )
    page.on("pageerror", lambda error: page_errors.append(str(error)))

    def check_images(label):
        broken = page.locator("img").evaluate_all(
            "items => items.filter(image => !image.complete || image.naturalWidth === 0)"
            ".map(image => image.currentSrc || image.src)"
        )
        assert not broken, f"{label}: broken img elements: {broken}"
        assert not image_failures, f"{label}: failed image requests: {image_failures}"
        assert not page_errors, f"{label}: browser errors: {page_errors}"

    try:
        for width in (1440, 390):
            page.set_viewport_size({"width": width, "height": 900 if width > 400 else 844})
            page.goto(BASE_URL, wait_until="networkidle")
            expect(page.get_by_role("tab", name="Samples", exact=True)).to_be_visible()
            check_images(f"Home {width}px")
            page.screenshot(path=f"/tmp/sigma-t79-home-{width}.png", full_page=True)

            samples_tab = page.get_by_role("tab", name="Samples", exact=True)
            if samples_tab.get_attribute("aria-selected") != "true":
                samples_tab.click()
            page.locator(
                '.sample-open[aria-label="Open Counting Constrained Binary Strings"]'
            ).click()
            expect(
                page.get_by_role("heading", name=re.compile("Counting Constrained Binary Strings"))
            ).to_be_visible()
            page.wait_for_load_state("networkidle")
            check_images(f"Project {width}px")
            page.screenshot(path=f"/tmp/sigma-t79-project-{width}.png", full_page=True)
    finally:
        browser.close()

print(
    "PASS real Chrome Home and Sample Project at 1440px and 390px; all img elements "
    "loaded, no failed image requests or browser errors"
)
