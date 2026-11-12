"""Real Chrome acceptance for the unauthenticated hosted sample workflow."""

from __future__ import annotations

import hashlib
import json
import os
import re
import shutil
import socket
import subprocess
import tempfile
import time
from pathlib import Path
from tempfile import TemporaryDirectory

import httpx
from playwright.sync_api import expect, sync_playwright

from sigma import paper_scores

ROOT = Path(__file__).resolve().parents[1]
CHROME = os.environ.get(
    "SIGMA_BROWSER_EXECUTABLE",
    "/Applications/Google Chrome.app/Contents/MacOS/Google Chrome",
)


def free_port() -> int:
    with socket.socket() as listener:
        listener.bind(("127.0.0.1", 0))
        return int(listener.getsockname()[1])


def wait_for(url: str, process: subprocess.Popen, log: Path) -> None:
    deadline = time.monotonic() + 30
    while time.monotonic() < deadline and process.poll() is None:
        try:
            if httpx.get(url, timeout=0.5).status_code < 500:
                return
        except httpx.HTTPError:
            time.sleep(0.1)
    raise RuntimeError(f"Guest browser fixture failed to start:\n{log.read_text(errors='replace')}")


def make_scored_sample_fixture(directory: Path) -> bytes:
    """Add an offline scored-paper sample without modifying the shipped catalog."""
    from uuid import uuid4

    shutil.copytree(ROOT / "samples", directory)
    sample = directory / "test-scored-warp-drive"
    shutil.copytree(ROOT / "samples" / "warp-drive-engineering", sample)
    project_path = sample / "project.json"
    project = json.loads(project_path.read_text(encoding="utf-8"))
    project["id"] = str(uuid4())
    project["title"] = "Warp Drive Design v9 (acceptance fixture)"
    # This is a modern sample with audited project.updated history. Keep the
    # final event in sync with the fixture's renamed title rather than
    # producing a corrupt sample that hides all public Samples from guests.
    last_event = project["events"][-1]
    assert last_event["kind"] == "project.updated"
    last_event["project_change"]["current"]["title"] = project["title"]
    project_path.write_text(json.dumps(project), encoding="utf-8")
    pdf = (ROOT / "tests/fixtures/sigma-valid-sample-paper.pdf").read_bytes()
    tex = (ROOT / "tests/fixtures/sigma-valid-sample-paper.tex").read_text(encoding="utf-8")
    sha = hashlib.sha256(pdf).hexdigest()
    judgment = paper_scores.PaperJudgment.model_validate(
        {
            key: {"earned": 75, "explanation": "Synthetic public PDF acceptance fixture."}
            for key in paper_scores.WEIGHTS
        }
    )
    paper_id = "f" * 32
    paper = sample / "sample-papers"
    paper.mkdir()
    record = {
        "paper_id": paper_id,
        "project_id": "$SIGMA_SAMPLE_PROJECT_ID",
        "draft": {"title": "Public Warp Drive PDF acceptance fixture"},
        "tex_source": tex,
        "pdf_sha256": sha,
        "pdf_size_bytes": len(pdf),
        "score": paper_scores._make_score(judgment, sha),
    }
    (paper / f"{paper_id}.json").write_text(json.dumps(record), encoding="utf-8")
    (paper / f"{paper_id}.pdf").write_bytes(pdf)
    return pdf


