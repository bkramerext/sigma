"""Real Chrome: Home Recent reflects persisted session activity without reload."""

import fcntl
import json
import os
from pathlib import Path
from uuid import uuid4

from playwright.sync_api import expect, sync_playwright

UI_ORIGIN = os.environ.get("SIGMA_HOME_RUNNING_UI_ORIGIN", "http://127.0.0.1:5173").rstrip("/")
API_ORIGIN = os.environ.get("SIGMA_HOME_RUNNING_API_ORIGIN", "http://127.0.0.1:8001").rstrip("/")

with sync_playwright() as playwright:
    browser = playwright.chromium.launch(
        executable_path=os.environ.get(
            "SIGMA_BROWSER_EXECUTABLE",
            "/Applications/Google Chrome.app/Contents/MacOS/Google Chrome",
        ),
        headless=True,
    )
    page = browser.new_page(viewport={"width": 1280, "height": 720})

    response = page.request.post(
        f"{API_ORIGIN}/api/projects/samples/open",
        data={"sample_id": "nonconsecutive-subset-sums"},
    )
    assert response.status == 200, response.text()
    project = response.json()
    project_path = Path(project["path"])
    project_id = project["project"]["id"]

    def forward(route):
        route.fulfill(response=route.fetch(url=route.request.url.replace(UI_ORIGIN, API_ORIGIN)))

    page.route("**/api/**", forward)
    page.goto(UI_ORIGIN + "/")
    recent_tab = page.get_by_role("tab", name="Recent", exact=True)
    recent_tab.click()
    recent_panel = page.get_by_role("tabpanel", name="Recent")
    recent_panel.locator(".recent-type-group summary").click()
    project_button = recent_panel.locator(".recent-open").first
    expect(project_button).to_be_visible()
    metadata = project_button.locator("xpath=../..").locator(".recent-meta-row > small > span")
    expect(metadata).not_to_contain_text("Running")

    session_id = str(uuid4())
    session_file = project_path / "research-sessions" / f"{session_id}.json"
    session_file.parent.mkdir(exist_ok=True)
    session_file.write_text(
        json.dumps(
            {
                "id": session_id,
                "project_id": project_id,
                "project_path": str(project_path.resolve()),
                "status": "running",
            }
        )
    )
    lock_path = session_file.with_name(f"{session_id}.worker.lock")
    with lock_path.open("a") as worker_lock:
        fcntl.flock(worker_lock.fileno(), fcntl.LOCK_EX)
        expect(metadata).to_contain_text(" · Running", timeout=10_000)
        assert recent_panel.locator(".home-runnable-state").count() == 0

        session_file.write_text(session_file.read_text().replace('"running"', '"stopped"'))
        expect(metadata).not_to_contain_text("Running", timeout=10_000)
        fcntl.flock(worker_lock.fileno(), fcntl.LOCK_UN)
    assert not page.locator("[role=alert]").count()
    print(
        "PASS real Chrome Home Recent updates inline Running status as the persisted session starts and stops"
    )
    browser.close()
