"""Real Chrome acceptance against the packaged Compose app, never Vite.

The test inserts ephemeral authenticated session records for two simulated
Google subjects into the disposable Compose auth database. The app's normal
cloud-auth middleware, workspace scoping, API, Nginx frontend, and Caddy edge
remain in use. This is not a Google OAuth exchange and it makes no inference
requests.
"""

from __future__ import annotations

import hashlib
import io
import json
import os
import re
import secrets
import shutil
import subprocess
import tempfile
import time
from pathlib import Path

import httpx
from playwright.sync_api import Error as PlaywrightError
from playwright.sync_api import expect, sync_playwright
from pypdf import PdfReader

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
    "real Tectonic PDF compilation and authenticated download": "NOT RUN",
    "malformed TeX fails without publishing a PDF": "NOT RUN",
    "saved TeX, PDF, report and session evidence survive backend recreation": "NOT RUN",
    "backup restores into fresh storage with identities and hashes intact": "NOT RUN",
    "restored workspace remains isolated from user B": "NOT RUN",
    "persistent_disk storage backend from T100": "SKIPPED — this run uses Compose's default local storage configuration",
    "inference generation from T99": "SKIPPED — this workflow is read/edit/export only; no provider calls",
}

COMPOSE = shutil.which("docker-compose")
if not COMPOSE:
    COMPOSE = "docker"
    COMPOSE_PREFIX = ["compose"]
else:
    COMPOSE_PREFIX = []

BASE_COMPOSE = ROOT / "deploy/compose.yaml"
RESTORE_VOLUME = f"{PROJECT}_t91-restore-{os.getpid()}"
OVERRIDE_FILE: Path | None = None

SEED_COMPILED_PAPER = r"""
import hashlib, json, sys
from datetime import UTC, datetime
from sigma import papers
path, project_id, paper_id = sys.argv[1:]
tex = r'''\documentclass{article}
\begin{document}
T91 packaged recovery acceptance.
The durable evidence value is 17.
\end{document}
'''
pdf = papers._compile_pdf(tex)
assert pdf.startswith(b"%PDF-") and pdf.rstrip().endswith(b"%%EOF")
record = {
    "paper_id": paper_id,
    "project_id": project_id,
    "created_at": datetime.now(UTC).isoformat(),
    "snapshot_sha256": "b" * 64,
    "draft": {"title": "T91 Packaged Recovery Paper"},
    "validation_warnings": [],
    "generation": {"fixture": "deterministic; no provider calls"},
    "source": {"fixture": "T91 durable source"},
    "tex_source": tex,
}
papers._save(path, record, pdf)
before = set(papers._paper_dir(path).iterdir())
try:
    papers._compile_pdf(r"\documentclass{article}\begin{document}\T91MalformedControlSequence\end{document}")
except RuntimeError as error:
    message = str(error)
    assert "Tectonic could not compile" in message and "No PDF was downloaded" in message
else:
    raise AssertionError("malformed TeX unexpectedly compiled")
after = set(papers._paper_dir(path).iterdir())
assert after == before, "failed compilation published a paper artifact"
stored = papers.get_paper(path, paper_id)
stored_pdf = papers.get_pdf(path, paper_id)
assert stored["tex_source"] == tex
assert hashlib.sha256(stored_pdf).hexdigest() == stored["pdf_sha256"]
print(json.dumps({"paper_id": paper_id, "tex_sha256": hashlib.sha256(tex.encode()).hexdigest(),
                  "pdf_sha256": hashlib.sha256(pdf).hexdigest(), "pdf_bytes": len(pdf),
                  "malformed_error": message}))
"""

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
        COMPOSE,
        *COMPOSE_PREFIX,
        "--project-name",
        PROJECT,
        "--env-file",
        COMPOSE_ENV,
        "-f",
        str(BASE_COMPOSE),
    ]
    if OVERRIDE_FILE:
        command.extend(("-f", str(OVERRIDE_FILE)))
    command.extend(args)
    return subprocess.run(command, cwd=ROOT, text=True, capture_output=True, check=True)


def backup_volume(source: str, archive: Path) -> None:
    archive.parent.mkdir(mode=0o700, parents=True, exist_ok=True)
    subprocess.run(
        [
            "docker",
            "run",
            "--rm",
            "-v",
            f"{source}:/source:ro",
            "-v",
            f"{archive.parent}:/backup",
            "alpine:3.21",
            "sh",
            "-ec",
            "tar -C /source -cf /backup/state.tar .",
        ],
        check=True,
        capture_output=True,
        text=True,
    )


def restore_volume(archive: Path, destination: str) -> None:
    subprocess.run(
        ["docker", "volume", "create", destination], check=True, capture_output=True, text=True
    )
    subprocess.run(
        [
            "docker",
            "run",
            "--rm",
            "-v",
            f"{archive.parent}:/backup:ro",
            "-v",
            f"{destination}:/restore",
            "alpine:3.21",
            "sh",
            "-ec",
            "tar -C /restore -xf /backup/state.tar",
        ],
        check=True,
        capture_output=True,
        text=True,
    )


