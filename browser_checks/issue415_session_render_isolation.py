"""Real-Chrome regression for large saved session lists and malformed history."""

import json
import os
import socket
import subprocess
import tempfile
import time
from pathlib import Path
from urllib.parse import quote
from uuid import uuid4

from playwright.sync_api import expect, sync_playwright

REPO = Path(__file__).resolve().parents[1]
ARCHIVE = REPO / "docs/evaluations/fixtures/t17-8-answer-free/live-session-91e96112-27ce-412e-841f-5cbf67cbba75.json"
CHROME = os.environ.get("SIGMA_BROWSER_EXECUTABLE", "/Applications/Google Chrome.app/Contents/MacOS/Google Chrome")


def free_port():
    with socket.socket() as listener:
        listener.bind(("127.0.0.1", 0))
        return listener.getsockname()[1]


def wait_for(url, process):
    import urllib.error
    import urllib.request

    for _ in range(300):
        if process.poll() is not None:
            raise AssertionError(f"Isolated server exited: {process.returncode}")
        try:
            with urllib.request.urlopen(url, timeout=1):
                return
        except (OSError, urllib.error.URLError):
            time.sleep(0.1)
    raise AssertionError(f"Server did not become ready: {url}")


with tempfile.TemporaryDirectory(prefix="sigma-issue415-chrome-") as temporary:
    root = Path(temporary)
    project_path = root / "ai-agent-reliability-test.sigma"
    sessions_path = project_path / "research-sessions"
    sessions_path.mkdir(parents=True)
    archived = json.loads(ARCHIVE.read_text(encoding="utf-8"))
    project = archived["project"]
    project["title"] = "Issue 415 isolated browser fixture"
    (project_path / "project.json").write_text(json.dumps(project), encoding="utf-8")
    source_session = archived["research_sessions"][0]
    session_ids = []
    for number in range(1, 7):
        session = json.loads(json.dumps(source_session))
        session["id"] = str(uuid4())
        session["session_number"] = number
        session["project_path"] = str(project_path.resolve())
        session["project_id"] = project.get("id")
        session["status"] = "completed"
        if number == 1:
            # This is read by stopped-session guidance before session details
            # render; shallow top-level normalization leaves it unchecked.
            session["status"] = "paused"
            if session.get("artifacts"):
                session["artifacts"][0]["investigator_output"] = None
        session_ids.append(session["id"])
        (sessions_path / f"{session['id']}.json").write_text(json.dumps(session), encoding="utf-8")

    api_port, ui_port = free_port(), free_port()
    while ui_port == api_port:
        ui_port = free_port()
    api_url, ui_url = f"http://127.0.0.1:{api_port}", f"http://127.0.0.1:{ui_port}"
    env = os.environ.copy()
    env["SIGMA_PROJECTS_ROOT"] = str(root)
    api = subprocess.Popen(["uv", "run", "--project", str(REPO), "python", "-m", "uvicorn", "sigma.server:create_app", "--factory", "--host", "127.0.0.1", "--port", str(api_port)], cwd=REPO, env=env, stdout=subprocess.DEVNULL, stderr=subprocess.DEVNULL)
    env["SIGMA_API_TARGET"] = api_url
    ui = subprocess.Popen(["npm", "--prefix", str(REPO / "frontend"), "run", "dev", "--", "--host", "127.0.0.1", "--port", str(ui_port)], cwd=REPO, env=env, stdout=subprocess.DEVNULL, stderr=subprocess.DEVNULL)
    try:
        wait_for(api_url + "/openapi.json", api)
        wait_for(ui_url, ui)
        with sync_playwright() as playwright:
            browser = playwright.chromium.launch(executable_path=CHROME, headless=True, args=["--disable-web-security"])
            page = browser.new_page(viewport={"width": 1440, "height": 1000})
            page_errors, console_errors, network = [], [], []
            page.on("pageerror", lambda error: page_errors.append(str(error)))
            page.on("console", lambda message: console_errors.append(message.text) if message.type == "error" else None)
            page.on("response", lambda response: network.append((response.status, response.url)) if "/api/projects/" in response.url else None)
            page.on("requestfailed", lambda request: network.append((0, f"FAILED {request.url}: {request.failure}")))
            def keep_one_session_active(route):
                response = route.fetch()
                payload = response.json()
                running = next(item for item in payload["sessions"] if item["id"] == session_ids[1])
                running["status"] = "running"
                running["current_action"] = "Investigating"
                route.fulfill(response=response, json=payload)
            page.route("**/api/projects/research-sessions?*", keep_one_session_active)
            page.goto(f"{ui_url}/project?path={quote(str(project_path), safe='')}")
            rows = page.locator("ol.session-list > li.session-row")
            try:
                expect(rows).to_have_count(6, timeout=20000)
            except AssertionError:
                print(json.dumps({"url": page.url, "body": page.locator("body").inner_text()[:2000], "page_errors": page_errors, "console_errors": console_errors[:20], "api_responses": network}, indent=2))
                raise
            expect(page.get_by_role("alert").filter(has_text="Session #1 stopped notice could not be displayed")).to_be_visible()
            expect(page.locator(f'li[data-session-id="{session_ids[2]}"] .session-status')).to_be_visible()
            expect(page.locator(f'li[data-session-id="{session_ids[1]}"] .session-status')).to_contain_text("running")
            expect(page.locator(".sessions-pane-heading .section-count")).to_contain_text("6 sessions")
            page.reload(wait_until="networkidle")
            expect(rows).to_have_count(6, timeout=20000)
            expect(page.get_by_role("alert").filter(has_text="Session #1 stopped notice could not be displayed")).to_be_visible()
            expect(page.locator(f'li[data-session-id="{session_ids[1]}"] .session-status')).to_contain_text("running")
            expect(page.locator(".session-list")).to_be_visible()
            page.get_by_role("button", name="Export project").click()
            expect(page.get_by_role("dialog", name="Export Project")).to_be_visible()
            with page.expect_download(timeout=15000) as download:
                page.get_by_role("button", name="Download").click()
            assert download.value.suggested_filename.endswith(".json")
            exported = json.loads(Path(download.value.path()).read_text(encoding="utf-8"))
            exported_sessions = [name for name in exported["files"] if name.startswith("research-sessions/") and name.endswith(".json")]
            assert len(exported_sessions) == 6, exported_sessions
            assert not page_errors, f"Uncaught browser exceptions: {page_errors}"
            assert any("research-sessions?" in url and status == 200 for status, url in network), network
            assert any("export" in url and status == 200 for status, url in network), network
            assert not any("research-sessions/" in url and "control" in url for _, url in network), network
            component_stacks = [message for message in console_errors if "Unable to render saved research session" in message or "SessionRenderBoundary" in message]
            print(json.dumps({"sessions_rendered": 6, "malformed_session_localized": True, "reload_preserved_sessions": True, "running_ui_state_survived_refresh": True, "exported_session_files": len(exported_sessions), "export_downloaded": download.value.suggested_filename, "uncaught_exceptions": page_errors, "react_diagnostics": component_stacks[:3], "api_responses": network}, indent=2))
            browser.close()
    finally:
        ui.terminate()
        api.terminate()
        ui.wait(timeout=10)
        api.wait(timeout=10)
