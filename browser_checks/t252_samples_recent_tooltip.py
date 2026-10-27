"""Real Chrome regression: Samples/Recent clicks do not trigger hover text."""

from __future__ import annotations

import os
import socket
import subprocess
import sys
import tempfile
import time
from pathlib import Path

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
    raise RuntimeError(f"Browser fixture failed to start:\n{log.read_text(errors='replace')}")


def main() -> None:
    api_port, ui_port = free_port(), free_port()
    while api_port == ui_port:
        ui_port = free_port()
    api_url = f"http://127.0.0.1:{api_port}"
    ui_url = f"http://127.0.0.1:{ui_port}"
    with tempfile.TemporaryDirectory(prefix="sigma-t252-browser-") as temporary:
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
                        sys.executable,
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
                        "run",
                        "dev",
                        "--",
                        "--host",
                        "127.0.0.1",
                        "--port",
                        str(ui_port),
                        "--strictPort",
                    ],
                    cwd=ROOT / "frontend",
                    env=env,
                    stdout=ui_output,
                    stderr=subprocess.STDOUT,
                )
                wait_for(ui_url, ui_process, ui_log)
                exercise(ui_url)
            finally:
                for process in (ui_process, api_process):
                    if process is not None:
                        process.terminate()
                        process.wait(timeout=10)


def exercise(ui_url: str) -> None:
    with sync_playwright() as playwright:
        browser = playwright.chromium.launch(executable_path=CHROME, headless=True)
        page = browser.new_page(viewport={"width": 1280, "height": 850})
        errors: list[str] = []
        page.on("pageerror", lambda error: errors.append(str(error)))
        page.goto(ui_url, wait_until="networkidle")
        samples = page.get_by_role("tab", name="Samples", exact=True)
        recent = page.get_by_role("tab", name="Recent", exact=True)
        tooltip = page.get_by_role("tooltip")
        expect(samples).to_have_attribute("aria-selected", "true")
        expect(tooltip).to_have_count(0)

        recent.click()
        expect(recent).to_have_attribute("aria-selected", "true")
        expect(page.locator(".guest-recent-message")).to_be_visible()
        page.wait_for_timeout(600)
        expect(tooltip).to_have_count(0)

        samples.click()
        expect(samples).to_have_attribute("aria-selected", "true")
        expect(page.locator("#samples-panel")).to_be_visible()
        page.wait_for_timeout(600)
        expect(tooltip).to_have_count(0)

        recent.hover()
        expect(tooltip).to_have_text("Sign in to save your projects.", timeout=3000)
        page.mouse.move(10, 10)
        expect(tooltip).to_have_count(0)

        samples.hover()
        expect(tooltip).to_have_text(
            "Show sample projects. Click again to collapse or expand all.", timeout=3000
        )
        page.mouse.move(10, 10)
        expect(tooltip).to_have_count(0)
        assert not errors, errors
        browser.close()


if __name__ == "__main__":
    main()

print(
    "PASS real Chrome: Samples/Recent switch on click without tooltips; hover tooltips remain available."
)
