"""Real Chrome current-understanding journeys using retained exercised projects.

Historical provider and deterministic fixture evidence stay distinct. No new
research sessions, providers, strategy edits or paper authoring are submitted.
SIGMA's actual export bytes and current-state API responses are retained.
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
from urllib.request import urlopen

from playwright.sync_api import expect, sync_playwright

REPO = Path(__file__).resolve().parents[1]
PROJECTS = Path(
    os.environ.get("SIGMA_STATE_CHECK_PROJECTS", "/tmp/sigma-research-experience-blue/projects")
).resolve()
OUTPUT = REPO / "docs/evaluations/increment_2"
EXPORTS = OUTPUT / "exports"
OUTPUT.mkdir(parents=True, exist_ok=True)


def free_port():
    with socket.socket() as sock:
        sock.bind(("127.0.0.1", 0))
        return sock.getsockname()[1]


def ready(url, process):
    deadline = time.monotonic() + 30
    while time.monotonic() < deadline:
        if process.poll() is not None:
            raise RuntimeError("Isolated server exited")
        try:
            with urlopen(url, timeout=1):
                return
        except OSError:
            time.sleep(0.1)
    raise RuntimeError("Isolated server unavailable")


slugs = ["maximum-regions-archived", "nonconsecutive-subset-sums", "maximum-regions-by-lines"]
for slug in slugs:
    if not (PROJECTS / (slug + ".sigma") / "project.json").is_file():
        raise RuntimeError(
            "Provide retained exercised copies via SIGMA_STATE_CHECK_PROJECTS; do not fabricate history"
        )
source_hashes = {
    str(p.relative_to(PROJECTS)): hashlib.sha256(p.read_bytes()).hexdigest()
    for slug in slugs
    for p in (PROJECTS / (slug + ".sigma")).rglob("*")
    if p.is_file()
}
observations = []
export_manifest = {
    "app_revision": subprocess.check_output(["git", "rev-parse", "HEAD"], text=True).strip(),
    "baseline_export_commit": "322cf5593eb4a9dff3d5ccf0f97300d5294ddb29",
    "new_provider_calls": 0,
    "new_research_sessions": 0,
    "format": "Actual SIGMA current-understanding GET response bytes; baseline audits/reports remain byte-identical",
    "projects": [],
}
with tempfile.TemporaryDirectory(prefix="sigma-current-state-browser-") as temporary:
    scratch = Path(temporary)
    env = {
        key: value
        for key, value in os.environ.items()
        if not key.startswith(("SIGMA_", "OPENAI_", "ANTHROPIC_"))
    }
    env["SIGMA_PROJECTS_ROOT"] = str(PROJECTS)
    for key, name in [
        ("SIGMA_STATE_DIR", "state"),
        ("SIGMA_AUTH_HOME", "auth"),
        ("SIGMA_CLOUD_AUTH_HOME", "cloud"),
    ]:
        directory = scratch / name
        directory.mkdir(mode=0o700)
        env[key] = str(directory)
    server = scratch / "offline_state_api.py"
    server.write_text("""import httpx
class OfflineClient(httpx.AsyncClient):
    def __init__(self, *args, **kwargs):
        kwargs['transport'] = httpx.MockTransport(lambda request: httpx.Response(503, json={'error': 'No external requests in this check'}))
        super().__init__(*args, **kwargs)
