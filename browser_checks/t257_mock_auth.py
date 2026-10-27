"""Real-Chrome acceptance for the local T257 mock-auth walkthrough."""

from __future__ import annotations

import json
import os
import re
import socket
import subprocess
import sys
import tempfile
import time
import urllib.error
import urllib.request
from pathlib import Path
from typing import Any
from urllib.parse import urlencode
from uuid import uuid4

from playwright.sync_api import expect, sync_playwright

ROOT = Path(__file__).resolve().parents[1]
FRONTEND = ROOT / "frontend"
SCREENSHOTS = ROOT / "docs" / "evaluations" / "t257" / "screenshots"
CHROME = os.environ.get(
    "SIGMA_BROWSER_EXECUTABLE",
    "/Applications/Google Chrome.app/Contents/MacOS/Google Chrome",
)


def wait_for(url: str, processes: tuple[subprocess.Popen, ...], logs: tuple[Path, ...]) -> None:
    deadline = time.monotonic() + 30
    while time.monotonic() < deadline:
        try:
            with urllib.request.urlopen(url, timeout=0.5):
                return
        except (OSError, urllib.error.URLError):
            if any(process.poll() is not None for process in processes):
                details = "\n".join(log.read_text(errors="replace") for log in logs)
                raise RuntimeError(f"The local mock-auth app failed to start:\n{details}")
            time.sleep(0.1)
    details = "\n".join(log.read_text(errors="replace") for log in logs)
    raise RuntimeError(f"The local mock-auth app did not become ready:\n{details}")


def free_port() -> int:
    with socket.socket() as listener:
        listener.bind(("127.0.0.1", 0))
        return int(listener.getsockname()[1])


def main() -> None:
    temporary_parent = Path("/private/tmp") if Path("/private/tmp").is_dir() else None
    with tempfile.TemporaryDirectory(prefix="sigma-t257-mock-", dir=temporary_parent) as value:
        root = Path(value)
        for name in ("auth", "workspaces", "projects", "state"):
            (root / name).mkdir(mode=0o700)
        environment = os.environ.copy()
        api_port, ui_port = free_port(), free_port()
        while ui_port == api_port:
            ui_port = free_port()
        origin = f"http://127.0.0.1:{ui_port}"
        api_origin = f"http://127.0.0.1:{api_port}"
        environment.update(
            {
                "SIGMA_CLOUD_AUTH_ENABLED": "true",
                "SIGMA_CLOUD_AUTH_LOCAL": "true",
                "SIGMA_MOCK_AUTH": "1",
                "SIGMA_CLOUD_PUBLIC_ORIGIN": origin,
                "SIGMA_API_TARGET": api_origin,
                "SIGMA_CLOUD_AUTH_HOME": str(root / "auth"),
                "SIGMA_CLOUD_WORKSPACES_ROOT": str(root / "workspaces"),
                "SIGMA_PROJECTS_ROOT": str(root / "projects"),
                "SIGMA_STATE_DIR": str(root / "state"),
                "OPENAI_API_KEY": "",
                "SIGMA_CLOUD_OPENAI_API_KEY": "",
            }
        )
        api_log = root / "api.log"
        ui_log = root / "ui.log"
        with api_log.open("w") as api_output, ui_log.open("w") as ui_output:
            api = subprocess.Popen(
                [
                    sys.executable,
                    "-m",
                    "uvicorn",
                    "sigma.api:app",
                    "--host",
                    "127.0.0.1",
                    "--port",
                    str(api_port),
                ],
                cwd=ROOT,
                env=environment,
                stdout=api_output,
                stderr=subprocess.STDOUT,
            )
            ui = subprocess.Popen(
                [
                    str(FRONTEND / "node_modules/.bin/vite"),
                    "--host",
                    "127.0.0.1",
                    "--port",
                    str(ui_port),
                    "--strictPort",
                ],
                cwd=FRONTEND,
                env=environment,
                stdout=ui_output,
                stderr=subprocess.STDOUT,
            )
            try:
                wait_for(
                    f"{api_origin}/api/ui-instance",
                    (api, ui),
                    (api_log, ui_log),
                )
                wait_for(f"{origin}/", (api, ui), (api_log, ui_log))
                exercise_browser(origin)
            finally:
                for process in (ui, api):
                    if process.poll() is None:
                        process.terminate()
                        try:
                            process.wait(timeout=5)
                        except subprocess.TimeoutExpired:
                            process.kill()
                            process.wait(timeout=5)


