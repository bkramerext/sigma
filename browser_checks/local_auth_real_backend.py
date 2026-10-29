"""Chromium against SIGMA's real local API with only external ChatGPT calls faked."""

from __future__ import annotations

import hashlib
import json
import os
import re
import secrets
import socket
import subprocess
import sys
import time
import urllib.parse
import urllib.request
from datetime import UTC, datetime
from http.cookies import SimpleCookie
from pathlib import Path
from tempfile import TemporaryDirectory
from uuid import uuid4

from playwright.sync_api import expect, sync_playwright

ROOT = Path(__file__).resolve().parents[1]
CHROME = os.environ.get(
    "SIGMA_BROWSER_EXECUTABLE", "/Applications/Google Chrome.app/Contents/MacOS/Google Chrome"
)
Z = "zetacontinuation@gmail.com"
N = "nontrivialzeeros@gmail.com"
UNINVITED = "new-user@example.org"
UNINVITED_OTHER = "another-new-user@example.org"
RETURNING = "returning-member@example.org"


def free_port() -> int:
    with socket.socket() as sock:
        sock.bind(("127.0.0.1", 0))
        return int(sock.getsockname()[1])


def wait_url(url: str, process: subprocess.Popen, log: Path) -> None:
    import urllib.error

    deadline = time.monotonic() + 20
    while time.monotonic() < deadline:
        if process.poll() is not None:
            raise AssertionError(f"server exited: {log.read_text(errors='replace')}")
        try:
            urllib.request.urlopen(url, timeout=0.5).close()
            return
        except (OSError, urllib.error.URLError):
            time.sleep(0.1)
    raise AssertionError(f"server did not start: {log.read_text(errors='replace')}")


def seed_state(auth_home: Path, credential_home: Path) -> dict[str, str]:
    from sigma import ai_store, chatgpt_auth, cloud_auth

    cfg = cloud_auth.config()
    assert cfg.enabled and cfg.local and cfg.database
    subjects = {
        Z: "google-subject-z",
        "brian.kramer.personal@gmail.com": "google-subject-b",
        N: "google-subject-n",
    }
    session_cookies: dict[str, str] = {}
    with cloud_auth._db(cfg) as db:
        db.execute(
            "INSERT OR REPLACE INTO bootstrap_subject(email,subject) VALUES(?,?)", (Z, subjects[Z])
        )
        for email, subject in subjects.items():
            role = "member" if email == N else "admin"
            allowance = 0.25 if email == N else None
            db.execute(
                "INSERT OR REPLACE INTO grants(kind,value,role,active,updated_at,allowance_usd) VALUES('email',?,?,1,?,?)",
                (email, role, cloud_auth._now(), allowance),
            )
            db.execute(
                "INSERT OR REPLACE INTO identities(subject,email,updated_at) VALUES(?,?,?)",
                (subject, email, cloud_auth._now()),
            )
            db.execute(
                """INSERT OR REPLACE INTO user_state(subject,email,role,access_active,workspace_id,
                   sponsorship_eligible,model_access,model_access_selected,model_connection_status,updated_at)
                   VALUES(?,?,?,1,NULL,1,?,?, 'connected',?)""",
                (
                    subject,
                    email,
                    role,
                    "personal" if email == Z else "sponsored",
                    1,
                    cloud_auth._now(),
                ),
            )
            raw = secrets.token_urlsafe(32)
            db.execute(
                "INSERT OR REPLACE INTO sessions(token_hash,subject,email,expires_at) VALUES(?,?,?,?)",
                (cloud_auth._hash(raw), subject, email, cloud_auth._now() + 3600),
            )
            session_cookies[email] = raw
        for email, guest_subject in (
            (UNINVITED, "google-subject-uninvited"),
            (UNINVITED_OTHER, "google-subject-uninvited-other"),
            (RETURNING, "google-subject-returning"),
        ):
            guest_cookie = secrets.token_urlsafe(32)
            db.execute(
                "INSERT OR REPLACE INTO identities(subject,email,updated_at) VALUES(?,?,?)",
                (guest_subject, email, cloud_auth._now()),
            )
            db.execute(
                "INSERT OR REPLACE INTO sessions(token_hash,subject,email,expires_at) VALUES(?,?,?,?)",
                (cloud_auth._hash(guest_cookie), guest_subject, email, cloud_auth._now() + 3600),
            )
            session_cookies[email] = guest_cookie
        returning_subject = "google-subject-returning"
        db.execute(
            "INSERT OR REPLACE INTO grants(kind,value,role,active,updated_at) VALUES('email',?,'member',0,?)",
            (RETURNING, cloud_auth._now()),
        )
        db.execute(
            "INSERT OR REPLACE INTO user_state(subject,email,role,access_active,workspace_id,sponsorship_eligible,model_access,updated_at) VALUES(?,?,'member',0,NULL,0,'personal',?)",
            (returning_subject, RETURNING, cloud_auth._now()),
        )
        db.execute(
            "INSERT OR REPLACE INTO invitation_requests(subject,email,requested_at,status,request_type) VALUES(?,?,?,'reviewed','invitation')",
            (returning_subject, RETURNING, cloud_auth._now() - 3600),
        )
        db.execute(
            "INSERT INTO feedback_requests(id,subject,account_email,contact_email,message,submitted_at,status) VALUES(?,?,?,?,?,?,'new')",
            (
                "f" * 32,
                "google-subject-n",
                N,
                "contact-provided@example.org",
                "Signed-in feedback fixture message",
                cloud_auth._now() - 20,
            ),
        )
        db.execute(
            "INSERT INTO feedback_requests(id,subject,account_email,contact_email,message,submitted_at,status) VALUES(?,NULL,NULL,?,?,?,'new')",
            (
                "a" * 32,
                "anonymous-contact@example.org",
                "Anonymous feedback fixture message",
                cloud_auth._now() - 10,
            ),
        )

    account_template = {
        "client_id": "fixture-chatgpt-client",
        "subject": "same-chatgpt-subject-z",
        "email": Z,
        "refresh_token": "seed-refresh",
        "id_token": "seed-id",
        "expires_at": time.time() + 3600,
        "earliest_refresh_at": 0,
        "scopes": sorted(
            chatgpt_auth.PLAN_SCOPES | {"openid", "profile", "email", "offline_access"}
        ),
        "token_type": "Bearer",
        "saved_at": datetime.now(UTC).isoformat(),
    }
    sponsor = account_template | {"access_token": "sponsor-seed-access"}
    personal = account_template | {"access_token": "personal-seed-access"}

    async def seed_stores() -> None:
        async with ai_store.sponsor_transaction() as state:
            state["accounts"] = {"sponsor-z": sponsor}
            state["active"] = "sponsor-z"
        principal = cloud_auth.Principal(subjects[Z], Z, "admin")
        token = cloud_auth._CURRENT_PRINCIPAL.set(principal)
        try:
            async with ai_store.transaction() as state:
                state["accounts"] = {"personal-z": personal}
                state["active"] = "personal-z"
                state["mode"] = "chatgpt"
        finally:
            cloud_auth._CURRENT_PRINCIPAL.reset(token)

    import asyncio

    asyncio.run(seed_stores())
    return session_cookies


