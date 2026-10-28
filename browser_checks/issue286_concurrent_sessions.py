"""Real Chrome acceptance for per-project concurrent-session Limits settings."""

import json
import os

from playwright.sync_api import expect, sync_playwright

UI = os.environ.get("SIGMA_BROWSER_BASE_URL", "http://127.0.0.1:5173").rstrip("/")
API = os.environ.get("SIGMA_BROWSER_FIXTURE_URL", "http://127.0.0.1:8002").rstrip("/")
CHROME = os.environ.get(
    "SIGMA_BROWSER_EXECUTABLE",
    "/Applications/Google Chrome.app/Contents/MacOS/Google Chrome",
)

with sync_playwright() as playwright:
    browser = playwright.chromium.launch(
        executable_path=CHROME, headless=True, args=["--disable-web-security"]
    )
    page = browser.new_page(viewport={"width": 1280, "height": 850})
    errors = []
    page.on("pageerror", lambda error: errors.append(str(error)))

    def forward(route):
        if route.request.url.endswith("/api/cloud-auth/status"):
            route.fulfill(
                status=200,
                content_type="application/json",
                body=json.dumps(
                    {
                        "target": "local",
                        "enabled": True,
                        "ready": True,
                        "authenticated": True,
                        "user": {"email": "issue286-member@example.test", "role": "member"},
                        "admin_contact_email": None,
                    }
                ),
            )
            return
        route.fulfill(response=route.fetch(url=route.request.url.replace(UI, API)))

    page.route("**/api/**", forward)
    page.goto(UI)
    samples = page.get_by_role("tabpanel", name="Samples")
    mathematics = samples.locator("details.sample-type-group").filter(has_text="Mathematics")
    if not mathematics.evaluate("group => group.open"):
        mathematics.locator("summary").click()
    samples.get_by_role(
        "button", name="Open Counting Constrained Binary Strings", exact=True
    ).click()
    expect(page.get_by_role("heading", name="Project")).to_be_visible()
    page.get_by_role("button", name="Project settings", exact=True).click()
    settings = page.get_by_role("dialog", name="Settings")
    settings.get_by_role("tab", name="Limits", exact=True).click()
    concurrent = settings.get_by_label("Maximum concurrent sessions")
    expect(concurrent).to_have_value("1")

    concurrent.fill("0")
    expect(settings.get_by_role("alert").filter(has_text="positive whole number")).to_be_visible()
    expect(settings.get_by_role("button", name="Save", exact=True)).to_be_disabled()

    chosen_limit = "9" * 80
    concurrent.fill(chosen_limit)
    expect(settings.get_by_role("button", name="Save", exact=True)).to_be_enabled()
    page.set_viewport_size({"width": 390, "height": 420})
    panel = settings.locator("#settings-panel-limits")
    box = settings.bounding_box()
    assert box and box["x"] >= 0 and box["x"] + box["width"] <= 390
    assert panel.evaluate("e => e.scrollHeight >= e.clientHeight")
    settings.get_by_role("button", name="Save", exact=True).click()
    expect(settings).to_have_count(0)

    saved = page.evaluate(
        """async () => {
          const path = new URL(location.href).searchParams.get('path');
          const response = await fetch('/api/projects/research-limits?' + new URLSearchParams({path}));
          return await response.json();
        }"""
    )
    assert saved["max_concurrent_sessions"] == chosen_limit, saved
    page.reload()
    page.get_by_role("button", name="Project settings", exact=True).click()
    settings = page.get_by_role("dialog", name="Settings")
    settings.get_by_role("tab", name="Limits", exact=True).click()
    expect(settings.get_by_label("Maximum concurrent sessions")).to_have_value(chosen_limit)
    assert not errors, errors
    print(
        "PASS real Chrome Project Settings → Limits: default 1, positive validation, no UI ceiling, responsive save/reopen"
    )
    browser.close()
