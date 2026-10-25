"""Self-starting real-Chrome Google sign-in acceptance using local fixtures.

The UI and API run against temporary storage. Google redirects/status are
deterministic browser fixtures; protected project requests reach the real API
through tests/cloud_workspace_test_app.py, whose identity headers are not
accepted by the production app.
"""

from __future__ import annotations

import json
import os
import socket
import subprocess
import time
from pathlib import Path
from tempfile import TemporaryDirectory
from urllib.parse import urlencode
from uuid import uuid4

import httpx
from playwright.sync_api import expect, sync_playwright

ROOT = Path(__file__).resolve().parents[1]
CHROME = os.environ.get(
    "SIGMA_BROWSER_EXECUTABLE",
    "/Applications/Google Chrome.app/Contents/MacOS/Google Chrome",
)
ACCOUNTS = {
    "A": {"email": "member-a@example.test", "subject": "t131-member-a"},
    "B": {"email": "member-b@example.test", "subject": "t131-member-b"},
    "denied": {"email": "denied@example.test", "subject": "t131-denied"},
}


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
    raise RuntimeError(f"Fixture server failed to start:\n{log.read_text(errors='replace')}")


def main() -> None:
    api_port, ui_port = free_port(), free_port()
    while ui_port == api_port:
        ui_port = free_port()
    api_url = f"http://127.0.0.1:{api_port}"
    ui_url = f"http://127.0.0.1:{ui_port}"
    api_process = ui_process = None

    with TemporaryDirectory(prefix="sigma-t131-google-browser-") as temporary:
        root = Path(temporary)
        os.chmod(root, 0o700)
        environment = os.environ.copy()
        environment.update(
            {
                "SIGMA_CLOUD_AUTH_ENABLED": "true",
                "SIGMA_CLOUD_PUBLIC_ORIGIN": ui_url,
                "SIGMA_TEST_BROWSER_ORIGIN": ui_url,
                "SIGMA_CLOUD_WORKSPACES_ROOT": str(root / "workspaces"),
                "SIGMA_PROJECTS_ROOT": str(root / "local-projects"),
                "SIGMA_STATE_DIR": str(root / "local-state"),
                "SIGMA_API_TARGET": api_url,
                "PYTHONPATH": os.pathsep.join(
                    (str(ROOT / "tests"), str(ROOT / "src"), os.environ.get("PYTHONPATH", ""))
                ),
            }
        )
        api_log, ui_log = root / "api.log", root / "ui.log"
        with api_log.open("w") as api_output, ui_log.open("w") as ui_output:
            api_process = subprocess.Popen(
                [
                    os.environ.get("SIGMA_PYTHON", str(ROOT / ".venv/bin/python")),
                    "-m",
                    "uvicorn",
                    "cloud_workspace_test_app:app",
                    "--host",
                    "127.0.0.1",
                    "--port",
                    str(api_port),
                    "--log-level",
                    "error",
                ],
                cwd=ROOT,
                env=environment,
                stdout=api_output,
                stderr=subprocess.STDOUT,
            )
            try:
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
                    env=environment,
                    stdout=ui_output,
                    stderr=subprocess.STDOUT,
                )
                wait_for(ui_url, ui_process, ui_log)
                exercise_browser(api_url, ui_url)
            finally:
                for process in (ui_process, api_process):
                    if process is not None:
                        process.terminate()
                        process.wait(timeout=10)


