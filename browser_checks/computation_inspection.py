"""Read-only real Chrome inspection of actual computational session evidence.
No provider requests; provides legible viewport captures and source navigation.
Run after causal_continuation.py while its retained scratch copies exist.
"""

import json
import os
import socket
import subprocess
import tempfile
import time
from pathlib import Path
from urllib.parse import urlencode
from urllib.request import urlopen

from playwright.sync_api import expect, sync_playwright

ROOT = Path(__file__).resolve().parents[1]
OUT = Path(os.environ.get("SIGMA_COMPUTATION_OUTPUT_DIR", ROOT / "docs/evaluations/increment_4"))
manifest = json.loads((OUT / "exports/MANIFEST.json").read_text())
scratch = Path(tempfile.mkdtemp(prefix="sigma-continuation-inspection-"))


def port():
    with socket.socket() as s:
        s.bind(("127.0.0.1", 0))
        return s.getsockname()[1]


def ready(url, process):
    for _ in range(200):
        if process.poll() is not None:
            raise RuntimeError("Server exited")
        try:
            with urlopen(url, timeout=1):
                return
        except OSError:
            time.sleep(0.1)
    raise RuntimeError("Server unavailable")


env = {k: v for k, v in os.environ.items() if not k.startswith(("SIGMA_", "OPENAI_", "ANTHROPIC_"))}
for key in ["SIGMA_STATE_DIR", "SIGMA_AUTH_HOME", "SIGMA_CLOUD_AUTH_HOME"]:
    directory = scratch / key
    directory.mkdir()
    env[key] = str(directory)
