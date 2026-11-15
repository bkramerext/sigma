"""Real Chrome release check on isolated copies of actual saved SIGMA projects.

Only the browser mutates the copies' project Preferences. Provider transport is
disabled. This script preserves the original copies and all research sessions.
"""

import json
import os
import re
import shutil
import socket
import subprocess
import sys
import tarfile
import tempfile
import time
from pathlib import Path
from urllib.parse import urlencode
from urllib.request import urlopen

from playwright.sync_api import expect, sync_playwright

ROOT = Path(os.environ.get("SIGMA_RELEASE_ROOT", Path(__file__).resolve().parents[3]))
OUT = Path(os.environ.get("SIGMA_RELEASE_OUT", Path(__file__).resolve().parent))
OUT.mkdir(parents=True, exist_ok=True)
EXPECTED_DIRECT_FOCUS = os.environ.get("SIGMA_EXPECT_DIRECT_FOCUS", "true") == "true"
EXPORTS = OUT / "exports"
EXPORTS.mkdir(exist_ok=True)
SOURCE_EXPORTS = ROOT / "docs/evaluations/increment_5/exports"
SOURCE_MANIFEST = json.loads((SOURCE_EXPORTS / "MANIFEST.json").read_text())
SCRATCH = Path(tempfile.mkdtemp(prefix="sigma-blue-main6-")).resolve()
PROJECTS = SCRATCH / "projects"
PROJECTS.mkdir(mode=0o700)
CHROME = "/Applications/Google Chrome.app/Contents/MacOS/Google Chrome"
SHA = subprocess.check_output(["git", "rev-parse", "HEAD"], cwd=ROOT, text=True).strip()
BASE_MAIN_SHA = subprocess.check_output(
    ["git", "merge-base", "HEAD", "origin/main"], cwd=ROOT, text=True
).strip()


def copy_project(item):
    slug = item["slug"]
    prefix = "subset" if slug == "nonconsecutive-subset-sums" else "algorithm"
    source = Path(item["path"])
    target = PROJECTS / f"{slug}.sigma"
    if source.is_dir():
        shutil.copytree(source, target)
        origin = str(source)
    else:
        archive = EXPORTS / f"{prefix}.project.tar.gz"
        if not archive.is_file():
            raise RuntimeError(f"Saved project source unavailable: {source}; no committed archive")
        with tarfile.open(archive, "r:gz") as bundle:
            bundle.extractall(PROJECTS, filter="data")
        origin = str(archive)
    changed = 0
    for file in (target / "research-sessions").glob("*.json"):
        if file.name in {"limits.json", "sequence.json"}:
            continue
        record = json.loads(file.read_text())
        if record.get("project_path") != str(target):
            record["project_path"] = str(target)
            file.write_text(json.dumps(record, indent=2))
            changed += 1
    return {
        "slug": slug,
        "prefix": prefix,
        "project_id": item["project_id"],
        "path": str(target),
        "source": origin,
        "rebound_session_paths": changed,
    }


COPIES = [copy_project(item) for item in SOURCE_MANIFEST["projects"]]
(OUT / "copy-provenance.json").write_text(
    json.dumps({"main_sha": SHA, "isolated_root": str(SCRATCH), "copies": COPIES}, indent=2)
)


def port():
    with socket.socket() as sock:
        sock.bind(("127.0.0.1", 0))
        return sock.getsockname()[1]


api_port, ui_port = port(), port()
api_url, ui_url = f"http://127.0.0.1:{api_port}", f"http://127.0.0.1:{ui_port}"
env = {
    key: value
    for key, value in os.environ.items()
    if not key.startswith(("SIGMA_", "OPENAI_", "ANTHROPIC_"))
}
for key in ["SIGMA_STATE_DIR", "SIGMA_AUTH_HOME", "SIGMA_CLOUD_AUTH_HOME"]:
    directory = SCRATCH / key
    directory.mkdir(mode=0o700)
    env[key] = str(directory)
env["SIGMA_PROJECTS_ROOT"] = str(PROJECTS)
env["SIGMA_API_TARGET"] = api_url
(SCRATCH / "offline_inspection.py").write_text("""import httpx
class OfflineClient(httpx.AsyncClient):
    def __init__(self,*args,**kwargs):
        kwargs['transport']=httpx.MockTransport(lambda req:httpx.Response(503,json={'error':'Offline release inspection; no provider calls permitted'}))
        super().__init__(*args,**kwargs)
httpx.AsyncClient=OfflineClient
from sigma.api import app
""")


def launch(command, output):
    return subprocess.Popen(
        command,
        cwd=ROOT,
        env=env,
        stdout=output.open("w"),
        stderr=subprocess.STDOUT,
        start_new_session=True,
    )