def main() -> None:
    api_port, ui_port = free_port(), free_port()
    while api_port == ui_port:
        ui_port = free_port()
    api_url = f"http://127.0.0.1:{api_port}"
    ui_url = f"http://127.0.0.1:{ui_port}"
    with TemporaryDirectory(prefix="sigma-guest-browser-") as temporary:
        root = Path(temporary)
        os.chmod(root, 0o700)
        public_pdf = make_scored_sample_fixture(root / "samples")
        env = os.environ.copy()
        env.update(
            {
                "SIGMA_GUEST_BROWSER_SAMPLE_ROOT": str(root / "samples"),
                "SIGMA_CLOUD_AUTH_ENABLED": "true",
                "GOOGLE_OIDC_CLIENT_ID": "fixture.apps.googleusercontent.com",
                "GOOGLE_OIDC_CLIENT_SECRET": "fixture-secret",
                "SIGMA_CLOUD_PUBLIC_ORIGIN": ui_url,
                "SIGMA_CLOUD_AUTH_HOME": str(root / "auth"),
                "SIGMA_CLOUD_WORKSPACES_ROOT": str(root / "workspaces"),
                "SIGMA_PROJECTS_ROOT": str(root / "saved-projects"),
                "SIGMA_STATE_DIR": str(root / "local-state"),
                "SIGMA_API_TARGET": api_url,
                "PYTHONPATH": os.pathsep.join(
                    (str(ROOT / "tests"), str(ROOT / "src"), os.environ.get("PYTHONPATH", ""))
                ),
            }
        )
        api_log, ui_log = root / "api.log", root / "ui.log"
        api_process = ui_process = None
        with api_log.open("w") as api_output, ui_log.open("w") as ui_output:
            try:
                api_process = subprocess.Popen(
                    [
                        str(ROOT / ".venv/bin/python"),
                        "-m",
                        "uvicorn",
                        "cloud_guest_browser_app:app",
                        "--host",
                        "127.0.0.1",
                        "--port",
                        str(api_port),
                        "--log-level",
                        "error",
                    ],
                    cwd=ROOT,
                    env=env,
                    stdout=api_output,
                    stderr=subprocess.STDOUT,
                )
                wait_for(api_url + "/api/ui-instance", api_process, api_log)
                ui_process = subprocess.Popen(
                    [
                        "npm",
                        "--prefix",
                        str(ROOT / "frontend"),
                        "run",
                        "dev",
                        "--",
                        "--host",
                        "127.0.0.1",
                        "--port",
                        str(ui_port),
                        "--strictPort",
                    ],
                    cwd=ROOT,
                    env=env,
                    stdout=ui_output,
                    stderr=subprocess.STDOUT,
                )
                wait_for(ui_url, ui_process, ui_log)
                exercise(ui_url, root, public_pdf)
            finally:
                for process in (ui_process, api_process):
                    if process is not None:
                        process.terminate()
                        process.wait(timeout=10)
        guest_dirs = list(Path(tempfile.gettempdir()).glob("sigma-guest-*"))
        assert (
            not list((root / "saved-projects").glob("*.sigma"))
            if (root / "saved-projects").exists()
            else True
        )
        print(
            f"PASS real Chrome guest sample workflow; transient workspaces observed: {len(guest_dirs)}"
        )


