"""Real Chrome checks for saved session Conclusions at desktop and phone widths."""

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


with tempfile.TemporaryDirectory(prefix="sigma-t47-browser-") as temporary:
    root = Path(temporary)
    project_path = root / "conclusions.sigma"
    archived = json.loads(ARCHIVE.read_text(encoding="utf-8"))
    project = archived["project"]
    session = archived["research_sessions"][0]
    sessions_path = project_path / "research-sessions"
    sessions_path.mkdir(parents=True)
    (project_path / "project.json").write_text(json.dumps(project), encoding="utf-8")
    session["project_path"] = str(project_path.resolve())
    session["outcome"]["conclusion"] = (
        "### Complete reviewed candidate answer\n\n"
        "Conditional on general position, the arrangement reaches the triangular bound for every n.\n\n"
        "### Verification and scope\n\nSIGMA has not independently verified the result."
    )
    session["outcome"]["solution_review"] = {
        "status": "achieved",
        "claim": "Conditional on general position, R(n) = 1 + n(n+1)/2.",
        "claim_scope": "conditional",
        "argument_summary": "The insertion bound and attaining construction match under the premise.",
        "assumptions": ["The lines are in general position."],
        "proof_obligations": [],
        "open_obligations": [],
        "argument_steps": [
            {
                "number": 1,
                "title": "Bound the pieces made by the new line",
                "argument": "At most n−1 crossings divide the new line into at most n pieces.",
                "epistemic_status": "deduction",
                "basis_artifact_ids": [],
                "research_artifact_id": session["artifacts"][0]["id"],
                "review": {
                    "disposition": "accepted",
                    "rationale": "The intersection bound yields at most n pieces.",
                    "objection": "",
                    "basis_artifact_ids": [],
                },
            }
        ],
        "strategy_findings": [],
        "skeptic_response": "The local insertion inference is sound under the stated premise.",
        "skeptic_objections": [],
        "unresolved_objections": [],
        "resolved_objections": [],
        "basis_artifact_ids": [],
    }
    session["artifacts"][0]["reasoning_steps"] = session["outcome"]["solution_review"][
        "argument_steps"
    ]
    session["artifacts"][0]["objective_review"] = {
        key: value
        for key, value in session["outcome"]["solution_review"].items()
        if key
        in {
            "status",
            "claim",
            "claim_scope",
            "argument_summary",
            "assumptions",
            "proof_obligations",
            "open_obligations",
            "unresolved_objections",
            "resolved_objections",
            "basis_artifact_ids",
            "argument_steps",
        }
    }
    session["outcome_conclusion_version"] = 1
    (sessions_path / f"{session['id']}.json").write_text(
        json.dumps(session, ensure_ascii=False), encoding="utf-8"
    )
    sessions = [session]

    api_port, ui_port = free_port(), free_port()
    while ui_port == api_port:
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
            expect(page.locator(".sessions-pane-heading .section-count")).to_contain_text(
                "1 session", timeout=15000
            )
            for session in sessions:
                row = page.locator(f'li[data-session-id="{session["id"]}"]')
                expect(row).to_be_visible(timeout=15000)
                disclosure = row.locator("button.session-row-disclosure")
                if disclosure.get_attribute("aria-expanded") != "true":
                    disclosure.click()
                outcome = row.get_by_role("region", name="Research outcome")
                conclusion = outcome.locator("details.outcome-conclusion")
                expect(conclusion).to_be_visible()
                assert conclusion.get_attribute("open") is not None
                assert conclusion.locator("summary").inner_text().strip() == "Conclusion"
                assert conclusion.evaluate(
                    "element => element.previousElementSibling.classList.contains('outcome-heading')"
                )
                expect(conclusion).to_contain_text(session["outcome"]["conclusion"].splitlines()[2])
                toggle = outcome.get_by_role("button", name="Render Conclusion as Markdown")
                toggle.click()
                expect(
                    outcome.get_by_role("button", name="Show Conclusion Markdown source")
                ).to_have_attribute("aria-pressed", "true")
                expect(conclusion.locator(".outcome-markdown h3").first).to_be_visible()
                toggle = outcome.get_by_role("button", name="Show Conclusion Markdown source")
                toggle.click()
                expect(conclusion.locator(".outcome-conclusion-source")).to_be_visible()
                outcome.get_by_text("Citations, Evidence & Obligations", exact=True).click()
                expect(outcome.locator(".outcome-evidence-subsection")).to_be_visible()
                expect(outcome).to_contain_text("Bound the pieces made by the new line")
                expect(outcome).to_contain_text("The intersection bound yields at most n pieces.")

            page.reload()
            first_row = page.locator(f'li[data-session-id="{sessions[0]["id"]}"]')
            if (
                first_row.locator("button.session-row-disclosure").get_attribute("aria-expanded")
                != "true"
            ):
                first_row.locator("button.session-row-disclosure").click()
            expect(first_row.locator("details.outcome-conclusion")).to_have_attribute("open", "")
            expect(first_row.locator("details.outcome-conclusion")).to_contain_text(
                "triangular bound"
            )

            page.set_viewport_size({"width": 375, "height": 812})
            for session in sessions:
                row = page.locator(f'li[data-session-id="{session["id"]}"]')
                if (
                    row.locator("button.session-row-disclosure").get_attribute("aria-expanded")
                    != "true"
                ):
                    row.locator("button.session-row-disclosure").click()
                conclusion = row.locator("details.outcome-conclusion")
                expect(conclusion).to_be_visible()
                assert conclusion.get_attribute("open") is not None
            overflow = page.evaluate(
                "({width: document.documentElement.clientWidth, scroll: document.documentElement.scrollWidth})"
            )
            assert overflow["scroll"] <= overflow["width"], overflow
            assert not starts, "Fixtures must not start provider sessions"
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

print("T47 conclusion real Chrome checks passed at 1440px and 375px; no provider calls made.")