def main() -> None:
    api_port, web_port = free_port(), free_port()
    origin = f"http://127.0.0.1:{web_port}"
    with TemporaryDirectory(prefix="sigma-local-auth-browser-") as temp:
        root = Path(temp)
        auth_db = root / "auth-db"
        auth_db.mkdir(mode=0o700)
        credential_home = root / "credentials"
        credential_home.mkdir(mode=0o700)
        project_home = root / "projects"
        project_home.mkdir(mode=0o700)
        workspace_home = root / "workspaces"
        workspace_home.mkdir(mode=0o700)
        audit = root / "provider-audit.log"
        audit.touch(mode=0o600)
        env = os.environ.copy()
        env.update(
            {
                "SIGMA_CLOUD_AUTH_ENABLED": "true",
                "SIGMA_CLOUD_AUTH_LOCAL": "true",
                "SIGMA_CLOUD_PUBLIC_ORIGIN": origin,
                "SIGMA_CLOUD_AUTH_HOME": str(auth_db),
                "SIGMA_AUTH_HOME": str(credential_home),
                "SIGMA_PROJECTS_ROOT": str(project_home),
                "SIGMA_CLOUD_WORKSPACES_ROOT": str(workspace_home),
                "SIGMA_CLOUD_ADMIN_CONTACT_EMAIL": Z,
                "GOOGLE_OIDC_CLIENT_ID": "fixture-google-client",
                "GOOGLE_OIDC_CLIENT_SECRET": "fixture-google-secret",
                "SIGMA_CLOUD_GLOBAL_SPEND_CEILING_USD": "50",
                "SIGMA_CLOUD_USER_SPEND_CEILING_USD": "5",
                "SIGMA_CLOUD_INFERENCE_PROVIDER": "chatgpt",
                "SIGMA_TEST_PROVIDER_AUDIT": str(audit),
                "SIGMA_CLOUD_SPONSOR_EMAIL": "",
                "SIGMA_LOCAL_SPONSORED_TEST_MODE": "",
                "SIGMA_API_TARGET": f"http://127.0.0.1:{api_port}",
                "PYTHONPATH": os.pathsep.join(
                    (str(ROOT / "tests"), str(ROOT / "src"), env.get("PYTHONPATH", ""))
                ),
            }
        )
        os.environ.update(
            {
                key: val
                for key, val in env.items()
                if key.startswith(("SIGMA_CLOUD_", "SIGMA_AUTH_HOME", "GOOGLE_OIDC_"))
            }
        )
        # Keep fixture database/config initialization in this process, then let
        # the API run in a separate process against the same durable files.
        cookies = seed_state(auth_db, credential_home)
        session_subjects = {
            cookies[N]: "google-subject-n",
            cookies[UNINVITED]: "google-subject-uninvited",
            cookies[UNINVITED_OTHER]: "google-subject-uninvited-other",
            cookies[RETURNING]: "google-subject-returning",
        }
        email_by_cookie = {cookie: email for email, cookie in cookies.items()}
        frontend = subprocess.Popen(
            [
                str(ROOT / "frontend/node_modules/.bin/vite"),
                "--host",
                "127.0.0.1",
                "--port",
                str(web_port),
                "--strictPort",
            ],
            cwd=ROOT / "frontend",
            env=env,
            stdout=subprocess.DEVNULL,
            stderr=subprocess.DEVNULL,
        )
        api_log = root / "api.log"

        def start_api() -> subprocess.Popen:
            handle = api_log.open("ab")
            process = subprocess.Popen(
                [
                    sys.executable,
                    "-m",
                    "uvicorn",
                    "chatgpt_oauth_browser_server:app",
                    "--host",
                    "127.0.0.1",
                    "--port",
                    str(api_port),
                    "--log-level",
                    "error",
                ],
                cwd=ROOT,
                env=env,
                stdout=handle,
                stderr=subprocess.STDOUT,
            )
            wait_url(f"http://127.0.0.1:{api_port}/api/ui-instance", process, api_log)
            return process

        api = None
        try:
            wait_url(origin, frontend, root / "frontend.log")
            api = start_api()
            with sync_playwright() as playwright:
                browser = playwright.chromium.launch(executable_path=CHROME, headless=True)
                context = browser.new_context()
                page = context.new_page()
                requests: list[tuple[str, str]] = []
                responses: list[tuple[str, int]] = []
                page.on(
                    "request",
                    lambda req: requests.append((req.method, urllib.parse.urlsplit(req.url).path)),
                )
                page.on(
                    "response",
                    lambda resp: responses.append(
                        (urllib.parse.urlsplit(resp.url).path, resp.status)
                    ),
                )

                def login_cookie(email: str) -> None:
                    context.clear_cookies()
                    context.add_cookies(
                        [
                            {
                                "name": "sigma_session",
                                "value": cookies[email],
                                "url": origin,
                                "httpOnly": True,
                                "sameSite": "Lax",
                            }
                        ]
                    )

                oauth_code = {"value": 0}
                completed_states: set[str] = set()

                def external_boundary(request) -> None:
                    parsed = urllib.parse.urlsplit(request.url)
                    if parsed.hostname != "auth.openai.com":
                        return
                    query = urllib.parse.parse_qs(parsed.query)
                    if "state" not in query or "redirect_uri" not in query:
                        return
                    state = query["state"][0]
                    if state in completed_states:
                        return
                    completed_states.add(state)
                    callback = query["redirect_uri"][0]
                    oauth_code["value"] += 1
                    params = urllib.parse.urlencode(
                        {
                            "state": query["state"][0],
                            "code": f"browser-oauth-{oauth_code['value']}",
                            "client_id": "fixture-chatgpt-client",
                        }
                    )
                    result = urllib.request.urlopen(callback + "?" + params, timeout=5)
                    assert result.status == 200 and b"Return to SIGMA" in result.read()

                context.on("request", external_boundary)

                invitation_posts: list[dict] = []

                def record_invitation(route) -> None:
                    request_body = route.request.post_data_json or {}
                    invitation_posts.append(request_body)
                    response = route.fetch(max_redirects=0)
                    # SMTP is deliberately unconfigured in this fixture. The
                    # real endpoint accepts the durable request as pending so
                    # the UI does not prompt for a duplicate submission.
                    assert response.status == 200, response.status
                    assert response.json() == {"status": "pending", "duplicate": False}
                    from sigma import cloud_auth

                    request_type = request_body.get("request_type", "invitation")
                    request_cookies = SimpleCookie(route.request.headers.get("cookie", ""))
                    session_cookie = request_cookies.get("sigma_session")
                    assert session_cookie is not None
                    subject = (
                        "google-subject-n"
                        if request_type == "reload"
                        else session_subjects[session_cookie.value]
                    )
                    cfg = cloud_auth.config()
                    with cloud_auth._db(cfg) as db:
                        row = db.execute(
                            "SELECT status,email,request_type,notification_error FROM invitation_requests WHERE subject=?",
                            (subject,),
                        ).fetchone()
                        expected_email = (
                            N if request_type == "reload" else email_by_cookie[session_cookie.value]
                        )
                        assert row is not None and row["email"] == expected_email, row
                        assert row["request_type"] == request_type, row
                        assert row["status"] == "pending", row
                        assert row["notification_error"] == "delivery failed", row
                    route.fulfill(response=response)

                page.route("**/api/cloud-auth/invitation-request", record_invitation)

                # Exercise the visible Google pill itself, including the
                # real local API redirect. Stop at a deterministic OAuth
                # authorization page so the browser test never contacts Google.
                page.goto(origin, wait_until="domcontentloaded")
                welcome = page.get_by_role("dialog", name="Welcome to SIGMA!")
                expect(welcome).to_be_visible()

                oauth_redirects: list[str] = []

                def login_redirect_fixture(route) -> None:
                    response = route.fetch(max_redirects=0)
                    assert response.status == 302, response.status
                    location = response.headers.get("location", "")
                    parsed = urllib.parse.urlsplit(location)
                    query = urllib.parse.parse_qs(parsed.query)
                    assert parsed.scheme == "https" and parsed.hostname == "accounts.google.com", (
                        location
                    )
                    assert parsed.path == "/o/oauth2/v2/auth", location
                    assert query.get("client_id") == ["fixture-google-client"], query
                    assert query.get("response_type") == ["code"], query
                    assert query.get("code_challenge_method") == ["S256"], query
                    oauth_redirects.append(location)
                    route.fulfill(
                        response=response,
                        status=200,
                        content_type="text/html",
                        body=("<title>Deterministic Google OAuth fixture</title>"),
                    )

                page.route("**/api/cloud-auth/login**", login_redirect_fixture)

                welcome_sign_in = welcome.get_by_role("link", name="Sign in with Google")
                expect(welcome_sign_in).to_be_visible()
                assert welcome_sign_in.get_attribute("href") == "/api/cloud-auth/login"
                requests.clear()
                with page.expect_navigation(url=re.compile(r"/api/cloud-auth/login")):
                    welcome_sign_in.click()
                assert ("GET", "/api/cloud-auth/login") in requests, requests
                assert len(oauth_redirects) == 1, oauth_redirects
                assert urllib.parse.urlsplit(page.url).path == "/api/cloud-auth/login"
                assert "Deterministic Google OAuth fixture" in page.title()

                page.goto(origin, wait_until="domcontentloaded")
                page.evaluate("sessionStorage.setItem('sigma.guestWelcomeDismissed', 'true')")
                page.reload(wait_until="domcontentloaded")
                google_sign_in = page.locator(".home-auth-pills .project-google-signin").filter(
                    has_text="Sign in with Google"
                )
                expect(google_sign_in).to_be_visible()
                assert google_sign_in.get_attribute("href") == "/api/cloud-auth/login"
                requests.clear()
                with page.expect_navigation(url=re.compile(r"/api/cloud-auth/login")):
                    google_sign_in.click()
                assert ("GET", "/api/cloud-auth/login") in requests, requests
                assert len(oauth_redirects) == 2, oauth_redirects
                assert urllib.parse.urlsplit(page.url).path == "/api/cloud-auth/login"
                assert "Deterministic Google OAuth fixture" in page.title()

                page.goto(origin, wait_until="domcontentloaded")
                login_cookie(Z)
                page.goto(origin, wait_until="domcontentloaded")
                google = page.locator(".identity-pill-stack .project-google-signin").first
                expect(google).to_have_text("Sign out of Google")
                pill = page.locator(".api-connection > summary")
                expect(pill.get_by_role("status")).to_have_text("ChatGPT connected")
                expect(pill).not_to_contain_text("Unlimited")
                assert pill.get_attribute("title") == (
                    "ChatGPT is connected. Click to return to sponsorship."
                )
                # The persistent existing cookie held an intentional personal
                # selection even though personal and sponsor ChatGPT emails match.
                status = page.evaluate(
                    "async () => (await (await fetch('/api/cloud-auth/status')).json()).account"
                )
                assert status["model_access"]["mode"] == "personal", status

                requests.clear()
                pill.click()
                expect(pill.get_by_role("status")).to_have_text("Sponsored ChatGPT")
                expect(pill.locator(".sponsored-allowance-inline")).to_have_text("Unlimited")
                assert ("POST", "/api/ai/disconnect") in requests, requests
                assert ("POST", "/api/ai/mode") in requests, requests
                pill.hover(position={"x": 25, "y": 15})
                assert pill.get_attribute("title") == (
                    "Sponsor Connected · zetacontinuation@gmail.com · Unlimited. "
                    "Click to connect your own ChatGPT account."
                )
                detail = page.locator(".sponsored-allowance-trigger")
                assert detail.get_attribute("title") == "Click to show sponsorship details."
                requests.clear()
                detail.click()
                expect(detail).to_have_attribute("aria-expanded", "true")
                assert not requests, requests
                detail.click()
                requests.clear()
                with page.expect_popup() as popup_info:
                    pill.click(position={"x": 24, "y": 14})
                popup_info.value.wait_for_timeout(100)
                expect(pill.get_by_role("status")).to_have_text("ChatGPT connected", timeout=15000)
                assert ("POST", "/api/ai/auth/begin") in requests, requests
                assert not any(path == "/api/ai/sponsor-auth/begin" for _, path in requests), (
                    requests
                )
                assert (
                    page.evaluate(
                        "async () => (await (await fetch('/api/cloud-auth/status')).json()).account.model_access.mode"
                    )
                    == "personal"
                )
                assert "Unlimited" not in pill.inner_text()
                personal_path = (
                    credential_home
                    / "personal-users"
                    / hashlib.sha256(b"sigma-cloud-workspace-v1\0google-subject-z").hexdigest()
                    / "credentials.json"
                )
                assert (
                    json.loads(personal_path.read_text())["accounts"]["personal-z"]["access_token"]
                    == "fixture-access-browser-oauth-1"
                )
                sponsor_path = credential_home / "credentials.json"
                assert (
                    json.loads(sponsor_path.read_text())["accounts"]["sponsor-z"]["access_token"]
                    == "sponsor-seed-access"
                )

                # Exercise sponsor maintenance through its distinct admin route;
                # callback completion must persist to the shared store only.
                response = page.evaluate(
                    "async () => { const r = await fetch('/api/ai/sponsor-auth/begin',{method:'POST',headers:{'Content-Type':'application/json'},body:'{}'}); return {status:r.status,body:await r.json()}; }"
                )
                assert response["status"] == 200, response
                assert ("POST", "/api/ai/sponsor-auth/begin") in requests, requests
                requests.clear()
                # Open through SIGMA's one-use redirect so the test covers the
                # actual HTTP authorization handoff and local callback listener.
                with page.expect_popup() as sponsor_popup:
                    page.evaluate(
                        "url => window.open(url, '_blank')",
                        origin + response["body"]["authorization_url"],
                    )
                sponsor_popup.value.wait_for_timeout(100)
                assert (
                    json.loads(sponsor_path.read_text())["accounts"]["sponsor-z"]["access_token"]
                    == "fixture-access-browser-oauth-2"
                )
                assert (
                    json.loads(personal_path.read_text())["accounts"]["personal-z"]["access_token"]
                    == "fixture-access-browser-oauth-1"
                )

                # This is a real server restart, not a new TestClient. The same
                # auth DB, credential home, and browser cookie remain in use.
                api.terminate()
                api.wait(timeout=10)
                api = start_api()
                page.reload(wait_until="domcontentloaded")
                expect(
                    page.locator(".api-connection > summary").get_by_role("status")
                ).to_have_text("ChatGPT connected")
                restarted = page.evaluate(
                    "async () => { const s=await (await fetch('/api/cloud-auth/status')).json(); const c=await (await fetch('/api/ai/connection?refresh=true')).json(); return {email:s.user.email,mode:s.account.model_access.mode,connection:c}; }"
                )
                assert restarted["email"] == Z and restarted["mode"] == "personal", restarted
                assert restarted["connection"]["account_label"] == Z, restarted
                assert (
                    json.loads(sponsor_path.read_text())["accounts"]["sponsor-z"]["access_token"]
                    == "fixture-access-browser-oauth-2"
                )

                login_cookie(N)
                page.reload(wait_until="domcontentloaded")
                member_pill = page.locator(".api-connection > summary")
                expect(member_pill.get_by_role("status")).to_have_text("Sponsored ChatGPT")
                expect(member_pill).not_to_contain_text("Unlimited")
                member_status = page.evaluate(
                    "async () => { const r=await fetch('/api/ai/connection?refresh=true'); return {status:r.status,body:await r.json()}; }"
                )
                assert member_status["status"] == 200 and Z not in json.dumps(
                    member_status["body"]
                ), member_status
                member_mode = page.evaluate(
                    "async () => { const r=await fetch('/api/ai/mode',{method:'POST',headers:{'Content-Type':'application/json'},body:JSON.stringify({mode:'sponsored'})}); return {status:r.status,body:await r.json()}; }"
                )
                assert member_mode["status"] == 200 and Z not in json.dumps(member_mode["body"]), (
                    member_mode
                )
                assert Z not in (member_pill.get_attribute("title") or "")
                assert Z not in (member_pill.get_attribute("aria-label") or "")
                member_pill.hover(position={"x": 25, "y": 15})
                assert Z not in (member_pill.get_attribute("title") or "")
                member_details = page.locator(".sponsored-allowance-trigger")
                assert member_details.get_attribute("title") == "Click to show sponsorship details."
                requests.clear()
                member_details.click()
                expect(member_details).to_have_attribute("aria-expanded", "true")
                details_text = page.locator("#sponsored-allowance-tooltip").inner_text()
                assert Z not in details_text
                assert not requests, requests
                from sigma import cloud_research, cloud_workspaces

                workspace = cloud_workspaces.workspace_for_subject("google-subject-n")
                assert workspace is not None
                now = cloud_research._now()
                session_id, idempotency = "fixture-zero-allowance-session", secrets.token_hex(16)
                with cloud_research._connect() as db:
                    db.execute(
                        "INSERT INTO jobs(session_id,workspace_id,project_id,idempotency_key,status,created_at,updated_at) VALUES(?,?,?,?,'terminal',?,?)",
                        (
                            session_id,
                            workspace.workspace_id,
                            "fixture-project",
                            idempotency,
                            now,
                            now,
                        ),
                    )
                    db.execute(
                        "INSERT INTO calls(call_id,session_id,workspace_id,amount_usd,status,token_reservation,input_tokens,output_tokens,created_at,updated_at) VALUES(?,?,?,0.22,'usage_estimated',0,0,0,?,?)",
                        (
                            "fixture-zero-allowance-call",
                            session_id,
                            workspace.workspace_id,
                            now,
                            now,
                        ),
                    )
                page.reload(wait_until="domcontentloaded")
                member_pill = page.locator(".api-connection > summary")
                # The member's exhausted allowance blocks real sponsored Play,
                # while the Sponsored ChatGPT pill still starts personal OAuth.
                assert member_pill.get_by_role("status").inner_text() == "Sponsored ChatGPT"
                expect(member_pill.locator(".sponsored-allowance-inline")).to_have_text(
                    "0.03", timeout=10000
                )
                reload_button = page.get_by_role("button", name="Reload me!")
                expect(reload_button).to_be_visible()
                reload_button.click()
                expect(page.get_by_text("Reload requested", exact=True)).to_be_visible()
                assert invitation_posts == [{"request_type": "reload"}], invitation_posts
                requests.clear()
                with page.expect_popup() as member_personal_popup:
                    member_pill.click(position={"x": 25, "y": 14})
                member_personal_popup.value.wait_for_timeout(100)
                expect(member_pill.get_by_role("status")).to_have_text(
                    "ChatGPT connected", timeout=15000
                )
                assert ("POST", "/api/ai/auth/begin") in requests, requests
                assert not any(path == "/api/ai/sponsor-auth/begin" for _, path in requests), (
                    requests
                )
                assert (
                    "0.03" not in member_pill.inner_text()
                    and "Unlimited" not in member_pill.inner_text()
                )
                selected_member = page.evaluate(
                    "async () => (await (await fetch('/api/cloud-auth/status')).json()).account.model_access.mode"
                )
                assert selected_member == "personal", selected_member

                # The uninvited Google identity gets an authenticated local
                # guest session and an invitation request path, while research
                # execution remains denied by the actual API middleware.
                login_cookie(UNINVITED)
                page.reload(wait_until="domcontentloaded")
                expect(
                    page.locator(".identity-pill-stack .project-google-signin").first
                ).to_have_text("Sign out of Google")
                status = page.evaluate(
                    "async () => (await (await fetch('/api/cloud-auth/status')).json())"
                )
                assert status["user"] == {"email": UNINVITED, "role": "guest"}, status
                assert not status["account"]["sponsorship"]["eligible"], status
                expect(page.get_by_role("button", name="Invite me!")).to_be_visible()
                assert page.locator(".api-connection").count() == 0
                page.get_by_role("button", name="Invite me!").click()
                invitation_dialog = page.get_by_role("dialog", name="Request an invitation")
                invitation_dialog.get_by_role("button", name="Invite me").click()
                expect(invitation_dialog.locator('[role="status"]')).to_contain_text(
                    "Your invitation request is recorded and awaiting administrator review."
                )
                expect(page.get_by_role("button", name="Invite me!")).to_have_count(0)
                assert invitation_posts == [{"request_type": "reload"}, {}], invitation_posts

                # A historical reviewed request does not suppress a fresh
                # request after its member grant has been revoked.
                login_cookie(RETURNING)
                page.reload(wait_until="domcontentloaded")
                returning_status = page.evaluate(
                    "async () => (await (await fetch('/api/cloud-auth/status')).json())"
                )
                assert returning_status["user"] == {"email": RETURNING, "role": "guest"}, (
                    returning_status
                )
                assert returning_status["account"]["invitation_status"] == "reviewed", (
                    returning_status
                )
                expect(page.get_by_role("button", name="Invite me!")).to_be_visible()
                page.get_by_role("button", name="Invite me!").click()
                returning_dialog = page.get_by_role("dialog", name="Request an invitation")
                returning_dialog.get_by_role("button", name="Invite me").click()
                expect(returning_dialog.locator('[role="status"]')).to_contain_text(
                    "Your invitation request is recorded and awaiting administrator review."
                )
                assert invitation_posts == [{"request_type": "reload"}, {}, {}], invitation_posts

                # Exercise authenticated guest workspace ownership through the
                # real API subprocess. The browser keeps the first guest cookie
                # while its verified Google session changes to a second guest.
                login_cookie(UNINVITED)
                page.reload(wait_until="domcontentloaded")
                owned_project = page.evaluate(
                    """async () => {
                      const catalog = await fetch('/api/projects/samples').then(r => r.json());
                      const sample = catalog.projects[0];
                      const opened = await fetch('/api/projects/samples/open', {
                        method: 'POST', headers: {'Content-Type':'application/json'},
                        body: JSON.stringify({sample_id: sample.id})
                      });
                      return {status: opened.status, project: await opened.json()};
                    }"""
                )
                assert owned_project["status"] == 200, owned_project
                guest_project_path = owned_project["project"]["path"]
                guest_project_id = owned_project["project"]["project"]["id"]
                from sigma import project_bundle

                def write_guest_member(relative: str, contents: bytes) -> None:
                    guest_project = Path(guest_project_path)
                    if guest_project.is_dir():
                        target = guest_project / relative
                        target.parent.mkdir(mode=0o700, parents=True, exist_ok=True)
                        target.write_bytes(contents)
                    else:
                        project_bundle.write_file(guest_project_path, relative, contents)

                guest_session_id = str(uuid4())
                write_guest_member(
                    f"research-sessions/{guest_session_id}.json",
                    json.dumps(
                        {
                            "id": guest_session_id,
                            "project_path": str(Path(guest_project_path).resolve()),
                            "project_id": guest_project_id,
                            "session_number": 1,
                            "status": "ended",
                            "message": "guest workspace identity fixture",
                            "steps": [],
                        }
                    ).encode(),
                )
                guest_execution_id = str(uuid4())
                guest_artifact = b"identity-private artifact"
                write_guest_member(
                    f"research-executions/{guest_execution_id}.json",
                    json.dumps(
                        {
                            "id": guest_execution_id,
                            "project_id": guest_project_id,
                            "status": "completed",
                            "created_at": datetime.now(UTC).isoformat(),
                            "artifacts": [
                                {
                                    "filename": "identity.txt",
                                    "media_type": "text/plain",
                                    "size_bytes": len(guest_artifact),
                                    "sha256": hashlib.sha256(guest_artifact).hexdigest(),
                                }
                            ],
                        }
                    ).encode(),
                )
                write_guest_member(
                    f"research-executions/{guest_execution_id}.artifacts/identity.txt",
                    guest_artifact,
                )
                guest_cookie = next(
                    item for item in context.cookies(origin) if item["name"].endswith("sigma_guest")
                )
                old_guest_cookie_value = guest_cookie["value"]
                owned_reads = page.evaluate(
                    """async ({path, sessionId, executionId}) => {
                      const urls = [
                        '/api/projects/inspect?' + new URLSearchParams({path}),
                        '/api/projects/research-sessions/' + sessionId + '?' + new URLSearchParams({path}),
                        '/api/projects/research-executions/' + executionId + '/artifacts/identity.txt?' + new URLSearchParams({path})
                      ];
                      const results = [];
                      for (const url of urls) {
                        const response = await fetch(url);
                        results.push({status: response.status, headers: {
                          cache: response.headers.get('cache-control'),
                          referrer: response.headers.get('referrer-policy'),
                          nosniff: response.headers.get('x-content-type-options'),
                          csp: response.headers.get('content-security-policy')
                        }, body: await response.text()});
                      }
                      return results;
                    }""",
                    {
                        "path": guest_project_path,
                        "sessionId": guest_session_id,
                        "executionId": guest_execution_id,
                    },
                )
                assert [item["status"] for item in owned_reads] == [200, 200, 200], owned_reads
                for item in owned_reads:
                    assert item["headers"] == {
                        "cache": "no-store",
                        "referrer": "no-referrer",
                        "nosniff": "nosniff",
                        "csp": "frame-ancestors 'none'",
                    }, item
                assert owned_reads[2]["body"] == guest_artifact.decode(), owned_reads[2]

                context.add_cookies(
                    [
                        {
                            "name": "sigma_session",
                            "value": cookies[UNINVITED_OTHER],
                            "url": origin,
                            "httpOnly": True,
                            "sameSite": "Lax",
                        }
                    ]
                )
                assert (
                    next(
                        item
                        for item in context.cookies(origin)
                        if item["name"].endswith("sigma_guest")
                    )["value"]
                    == old_guest_cookie_value
                ), "The browser did not retain the first guest cookie during identity switch"
                cross_project = page.evaluate(
                    """async ({path, sessionId, executionId}) => {
                      const requests = [
                        ['/api/projects/inspect', {path}],
                        ['/api/projects/research-sessions/' + sessionId, {path}],
                        ['/api/projects/research-executions/' + executionId + '/artifacts/identity.txt', {path}]
                      ];
                      const results = [];
                      for (const [route, params] of requests) {
                        const response = await fetch(route + '?' + new URLSearchParams(params));
                        results.push({status: response.status, body: await response.text()});
                      }
                      return results;
                    }""",
                    {
                        "path": guest_project_path,
                        "sessionId": guest_session_id,
                        "executionId": guest_execution_id,
                    },
                )
                assert [item["status"] for item in cross_project] == [404, 404, 404], cross_project
                new_guest_cookie = next(
                    item for item in context.cookies(origin) if item["name"].endswith("sigma_guest")
                )
                assert new_guest_cookie["value"] != old_guest_cookie_value, (
                    "Switching Google identities reused the prior guest workspace cookie"
                )

                # Sign in as the built-in admin and verify the pending guest
                # request appears in the actual administration dialog. Approve
                # it there, then resolve the same Google session as a member.
                login_cookie(Z)
                page.goto(origin, wait_until="domcontentloaded")
                page.get_by_role("link", name="Administrator settings").click()
                admin = page.get_by_role("dialog", name="Administrator Settings")
                expect(admin).to_be_visible()
                expect(admin.locator(".admin-tabs")).to_have_count(0)
                expect(admin.locator(".admin-collapsible-section")).to_have_count(4)
                usage_section = admin.locator(".admin-account-usage-section")
                expect(usage_section).to_have_attribute("open", "")
                expect(admin.locator(".admin-usage-table")).to_be_visible()
                usage_section.locator("summary").click()
                expect(usage_section).not_to_have_attribute("open", "")
                expect(admin.locator(".admin-usage-table")).to_be_hidden()
                usage_section.locator("summary").click()
                expect(usage_section).to_have_attribute("open", "")
                header_size = admin.locator(".admin-feedback-table thead th").first.evaluate(
                    "element => parseFloat(getComputedStyle(element).fontSize)"
                )
                arrow_size = admin.locator(".admin-feedback-section summary").evaluate(
                    "element => parseFloat(getComputedStyle(element, '::before').fontSize)"
                )
                assert header_size >= 12, header_size
                assert arrow_size >= 27, arrow_size
                reload_row = admin.locator(".admin-invitation-table").get_by_role(
                    "row", name=re.compile(re.escape(N))
                )
                expect(reload_row).to_contain_text("Allowance reload request")
                invitation_row = admin.locator(".admin-invitation-table").get_by_role(
                    "row", name=re.compile(re.escape(UNINVITED))
                )
                expect(invitation_row).to_be_visible()
                returning_row = admin.locator(".admin-invitation-table").get_by_role(
                    "row", name=re.compile(re.escape(RETURNING))
                )
                expect(returning_row).to_be_visible()
                feedback_table = admin.locator(".admin-feedback-table")
                expect(feedback_table.locator("thead")).to_contain_text("Google account")
                expect(feedback_table.locator("thead")).not_to_contain_text("Contact")
                signed_feedback = feedback_table.locator("tbody tr").filter(
                    has_text="Signed-in feedback fixture message"
                )
                expect(signed_feedback.locator("td").nth(0)).to_have_text(N)
                expect(signed_feedback.locator("th")).not_to_contain_text("Signed-in account")
                expect(signed_feedback).not_to_contain_text("contact-provided@example.org")
                feedback_actions = signed_feedback.locator(".admin-feedback-actions button")
                expect(feedback_actions).to_have_count(3)
                action_colors = feedback_actions.evaluate_all(
                    "elements => elements.map(element => getComputedStyle(element).color)"
                )
                assert len(set(action_colors)) == 1, action_colors
                action_tops = feedback_actions.evaluate_all(
                    "elements => elements.map(element => element.getBoundingClientRect().top)"
                )
                assert max(action_tops) - min(action_tops) <= 2, action_tops
                anonymous_feedback = feedback_table.locator("tbody tr").filter(
                    has_text="Anonymous feedback fixture message"
                )
                expect(anonymous_feedback.locator("td").nth(0)).to_have_text("Not signed in")
                anonymous_feedback.get_by_role("button", name="Remove").click()
                expect(
                    feedback_table.locator("tbody tr").filter(
                        has_text="Anonymous feedback fixture message"
                    )
                ).to_have_count(0)
                remaining_feedback = page.evaluate(
                    "async () => (await (await fetch('/api/cloud-auth/admin/feedback')).json()).feedback"
                )
                assert all(
                    row["message"] != "Anonymous feedback fixture message"
                    for row in remaining_feedback
                ), remaining_feedback
                invitation_row.get_by_role("button", name="Add").click()
                expect(
                    admin.locator(".admin-invitation-table").get_by_role(
                        "row", name=re.compile(re.escape(UNINVITED))
                    )
                ).to_have_count(0)
                expect(
                    admin.locator(".admin-authorized-table").get_by_role(
                        "row", name=re.compile(re.escape(UNINVITED))
                    )
                ).to_be_visible()
                # Approval deliberately requires a subsequent sign-in. The
                # admin's session inventory may retire the pre-approval guest
                # session, so issue a fresh deterministic session fixture.
                from sigma import cloud_auth

                approved_session = secrets.token_urlsafe(32)
                with cloud_auth._db(cloud_auth.config()) as db:
                    db.execute(
                        "INSERT INTO sessions(token_hash,subject,email,expires_at) VALUES(?,?,?,?)",
                        (
                            cloud_auth._hash(approved_session),
                            "google-subject-uninvited",
                            UNINVITED,
                            cloud_auth._now() + 3600,
                        ),
                    )
                cookies[UNINVITED] = approved_session
                login_cookie(UNINVITED)
                approved_principal = cloud_auth.resolve_session(cookies[UNINVITED])
                with cloud_auth._db(cloud_auth.config()) as db:
                    approval_debug = {
                        "session": db.execute(
                            "SELECT subject,email,expires_at FROM sessions WHERE token_hash=?",
                            (cloud_auth._hash(cookies[UNINVITED]),),
                        ).fetchone(),
                        "grant": db.execute(
                            "SELECT value,role,active FROM grants WHERE kind='email' AND value=?",
                            (UNINVITED,),
                        ).fetchone(),
                    }
                assert approved_principal is not None and approved_principal.role == "member", (
                    approved_principal,
                    approval_debug,
                )
                page.reload(wait_until="domcontentloaded")
                approved_status = page.evaluate(
                    "async () => (await (await fetch('/api/cloud-auth/status')).json())"
                )
                assert approved_status["user"] == {"email": UNINVITED, "role": "member"}, (
                    approved_status
                )
                assert approved_status["account"]["invitation_welcome_pending"], approved_status
                invited_welcome = page.get_by_role("dialog", name="You have been invited!")
                expect(invited_welcome).to_be_visible()
                invited_welcome.get_by_role("button", name="Let's get started").click()
                expect(invited_welcome).to_have_count(0)
                assert not page.evaluate(
                    "async () => (await (await fetch('/api/cloud-auth/status')).json()).account.invitation_welcome_pending"
                )
                expect(page.get_by_role("button", name="Invite me!")).to_have_count(0)
                login_cookie(Z)
                page.reload(wait_until="domcontentloaded")
                page.get_by_role("button", name="About").click()
                about = page.get_by_role("dialog", name="About SIGMA")
                feedback = about.locator(".about-feedback-disclosure")
                feedback.locator("summary").click()
                feedback_button = feedback.get_by_role("button", name="Send Feedback")
                feedback.locator("textarea").fill("Check the action button presentation.")
                expect(feedback_button).to_be_enabled()
                action_style = feedback_button.evaluate(
                    "e => { const s=getComputedStyle(e); const r=e.getBoundingClientRect(); const t=e.closest('form').querySelector('textarea').getBoundingClientRect(); return {background:s.backgroundColor,color:s.color,decoration:s.textDecorationLine,left:r.left,textareaLeft:t.left,top:r.top,textareaBottom:t.bottom}; }"
                )
                assert action_style["background"] in {"rgba(0, 0, 0, 0)", "transparent"}, (
                    action_style
                )
                assert action_style["decoration"] == "underline", action_style
                assert action_style["color"] == "rgb(227, 180, 133)", action_style
                assert abs(action_style["left"] - action_style["textareaLeft"]) < 1, action_style
                assert action_style["top"] >= action_style["textareaBottom"], action_style
                browser.close()
            print(
                "PASS local Chromium ↔ real SIGMA API: Google sign-in, new and reviewed-request reapplication, invitation/reload admin actions, member approval, feedback identity/removal/action styling, cache headers, and cross-identity workspace isolation"
            )
        finally:
            if api is not None and api.poll() is None:
                api.terminate()
                api.wait(timeout=10)
            frontend.terminate()
            try:
                frontend.wait(timeout=5)
            except subprocess.TimeoutExpired:
                frontend.kill()
                frontend.wait(timeout=5)


if __name__ == "__main__":
    main()