api = launch(
    [
        sys.executable,
        "-m",
        "uvicorn",
        "offline_inspection:app",
        "--app-dir",
        str(SCRATCH),
        "--host",
        "127.0.0.1",
        "--port",
        str(api_port),
    ],
    SCRATCH / "api.txt",
)
ui = launch(
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
    SCRATCH / "ui.txt",
)


def ready(url, process):
    for _ in range(200):
        if process.poll() is not None:
            raise RuntimeError(f"Server exited: {url}")
        try:
            with urlopen(url, timeout=1):
                return
        except OSError:
            time.sleep(0.1)
    raise RuntimeError(f"Server unavailable: {url}")


def api_json(route, path):
    with urlopen(
        api_url + "/api/projects/" + route + "?" + urlencode({"path": path}), timeout=25
    ) as response:
        return json.load(response)


def api_bytes(route, path, **extra):
    with urlopen(
        api_url + "/api/projects/" + route + "?" + urlencode({"path": path, **extra}), timeout=25
    ) as response:
        return response.read()


def open_project(page, copy):
    page.goto(ui_url + "/")
    page.get_by_role("button", name="Open", exact=True).click()
    dialog = page.get_by_role("dialog", name="Open Project")
    dialog.get_by_label("Project directory").fill(copy["path"])
    dialog.get_by_role("button", name="Open Project", exact=True).click()
    expect(page.locator(".current-understanding")).to_be_visible()


def preference(page, enabled):
    page.get_by_role("button", name="Project settings", exact=True).click()
    dialog = page.get_by_role("dialog", name="Settings")
    dialog.get_by_role("tab", name="Preferences").click()
    checkbox = dialog.get_by_role("checkbox", name="Show advanced Outcome details")
    checkbox.check() if enabled else checkbox.uncheck()
    dialog.get_by_role("button", name="Save", exact=True).click()
    expect(dialog).to_be_hidden()


def expand(row):
    disclosure = row.locator(".session-row-disclosure")
    if disclosure.get_attribute("aria-expanded") != "true":
        disclosure.click()
    expect(row.locator(".session-outcome")).to_be_visible()


