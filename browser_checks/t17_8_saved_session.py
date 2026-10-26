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
    session["problem"] = "Determine the maximum number of regions cut out by n straight lines."
    session["strategy_text"] = (
        "Insert one line at a time, prove an upper bound for each increment, and give an arrangement attaining every increment."
    )
    argument = [
        (
            "Assumptions",
            "Work in the Euclidean plane with n distinct lines. For attainment, choose a general-position arrangement: no parallel pairs and no triple intersections.",
            "assumption",
        ),
        (
            "At most n regions are added",
            "The nth line has at most n−1 intersection points with earlier lines, hence at most n pieces. Each piece can split at most one old region, so the increment is at most n.",
            "deduction",
        ),
        (
            "Why crossings split distinct regions",
            "Every old region is an intersection of open half-planes, hence convex. Two separated pieces cannot be in one old region, because the segment between them would cross an earlier line. An open region met by the new line has points on both sides and is split into two.",
            "deduction",
        ),
        (
            "Attainment",
            "For lines L_k: y=kx+k², intersections with earlier L_i have x=−(i+k), distinct for fixed k. No three lines meet at one point, so the nth inserted line has n−1 crossings and creates n regions.",
            "deduction",
        ),
        (
            "Recurrence and base case",
            "The bound and construction give R(n)=R(n−1)+n for n≥1. The empty arrangement has R(0)=1.",
            "deduction",
        ),
        (
            "Closed form",
            "Induction yields R(n)=1+Σ(k=1…n)k=1+n(n+1)/2: the base n=0 holds, and adding n gives the formula at n.",
            "deduction",
        ),
    ]
    latest = session["artifacts"][-1]
    review = latest.setdefault("objective_review", {})
    review["argument_steps"] = [
        {
            "number": index,
            "title": title,
            "argument": text,
            "epistemic_status": status,
            "basis_artifact_ids": [],
            "research_artifact_id": latest["id"],
            "review": {
                "disposition": "accepted",
                "rationale": "The assumptions and cited geometric argument support this step; no formal checker ran.",
                "objection": "",
                "basis_artifact_ids": [],
            },
        }
        for index, (title, text, status) in enumerate(argument, 1)
    ]
    session["outcome"]["solution_review"] = review
    session["outcome"]["summary"] = (
        "R(n)=1+n(n+1)/2 is supported by the saved insertion argument and an attaining family; candidate remains unverified."
    )
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
            expect(outcome).to_contain_text("Attainment")
            expect(outcome).to_contain_text("No three lines meet")
            expect(outcome).to_contain_text("Closed form")
            expect(outcome).to_contain_text("Sources:")
            expect(outcome).to_contain_text("Convincing but unverified")
            markdown_toggle = outcome.get_by_role("button", name="Render outcome as Markdown")
            expect(markdown_toggle).to_be_visible()
            expect(markdown_toggle).to_have_attribute("aria-pressed", "false")
            expect(markdown_toggle).to_have_attribute("title", "Render outcome as Markdown")
            icon = markdown_toggle.locator("svg.markdown-logo")
            expect(icon).to_be_visible()
            assert icon.locator("path").count() == 2
            icon_geometry = icon.evaluate(
                "e => [...e.querySelectorAll('path')].map(p => { const b=p.getBBox(), s=getComputedStyle(p); return [b.width, b.height, s.fill]; })"
            )
            assert all(
                width > 0 and height > 0 and fill != "none" for width, height, fill in icon_geometry
            ), icon_geometry
            markdown_toggle.hover()
            assert (
                markdown_toggle.locator("svg.markdown-logo path").first.evaluate(
                    "e => getComputedStyle(e).fill"
                )
                == "rgb(241, 197, 141)"
            )
            markdown_toggle.focus()
            page.keyboard.press("Tab")
            page.keyboard.press("Shift+Tab")
            expect(markdown_toggle).to_be_focused()
            assert markdown_toggle.evaluate("e => getComputedStyle(e).outlineStyle") == "solid"
            markdown_toggle.click()
            source_toggle = outcome.get_by_role("button", name="Show plain outcome text")
            expect(source_toggle).to_have_attribute("aria-pressed", "true")
            expect(source_toggle).to_have_attribute("title", "Show plain outcome text")
            assert (
                source_toggle.locator("svg.markdown-logo path").first.evaluate(
                    "e => getComputedStyle(e).fill"
                )
                == "rgb(241, 197, 141)"
            )
            source_toggle.click()
            expect(
                outcome.get_by_role("button", name="Render outcome as Markdown")
            ).to_have_attribute("aria-pressed", "false")
            for width, height in ((1440, 1000), (390, 844)):
                page.set_viewport_size({"width": width, "height": height})
                expect(markdown_toggle).to_be_visible()
                bounds = markdown_toggle.bounding_box()
                assert bounds and bounds["x"] >= 0 and bounds["x"] + bounds["width"] <= width
                assert page.evaluate("document.documentElement.scrollWidth <= window.innerWidth")
                page.screenshot(
                    path=f"/tmp/sigma-t17-8-markdown-toggle-{width}.png", full_page=True
                )
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
