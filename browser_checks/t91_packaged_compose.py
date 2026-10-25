"""Real Chrome acceptance against the packaged Compose app, never Vite.

The test inserts ephemeral authenticated session records for two simulated
Google subjects into the disposable Compose auth database. The app's normal
cloud-auth middleware, workspace scoping, API, Nginx frontend, and Caddy edge
remain in use. This is not a Google OAuth exchange and it makes no inference
requests.
"""

from __future__ import annotations

import hashlib
import json
import os
import re
import subprocess
import tempfile
import time
from pathlib import Path

import httpx
from playwright.sync_api import Error as PlaywrightError
from playwright.sync_api import expect, sync_playwright

ROOT = Path(__file__).resolve().parents[1]
BASE_URL = os.environ.get("SIGMA_T91_BASE_URL", "http://localhost:18080").rstrip("/")
CHROME = os.environ.get(
    "SIGMA_T91_CHROME",
    os.environ.get(
        "SIGMA_BROWSER_EXECUTABLE", "/Applications/Google Chrome.app/Contents/MacOS/Google Chrome"
    ),
)
PROJECT = os.environ["SIGMA_T91_COMPOSE_PROJECT"]
COMPOSE_ENV = os.environ["SIGMA_T91_COMPOSE_ENV"]
SAMPLE = ROOT / "samples/nonconsecutive-subset-sums/project.json"
ORIGIN = "https://localhost"
MATRIX = {
    "packaged Compose SPA/API and stock sample catalog": "NOT RUN",
    "sample project copy; project and strategy edits; save/reload/reopen": "NOT RUN",
    "saved sessions, outcomes, and report download": "NOT RUN",
    "workspace survives backend container recreation": "NOT RUN",
    "user B denied user A project and saved evidence": "NOT RUN",
    "real Google OAuth": "SKIPPED — simulated sessions only; no OAuth exchange",
    "compiled PDF download": "SKIPPED — no saved PDF fixture; generation would require provider work",
    "persistent_disk storage backend from T100": "SKIPPED — this run uses Compose's default local storage configuration",
    "inference generation from T99": "SKIPPED — this workflow is read/edit/export only; no provider calls",
}

SEED_SESSIONS = r"""
import json, secrets
from sigma import cloud_auth
cfg = cloud_auth.config()
if not cfg.enabled or cfg.error or not cfg.database:
    raise SystemExit("hosted fixture configuration is not ready")
users = []
with cloud_auth._db(cfg) as db:
    for suffix in ("a", "b"):
        subject = "t91-simulated-google-subject-" + suffix
        email = "t91-user-" + suffix + "@example.test"
        raw = secrets.token_urlsafe(32)
        db.execute(
            "INSERT OR REPLACE INTO grants(kind,value,role,active,updated_at,allowance_usd) VALUES('email',?,'member',1,?,NULL)",
            (email, cloud_auth._now()),
        )
        db.execute(
            "INSERT OR REPLACE INTO identities(subject,email,updated_at) VALUES(?,?,?)",
            (subject, email, cloud_auth._now()),
        )
        db.execute(
            "INSERT OR REPLACE INTO sessions(token_hash,subject,email,expires_at) VALUES(?,?,?,?)",
            (cloud_auth._hash(raw), subject, email, cloud_auth._now() + 3600),
        )
        users.append({"suffix": suffix, "subject": subject, "email": email, "token": raw})
for user in users:
    principal = cloud_auth.resolve_session(user["token"])
    if not principal or principal.email != user["email"]:
        raise SystemExit("seeded fixture session did not resolve")
print(json.dumps(users))
"""


def compose(*args: str) -> subprocess.CompletedProcess[str]:
    command = [
        "env",
        "-u",
        "SIGMA_CLOUD_BOOTSTRAP_ADMIN_EMAIL",
        "docker",
        "compose",
        "--project-name",
        PROJECT,
        "--env-file",
        COMPOSE_ENV,
        "-f",
        str(ROOT / "deploy/compose.yaml"),
        *args,
    ]
    return subprocess.run(command, cwd=ROOT, text=True, capture_output=True, check=True)


def seed_users() -> list[dict[str, str]]:
    result = compose("exec", "-T", "backend", "python", "-c", SEED_SESSIONS)
    try:
        return json.loads(result.stdout.strip().splitlines()[-1])
    except (IndexError, json.JSONDecodeError) as error:
        raise RuntimeError("Could not read the ephemeral session fixture output") from error


