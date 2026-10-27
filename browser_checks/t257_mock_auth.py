"""Real-Chrome acceptance for the local T257 mock-auth walkthrough."""

from __future__ import annotations

import os
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


def main() -> None:
    temporary_parent = Path("/private/tmp") if Path("/private/tmp").is_dir() else None
    with tempfile.TemporaryDirectory(prefix="sigma-t257-mock-", dir=temporary_parent) as value:
        root = Path(value)
        for name in ("auth", "workspaces", "projects", "state"):
            (root / name).mkdir(mode=0o700)
        environment = os.environ.copy()
        environment.update(
            {
                "SIGMA_CLOUD_AUTH_ENABLED": "true",
                "SIGMA_CLOUD_AUTH_LOCAL": "true",
                "SIGMA_MOCK_AUTH": "1",
                "SIGMA_CLOUD_PUBLIC_ORIGIN": "http://127.0.0.1:5173",
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
                    "8000",
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
                    "5173",
                    "--strictPort",
                ],
                cwd=FRONTEND,
                env=environment,
                stdout=ui_output,
                stderr=subprocess.STDOUT,
            )
            try:
                wait_for(
                    "http://127.0.0.1:8000/api/ui-instance",
                    (api, ui),
                    (api_log, ui_log),
                )
                wait_for("http://127.0.0.1:5173/", (api, ui), (api_log, ui_log))
                exercise_browser()
            finally:
                for process in (ui, api):
                    if process.poll() is None:
                        process.terminate()
                        try:
                            process.wait(timeout=5)
                        except subprocess.TimeoutExpired:
                            process.kill()
                            process.wait(timeout=5)


def exercise_browser() -> None:
    with sync_playwright() as playwright:
        browser = playwright.chromium.launch(executable_path=CHROME, headless=True)
        page = browser.new_page(viewport={"width": 1440, "height": 900})
        errors: list[str] = []
        page.on("pageerror", lambda error: errors.append(str(error)))
        page.goto("http://127.0.0.1:5173/", wait_until="networkidle")
        identity = page.get_by_label("Mock authentication identity")
        expect(identity).to_be_visible()
        expect(page.locator(".api-connection > summary")).to_have_count(1)
        expect(page.locator(".api-connection > summary")).to_contain_text("Guest")
        inspect_account_view(page, 1440, 900, "Guest · Explore SIGMA")
        inspect_account_view(page, 390, 844, "Guest · Explore SIGMA")
        guest_projects = page.evaluate(
            "async () => (await (await fetch('/api/projects/recent')).json()).projects"
        )
        assert guest_projects == [], guest_projects

        select_identity(page, "member-a")
        expect(page.locator(".account-model-status > summary")).to_contain_text("Regular user")
        inspect_account_view(page, 1440, 900, "Regular user")
        expect(page.get_by_label("Mock funding mode")).to_have_value("personal")
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
        page.goto(
            "http://127.0.0.1:5173/project?" + urlencode({"path": member_project_path}),
            wait_until="networkidle",
        )
        expect(page.locator(".project-art-header")).to_be_visible()
        inspect_account_view(page, 1440, 900, "Regular user")
        inspect_account_view(page, 390, 844, "Regular user")

        page.goto("http://127.0.0.1:5173/", wait_until="networkidle")
        identity = page.get_by_label("Mock authentication identity")
        select_identity(page, "member-b")
        expect(page.locator(".account-model-status > summary")).to_contain_text("Regular user")
        member_b_projects = page.evaluate(
            "async () => (await (await fetch('/api/projects/recent')).json()).projects"
        )
        assert all(item["path"] != member_project_path for item in member_b_projects)
        denied_project = page.evaluate(
            """async path => (await fetch('/api/projects/inspect?'
                + new URLSearchParams({path}))).status""",
            member_project_path,
        )
        assert denied_project in {400, 403, 404}, denied_project

        identity = page.get_by_label("Mock authentication identity")
        select_identity(page, "admin")
        expect(page.locator(".account-model-status > summary")).to_contain_text("Administrator")
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
            "http://127.0.0.1:5173/project?" + urlencode({"path": admin_project["body"]["path"]}),
            wait_until="networkidle",
        )
        expect(page.locator(".account-model-status > summary")).to_contain_text("Administrator")
        inspect_account_view(page, 390, 844, "Administrator")

        page.goto("http://127.0.0.1:5173/", wait_until="networkidle")
        identity = page.get_by_label("Mock authentication identity")
        select_identity(page, "uninvited")
        page.set_viewport_size({"width": 390, "height": 844})
        page.locator(".api-connection > summary").click()
        denied_dialog = page.get_by_role("dialog")
        expect(denied_dialog).to_contain_text("Access is not granted")
        assert_dialog_layout(page)
        denied_projects = page.evaluate(
            "async () => (await (await fetch('/api/projects/recent')).json()).projects"
        )
        assert denied_projects == [], denied_projects
        denied_dialog.get_by_role("button", name="Request invitation").click()
        expect(
            denied_dialog.get_by_text("Invitation requested. We'll get back to you.")
        ).to_be_visible()

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
        assert result["status"] == "failed" and "provider unavailable" in result["message"]

        assert not errors, errors
        browser.close()
    print(
        "PASS local mock-auth browser: Guest, Member A/B project isolation, Administrator with "
        "no extra allowance, Uninvited invitation request, sponsored exhaustion, and "
        "provider-unavailable simulation; no provider credentials or calls."
    )


