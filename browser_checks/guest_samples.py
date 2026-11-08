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
from urllib.parse import parse_qs, urlsplit

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
        opened_projects: list[dict] = []
        recent_responses: list[str] = []
        api_failures: list[str] = []
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

        def capture(response):
            if response.url.endswith("/api/projects/samples/open"):
                opened_projects.append(response.json())

        page.on("response", capture)
        page.goto(ui_url, wait_until="networkidle")
        expect(page.get_by_role("heading", name="Projects")).to_be_visible()
        # Guest has no per-user default; its visible model pill must not poll protected settings.
        expect(page.get_by_role("button", name="Model Sign in")).to_be_visible()
        welcome = page.get_by_role("dialog", name="Welcome to SIGMA!")
        expect(welcome).to_be_visible()
        expect(welcome).to_contain_text("Explore as a guest without running or saving projects")
        expect(welcome).to_contain_text("request an invitation to become a member")
        expect(welcome).to_contain_text(
            "decides whether to include sponsorship when granting your invitation"
        )
        expect(welcome.locator(".invitation-welcome-about-hint")).to_contain_text(
            "About SIGMA pill"
        )
        expect(welcome.locator("#invitation-welcome-phrase")).not_to_be_empty()
        assert welcome.evaluate("el => getComputedStyle(el).transform") == (
            "matrix(1.25, 0, 0, 1.25, 0, 0)"
        )
        assert (
            welcome.locator(".invitation-welcome-intro").evaluate(
                "el => getComputedStyle(el).marginBottom"
            )
            == "16px"
        )
        assert (
            welcome.locator("#invitation-welcome-phrase").evaluate(
                "el => getComputedStyle(el).fontStyle"
            )
            == "italic"
        )
        expect(welcome.get_by_role("link", name="Sign in with Google")).to_have_count(0)
        welcome.get_by_role("button", name="Let's get started").click()
        expect(welcome).to_have_count(0)
        page.route(
            "**/api/test-long-error",
            lambda route: route.fulfill(
                status=503,
                headers={"content-type": "application/json"},
                body='{"error":"' + ("provider detail " * 200) + '"}',
            ),
        )
        page.evaluate("fetch('/api/test-long-error')")
        long_error_toast = page.locator(".request-toast").last
        expect(long_error_toast).to_contain_text("unusually long error response")
        assert len(long_error_toast.inner_text()) < 250
        page.unroute("**/api/test-long-error")
        expect(page.get_by_role("link", name="Sign in with Google")).to_be_visible()
        # A signed-out guest has not completed Google verification, so the
        # invitation action and its dialog must be absent.
        expect(page.get_by_role("link", name="Sign in with Google")).to_be_visible()
        expect(page.get_by_role("button", name="Invite me!")).to_have_count(0)
        expect(page.get_by_role("dialog", name="Request an invitation")).to_have_count(0)
        expect(page.get_by_role("button", name="New")).to_have_count(0)
        expect(page.get_by_role("button", name="Open", exact=True)).to_have_count(0)
        expect(page.get_by_role("tab", name="Saved")).to_be_enabled()
        # Idle browser tabs have an explicit favicon, so the temporary
        # running/queued heartbeat cannot remain cached after work completes.
        expect(page.locator('link[rel="icon"]')).to_have_attribute("href", "/favicon.svg")
        expect(page.get_by_role("tab", name="Samples")).to_have_attribute("aria-selected", "true")
        expect(page.locator("details.sample-type-group").first).to_be_visible()
        assert page.locator("details.sample-type-group[open]").count() == 0
        scored_group = page.locator("details.sample-type-group").filter(
            has_text="Warp Drive Design v9 (acceptance fixture)"
        )
        expect(scored_group).to_be_visible()
        scored_group.evaluate("element => { element.open = true; }")
        star = scored_group.get_by_role("link", name="View high scoring paper (75/100)")
        expect(star).to_be_visible()
        expect(star).to_have_attribute("data-tooltip", "Marked as a high scoring paper (>70)")
        expect(star).to_have_attribute("target", "_blank")
        expect(star).to_have_attribute("rel", "noopener noreferrer")
        expect(scored_group).to_contain_text("Best score 75/100")
        expect(scored_group.locator(".recent-title-star")).to_have_count(1)
        star_color = star.evaluate("element => getComputedStyle(element).color")
        star.hover()
        hover_color = star.evaluate("element => getComputedStyle(element).color")
        assert hover_color != star_color
        assert (
            star.evaluate("element => getComputedStyle(element).backgroundColor")
            == "rgba(0, 0, 0, 0)"
        )
        star.focus()
        assert star.evaluate("element => getComputedStyle(element).color") == hover_color
        assert scored_group.locator(".recent-pin, .recent-forget").count() == 0
        pdf_response = httpx.get(ui_url + star.get_attribute("href"), timeout=10)
        assert pdf_response.status_code == 200, pdf_response.text[:500]
        assert pdf_response.headers["content-type"].startswith("application/pdf")
        assert "inline" in pdf_response.headers["content-disposition"]
        assert pdf_response.content == public_pdf
        # An unauthenticated HTTP client received the PDF without a guest
        # session cookie, working project, provider connection or research run.
        scored_group.evaluate("element => { element.open = false; }")
        page.get_by_role("tab", name="Saved").click()
        message = page.locator("#recent-panel .guest-recent-message")
        expect(message.locator("span").nth(0)).to_have_text("Sign in to create and")
        expect(message.locator("span").nth(1)).to_have_text("save your own projects.")
        typography = message.evaluate("element => getComputedStyle(element)")
        assert typography["fontFamily"].startswith("Georgia"), typography
        assert typography["fontSize"] == "18px", typography
        expect(page.get_by_role("tab", name="Saved")).to_have_attribute("aria-selected", "true")
        assert recent_responses == [], recent_responses
        page.get_by_role("tab", name="Samples").click()
        sign_in = page.get_by_role("link", name="Sign in with Google")
        expect(sign_in).to_have_attribute("href", "/api/cloud-auth/login")
        expect(page.locator(".home-auth-pills .api-connection")).to_have_count(0)
        expect(page.get_by_role("dialog", name="Account and model settings")).to_have_count(0)

        sample_group = page.locator("details.sample-type-group").filter(
            has_text="Did Jesus Use Cannabis?"
        )
        qubit_group = page.locator("details.sample-type-group").filter(
            has_text="When Does Qubit Decoherence Require a Non-Markovian Model?"
        )
        expect(qubit_group).to_be_visible()
        qubit_group.evaluate("element => { element.open = true; }")
        expect(qubit_group.locator("summary")).to_contain_text("Physics")
        expect(qubit_group.locator("summary svg.research-type-icon-physics")).to_be_visible()
        expect(
            qubit_group.get_by_role(
                "button", name="Open When Does Qubit Decoherence Require a Non-Markovian Model?"
            )
        ).to_be_visible()
        sample_group.evaluate("element => { element.open = true; }")
        expect(sample_group.locator("button.sample-open")).to_be_visible()
        if page.get_by_text("Authentication required.").count():
            raise AssertionError(
                f"unexpected authentication failure; API responses: {api_failures}"
            )

        page.get_by_role("button", name="About SIGMA", exact=True).click()
        expect(page.get_by_role("dialog", name="About SIGMA")).to_be_visible()
        policy = page.get_by_role("link", name="Privacy Notice")
        policy.scroll_into_view_if_needed()
        expect(policy).to_be_visible()
        policy.click()
        expect(page.get_by_role("heading", name="SIGMA Privacy Notice")).to_be_visible()
        page.goto(ui_url)
        expect(page.get_by_role("heading", name="Projects")).to_be_visible()

        sample_group.locator("button.sample-open").evaluate("button => button.click()")
        expect(
            page.get_by_role("heading", name=re.compile(r"Did Jesus Use Cannabis\? v[12]"))
        ).to_be_visible(timeout=15000)
        page.get_by_role("link", name="Go back to home page").click()
        expect(page.get_by_role("heading", name="Projects")).to_be_visible()
        sample_group = page.locator("details.sample-type-group").filter(
            has_text="Did Jesus Use Cannabis?"
        )
        expect(sample_group).to_have_attribute("open", "")
        sample_group.locator("button.sample-open").click()
        expect(
            page.get_by_role("heading", name=re.compile(r"Did Jesus Use Cannabis\? v[12]"))
        ).to_be_visible(timeout=15000)
        expect(page.locator(".project-identity-pill-stack .api-connection")).to_have_count(0)
        # The Markdown icon must match the title pencil at rest and on hover.
        # The three-field Project Description renders Markdown directly;
        # only strategies retain a plain/Markdown conversion button.
        project_markdown = page.locator(
            ".project-pane-title-line .project-markdown-slot .sigma-render-toggle"
        )
        expect(project_markdown).to_have_count(0)
        subject = page.locator(".sigma-description-field").first
        expect(subject.get_by_role("heading", name="Research Subject")).to_be_visible()
        expect(subject.locator(".sigma-description-rendered")).to_be_visible()
        expect(page.get_by_role("heading", name="Desired Outcomes")).to_be_visible()
        expect(page.get_by_role("heading", name="Paper Requirements")).to_be_visible()
        pencil_button = page.locator(".project-pane-title-line .project-title-pencil")
        expect(pencil_button).to_be_visible()
        icon_style = (
            "element => { const s = getComputedStyle(element); "
            "return [s.color, s.backgroundImage, s.borderTopColor, "
            "s.borderTopLeftRadius, s.boxShadow, s.textShadow]; }"
        )
        pencil_button.hover()
        expect(page.locator("#sigma-ui-tooltip")).to_have_text("Edit text and description")
        assert pencil_button.get_attribute("title") is None
        strategy_pencils = page.locator(".strategy-title-pencil")
        assert strategy_pencils.count() > 0
        assert all(
            value == "Edit strategy title and approach"
            for value in strategy_pencils.evaluate_all(
                "buttons => buttons.map(button => button.dataset.tooltip)"
            )
        )
        assert all(
            value is None
            for value in strategy_pencils.evaluate_all(
                "buttons => buttons.map(button => button.getAttribute('title'))"
            )
        )
        strategy_markdown = page.locator(
            ".strategy-title-line .strategy-markdown-slot .sigma-render-toggle"
        ).first
        strategy_pencil = strategy_pencils.first
        expect(strategy_markdown).to_be_visible()
        assert strategy_markdown.get_attribute("title") is None
        assert strategy_markdown.evaluate(icon_style) == strategy_pencil.evaluate(icon_style)
        strategy_pencil.hover()
        expect(strategy_pencil).to_have_css("color", "rgb(255, 242, 233)")
        strategy_hover_style = strategy_pencil.evaluate(icon_style)
        strategy_markdown.hover()
        expect(strategy_markdown).to_have_css("color", "rgb(255, 242, 233)")
        assert strategy_markdown.evaluate(icon_style) == strategy_hover_style
        strategy_offset = strategy_markdown.locator("svg.markdown-logo").evaluate(
            """svg => {
              const bounds = svg.getBBox();
              const midpoint = new DOMPoint(bounds.x + bounds.width / 2,
                bounds.y + bounds.height / 2).matrixTransform(svg.getScreenCTM());
              const button = svg.closest('button').getBoundingClientRect();
              return [midpoint.x - (button.left + button.right) / 2,
                      midpoint.y - (button.top + button.bottom) / 2];
            }"""
        )
        assert all(abs(offset) < 1 for offset in strategy_offset), strategy_offset
        page.mouse.move(0, 0)
        project_google = page.get_by_role("link", name="Sign in with Google")
        expect(project_google).to_be_visible()
        # Guests have not selected a verified Google account, so they cannot
        # request an invitation yet. The two pills must never appear together.
        expect(page.get_by_role("button", name="Invite me!")).to_have_count(0)
        papers_before = len(paper_requests)
        papers_pane = page.locator(".papers-pane")
        expect(papers_pane.get_by_role("heading", name="Papers")).to_be_visible()
        expect(papers_pane).to_contain_text("Sign in to export your research as TeX.")
        expect(papers_pane.get_by_role("button", name="Generate paper")).to_have_count(0)
        assert len(paper_requests) == papers_before, paper_requests
        play = page.locator(".sessions-pane-heading").get_by_role(
            "button", name="New session", exact=True
        )
        expect(play).to_be_enabled()
        mutations_before_play = len(mutation_requests)
        dispatches_before_play = len(research_dispatch_requests)
        play.click()
        play_dialog = page.get_by_role("dialog", name="Ready to investigate?")
        expect(play_dialog).to_contain_text("Sign in to run a research session.")
        expect(play_dialog.get_by_role("button", name="Sign in with Google")).to_be_visible()
        expect(play_dialog.get_by_role("button", name="Close sign-in prompt")).to_be_visible()
        actions = play_dialog.locator(".settings-actions")
        assert (
            actions.evaluate("element => getComputedStyle(element).justifyContent") == "flex-start"
        )
        action_colors = actions.locator("button").evaluate_all(
            "buttons => buttons.map(button => getComputedStyle(button).color)"
        )
        assert len(action_colors) == 1, action_colors
        assert len(mutation_requests) == mutations_before_play, mutation_requests
        assert len(research_dispatch_requests) == dispatches_before_play, research_dispatch_requests
        play_dialog.get_by_role("button", name="Close sign-in prompt").click()
        expect(play_dialog).to_have_count(0)
        expect(play).to_be_focused()
        assert len(mutation_requests) == mutations_before_play, mutation_requests
        assert len(research_dispatch_requests) == dispatches_before_play, research_dispatch_requests
        page.get_by_role("button", name="Generate strategy", exact=True).click()
        expect(
            page.get_by_role("status").filter(has_text="AI features require a signed-in account.")
        ).to_be_visible()
        expect(page.get_by_role("link", name="Go back to home page")).to_be_visible()
        assert opened_projects
        assert Path(opened_projects[-1]["path"]).is_dir()
        assert not Path(opened_projects[-1]["path"]).is_relative_to(root / "saved-projects")
        recent = page.evaluate(
            "async () => (await (await fetch('/api/projects/recent')).json()).projects"
        )
        assert recent == [], recent
        # Earlier expected 401s can leave an auth notice; ensure no gated mutation.
        assert len(mutation_requests) == mutations_before_play
        play.click()
        play_dialog = page.get_by_role("dialog", name="Ready to investigate?")
        expect(play_dialog.get_by_role("button", name="Sign in with Google")).to_be_visible()
        page.unroute("**/api/cloud-auth/login**")
        page.route(
            "**/api/cloud-auth/login**",
            lambda route: route.fulfill(
                status=200,
                content_type="text/html",
                body="<!doctype html><title>OAuth fixture</title>",
            ),
        )
        with page.expect_request("**/api/cloud-auth/login**") as sign_in_request:
            play_dialog.get_by_role("button", name="Sign in with Google").click()
        expect(play_dialog).to_have_count(0)
        sign_in_url = urlsplit(sign_in_request.value.url)
        assert sign_in_url.path == "/api/cloud-auth/login", sign_in_url
        return_to = parse_qs(sign_in_url.query).get("return_to", [None])[0]
        assert return_to == f"/project?path={opened_projects[-1]['path']}&resume_play=1", return_to
        assert page.evaluate("sessionStorage.getItem('sigma.playSignInReturn')") == "true"
        assert page.evaluate("sessionStorage.getItem('sigma.resumeGuestPlay')") == "true"
        session = {"authenticated": True}

        def cloud_status(route):
            route.fulfill(
                status=200,
                content_type="application/json",
                body=json.dumps(
                    {
                        "enabled": True,
                        "ready": True,
                        "authenticated": session["authenticated"],
                        "user": {"email": "member@example.org", "role": "member"}
                        if session["authenticated"]
                        else None,
                        "account": {
                            "identity": {"email": "member@example.org", "verified": True},
                            "access": {"status": "active", "role": "member"},
                            "workspace": {"available": True, "id": "fixture"},
                            "model_access": {"mode": "personal", "connection": "connected"},
                            "sponsorship": {"eligible": False, "forced": False},
                        }
                        if session["authenticated"]
                        else None,
                        "target": "local",
                        "admin_contact_email": None,
                    }
                ),
            )

        page.route("**/api/cloud-auth/status", cloud_status)
        page.route(
            "**/api/projects/proposals/config?**",
            lambda route: route.fulfill(
                status=200,
                content_type="application/json",
                body=json.dumps(
                    {
                        "available": True,
                        "binding": "fixture-member",
                        "model": "gpt-6.1-sol",
                        "reasoning_effort": "high",
                        "project_id": "fixture-project",
                        "message": "Fixture connection is ready.",
                    }
                ),
            ),
        )

        def generous_research_limits(route):
            response = route.fetch()
            limits = response.json()
            limits["model_calls"] = 30
            route.fulfill(response=response, json=limits)

        page.route("**/api/projects/research-limits?**", generous_research_limits)
        # Live presence and activity polling intentionally keep network requests open;
        # the explicit UI assertions below, not network idleness, establish readiness.
        page.goto(f"{ui_url}{return_to}", wait_until="domcontentloaded")
        expect(
            page.get_by_role("heading", name=re.compile(r"Did Jesus Use Cannabis\? v[12]"))
        ).to_be_visible()
        expect(page.get_by_role("dialog", name="Welcome to SIGMA!")).to_have_count(0)
        # The imported sample may use a retired built-in project type. Its
        # complete saved snapshot requires explicit acknowledgement before
        # the sign-in return can resume the start confirmation.
        missing_type = page.get_by_role("alertdialog", name="Project type unavailable")
        if missing_type.is_visible():
            expect(missing_type).to_contain_text("complete saved settings")
            missing_type.get_by_role("button", name="Continue with saved settings").click()
        expect(page.get_by_role("button", name="Start Session 1")).to_be_visible(timeout=15000)
        assert page.evaluate("sessionStorage.getItem('sigma.resumeGuestPlay')") is None
        resumed_mutations = len(mutation_requests)
        page.locator(".session-start-link").filter(has_text="Cancel").click()
        assert len(mutation_requests) == resumed_mutations, mutation_requests
        assert not any(
            "/api/projects/research-sessions/start" in url for url in research_dispatch_requests
        ), research_dispatch_requests
        page.route(
            "**/api/projects/guest-copy",
            lambda route: route.fulfill(
                status=201,
                content_type="application/json",
                body=json.dumps({"path": opened_projects[-1]["path"]}),
            ),
        )

        def sign_out(route):
            session["authenticated"] = False
            route.fulfill(status=204)

        page.route("**/api/cloud-auth/logout", sign_out)
        # This member context did not previously show a guest welcome. Signing
        # out should not make the same tab look like a first-time guest visit.
        page.evaluate("sessionStorage.removeItem('sigma.guestWelcomeDismissed')")
        page.get_by_role("button", name="Sign out of Google").click()
        expect(page).to_have_url(re.compile(r"/project\?path="))
        expect(page.get_by_role("dialog", name="Welcome to SIGMA!")).to_have_count(0)
        expect(
            page.get_by_role("heading", name=re.compile(r"Did Jesus Use Cannabis\? v[12]"))
        ).to_be_visible()
        assert not failures, failures
        assert (
            not list((root / "saved-projects").glob("*.sigma"))
            if (root / "saved-projects").exists()
            else True
        )
        backdrop_context = browser.new_context(viewport={"width": 1280, "height": 850})
        backdrop_page = backdrop_context.new_page()
        backdrop_page.goto(ui_url, wait_until="networkidle")
        backdrop_welcome = backdrop_page.get_by_role("dialog", name="Welcome to SIGMA!")
        expect(backdrop_welcome).to_be_visible()
        backdrop_page.mouse.click(2, 2)
        # The welcome modal dismisses on a backdrop click.
        expect(backdrop_welcome).to_have_count(0)
        backdrop_context.close()
        browser.close()


if __name__ == "__main__":
    main()
