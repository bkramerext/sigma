"""T201 Chromium acceptance: bounded history permits repeatable research."""

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
    expect(page.locator(".session-start-limits")).to_have_text("1 round · 2 total turns")
    page.set_viewport_size({"width": 390, "height": 844})
    for button in (
        page.get_by_role("button", name="Start Session #2"),
        page.locator('button[title="Cancel starting a research session"]'),
    ):
        box = button.bounding_box()
        assert box is not None, "Research start action must be visible"
        assert box["x"] >= 0 and box["x"] + box["width"] <= 390, (
            f"Research start action overflows narrow viewport: {box}"
        )
    page.set_viewport_size({"width": 1440, "height": 900})
    page.locator('button[title="Start Session #2"]').click()
    row = page.locator(".session-row").filter(has_text="Session #2")
    expect(row).to_be_visible(timeout=15000)
    expect(row.locator(".session-status")).to_have_text(
        re.compile("completed|ended"), timeout=30000
    )
    deadline = time.monotonic() + 10
    while time.monotonic() < deadline and (
        not calls.exists() or len(calls.read_text().splitlines()) < 2
    ):
        time.sleep(0.1)
    assert calls.read_text().splitlines() == ["research_investigator", "research_skeptic"]
    assert read_file(path, saved_member) == before

    new_files = [
        name
        for name in read_bundle(path)["files"]
        if name.startswith("research-sessions/")
        and name.removeprefix("research-sessions/") not in {"limits.json", "sequence.json"}
        and name not in session_files
    ]
    assert len(new_files) == 1
    first = json.loads(read_file(path, new_files[0]))
    assert first["session_number"] == 2
    assert first["strategy_id"] == info["strategy"]
    assert first["calls_used"] == 2 and first["artifacts"]
    assert first["prior_session_obligations_omitted"] >= 1
    assert first["prior_session_obligation_omitted_ids_by_strategy"][info["strategy"]]
    manifest = first["steps"][0]["context_manifest"]
    assert manifest["omitted_prior_session_obligations"]["count"] >= 1
    assert info["omitted"] in manifest["omitted_prior_session_obligations"]["obligation_ids"]
    assert info["omitted_text"] not in str(manifest)

    # The same eligible strategy remains usable, with its durable history intact.
    page.get_by_role("button", name="Start a new research session").click()
    page.locator('button[title="Start Session #3"]').click()
    second_row = page.locator(".session-row").filter(has_text="Session #3")
    expect(second_row).to_be_visible(timeout=15000)
    expect(second_row.locator(".session-status")).to_have_text(
        re.compile("completed|ended"), timeout=30000
    )
    assert calls.read_text().splitlines() == [
        "research_investigator",
        "research_skeptic",
        "research_investigator",
        "research_skeptic",
    ]
    assert read_file(path, saved_member) == before
    assert not errors, errors
    page.screenshot(path="/tmp/sigma-t201-recovery.png", full_page=True)
    browser.close()

print(
    "PASS T201 Chromium: repeatable bounded research, provenance, narrow start controls and immutable history"
)
