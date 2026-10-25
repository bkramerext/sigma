"""Real Chrome sessions over the production API with deterministic principals."""

import json
import os
import socket
import subprocess
import time
from pathlib import Path
from tempfile import TemporaryDirectory

import httpx
from playwright.sync_api import expect, sync_playwright

ROOT = Path(__file__).resolve().parents[1]


def free_port() -> int:
    with socket.socket() as sock:
        sock.bind(("127.0.0.1", 0))
        return int(sock.getsockname()[1])


def wait_for(url: str, process: subprocess.Popen, log: Path) -> None:
    deadline = time.monotonic() + 20
    while time.monotonic() < deadline and process.poll() is None:
        try:
            if httpx.get(url, timeout=0.5).status_code < 500:
                return
        except httpx.HTTPError:
            time.sleep(0.1)
    raise RuntimeError(f"Fixture server failed to start:\n{log.read_text(errors='replace')}")


def main() -> None:
    api_port, ui_port = free_port(), free_port()
    api_url = f"http://127.0.0.1:{api_port}"
    ui_url = f"http://127.0.0.1:{ui_port}"
    api_process = ui_process = None
    with TemporaryDirectory(prefix="sigma-t22-browser-") as temporary:
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
        api_log = root / "api.log"
        ui_log = root / "ui.log"
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
                wait_for(f"{api_url}/api/ui-instance", api_process, api_log)
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

                with sync_playwright() as playwright:
                    browser = playwright.chromium.launch(
                        executable_path=os.environ.get(
                            "SIGMA_BROWSER_EXECUTABLE",
                            "/Applications/Google Chrome.app/Contents/MacOS/Google Chrome",
                        ),
                        headless=True,
                    )
                    try:
                        contexts = []
                        pages = []
                        for subject, email in (
                            ("subject-a", "a@example.test"),
                            ("subject-b", "b@example.test"),
                        ):
                            context = browser.new_context(
                                extra_http_headers={
                                    "X-Test-Subject": subject,
                                    "X-Test-Email": email,
                                },
                                viewport={"width": 1280, "height": 850},
                            )
                            context.route(
                                "**/api/cloud-auth/status",
                                lambda route, _request, user=email: route.fulfill(
                                    status=200,
                                    content_type="application/json",
                                    body=json.dumps(
                                        {
                                            "enabled": True,
                                            "ready": True,
                                            "authenticated": True,
                                            "user": {"email": user, "role": "member"},
                                            "admin_contact_email": None,
                                        }
                                    ),
                                ),
                            )
                            page = context.new_page()
                            page.goto(ui_url, wait_until="networkidle")
                            expect(page.get_by_role("heading", name="Projects")).to_be_visible()
                            contexts.append(context)
                            pages.append(page)

                        async_create = """async title => {
                          const response = await fetch('/api/projects/create', {
                            method: 'POST', headers: {'Content-Type':'application/json'},
                            body: JSON.stringify({title, problem: 'Private test question'})
                          });
                          return {status: response.status, body: await response.json()};
                        }"""
                        created = []
                        for page, title in zip(pages, ("Browser A private", "Browser B private")):
                            result = page.evaluate(async_create, title)
                            assert result["status"] == 201, result
                            created.append(result["body"])
                            page.reload(wait_until="networkidle")
                            page.get_by_role("tab", name="Recent").click()
                            page.locator(".recent-type-group summary").click()
                            expect(page.get_by_text(title, exact=True)).to_be_visible()

                        page_a, page_b = pages
                        expect(page_a.get_by_text("Browser B private", exact=True)).to_have_count(0)
                        expect(page_b.get_by_text("Browser A private", exact=True)).to_have_count(0)
                        cross = page_a.evaluate(
                            """async path => {
                              const response = await fetch('/api/projects/inspect?path=' + encodeURIComponent(path));
                              return {status: response.status, body: await response.json()};
                            }""",
                            created[1]["path"],
                        )
                        assert cross == {
                            "status": 404,
                            "body": {"error": "Project not found or access denied."},
                        }, cross
                        assert Path(created[0]["path"]).parent != Path(created[1]["path"]).parent
                        for width in (1280, 390):
                            page_a.set_viewport_size({"width": width, "height": 850})
                            assert page_a.evaluate(
                                "document.documentElement.scrollWidth <= window.innerWidth"
                            )
                        for context in contexts:
                            context.close()
                    finally:
                        browser.close()
            finally:
                if ui_process is not None:
                    ui_process.terminate()
                    ui_process.wait(timeout=10)
                if api_process is not None:
                    api_process.terminate()
                    api_process.wait(timeout=10)

    print(
        "PASS real Chrome A/B sessions over isolated production API storage; separate Recents and cross-project API denial"
    )


if __name__ == "__main__":
    main()