def exercise_browser(api_url: str, ui_url: str) -> None:
    identity: dict[str, str] | None = None
    denied_email: str | None = None
    next_login = "A"
    login_attempts: list[str] = []
    budget = {
        "allowance_usd": 2.0,
        "estimated_usage_usd": 2.0,
        "held_usd": 0.0,
        "reserved_and_estimated_usd": 2.0,
        "remaining_usd": 0.0,
        "unknown_provider_attempts": 0,
    }

    with sync_playwright() as playwright:
        browser = playwright.chromium.launch(executable_path=CHROME, headless=True)
        context = browser.new_context(viewport={"width": 1280, "height": 800})
        page = context.new_page()
        errors: list[str] = []
        page.on("pageerror", lambda error: errors.append(str(error)))

        def headers_for(principal: dict[str, str] | None) -> dict[str, str]:
            headers = {"Origin": ui_url}
            if principal:
                headers.update(
                    {
                        "X-Test-Subject": principal["subject"],
                        "X-Test-Email": principal["email"],
                    }
                )
            return headers

        def set_identity(principal: dict[str, str] | None) -> None:
            nonlocal identity
            identity = principal

        def forward_api(route) -> None:
            route.fulfill(
                response=route.fetch(
                    url=route.request.url.replace(ui_url, api_url),
                    headers={**route.request.headers, **headers_for(identity)},
                )
            )

        def auth_status(route) -> None:
            route.fulfill(
                status=200,
                content_type="application/json",
                body=json.dumps(
                    {
                        "target": "local",
                        "enabled": True,
                        "ready": True,
                        "authenticated": identity is not None,
                        "user": (
                            {"email": identity["email"], "role": "member"} if identity else None
                        ),
                        "admin_contact_email": None,
                    }
                ),
            )

        def denied_status(route) -> None:
            if denied_email:
                route.fulfill(
                    status=200,
                    content_type="application/json",
                    body=json.dumps({"email": denied_email}),
                )
            else:
                route.fulfill(status=404, content_type="application/json", body="{}")

        def begin_login(route) -> None:
            nonlocal denied_email, next_login
            account = next_login
            next_login = "B" if account == "A" else "denied"
            login_attempts.append(account)
            if account == "denied":
                set_identity(None)
                denied_email = ACCOUNTS[account]["email"]
                location = ui_url + "/?access=denied"
            else:
                denied_email = None
                set_identity(ACCOUNTS[account])
                location = ui_url + "/"
            route.fulfill(status=302, headers={"Location": location})

        def sign_out(route) -> None:
            nonlocal denied_email
            set_identity(None)
            denied_email = None
            route.fulfill(status=200, content_type="application/json", body="{}")

        page.route("**/api/**", forward_api)
        page.route("**/api/cloud-auth/status", auth_status)
        page.route("**/api/cloud-auth/denied", denied_status)
        page.route("**/api/cloud-auth/login", begin_login)
        page.route("**/api/cloud-auth/logout", sign_out)
        page.route(
            "**/api/cloud-research/budget",
            lambda route: route.fulfill(
                status=200,
                content_type="application/json",
                headers={"Cache-Control": "no-store"},
                body=json.dumps(budget),
            ),
        )

        def api_request(method: str, path: str, principal: dict[str, str] | None = None, **kwargs):
            return httpx.request(
                method,
                api_url + path,
                headers=headers_for(principal),
                timeout=10,
                **kwargs,
            )

        try:
            # Anonymous and rejected/forged test identities cannot read private API data.
            assert api_request("GET", "/api/projects/recent").status_code == 401
            # The isolated adapter accepts test identities, so rejected behavior is
            # represented by an explicitly revoked identity header, which fails closed.
            rejected = httpx.get(
                api_url + "/api/projects/recent",
                headers=headers_for(ACCOUNTS["denied"]) | {"X-Test-Revoked": "true"},
                timeout=10,
            )
            assert rejected.status_code == 401, rejected.text

            page.goto(ui_url + "/", wait_until="networkidle")
            expect(
                page.get_by_role(
                    "heading", name="Sign in with approved Gmail account to access projects."
                )
            ).to_be_visible()
            expect(page.get_by_role("link", name="Administrator Settings")).to_have_count(0)
            page.get_by_role("button", name="Sign in with Google").click()
            account = page.get_by_role("dialog", name="Connect your Google account")
            expect(account.locator(".google-account-target")).to_have_count(0)
            account.get_by_role("link", name="Sign in with Google", exact=True).click()
            expect(page).to_have_url(ui_url + "/")
            expect(page.get_by_role("heading", name="Projects")).to_be_visible()
            assert login_attempts == ["A"]

            # Reload preserves the deterministic fixture principal; protected project
            # creation/recent requests still pass through the real API and workspace code.
            page.reload(wait_until="networkidle")
            expect(page.get_by_role("heading", name="Projects")).to_be_visible()
            created = api_request(
                "POST",
                "/api/projects/create",
                identity,
                json={
                    "title": f"T131 browser private A {uuid4().hex[:8]}",
                    "problem": "Deterministic OAuth browser fixture.",
                },
            )
            assert created.status_code == 201, created.text
            project_a = created.json()
            assert any(
                row["path"] == project_a["path"]
                for row in api_request("GET", "/api/projects/recent", identity).json()["projects"]
            )

            # Preserve the existing header/account acceptance while checking layout.
            page.goto(
                ui_url + "/project?" + urlencode({"path": project_a["path"]}),
                wait_until="networkidle",
            )
            controls = page.locator(".project-art-header .header-controls")
            google = controls.locator(".project-google-signin")
            expect(google).to_have_text("Google account connected")
            expect(google).not_to_contain_text(ACCOUNTS["A"]["email"])
            model = controls.locator(".project-model-pill")
            thinking = controls.locator(".project-thinking-pill")
            difficulty = controls.locator(".project-difficulty-badge")
            chatgpt = controls.locator(".project-chatgpt-signin > summary")
            for control in (model, thinking, difficulty, google, chatgpt):
                expect(control).to_be_visible()
            for width, height in ((1280, 800), (390, 844), (320, 700)):
                page.set_viewport_size({"width": width, "height": height})
                expect(google).to_be_visible()
                assert page.evaluate("document.documentElement.scrollWidth <= innerWidth"), width

            # Account switch is another fixture redirect; the API must expose only B's
            # workspace after the browser identity changes and the app reloads.
            google.click()
            account = page.get_by_role("dialog", name="Google account")
            expect(account.get_by_text(ACCOUNTS["A"]["email"], exact=True)).to_be_visible()
            page.evaluate("window.scrollTo(0, 0)")
            expect(account.get_by_role("button", name="Sign out", exact=True)).to_be_visible()
            account.get_by_role("button", name="Sign out", exact=True).click()
            expect(page).to_have_url(ui_url + "/")
            expect(
                page.get_by_role(
                    "heading", name="Sign in with approved Gmail account to access projects."
                )
            ).to_be_visible()
            assert api_request("GET", "/api/projects/recent").status_code == 401

            page.get_by_role("button", name="Sign in with Google").click()
            account = page.get_by_role("dialog", name="Connect your Google account")
            account.get_by_role("link", name="Sign in with Google", exact=True).click()
            expect(page.get_by_role("heading", name="Projects")).to_be_visible()
            assert login_attempts == ["A", "B"]
            page.reload(wait_until="networkidle")
            expect(page.get_by_role("heading", name="Projects")).to_be_visible()
            assert api_request("GET", "/api/projects/recent", identity).json()["projects"] == []
            project_b = api_request(
                "POST",
                "/api/projects/create",
                identity,
                json={
                    "title": f"T131 browser private B {uuid4().hex[:8]}",
                    "problem": "Account B fixture.",
                },
            )
            assert project_b.status_code == 201, project_b.text
            assert (
                api_request("GET", "/api/projects/recent", ACCOUNTS["A"]).json()["projects"][0][
                    "path"
                ]
                == project_a["path"]
            )
            assert (
                api_request("GET", "/api/projects/recent", ACCOUNTS["B"]).json()["projects"][0][
                    "path"
                ]
                == project_b.json()["path"]
            )

            # A valid but ungranted fixture identity returns the rejected-access UI
            # and still has no private API principal.
            page.get_by_role("button", name="Google account connected").click()
            account = page.get_by_role("dialog", name="Google account")
            account.get_by_role("button", name="Sign out", exact=True).click()
            page.get_by_role("button", name="Sign in with Google").click()
            account = page.get_by_role("dialog", name="Connect your Google account")
            account.get_by_role("link", name="Sign in with Google", exact=True).click()
            expect(page.get_by_role("heading", name="Access not yet granted")).to_be_visible()
            expect(page.get_by_text(ACCOUNTS["denied"]["email"], exact=True)).to_be_visible()
            assert api_request("GET", "/api/projects/recent").status_code == 401
            assert login_attempts == ["A", "B", "denied"]
            assert not errors, errors
        finally:
            context.close()
            browser.close()

    print(
        "PASS real Chrome deterministic local sign-in, reload persistence, logout, "
        "anonymous/revoked denial, rejected identity, account switching and isolated project workspaces; "
        "no external Google OAuth or provider calls"
    )


if __name__ == "__main__":
    main()
