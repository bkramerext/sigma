"""T201 Chromium acceptance with isolated evidence and a fake provider."""

import json
import os
import re
import time
from pathlib import Path
from urllib.parse import quote

from playwright.sync_api import expect, sync_playwright

from sigma.project_bundle import read_bundle, read_file

info = json.loads(Path(os.environ["SIGMA_T201_INFO"]).read_text())
path = Path(info["path"])
base_url = os.environ.get("SIGMA_T201_BASE_URL", "http://127.0.0.1:5173")
saved_member = f"research-sessions/{info['session']}.json"
calls = Path(info["calls"])
before = read_file(path, saved_member)
session_files = {
    name
    for name in read_bundle(path)["files"]
    if name.startswith("research-sessions/")
    and name.removeprefix("research-sessions/") not in {"limits.json", "sequence.json"}
}
with sync_playwright() as playwright:
    browser = playwright.chromium.launch(
        executable_path=os.environ["SIGMA_BROWSER_EXECUTABLE"], headless=True
    )
    page = browser.new_page(viewport={"width": 1440, "height": 900})
    errors = []
    page.on("pageerror", lambda error: errors.append(str(error)))
    page.goto(base_url + "/project?path=" + quote(str(path), safe=""))
    expect(page.get_by_role("heading", name="T201 overflow fixture")).to_be_visible()
    page.get_by_role("button", name="Start a new research session").click()
    page.locator('button[title="Confirm start new Session 2"]').click()
    alert = page.locator(".sessions-pane [role=alert]")
    # The user-facing overflow error intentionally omits internal evidence hashes
    # and individual obligation text. Verify actionable guidance instead; the
    # saved artifact and absence of provider calls are asserted below.
    expect(alert).to_contain_text(
        "unresolved prior-session obligations exceed the safe context bound"
    )
    expect(alert).to_contain_text("Saved research is unchanged")
    expect(alert).to_contain_text(
        "start a new, narrower strategy informed by its saved findings"
    )
    assert info["omitted"] not in alert.inner_text()
    assert info["omitted_text"] not in alert.inner_text()
    expect(page.get_by_role("button", name="Start a new research session")).to_be_visible()
    assert read_file(path, saved_member) == before
    assert not calls.exists(), "blocked start must make no provider call"
    assert "research-sessions/sequence.json" not in read_bundle(path)["files"], (
        "blocked start reserved a session number"
    )
    assert {
        name
        for name in read_bundle(path)["files"]
        if name.startswith("research-sessions/")
        and name.removeprefix("research-sessions/") not in {"limits.json", "sequence.json"}
    } == session_files
    page.get_by_role("button", name="New", exact=True).click()
    form = page.locator(".strategy-form")
    expect(form).to_be_visible()
    form.get_by_label("Title").fill("Narrow follow-up")
    follow_up = form.get_by_label("Hypothesis / approach")
    follow_up.fill(f"Investigate the saved finding: {info['omitted_text']}")
    assert info["omitted_text"] in follow_up.input_value()
    form.get_by_role("button", name="Save", exact=True).click()
    expect(form).to_have_count(0)
    original = page.locator(f'li[data-strategy-id="{info["strategy"]}"]')
    original.get_by_role("button", name="Disable", exact=True).click()
    expect(original.get_by_role("button", name="Enable", exact=True)).to_be_visible()
    page.get_by_role("button", name="Start a new research session").click()
    page.locator('button[title="Confirm start new Session 2"]').click()
    child_row = page.locator(".session-row").filter(has_text="Session #2")
    expect(child_row).to_be_visible(timeout=15000)
    expect(child_row.locator(".session-status")).to_have_text(
        re.compile("completed|ended"), timeout=30000
    )
    deadline = time.monotonic() + 10
    while time.monotonic() < deadline and (
        not calls.exists() or len(calls.read_text().splitlines()) < 2
    ):
        time.sleep(0.1)
    assert calls.read_text().splitlines() == ["research_investigator", "research_skeptic"]
    child_files = [
        name
        for name in read_bundle(path)["files"]
        if name.startswith("research-sessions/")
        and name.removeprefix("research-sessions/") not in {"limits.json", "sequence.json"}
        and name not in session_files
    ]
    assert len(child_files) == 1
    child = json.loads(read_file(path, child_files[0]))
    assert child["session_number"] == 2 and child["calls_used"] == 2 and child["artifacts"]
    assert child["strategy_id"] != info["strategy"]
    assert read_file(path, saved_member) == before
    assert not errors, errors
    page.screenshot(path="/tmp/sigma-t201-recovery.png", full_page=True)
    browser.close()
print(
    "PASS local Chromium: overflow details, no session or calls, preserved evidence, fork and disable, fake-provider child progress"
)