def write_restore_override(path: Path) -> None:
    path.write_text(
        f"volumes:\n  sigma-state:\n    external: true\n    name: {RESTORE_VOLUME}\n",
        encoding="utf-8",
    )


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
    global OVERRIDE_FILE
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
            report_digest = hashlib.sha256(report_file.read_bytes()).hexdigest()
            expect(dialog).to_be_hidden()
            papers_response = api_get(user_a, "/api/projects/papers", path=path)
            assert papers_response.status_code == 200, papers_response.text
            papers_response.json()["papers"]
            paper_id = secrets.token_hex(16)
            try:
                seed_result = compose(
                    "exec",
                    "-T",
                    "backend",
                    "python",
                    "-c",
                    SEED_COMPILED_PAPER,
                    path,
                    project_id,
                    paper_id,
                )
            except subprocess.CalledProcessError as error:
                raise RuntimeError(
                    f"Packaged PDF fixture failed: {error.stderr or error.stdout}"
                ) from error
            compiled = json.loads(seed_result.stdout.strip().splitlines()[-1])
            pdf_response = api_get(user_a, f"/api/projects/papers/{paper_id}/pdf", path=path)
            assert pdf_response.status_code == 200, pdf_response.text
            assert pdf_response.headers.get("content-type", "").startswith("application/pdf")
            assert "attachment" in pdf_response.headers.get("content-disposition", "")
            pdf = pdf_response.content
            assert hashlib.sha256(pdf).hexdigest() == compiled["pdf_sha256"]
            assert pdf.startswith(b"%PDF-") and pdf.rstrip().endswith(b"%%EOF")
            reader = PdfReader(io.BytesIO(pdf), strict=True)
            assert len(reader.pages) == 1
            assert "T91 packaged recovery acceptance" in reader.pages[0].extract_text()
            assert compiled["pdf_bytes"] > 1000
            paper_record_response = api_get(user_a, f"/api/projects/papers/{paper_id}", path=path)
            assert paper_record_response.status_code == 200, paper_record_response.text
            paper_record = paper_record_response.json()
            assert (
                paper_record["tex_source"]
                and hashlib.sha256(paper_record["tex_source"].encode()).hexdigest()
                == compiled["tex_sha256"]
            )
            MATRIX["real Tectonic PDF compilation and authenticated download"] = (
                f"PASS — Tectonic PDF validated and authenticated download matched SHA-256 {compiled['pdf_sha256']} ({compiled['pdf_bytes']} bytes)"
            )
            MATRIX["malformed TeX fails without publishing a PDF"] = (
                "PASS — explicit Tectonic failure; no paper files appeared"
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
            denied_pdf = api_get(user_b, f"/api/projects/papers/{paper_id}/pdf", path=path)
            assert denied_pdf.status_code == 404, denied_pdf.text
            denied_paper = api_get(user_b, f"/api/projects/papers/{paper_id}", path=path)
            assert denied_paper.status_code == 404, denied_paper.text
            MATRIX["user B denied user A project and saved evidence"] = (
                "PASS (Recent omits project; inspect, export, session and PDF APIs return 404)"
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
            after_restart_paper = api_get(
                user_a, f"/api/projects/papers/{paper_id}", path=path
            ).json()
            assert after_restart_paper["tex_source"] == paper_record["tex_source"]
            after_restart_pdf = api_get(user_a, f"/api/projects/papers/{paper_id}/pdf", path=path)
            assert hashlib.sha256(after_restart_pdf.content).hexdigest() == compiled["pdf_sha256"]
            after_restart_session = api_get(
                user_a, f"/api/projects/research-sessions/{session_id}", path=path
            ).json()
            assert after_restart_session["id"] == detail["id"]
            assert after_restart_session["outcome"] == detail["outcome"]
            assert after_restart_session["artifacts"] == detail["artifacts"]
            after_restart_report = api_get(
                user_a, "/api/projects/export/report", path=path, format="html"
            )
            assert after_restart_report.status_code == 200, after_restart_report.text
            assert hashlib.sha256(after_restart_report.content).hexdigest() == report_digest
            assert hashlib.sha256(SAMPLE.read_bytes()).hexdigest() == source_digest
            assert not page_errors, page_errors
            MATRIX["workspace survives backend container recreation"] = (
                "PASS (project/strategy/session IDs, outcomes/evidence, TeX/PDF and report hash survived)"
            )

            MATRIX["saved TeX, PDF, report and session evidence survive backend recreation"] = (
                f"PASS — TeX SHA-256 {compiled['tex_sha256']}; PDF SHA-256 unchanged; session evidence equal; report SHA-256 {report_digest} unchanged"
            )

            MATRIX["backup restores into fresh storage with identities and hashes intact"] = (
                "RUNNING"
            )
            volumes = subprocess.run(
                [
                    "docker",
                    "volume",
                    "ls",
                    "-q",
                    "--filter",
                    f"label=com.docker.compose.project={PROJECT}",
                    "--filter",
                    "label=com.docker.compose.volume=sigma-state",
                ],
                check=True,
                text=True,
                capture_output=True,
            ).stdout.splitlines()
            assert len(volumes) == 1, f"expected one source state volume, got {volumes}"
            source_volume = volumes[0]
            backup_dir = Path(tempfile.mkdtemp(prefix="sigma-t91-recovery-"))
            backup_dir.chmod(0o700)
            archive = backup_dir / "state.tar"
            compose("stop", "backend")
            backup_volume(source_volume, archive)
            # A failed extraction is a failed restore: it must raise and must
            # never be included in a PASS result.
            invalid_archive = backup_dir / "invalid.tar"
            invalid_archive.write_bytes(b"not a tar archive")
            failed_volume = f"{RESTORE_VOLUME}-failed"
            subprocess.run(
                ["docker", "volume", "create", failed_volume],
                text=True,
                capture_output=True,
                check=True,
            )
            failed_result = subprocess.run(
                [
                    "docker",
                    "run",
                    "--rm",
                    "-v",
                    f"{invalid_archive.parent}:/backup:ro",
                    "-v",
                    f"{failed_volume}:/restore",
                    "alpine:3.21",
                    "sh",
                    "-ec",
                    "tar -C /restore -xf /backup/invalid.tar",
                ],
                text=True,
                capture_output=True,
                check=False,
            )
            assert failed_result.returncode != 0, "invalid backup was reported as restored"
            subprocess.run(
                ["docker", "volume", "rm", failed_volume],
                check=True,
                capture_output=True,
                text=True,
            )
            restore_volume(archive, RESTORE_VOLUME)
            OVERRIDE_FILE = backup_dir / "compose-restore.yaml"
            write_restore_override(OVERRIDE_FILE)
            compose("up", "-d", "--force-recreate", "backend")
            deadline = time.monotonic() + 90
            while time.monotonic() < deadline:
                try:
                    status = api_get(user_a, "/api/cloud-auth/status").json()
                    if status.get("ready"):
                        break
                except (httpx.HTTPError, ValueError):
                    pass
                time.sleep(1)
            else:
                raise RuntimeError("backend did not become ready on restored storage")
            restored_owner = api_get(user_a, "/api/projects/inspect", path=path)
            assert restored_owner.status_code == 200, restored_owner.text
            restored_project = restored_owner.json()["project"]
            assert restored_project["id"] == project_id
            assert restored_project["strategies"][0]["id"] == strategy_ids[0]
            restored_paper = api_get(user_a, f"/api/projects/papers/{paper_id}", path=path)
            assert restored_paper.status_code == 200, restored_paper.text
            assert restored_paper.json()["tex_source"] == paper_record["tex_source"]
            restored_pdf = api_get(user_a, f"/api/projects/papers/{paper_id}/pdf", path=path)
            assert hashlib.sha256(restored_pdf.content).hexdigest() == compiled["pdf_sha256"]
            restored_session = api_get(
                user_a, f"/api/projects/research-sessions/{session_id}", path=path
            )
            assert restored_session.status_code == 200, restored_session.text
            restored_detail = restored_session.json()
            assert restored_detail["id"] == detail["id"]
            assert restored_detail["outcome"] == detail["outcome"]
            assert restored_detail["artifacts"] == detail["artifacts"]
            restored_report = api_get(
                user_a, "/api/projects/export/report", path=path, format="html"
            )
            assert hashlib.sha256(restored_report.content).hexdigest() == report_digest
            assert api_get(user_b, "/api/projects/inspect", path=path).status_code == 404
            assert (
                api_get(user_b, f"/api/projects/papers/{paper_id}/pdf", path=path).status_code
                == 404
            )
            assert (
                api_get(user_b, "/api/projects/export/report", path=path, format="html").status_code
                == 404
            )
            assert (
                api_get(
                    user_b, f"/api/projects/research-sessions/{session_id}", path=path
                ).status_code
                == 404
            )
            MATRIX["backup restores into fresh storage with identities and hashes intact"] = (
                f"PASS — fresh volume; project/session/paper IDs preserved; PDF SHA-256 {compiled['pdf_sha256']}; HTML report SHA-256 {report_digest}"
            )
            MATRIX["restored workspace remains isolated from user B"] = (
                "PASS — restored project, PDF, and session evidence return 404"
            )
            MATRIX["failed restores do not report success"] = (
                "PASS — invalid tar extraction returned nonzero; only verified owner checks marked restore PASS"
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
