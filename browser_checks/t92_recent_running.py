"""T92 real-Chromium acceptance: active Recent status, polling, mobile and reload.

Uses an isolated local fixture API; status alone is controlled at the transport
boundary. No provider requests or research work are dispatched.
"""

import json
import os
from pathlib import Path

from playwright.sync_api import expect, sync_playwright

UI = os.environ.get("SIGMA_RECENTS_UI_ORIGIN", "http://127.0.0.1:5173").rstrip("/")
API = os.environ.get("SIGMA_RECENTS_API_ORIGIN", "http://127.0.0.1:8001").rstrip("/")
running: set[str] = set()

with sync_playwright() as playwright:
    browser = playwright.chromium.launch(
        executable_path=os.environ.get(
            "SIGMA_BROWSER_EXECUTABLE",
            "/Applications/Google Chrome.app/Contents/MacOS/Google Chrome",
        ),
        headless=True,
    )
    page = browser.new_page(viewport={"width": 1280, "height": 720})
    errors: list[str] = []
    page.on("pageerror", lambda error: errors.append(str(error)))

    def forward(route):
        response = route.fetch(url=route.request.url.replace(UI, API))
        if route.request.url.split("?", 1)[0] == f"{UI}/api/projects/recent":
            data = response.json()
            for entry in data["projects"]:
                entry["research_running"] = entry["id"] in running
            route.fulfill(response=response, body=json.dumps(data))
        else:
            route.fulfill(response=response)

    page.route("**/api/**", forward)
    page.goto(UI)
    samples = page.get_by_role("tabpanel", name="Samples")
    samples.get_by_role("button", name="Open Nonconsecutive Subset Sums Modulo 3").click()
    expect(page.get_by_role("heading", name="Nonconsecutive Subset Sums Modulo 3 v1")).to_be_visible()
    project_path = page.evaluate("new URL(location.href).searchParams.get('path')")
    project_id = json.loads(Path(project_path, "project.json").read_text())["id"]
    page.get_by_role("button", name="Back to home", exact=True).click()
    recent = page.get_by_role("tabpanel", name="Recent")
    entry = recent.get_by_role("button", name="Nonconsecutive Subset Sums Modulo 3 v1", exact=True)
    expect(entry).to_be_visible()
    metadata = entry.locator("xpath=../..").locator(".recent-meta-row > small > span")
    initial = metadata.inner_text()
    assert "Running" not in initial and initial.count(" · ") == 1, initial

    running.add(project_id)
    expect(metadata).to_contain_text(" · Running · ", timeout=10000)
    label = metadata.locator(".recent-running")
    assert label.evaluate("e => getComputedStyle(e).color") == "rgb(143, 189, 154)"
    for width, height in ((1280, 720), (390, 844), (320, 700)):
        page.set_viewport_size({"width": width, "height": height})
        expect(label).to_be_visible()
        assert page.evaluate("document.documentElement.scrollWidth <= innerWidth"), width

    page.reload()
    recent = page.get_by_role("tabpanel", name="Recent")
    entry = recent.get_by_role("button", name="Nonconsecutive Subset Sums Modulo 3 v1", exact=True)
    metadata = entry.locator("xpath=../..").locator(".recent-meta-row > small > span")
    expect(metadata).to_contain_text(" · Running · ", timeout=10000)
    running.clear()
    expect(metadata).to_have_text(initial, timeout=10000)
    assert not errors, errors
    browser.close()
    print("PASS T92 real Chrome: idle, active, live polling, reload, clear, 1280/390/320px")
