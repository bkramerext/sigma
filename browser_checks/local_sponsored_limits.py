"""Real-Chrome acceptance for editable local sponsored research limits.

Uses the deterministic provider fixture. The browser never invokes a provider.
"""

from __future__ import annotations

import json
import os
import socket
import subprocess
import time
from pathlib import Path
from urllib.parse import urlencode
from urllib.request import Request, urlopen

from playwright.sync_api import expect, sync_playwright

ROOT = Path(__file__).resolve().parents[1]
CHROME = os.environ.get(
    "SIGMA_BROWSER_EXECUTABLE",
    "/Applications/Google Chrome.app/Contents/MacOS/Google Chrome",
)
UI_ORIGIN = os.environ.get("SIGMA_BROWSER_BASE_URL", "http://127.0.0.1:5173").rstrip("/")


def free_port() -> int:
    with socket.socket() as listener:
        listener.bind(("127.0.0.1", 0))
        return int(listener.getsockname()[1])


def wait_for(url: str, process: subprocess.Popen[bytes]) -> None:
    import urllib.error

    deadline = time.monotonic() + 20
    while time.monotonic() < deadline:
        if process.poll() is not None:
            raise RuntimeError(f"Fixture process exited before startup: {url}")
        try:
            with urlopen(url, timeout=0.5):
                return
        except (OSError, urllib.error.URLError):
            time.sleep(0.1)
    raise RuntimeError(f"Fixture process did not become ready: {url}")


def main() -> None:
    api_port = free_port()
    api_origin = f"http://127.0.0.1:{api_port}"
    env = os.environ.copy()
    for name in ("SIGMA_CLOUD_AUTH_ENABLED", "SIGMA_CLOUD_AUTH_LOCAL", "SIGMA_MOCK_AUTH"):
        env[name] = "false"
    api = subprocess.Popen(
        [
            str(ROOT / ".venv/bin/uvicorn"),
            "provider_fixture:app",
            "--app-dir",
            "browser_checks",
            "--host",
            "127.0.0.1",
            "--port",
            str(api_port),
        ],
        cwd=ROOT,
        env=env,
        stdout=subprocess.DEVNULL,
        stderr=subprocess.STDOUT,
    )
    try:
        wait_for(api_origin + "/api/ai/connection", api)
        data = json.dumps(
            {
                "title": "Local sponsored limits browser check",
                "problem": "Check a bounded recurrence.",
            }
        ).encode()
        request = Request(
            api_origin + "/api/projects/create",
            data=data,
            headers={"Content-Type": "application/json"},
        )
        with urlopen(request, timeout=5) as response:
            created = json.load(response)
        path = created["path"]

        with sync_playwright() as playwright:
            browser = playwright.chromium.launch(executable_path=CHROME, headless=True)
            try:
                page = browser.new_page(viewport={"width": 1440, "height": 900})
                errors: list[str] = []
                page.on("pageerror", lambda error: errors.append(str(error)))

                def forward(route) -> None:
                    if route.request.url.endswith("/api/cloud-auth/welcome"):
                        route.fulfill(status=204)
                    elif route.request.url.endswith("/api/cloud-auth/status"):
                        route.fulfill(
                            status=200,
                            content_type="application/json",
                            body=json.dumps(
                                {
                                    "target": "local",
                                    "enabled": True,
                                    "ready": True,
                                    "authenticated": True,
                                    "user": {"email": "member@example.test", "role": "member"},
                                    "account": {
                                        "sponsorship": {"eligible": True},
                                        "model_access": {"mode": "sponsored"},
                                    },
                                    "admin_contact_email": None,
                                }
                            ),
                        )
                    else:
                        response = route.fetch(url=route.request.url.replace(UI_ORIGIN, api_origin))
                        route.fulfill(response=response)

                page.route(
                    "**/api/**",
                    lambda route: forward(route),
                )
                page.goto(
                    f"{UI_ORIGIN}/project?{urlencode({'path': path})}",
                    wait_until="networkidle",
                )
                welcome = page.locator("#invitation-welcome-dialog")
                if welcome.count() and welcome.is_visible():
                    welcome.get_by_role("button", name="Let's get started").click()
                    expect(welcome).to_have_count(0)
                if not page.get_by_role("button", name="Project settings", exact=True).count():
                    raise AssertionError(
                        f"Project page did not render. URL={page.url}; "
                        f"text={page.locator('body').inner_text()[:800]}; errors={errors}"
                    )
                page.get_by_role("button", name="Project settings", exact=True).click()
                settings = page.get_by_role("dialog", name="Settings")
                settings.get_by_role("tab", name="Limits", exact=True).click()
                expect(
                    settings.get_by_text(
                        "Local sponsored research uses this project’s saved call limit, up to 120 calls."
                    )
                ).to_be_visible()
                calls = settings.get_by_label("Maximum agent calls", exact=True)
                expect(calls).to_have_value("30")
                calls.fill("12")
                settings.get_by_role("button", name="Save", exact=True).click()
                expect(settings).to_be_hidden()
                saved = page.evaluate(
                    """async () => {
                      const path = new URL(location.href).searchParams.get('path');
                      const response = await fetch('/api/projects/research-limits?' + new URLSearchParams({path}));
                      return await response.json();
                    }"""
                )
                assert saved["model_calls"] == 12, saved
                page.reload(wait_until="networkidle")
                page.get_by_role("button", name="Project settings", exact=True).click()
                settings = page.get_by_role("dialog", name="Settings")
                settings.get_by_role("tab", name="Limits", exact=True).click()
                expect(settings.get_by_label("Maximum agent calls", exact=True)).to_have_value("12")
                assert not errors, errors
                page.screenshot(path="/tmp/sigma-local-sponsored-limits.png", full_page=True)
            finally:
                browser.close()
        print(
            "PASS local sponsored model-call setting saves, reads, and survives browser reload at 12"
        )
    finally:
        api.terminate()
        try:
            api.wait(timeout=5)
        except subprocess.TimeoutExpired:
            api.kill()
            api.wait(timeout=5)


if __name__ == "__main__":
    main()
