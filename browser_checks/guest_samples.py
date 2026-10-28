"""Real Chrome acceptance for the unauthenticated hosted sample workflow."""

from __future__ import annotations

import json
import os
import re
import socket
import subprocess
import tempfile
import time
from pathlib import Path
from tempfile import TemporaryDirectory
from urllib.parse import parse_qs, urlsplit

import httpx
from playwright.sync_api import expect, sync_playwright

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


def main() -> None:
    api_port, ui_port = free_port(), free_port()
    while api_port == ui_port:
        ui_port = free_port()
    api_url = f"http://127.0.0.1:{api_port}"
    ui_url = f"http://127.0.0.1:{ui_port}"
    with TemporaryDirectory(prefix="sigma-guest-browser-") as temporary:
        root = Path(temporary)
        os.chmod(root, 0o700)
        env = os.environ.copy()
        env.update(
            {
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
                exercise(ui_url, root)
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


def exercise(ui_url: str, root: Path) -> None:
    with sync_playwright() as playwright:
        browser = playwright.chromium.launch(executable_path=CHROME, headless=True)
        page = browser.new_page(viewport={"width": 1280, "height": 850})
        failures: list[str] = []
        opened_projects: list[dict] = []
        recent_responses: list[str] = []
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
        welcome = page.get_by_role("dialog", name="Welcome to SIGMA!")
        expect(welcome).to_be_visible()
        expect(welcome).to_contain_text("Explore as a guest without running or saving projects")
        expect(welcome).to_contain_text("request an invitation to become a member")
        expect(welcome).to_contain_text(
            "decides whether to include sponsorship when granting your invitation"
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
        expect(page.get_by_role("tab", name="Samples")).to_have_attribute("aria-selected", "true")
        expect(page.locator("details.sample-type-group").first).to_be_visible()
        assert page.locator("details.sample-type-group[open]").count() == 0
        page.get_by_role("tab", name="Saved").click()
        message = page.locator(".guest-recent-message")
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
        sample_group.evaluate("element => { element.open = true; }")
        expect(sample_group.locator("button.sample-open")).to_be_visible()
        expect(page.get_by_text("Authentication required.")).to_have_count(0)

        page.get_by_role("button", name="About SIGMA", exact=True).click()
        expect(page.get_by_role("dialog", name="About SIGMA")).to_be_visible()
        policy = page.get_by_role("link", name="Privacy Notice")
        policy.scroll_into_view_if_needed()
        expect(policy).to_be_visible()
        policy.click()
        expect(page.get_by_role("heading", name="SIGMA Privacy Notice")).to_be_visible()
        page.get_by_role("button", name="Close", exact=True).click()
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
        project_google = page.get_by_role("link", name="Sign in with Google")
        expect(project_google).to_be_visible()
        # Guests have not selected a verified Google account, so they cannot
        # request an invitation yet. The two pills must never appear together.
        expect(page.get_by_role("button", name="Invite me!")).to_have_count(0)
        expect(
            page.locator(
                "header .header-controls button:visible, header .header-controls a:visible"
            )
        ).to_have_count(5)
        papers_before_dialog = len(paper_requests)
        page.get_by_role("button", name="LaTeX research paper").click()
        tex_dialog = page.get_by_role("dialog", name="Academic paper using LaTeX")
        expect(tex_dialog).to_contain_text("Sign in to export your research as TeX.")
        assert len(paper_requests) == papers_before_dialog, paper_requests
        tex_dialog.get_by_role("button", name="Close").click()
        play = page.get_by_role("button", name="Start a new research session", exact=True)
        expect(play).to_be_enabled()
        mutations_before_play = len(mutation_requests)
        dispatches_before_play = len(research_dispatch_requests)
        play.click()
        play_dialog = page.get_by_role("dialog", name="Ready to investigate?")
        expect(play_dialog).to_contain_text("Sign in to run a research session.")
        expect(play_dialog.get_by_role("button", name="Sign in with Google")).to_be_visible()
        expect(play_dialog.get_by_role("button", name="Cancel")).to_be_visible()
        actions = play_dialog.locator(".settings-actions")
        assert (
            actions.evaluate("element => getComputedStyle(element).justifyContent") == "flex-start"
        )
        action_colors = actions.locator("button").evaluate_all(
            "buttons => buttons.map(button => getComputedStyle(button).color)"
        )
        assert len(action_colors) == 2 and action_colors[0] == action_colors[1], action_colors
        assert len(mutation_requests) == mutations_before_play, mutation_requests
        assert len(research_dispatch_requests) == dispatches_before_play, research_dispatch_requests
        play_dialog.get_by_role("button", name="Cancel").click()
        expect(play_dialog).to_have_count(0)
        expect(play).to_be_focused()
        assert len(mutation_requests) == mutations_before_play, mutation_requests
        assert len(research_dispatch_requests) == dispatches_before_play, research_dispatch_requests
        page.get_by_role("button", name="Generate", exact=True).click()
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
        expect(page.get_by_text("Authentication required.")).to_have_count(0)
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
        page.goto(f"{ui_url}{return_to}", wait_until="networkidle")
        expect(
            page.get_by_role("heading", name=re.compile(r"Did Jesus Use Cannabis\? v[12]"))
        ).to_be_visible()
        expect(page.get_by_role("dialog", name="Welcome to SIGMA!")).to_have_count(0)
        expect(page.get_by_role("button", name="Start new session #1")).to_be_visible(timeout=15000)
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
        expect(backdrop_welcome).to_have_count(0)
        backdrop_context.close()
        browser.close()


if __name__ == "__main__":
    main()
