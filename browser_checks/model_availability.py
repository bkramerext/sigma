"""Real Chrome model-control behavior under deterministic HTTP failures."""

import json
import os

from playwright.sync_api import expect, sync_playwright

BASE_URL = os.environ.get("SIGMA_BROWSER_BASE_URL", "http://127.0.0.1:5173").rstrip("/")
FIXTURE_URL = os.environ.get("SIGMA_BROWSER_FIXTURE_URL", "http://127.0.0.1:8001").rstrip("/")


def forward_api(route):
    headers = dict(route.request.headers)
    headers["origin"] = os.environ.get("SIGMA_BROWSER_REQUEST_ORIGIN", BASE_URL)
    route.fulfill(
        response=route.fetch(url=route.request.url.replace(BASE_URL, FIXTURE_URL), headers=headers)
    )


with sync_playwright() as playwright:
    browser = playwright.chromium.launch(
        executable_path=os.environ.get(
            "SIGMA_BROWSER_EXECUTABLE",
            "/Applications/Google Chrome.app/Contents/MacOS/Google Chrome",
        ),
        headless=True,
    )
    page = browser.new_page(viewport={"width": 1280, "height": 850})
    page_errors: list[str] = []
    page.on("pageerror", lambda error: page_errors.append(str(error)))
    page.route("**/api/**", forward_api)
    page.goto(BASE_URL)
    samples = page.get_by_role("tabpanel", name="Samples", exact=True)
    sample_group = samples.locator("details.sample-type-group").filter(has_text="Mathematics")
    if not sample_group.evaluate("group => group.open"):
        sample_group.locator("summary").click()
    sample = samples.get_by_role("button", name="Open Maximum Regions Formed by Lines", exact=True)
    sample.click()
    expect(page.get_by_role("heading", name="Maximum Regions Formed by Lines")).to_be_visible()
    path = page.evaluate("new URL(location.href).searchParams.get('path')")
    assert path

    saved_before = page.evaluate(
        """async path => {
          const response = await fetch('/api/projects/inspect?' + new URLSearchParams({path}));
          return (await response.json()).project;
        }""",
        path,
    )
    assert saved_before["ai_model"] == "gpt-6.1-sol"
    assert saved_before["reasoning_effort"] == "high"
    assert saved_before["difficulty"] is not None

    # The project no longer owns Model/Thinking controls. Even when the
    # provider catalog fails, the user's saved pair remains readable from
    # home Settings without modifying the project.
    def catalog_failure(response_status):
        def handle(route):
            route.fulfill(
                status=response_status,
                content_type="application/json",
                body=json.dumps({"error": "fixture failure"}),
            )

        return handle

    for status in (401, 403, 503):
        page.route("**/api/ai/models", catalog_failure(status))
        page.goto(BASE_URL)
        page.get_by_role("button", name="Settings", exact=True).click()
        dialog = page.get_by_role("dialog", name="Settings")
        expect(dialog).to_be_visible()
        dialog.get_by_role("tab", name="Model").click()
        model = dialog.locator("#sigma-global-model")
        thinking = dialog.locator("#sigma-global-effort")
        # SIGMA's themed dropdowns are combobox buttons, not native <select>s.
        expect(model).to_have_attribute("role", "combobox")
        expect(model).to_contain_text("gpt-6.1-sol")
        expect(thinking).to_have_attribute("role", "combobox")
        expect(thinking).to_contain_text("High")
        model.click()
        expect(dialog.get_by_role("listbox", name="Model").get_by_role("option")).to_have_count(1)
        expect(dialog.get_by_role("listbox", name="Model").get_by_role("option").first).to_have_attribute("aria-selected", "true")
        model.click()
        expect(dialog.get_by_role("button", name="Save", exact=True)).to_be_disabled()
        for width in (1280, 390, 320):
            page.set_viewport_size({"width": width, "height": 850})
            assert page.evaluate("document.documentElement.scrollWidth <= innerWidth"), width
        saved_after = page.evaluate(
            """async path => {
              const response = await fetch('/api/projects/inspect?' + new URLSearchParams({path}));
              return (await response.json()).project;
            }""",
            path,
        )
        assert {
            key: saved_after[key] for key in ("id", "ai_model", "reasoning_effort", "difficulty")
        } == {
            key: saved_before[key] for key in ("id", "ai_model", "reasoning_effort", "difficulty")
        }
        dialog.get_by_role("button", name="Close Settings").click()
        page.unroute("**/api/ai/models")

    assert not page_errors, page_errors
    browser.close()

print(
    "PASS model catalog HTTP errors preserve saved settings and expose disabled/unverified controls at desktop and mobile widths; no inference calls made."
)