def assert_dialog_layout(page) -> None:
    dialog = page.get_by_role("dialog", name="Account and model settings")
    expect(dialog).to_be_visible()
    page.wait_for_function(
        """() => {
            const dialog = document.querySelector('.connection-details[role="dialog"]');
            if (!dialog) return false;
            const rect = dialog.getBoundingClientRect();
            return rect.width > 0 && rect.height > 0 && rect.left >= 0
                && rect.right <= innerWidth && rect.top >= 0 && rect.bottom <= innerHeight;
        }"""
    )
    overflow = page.evaluate(
        """() => ({
            viewport: innerWidth,
            document: document.documentElement.scrollWidth,
            offenders: Array.from(document.querySelectorAll('body *'))
                .map(element => ({
                    selector: `${element.tagName.toLowerCase()}${element.className && typeof element.className === 'string' ? '.' + element.className.trim().replace(/\\s+/g, '.') : ''}`,
                    left: Math.round(element.getBoundingClientRect().left),
                    right: Math.round(element.getBoundingClientRect().right),
                }))
                .filter(element => element.right > innerWidth + 1 || element.left < -1)
                .slice(0, 12),
        })"""
    )
    assert overflow["document"] <= overflow["viewport"], overflow
    page.wait_for_function(
        """() => {
            const dialog = document.querySelector('.connection-details[role="dialog"]');
            return !!dialog && dialog.contains(document.activeElement);
        }"""
    )
    relation = page.evaluate(
        """() => {
            const trigger = document.querySelector('.api-connection > summary').getBoundingClientRect();
            const dialog = document.querySelector('.connection-details[role="dialog"]').getBoundingClientRect();
            return {triggerTop: trigger.top, triggerBottom: trigger.bottom,
                dialogTop: dialog.top, dialogBottom: dialog.bottom};
        }"""
    )
    below = relation["dialogTop"] >= relation["triggerBottom"] + 4
    above = relation["dialogBottom"] <= relation["triggerTop"] - 4
    assert below or above, f"account dialog overlaps its pill: {relation}"


def inspect_account_view(page, width: int, height: int, expected: str) -> None:
    page.set_viewport_size({"width": width, "height": height})
    summary = page.locator(".api-connection > summary")
    expect(summary).to_have_count(1)
    summary.click()
    dialog = page.get_by_role("dialog", name="Account and model settings")
    expect(dialog).to_contain_text(expected)
    assert_dialog_layout(page)
    page.keyboard.press("Escape")
    expect(dialog).to_have_count(0)
    page.wait_for_function(
        "document.activeElement === document.querySelector('.api-connection > summary')"
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
