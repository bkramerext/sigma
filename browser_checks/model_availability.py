"""Real Chrome model-control behavior under deterministic HTTP failures."""

import json
import os

from playwright.sync_api import expect, sync_playwright

BASE_URL = os.environ.get("SIGMA_BROWSER_BASE_URL", "http://127.0.0.1:5173").rstrip("/")
FIXTURE_URL = os.environ.get("SIGMA_BROWSER_FIXTURE_URL", "http://127.0.0.1:8001").rstrip("/")


def forward_api(route):
    headers = dict(route.request.headers)
    headers["origin"] = BASE_URL
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
    samples.get_by_role("button", name="Open Maximum Regions Formed by Lines", exact=True).click()
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

    cases = [
        (
            401,
            "Model availability requires an authorized session. Sign in again or contact the SIGMA administrator. Saved settings are unchanged.",
        ),
        (
            403,
            "Model availability requires an authorized session. Sign in again or contact the SIGMA administrator. Saved settings are unchanged.",
        ),
        (
            503,
            "Model availability check failed (HTTP 503). Retry after connectivity is restored. Saved settings are unchanged.",
        ),
    ]
    for status, expected_message in cases:
        page.route(
            "**/api/ai/models",
            lambda route, response_status=status: route.fulfill(
                status=response_status,
                content_type="application/json",
                body=json.dumps({"error": "fixture failure"}),
            ),
        )
        page.reload()
        model = page.locator(".project-model-pill")
        thinking = page.locator(".project-thinking-pill")
        difficulty = page.locator(".project-difficulty-badge")
        expect(model).to_be_disabled()
        expect(thinking).to_be_disabled()
        expect(difficulty).to_be_enabled()
        expect(model).to_contain_text("gpt-6.1-sol")
        expect(thinking).to_contain_text("High")
        expect(page.locator(".project-controls-message")).to_have_text(expected_message)
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
        page.unroute("**/api/ai/models")

    assert not page_errors, page_errors
    browser.close()

print(
    "PASS model catalog HTTP errors preserve saved settings and expose disabled/unverified controls at desktop and mobile widths; no inference calls made."
)
