"""Real-browser regression for the hosted SIGMA-sponsored API connection pill."""

from __future__ import annotations

import json
import os
import re
import socket
import subprocess
import time
from pathlib import Path

from playwright.sync_api import TimeoutError as PlaywrightTimeoutError
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


def dismiss_sponsor_welcome(page) -> None:
    welcome = page.locator("#invitation-welcome-dialog")
    if not welcome.count() or not welcome.is_visible():
        return
    welcome.get_by_role("button", name="Let's get started").click(timeout=2000)
    expect(welcome).to_have_count(0)


def dismiss_welcome_if_present(page, timeout: int = 1000) -> None:
    welcome = page.locator("#invitation-welcome-dialog")
    try:
        expect(welcome).to_be_visible(timeout=timeout)
    except PlaywrightTimeoutError:
        return
    dismiss_sponsor_welcome(page)


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
        local_sponsored_mode = {"value": False}
        local_sponsor_reauth = {"value": False}
        sponsored_test_mode = {"value": False}
        mock_provider = {"value": "connected"}
        local_connect_succeeds = {"value": False}
        welcome_pending = {"value": True}
        guest_mode = {"value": False}
        admin_mode = {"value": False}
        admin_grants = [
            {
                "kind": "email",
                "value": "admin@example.test",
                "role": "admin",
                "active": 1,
                "updated_at": 100,
                "allowance_usd": None,
                "effective_allowance_usd": 2.0,
            },
            {
                "kind": "email",
                "value": "New.Member@example.test",
                "role": "member",
                "active": 1,
                "updated_at": 10,
                "allowance_usd": 1.0,
                "effective_allowance_usd": 1.0,
            },
            {
                "kind": "email",
                "value": "new.member@example.test",
                "role": "member",
                "active": 1,
                "updated_at": 20,
                "allowance_usd": 2.0,
                "effective_allowance_usd": 2.0,
            },
        ]
        admin_invitation_requests = [
            {
                "subject": "already-authorized",
                "email": "new.member@example.test",
                "requested_at": 1_797_999_999,
                "status": "pending",
            },
            {
                "subject": "new-invitee",
                "email": "new-invitee@example.test",
                "requested_at": 1_798_000_000,
                "status": "notified",
            },
            {
                "subject": "remove-invitee",
                "email": "remove-invitee@example.test",
                "requested_at": 1_798_000_001,
                "status": "pending",
            },
            *[
                {
                    "subject": f"scroll-request-{index}",
                    "email": f"scroll-{index}@example.test",
                    "requested_at": 1_798_000_002 + index,
                    "status": "pending",
                }
                for index in range(4)
            ],
        ]
        admin_grants.extend(
            {
                "kind": "email",
                "value": f"member-{index:02}@example.test",
                "role": "member",
                "active": 1,
                "updated_at": 30 + index,
                "allowance_usd": None,
                "effective_allowance_usd": 2.0,
            }
            for index in range(30)
        )
        invitation_failures = {"remaining": 0}
        funding = {
            "allowance_usd": 0.25,
            "estimated_usage_usd": 0.21,
            "held_usd": 0,
            "remaining_usd": 0.04,
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
                    "target": "local" if local_sponsored_mode["value"] else "hosted",
                    "mock_auth": sponsored_test_mode["value"],
                    "mock_identity": sponsored_test_mode["value"],
                    "sponsored_test_mode": sponsored_test_mode["value"],
                    "enabled": True,
                    "ready": True,
                    "authenticated": not guest_mode["value"],
                    "user": None
                    if guest_mode["value"]
                    else {
                        "email": "admin@example.test"
                        if admin_mode["value"]
                        else "member@example.test",
                        "role": "admin" if admin_mode["value"] else "member",
                    },
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
            elif path.endswith("/api/cloud-auth/mock/select") and method == "POST":
                selected["mode"] = "sponsored"
                mock_provider["value"] = "connected"
                route.fulfill(status=204)
                return
            elif path.endswith("/api/cloud-auth/mock/funding"):
                payload = {
                    "mode": "sponsored",
                    "allowance": {"remaining_usd": funding["remaining_usd"], "simulated": True},
                    "provider": mock_provider["value"],
                }
            elif path.endswith("/api/cloud-auth/local-sponsored-allowance"):
                payload = funding | {"local_preview": True, "simulated": False}
            elif path.endswith("/api/cloud-auth/mock/provider") and method == "POST":
                mock_provider["value"] = request.url.split("scenario=", 1)[-1]
                payload = {"provider": mock_provider["value"], "simulated": True}
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
                if local_sponsor_reauth["value"]:
                    payload = {
                        "mode": "chatgpt",
                        "status": "reauth_required",
                        "label": "Reconnect ChatGPT",
                        "guidance": "Sponsor credentials are unavailable.",
                        "checked_at": None,
                        "ttl_seconds": 0,
                        "accounts": [],
                    }
                else:
                    payload = {
                        "mode": "api_key",
                        "status": "connected"
                        if selected["mode"] == "sponsored" or local_connect_succeeds["value"]
                        else "disconnected",
                        "label": "OpenAI API connected",
                        "guidance": "",
                        "checked_at": "2026-10-27T00:00:00Z",
                        "ttl_seconds": 0,
                        "accounts": [],
                    }
            elif (
                path.endswith(("/api/ai/auth/begin", "/api/ai/sponsor-auth/begin"))
                and method == "POST"
            ):
                payload = {
                    "id": "test-connect",
                    "authorization_url": origin + "/api/ai/auth/open/test-connect",
                }
            elif path.endswith("/api/ai/auth/attempt/test-connect"):
                if local_connect_succeeds["value"]:
                    local_sponsor_reauth["value"] = False
                payload = {
                    "status": "connected" if local_connect_succeeds["value"] else "failed",
                    "retryable": False,
                    "message": "ChatGPT sign-in did not complete.",
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
                payload = {"identity_available": True, "invitation_status": None}
            elif path.endswith("/api/cloud-auth/invitation-request") and method == "POST":
                if invitation_failures["remaining"]:
                    invitation_failures["remaining"] -= 1
                    route.fulfill(
                        status=503,
                        content_type="application/json",
                        body=json.dumps(
                            {"error": "Your request could not be sent. Please try again later."}
                        ),
                    )
                    return
                payload = {"status": "notified", "duplicate": False}
            elif path.endswith("/api/cloud-auth/admin/grants") and method == "GET":
                payload = {
                    "bootstrap_admin": "admin@example.test",
                    "grants": admin_grants,
                    "sessions": [],
                }
            elif path.endswith("/api/cloud-auth/admin/grants") and method == "POST":
                entry = body.copy()
                entry.update(
                    active=1,
                    updated_at=max(grant["updated_at"] for grant in admin_grants) + 1,
                    effective_allowance_usd=2.0,
                )
                admin_grants.append(entry)
                payload = entry
            elif path.endswith("/api/cloud-auth/admin/grants/updates") and method == "PUT":
                for update in body["updates"]:
                    for grant in admin_grants:
                        if grant["kind"] == update["kind"] and grant["value"] == update["value"]:
                            grant.update(update, updated_at=grant["updated_at"] + 1)
                payload = {"updated": body["updates"]}
            elif "/api/cloud-auth/admin/invitation-requests/" in path and method == "PUT":
                subject = path.rsplit("/", 1)[-1]
                for request_item in admin_invitation_requests:
                    if request_item["subject"] == subject:
                        request_item["status"] = body["status"]
                payload = {"status": body["status"]}
            elif path.endswith("/api/cloud-auth/admin/invitation-requests"):
                payload = {
                    "requests": [
                        request_item
                        for request_item in admin_invitation_requests
                        if request_item["status"] not in {"reviewed", "declined"}
                    ]
                }
            elif path.endswith("/api/cloud-auth/admin/feedback"):
                payload = {"feedback": []}
            elif path.endswith(("/api/projects/samples", "/api/projects/recent")):
                payload = {"projects": []}
            elif path.endswith("/api/ui-instance"):
                payload = {"instance": "browser-test"}
            route.fulfill(status=200, content_type="application/json", body=json.dumps(payload))

        page.route("**/api/**", mock_api)
        page.goto(origin + "/", wait_until="networkidle")
        assert (
            page.locator("html").evaluate("element => getComputedStyle(element).backgroundColor")
            == "rgb(2, 7, 17)"
        )
        assert (
            page.locator("body").evaluate("element => getComputedStyle(element).backgroundColor")
            == "rgb(2, 7, 17)"
        )
        assert "sigma-home-background-copper.png" in page.locator("body").evaluate(
            "element => getComputedStyle(element).backgroundImage"
        )
        credit = page.locator(".home-art-credit")
        expect(credit).to_be_visible()
        credit_lines = [line.strip() for line in credit.inner_text().splitlines() if line.strip()]
        assert credit_lines[0] == "Crafted by Brian Kramer", credit_lines
        assert re.fullmatch(r"and [a-z-]+ OpenAI agents\.", credit_lines[1]), credit_lines
        welcome = page.locator("#invitation-welcome-dialog")
        expect(welcome).to_be_visible()
        expect(welcome.get_by_role("heading", name="You have been invited!")).to_be_visible()
        expect(welcome).to_contain_text("You have $0.04 remaining in your sponsored allowance.")
        expect(welcome.locator(".invitation-welcome-intro")).to_contain_text(
            "SIGMA tracks your sponsored allowance as you use ChatGPT"
        )
        expect(welcome.locator(".invitation-welcome-intro")).to_contain_text(
            "connect your own ChatGPT account"
        )
        expect(welcome.locator(".cloud-auth-kicker")).to_have_count(0)
        expect(welcome.locator("#invitation-welcome-phrase")).not_to_be_empty()
        phrase_style = welcome.locator("#invitation-welcome-phrase").evaluate(
            "element => { const style = getComputedStyle(element); return { background: style.backgroundColor, border: style.borderLeftWidth, fontStyle: style.fontStyle, padding: style.padding }; }"
        )
        assert phrase_style == {
            "background": "rgba(0, 0, 0, 0)",
            "border": "0px",
            "fontStyle": "italic",
            "padding": "0px",
        }, phrase_style
        welcome_box = welcome.bounding_box()
        assert welcome_box is not None
        assert abs(welcome_box["x"] + welcome_box["width"] / 2 - 720) < 30, welcome_box
        assert abs(welcome_box["y"] + welcome_box["height"] / 2 - 450) < 30, welcome_box
        welcome.get_by_role("button", name="Let's get started").click()
        expect(welcome).to_have_count(0)
        # Invitation actions belong only to signed-out visitors.
        expect(
            page.locator(".home-auth-pills .identity-pill-stack .project-invite-me")
        ).to_have_count(0)
        page.reload(wait_until="domcontentloaded")
        expect(page.locator("#invitation-welcome-dialog")).to_have_count(0)
        page.goto(origin + "/?fresh-entry=1", wait_until="domcontentloaded")
        fresh_welcome = page.locator("#invitation-welcome-dialog")
        expect(fresh_welcome).to_have_count(0)
        page.goto(origin + "/not-found", wait_until="domcontentloaded")
        dismiss_sponsor_welcome(page)
        fallback_pill = page.locator(".api-connection > summary")
        expect(fallback_pill).to_have_attribute("aria-label", "Sponsored ChatGPT")
        page.goto(origin + "/", wait_until="domcontentloaded")
        dismiss_sponsor_welcome(page)
        funding.update(
            allowance_usd=2,
            estimated_usage_usd=0.25,
            held_usd=0.25,
            remaining_usd=1.5,
        )
        page.evaluate("window.dispatchEvent(new Event('sigma-sponsored-budget-refresh'))")
        pill = page.locator(".api-connection > summary")
        expect(pill).to_be_visible()
        expect(pill).to_contain_text("Sponsored ChatGPT")
        expect(pill.locator(".sponsored-allowance-inline")).to_have_text("$1.50")
        allowance = page.get_by_role("button", name="Sponsored allowance details")
        assert allowance.evaluate("e => getComputedStyle(e).backgroundColor") == "rgba(0, 0, 0, 0)"
        allowance.hover()
        allowance_text = page.locator(".sponsored-allowance-tooltip")
        expect(allowance_text).to_contain_text("SIGMA covers eligible model calls")
        expect(page.locator("#sigma-ui-tooltip")).to_have_count(0)
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
        expect(pill).to_contain_text("Sponsored ChatGPT")
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
        expect(forced_pill).to_contain_text("Sponsored ChatGPT")
        expect(forced_pill).to_have_attribute(
            "aria-label", "Sponsored ChatGPT; sponsored mode is required; connected"
        )
        forced_pill.hover()
        expect(allowance_text).to_contain_text("Sponsored mode is required for this account")
        forced_pill.click()
        assert not any(path.endswith("/api/ai/mode") for path, _ in posts), posts
        page.reload(wait_until="domcontentloaded")
        expect(page.locator(".api-connection > summary")).to_contain_text("Sponsored ChatGPT")

        # The guest invitation action belongs directly below About in the
        # right-hand home header action stack, and still opens its dialog.
        guest_mode["value"] = True
        page.reload(wait_until="domcontentloaded")
        guest_welcome = page.locator("#invitation-welcome-dialog")
        if guest_welcome.count():
            expect(guest_welcome.locator(".invitation-welcome-intro")).to_contain_text(
                "Explore as a guest without running or saving projects"
            )
            expect(guest_welcome.locator(".invitation-welcome-intro")).to_contain_text(
                "request an invitation to become a member"
            )
            expect(guest_welcome.locator(".invitation-welcome-intro")).to_contain_text(
                "decides whether to include sponsorship when granting your invitation"
            )
            expect(guest_welcome.get_by_role("link", name="Sign in with Google")).to_have_count(0)
            guest_welcome.get_by_role("button", name="Let's get started").click()
        about = page.locator(".home-topline .home-about-button")
        invite = page.locator(".home-auth-pills .identity-pill-stack .project-invite-me")
        google = page.locator(".home-auth-pills a.project-google-signin")
        expect(about).to_be_visible()
        expect(invite).to_be_visible()
        expect(google).to_be_visible()
        expect(page.locator(".home-auth-pills .api-connection")).to_have_count(0)
        google_box = google.bounding_box()
        invite_box = invite.bounding_box()
        assert google_box and invite_box
        assert invite_box["y"] >= google_box["y"] + google_box["height"], (google_box, invite_box)
        assert abs(invite_box["x"] - google_box["x"]) < 2, (google_box, invite_box)
        invite.click()
        invitation_dialog = page.locator("#google-invitation-dialog")
        expect(invitation_dialog).to_be_visible()
        expect(invitation_dialog.locator(".google-account-email")).to_have_count(0)
        expect(invitation_dialog.get_by_role("link", name="Privacy Notice")).to_be_visible()
        signin_box = invitation_dialog.locator(".google-invitation-signin").bounding_box()
        signin_intro_box = invitation_dialog.locator(":scope > p").first.bounding_box()
        invitation_footer_box = invitation_dialog.locator(
            ".google-invitation-footer"
        ).bounding_box()
        assert signin_box and signin_intro_box and invitation_footer_box
        gap_above_signin = signin_box["y"] - (signin_intro_box["y"] + signin_intro_box["height"])
        gap_below_signin = invitation_footer_box["y"] - (signin_box["y"] + signin_box["height"])
        assert abs(gap_below_signin / gap_above_signin - 2.5) <= 0.3, (
            gap_above_signin,
            gap_below_signin,
        )
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
        dismiss_welcome_if_present(page, timeout=10000)
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
        invitation_failures["remaining"] = 1
        posts.clear()
        page.goto(origin + "/?access=denied&invite=1", wait_until="domcontentloaded")
        invitation_dialog = page.locator("#google-invitation-dialog")
        expect(invitation_dialog).to_be_visible()
        expect(invitation_dialog.get_by_role("alert")).to_have_count(1)
        expect(invitation_dialog.get_by_role("alert")).to_contain_text(
            "Your request could not be sent. Please try again later."
        )
        retry = invitation_dialog.get_by_role("button", name="Try again")
        expect(retry).to_be_visible()
        assert (
            retry.evaluate("element => getComputedStyle(element).textDecorationLine") == "underline"
        )
        assert retry.evaluate("element => getComputedStyle(element).backgroundColor") == (
            "rgba(0, 0, 0, 0)"
        )
        retry.click()
        expect(invitation_dialog).not_to_be_visible()
        assert sum(path.endswith("/api/cloud-auth/invitation-request") for path, _ in posts) == 2, (
            posts
        )

        # The administrator can grant a notified request directly. Legacy
        # case variants collapse to one Authorized users row, selecting the
        # most recently updated rule.
        guest_mode["value"] = False
        admin_mode["value"] = True
        page.goto(origin + "/", wait_until="domcontentloaded")
        dismiss_sponsor_welcome(page)
        expect(page.locator("#invitation-welcome-dialog")).to_have_count(0)
        expect(page.locator(".home-topline .home-about-button")).to_have_text("About SIGMA")
        admin_pill = page.get_by_role("link", name="Administrator settings")
        expect(admin_pill).to_have_text("Admin Settings")
        admin_pill.click()
        admin_dialog = page.get_by_role("dialog", name="Administrator Settings")
        expect(admin_dialog).to_be_visible()
        authorized_panel = admin_dialog.locator(".admin-access-panel")
        authorized_scroll = admin_dialog.locator(".admin-authorized-table-scroll")
        expect(authorized_panel).to_have_css("overflow-y", "hidden")
        expect(authorized_scroll).to_contain_text("member-29@example.test")
        scroll_dimensions = authorized_scroll.evaluate(
            "element => ({scrollHeight: element.scrollHeight, clientHeight: element.clientHeight, height: element.getBoundingClientRect().height})"
        )
        assert scroll_dimensions["scrollHeight"] > scroll_dimensions["clientHeight"], (
            scroll_dimensions
        )
        authorized_heading = admin_dialog.get_by_role("heading", name="Authorized users")
        authorized_table = authorized_heading.locator("xpath=following::table[1]")
        expect(authorized_table).to_contain_text("admin@example.test")
        duplicate_rows = authorized_table.locator("tbody tr").filter(
            has_text="new.member@example.test"
        )
        assert duplicate_rows.count() == 1, authorized_table.inner_text()
        duplicate_row = duplicate_rows.first
        expect(duplicate_row).to_contain_text("new.member@example.test")
        expect(duplicate_row).to_contain_text("$2.00")
        assert authorized_table.locator("thead th").nth(2).inner_text().strip() == (
            "Sponsorship allowance"
        )
        role_box = duplicate_row.locator("select").bounding_box()
        allowance_control = duplicate_row.locator(".admin-allowance-input")
        allowance_input_box = allowance_control.locator("input").bounding_box()
        allowance_currency_box = allowance_control.locator('[aria-hidden="true"]').bounding_box()
        effective_box = duplicate_row.locator(".admin-allowance-cell small").bounding_box()
        assert role_box and allowance_input_box and allowance_currency_box and effective_box
        assert abs(role_box["y"] - allowance_input_box["y"]) <= 1, (
            role_box,
            allowance_input_box,
        )
        assert (
            abs(
                allowance_currency_box["y"]
                + allowance_currency_box["height"] / 2
                - allowance_input_box["y"]
                - allowance_input_box["height"] / 2
            )
            <= 1
        ), (allowance_currency_box, allowance_input_box)
        assert effective_box["y"] - allowance_input_box["y"] - allowance_input_box["height"] <= 6, (
            allowance_input_box,
            effective_box,
        )
        duplicate_row.locator(".admin-allowance-cell input").fill("2.75")
        save_button = admin_dialog.get_by_role("button", name="Save", exact=True)
        close_button = admin_dialog.get_by_role("button", name="Close", exact=True)
        save_box = save_button.bounding_box()
        close_box = close_button.bounding_box()
        heading_box = admin_dialog.locator(".admin-dialog-heading h2").bounding_box()
        assert save_box and close_box and heading_box
        assert save_box["x"] >= heading_box["x"] + heading_box["width"], (
            heading_box,
            save_box,
        )
        assert save_box["x"] < close_box["x"] and abs(save_box["y"] - close_box["y"]) <= 1, (
            save_box,
            close_box,
        )
        save_button.click()
        expect(save_button).to_have_count(0)
        invitation_row = (
            admin_dialog.locator(".admin-access-panel table")
            .first.locator("tbody tr")
            .filter(has_text="new-invitee@example.test")
        )
        expect(invitation_row.get_by_role("button", name="Remove", exact=True)).to_be_visible()
        invitation_table = admin_dialog.locator(".admin-invitation-table")
        expect(
            admin_dialog.get_by_role("heading", name="Invitation/reload requests")
        ).to_be_visible()
        invitation_scroll = admin_dialog.locator(".admin-invitation-scroll")
        invitation_dimensions = invitation_scroll.evaluate(
            "element => ({scrollHeight: element.scrollHeight, clientHeight: element.clientHeight})"
        )
        assert invitation_dimensions["scrollHeight"] > invitation_dimensions["clientHeight"]
        expect(
            invitation_table.locator("tbody tr").filter(has_text="new.member@example.test")
        ).to_have_count(0)
        invite_add = invitation_row.get_by_role("button", name="Add", exact=True)
        invite_remove = invitation_row.get_by_role("button", name="Remove", exact=True)
        assert invite_add.evaluate(
            "element => getComputedStyle(element).color"
        ) == invite_remove.evaluate("element => getComputedStyle(element).color")
        invite_add_box = invite_add.bounding_box()
        invite_remove_box = invite_remove.bounding_box()
        assert invite_add_box and invite_remove_box
        assert invite_remove_box["x"] > invite_add_box["x"] + invite_add_box["width"] + 8
        expect(invitation_table.get_by_role("columnheader", name="Status")).to_have_count(0)
        invitation_columns = invitation_table.locator("colgroup col")
        assert invitation_columns.count() == 3
        first_column_width = invitation_columns.nth(0).evaluate(
            "element => element.getBoundingClientRect().width"
        )
        table_width = invitation_table.evaluate("element => element.getBoundingClientRect().width")
        assert abs(first_column_width / table_width - 1 / 3) < 0.01, (
            first_column_width,
            table_width,
        )
        invitation_row.get_by_role("button", name="Add", exact=True).click()
        granted_row = authorized_table.locator("tbody tr").filter(
            has_text="new-invitee@example.test"
        )
        expect(granted_row).to_be_visible()
        if invitation_row.count():
            raise AssertionError(admin_invitation_requests)
        expect(invitation_row).to_have_count(0)
        removed_invitation = admin_dialog.locator(".admin-invitation-table tbody tr").filter(
            has_text="remove-invitee@example.test"
        )
        removed_invitation.get_by_role("button", name="Remove", exact=True).click()
        expect(removed_invitation).to_have_count(0)
        admin_dialog.get_by_role("button", name="Close", exact=True).click()
        guest_mode["value"] = False
        admin_mode["value"] = False
        funding.update(remaining_usd=0)
        page.goto(origin + "/", wait_until="domcontentloaded")
        dismiss_sponsor_welcome(page)
        posts.clear()
        reload_button = page.get_by_role("button", name="Reload me!")
        expect(reload_button).to_be_visible()
        expect(page.locator(".api-connection > summary")).to_have_count(0)
        expect(reload_button).to_have_class(re.compile(r"reload-me-connection"))
        reload_button.click()
        expect(page.get_by_text("Reload requested", exact=True)).to_be_visible()
        assert len(posts) == 1 and posts[0][0].endswith("/api/cloud-auth/invitation-request")
        assert posts[0][1] == {"request_type": "reload"}, posts
        local_sponsored_mode["value"] = True
        local_connect_succeeds["value"] = False
        forced["value"] = False
        selected["mode"] = "personal"
        funding.update(remaining_usd=0.75)
        page.goto(origin + "/", wait_until="domcontentloaded")
        dismiss_sponsor_welcome(page)
        sponsored_summary = page.locator(".api-connection > summary")
        expect(sponsored_summary).to_have_attribute("aria-label", "Connect to ChatGPT")
        with page.expect_request("**/api/ai/mode") as sponsor_choice:
            sponsored_summary.click()
        assert sponsor_choice.value.method == "POST"
        assert sponsor_choice.value.post_data_json == {"mode": "sponsored"}
        expect(sponsored_summary).to_have_attribute("aria-label", "Sponsored ChatGPT; connected")
        expect(page.locator(".sponsored-allowance-tooltip")).to_contain_text(
            "Click to switch to your own ChatGPT account."
        )
        expect(page.get_by_text("MOCK AUTH · LOCAL ONLY")).to_have_count(0)
        expect(page.get_by_text("Complete sign-in in the browser.")).to_have_count(0)
        posts.clear()
        with page.expect_request("**/api/ai/auth/begin"):
            sponsored_summary.click()
        expect(sponsored_summary).to_have_attribute("aria-label", "Sponsored ChatGPT; connected")
        assert not any(
            path.endswith("/api/ai/mode") and body.get("mode") == "personal" for path, body in posts
        ), posts
        local_connect_succeeds["value"] = True
        posts.clear()
        with page.expect_request("**/api/ai/auth/begin"):
            sponsored_summary.click()
        expect(sponsored_summary).to_have_attribute("aria-label", "Disconnect from ChatGPT")
        assert any(
            path.endswith("/api/ai/mode") and body.get("mode") == "personal" for path, body in posts
        ), posts

        selected["mode"] = "sponsored"
        local_sponsor_reauth["value"] = True
        local_connect_succeeds["value"] = True
        page.reload(wait_until="domcontentloaded")
        sponsored_summary = page.locator(".api-connection > summary")
        expect(sponsored_summary).to_have_attribute("aria-label", "Sponsored ChatGPT")
        expect(page.locator(".sponsored-allowance-tooltip")).to_contain_text(
            "Click to reconnect SIGMA-sponsored ChatGPT"
        )
        posts.clear()
        with page.expect_request("**/api/ai/sponsor-auth/begin"):
            page.get_by_role("button", name="Sponsored allowance details").click()
        expect(sponsored_summary).to_have_attribute("aria-label", "Sponsored ChatGPT; connected")
        assert any(path.endswith("/api/ai/sponsor-auth/begin") for path, _ in posts), posts
        expect(page.locator(".connection-pill-message")).to_have_count(0)

        admin_mode["value"] = True
        selected["mode"] = "sponsored"
        page.goto(origin + "/", wait_until="domcontentloaded")
        dismiss_sponsor_welcome(page)
        expect(page.locator("#invitation-welcome-dialog")).to_have_count(0)
        page.get_by_role("link", name="Administrator settings").click()
        admin_dialog = page.get_by_role("dialog", name="Administrator Settings")
        with page.expect_request("**/api/ai/sponsor-auth/begin"):
            admin_dialog.get_by_role("button", name="Reconnect sponsor ChatGPT").click()
        expect(admin_dialog).to_be_visible()
        admin_dialog.get_by_role("button", name="Close", exact=True).click()
        admin_mode["value"] = False

        sponsored_test_mode["value"] = True
        selected["mode"] = "sponsored"
        page.goto(origin + "/", wait_until="domcontentloaded")
        dismiss_sponsor_welcome(page)
        sponsored_summary = page.locator(".api-connection > summary")
        expect(sponsored_summary.locator(".sponsored-allowance-inline")).to_have_text("$0.75")
        expect(page.get_by_text("MOCK AUTH · LOCAL ONLY")).to_be_visible()
        expect(sponsored_summary.locator(".connection-dot")).to_have_css(
            "background-color", "rgb(117, 177, 140)"
        )
        allowance = page.get_by_role("button", name="Sponsored allowance details")
        allowance.hover()
        expect(page.locator(".sponsored-allowance-tooltip")).to_contain_text(
            "This mock sponsorship and its allowance are simulated"
        )
        sponsored_summary.click()
        expect(sponsored_summary).to_have_attribute("aria-label", "Sponsored ChatGPT")
        expect(sponsored_summary.locator(".connection-dot")).to_have_css(
            "background-color", "rgb(127, 140, 150)"
        )
        page.reload(wait_until="domcontentloaded")
        sponsored_summary = page.locator(".api-connection > summary")
        expect(sponsored_summary).to_have_attribute("aria-label", "Sponsored ChatGPT; connected")
        expect(page.get_by_text("MOCK AUTH · LOCAL ONLY")).to_be_visible()
        browser.close()


if __name__ == "__main__":
    main()
