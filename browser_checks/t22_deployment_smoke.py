"""Real Chrome to Worker dev server to live local API container; no API mocks."""

from __future__ import annotations

import os
from urllib.parse import urljoin

from playwright.sync_api import expect, sync_playwright

base = os.environ.get("SIGMA_BROWSER_BASE_URL", "http://127.0.0.1:8787")
errors: list[str] = []
requests: list[str] = []

with sync_playwright() as playwright:
    browser = playwright.chromium.launch(
        executable_path=os.environ.get(
            "SIGMA_BROWSER_EXECUTABLE", "/Applications/Google Chrome.app/Contents/MacOS/Google Chrome"
        ),
        headless=True,
    )
    page = browser.new_page(viewport={"width": 1440, "height": 1000}, accept_downloads=True)
    page.on("pageerror", lambda error: errors.append(str(error)))
    page.on("console", lambda message: errors.append(message.text) if message.type == "error" else None)
    page.on("request", lambda request: requests.append(request.url) if "/api/" in request.url else None)
    page.goto(urljoin(base, "/demo"), wait_until="networkidle")
    expect(page.get_by_role("heading", name="Explore a SIGMA research project")).to_be_visible()
    expect(page.get_by_role("heading", name="Counting Pairwise Handshakes")).to_be_visible()
    expect(page.get_by_text("Direct counting", exact=True)).to_be_visible()
    expect(page.get_by_role("heading", name="Research sessions")).to_be_visible()
    page.get_by_text("Session #1: Direct counting", exact=False).click()
    expect(page.get_by_text("Saved research artifacts")).to_be_visible()
    expect(page.get_by_text("Inspect saved computation")).to_be_visible()

    audit = page.request.get(urljoin(base, "/api/cloud-demo/"))
    assert audit.status == 200 and '"export_version":2' in audit.text().replace(" ", "")
    for extension, expected in (
        ("txt", "Research problem:"),
        ("html", "<!doctype html>"),
        ("tex", "\\documentclass"),
    ):
        response = page.request.get(urljoin(base, f"/api/cloud-demo/report?format={extension}"))
        assert response.status == 200, (extension, response.status)
        assert expected in response.text(), extension
        assert response.headers.get("cache-control") == "no-store"

    private = page.request.get(urljoin(base, "/api/projects/recent"))
    assert private.status == 401, (private.status, private.text())
    mutation = page.request.post(
        urljoin(base, "/api/projects/init"),
        data={"title": "must not create"},
        headers={"Origin": "http://127.0.0.1:8787"},
    )
    assert mutation.status in (401, 403), (mutation.status, mutation.text())
    assert any("/api/cloud-demo/" in item for item in requests)
    assert not errors, errors
    page.set_viewport_size({"width": 390, "height": 844})
    page.reload(wait_until="networkidle")
    expect(page.get_by_role("heading", name="Counting Pairwise Handshakes")).to_be_visible()
    assert page.locator("body").evaluate("el => el.scrollWidth <= window.innerWidth")
    browser.close()

print("real Chrome-to-Worker-to-API deployment smoke passed (local deterministic fixture only)")
