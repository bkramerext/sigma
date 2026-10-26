"""Real Chromium paper preflight, conflict and retry with an isolated fake provider."""

import hashlib
import json
import os
from pathlib import Path
from urllib.parse import quote

from playwright.sync_api import expect, sync_playwright

info = json.loads(Path(os.environ["SIGMA_T202_INFO"]).read_text())
path = Path(info["path"])
session = path / "research-sessions" / (info["session"] + ".json")
call_log = Path(info["calls"])
initial = session.read_bytes()
change_on_preflight = False
observed_change = False


def paper_files():
    directory = path / "papers"
    return {
        item.name: hashlib.sha256(item.read_bytes()).hexdigest()
        for item in directory.glob("*")
        if item.is_file()
    }


with sync_playwright() as playwright:
    browser = playwright.chromium.launch(
        executable_path=os.environ["SIGMA_BROWSER_EXECUTABLE"], headless=True
    )
    page = browser.new_page(viewport={"width": 1440, "height": 900})
    errors = []
    page.on("pageerror", lambda error: errors.append(str(error)))

    def intercept(route):
        global change_on_preflight, observed_change
        response = route.fetch()
        if change_on_preflight:
            saved = json.loads(session.read_text())
            saved["artifacts"][0]["claim_or_question"] += " Evidence changed after preflight."
            session.write_text(json.dumps(saved), encoding="utf-8")
            change_on_preflight = False
            observed_change = True
        route.fulfill(response=response)

    page.route("**/api/projects/papers/preflight?*", intercept)
    page.goto("http://127.0.0.1:5173/project?path=" + quote(str(path), safe=""))
    expect(page.get_by_role("heading", name="T202 paper fixture")).to_be_visible()
    page.get_by_role("button", name="LaTeX research paper").click()
    dialog = page.get_by_role("dialog", name="Academic paper using LaTeX")
    dialog.get_by_role("button", name="Generate paper", exact=True).click()
    expect(dialog.get_by_text("Paper saved in Saved versions.")).to_be_visible(timeout=30000)
    expect(dialog.locator(".saved-paper-card")).to_have_count(1)
    assert call_log.read_text().splitlines() == ["sigma_research_paper"]
    assert session.read_bytes() == initial
    baseline = paper_files()
    assert len(baseline) == 2, baseline

    change_on_preflight = True
    dialog.get_by_role("button", name="Generate new version").click()
    alert = dialog.get_by_role("alert")
    expect(alert).to_contain_text("Research changed after paper preflight")
    expect(alert).to_contain_text("No provider request was made for this attempt")
    expect(alert).to_contain_text("select Generate again to retry")
    assert observed_change and call_log.read_text().splitlines() == ["sigma_research_paper"]
    assert paper_files() == baseline
    assert b"Evidence changed after preflight." in session.read_bytes()
    expect(dialog.locator(".saved-paper-card")).to_have_count(1)

    dialog.get_by_role("button", name="Generate new version").click()
    expect(dialog.get_by_text("Paper saved in Saved versions.")).to_be_visible(timeout=30000)
    expect(dialog.locator(".saved-paper-card")).to_have_count(2)
    assert call_log.read_text().splitlines() == ["sigma_research_paper", "sigma_research_paper"]
    assert all(paper_files()[name] == digest for name, digest in baseline.items())
    assert b"Evidence changed after preflight." in session.read_bytes()
    assert not errors, errors
    page.screenshot(path="/tmp/sigma-t202-paper.png", full_page=True)
    browser.close()
print(
    "PASS T202 Chromium: stable fake paper, genuine preflight conflict with zero calls, preserved versions and evidence, successful retry"
)