def exercise(ui_url: str, root: Path, public_pdf: bytes) -> None:
    with sync_playwright() as playwright:
        browser = playwright.chromium.launch(executable_path=CHROME, headless=True)
        page = browser.new_page(viewport={"width": 1280, "height": 850})
        failures: list[str] = []
        recent_responses: list[str] = []
        api_failures: list[str] = []
        protected_guest_requests: list[str] = []
        paper_requests: list[str] = []
        mutation_requests: list[str] = []
        research_dispatch_requests: list[str] = []
        page.on("pageerror", lambda error: failures.append(str(error)))
        page.route("**/api/cloud-auth/login**", lambda route: route.abort())
        page.on(
            "response",
            lambda response: (
                recent_responses.append(response.url)
                if response.url.endswith("/api/projects/recent")
                else None
            ),
        )
        page.on(
            "response",
            lambda response: (
                api_failures.append(f"{response.status} {response.url}")
                if "/api/" in response.url and response.status >= 400
                else None
            ),
        )

        def capture_request(request):
            if any(
                part in request.url
                for part in (
                    "/api/user-preferences/",
                    "/api/projects/diagnostics",
                    "/api/projects/research-qa",
                )
            ):
                protected_guest_requests.append(request.url)
            if request.method in {"POST", "PUT", "PATCH", "DELETE"}:
                mutation_requests.append(request.url)
            if any(
                part in request.url
                for part in (
                    "/api/projects/proposals/config",
                    "/api/projects/research-limits",
                    "/api/projects/research-sessions/start",
                )
            ):
                research_dispatch_requests.append(request.url)
            if "/api/projects/papers" in request.url:
                paper_requests.append(request.url)

        page.on("request", capture_request)

        # Regression: after sign-out, My Work may be the first API read,
        # before the Samples tab has ever established a guest workspace.
        cold_context = browser.new_context(viewport={"width": 1280, "height": 850})
        initial_my_work = cold_context.request.get(ui_url + "/api/projects/recent")
        assert initial_my_work.status == 200, initial_my_work.text()
        assert initial_my_work.json() == {"projects": []}
        assert any("sigma_guest" in cookie["name"] for cookie in cold_context.cookies())
        cold_context.close()

        # A remembered member My Work tab must not hide Samples on guest entry.
        page.add_init_script("window.localStorage.setItem('sigma.homeCatalogTab', 'recent')")
        page.goto(ui_url, wait_until="networkidle")
        expect(page.get_by_role("heading", name="Projects")).to_be_visible()
        expect(page.get_by_role("tab", name="Samples")).to_have_attribute("aria-selected", "true")
        welcome = page.get_by_role("dialog", name="Welcome to SIGMA!")
        expect(welcome).to_contain_text("without signing in")
        welcome.get_by_role("button", name="Let's get started").click()
        expect(page.get_by_role("button", name="About SIGMA", exact=True)).to_be_visible()
        expect(page.get_by_role("link", name="Sign in with Google")).to_be_visible()
        expect(page.locator(".home-account-grid .global-model-pill-position")).to_have_count(0)
        expect(page.locator("link[rel=icon]")).to_have_attribute("href", "/favicon.svg")
        expect(page.get_by_role("button", name="New project")).to_be_visible()
        expect(page.get_by_role("tab", name="Samples")).to_have_attribute("aria-selected", "true")
        expect(page.locator("details.sample-type-group").first).to_be_visible()
        assert not failures, failures

        scored_group = page.locator("details.sample-type-group").filter(
            has_text="Warp Drive Design v9 (acceptance fixture)"
        )
        scored_group.evaluate("element => { element.open = true; }")
        star = scored_group.get_by_role("link", name="View high scoring paper (75/100)")
        expect(star).to_have_attribute(
            "data-tooltip", "Marked as a high scoring paper (70 or higher)"
        )
        expect(star).to_have_attribute("target", "_blank")
        expect(star).to_have_attribute("rel", "noopener noreferrer")
        pdf_response = httpx.get(ui_url + star.get_attribute("href"), timeout=10)
        assert pdf_response.status_code == 200
        assert pdf_response.content == public_pdf
        scored_group.evaluate("element => { element.open = false; }")

        # My Work is a visitor-private temporary index, not a sign-in invitation.
        page.get_by_role("tab", name="My Work").click()
        expect(page.locator("#recent-panel .guest-recent-message")).to_have_count(0)
        expect(page.get_by_role("tab", name="My Work")).to_have_attribute("aria-selected", "true")
        assert page.locator("#recent-panel .recent-project").count() == 0
        page.get_by_role("tab", name="Samples").click()

        sample_group = page.locator("details.sample-type-group").filter(
            has_text="Did Jesus Use Cannabis?"
        )
        sample_group.evaluate("element => { element.open = true; }")
        with page.expect_response(
            lambda response: (
                response.url.endswith("/api/projects/samples/open")
                and response.request.method == "POST"
            )
        ) as opened_response:
            sample_group.locator("button.sample-open").click()
        expect(
            page.get_by_role("heading", name=re.compile(r"Did Jesus Use Cannabis\? v[12]"))
        ).to_be_visible(timeout=15000)
        assert opened_response.value.ok, opened_response.value.status
        sandbox_path = opened_response.value.json()["path"]
        assert Path(sandbox_path).is_dir()
        assert not Path(sandbox_path).is_relative_to(root / "saved-projects")
        expect(page.locator(".project-pane .project-description-toolbar-edit")).to_be_enabled()
        expect(page.locator(".project-classification-settings-button")).to_be_enabled()
        expect(page.locator(".project-download-button")).to_be_enabled()
        expect(page.locator(".strategy-title-pencil").first).to_be_enabled()
        expect(page.get_by_role("link", name="Sign in with Google")).to_be_visible()
        assert page.locator("[title]").count() == 0, "Native tooltips are forbidden"

        # AI actions must explain their behavior, never call a provider.
        page.get_by_role("button", name="Generate strategy", exact=True).click()
        strategy_preview = page.get_by_role("dialog", name="Generate a strategy")
        expect(strategy_preview).to_contain_text("No ChatGPT request was made")
        strategy_preview.get_by_role("button", name="Close preview").click()

        # All three guest actions show small, dismissible cards without
        # replacing the project UI, running research, or opening a modal.
        page.locator(".sessions-pane-heading").get_by_role(
            "button", name="New session", exact=True
        ).click()
        research_preview = page.get_by_role("status", name="Research sessions")
        expect(research_preview).to_contain_text("connected ChatGPT account")
        expect(page.get_by_role("group", name="Example session configuration")).to_have_count(0)
        research_preview.get_by_role("button", name="Dismiss preview").click()
        expect(research_preview).to_have_count(0)

        papers_pane = page.locator(".papers-pane")
        expect(papers_pane.get_by_role("heading", name="Papers")).to_be_visible()
        papers_pane.get_by_role("button", name="New paper").click()
        paper_preview = papers_pane.get_by_role("status", name="Generate a research paper")
        expect(paper_preview).to_contain_text("connected ChatGPT account")
        expect(papers_pane.get_by_role("button", name="Start Paper")).to_have_count(0)
        paper_preview.get_by_role("button", name="Dismiss preview").click()
        expect(paper_preview).to_have_count(0)

        page.get_by_role("button", name="Research Q/A").click()
        qa_dialog = page.get_by_role("dialog", name="Research Q/A")
        qa_dialog.get_by_role("textbox", name="Question").fill(
            "What evidence supports the central research question?"
        )
        qa_dialog.get_by_role("button", name="Ask", exact=True).click()
        qa_preview = qa_dialog.get_by_role("status", name="Ask about your research")
        expect(qa_preview).to_contain_text("connected ChatGPT account")
        expect(qa_dialog.get_by_role("textbox", name="Question")).to_have_value(
            "What evidence supports the central research question?"
        )
        qa_preview.get_by_role("button", name="Dismiss preview").click()
        expect(qa_preview).to_have_count(0)
        qa_dialog.get_by_role("button", name="Close research Q/A").click()

        strategy_markdown = page.locator(
            ".strategy-title-line .strategy-markdown-slot .sigma-render-toggle"
        ).first
        expect(strategy_markdown).to_be_enabled()
        strategy_markdown.click()
        markdown_preview = page.get_by_role("dialog", name="AI Markdown formatting")
        expect(markdown_preview).to_contain_text("No ChatGPT request was made")
        markdown_preview.get_by_role("button", name="Close preview").click()

        page.get_by_role("link", name="Go back to home page").click()
        expect(page.get_by_role("heading", name="Projects")).to_be_visible()
        my_work = page.get_by_role("tab", name="My Work")
        if my_work.get_attribute("aria-selected") != "true":
            my_work.click()
        expect(my_work).to_have_attribute("aria-selected", "true")
        # Existing temporary work survives navigation, not backend restarts.
        # Clicking an already-selected tab would collapse its groups.
        expect(page.locator("details.recent-type-group").first).to_be_visible(timeout=15000)
        for group in page.locator("details.recent-type-group").all():
            group.evaluate("element => { element.open = true; }")
        expect(
            page.get_by_text(re.compile(r"Did Jesus Use Cannabis\? v[12]")).first
        ).to_be_visible()
        private = page.evaluate(
            "async () => (await (await fetch('/api/projects/recent')).json()).projects"
        )
        assert any(entry["path"] == sandbox_path for entry in private), private

        # Another anonymous cookie cannot see, open or export the first visitor's work.
        other_context = browser.new_context(viewport={"width": 1280, "height": 850})
        other_page = other_context.new_page()
        other_page.goto(ui_url, wait_until="networkidle")
        other_welcome = other_page.get_by_role("dialog", name="Welcome to SIGMA!")
        if other_welcome.is_visible():
            other_welcome.get_by_role("button", name="Let's get started").click()
        guest_b = other_page.evaluate(
            """async path => {
              const list = await fetch('/api/projects/recent');
              const open = await fetch('/api/projects/open', {
                method: 'POST', headers: {'Content-Type':'application/json'},
                body: JSON.stringify({path})
              });
              const exportResult = await fetch(
                '/api/projects/download?' + new URLSearchParams({path}));
              return {list: (await list.json()).projects,
                      open: open.status, export: exportResult.status};
            }""",
            sandbox_path,
        )
        assert guest_b["list"] == [], guest_b
        assert guest_b["open"] == 404, guest_b
        assert guest_b["export"] == 404, guest_b
        other_context.close()

        # Create a second project without navigating so this tab has its
        # saved-list metadata but has never cached its full ProjectView.
        cold_path = page.evaluate(
            """async () => {
              const catalog = await (await fetch('/api/projects/samples')).json();
              const candidate = catalog.projects.find(
                sample => sample.title === 'Operation Narrow Passage');
              if (!candidate) throw new Error('Cold-open sample missing');
              const response = await fetch('/api/projects/samples/open', {
                method: 'POST',
                headers: {'Content-Type': 'application/json'},
                body: JSON.stringify({sample_id: candidate.id})
              });
              if (!response.ok) throw new Error('Could not create cold-open project');
              return (await response.json()).path;
            }"""
        )
        assert cold_path != sandbox_path
        cold_group = page.locator("#recent-panel details.recent-type-group").filter(
            has_text="Operation Narrow Passage"
        )
        expect(cold_group).to_have_count(1, timeout=20000)
        cold_group.evaluate("element => { element.open = true; }")
        cold_entry = cold_group.locator("button.recent-open").filter(
            has_text="Operation Narrow Passage"
        )
        expect(cold_entry).to_be_visible()

        # Hold real open responses so browser assertions distinguish waiting on
        # Home (cold) from immediate navigation followed by revalidation (warm).
        page.evaluate(
            """() => {
              const original = window.fetch.bind(window);
              window.__sigmaOriginalFetch = original;
              window.__sigmaOpenRevalidations = 0;
              window.fetch = (request, options) => {
                if (String(request).endsWith('/api/projects/open')) {
                  window.__sigmaOpenRevalidations += 1;
                  return new Promise(resolve => setTimeout(resolve, 2500))
                    .then(() => original(request, options));
                }
                return original(request, options);
              };
            }"""
        )
        cold_entry.click()
        expect(cold_entry.locator(".project-opening-label")).to_have_text("Opening...")
        expect(page.get_by_role("heading", name="Projects")).to_be_visible()
        expect(
            page.get_by_role("heading", name=re.compile(r"Operation Narrow Passage v[0-9]+"))
        ).to_be_visible(timeout=7000)

        page.get_by_role("link", name="Go back to home page").click()
        page.get_by_role("tab", name="My Work").click()
        warm_group = page.locator("#recent-panel details.recent-type-group").filter(
            has_text="Did Jesus Use Cannabis?"
        )
        expect(warm_group).to_have_count(1)
        warm_group.evaluate("element => { element.open = true; }")
        warm_entry = warm_group.locator("button.recent-open").filter(
            has_text="Did Jesus Use Cannabis?"
        )
        expect(warm_entry).to_be_visible()
        page.evaluate("window.__sigmaOpenRevalidations = 0")
        warm_entry.click()
        expect(
            page.get_by_role("heading", name=re.compile(r"Did Jesus Use Cannabis\? v[12]"))
        ).to_be_visible(timeout=1800)
        page.wait_for_function("window.__sigmaOpenRevalidations > 0", timeout=1800)
        expect(page.get_by_text("Opening project…")).to_have_count(0)
        page.evaluate("() => { window.fetch = window.__sigmaOriginalFetch; }")

        assert not [
            request
            for request in mutation_requests
            if any(
                part in request
                for part in (
                    "/research-sessions/start",
                    "/papers/",
                    "/research-qa",
                    "/text/convert",
                    "/strategy-inference",
                    "/proposals",
                )
            )
        ], mutation_requests
        assert not failures, failures
        assert not list((root / "saved-projects").glob("*.sigma"))
        browser.close()


if __name__ == "__main__":
    main()