observations = {
    "tested_sha": SHA,
    "base_main_sha": BASE_MAIN_SHA,
    "browser": subprocess.check_output([CHROME, "--version"], text=True).strip(),
    "provider_calls": 0,
    "new_sessions": 0,
    "projects": [],
    "viewports": [],
    "conclusion_markdown": [],
    "page_errors": [],
    "request_toasts": 0,
    "direct_artifact_focus": None,
}
baselines = {}
try:
    ready(api_url + "/openapi.json", api)
    ready(ui_url, ui)
    for copy in COPIES:
        original = json.loads(
            (SOURCE_EXPORTS / f"{copy['prefix']}.browser-final.audit.json").read_text()
        )
        before = api_json("export", copy["path"])
        assert before["project"]["id"] == original["project"]["id"]
        assert [item["id"] for item in before["research_sessions"]] == [
            item["id"] for item in original["research_sessions"]
        ]
        assert [item["artifacts"] for item in before["research_sessions"]] == [
            item["artifacts"] for item in original["research_sessions"]
        ]
        assert [item["steps"] for item in before["research_sessions"]] == [
            item["steps"] for item in original["research_sessions"]
        ]
        baselines[copy["slug"]] = before["research_sessions"]
        observations["projects"].append(
            {
                "slug": copy["slug"],
                "id": copy["project_id"],
                "sessions_before": len(before["research_sessions"]),
                "source_artifacts_steps_equal": True,
            }
        )

    with sync_playwright() as playwright:
        browser = playwright.chromium.launch(executable_path=CHROME, headless=True)
        page = browser.new_page(viewport={"width": 1440, "height": 1000})
        page.set_default_timeout(10000)
        page.on("pageerror", lambda error: observations["page_errors"].append(str(error)))
        page.route(
            "**/api/**",
            lambda route: route.fulfill(
                response=route.fetch(
                    url=route.request.url.replace(ui_url, api_url),
                    headers={**route.request.headers, "origin": "http://127.0.0.1:5173"},
                )
            ),
        )
        # Prepare two independent Simple preferences via the real settings UI.
        for copy in COPIES:
            open_project(page, copy)
            preference(page, False)
            expect(page.locator(".outcome-advanced")).to_have_count(0)
        for copy in COPIES:
            open_project(page, copy)
            actual_run = next(
                run
                for run in SOURCE_MANIFEST["runs"]
                if run["project_id"] == copy["project_id"] and run["mode"] == "actual"
            )
            row = page.locator(f'[data-session-id="{actual_run["session_id"]}"]')
            expand(row)
            simple = row.locator(".outcome-simple")
            expect(simple).to_be_visible()
            assert simple.locator(".outcome-summary-kicker").text_content().strip() == "Conclusion"
            assert len(simple.locator(".outcome-summary-text > p").first.inner_text()) <= 902
            if copy["prefix"] == "subset":
                old_id = json.loads((SOURCE_EXPORTS / "subset.before.audit.json").read_text())[
                    "research_sessions"
                ][0]["id"]
                historical = page.locator(f'[data-session-id="{old_id}"]')
                expand(historical)
                expect(historical.locator(".outcome-simple")).to_contain_text(
                    "Historical session summary"
                )
                assert (
                    "No Conclusion was saved"
                    not in historical.locator(".outcome-simple").inner_text()
                )
            for width in [1440, 390, 320]:
                page.set_viewport_size({"width": width, "height": 1000 if width == 1440 else 844})
                simple.evaluate("node => node.scrollIntoView({block:'start'})")
                overflow = page.evaluate("document.documentElement.scrollWidth > window.innerWidth")
                assert not overflow
                assert page.locator(".request-toast").count() == 0
                page.screenshot(path=str(OUT / f"{copy['prefix']}-simple-{width}.png"))
                observations["viewports"].append(
                    {
                        "project": copy["slug"],
                        "mode": "simple",
                        "width": width,
                        "overflow": overflow,
                    }
                )
            page.set_viewport_size({"width": 1440, "height": 1000})
            preference(page, True)
            page.reload()
            row = page.locator(f'[data-session-id="{actual_run["session_id"]}"]')
            expand(row)
            advanced = row.locator(".outcome-advanced")
            expect(advanced).to_be_visible()
            conclusion = row.locator(".outcome-conclusion")
            expect(conclusion).to_be_visible()
            conclusion_toggle = conclusion.locator("button.sigma-render-toggle")
            toggle_label = conclusion_toggle.get_attribute("aria-label")
            if toggle_label in {"Show saved Conclusion", "Render Conclusion as Markdown"}:
                if toggle_label == "Show saved Conclusion":
                    conclusion_toggle.click()
                    expect(conclusion_toggle).to_have_attribute("aria-pressed", "false")
                    expect(conclusion_toggle).to_have_attribute(
                        "aria-label", "Render Conclusion as Markdown"
                    )
                conclusion_toggle.click()
                expect(conclusion_toggle).to_have_attribute("aria-pressed", "true")
                expect(conclusion.locator(".outcome-markdown h3").first).to_be_visible()
                observations["conclusion_markdown"].append(
                    {
                        "project": copy["slug"],
                        "result": "PASS saved mathematical Conclusion rendered and source toggle retained",
                    }
                )
            else:
                # A non-mathematical saved conclusion offers provider-backed
                # formatting. Do not invoke it in this offline acceptance.
                assert toggle_label == "Format Conclusion with AI", toggle_label
                observations["conclusion_markdown"].append(
                    {
                        "project": copy["slug"],
                        "result": "BLOCKED provider-backed conversion intentionally not called",
                    }
                )
            saved = api_json("export", copy["path"])
            session = next(
                item
                for item in saved["research_sessions"]
                if item["id"] == actual_run["session_id"]
            )
            if copy["prefix"] == "subset":
                packet = next(iter(session["approved_continuations"].values()))
                inherited = row.locator(".continuation-evidence")
                assert inherited.get_attribute("open") is None
                inherited.locator(":scope > summary").click()
                expect(
                    inherited.get_by_role("button", name=re.compile("Approved source")).first
                ).to_be_visible()
                source_session = packet["sources"][0]["source"]["session_id"]
                inherited.get_by_role("button", name=re.compile("Approved source")).first.click()
                expect(
                    page.locator(f'[data-session-id="{source_session}"] .session-row-disclosure')
                ).to_have_attribute("aria-expanded", "true")
                assert packet["sources"][0]["artifact_id"] in inherited.inner_text()
                approved = {item["artifact_id"] for item in packet["sources"]}
                unapproved = next(
                    (artifact, old_session)
                    for old_session in saved["research_sessions"]
                    if old_session["id"] != session["id"]
                    for artifact in old_session["artifacts"]
                    if artifact["id"] not in approved
                )
                assert unapproved[0]["id"] not in {
                    item["artifact_id"] for item in packet["sources"]
                }
                old_row = page.locator(f'[data-session-id="{unapproved[1]["id"]}"]')
                expand(old_row)
                old_evidence = old_row.locator(".outcome-evidence-subsection")
                old_evidence.locator(":scope > summary").click()
                expect(old_evidence.locator(".research-artifacts > ol > li").first).to_be_visible()
                observations["unapproved_history_accessible"] = unapproved[0]["id"]
                current = api_json("current-understanding", copy["path"])
                findings = {item["id"]: item for item in current.get("findings", [])}
                chosen = next(
                    (
                        findings[item]
                        for item in current.get("current_finding_ids", [])
                        if item in findings and findings[item]["source"]["available"]
                    ),
                    None,
                )
                if chosen:
                    source = chosen["source"]
                    button = page.locator(
                        ".current-understanding button[aria-label^='Inspect finding']"
                    ).first
                    button.click()
                    expected_id = (
                        f"research-artifact-{source['session_id']}-{source['artifact_id']}"
                    )
                    if EXPECTED_DIRECT_FOCUS:
                        expect(page.locator(f"#{expected_id}")).to_be_focused()
                    else:
                        page.wait_for_timeout(250)
                        assert page.locator(f"#{expected_id}").count() == 0
                    observations["direct_artifact_focus"] = (
                        page.evaluate("document.activeElement.id") == expected_id
                    )
                    observations["direct_artifact_expected_id"] = expected_id
                    page.screenshot(path=str(OUT / "subset-inspect-finding-focused.png"))
            for width in [1440, 390, 320]:
                page.set_viewport_size({"width": width, "height": 1000 if width == 1440 else 844})
                page.reload()
                row = page.locator(f'[data-session-id="{actual_run["session_id"]}"]')
                expand(row)
                evidence = row.locator(".outcome-evidence-subsection")
                evidence.locator(":scope > summary").click()
                detail = evidence.locator(".research-artifacts > ol > li > details").first
                detail.locator(":scope > summary").click()
                execution = detail.locator(".research-execution-record")
                execution.locator(":scope > summary").click()
                payload = json.loads(execution.locator("pre").inner_text())
                api_record = api_json(f"research-executions/{payload['id']}", copy["path"])
                for key in ["id", "source", "source_sha256", "status", "stdout", "stderr", "agent"]:
                    assert payload[key] == api_record[key], (copy["slug"], key)
                assert payload["agent"]["role"] == "investigator"
                execution.locator("summary").evaluate(
                    "node => node.scrollIntoView({block:'start'})"
                )
                overflow = page.evaluate("document.documentElement.scrollWidth > window.innerWidth")
                assert not overflow
                assert page.locator(".request-toast").count() == 0
                page.screenshot(path=str(OUT / f"{copy['prefix']}-advanced-execution-{width}.png"))
                observations["viewports"].append(
                    {
                        "project": copy["slug"],
                        "mode": "advanced",
                        "width": width,
                        "execution_id": payload["id"],
                        "overflow": overflow,
                    }
                )
            if copy["prefix"] == "subset":
                page.set_viewport_size({"width": 320, "height": 844})
                page.get_by_role("button", name="Project settings", exact=True).click()
                dialog = page.get_by_role("dialog", name="Settings")
                bounds = dialog.bounding_box()
                assert bounds and bounds["x"] >= -1 and bounds["x"] + bounds["width"] <= 321
                dialog.get_by_role("tab", name="Preferences").click()
                expect(
                    dialog.get_by_role("checkbox", name="Show advanced Outcome details")
                ).to_be_checked()
                page.screenshot(path=str(OUT / "subset-preferences-320.png"))
                dialog.get_by_role("button", name="Cancel", exact=True).click()
                page.set_viewport_size({"width": 1440, "height": 1000})
        assert not observations["page_errors"], observations["page_errors"]
        assert observations["direct_artifact_focus"] is EXPECTED_DIRECT_FOCUS
        browser.close()

    for copy in COPIES:
        after_raw = api_bytes("export", copy["path"])
        after = json.loads(after_raw)
        assert after["research_sessions"] == baselines[copy["slug"]]
        assert after["project"]["show_advanced_outcome_details"] is True
        (EXPORTS / f"{copy['prefix']}.main.audit.json").write_bytes(after_raw)
        if copy["prefix"] == "subset":
            for fmt in ["txt", "html", "tex"]:
                (EXPORTS / f"subset.main.report.{fmt}").write_bytes(
                    api_bytes("export/report", copy["path"], format=fmt)
                )
    (OUT / "browser-observations.json").write_text(json.dumps(observations, indent=2) + "\n")
    print(
        json.dumps(
            {
                "result": "PASS",
                "tested_sha": SHA,
                "base_main_sha": observations["base_main_sha"],
                "browser": observations["browser"],
                "viewports": len(observations["viewports"]),
                "page_errors": observations["page_errors"],
                "direct_artifact_focus": observations["direct_artifact_focus"],
                "scratch": str(SCRATCH),
            },
            indent=2,
        )
    )
finally:
    for process in [ui, api]:
        if process.poll() is None:
            process.terminate()
            process.wait(timeout=10)