def exercise_browser(origin: str) -> None:
    with sync_playwright() as playwright:
        browser = playwright.chromium.launch(executable_path=CHROME, headless=True)
        page = browser.new_page(viewport={"width": 1440, "height": 900})
        errors: list[str] = []
        page.on("pageerror", lambda error: errors.append(str(error)))
        page.goto(origin + "/", wait_until="networkidle")
        identity = page.get_by_label("Mock authentication identity")
        expect(identity).to_be_visible()
        SCREENSHOTS.mkdir(parents=True, exist_ok=True)
        page.screenshot(path=str(SCREENSHOTS / "green-next-home-guest-desktop.png"), full_page=True)
        expect(page.locator(".api-connection > summary")).to_have_count(1)
        expect(page.get_by_role("dialog", name="ChatGPT connection settings")).to_have_count(0)
        inspect_account_view(page, 1440, 900, "Guest · Explore SIGMA")
        inspect_account_view(page, 390, 844, "Guest · Explore SIGMA")
        page.screenshot(path=str(SCREENSHOTS / "green-next-home-guest-narrow.png"), full_page=True)

        disconnect_page = browser.new_page(viewport={"width": 1280, "height": 800})
        disconnect_state = {"connected": True, "requests": 0, "connect_requests": 0}

        def mock_disconnect_api(route) -> None:
            request = route.request
            if request.url.endswith("/api/cloud-auth/status"):
                route.fulfill(
                    status=200,
                    content_type="application/json",
                    body='{"enabled":false,"ready":true,"authenticated":false,"user":null,"admin_contact_email":null}',
                )
            elif "/api/ai/connection" in request.url:
                connected = disconnect_state["connected"]
                route.fulfill(
                    status=200,
                    content_type="application/json",
                    body=json.dumps(
                        {
                            "mode": "chatgpt",
                            "status": "connected" if connected else "disconnected",
                            "label": "ChatGPT connected" if connected else "Connect to ChatGPT",
                            "guidance": "",
                            "checked_at": "2026-10-27T00:00:00Z",
                            "ttl_seconds": 60,
                            "active_account": "fixture-account" if connected else None,
                            "account_label": "fixture@example.test" if connected else None,
                            "accounts": (
                                [{"id": "fixture-account", "label": "fixture@example.test"}]
                                if connected
                                else []
                            ),
                        }
                    ),
                )
            elif request.url.endswith("/api/ai/disconnect"):
                disconnect_state["requests"] += 1
                disconnect_state["connected"] = False
                route.fulfill(
                    status=200,
                    content_type="application/json",
                    body='{"remote_revocation_confirmed":true,"message":"Disconnected."}',
                )
            elif request.url.endswith("/api/ai/auth/begin"):
                disconnect_state["connect_requests"] += 1
                route.fulfill(
                    status=503,
                    content_type="application/json",
                    body='{"error":"Fixture ChatGPT sign-in unavailable."}',
                )
            else:
                route.continue_()

        disconnect_page.route("**/api/**", mock_disconnect_api)
        disconnect_page.goto(origin + "/", wait_until="domcontentloaded")
        chatgpt_pill = disconnect_page.locator(".api-connection > summary")
        expect(chatgpt_pill).to_have_text("Disconnect from ChatGPT")
        chatgpt_pill.click()
        expect(chatgpt_pill).to_have_text("Connect to ChatGPT")
        assert disconnect_state["requests"] == 1, disconnect_state
        chatgpt_pill.click()
        expect(disconnect_page.locator('.connection-pill-message[role="alert"]')).to_contain_text(
            "Fixture ChatGPT sign-in unavailable."
        )
        assert disconnect_state["connect_requests"] == 1, disconnect_state
        expect(
            disconnect_page.get_by_role("dialog", name="ChatGPT connection settings")
        ).to_have_count(0)
        disconnect_page.close()

        google_state = {"authenticated": True, "connected": True, "disconnect_requests": 0}
        identity_page = browser.new_page(viewport={"width": 1280, "height": 800})

        def mock_google_identity_api(route) -> None:
            request = route.request
            if request.url.endswith("/api/cloud-auth/status"):
                route.fulfill(
                    status=200,
                    content_type="application/json",
                    body=json.dumps(
                        {
                            "target": "local",
                            "enabled": True,
                            "ready": True,
                            "authenticated": google_state["authenticated"],
                            "user": {"email": "member@example.test", "role": "member"}
                            if google_state["authenticated"]
                            else None,
                            "admin_contact_email": None,
                        }
                    ),
                )
            elif "/api/ai/connection" in request.url:
                connected = google_state["connected"] and google_state["authenticated"]
                route.fulfill(
                    status=200,
                    content_type="application/json",
                    body=json.dumps(
                        {
                            "mode": "chatgpt",
                            "status": "connected" if connected else "disconnected",
                            "label": "ChatGPT connected" if connected else "Connect to ChatGPT",
                            "guidance": "",
                            "checked_at": "2026-10-27T00:00:00Z",
                            "ttl_seconds": 60,
                            "active_account": "fixture-account" if connected else None,
                            "account_label": "fixture@example.test" if connected else None,
                            "accounts": (
                                [{"id": "fixture-account", "label": "fixture@example.test"}]
                                if connected
                                else []
                            ),
                        }
                    ),
                )
            elif request.url.endswith("/api/cloud-auth/logout"):
                google_state["authenticated"] = False
                route.fulfill(status=200, content_type="application/json", body="{}")
            elif request.url.endswith("/api/cloud-auth/login"):
                google_state["authenticated"] = True
                route.fulfill(status=302, headers={"Location": "/"})
            elif request.url.endswith("/api/ai/disconnect"):
                google_state["disconnect_requests"] += 1
                google_state["connected"] = False
                route.fulfill(status=200, content_type="application/json", body="{}")
            else:
                route.continue_()

        identity_page.route("**/api/**", mock_google_identity_api)
        identity_page.goto(origin + "/", wait_until="domcontentloaded")
        google_pill = identity_page.locator(".project-google-signin")
        chatgpt_pill = identity_page.locator(".api-connection > summary")
        expect(google_pill).to_have_text("Sign out of Google")
        expect(chatgpt_pill).to_have_text("Disconnect from ChatGPT")
        google_pill.click()
        expect(google_pill).to_have_text("Sign in with Google")
        expect(chatgpt_pill).to_have_text("Connect to ChatGPT")
        expect(chatgpt_pill).to_have_attribute("aria-disabled", "true")
        assert google_state["disconnect_requests"] == 0, google_state
        google_pill.click()
        expect(google_pill).to_have_text("Sign out of Google")
        expect(chatgpt_pill).to_have_text("Disconnect from ChatGPT")
        expect(chatgpt_pill).to_have_attribute("aria-disabled", "false")
        assert google_state["disconnect_requests"] == 0, google_state
        identity_page.close()

        guest_projects = page.evaluate(
            "async () => (await (await fetch('/api/projects/recent')).json()).projects"
        )
        assert guest_projects == [], guest_projects

        select_identity(page, "member-a")
        expect(page.locator(".api-connection > summary")).to_be_visible()
        inspect_account_view(page, 1440, 900, "Regular user")
        expect(page.get_by_label("Mock funding mode")).to_have_value("personal")
        new_action = page.get_by_role("button", name="New", exact=True)
        open_action = page.get_by_role("button", name="Open", exact=True)
        expect(new_action).to_be_visible()
        expect(new_action).to_be_enabled()
        expect(open_action).to_be_visible()
        expect(open_action).to_be_enabled()
        page.get_by_role("tab", name="Recent").click()
        expect(page.get_by_text("No recent projects yet.", exact=False)).to_be_visible()
        page.get_by_role("tab", name="Samples").click()
        page.screenshot(
            path=str(SCREENSHOTS / "green-next-home-member-desktop.png"), full_page=True
        )
        page.set_viewport_size({"width": 390, "height": 844})
        page.screenshot(path=str(SCREENSHOTS / "green-next-home-member-narrow.png"), full_page=True)
        page.set_viewport_size({"width": 1440, "height": 900})
        new_action.click()
        new_dialog = page.get_by_role("dialog", name="New Project")
        expect(new_dialog).to_be_visible()
        new_dialog.get_by_role("button", name="Cancel").click()
        open_action.click()
        open_dialog = page.get_by_role("dialog", name="Open Project")
        expect(open_dialog).to_be_visible()
        open_dialog.get_by_role("button", name="Cancel").click()
        member_allowance = page.evaluate(
            "async () => (await (await fetch('/api/cloud-auth/mock/funding')).json())"
            ".allowance.remaining_usd"
        )
        assert member_allowance == 25.0, member_allowance
        created = page.evaluate(
            """async () => {
                const response = await fetch('/api/projects/create', {
                    method: 'POST', headers: {'Content-Type': 'application/json'},
                    body: JSON.stringify({title: 'T257 Member A isolation',
                        problem: 'Check owner-scoped project requests.'}),
                });
                return {status: response.status, body: await response.json()};
            }"""
        )
        assert created["status"] == 201, created
        member_project_path = created["body"]["path"]
        page.goto(origin + "/", wait_until="networkidle")
        expect(page.get_by_role("button", name="New", exact=True)).to_be_enabled()
        expect(page.get_by_role("button", name="Open", exact=True)).to_be_enabled()
        page.get_by_role("tab", name="Recent").click()
        page.get_by_text("1 project", exact=True).click()
        recent_project = page.get_by_role("button", name="T257 Member A isolation", exact=True)
        expect(recent_project).to_be_visible()
        recent_project.click()
        expect(page.locator(".project-art-header")).to_be_visible()
        expect(page.get_by_role("heading", name="T257 Member A isolation")).to_be_visible()
        page.goto(
            origin + "/project?" + urlencode({"path": member_project_path}),
            wait_until="networkidle",
        )
        expect(page.locator(".project-art-header")).to_be_visible()
        inspect_account_view(page, 1440, 900, "Regular user")
        inspect_account_view(page, 390, 844, "Regular user")
        page.screenshot(
            path=str(SCREENSHOTS / "green-next-project-member-narrow.png"), full_page=True
        )
        page.set_viewport_size({"width": 1440, "height": 900})
        page.screenshot(
            path=str(SCREENSHOTS / "green-next-project-member-desktop.png"), full_page=True
        )

        page.goto(origin + "/", wait_until="networkidle")
        identity = page.get_by_label("Mock authentication identity")
        select_identity(page, "member-b")
        expect(page.locator(".api-connection > summary")).to_be_visible()
        member_b_projects = page.evaluate(
            "async () => (await (await fetch('/api/projects/recent')).json()).projects"
        )
        assert all(item["path"] != member_project_path for item in member_b_projects), (
            member_b_projects
        )
        denied_project = page.evaluate(
            """async path => (await fetch('/api/projects/inspect?'
                + new URLSearchParams({path}))).status""",
            member_project_path,
        )
        assert denied_project in {400, 403, 404}, denied_project

        identity = page.get_by_label("Mock authentication identity")
        select_identity(page, "admin")
        expect(page.locator(".api-connection > summary")).to_be_visible()
        inspect_account_view(page, 390, 844, "Administrator")
        admin_allowance = page.evaluate(
            "async () => (await (await fetch('/api/cloud-auth/mock/funding')).json())"
            ".allowance.remaining_usd"
        )
        assert admin_allowance == member_allowance, admin_allowance
        admin_project = page.evaluate(
            """async () => {
                const response = await fetch('/api/projects/create', {
                    method: 'POST', headers: {'Content-Type': 'application/json'},
                    body: JSON.stringify({title: 'T257 Administrator visual check',
                        problem: 'Check administrator account presentation.'}),
                });
                return {status: response.status, body: await response.json()};
            }"""
        )
        assert admin_project["status"] == 201, admin_project
        page.goto(
            origin + "/project?" + urlencode({"path": admin_project["body"]["path"]}),
            wait_until="networkidle",
        )
        expect(page.locator(".api-connection > summary")).to_be_visible()
        inspect_account_view(page, 390, 844, "Administrator")

        page.goto(origin + "/", wait_until="networkidle")
        identity = page.get_by_label("Mock authentication identity")
        select_identity(page, "uninvited")
        page.set_viewport_size({"width": 390, "height": 844})
        denied_dialog = page.get_by_role("dialog", name="Request an invitation")
        expect(denied_dialog).to_be_visible()
        expect(denied_dialog).to_contain_text("couldn’t find an active SIGMA invitation")
        expect(denied_dialog).not_to_contain_text("sign in with another account")
        expect(page.locator(".project-google-signin")).to_have_text("Sign in with Google")
        expect(denied_dialog.get_by_role("link", name="Use another account")).to_have_count(0)
        denied_identity = page.evaluate(
            "async () => await (await fetch('/api/cloud-auth/status')).json()"
        )
        assert denied_identity["authenticated"] is False, denied_identity
        assert denied_identity["user"] is None, denied_identity
        denied_dialog.get_by_role("button", name="Request invitation").click()
        expect(
            denied_dialog.get_by_text("Invitation requested. We'll get back to you.")
        ).to_be_visible()
        denied_dialog.get_by_role("button", name="Close").click()
        expect(page.get_by_role("button", name="New", exact=True)).to_have_count(0)
        expect(page.get_by_role("button", name="Open", exact=True)).to_have_count(0)
        recent_tab = page.get_by_role("tab", name="Recent")
        expect(recent_tab).to_be_visible()
        recent_tab.click()
        expect(page.get_by_text("Sign in to create and", exact=False)).to_be_visible()
        page.screenshot(path=str(SCREENSHOTS / "green-next-denied-invitation.png"), full_page=True)
        denied_projects = page.evaluate(
            "async () => (await (await fetch('/api/projects/recent')).json()).projects"
        )
        assert denied_projects == [], denied_projects

        select_identity(page, "member-a")
        page.get_by_label("Mock funding mode").select_option("sponsored")
        page.get_by_label("Mock sponsorship allowance").select_option("exhausted")
        page.get_by_label("Mock provider state").select_option("connected")
        catalog = page.evaluate(
            "async () => (await (await fetch('/api/projects/samples')).json()).projects"
        )
        sample = next(project for project in catalog if project["strategy_count"] > 0)
        opened = page.evaluate(
            """async sample_id => {
                const response = await fetch('/api/projects/samples/open', {
                    method: 'POST', headers: {'Content-Type': 'application/json'},
                    body: JSON.stringify({sample_id}),
                });
                return {status: response.status, body: await response.json()};
            }""",
            sample["id"],
        )
        assert opened["status"] == 200, opened
        project = opened["body"]["project"]
        project_path = opened["body"]["path"]
        strategy_id = project["strategies"][0]["id"]

        def start_mock_research() -> dict[str, Any]:
            return page.evaluate(
                """async request => {
                    const response = await fetch('/api/projects/research-sessions/mock', {
                        method: 'POST', headers: {'Content-Type': 'application/json'},
                        body: JSON.stringify(request),
                    });
                    return {status: response.status, body: await response.json()};
                }""",
                {
                    "path": project_path,
                    "strategy_id": strategy_id,
                    "expected_project_id": project["id"],
                    "idempotency_key": str(uuid4()),
                },
            )

        exhausted = start_mock_research()
        assert exhausted["status"] == 200 and exhausted["body"]["simulated"], exhausted
        result = advance_latest_session(page, project_path)
        assert result["status"] == "failed" and "allowance exhausted" in result["message"]

        page.get_by_label("Mock sponsorship allowance").select_option("available")
        page.get_by_label("Mock provider state").select_option("unavailable")
        provider_error = start_mock_research()
        assert provider_error["status"] == 200 and provider_error["body"]["simulated"]
        result = advance_latest_session(page, project_path)
        assert result["status"] == "failed" and "unavailable" in result["message"].lower(), result

        page.get_by_label("Mock provider state").select_option("connected")
        resumable = start_mock_research()
        assert resumable["status"] == 200 and resumable["body"]["simulated"], resumable
        session_id = resumable["body"]["id"]
        progress = page.evaluate(
            """async path => {
                const response = await fetch('/api/projects/research-sessions?'
                    + new URLSearchParams({path}));
                return (await response.json()).sessions;
            }""",
            project_path,
        )
        assert next(row for row in progress if row["id"] == session_id)["status"] == "running"
        stopped = page.evaluate(
            """async request => {
                const response = await fetch(`/api/projects/research-sessions/${request.id}/control`, {
                    method: 'POST', headers: {'Content-Type': 'application/json'},
                    body: JSON.stringify({path: request.path, action: 'stop'}),
                });
                return {status: response.status, body: await response.json()};
            }""",
            {"id": session_id, "path": project_path},
        )
        assert stopped["status"] == 200 and stopped["body"]["status"] == "stopped", stopped
        page.goto(origin + "/project?" + urlencode({"path": project_path}))
        row = page.locator(f'li[data-session-id="{session_id}"]')
        resume_button = row.get_by_role("button", name="Resume", exact=True)
        expect(resume_button).to_be_visible()
        expect(row.get_by_role("button", name="Stop", exact=True)).to_have_count(0)
        scroll_before_resume = page.evaluate("window.scrollY")
        with page.expect_response(
            lambda response: response.url.endswith(f"/{session_id}/control")
        ) as control_response:
            resume_button.evaluate("element => element.click()")
        response = control_response.value
        assert response.status == 200, response.text()
        assert response.json()["status"] == "queued"
        expect(row.locator(".session-status")).to_have_text(
            re.compile(r"^(running|ended)$"), timeout=10_000
        )
        assert page.evaluate("window.scrollY") == scroll_before_resume
        resumed_record = page.evaluate(
            """async request => {
                const response = await fetch(`/api/projects/research-sessions/${request.id}?`
                    + new URLSearchParams({path: request.path}));
                return await response.json();
            }""",
            {"id": session_id, "path": project_path},
        )
        assert any(event["kind"] == "simulation.resumed" for event in resumed_record["events"])

        assert not errors, errors
        browser.close()
    print(
        "PASS local mock-auth browser: Guest, Member A/B project isolation, Administrator with "
        "no extra allowance, Uninvited invitation request, sponsored exhaustion, and "
        "provider-unavailable simulation, plus provider-free pause/resume without scroll; "
        "no provider credentials or calls."
    )


