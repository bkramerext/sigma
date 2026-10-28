"""Browser regression for personal/sponsored ChatGPT pill transitions."""

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
    attempt_failure = {"value": False}
    current_user = {"email": "zetacontinuation@gmail.com", "role": "admin"}
    sponsor_connected = {"value": True}
    google_authenticated = {"value": True}
    posts: list[tuple[str, dict]] = []
    connected = {"value": False}
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
            if path.endswith("/api/cloud-auth/status"):
                payload: object = {
                    "target": "local",
                    "enabled": True,
                    "ready": True,
                    "authenticated": google_authenticated["value"],
                    "user": current_user.copy() if google_authenticated["value"] else None,
                    "account": {
                        "identity": {"email": current_user["email"], "verified": True},
                        "access": {"status": "invited", "role": current_user["role"]},
                        "workspace": {"available": True, "id": "local-admin"},
                        "model_access": {
                            "mode": selected_mode["value"],
                            "connection": "connected" if connected["value"] else "disconnected",
                        },
                        "sponsorship": {"eligible": True, "forced": False},
                        "invitation_welcome_pending": False,
                    },
                    "admin_contact_email": "zetacontinuation@gmail.com",
                }
            elif path.endswith("/api/ai/connection"):
                is_sponsored = selected_mode["value"] == "sponsored"
                provider_connected = (
                    sponsor_connected["value"] if is_sponsored else connected["value"]
                )
                payload = {
                    "mode": "chatgpt",
                    "status": "connected" if provider_connected else "disconnected",
                    "label": "Connected" if provider_connected else "Connect to ChatGPT",
                    "guidance": "",
                    "checked_at": "2026-10-28T00:00:00Z" if provider_connected else None,
                    "ttl_seconds": 30,
                    "active_account": "personal-z-registration"
                    if not is_sponsored
                    else "sponsor-registration",
                    "account_label": "zetacontinuation@gmail.com" if provider_connected else None,
                    "sponsor_account_selected": is_sponsored,
                    "accounts": [
                        {"id": "personal-z-registration", "label": "zetacontinuation@gmail.com"}
                    ],
                }
            elif path.endswith(
                ("/api/cloud-auth/local-sponsored-allowance", "/api/cloud-research/budget")
            ):
                remaining = 0.37 if current_user["role"] == "member" else 10
                payload = {
                    "allowance_usd": remaining,
                    "estimated_usage_usd": 0,
                    "held_usd": 0,
                    "remaining_usd": remaining,
                    "global_remaining_usd": 50,
                    "unknown_provider_attempts": 0,
                }
            elif path.endswith("/api/cloud-research/connection"):
                payload = {
                    "mode": "sponsored",
                    "status": "connected" if sponsor_connected["value"] else "unavailable",
                    "label": "Sponsored ChatGPT",
                    "guidance": "",
                    "checked_at": "2026-10-28T00:00:00Z",
                    "account_label": "zetacontinuation@gmail.com",
                }
            elif path.endswith("/api/ai/auth/begin") and method == "POST":
                payload = {
                    "id": "personal-attempt",
                    "authorization_url": "/api/ai/auth/open/personal-attempt",
                }
            elif path.endswith("/api/ai/sponsor-auth/begin") and method == "POST":
                payload = {
                    "id": "sponsor-attempt",
                    "authorization_url": "/api/ai/auth/open/sponsor-attempt",
                }
            elif path.endswith("/api/ai/auth/attempt/personal-attempt"):
                payload = (
                    {
                        "status": "failed",
                        "retryable": False,
                        "message": "Simulated OAuth cancellation.",
                    }
                    if attempt_failure["value"]
                    else {
                        "status": "connected" if attempt_complete["value"] else "connecting",
                        "retryable": False,
                        "message": "",
                    }
                )
            elif path.endswith("/api/ai/mode") and method == "POST":
                selected_mode["value"] = body["mode"]
                payload = {
                    "mode": "chatgpt",
                    "status": "connected",
                    "label": "Connected",
                    "guidance": "",
                    "checked_at": "2026-10-28T00:00:00Z",
                    "ttl_seconds": 30,
                    "active_account": "personal-z-registration",
                    "accounts": [],
                }
            elif path.endswith("/api/ai/disconnect") and method == "POST":
                connected["value"] = False
                payload = {"status": "disconnected"}
            elif path.endswith(("/api/projects/recent", "/api/projects/samples")):
                payload = {"projects": []}
            elif path.endswith("/api/ui-instance"):
                payload = {"instance": "local-admin-sponsor-pill"}
            elif path.endswith("/api/cloud-auth/logout") and method == "POST":
                google_authenticated["value"] = False
                payload = {"logged_out": True}
            else:
                payload = {}
            route.fulfill(status=200, content_type="application/json", body=json.dumps(payload))

        page.route("**/api/**", mock_api)
        page.goto(origin + "/", wait_until="domcontentloaded")
        google_pill = page.locator(".identity-pill-stack .project-google-signin").first
        expect(google_pill).to_have_text("Sign out of Google")
        expect(google_pill).to_have_attribute("aria-label", "Sign out of Google")
        pill = page.locator(".api-connection > summary")

        # Existing Google session, persistent personal selection, and a saved
        # Z personal registration. The same provider email owns sponsor creds.
        expect(pill.get_by_role("status")).to_have_text("Connect to ChatGPT")
        expect(pill).to_have_attribute("aria-label", "Connect to ChatGPT")
        expect(pill).not_to_contain_text("Unlimited")
        assert pill.get_attribute("data-tooltip") in (None, "")
        posts.clear()
        with page.expect_request("**/api/ai/auth/begin") as begin:
            pill.click()
        assert begin.value.method == "POST"
        assert begin.value.post_data_json == {
            "account_id": "personal-z-registration",
            "enable_plan": False,
        }
        assert not any(url.endswith("/api/ai/sponsor-auth/begin") for url, _ in posts), posts
        attempt_complete["value"] = True
        connected["value"] = True
        expect(pill.get_by_role("status")).to_have_text("Disconnect from ChatGPT")
        expect(pill).to_have_attribute("aria-label", "Disconnect from ChatGPT")
        expect(pill).not_to_contain_text("Unlimited")
        assert pill.get_attribute("data-tooltip") == "Connected as zetacontinuation@gmail.com."
        assert not any(
            url.endswith("/api/ai/mode") and body == {"mode": "sponsored"} for url, body in posts
        ), posts

        # Disconnect affects the personal registration and intentionally
        # returns this user to sponsorship.
        posts.clear()
        pill.click()
        expect(pill.get_by_role("status")).to_have_text("Sponsored ChatGPT")
        assert selected_mode["value"] == "sponsored", posts
        expect(pill.locator(".sponsored-allowance-inline")).to_have_text("Unlimited")
        assert any(
            url.endswith("/api/ai/mode") and body == {"mode": "sponsored"} for url, body in posts
        ), posts
        tip = page.locator("#sponsored-allowance-tooltip")
        expect(tip).to_contain_text("Sponsor Connected · zetacontinuation@gmail.com · Unlimited")
        expect(tip).to_contain_text("Click to connect your own ChatGPT account.")
        assert len(tip.inner_text()) < 150
        page.locator(".sponsored-allowance-trigger").hover()
        expect(tip).to_be_visible()

        # A sponsored member sees only their allowance and provider state.
        # Even if an upstream fixture includes a sponsor label, no member UI
        # text, tooltip, or accessibility label exposes it.
        current_user.update(email="nontrivialzeeros@gmail.com", role="member")
        selected_mode["value"] = "sponsored"
        sponsor_connected["value"] = False
        page.reload(wait_until="domcontentloaded")
        member_pill = page.locator(".api-connection > summary")
        expect(member_pill.get_by_role("status")).to_have_text("Sponsored ChatGPT")
        expect(member_pill.locator(".sponsored-allowance-inline")).to_have_text("0.37")
        expect(member_pill).to_have_attribute("aria-label", "Sponsored ChatGPT")
        member_tip = page.locator("#sponsored-allowance-tooltip")
        expect(member_tip).to_contain_text("$0.37 remaining · Unavailable")
        expect(member_tip).to_contain_text("Click to connect your own ChatGPT account.")
        expect(member_tip).not_to_contain_text("zetacontinuation@gmail.com")
        page.locator(".sponsored-allowance-trigger").hover()
        expect(member_tip).to_be_visible()
        posts.clear()
        attempt_complete["value"] = True
        with page.expect_request("**/api/ai/auth/begin") as member_personal_begin:
            member_pill.click()
        connected["value"] = True
        assert member_personal_begin.value.post_data_json == {"enable_plan": False}
        assert not any(url.endswith("/api/ai/sponsor-auth/begin") for url, _ in posts), posts
        expect(member_pill.get_by_role("status")).to_have_text("Disconnect from ChatGPT")
        expect(member_pill).not_to_contain_text("0.37")
        expect(member_pill).not_to_contain_text("Unlimited")

        # Failed/cancelled OAuth keeps the current funding mode and surfaces
        # recovery feedback instead of silently switching billing.
        member_pill.click()
        expect(member_pill.get_by_role("status")).to_have_text("Sponsored ChatGPT")
        assert selected_mode["value"] == "sponsored"
        posts.clear()
        attempt_complete["value"] = False
        attempt_failure["value"] = True
        with page.expect_request("**/api/ai/auth/begin"):
            member_pill.click()
        expect(page.locator(".connection-pill-message[role=alert]")).to_have_text(
            "Simulated OAuth cancellation."
        )
        expect(member_pill.get_by_role("status")).to_have_text("Sponsored ChatGPT")
        assert selected_mode["value"] == "sponsored"
        assert not any(url.endswith("/api/ai/mode") for url, _ in posts), posts
        assert not any(url.endswith("/api/ai/sponsor-auth/begin") for url, _ in posts), posts
        google_pill.click()
        expect(page.locator(".identity-pill-stack .project-google-signin").first).to_have_text(
            "Sign in with Google"
        )
        browser.close()


if __name__ == "__main__":
    main()
