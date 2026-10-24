"""Real Chrome projection check for the archived answer-free T17.8 session."""

import json
import os
import socket
import subprocess
import tempfile
import time
from pathlib import Path
from urllib.parse import quote

from playwright.sync_api import expect, sync_playwright

REPO = Path(__file__).resolve().parents[1]
ARCHIVE = (
    REPO / "docs/evaluations/fixtures/t17-8-answer-free/"
    "live-session-91e96112-27ce-412e-841f-5cbf67cbba75.json"
)
CHROME = os.environ.get(
    "SIGMA_BROWSER_EXECUTABLE",
    "/Applications/Google Chrome.app/Contents/MacOS/Google Chrome",
)


def free_port() -> int:
    with socket.socket() as listener:
        listener.bind(("127.0.0.1", 0))
        return int(listener.getsockname()[1])


def wait_for(url: str, process: subprocess.Popen, timeout: float = 30) -> None:
    import urllib.error
    import urllib.request

    deadline = time.monotonic() + timeout
    while time.monotonic() < deadline:
        if process.poll() is not None:
            raise AssertionError(f"Isolated server exited with status {process.returncode}")
        try:
            with urllib.request.urlopen(url, timeout=1):
                return
        except (OSError, urllib.error.URLError):
            time.sleep(0.1)
    raise AssertionError(f"Isolated server did not become ready: {url}")


with tempfile.TemporaryDirectory(prefix="sigma-t17-8-browser-") as temporary:
    root = Path(temporary)
    project_path = root / "maximum-regions.sigma"
    sessions_path = project_path / "research-sessions"
    sessions_path.mkdir(parents=True)

    archived_export = json.loads(ARCHIVE.read_text(encoding="utf-8"))
    project = archived_export["project"]
    session = archived_export["research_sessions"][0]
    (project_path / "project.json").write_text(
        json.dumps(project, ensure_ascii=False), encoding="utf-8"
    )
    session["project_path"] = str(project_path.resolve())
    (sessions_path / f"{session['id']}.json").write_text(
        json.dumps(session, ensure_ascii=False, separators=(",", ":")), encoding="utf-8"
    )

    api_port, ui_port = free_port(), free_port()
    while ui_port == api_port:
        ui_port = free_port()
    api_url = f"http://127.0.0.1:{api_port}"
    ui_url = f"http://127.0.0.1:{ui_port}"
    environment = os.environ.copy()
    environment["SIGMA_PROJECTS_ROOT"] = str(root)
    api = subprocess.Popen(
        [
            "uv",
            "run",
            "--project",
            str(REPO),
            "python",
            "-m",
            "uvicorn",
            "sigma.server:create_app",
            "--factory",
            "--host",
            "127.0.0.1",
            "--port",
            str(api_port),
        ],
        cwd=REPO,
        env=environment,
        stdout=subprocess.DEVNULL,
        stderr=subprocess.DEVNULL,
    )
    environment["SIGMA_API_TARGET"] = api_url
    ui = subprocess.Popen(
        [
            "npm",
            "--prefix",
            str(REPO / "frontend"),
            "run",
            "dev",
            "--",
            "--host",
            "127.0.0.1",
            "--port",
            str(ui_port),
        ],
        cwd=REPO,
        env=environment,
        stdout=subprocess.DEVNULL,
        stderr=subprocess.DEVNULL,
    )
    try:
        wait_for(api_url + "/openapi.json", api)
        wait_for(ui_url, ui)
        with sync_playwright() as playwright:
            browser = playwright.chromium.launch(
                executable_path=CHROME,
                headless=True,
                args=["--disable-web-security"],
            )
            page = browser.new_page(viewport={"width": 1440, "height": 1000})
            errors: list[str] = []
            starts: list[str] = []
            page.on("pageerror", lambda error: errors.append(str(error)))
            page.on(
                "request",
                lambda request: (
                    starts.append(request.url)
                    if request.url.endswith("/api/projects/research-sessions/start")
                    else None
                ),
            )
            page.goto(f"{ui_url}/project?path={quote(str(project_path), safe='')}")
            session_row = page.locator(f'li[data-session-id="{session["id"]}"]')
            expect(session_row).to_be_visible(timeout=15000)
            expect(session_row.locator(".session-status")).to_have_text("ended")
            expect(session_row.locator(".session-strategy-name")).to_contain_text(
                "solution candidate (unverified)"
            )
            disclosure = session_row.locator("button.session-row-disclosure")
            count = page.locator(".sessions-pane-heading .section-count")
            count_x_before = count.bounding_box()["x"]
            if disclosure.get_attribute("aria-expanded") != "true":
                disclosure.click()
            disclosure.click()
            expect(session_row.locator(".session-row-content")).to_be_hidden()
            assert abs(count.bounding_box()["x"] - count_x_before) <= 0.5
            disclosure.click()
            expect(session_row.locator(".session-row-content")).to_be_visible()
            outcome = session_row.get_by_role("region", name="Research outcome")
            expect(outcome).to_be_visible()
            review = session["outcome"]["solution_review"]
            expect(outcome).to_contain_text(review["claim"])
            expect(outcome).to_contain_text(review["argument_summary"])
            expect(outcome).to_contain_text("Convincing but unverified")
            outcome.get_by_text("Citations, Evidence & Obligations", exact=True).click()
            artifacts = session_row.get_by_role("region", name="Research artifacts")
            expect(artifacts).to_be_visible()
            expect(artifacts.locator("li")).to_have_count(len(session["artifacts"]))
            for artifact in session["artifacts"]:
                expect(artifacts).to_contain_text(artifact["claim_or_question"])
            page.locator('.project-pane-actions [aria-label="Export project"]').click()
            export_dialog = page.get_by_role("dialog", name="Export Project")
            expect(export_dialog).to_be_visible()
            expect(export_dialog.get_by_role("radio")).to_have_count(3)
            expect(export_dialog).not_to_contain_text("LaTeX report")
            export_dialog.get_by_role("button", name="Cancel").click()
            assert not starts, "The saved-session check must not start a research session"
            assert not errors, errors
            browser.close()
    finally:
        for process in (ui, api):
            process.terminate()
        for process in (ui, api):
            try:
                process.wait(timeout=5)
            except subprocess.TimeoutExpired:
                process.kill()
                process.wait(timeout=5)

print("T17.8 archived-session real Chrome projection passed; no provider calls made.")
