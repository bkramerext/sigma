"""Real Chrome persistent-disk workflow against SIGMA's actual local API.

Auth uses the explicitly identified isolated X-Test-* identity adapter from
tests/cloud_workspace_test_app.py. No Google OAuth or inference provider is used.
"""

from __future__ import annotations

import hashlib
import os
import socket
import subprocess
import sys
import time
from pathlib import Path
from tempfile import TemporaryDirectory

import httpx
from playwright.sync_api import expect, sync_playwright

ROOT = Path(__file__).resolve().parents[1]
API = ""
UI = ""
CHROME = os.environ.get(
    "SIGMA_BROWSER_EXECUTABLE", "/Applications/Google Chrome.app/Contents/MacOS/Google Chrome"
)


def port_free(port: int) -> bool:
    with socket.socket() as sock:
        try:
            sock.bind(("127.0.0.1", port))
        except OSError:
            return False
    return True


def free_port() -> int:
    with socket.socket() as sock:
        sock.bind(("127.0.0.1", 0))
        return int(sock.getsockname()[1])


def wait_ready(url: str, process: subprocess.Popen, log: Path) -> None:
    deadline = time.monotonic() + 25
    while time.monotonic() < deadline and process.poll() is None:
        try:
            if httpx.get(url, timeout=0.25).status_code == 200:
                return
        except httpx.HTTPError:
            time.sleep(0.1)
    raise RuntimeError(f"Local test service failed to start:\n{log.read_text(errors='replace')}")


