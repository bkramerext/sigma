"""Real Chrome acceptance for paused-session explanations and safe resume guidance."""

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
ARCHIVE = (
    REPO
    / "docs/evaluations/fixtures/t17-8-answer-free/live-session-91e96112-27ce-412e-841f-5cbf67cbba75.json"
)
CHROME = os.environ.get(
    "SIGMA_BROWSER_EXECUTABLE", "/Applications/Google Chrome.app/Contents/MacOS/Google Chrome"
)


def free_port() -> int:
    with socket.socket() as listener:
        listener.bind(("127.0.0.1", 0))
        return int(listener.getsockname()[1])


def wait_for(url: str, process: subprocess.Popen) -> None:
    import urllib.error
    import urllib.request

    deadline = time.monotonic() + 30
    while time.monotonic() < deadline:
        if process.poll() is not None:
            raise AssertionError(f"Isolated server exited with status {process.returncode}")
        try:
            with urllib.request.urlopen(url, timeout=1):
                return
        except (OSError, urllib.error.URLError):
            time.sleep(0.1)
    raise AssertionError(f"Isolated server did not become ready: {url}")


with tempfile.TemporaryDirectory(prefix="sigma-t95-browser-") as temporary:
    root = Path(temporary)
    project_path = root / "paused-project.sigma"
    sessions_path = project_path / "research-sessions"
    sessions_path.mkdir(parents=True)
    export = json.loads(ARCHIVE.read_text(encoding="utf-8"))
    project, session = export["project"], export["research_sessions"][0]
    session["status"] = "paused"
    session["message"] = (
        "Backend restarted before the session completed. In-flight provider calls are interrupted and will not be retried automatically."
    )
    session["current_action"] = "Paused after backend restart"
    if session.get("steps"):
        session["steps"][-1].update(
            {
                "status": "interrupted",
                "failure_kind": "interrupted",
                "interruption_reason": "backend_restart",
            }
        )
    (project_path / "project.json").write_text(json.dumps(project), encoding="utf-8")
    session["project_path"] = str(project_path.resolve())
    (sessions_path / f"{session['id']}.json").write_text(
        json.dumps(session, separators=(",", ":")), encoding="utf-8"
    )
    pause_cases = [
        (
            "Manual pause",
            "Paused by user. A dispatched provider request may still consume allowance.",
            "Paused",
        ),
        (
            "Context limit",
            "Research context exceeded the 256 KB UTF-8 byte limit; no provider call was made.",
            "Paused · context limit",
        ),
        ("Wall-clock limit", "Configured session duration reached.", "Paused · wall-clock limit"),
        (
            "Cost limit",
            "Configured cost limit reached; research remains paused.",
            "Paused · cost limit",
        ),
        (
            "Connection change",
            "AI account or billing identity changed; research remains paused.",
            "Paused",
        ),
        ("Project change", "Project or strategy changed; research remains paused.", "Paused"),
        ("Other guard", "A guarded session condition requires review.", "Paused"),
    ]
    for number, (label, message, action) in enumerate(pause_cases, start=2):
        variant = json.loads(json.dumps(session))
        variant_id = str(uuid4())
        variant.update(
            {
                "id": variant_id,
                "session_number": number,
                "strategy_title": label,
                "status": "paused",
                "message": message,
                "current_action": action,
                "steps": [],
                "strategy_runs": [],
            }
        )
        (sessions_path / f"{variant_id}.json").write_text(
            json.dumps(variant, separators=(",", ":")), encoding="utf-8"
        )

    api_port, ui_port = free_port(), free_port()
    while api_port == ui_port:
        ui_port = free_port()
    api_url, ui_url = f"http://127.0.0.1:{api_port}", f"http://127.0.0.1:{ui_port}"
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
                executable_path=CHROME, headless=True, args=["--disable-web-security"]
            )
            context = browser.new_context(viewport={"width": 1440, "height": 1000})
            page = context.new_page()
            page_errors: list[str] = []
            session_starts: list[str] = []
            page.on("pageerror", lambda error: page_errors.append(str(error)))
            page.on(
                "request",
                lambda request: (
                    session_starts.append(request.url)
                    if request.url.endswith("/api/projects/research-sessions/start")
                    else None
                ),
            )
            target = f"{ui_url}/project?path={quote(str(project_path), safe='')}"
            page.goto(target)
            row = page.locator(f'li[data-session-id="{session["id"]}"]')
            expect(row.locator(".session-status")).to_have_text("stopped")
            clarity = row.locator(".stopped-session-guidance")
            expect(clarity).to_contain_text("session was interrupted when its backend work stopped")
            expect(clarity).to_contain_text("Saved research is preserved.")
            expect(clarity).to_contain_text(
                "previously dispatched provider request may already have used allowance"
            )
            expect(clarity).to_contain_text("Resume when you are ready")
            expect(row.locator('button[title="Resume Session 1"]')).to_be_visible()
            expected_guidance = {
                2: "stopped by user",
                3: "required context exceeded the available context limit",
                4: "configured elapsed-time limit",
                5: "configured cost or call budget limit",
                6: "selected model or AI connection changed",
                7: "project or one of its strategies changed",
                8: "Review the stop details above",
            }
            for number, guidance in expected_guidance.items():
                variant = page.locator(".session-row").filter(has_text=f"Session #{number}")
                expect(variant.locator(".stopped-session-guidance")).to_contain_text(guidance)
            for width in (1440, 390):
                page.set_viewport_size({"width": width, "height": 844})
                assert page.evaluate("document.documentElement.scrollWidth <= window.innerWidth")
            page.screenshot(path="/tmp/sigma-t95-paused-desktop.png", full_page=True)
            context.close()

            reopened = browser.new_context(viewport={"width": 390, "height": 844})
            page = reopened.new_page()
            page.route(
                "**/api/projects/research-sessions/*/control",
                lambda route: route.fulfill(
                    status=409,
                    content_type="application/json",
                    body=json.dumps({"error": "AI connection changed; review it before resuming."}),
                ),
            )
            page.goto(target)
            row = page.locator(f'li[data-session-id="{session["id"]}"]')
            expect(row.locator(".session-status")).to_have_text("stopped")
            expect(row.locator(".stopped-session-guidance")).to_contain_text(
                "session was interrupted when its backend work stopped"
            )
            page.locator('button[title="Resume Session 1"]').click()
            expect(page.get_by_role("alert")).to_be_visible(timeout=10000)
            expect(page.get_by_role("alert")).to_contain_text("AI connection changed")
            expect(row.locator(".session-status")).to_have_text("stopped")
            assert not session_starts, "Opening or viewing paused work must not start a session"
            assert not page_errors, page_errors
            page.screenshot(path="/tmp/sigma-t95-paused-mobile.png", full_page=True)
            browser.close()
    finally:
        ui.terminate()
        api.terminate()
        ui.wait(timeout=10)
        api.wait(timeout=10)

print(
    "T95 real Chrome stopped-session guidance, reload/reopen, guarded resume, and responsive checks passed"
)