def inspect_account_view(page, width: int, height: int, _expected: str) -> None:
    page.set_viewport_size({"width": width, "height": height})
    google = page.locator(".identity-pill-stack > .project-google-signin")
    summary = page.locator(".api-connection > summary")
    expect(google).to_have_count(1)
    expect(google).to_be_visible()
    expect(summary).to_have_count(1)
    expect(summary).to_be_visible()
    assert google.inner_text() in {"Sign out of Google", "Sign in with Google"}
    assert summary.inner_text() in {"Connect to ChatGPT", "Disconnect from ChatGPT"}
    assert not any(
        role in summary.inner_text() for role in ("Guest", "Regular user", "Administrator")
    )
    gap = page.evaluate("""() => {
      const google = document.querySelector('.identity-pill-stack > .project-google-signin').getBoundingClientRect();
      const chatgpt = document.querySelector('.api-connection > summary').getBoundingClientRect();
      return {vertical: Math.round(chatgpt.top - google.bottom), alignment: Math.round(chatgpt.left - google.left)};
    }""")
    assert gap["vertical"] >= 14, f"Google and ChatGPT pills are only {gap['vertical']}px apart"
    assert abs(gap["alignment"]) <= 2, f"Stacked pills are not left-aligned: {gap}"
    expect(page.get_by_role("dialog", name="ChatGPT connection settings")).to_have_count(0)
    assert not any(
        choice in summary.inner_text()
        for choice in ("Use the same Google account", "Use a different ChatGPT account", "API key")
    )


def advance_latest_session(page, path: str) -> dict[str, Any]:
    result = page.evaluate(
        """async path => {
            let data;
            for (let attempt = 0; attempt < 3; attempt += 1) {
                const response = await fetch('/api/projects/research-sessions?'
                    + new URLSearchParams({path}));
                data = await response.json();
            }
            return data.sessions[0];
        }""",
        path,
    )
    return result


def select_identity(page, identity: str) -> None:
    with page.expect_navigation(wait_until="networkidle"):
        page.get_by_label("Mock authentication identity").select_option(identity)


if __name__ == "__main__":
    main()
