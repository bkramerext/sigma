"""Replay the owner's Issue 415 bundle in isolated real Chrome, without source writes.

Set SIGMA_ISSUE415_BUNDLE to a local sigma.project.bundle JSON file. The source
is read only; SIGMA imports a copy under a temporary workspace before launch.
"""

import hashlib
import json
import os
import socket
import subprocess
import tempfile
import time
from pathlib import Path
from urllib.parse import quote

from playwright.sync_api import expect, sync_playwright

from sigma.project_bundle import _decode, import_bundle, read_bundle

REPO = Path(__file__).resolve().parents[1]
CHROME = os.environ.get(
    "SIGMA_BROWSER_EXECUTABLE", "/Applications/Google Chrome.app/Contents/MacOS/Google Chrome"
)
SOURCE = Path(os.environ["SIGMA_ISSUE415_BUNDLE"]).expanduser().resolve()


def free_port():
    with socket.socket() as listener:
        listener.bind(("127.0.0.1", 0))
        return listener.getsockname()[1]


def wait_for(url, process):
    import urllib.error
    import urllib.request

    for _ in range(300):
        if process.poll() is not None:
            raise AssertionError(f"Isolated server exited: {process.returncode}")
        try:
            with urllib.request.urlopen(url, timeout=1):
                return
        except (OSError, urllib.error.URLError):
            time.sleep(0.1)
    raise AssertionError(f"Server did not become ready: {url}")


source_hash_before = hashlib.sha256(SOURCE.read_bytes()).hexdigest()
source_bundle = read_bundle(SOURCE)
source_members = _decode(source_bundle)
project_document = json.loads(source_members["project.json"])
session_records = {
    session["id"]: session
    for name, raw in source_members.items()
    if name.startswith("research-sessions/")
    and name.endswith(".json")
    and name not in {"research-sessions/limits.json", "research-sessions/sequence.json"}
    for session in [json.loads(raw)]
}
target_session = next(
    record for record in session_records.values() if record.get("session_number") == 6
)
target_id = target_session["id"]
session_baselines = {
    record["id"]: {
        "session_number": record["session_number"],
        "calls_used": record.get("calls_used"),
        "steps": len(record.get("steps", [])),
        "artifacts": [artifact.get("id") for artifact in record.get("artifacts", [])],
    }
    for record in session_records.values()
}
target_baseline = session_baselines[target_id]

