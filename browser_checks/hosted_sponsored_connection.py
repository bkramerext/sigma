"""Real-browser regression for the hosted SIGMA-sponsored API connection pill."""

from __future__ import annotations

import json
import os
import re
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
    phrase_source = (ROOT / "frontend/src/invitation-welcome-phrases.ts").read_text(
        encoding="utf-8"
    )
    phrases = re.findall(r"^  '(.+)',?$", phrase_source, re.MULTILINE)
    assert len(phrases) == 100 and len(set(phrases)) == 100, (len(phrases), len(set(phrases)))
    with sync_playwright() as playwright:
        browser = playwright.chromium.launch(executable_path=CHROME, headless=True)
        page = browser.new_page(viewport={"width": 1440, "height": 900})
        selected = {"mode": "personal"}
        forced = {"value": False}
        welcome_pending = {"value": True}
        guest_mode = {"value": False}
        funding = {
            "allowance_usd": 0.75,
            "estimated_usage_usd": 0,
            "held_usd": 0,
            "remaining_usd": 0.75,
        }
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
                    "authenticated": not guest_mode["value"],
                    "user": None
                    if guest_mode["value"]
                    else {"email": "member@example.test", "role": "member"},
                    "account": None
                    if guest_mode["value"]
                    else {
                        "identity": {"email": "member@example.test", "verified": True},
                        "access": {"status": "invited", "role": "member"},
                        "workspace": {"available": True, "id": "workspace-test"},
                        "model_access": {"mode": selected["mode"], "connection": "connected"},
                        "sponsorship": {"eligible": True, "forced": forced["value"]},
                        "invitation_welcome_pending": welcome_pending["value"],
                    },
                    "admin_contact_email": "admin@example.test",
                }
            elif path.endswith("/api/cloud-research/budget"):
                payload = funding | {
                    "reserved_and_estimated_usd": funding["estimated_usage_usd"]
                    + funding["held_usd"],
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
            elif path.endswith("/api/cloud-auth/welcome") and method == "POST":
                welcome_pending["value"] = False
                payload = {"dismissed": True}
            elif path.endswith("/api/cloud-auth/denied"):
                payload = {"email": "new-guest@example.test", "invitation_status": None}
            elif path.endswith("/api/cloud-auth/invitation-request") and method == "POST":
                payload = {"status": "notified", "duplicate": False}
            elif path.endswith(("/api/projects/samples", "/api/projects/recent")):
                payload = {"projects": []}
            elif path.endswith("/api/ui-instance"):
                payload = {"instance": "browser-test"}
            route.fulfill(status=200, content_type="application/json", body=json.dumps(payload))

        page.route("**/api/**", mock_api)
        page.goto(origin + "/", wait_until="networkidle")
        assert page.locator("html").evaluate(
            "element => getComputedStyle(element).backgroundColor"
        ) == "rgb(2, 7, 17)"
        assert page.locator("body").evaluate(
            "element => getComputedStyle(element).backgroundColor"
        ) == "rgb(2, 7, 17)"
        credit = page.locator(".home-art-credit")
        expect(credit).to_be_visible()
        credit_lines = [line.strip() for line in credit.inner_text().splitlines() if line.strip()]
        assert credit_lines[0] == "Crafted by Brian Kramer", credit_lines
        assert re.fullmatch(r"and [a-z-]+ OpenAI agents\.", credit_lines[1]), credit_lines
        welcome = page.locator("#invitation-welcome-dialog")
        expect(welcome).to_be_visible()
        expect(welcome.get_by_role("heading", name="You have been invited!")).to_be_visible()
        expect(welcome).to_contain_text("We will start you off with a $0.75 allowance.")
        expect(welcome.locator("#invitation-welcome-phrase")).not_to_be_empty()
        welcome_box = welcome.bounding_box()
        assert welcome_box is not None
        assert abs(welcome_box["x"] + welcome_box["width"] / 2 - 720) < 30, welcome_box
        assert abs(welcome_box["y"] + welcome_box["height"] / 2 - 450) < 30, welcome_box
        welcome.get_by_role("button", name="Let's get started").click()
        expect(welcome).to_have_count(0)
        # Keep the temporary invitation action available for signed-in
        # accounts so the Google account chooser can be tested from an
        # existing session as well as a guest session.
        expect(
            page.locator(".home-topline .home-header-actions .project-invite-me")
        ).to_be_visible()
        page.reload(wait_until="domcontentloaded")
        expect(page.locator("#invitation-welcome-dialog")).to_have_count(0)
        funding.update(
            allowance_usd=2,
            estimated_usage_usd=0.25,
            held_usd=0.25,
            remaining_usd=1.5,
        )
        page.evaluate("window.dispatchEvent(new Event('sigma-sponsored-budget-refresh'))")
        pill = page.locator(".api-connection > summary")
        expect(pill).to_be_visible()
        expect(pill).to_contain_text("SIGMA-sponsored GPT Usage")
        allowance = page.get_by_role("button", name="Sponsored allowance details")
        allowance.hover()
        allowance_text = page.locator(".sponsored-allowance-tooltip")
        expect(allowance_text).to_contain_text("$1.50 remaining of $2.00 per-user allowance")
        expect(allowance_text).to_contain_text("$0.25 estimated and $0.25 held")
        allowance.focus()
        expect(allowance_text).to_be_visible()
        pill.focus()
        expect(allowance_text).to_be_visible()
        funding.update(remaining_usd=1.25, estimated_usage_usd=0.50)
        page.evaluate("window.dispatchEvent(new Event('sigma-sponsored-budget-refresh'))")
        expect(allowance_text).to_contain_text("$1.25 remaining")
        page.set_viewport_size({"width": 390, "height": 844})
        allowance.click()
        expect(allowance).to_have_attribute("aria-expanded", "true")
        expect(allowance_text).to_be_visible()
        allowance.click()
        expect(allowance).to_have_attribute("aria-expanded", "false")
        pill.click()
        expect(pill).to_contain_text("SIGMA-sponsored GPT Usage")
        expect(allowance_text).to_contain_text("Sponsored model connection: connected")
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

        # A forced member keeps the required state through reload and the pill
        # cannot initiate a change request.
        selected["mode"] = "sponsored"
        forced["value"] = True
        posts.clear()
        page.reload(wait_until="domcontentloaded")
        forced_pill = page.locator(".api-connection > summary")
        expect(forced_pill).to_contain_text("SIGMA-sponsored GPT Usage")
        expect(forced_pill).to_have_attribute(
            "aria-label", "SIGMA-sponsored GPT Usage; sponsored mode is required; connected"
        )
        forced_pill.hover()
        expect(allowance_text).to_contain_text("Sponsored mode is required for this account")
        forced_pill.click()
        assert not any(path.endswith("/api/ai/mode") for path, _ in posts), posts
        page.reload(wait_until="domcontentloaded")
        expect(page.locator(".api-connection > summary")).to_contain_text(
            "SIGMA-sponsored GPT Usage"
        )

        # The guest invitation action belongs directly below About in the
        # right-hand home header action stack, and still opens its dialog.
        guest_mode["value"] = True
        page.reload(wait_until="domcontentloaded")
        about = page.locator(".home-topline .home-about-button")
        invite = page.locator(".home-topline .home-header-actions .project-invite-me")
        expect(about).to_be_visible()
        expect(invite).to_be_visible()
        about_box = about.bounding_box()
        invite_box = invite.bounding_box()
        assert about_box and invite_box
        assert invite_box["y"] >= about_box["y"] + about_box["height"], (about_box, invite_box)
        invite.click()
        invitation_dialog = page.locator("#google-invitation-dialog")
        expect(invitation_dialog).to_be_visible()
        expect(invitation_dialog.get_by_role("link", name="Privacy Notice")).to_be_visible()
        heading_box = invitation_dialog.locator(".google-invitation-heading h2").bounding_box()
        close_box = invitation_dialog.get_by_role("button", name="Close").bounding_box()
        assert heading_box and close_box
        assert close_box["x"] >= heading_box["x"] + heading_box["width"], (heading_box, close_box)
        assert (
            invitation_dialog.get_by_role("button", name="Close").evaluate(
                "element => getComputedStyle(element).textDecorationLine"
            )
            == "underline"
        )
        assert (
            invitation_dialog.get_by_role("button", name="Close").evaluate(
                "element => getComputedStyle(element).backgroundColor"
            )
            == "rgba(0, 0, 0, 0)"
        )
        dialog_box = invitation_dialog.bounding_box()
        privacy_box = invitation_dialog.get_by_role("link", name="Privacy Notice").bounding_box()
        assert dialog_box and privacy_box
        assert abs(privacy_box["x"] - dialog_box["x"] - 24) <= 2, (dialog_box, privacy_box)
        invitation_dialog.get_by_role("link", name="Privacy Notice").click()
        expect(page).to_have_url(re.compile(r"/privacy\?return_to="))
        page.locator(".privacy-close-button").click()
        invitation_dialog = page.locator("#google-invitation-dialog")
        expect(invitation_dialog).to_be_visible()
        invitation_dialog.get_by_role("button", name="Close").click()
        page.locator(".home-topline .home-about-button").click()
        about_dialog = page.locator(".about-dialog")
        expect(about_dialog.get_by_role("link", name="Privacy Notice")).to_be_visible()
        about_dialog.get_by_role("link", name="Privacy Notice").click()
        expect(page).to_have_url(re.compile(r"/privacy\?return_to=.*return_dialog=about"))
        page.locator(".privacy-close-button").click()
        expect(about_dialog).to_be_visible()
        about_dialog.get_by_text("Send product feedback", exact=True).click()
        about_dialog.locator(".about-feedback-form a").click()
        expect(page).to_have_url(re.compile(r"/privacy\?return_to=.*return_dialog=about"))
        page.locator(".privacy-close-button").click()
        expect(about_dialog).to_be_visible()

        # An invite-intent Google sign-in submits immediately after identity
        # verification and removes Invite me without reopening a dialog.
        posts.clear()
        page.goto(origin + "/?access=denied&invite=1", wait_until="networkidle")
        expect(page.locator(".project-invite-me")).to_have_count(0)
        expect(page.locator("#google-invitation-dialog")).not_to_be_visible()
        assert sum(path.endswith("/api/cloud-auth/invitation-request") for path, _ in posts) == 1, (
            posts
        )
        browser.close()


if __name__ == "__main__":
    main()
