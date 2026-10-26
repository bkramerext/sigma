"""T201 Chromium acceptance with an isolated persisted fixture and no inference."""

import json
import os
from pathlib import Path
from urllib.parse import quote

from playwright.sync_api import expect, sync_playwright

info = json.loads(Path(os.environ["SIGMA_T201_INFO"]).read_text())
path = Path(info["path"])
saved = path / "research-sessions" / (info["session"] + ".json")
before = saved.read_bytes()
with sync_playwright() as playwright:
    browser = playwright.chromium.launch(
        executable_path=os.environ["SIGMA_BROWSER_EXECUTABLE"], headless=True
    )
    page = browser.new_page(viewport={"width": 1440, "height": 900})
    errors = []
    page.on("pageerror", lambda error: errors.append(str(error)))
    page.goto("http://127.0.0.1:5173/project?path=" + quote(str(path), safe=""))
    expect(page.get_by_role("heading", name="T201 overflow fixture")).to_be_visible()
    page.get_by_role("button", name="Start a new research session").click()
    page.locator('button[title="Confirm start new Session 2"]').click()
    alert = page.locator(".sessions-pane [role=alert]")
    expect(alert).to_contain_text(info["omitted"])
    expect(alert).to_contain_text("Resolve fixture boundary obligation")
    expect(alert).to_contain_text("Fork strategy from findings")
    expect(page.get_by_role("button", name="Start a new research session")).to_be_visible()
    assert saved.read_bytes() == before
    row = page.locator(f'li[data-session-id="{info["session"]}"]')
    if row.locator(".session-row-content").is_hidden():
        row.locator(".session-row-disclosure").click()
    row.get_by_role("button", name="Fork strategy from findings").click()
    form = page.locator(".strategy-form")
    expect(form).to_be_visible()
    assert (
        "Resolve fixture boundary obligation"
        in form.get_by_label("Hypothesis / approach").input_value()
    )
    form.get_by_role("button", name="Save", exact=True).click()
    expect(form).to_have_count(0)
    original = page.locator(f'li[data-strategy-id="{info["strategy"]}"]')
    original.get_by_role("button", name="Disable", exact=True).click()
    expect(original.get_by_role("button", name="Enable", exact=True)).to_be_visible()
    assert saved.read_bytes() == before
    assert not errors, errors
    page.screenshot(path="/tmp/sigma-t201-recovery.png", full_page=True)
    browser.close()
print("PASS local Chromium: overflow details, no new session, evidence preserved, fork and disable")
