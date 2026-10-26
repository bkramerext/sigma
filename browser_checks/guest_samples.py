"""Real Chrome acceptance for the unauthenticated hosted sample workflow."""

from __future__ import annotations

import os
import socket
import subprocess
import tempfile
import time
from pathlib import Path
from tempfile import TemporaryDirectory

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
        page.on("pageerror", lambda error: failures.append(str(error)))

        def capture(response):
            if response.url.endswith("/api/projects/samples/open"):
                opened_projects.append(response.json())

        page.on("response", capture)
        page.goto(ui_url, wait_until="networkidle")
        expect(page.get_by_role("heading", name="Projects")).to_be_visible()
        expect(page.get_by_text("Explore sample projects while you’re here.")).to_be_visible()
        expect(page.get_by_role("button", name="New")).to_be_visible()
        expect(page.get_by_role("button", name="Open", exact=True)).to_be_visible()
        expect(page.get_by_role("button", name="Recent")).to_be_disabled()
        expect(page.get_by_role("button", name="Samples")).to_have_count(0)
        expect(page.get_by_role("button", name="Open Did Jesus Use Cannabis?")).to_be_visible()
        expect(page.get_by_text("Authentication required.")).to_have_count(0)

        page.get_by_role("button", name="About", exact=True).click()
        expect(page.get_by_role("dialog", name="About SIGMA")).to_be_visible()
        policy = page.get_by_role("link", name="Privacy Policy")
        policy.scroll_into_view_if_needed()
        expect(policy).to_be_visible()
        policy.click()
        expect(page.get_by_role("heading", name="SIGMA Privacy Notice")).to_be_visible()
        expect(page.get_by_role("link", name="Return to SIGMA")).to_be_visible()
        page.get_by_role("link", name="Return to SIGMA").click()

        page.get_by_role("button", name="Open Did Jesus Use Cannabis?").click()
        expect(page.get_by_role("heading", name="Did Jesus Use Cannabis? v1")).to_be_visible(
            timeout=15000
        )
        expect(page.get_by_role("button", name="Back to home").first).to_be_visible()
        assert opened_projects
        assert Path(opened_projects[-1]["path"]).is_dir()
        assert not Path(opened_projects[-1]["path"]).is_relative_to(root / "saved-projects")
        recent = page.evaluate(
            "async () => (await (await fetch('/api/projects/recent')).json()).projects"
        )
        assert recent == [], recent
        expect(page.get_by_text("Authentication required.")).to_have_count(0)
        assert not failures, failures
        assert (
            not list((root / "saved-projects").glob("*.sigma"))
            if (root / "saved-projects").exists()
            else True
        )
        browser.close()


if __name__ == "__main__":
    main()