def api_get(user: dict[str, str], endpoint: str, **params: str) -> httpx.Response:
    return httpx.get(
        BASE_URL + endpoint,
        params=params,
        headers={"Cookie": "__Host-sigma_session=" + user["token"]},
        timeout=15,
    )


def main() -> None:
    if not Path(CHROME).is_file():
        MATRIX["packaged Compose SPA/API and stock sample catalog"] = (
            "FAIL — installed Chrome executable not found"
        )
        raise SystemExit(1)

    MATRIX["packaged Compose SPA/API and stock sample catalog"] = "RUNNING"
    source_digest = hashlib.sha256(SAMPLE.read_bytes()).hexdigest()
    users = seed_users()
    user_a, user_b = users
    page_errors: list[str] = []
    injected_auth: list[bool] = []
    with (
        tempfile.TemporaryDirectory(prefix="sigma-t91-report-") as temporary,
        sync_playwright() as playwright,
    ):
        browser = playwright.chromium.launch(executable_path=CHROME, headless=True)
        try:

            def new_user_page(user: dict[str, str]):
                context = browser.new_context(viewport={"width": 1440, "height": 1000})
                context.set_extra_http_headers({"Cookie": "__Host-sigma_session=" + user["token"]})

                def attach_session(route):
                    headers = dict(route.request.headers)
                    if route.request.url.endswith("/api/cloud-auth/status"):
                        injected_auth.append(
                            headers.get("cookie", "") == "__Host-sigma_session=" + user["token"]
                        )
                    if route.request.method not in {"GET", "HEAD", "OPTIONS"}:
                        headers["origin"] = ORIGIN
                    response = route.fetch(headers=headers)
                    route.fulfill(response=response)

                context.route("**/api/**", attach_session)
                page = context.new_page()
                page.on("pageerror", lambda error: page_errors.append(str(error)))
                page.goto(BASE_URL + "/", wait_until="networkidle")
                status_response = api_get(user, "/api/cloud-auth/status")
                body = status_response.json()
                assert (
                    body.get("authenticated") is True
                    and body.get("user", {}).get("email") == user["email"]
                ), {
                    "response": {"status": status_response.status_code, "body": body},
                    "browser_cookie_sent": injected_auth[-1:],
                    "page_errors": page_errors,
                }
                return context, page

            _context_a, page_a = new_user_page(user_a)
            _context_b, page_b = new_user_page(user_b)
            expect(page_a.get_by_role("tab", name="Samples", exact=True)).to_be_visible()
            sample_button = page_a.get_by_role("tabpanel", name="Samples").get_by_role(
                "button", name="Open Nonconsecutive Subset Sums Modulo 3", exact=True
            )
            expect(sample_button).to_be_visible()
            sample_button.click()
            page_a.wait_for_url("**/project?*")
            expect(page_a.locator(".project-pane-title-line .current-project")).to_contain_text(
                "Nonconsecutive Subset Sums Modulo 3 v1"
            )
            path = page_a.evaluate("new URL(location.href).searchParams.get('path')")
            assert path and "/workspaces/" in path, path
            original_response = api_get(user_a, "/api/projects/inspect", path=path)
            assert original_response.status_code == 200, original_response.text
            original = original_response.json()["project"]
            project_id = original["id"]
            strategy_ids = [strategy["id"] for strategy in original["strategies"]]
            MATRIX["packaged Compose SPA/API and stock sample catalog"] = "PASS"

            MATRIX["sample project copy; project and strategy edits; save/reload/reopen"] = (
                "RUNNING"
            )
            page_a.get_by_role(
                "button", name=re.compile("Edit project title and description:")
            ).click()
            page_a.get_by_label("Project title", exact=True).fill("T91 Packaged Chrome Copy")
            page_a.locator("#text-editor-project-project").fill(
                "T91 packaged application persistence acceptance."
            )
            page_a.locator(".project-title-edit-form").get_by_role(
                "button", name="Save", exact=True
            ).click()
            expect(page_a.locator(".project-pane-title-line .current-project")).to_have_text(
                "T91 Packaged Chrome Copy"
            )

            page_a.locator("li[data-strategy-id]").first.get_by_role(
                "button", name=re.compile("Edit strategy title and description:")
            ).click()
            page_a.get_by_label("Strategy title", exact=True).fill("T91 Durable Strategy")
            page_a.locator(".strategy-rename-form").get_by_role(
                "button", name="Save", exact=True
            ).click()
            expect(page_a.locator("li[data-strategy-id]").first).to_contain_text(
                "T91 Durable Strategy"
            )
            edited_response = api_get(user_a, "/api/projects/inspect", path=path)
            assert edited_response.status_code == 200, edited_response.text
            edited = edited_response.json()["project"]
            assert edited["id"] == project_id
            assert edited["problem"] == "T91 packaged application persistence acceptance."
            assert [strategy["id"] for strategy in edited["strategies"]] == strategy_ids
            assert edited["strategies"][0]["title"] == "T91 Durable Strategy"
            page_a.get_by_role("button", name="Back to home", exact=True).click()
            page_a.goto(BASE_URL + "/", wait_until="networkidle")
            page_a.reload(wait_until="networkidle")
            expect(page_a.get_by_role("tab", name="Samples", exact=True)).to_be_visible()
            recent_response = api_get(user_a, "/api/projects/recent")
            assert recent_response.status_code == 200, recent_response.text
            recent_projects = recent_response.json().get("projects", [])
            assert any(
                entry.get("id") == project_id and entry.get("title") == "T91 Packaged Chrome Copy"
                for entry in recent_projects
            ), {"recent_projects": recent_projects, "page_errors": page_errors}
            page_a.get_by_role("tab", name="Recent", exact=True).click()
            for group in page_a.get_by_role("tabpanel", name="Recent").locator("details").all():
                if group.get_attribute("open") is None:
                    group.locator("summary").click()
            page_a.get_by_role("tabpanel", name="Recent").get_by_role(
                "button", name="T91 Packaged Chrome Copy", exact=True
            ).click()
            expect(page_a.locator(".project-pane-title-line .current-project")).to_have_text(
                "T91 Packaged Chrome Copy"
            )
            expect(page_a.locator("li[data-strategy-id]").first).to_contain_text(
                "T91 Durable Strategy"
            )
            reloaded = page_a.evaluate(
                "async path => (await (await fetch('/api/projects/inspect?' + new URLSearchParams({path}))).json()).project",
                path,
            )
            assert reloaded["id"] == project_id
            assert reloaded["problem"] == "T91 packaged application persistence acceptance."
            assert reloaded["strategies"][0]["id"] == strategy_ids[0]
            MATRIX["sample project copy; project and strategy edits; save/reload/reopen"] = "PASS"

            MATRIX["saved sessions, outcomes, and report download"] = "RUNNING"
            rows = page_a.locator("li[data-session-id]")
            expect(rows).to_have_count(5)
            first = rows.first
            disclosure = first.locator(".session-row-disclosure")
            if disclosure.get_attribute("aria-expanded") != "true":
                disclosure.click()
            expect(first.locator(".session-outcome-inline")).to_be_visible()
            expect(first.locator(".session-outcome-inline")).to_contain_text("Mixed")
            session_id = first.get_attribute("data-session-id")
            detail_response = api_get(
                user_a, f"/api/projects/research-sessions/{session_id}", path=path
            )
            assert detail_response.status_code == 200, detail_response.text
            detail = detail_response.json()
            assert detail.get("outcome") and detail.get("artifacts"), (
                "saved research fixture absent"
            )
            # Use the actual packaged UI's Export dialog and browser download.
            page_a.get_by_role("button", name="Export project", exact=True).click()
            dialog = page_a.get_by_role("dialog", name="Export Project")
            dialog.get_by_label("HTML report").check()
            with page_a.expect_download() as downloaded:
                dialog.get_by_role("button", name="Download", exact=True).click()
            report_file = Path(temporary) / "sigma-t91-report.html"
            downloaded.value.save_as(report_file)
            report = report_file.read_text(encoding="utf-8")
            assert "T91 Packaged Chrome Copy" in report
            assert "Open proof obligations" in report
            assert "Verification status" in report
            expect(dialog).to_be_hidden()
            papers_response = api_get(user_a, "/api/projects/papers", path=path)
            assert papers_response.status_code == 200, papers_response.text
            papers = papers_response.json()["papers"]
            downloadable = next((paper for paper in papers if paper.get("pdf_available")), None)
            if downloadable:
                pdf_result = page_a.evaluate(
                    "async ({path,id}) => {const r=await fetch('/api/projects/papers/' + id + '/pdf?' + new URLSearchParams({path})); const b=new Uint8Array(await r.arrayBuffer()); return {status:r.status,magic:String.fromCharCode(...b.slice(0,5)),size:b.length}}",
                    {"path": path, "id": downloadable["paper_id"]},
                )
                assert (
                    pdf_result["status"] == 200
                    and pdf_result["magic"] == "%PDF-"
                    and pdf_result["size"] > 1000
                ), pdf_result
                MATRIX["compiled PDF download"] = (
                    f"PASS — saved PDF downloaded ({pdf_result['size']} bytes)"
                )
            MATRIX["saved sessions, outcomes, and report download"] = (
                "PASS (5 saved sessions; Mixed outcome, cited research artifact, and HTML report downloaded)"
            )

            # Confirm B has its own Recent list and cannot retrieve A's path,
            # session, or the saved research evidence carried by that session.
            expect(page_b.get_by_role("tab", name="Recent", exact=True)).to_be_visible()
            page_b.get_by_role("tab", name="Recent", exact=True).click()
            for group in page_b.get_by_role("tabpanel", name="Recent").locator("details").all():
                if group.get_attribute("open") is None:
                    group.locator("summary").click()
            expect(
                page_b.get_by_role("tabpanel", name="Recent").get_by_text(
                    "T91 Packaged Chrome Copy", exact=True
                )
            ).to_have_count(0)
            denied_project = api_get(user_b, "/api/projects/inspect", path=path)
            assert denied_project.status_code == 404, denied_project.text
            denied_report = api_get(user_b, "/api/projects/export", path=path)
            assert denied_report.status_code == 404, denied_report.text
            denied_session = api_get(
                user_b,
                f"/api/projects/research-sessions/{session_id}",
                path=path,
            )
            assert denied_session.status_code == 404, denied_session.text
            MATRIX["user B denied user A project and saved evidence"] = (
                "PASS (Recent omits project; inspect, export, and session/evidence APIs return 404)"
            )

            # Force a new backend container while both Chrome contexts retain
            # their simulated session credentials and the volume remains.
            MATRIX["workspace survives backend container recreation"] = "RUNNING"
            compose("up", "-d", "--force-recreate", "backend")
            deadline = time.monotonic() + 90
            while time.monotonic() < deadline:
                try:
                    status = page_a.evaluate(
                        "async () => await (await fetch('/api/cloud-auth/status', {cache:'no-store'})).json()"
                    )
                    if status.get("ready"):
                        break
                except PlaywrightError:
                    pass
                time.sleep(1)
            else:
                raise RuntimeError("backend did not become ready after container recreation")
            page_a.goto(BASE_URL + "/", wait_until="networkidle")
            page_a.get_by_role("tab", name="Recent", exact=True).click()
            for group in page_a.get_by_role("tabpanel", name="Recent").locator("details").all():
                if group.get_attribute("open") is None:
                    group.locator("summary").click()
            page_a.get_by_role("tabpanel", name="Recent").get_by_role(
                "button", name="T91 Packaged Chrome Copy", exact=True
            ).click()
            expect(page_a.locator(".project-pane-title-line .current-project")).to_have_text(
                "T91 Packaged Chrome Copy"
            )
            expect(page_a.locator("li[data-strategy-id]").first).to_contain_text(
                "T91 Durable Strategy"
            )
            after_restart_response = api_get(user_a, "/api/projects/inspect", path=path)
            assert after_restart_response.status_code == 200, after_restart_response.text
            after_restart = after_restart_response.json()["project"]
            assert after_restart["id"] == project_id
            assert after_restart["problem"] == "T91 packaged application persistence acceptance."
            assert after_restart["strategies"][0]["title"] == "T91 Durable Strategy"
            status_after_restart = api_get(user_a, "/api/cloud-auth/status").json()
            assert status_after_restart["authenticated"] is True, status_after_restart
            assert hashlib.sha256(SAMPLE.read_bytes()).hexdigest() == source_digest
            assert not page_errors, page_errors
            MATRIX["workspace survives backend container recreation"] = (
                "PASS (same session, project/strategy IDs and edits reopened)"
            )
        finally:
            browser.close()

    print(json.dumps(MATRIX, ensure_ascii=False, indent=2))
    if any(
        value.startswith("FAIL") or value in {"NOT RUN", "RUNNING"} for value in MATRIX.values()
    ):
        raise SystemExit(1)
    print(
        "PASS real Chrome against packaged Compose frontend/backend/edge; no Vite process; no OAuth or inference calls"
    )


if __name__ == "__main__":
    try:
        main()
    except Exception as error:
        for item, value in MATRIX.items():
            if value == "RUNNING":
                MATRIX[item] = f"FAIL — {type(error).__name__}: {error}"
            elif value == "NOT RUN":
                MATRIX[item] = "SKIPPED — an earlier acceptance step failed"
        print(json.dumps(MATRIX, ensure_ascii=False, indent=2))
        raise
