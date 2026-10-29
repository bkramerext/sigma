"""Chromium against SIGMA's real local API with only external ChatGPT calls faked."""

from __future__ import annotations

import hashlib
import json
import os
import secrets
import socket
import subprocess
import sys
import time
import urllib.parse
import urllib.request
from datetime import UTC, datetime
from pathlib import Path
from tempfile import TemporaryDirectory

from playwright.sync_api import expect, sync_playwright

ROOT = Path(__file__).resolve().parents[1]
CHROME = os.environ.get(
    "SIGMA_BROWSER_EXECUTABLE", "/Applications/Google Chrome.app/Contents/MacOS/Google Chrome"
)
Z = "zetacontinuation@gmail.com"
N = "nontrivialzeeros@gmail.com"
UNINVITED = "new-user@example.org"


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
        guest_subject = "google-subject-uninvited"
        guest_cookie = secrets.token_urlsafe(32)
        db.execute(
            "INSERT OR REPLACE INTO identities(subject,email,updated_at) VALUES(?,?,?)",
            (guest_subject, UNINVITED, cloud_auth._now()),
        )
        db.execute(
            "INSERT OR REPLACE INTO sessions(token_hash,subject,email,expires_at) VALUES(?,?,?,?)",
            (cloud_auth._hash(guest_cookie), guest_subject, UNINVITED, cloud_auth._now() + 3600),
        )
        session_cookies[UNINVITED] = guest_cookie

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
                        "INSERT INTO calls(call_id,session_id,workspace_id,amount_usd,status,token_reservation,input_tokens,output_tokens,created_at,updated_at) VALUES(?,?,?,0.25,'usage_estimated',0,0,0,?,?)",
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
                    "0.00", timeout=10000
                )
                play_attempt = page.evaluate(
                    """async () => {
                      const post = async (url, body) => { const r=await fetch(url,{method:'POST',headers:{'Content-Type':'application/json'},body:JSON.stringify(body)}); return {status:r.status,body:await r.json()}; };
                      const created = await post('/api/projects/create',{title:'Zero allowance browser regression '+crypto.randomUUID(),problem:'Verify budget admission before sponsored Play.'});
                      if (created.status !== 201) return {stage:'create',...created};
                      const path=created.body.path, project=created.body.project;
                      const strategy = await post('/api/projects/strategies',{path,title:'Check admission',approach:'Attempt the session only after budget admission.'});
                      if (strategy.status !== 201) return {stage:'strategy',...strategy};
                      const strategiesResponse=await fetch('/api/projects/strategies?'+new URLSearchParams({path}));
                      const strategyId=(await strategiesResponse.json()).strategies[0].id;
                      const [configResponse,limitsResponse]=await Promise.all([
                        fetch('/api/projects/proposals/config?'+new URLSearchParams({path})),
                        fetch('/api/projects/research-limits?'+new URLSearchParams({path}))
                      ]);
                      const config=await configResponse.json(), limits=await limitsResponse.json();
                      return await post('/api/projects/research-sessions/start',{
                        path,strategy_id:strategyId,strategy_ids:[strategyId],
                        idempotency_key:crypto.randomUUID(),expected_project_id:project.id,
                        expected_binding:config.binding,expected_limits:limits
                      });
                    }"""
                )
                assert play_attempt["status"] in {400, 409, 503}, play_attempt
                assert any(
                    word in json.dumps(play_attempt).casefold()
                    for word in ("allowance", "budget", "ceiling")
                ), play_attempt
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
                    "0.00" not in member_pill.inner_text()
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
                invitation_posts: list[dict] = []
                page.route(
                    "**/api/cloud-auth/invitation-request",
                    lambda route: (
                        invitation_posts.append(route.request.post_data_json or {}),
                        route.fulfill(
                            status=200,
                            content_type="application/json",
                            body='{"status":"notified","duplicate":false}',
                        ),
                    ),
                )
                page.get_by_role("button", name="Invite me!").click()
                invitation_dialog = page.get_by_role("dialog", name="Request an invitation")
                invitation_dialog.get_by_role("button", name="Invite me").click()
                expect(invitation_dialog.locator('[role="status"]')).to_contain_text(
                    "Your invitation request is recorded and awaiting administrator review."
                )
                expect(page.get_by_role("button", name="Invite me!")).to_have_count(0)
                assert invitation_posts == [{}], invitation_posts
                browser.close()
            print(
                "PASS local Chromium ↔ real SIGMA API: same-email personal/sponsor OAuth, persistence, server restart, member privacy, zero-budget Play denial, and authenticated uninvited-user invitation UI"
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
