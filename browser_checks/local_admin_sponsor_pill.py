"""Browser regression for a local Google admin reconnecting the sponsor account."""

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
        import urllib.request

        deadline = time.monotonic() + 20
        while time.monotonic() < deadline:
            if process.poll() is not None:
                raise RuntimeError("Vite exited before browser test startup")
            try:
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
    selected_mode = {"value": "personal"}
    attempt_complete = {"value": False}
    active_account = {"value": "selected-sponsor"}
    selected_account_is_sponsor = {"value": True}
    posts: list[tuple[str, dict]] = []
    with sync_playwright() as playwright:
        browser = playwright.chromium.launch(executable_path=CHROME, headless=True)
        page = browser.new_page(viewport={"width": 1440, "height": 900})

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
                    "target": "local",
                    "enabled": True,
                    "ready": True,
                    "authenticated": True,
                    "user": {"email": "zetacontinuation@gmail.com", "role": "admin"},
                    "account": {
                        "identity": {"email": "zetacontinuation@gmail.com", "verified": True},
                        "access": {"status": "invited", "role": "admin"},
                        "workspace": {"available": True, "id": "local-admin"},
                        "model_access": {
                            "mode": selected_mode["value"],
                            "connection": "disconnected",
                        },
                        "sponsorship": {"eligible": True, "forced": False},
                        "invitation_welcome_pending": False,
                    },
                    "admin_contact_email": "zetacontinuation@gmail.com",
                }
            elif path.endswith("/api/ai/connection"):
                connected = attempt_complete["value"]
                payload = {
                    "mode": "chatgpt",
                    "status": "connected" if connected else "disconnected",
                    "label": "Connected" if connected else "Connect to ChatGPT",
                    "guidance": "",
                    "checked_at": "2026-10-28T00:00:00Z" if connected else None,
                    "ttl_seconds": 30,
                    "active_account": active_account["value"],
                    "sponsor_account_selected": selected_account_is_sponsor["value"],
                    "accounts": [
                        {
                            "id": active_account["value"],
                            "label": "zetacontinuation@gmail.com"
                            if selected_account_is_sponsor["value"]
                            else "personal-chatgpt@example.test",
                        }
                    ],
                }
            elif path.endswith(
                ("/api/cloud-auth/local-sponsored-allowance", "/api/cloud-research/budget")
            ):
                payload = {
                    "allowance_usd": 10,
                    "estimated_usage_usd": 0,
                    "held_usd": 0,
                    "remaining_usd": 10,
                    "global_remaining_usd": 50,
                    "unknown_provider_attempts": 0,
                }
            elif path.endswith("/api/cloud-research/connection"):
                payload = {
                    "mode": "sponsored",
                    "status": "connected" if attempt_complete["value"] else "disconnected",
                    "label": "Sponsored ChatGPT",
                    "guidance": "",
                    "checked_at": "2026-10-28T00:00:00Z",
                }
            elif path.endswith("/api/ai/sponsor-auth/begin") and method == "POST":
                payload = {
                    "id": "sponsor-attempt",
                    "authorization_url": "/api/ai/auth/open/sponsor-attempt",
                }
            elif path.endswith("/api/ai/auth/begin") and method == "POST":
                if body.get("account_id") == "selected-sponsor":
                    route.fulfill(
                        status=403,
                        content_type="application/json",
                        body=json.dumps(
                            {"error": "Use Admin Settings to renew the sponsor account."}
                        ),
                    )
                    return
                payload = {
                    "id": "personal-attempt",
                    "authorization_url": "/api/ai/auth/open/personal-attempt",
                }
            elif path.endswith(
                ("/api/ai/auth/attempt/sponsor-attempt", "/api/ai/auth/attempt/personal-attempt")
            ):
                payload = {
                    "status": "connected" if attempt_complete["value"] else "connecting",
                    "retryable": False,
                    "message": "",
                }
            elif path.endswith("/api/ai/mode") and method == "POST":
                selected_mode["value"] = body["mode"]
                payload = {
                    "mode": "chatgpt",
                    "status": "connected",
                    "label": "Connected",
                    "guidance": "",
                    "checked_at": "2026-10-28T00:00:00Z",
                    "ttl_seconds": 30,
                    "active_account": active_account["value"],
                    "accounts": [],
                }
            elif path.endswith(("/api/projects/recent", "/api/projects/samples")):
                payload = {"projects": []}
            elif path.endswith("/api/ui-instance"):
                payload = {"instance": "local-admin-sponsor-pill"}
            route.fulfill(status=200, content_type="application/json", body=json.dumps(payload))

        page.route("**/api/**", mock_api)
        page.goto(origin + "/", wait_until="domcontentloaded")
        summary = page.locator(".api-connection > summary")
        expect(summary).to_have_attribute("aria-label", "Connect to ChatGPT")
        posts.clear()
        with page.expect_request("**/api/ai/sponsor-auth/begin") as oauth_begin:
            summary.click()
        assert oauth_begin.value.method == "POST"
        assert oauth_begin.value.post_data_json == {"enable_plan": False}
        assert any(url.endswith("/api/ai/sponsor-auth/begin") for url, _ in posts), posts
        assert not any(url.endswith("/api/ai/auth/begin") for url, _ in posts), posts

        attempt_complete["value"] = True
        expect(summary).to_have_attribute("aria-label", "Sponsored ChatGPT; connected")
        assert any(
            url.endswith("/api/ai/mode") and body == {"mode": "sponsored"} for url, body in posts
        ), posts
        expect(page.locator(".connection-pill-message[role=alert]")).to_have_count(0)

        # A genuinely personal account remains on the personal endpoint and
        # keeps personal mode after sign-in.
        selected_mode["value"] = "personal"
        attempt_complete["value"] = False
        active_account["value"] = "personal-registration"
        selected_account_is_sponsor["value"] = False
        page.reload(wait_until="domcontentloaded")
        summary = page.locator(".api-connection > summary")
        expect(summary).to_have_attribute("aria-label", "Connect to ChatGPT")
        posts.clear()
        with page.expect_request("**/api/ai/auth/begin") as personal_begin:
            summary.click()
        assert personal_begin.value.method == "POST"
        assert personal_begin.value.post_data_json["account_id"] == "personal-registration"
        assert not any(url.endswith("/api/ai/sponsor-auth/begin") for url, _ in posts), posts
        attempt_complete["value"] = True
        expect(summary).to_have_attribute("aria-label", "ChatGPT connected")
        assert not any(
            url.endswith("/api/ai/mode") and body == {"mode": "sponsored"} for url, body in posts
        ), posts
        browser.close()


if __name__ == "__main__":
    main()
