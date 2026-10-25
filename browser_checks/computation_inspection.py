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
from urllib.request import urlopen

from playwright.sync_api import expect, sync_playwright

ROOT = Path(__file__).resolve().parents[1]
OUT = ROOT / "docs/evaluations/increment_4"
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
            for width in [1440, 390, 320]:
                page.set_viewport_size({"width": width, "height": 1000 if width == 1440 else 844})
                page.reload()
                row = page.locator(f'[data-session-id="{run["session_id"]}"]')
                row.wait_for()
                toggle = row.locator(".session-row-disclosure")
                if toggle.get_attribute("aria-expanded") != "true":
                    toggle.click()
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
