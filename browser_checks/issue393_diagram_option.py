"""Real-Chrome acceptance for the default-on diagram-and-table preference."""

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
    errors: list[str] = []
    page.on("pageerror", lambda error: errors.append(str(error)))
    page.on(
        "response",
        lambda response: (
            print(f"API {response.status} {response.url}")
            if "/api/projects/samples/open" in response.url
            else None
        ),
    )
    page.goto(origin + "/")
    samples = page.get_by_role("tab", name="Samples", exact=True)
    if samples.get_attribute("aria-selected") != "true":
        samples.click()
    page.locator("details.sample-type-group").filter(has_text="Computer Science").locator(
        "summary"
    ).click(timeout=10_000)
    button = page.get_by_role("button", name="Open Sovereign AI Federation", exact=True)
    expect(button).to_be_visible(timeout=10_000)
    button.click()
    try:
        page.wait_for_url("**/project?*", timeout=10_000)
    except Exception:
        page.screenshot(path="/tmp/sigma-issue393-open-failure.png", full_page=True)
        print(
            "sample-open diagnostic",
            page.url,
            "alerts",
            page.locator('[role="alert"]').all_text_contents(),
            "page errors",
            errors,
        )
        raise
    page.get_by_role("button", name="LaTeX research paper", exact=True).click()
    dialog = page.get_by_role("dialog", name="Academic paper using LaTeX")
    option = dialog.get_by_role("checkbox", name="Include diagrams and tables")
    expect(option).to_be_visible()
    expect(option).to_be_checked()
    option.uncheck()
    expect(option).not_to_be_checked()
    page.reload()
    page.get_by_role("button", name="LaTeX research paper", exact=True).click()
    dialog = page.get_by_role("dialog", name="Academic paper using LaTeX")
    option = dialog.get_by_role("checkbox", name="Include diagrams and tables")
    expect(option).not_to_be_checked()
    option.check()
    expect(dialog.get_by_role("checkbox", name="Include diagrams and tables")).to_be_checked()
    print("PASS diagram-and-table option default-on and persistence in real Chrome")
    browser.close()