httpx.AsyncClient = OfflineClient
from sigma.api import app
""")
    api_port, ui_port = free_port(), free_port()
    while api_port == ui_port:
        ui_port = free_port()
    api_url, ui_url = f"http://127.0.0.1:{api_port}", f"http://127.0.0.1:{ui_port}"
    api = subprocess.Popen(
        [
            "uv",
            "run",
            "python",
            "-m",
            "uvicorn",
            "offline_state_api:app",
            "--app-dir",
            str(scratch),
            "--host",
            "127.0.0.1",
            "--port",
            str(api_port),
        ],
        cwd=REPO,
        env=env,
        stdout=(scratch / "api.log").open("w"),
        stderr=subprocess.STDOUT,
    )
    env["SIGMA_API_TARGET"] = api_url
    ui = subprocess.Popen(
        [
            "npm",
            "--prefix",
            "frontend",
            "run",
            "dev",
            "--",
            "--host",
            "127.0.0.1",
            "--port",
            str(ui_port),
            "--strictPort",
        ],
        cwd=REPO,
        env=env,
        stdout=subprocess.DEVNULL,
        stderr=subprocess.DEVNULL,
    )
    try:
        ready(api_url + "/openapi.json", api)
        ready(ui_url, ui)
        with sync_playwright() as pw:
            browser = pw.chromium.launch(
                executable_path=os.environ.get(
                    "SIGMA_BROWSER_EXECUTABLE",
                    "/Applications/Google Chrome.app/Contents/MacOS/Google Chrome",
                ),
                headless=True,
            )
            page = browser.new_page(viewport={"width": 1440, "height": 1000}, accept_downloads=True)
            errors, inference = [], []
            page.on("pageerror", lambda error: errors.append(str(error)))
            page.on(
                "request",
                lambda request: (
                    inference.append(request.url)
                    if request.method == "POST"
                    and any(
                        s in request.url
                        for s in ("generate", "/research-sessions/start", "/agentic")
                    )
                    else None
                ),
            )
            page.route(
                "**/api/**",
                lambda route: route.fulfill(
                    response=route.fetch(
                        url=route.request.url.replace(ui_url, api_url),
                        headers={**route.request.headers, "origin": "http://127.0.0.1:5173"},
                    )
                ),
            )
            for slug in slugs:
                path = str(PROJECTS / (slug + ".sigma"))
                page.goto(ui_url + "/")
                page.get_by_role("button", name="Open", exact=True).click()
                dialog = page.get_by_role("dialog", name="Open Project")
                dialog.get_by_label("Project directory").fill(path)
                dialog.get_by_role("button", name="Open Project", exact=True).click()
                summary = page.locator(".current-understanding")
                summary.wait_for()
                expect(summary).to_contain_text("Current findings")
                expect(summary).to_contain_text("What changed / superseded")
                expect(summary).to_contain_text("Open or not yet reconciled")
                response = page.request.get(
                    ui_url + "/api/projects/current-understanding?path=" + quote(path, safe="")
                )
                assert response.status == 200
                state = response.json()
                (EXPORTS / (slug + ".current-understanding.json")).write_bytes(response.body())
                assert state["project_status"] == "not_determined"
                if slug == "maximum-regions-archived":
                    expect(summary).to_contain_text("1+n(n+1)/2")
                    assert not state["next_investigations"]
                    assert (
                        sum(o["status"] == "resolved_reported" for o in state["obligations"]) == 4
                    )
                    expect(summary).to_contain_text("historical unreconciled")
                elif slug == "nonconsecutive-subset-sums":
                    expect(summary).to_contain_text("exponent explanation")
                    assert any(c["kind"] == "local_refutation_reported" for c in state["changes"])
                    assert state["next_investigations"]
                    assert len(state["findings"]) == 5
                else:
                    expect(summary).to_contain_text("No reviewed finding is saved")
                    assert not state["findings"] and not state["obligations"]
                navigation = []
                for name in ("Inspect finding:", "Inspect earlier evidence:"):
                    buttons = summary.get_by_role("button").filter(has_text="Session")
                    target = next(
                        (
                            b
                            for b in buttons.all()
                            if (b.get_attribute("aria-label") or "").startswith(name)
                        ),
                        None,
                    )
                    if target:
                        target.click()
                        # The exact artifact receives focus, with its parent
                        # session and evidence disclosure expanded.
                        page.wait_for_function(
                            "document.activeElement?.id.startsWith('research-artifact-')"
                        )
                        focused = page.evaluate("document.activeElement.id")
                        artifact = page.locator('[id="' + focused + '"]')
                        expect(artifact.locator(":scope > details")).to_have_attribute("open", "")
                        assert (
                            artifact.locator("xpath=ancestor::li[@data-session-id]")
                            .locator(".session-row-disclosure")
                            .get_attribute("aria-expanded")
                            == "true"
                        )
                        assert (
                            artifact.locator(
                                "xpath=ancestor::details[contains(@class,'outcome-evidence-subsection')]"
                            ).get_attribute("open")
                            is not None
                        )
                        navigation.append({"control": name, "focused_artifact": focused})
                dimensions = []
                for width, height in [(1440, 1000), (390, 844), (320, 700)]:
                    page.set_viewport_size({"width": width, "height": height})
                    dims = page.evaluate(
                        "({width:innerWidth,scrollWidth:document.documentElement.scrollWidth})"
                    )
                    assert dims["scrollWidth"] <= width, dims
                    dimensions.append(dims)
                    if width in (1440, 390):
                        summary.locator(":scope > summary").scroll_into_view_if_needed()
                        page.screenshot(path=str(OUTPUT / f"{slug}-{width}.png"))
                page.set_viewport_size({"width": 1440, "height": 1000})
                # Actual browser audit download, compared to the already
                # committed API export. No manual reconstruction of results.
                page.get_by_role("button", name="Export project", exact=True).click()
                dialog = page.get_by_role("dialog", name="Export Project")
                dialog.get_by_role("radio", name="Project Audit", exact=True).check()
                dialog.get_by_role("checkbox").uncheck()
                with page.expect_download() as download:
                    dialog.get_by_role("button", name="Download", exact=True).click()
                downloaded = scratch / (slug + ".audit.json")
                download.value.save_as(str(downloaded))
                original = EXPORTS / (slug + ".audit.json")
                assert json.loads(downloaded.read_bytes()) == json.loads(original.read_bytes()), (
                    "Current state must not alter audit content"
                )
                # Browser downloads pretty-print the same actual export; keep
                # those bytes too rather than substituting the earlier response.
                browser_export = EXPORTS / (slug + ".browser.audit.json")
                browser_export.write_bytes(downloaded.read_bytes())
                ids = state["current_finding_ids"]
                page.reload()
                page.locator(".current-understanding").wait_for()
                reread = page.request.get(
                    ui_url + "/api/projects/current-understanding?path=" + quote(path, safe="")
                ).json()
                assert reread == state and reread["current_finding_ids"] == ids
                export_manifest["projects"].append(
                    {
                        "slug": slug,
                        "project_id": state["project_id"],
                        "source_session_ids": sorted(
                            {f["source"]["session_id"] for f in state["findings"]}
                        ),
                        "files": [
                            {
                                "path": p.name,
                                "format": "SIGMA browser Project Audit JSON"
                                if ".browser.audit." in p.name
                                else "SIGMA current-understanding API JSON",
                                "sha256": hashlib.sha256(p.read_bytes()).hexdigest(),
                                "bytes": p.stat().st_size,
                            }
                            for p in (
                                EXPORTS / (slug + ".current-understanding.json"),
                                browser_export,
                            )
                        ],
                        "audit_content_unchanged": True,
                        "research_activity": "Read-only current-state/evidence navigation, reload, viewport and real audit-export checks. No new session or provider work.",
                    }
                )
                observations.append(
                    {
                        "project": slug,
                        "dimensions": dimensions,
                        "navigation": navigation,
                        "current_finding_ids": ids,
                    }
                )
            assert not errors and not inference, (errors, inference)
            browser_version = browser.version
            browser.close()
    finally:
        for process in (ui, api):
            process.terminate()
        for process in (ui, api):
            try:
                process.wait(timeout=5)
            except subprocess.TimeoutExpired:
                process.kill()
                process.wait(timeout=5)
assert all(
    hashlib.sha256((PROJECTS / name).read_bytes()).hexdigest() == value
    for name, value in source_hashes.items()
)
(OUTPUT / "browser-observations.json").write_text(
    json.dumps(
        {
            "app_revision": export_manifest["app_revision"],
            "browser": browser_version,
            "projects": observations,
            "source_file_hashes": source_hashes,
            "source_bytes_unchanged": True,
            "page_errors": errors,
            "inference_requests": inference,
        },
        indent=2,
    )
)
(EXPORTS / "CURRENT_STATE_MANIFEST.json").write_text(json.dumps(export_manifest, indent=2))
print(
    "PASS real Chrome: current understanding, exact evidence navigation, original archives, empty sample, stable reload/IDs, desktop/390/320px, actual audit exports unchanged, no provider work"
)