def main() -> None:
    global API, UI
    if not Path(CHROME).is_file():
        raise RuntimeError(f"Real Chrome executable is unavailable: {CHROME}")
    api_port, ui_port = free_port(), free_port()
    API = f"http://127.0.0.1:{api_port}"
    UI = f"http://127.0.0.1:{ui_port}"
    sample = ROOT / "samples/nonconsecutive-subset-sums/project.json"
    original_hash = hashlib.sha256(sample.read_bytes()).hexdigest()
    with TemporaryDirectory(prefix="sigma-t100-browser-") as temporary:
        base = Path(temporary)
        base.chmod(0o700)
        disk = base / "persistent-disk"
        disk.mkdir(mode=0o700)
        env = os.environ.copy()
        env.update(
            {
                "SIGMA_STORAGE_BACKEND": "persistent_disk",
                "SIGMA_STORAGE_ROOT": str(disk),
                "SIGMA_TEST_BROWSER_ORIGIN": UI,
                "SIGMA_CLOUD_AUTH_ENABLED": "true",
                "SIGMA_CLOUD_PUBLIC_ORIGIN": "https://sigma.test",
                "SIGMA_CLOUD_BOOTSTRAP_ADMIN_EMAIL": "admin@example.test",
                "SIGMA_CLOUD_ADMIN_CONTACT_EMAIL": "admin@example.test",
                "GOOGLE_OIDC_CLIENT_ID": "fixture.apps.googleusercontent.com",
                "GOOGLE_OIDC_CLIENT_SECRET": "fixture-secret-no-network",
                "SIGMA_CLOUD_OPENAI_API_KEY": "deterministic-no-inference-fixture",
                "SIGMA_CLOUD_GLOBAL_SPEND_CEILING_USD": "1.00",
                "SIGMA_CLOUD_USER_SPEND_CEILING_USD": "0.25",
                "SIGMA_CLOUD_USER_MAX_CONCURRENT": "1",
                "SIGMA_CLOUD_GLOBAL_MAX_CONCURRENT": "2",
                "SIGMA_CLOUD_USER_MAX_QUEUED": "2",
                "SIGMA_CLOUD_GLOBAL_MAX_QUEUED": "4",
                "SIGMA_CLOUD_USER_TOKEN_BUDGET": "1000000",
                "PYTHONPATH": os.pathsep.join(
                    (str(ROOT / "tests"), str(ROOT / "src"), os.environ.get("PYTHONPATH", ""))
                ),
            }
        )
        api_log = base / "api.log"
        ui_log = base / "ui.log"

        def start_api() -> subprocess.Popen:
            with api_log.open("a") as output:
                process = subprocess.Popen(
                    [
                        sys.executable,
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
                    env=env,
                    stdout=output,
                    stderr=subprocess.STDOUT,
                )
            wait_ready(API + "/api/ui-instance", process, api_log)
            return process

        api_process = start_api()
        ui_process = None
        try:
            with ui_log.open("w") as output:
                ui_process = subprocess.Popen(
                    [
                        "npm",
                        "--prefix",
                        "frontend",
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
                    stdout=output,
                    stderr=subprocess.STDOUT,
                )
            wait_ready(UI, ui_process, ui_log)
            with sync_playwright() as playwright:
                browser = playwright.chromium.launch(executable_path=CHROME, headless=True)
                context = browser.new_context(viewport={"width": 1440, "height": 1000})
                page = context.new_page()
                page_errors: list[str] = []
                page.on("pageerror", lambda error: page_errors.append(str(error)))
                subject = "t100-fixture-subject-a"

                def forward(route):
                    if route.request.url.endswith("/api/cloud-auth/status"):
                        route.fulfill(
                            status=200,
                            json={
                                "enabled": True,
                                "ready": True,
                                "authenticated": True,
                                "target": "hosted",
                                "user": {"email": "fixture-a@example.test", "role": "member"},
                                "admin_contact_email": "admin@example.test",
                                "local_setup_missing": [],
                            },
                        )
                        return
                    headers = {
                        **route.request.headers,
                        "x-test-subject": subject,
                        "x-test-email": f"{subject}@example.test",
                    }
                    response = route.fetch(url=route.request.url.replace(UI, API), headers=headers)
                    route.fulfill(response=response)

                page.route("**/api/**", forward)
                page.goto(UI)
                page.get_by_role("tabpanel", name="Samples").get_by_role(
                    "button", name="Open Nonconsecutive Subset Sums Modulo 3", exact=True
                ).click()
                expect(page.locator(".project-pane-title-line .current-project")).to_contain_text(
                    "Nonconsecutive Subset Sums Modulo 3 v1"
                )
                path = page.evaluate("new URL(location.href).searchParams.get('path')")
                assert path and str(disk / "workspaces") in path
                source_view = page.request.get(
                    API + "/api/projects/inspect",
                    params={"path": path},
                    headers={"x-test-subject": subject, "x-test-email": f"{subject}@example.test"},
                ).json()
                project_id = source_view["project"]["id"]
                source_strategy_ids = [item["id"] for item in source_view["project"]["strategies"]]

                page.get_by_role(
                    "button", name=re.compile("Edit project title and description:")
                ).click()
                page.get_by_label("Project title", exact=True).fill("T100 Persistent Sample Copy")
                page.locator("#text-editor-project-project").fill(
                    "Edited details survive reload and disk restore."
                )
                page.locator(".project-title-edit-form").get_by_role(
                    "button", name="Save", exact=True
                ).click()
                expect(page.locator(".project-pane-title-line .current-project")).to_have_text(
                    "T100 Persistent Sample Copy"
                )

                strategy_button = page.locator("li[data-strategy-id]").first.get_by_role(
                    "button", name=re.compile("Edit strategy title and description:")
                )
                strategy_button.click()
                title_input = page.get_by_label("Strategy title", exact=True)
                title_input.fill("T100 Durable Strategy")
                page.locator(".strategy-rename-form").get_by_role(
                    "button", name="Save", exact=True
                ).click()
                expect(page.locator("li[data-strategy-id]").first).to_contain_text(
                    "T100 Durable Strategy"
                )
                edited_view = page.request.get(
                    API + "/api/projects/inspect",
                    params={"path": path},
                    headers={"x-test-subject": subject},
                ).json()["project"]
                assert edited_view["id"] == project_id
                assert edited_view["problem"] == "Edited details survive reload and disk restore."
                assert [item["id"] for item in edited_view["strategies"]] == source_strategy_ids

                page.get_by_role("button", name="Back to home", exact=True).click()
                recent = page.get_by_role("tabpanel", name="Recent")
                expect(
                    recent.get_by_role("button", name="T100 Persistent Sample Copy", exact=True)
                ).to_be_visible()
                page.reload()
                page.goto(UI)
                recent_tab = page.get_by_role("tab", name="Recent", exact=True)
                if recent_tab.get_attribute("aria-selected") != "true":
                    recent_tab.click()
                recent = page.get_by_role("tabpanel", name="Recent")
                recent.get_by_role("button", name="T100 Persistent Sample Copy", exact=True).click()
                expect(page.locator(".project-pane-title-line .current-project")).to_have_text(
                    "T100 Persistent Sample Copy"
                )
                expect(page.locator("li[data-strategy-id]").first).to_contain_text(
                    "T100 Durable Strategy"
                )

                api_process.terminate()
                api_process.wait(timeout=10)
                api_process = start_api()
                page.goto(UI)
                recent_tab = page.get_by_role("tab", name="Recent", exact=True)
                if recent_tab.get_attribute("aria-selected") != "true":
                    recent_tab.click()
                page.get_by_role("tabpanel", name="Recent").get_by_role(
                    "button", name="T100 Persistent Sample Copy", exact=True
                ).click()
                expect(page.locator(".project-pane-title-line .current-project")).to_have_text(
                    "T100 Persistent Sample Copy"
                )
                expect(page.locator("li[data-strategy-id]").first).to_contain_text(
                    "T100 Durable Strategy"
                )
                evidence_dir = ROOT / "docs/evaluations/t100"
                evidence_dir.mkdir(parents=True, exist_ok=True)
                page.screenshot(
                    path=str(evidence_dir / "persistent-disk-chrome.png"), full_page=True
                )

                outsider = "t100-fixture-subject-b"
                denied = page.request.get(
                    API + "/api/projects/inspect",
                    params={"path": path},
                    headers={"x-test-subject": outsider, "x-test-email": "b@example.test"},
                )
                assert denied.status == 404, denied.text()
                assert hashlib.sha256(sample.read_bytes()).hexdigest() == original_hash
                assert not page_errors, page_errors
                browser.close()
        finally:
            if ui_process and ui_process.poll() is None:
                ui_process.terminate()
                ui_process.wait(timeout=10)
            if api_process and api_process.poll() is None:
                api_process.terminate()
                api_process.wait(timeout=10)
    print(
        "PASS real Chrome persistent_disk: stock sample copied, project details and strategy edited, save/reload/reopen, backend restart, Recent identity, other subject denied, stock sample unchanged; fixture auth only; no inference calls"
    )


if __name__ == "__main__":
    import re

    main()
