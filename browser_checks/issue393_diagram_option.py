"""Real-Chrome acceptance for the experimental paper diagram preference."""

import os

from playwright.sync_api import expect, sync_playwright

origin = os.environ.get("SIGMA_DIAGRAM_UI_ORIGIN", "http://127.0.0.1:5194")
with sync_playwright() as playwright:
    browser = playwright.chromium.launch(
        executable_path=os.environ.get(
            "SIGMA_BROWSER_EXECUTABLE",
            "/Applications/Google Chrome.app/Contents/MacOS/Google Chrome",
        ),
        headless=True,
    )
    context = browser.new_context(viewport={"width": 1440, "height": 1000})
    page = context.new_page()
    page.goto(origin + "/")
    samples = page.get_by_role("tab", name="Samples", exact=True)
    if samples.get_attribute("aria-selected") != "true":
        samples.click()
    page.locator("details.sample-type-group").filter(has_text="Computer Science").locator("summary").click(timeout=10_000)
    button = page.get_by_role("button", name="Open Sovereign AI Federation", exact=True)
    expect(button).to_be_visible(timeout=10_000)
    button.click()
    page.wait_for_url("**/project?*")
    page.get_by_role("button", name="LaTeX research paper", exact=True).click()
    dialog = page.get_by_role("dialog", name="Academic paper using LaTeX")
    option = dialog.get_by_role("checkbox", name="Include diagrams (experimental)")
    expect(option).to_be_visible()
    expect(option).not_to_be_checked()
    option.check()
    expect(option).to_be_checked()
    page.reload()
    page.get_by_role("button", name="LaTeX research paper", exact=True).click()
    dialog = page.get_by_role("dialog", name="Academic paper using LaTeX")
    expect(dialog.get_by_role("checkbox", name="Include diagrams (experimental)")).to_be_checked()
    dialog.get_by_role("checkbox", name="Include diagrams (experimental)").uncheck()
    expect(
        dialog.get_by_role("checkbox", name="Include diagrams (experimental)")
    ).not_to_be_checked()
    print("PASS diagram option default-off and persistence in real Chrome")
    browser.close()