with tempfile.TemporaryDirectory(prefix="sigma-issue415-owner-replay-") as temporary:
    root = Path(temporary)
    project_path = root / SOURCE.name
    import_bundle(source_bundle, project_path)
    api_port, ui_port = free_port(), free_port()
    while ui_port == api_port:
        ui_port = free_port()
    api_url = f"http://127.0.0.1:{api_port}"
    ui_url = f"http://127.0.0.1:{ui_port}"
    env = os.environ.copy()
    env["SIGMA_PROJECTS_ROOT"] = str(root)
    api = subprocess.Popen(
        [
            "uv",
            "run",
            "--project",
            str(REPO),
            "python",
            "-m",
            "uvicorn",
            "sigma.server:create_app",
            "--factory",
            "--host",
            "127.0.0.1",
            "--port",
            str(api_port),
        ],
        cwd=REPO,
        env=env,
        stdout=subprocess.DEVNULL,
        stderr=subprocess.DEVNULL,
    )
    env["SIGMA_API_TARGET"] = api_url
    ui = subprocess.Popen(
        [
            "npm",
            "--prefix",
            str(REPO / "frontend"),
            "run",
            "dev",
            "--",
            "--host",
            "127.0.0.1",
            "--port",
            str(ui_port),
        ],
        cwd=REPO,
        env=env,
        stdout=subprocess.DEVNULL,
        stderr=subprocess.DEVNULL,
    )
    try:
        wait_for(api_url + "/openapi.json", api)
        wait_for(ui_url, ui)
        with sync_playwright() as playwright:
            browser = playwright.chromium.launch(
                executable_path=CHROME,
                headless=True,
                args=["--disable-web-security"],
            )
            page = browser.new_page(viewport={"width": 1440, "height": 1000})
            page_errors, console_errors, network = [], [], []
            page.on(
                "pageerror",
                lambda error: page_errors.append(
                    {"message": str(error), "stack": getattr(error, "stack", None)}
                ),
            )
            page.on(
                "console",
                lambda message: (
                    console_errors.append(message.text) if message.type == "error" else None
                ),
            )
            page.on(
                "response",
                lambda response: (
                    network.append((response.status, response.url))
                    if "/api/projects/" in response.url
                    else None
                ),
            )
            page.goto(f"{ui_url}/project?path={quote(str(project_path), safe='')}")
            rows = page.locator("ol.session-list > li.session-row")
            try:
                expect(rows).to_have_count(6, timeout=12000)
            except AssertionError:
                print(
                    json.dumps(
                        {
                            "project_loaded": page.get_by_role(
                                "heading", name=project_document["title"]
                            ).count()
                            > 0,
                            "session_rows": rows.count(),
                            "body_excerpt": page.locator("body").inner_text()[:600],
                            "page_errors": page_errors,
                            "react_diagnostics": console_errors[:5],
                            "api_statuses": [
                                (status, url.split("/")[-1].split("?")[0])
                                for status, url in network
                            ],
                        },
                        indent=2,
                    )
                )
                raise
            sessions_toggle = page.locator(".sessions-pane-heading .workspace-section-disclosure")
            if sessions_toggle.get_attribute("aria-expanded") != "true":
                sessions_toggle.click()
            expect(page.locator(".session-list")).to_be_visible()
            expect(
                page.get_by_role("alert").filter(has_text="Session #6 could not be displayed")
            ).to_have_count(0)
            expect(page.locator(".session-render-error")).to_have_count(0)
            target_row = page.locator("li.session-row").filter(
                has=page.locator(".session-row-title", has_text="Session #6")
            )
            expect(target_row).to_be_visible()
            target_row.locator(".session-row-disclosure").click()
            expect(target_row.locator(".session-progress-inline")).to_contain_text(
                f"{target_baseline['calls_used']}/"
            )
            advanced_button = target_row.get_by_role("button", name="Advanced Outcome")
            if advanced_button.count():
                advanced_button.click()
            expect(target_row.locator(".outcome-subsections")).to_be_visible(timeout=10000)
            page.reload(wait_until="networkidle")
            expect(rows).to_have_count(6, timeout=20000)
            expect(target_row).to_be_visible()
            target_row.locator(".session-row-disclosure").click()
            advanced_button = target_row.get_by_role("button", name="Advanced Outcome")
            if advanced_button.count():
                advanced_button.click()
            expect(target_row.locator(".outcome-subsections")).to_be_visible(timeout=10000)
            page.get_by_role("button", name="Export project").click()
            expect(page.get_by_role("dialog", name="Export Project")).to_be_visible()
            with page.expect_download(timeout=20000) as download:
                page.get_by_role("button", name="Download").click()
            exported = json.loads(Path(download.value.path()).read_text(encoding="utf-8"))
            exported_sessions = {
                value["id"]: value
                for name, value in exported["files"].items()
                if name.startswith("research-sessions/")
                and name.endswith(".json")
                and name not in {"research-sessions/limits.json", "research-sessions/sequence.json"}
            }
            assert len(exported_sessions) == 6, len(exported_sessions)
            assert set(exported_sessions) == set(session_baselines)
            for session_id, baseline in session_baselines.items():
                exported_session = exported_sessions[session_id]
                assert len(exported_session.get("steps", [])) == baseline["steps"]
                assert [
                    item.get("id") for item in exported_session.get("artifacts", [])
                ] == baseline["artifacts"]
            exported_target = exported_sessions[target_id]
            assert exported_target["session_number"] == 6
            assert not page_errors, page_errors
            assert any("/api/projects/open" in url and status == 200 for status, url in network)
            assert any("research-sessions?" in url and status == 200 for status, url in network)
            assert any("/api/projects/export?" in url and status == 200 for status, url in network)
            assert not any("research-sessions/" in url and "control" in url for _, url in network)
            source_hash_after = hashlib.sha256(SOURCE.read_bytes()).hexdigest()
            print(
                json.dumps(
                    {
                        "project_id": project_document["id"],
                        "session_count": len(exported_sessions),
                        "all_session_steps_and_artifacts_preserved": True,
                        "session_6": {
                            "calls_used": target_baseline["calls_used"],
                            "steps": target_baseline["steps"],
                            "artifacts_exported": len(exported_target.get("artifacts", [])),
                            "rendered_after_refresh": True,
                        },
                        "project_export": "passed",
                        "source_bundle_unchanged": source_hash_before == source_hash_after,
                        "uncaught_page_errors": page_errors,
                        "react_render_diagnostics": console_errors[:5],
                        "api_statuses": [
                            (status, url.split("/")[-1].split("?")[0]) for status, url in network
                        ],
                    },
                    indent=2,
                )
            )
            browser.close()
    finally:
        ui.terminate()
        api.terminate()
        ui.wait(timeout=10)
        api.wait(timeout=10)