env["SIGMA_PROJECTS_ROOT"] = str(Path(manifest["isolated_root"]) / "projects")
(scratch / "offline_inspection.py").write_text("""import httpx
class OfflineClient(httpx.AsyncClient):
    def __init__(self,*args,**kwargs):
        kwargs['transport']=httpx.MockTransport(lambda req:httpx.Response(503,json={'error':'Offline inspection; no calls permitted'}))
        super().__init__(*args,**kwargs)
httpx.AsyncClient=OfflineClient
from sigma.api import app
""")
a, u = port(), port()
api_url, ui_url = f"http://127.0.0.1:{a}", f"http://127.0.0.1:{u}"
env["SIGMA_API_TARGET"] = api_url
api = subprocess.Popen(
    [
        "uv",
        "run",
        "python",
        "-m",
        "uvicorn",
        "offline_inspection:app",
        "--app-dir",
        str(scratch),
        "--host",
        "127.0.0.1",
        "--port",
        str(a),
    ],
    cwd=ROOT,
    env=env,
    stdout=(scratch / "api.txt").open("w"),
    stderr=subprocess.STDOUT,
)
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
        str(u),
        "--strictPort",
    ],
    cwd=ROOT,
    env=env,
    stdout=subprocess.DEVNULL,
    stderr=subprocess.STDOUT,
)
observations = []
checked_projects = set()
try:
    ready(api_url + "/openapi.json", api)
    ready(ui_url, ui)
    with sync_playwright() as pw:
        browser = pw.chromium.launch(
            executable_path="/Applications/Google Chrome.app/Contents/MacOS/Google Chrome",
            headless=True,
        )
        page = browser.new_page(viewport={"width": 1440, "height": 1000})
        page.set_default_timeout(10000)
        errors = []
        page.on("pageerror", lambda e: errors.append(str(e)))
        page.route(
            "**/api/**",
            lambda route: route.fulfill(
                response=route.fetch(
                    url=route.request.url.replace(ui_url, api_url),
                    headers={**route.request.headers, "origin": "http://127.0.0.1:5173"},
                )
            ),
        )
        # Set both isolated project copies to Simple through the UI. The later
        # subset change must not change the graph project's saved preference.
        for project in manifest["projects"]:
            page.goto(ui_url + "/")
            page.get_by_role("button", name="Open", exact=True).click()
            setup = page.get_by_role("dialog", name="Open Project")
            setup.get_by_label("Project directory").fill(project["path"])
            setup.get_by_role("button", name="Open Project", exact=True).click()
            page.locator(".sessions-pane li[data-session-id]").first.wait_for()
            if page.locator(".outcome-advanced").count():
                page.get_by_role("button", name="Project settings", exact=True).click()
                settings_dialog = page.get_by_role("dialog", name="Settings")
                settings_dialog.get_by_role("tab", name="Preferences").click()
                settings_dialog.get_by_role(
                    "checkbox", name="Show advanced Outcome details"
                ).uncheck()
                settings_dialog.get_by_role("button", name="Save", exact=True).click()
            expect(page.locator(".outcome-advanced")).to_have_count(0)
        for run in manifest["runs"]:
            if run["mode"] not in {"actual", "error", "timeout", "sage", "restart"}:
                continue
            project = next(p for p in manifest["projects"] if p["project_id"] == run["project_id"])
            slug = run["scenario"] + "-" + run["mode"]
            page.goto(ui_url + "/")
            page.get_by_role("button", name="Open", exact=True).click()
            dialog = page.get_by_role("dialog", name="Open Project")
            dialog.get_by_label("Project directory").fill(project["path"])
            dialog.get_by_role("button", name="Open Project", exact=True).click()
            page.locator(".current-understanding").wait_for()
            row = page.locator(f'[data-session-id="{run["session_id"]}"]')
            row.wait_for()
            first_project_open = project["project_id"] not in checked_projects
            if first_project_open:
                if run["scenario"] == "subset":
                    old_audit = json.loads((OUT / "exports/subset.before.audit.json").read_text())
                    old_id = old_audit["research_sessions"][0]["id"]
                    historical = page.locator(f'[data-session-id="{old_id}"]')
                    if (
                        historical.locator(".session-row-disclosure").get_attribute("aria-expanded")
                        != "true"
                    ):
                        historical.locator(".session-row-disclosure").click()
                    expect(historical.locator(".outcome-simple")).to_contain_text(
                        "Historical session summary"
                    )
                    assert (
                        "No Conclusion was saved"
                        not in historical.locator(".outcome-simple").inner_text()
                    )
                checked_projects.add(project["project_id"])
            if row.locator(".session-row-disclosure").get_attribute("aria-expanded") != "true":
                row.locator(".session-row-disclosure").click()
            if first_project_open:
                expect(row.locator(".outcome-simple")).to_be_visible()
            if row.locator(".outcome-simple").count():
                simple = row.locator(".outcome-simple")
                assert simple.is_visible()
                assert "Verification:" in simple.inner_text()
                assert (
                    simple.locator(".outcome-summary-kicker").text_content().strip() == "Conclusion"
                )
                assert len(simple.locator(".outcome-summary-text > p").first.inner_text()) <= 902
                assert row.locator(".continuation-evidence").count() == 0
                settings = page.get_by_role("button", name="Project settings", exact=True)
                settings.click()
                preferences = page.get_by_role("dialog", name="Settings")
                preferences.get_by_role("tab", name="Preferences").click()
                preferences.get_by_role("checkbox", name="Show advanced Outcome details").check()
                preferences.get_by_role("button", name="Save", exact=True).click()
                expect(row.locator(".outcome-advanced")).to_be_visible()
                if run["scenario"] == "subset":
                    expect(historical.locator(".outcome-conclusion")).to_contain_text(
                        "Historical session summary"
                    )
            for width in [1440, 390, 320]:
                page.set_viewport_size({"width": width, "height": 1000 if width == 1440 else 844})
                page.reload()
                row = page.locator(f'[data-session-id="{run["session_id"]}"]')
                row.wait_for()
                toggle = row.locator(".session-row-disclosure")
                if toggle.get_attribute("aria-expanded") != "true":
                    toggle.click()
                assert row.locator(".outcome-advanced").is_visible()
                assert row.locator(".outcome-conclusion").is_visible()
                assert row.locator(".sigma-render-toggle .markdown-logo").first.is_visible()
                inherited = row.locator(".continuation-evidence")
                if inherited.count():
                    assert inherited.get_attribute("open") is None
                    inherited.locator(":scope > summary").click()
                    assert inherited.get_by_role(
                        "button", name="Approved source", exact=False
                    ).first.is_visible()
                    if width == 1440:
                        after_audit = json.loads(
                            (
                                OUT
                                / "exports"
                                / (
                                    "subset.after.audit.json"
                                    if run["scenario"] == "subset"
                                    else "algorithm.after.audit.json"
                                )
                            ).read_text()
                        )
                        saved_session = next(
                            item
                            for item in after_audit["research_sessions"]
                            if item["id"] == run["session_id"]
                        )
                        first_packet = next(iter(saved_session["approved_continuations"].values()))
                        source_session_id = first_packet["sources"][0]["source"]["session_id"]
                        inherited.get_by_role(
                            "button", name="Approved source", exact=False
                        ).first.click()
                        expect(
                            page.locator(
                                f'[data-session-id="{source_session_id}"] .session-row-disclosure'
                            )
                        ).to_have_attribute("aria-expanded", "true")
                evidence = row.locator(".outcome-evidence-subsection")
                if evidence.get_attribute("open") is None:
                    evidence.locator(":scope > summary").click()
                artifact = row.locator(".research-artifacts > ol > li").first
                detail = artifact.locator(":scope > details")
                if detail.get_attribute("open") is None:
                    detail.locator(":scope > summary").click()
                execution = artifact.locator(".research-execution-record")
                execution.locator(":scope > summary").click()
                payload = json.loads(execution.locator("pre").inner_text())
                expect(execution.locator("pre")).to_contain_text("source_sha256")
                assert payload["id"] and payload["source"]
                file = OUT / "exports" / f"execution.{payload['id']}.json"
                exact = json.loads(file.read_text())
                for key in ["source", "source_sha256", "status", "exit_code", "stdout", "stderr"]:
                    assert payload[key] == exact[key], (slug, key)
                execution.locator("summary").evaluate(
                    "node => node.scrollIntoView({block: 'start'})"
                )
                page.screenshot(path=str(OUT / f"{slug}-execution-{width}.png"))
                if slug == "subset-actual" and width == 1440:
                    conclusion = row.locator(".outcome-conclusion")
                    conclusion.get_by_role("button", name="Render Conclusion as Markdown").click()
                    expect(conclusion.locator(".outcome-markdown h3").first).to_contain_text(
                        "Partial finding"
                    )
                if slug == "subset-actual" and width in {390, 320}:
                    page.get_by_role("button", name="Project settings", exact=True).click()
                    settings_dialog = page.get_by_role("dialog", name="Settings")
                    expect(settings_dialog).to_be_visible()
                    bounds = settings_dialog.bounding_box()
                    assert (
                        bounds and bounds["x"] >= -1 and bounds["x"] + bounds["width"] <= width + 1
                    ), bounds
                    settings_dialog.get_by_role("tab", name="Preferences").click()
                    expect(
                        settings_dialog.get_by_role(
                            "checkbox", name="Show advanced Outcome details"
                        )
                    ).to_be_checked()
                    page.screenshot(path=str(OUT / f"settings-preferences-{width}.png"))
                    settings_dialog.get_by_role("button", name="Cancel", exact=True).click()
                observations.append(
                    {
                        "case": slug,
                        "session_id": run["session_id"],
                        "execution_id": payload["id"],
                        "status": payload["status"],
                        "width": width,
                        "reload_exact_execution_equal": True,
                        "horizontal_overflow": page.evaluate(
                            "document.documentElement.scrollWidth > window.innerWidth"
                        ),
                    }
                )
        assert not errors, errors
        browser.close()
    for project in manifest["projects"]:
        prefix = "subset" if project["slug"] == "nonconsecutive-subset-sums" else "algorithm"
        with urlopen(
            api_url + "/api/projects/export?" + urlencode({"path": project["path"]}),
            timeout=25,
        ) as response:
            final_raw = response.read()
        final_audit = json.loads(final_raw)
        prior_audit = json.loads((OUT / "exports" / f"{prefix}.after.audit.json").read_text())
        assert final_audit["research_sessions"] == prior_audit["research_sessions"]
        assert final_audit["project"]["show_advanced_outcome_details"] is True
        (OUT / "exports" / f"{prefix}.browser-final.audit.json").write_bytes(final_raw)
    (OUT / "inspection-observations.json").write_text(
        json.dumps(
            {
                "observations": observations,
                "page_errors": errors,
                "new_sessions": 0,
                "new_provider_calls": 0,
                "browser": "Actual installed Google Chrome, Playwright",
            },
            indent=2,
        )
    )
    print(
        "PASS existing execution source/output navigation and reload at 1440/390/320px; no page errors; 0 new sessions/calls. Overflow observations are recorded separately."
    )
finally:
    for p in [ui, api]:
        if p.poll() is None:
            p.terminate()
            p.wait(timeout=10)
