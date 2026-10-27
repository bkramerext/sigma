"""Real-browser regression for the hosted SIGMA-sponsored API connection pill."""

from __future__ import annotations

import json
import os
import socket
import subprocess
import time
from pathlib import Path

from playwright.sync_api import expect, sync_playwright

ROOT = Path(__file__).resolve().parents[1]
FRONTEND = ROOT / "frontend"
CHROME = os.environ.get(
    "SIGMA_BROWSER_EXECUTABLE",
    "/Applications/Google Chrome.app/Contents/MacOS/Google Chrome",
)


def free_port() -> int:
    with socket.socket() as listener:
        listener.bind(("127.0.0.1", 0))
        return int(listener.getsockname()[1])


def main() -> None:
    port = free_port()
    origin = f"http://127.0.0.1:{port}"
    env = os.environ.copy()
    env["SIGMA_API_TARGET"] = "http://127.0.0.1:9"
    process = subprocess.Popen(
        [
            str(FRONTEND / "node_modules/.bin/vite"),
            "--host",
            "127.0.0.1",
            "--port",
            str(port),
            "--strictPort",
        ],
        cwd=FRONTEND,
        env=env,
        stdout=subprocess.DEVNULL,
        stderr=subprocess.STDOUT,
    )
    try:
        deadline = time.monotonic() + 20
        while time.monotonic() < deadline:
            if process.poll() is not None:
                raise RuntimeError("Vite exited before browser test startup")
            try:
                import urllib.request

                urllib.request.urlopen(origin, timeout=0.5).close()
                break
            except OSError:
                time.sleep(0.1)
        else:
            raise RuntimeError("Vite did not become ready")
        exercise(origin)
    finally:
        process.terminate()
        try:
            process.wait(timeout=5)
        except subprocess.TimeoutExpired:
            process.kill()
            process.wait(timeout=5)


def exercise(origin: str) -> None:
    with sync_playwright() as playwright:
        browser = playwright.chromium.launch(executable_path=CHROME, headless=True)
        page = browser.new_page(viewport={"width": 1440, "height": 900})
        selected = {"mode": "personal"}
        posts: list[tuple[str, dict]] = []
        failures: list[str] = []
        page.on("pageerror", lambda error: failures.append(str(error)))

        def mock_api(route) -> None:
            request = route.request
            path = request.url.split("?", 1)[0]
            method = request.method
            body = request.post_data_json if request.post_data else {}
            if method == "POST":
                posts.append((path, body))
            payload: object = {}
            if path.endswith("/api/cloud-auth/status"):
                payload = {
                    "target": "hosted",
                    "enabled": True,
                    "ready": True,
                    "authenticated": True,
                    "user": {"email": "member@example.test", "role": "member"},
                    "account": {
                        "identity": {"email": "member@example.test", "verified": True},
                        "access": {"status": "invited", "role": "member"},
                        "workspace": {"available": True, "id": "workspace-test"},
                        "model_access": {"mode": selected["mode"], "connection": "connected"},
                        "sponsorship": {"eligible": True},
                    },
                    "admin_contact_email": "admin@example.test",
                }
            elif path.endswith("/api/cloud-research/budget"):
                payload = {
                    "allowance_usd": 2,
                    "estimated_usage_usd": 0,
                    "held_usd": 0,
                    "reserved_and_estimated_usd": 0,
                    "remaining_usd": 2,
                    "unknown_provider_attempts": 0,
                }
            elif path.endswith("/api/cloud-research/connection"):
                payload = {
                    "mode": "sponsored",
                    "status": "connected",
                    "label": "OpenAI API connected",
                    "guidance": "",
                    "checked_at": "2026-10-27T00:00:00Z",
                }
            elif path.endswith("/api/ai/connection"):
                payload = {
                    "mode": "api_key",
                    "status": "connected" if selected["mode"] == "sponsored" else "disconnected",
                    "label": "OpenAI API connected",
                    "guidance": "",
                    "checked_at": "2026-10-27T00:00:00Z",
                    "ttl_seconds": 0,
                    "accounts": [],
                }
            elif path.endswith("/api/ai/mode") and method == "POST":
                selected["mode"] = body.get("mode")
                payload = {
                    "mode": "api_key",
                    "status": "connected",
                    "label": "OpenAI API connected",
                    "guidance": "",
                    "checked_at": "2026-10-27T00:00:00Z",
                    "ttl_seconds": 0,
                    "accounts": [],
                }
            elif path.endswith(("/api/projects/samples", "/api/projects/recent")):
                payload = {"projects": []}
            elif path.endswith("/api/ui-instance"):
                payload = {"instance": "browser-test"}
            route.fulfill(status=200, content_type="application/json", body=json.dumps(payload))

        page.route("**/api/**", mock_api)
        page.goto(origin + "/", wait_until="networkidle")
        pill = page.locator(".api-connection > summary")
        expect(pill).to_be_visible()
        expect(pill).to_contain_text("Use SIGMA-sponsored API")
        pill.click()
        expect(pill).to_contain_text("SIGMA-sponsored API connected")
        expect(page.get_by_text("Request Failed", exact=True)).to_have_count(0)
        assert any(
            path.endswith("/api/ai/mode") and body == {"mode": "sponsored"} for path, body in posts
        ), posts
        assert not any(path.endswith("/api/ai/auth/begin") for path, _ in posts), posts
        pill.click()
        assert not any(
            path.endswith("/api/ai/mode") and body.get("mode") == "personal" for path, body in posts
        ), posts
        expect(page.get_by_text("Samples", exact=True)).to_be_visible()
        assert not failures, failures
        browser.close()


if __name__ == "__main__":
    main()
