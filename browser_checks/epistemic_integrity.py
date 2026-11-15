"""Increment 1: real Chrome review of unchanged archives and declaration variants.

No provider dispatch, argument enrichment, or canonical project mutation. The
variant records change only verification declarations to test presentation;
they do not represent successful research or independent verification.
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
ARCHIVE = (
    REPO
    / "docs/evaluations/fixtures/t17-8-answer-free/live-session-91e96112-27ce-412e-841f-5cbf67cbba75.json"
)
EVIDENCE = Path(os.environ.get("SIGMA_EPISTEMIC_EVIDENCE", "/tmp/sigma-epistemic-integrity"))
EVIDENCE.mkdir(parents=True, exist_ok=True)


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
    raise RuntimeError("Isolated server did not become ready")


source_hashes = {
    str(p.relative_to(REPO)): hashlib.sha256(p.read_bytes()).hexdigest()
    for p in [ARCHIVE, *REPO.glob("samples/**/*")]
    if p.is_file()
}
observed = []
with tempfile.TemporaryDirectory(prefix="sigma-epistemic-browser-") as temporary:
    scratch = Path(temporary)
    root = scratch / "projects"
    root.mkdir()
    for name, code in [
        ("archive", "original"),
        ("incomplete", "incomplete"),
        ("unknown", "unknown"),
        ("verified", "verified"),
        ("missing", None),
    ]:
        data = json.loads(ARCHIVE.read_text())
        dest = root / (name + ".sigma")
        dest.mkdir()
        (dest / "project.json").write_text(json.dumps(data["project"]))
        (dest / "research-sessions").mkdir()
        session = data["research_sessions"][0]
        session["project_path"] = str(dest.resolve())
        if code != "original":
            for artifact in session["artifacts"]:
                if code is None:
                    artifact["objective_review"].pop("verification_status", None)
                else:
                    artifact["objective_review"]["verification_status"] = code
        (dest / "research-sessions" / (session["id"] + ".json")).write_text(json.dumps(session))
    record_hashes = {
        str(p.relative_to(root)): hashlib.sha256(p.read_bytes()).hexdigest()
        for p in root.rglob("*.json")
    }
    api_port, ui_port = free_port(), free_port()
    while api_port == ui_port:
        ui_port = free_port()
    api_url, ui_url = f"http://127.0.0.1:{api_port}", f"http://127.0.0.1:{ui_port}"
    env = {
        key: value
        for key, value in os.environ.items()
        if not key.startswith(("SIGMA_", "OPENAI_", "ANTHROPIC_"))
    }
    for key, name in [
        ("SIGMA_PROJECTS_ROOT", "projects"),
        ("SIGMA_STATE_DIR", "state"),
        ("SIGMA_AUTH_HOME", "auth"),
        ("SIGMA_CLOUD_AUTH_HOME", "cloud-auth"),
    ]:
        directory = scratch / name
        directory.mkdir(exist_ok=True, mode=0o700)
        env[key] = str(directory)
    server = scratch / "offline_api.py"
    server.write_text("""import httpx
class OfflineClient(httpx.AsyncClient):
    def __init__(self, *args, **kwargs):
        kwargs['transport'] = httpx.MockTransport(lambda request: httpx.Response(503, json={'error': 'No external requests in this check'}))
        super().__init__(*args, **kwargs)
httpx.AsyncClient = OfflineClient
from sigma.api import app
""")
    api = subprocess.Popen(
        [
            "uv",
            "run",
            "python",
            "-m",
            "uvicorn",
            "offline_api:app",
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
        try:
            ready(api_url + "/openapi.json", api)
        except RuntimeError:
            print((scratch / "api.log").read_text())
            raise
        ready(ui_url, ui)
        with sync_playwright() as pw:
            browser = pw.chromium.launch(
                executable_path=os.environ.get(
                    "SIGMA_BROWSER_EXECUTABLE",
                    "/Applications/Google Chrome.app/Contents/MacOS/Google Chrome",
                ),
                headless=True,
            )
            page = browser.new_page(viewport={"width": 1440, "height": 1000})
            errors, inference_requests = [], []
            page.on("pageerror", lambda error: errors.append(str(error)))
            page.on(
                "request",
                lambda request: (
                    inference_requests.append(request.url)
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
            for name, label in [
                ("archive", "Convincing but unverified"),
                ("incomplete", "Incomplete"),
                ("unknown", "Unknown"),
                ("verified", "Reported verified; not independently checked by SIGMA"),
                ("missing", "Unknown"),
            ]:
                page.goto(ui_url + "/project?path=" + quote(str(root / (name + ".sigma")), safe=""))
                row = page.locator("li[data-session-id]")
                row.wait_for()
                disclosure = row.locator(".session-row-disclosure")
                if disclosure.get_attribute("aria-expanded") != "true":
                    disclosure.click()
                outcome = row.get_by_role("region", name="Research outcome")
                expect(outcome.locator(".outcome-label")).to_contain_text(
                    "unstructured argument, unassessed"
                )
                expect(outcome.locator(".outcome-verification")).to_have_text(
                    "Verification: " + label
                )
                expect(outcome.locator(".outcome-conclusion")).to_contain_text(
                    "saved narrative is available"
                )
                # Conclusion source and rendered modes retain the availability notice and current label.
                outcome.get_by_role(
                    "button", name="Render Conclusion as Markdown", exact=True
                ).click()
                expect(outcome.locator(".outcome-conclusion")).to_contain_text(
                    "saved narrative is available"
                )
                outcome.get_by_role(
                    "button", name="Show Conclusion Markdown source", exact=True
                ).click()
                for detail in outcome.locator(".outcome-subsection").all():
                    if detail.get_attribute("open") is None:
                        detail.locator(":scope > summary").click()
                for field in outcome.locator(".outcome-label-value").all():
                    if field.locator("dt").inner_text() in ("Verification", "Verification status"):
                        expect(field.locator("dd")).to_contain_text(label)
                evidence_review = outcome.locator(".outcome-evidence-subsection .solution-review")
                expect(evidence_review).to_contain_text("Verification: " + label)
                expect(outcome).not_to_contain_text("substantive argument not captured")
                # Both normal and rendered Outcome use the same Python presentation label.
                outcome.get_by_role("button", name="Render outcome as Markdown", exact=True).click()
                expect(outcome.locator(":scope > .outcome-markdown")).to_contain_text(
                    "Verification: " + label
                )
                outcome.get_by_role("button", name="Show plain outcome text", exact=True).click()
                if name == "archive":
                    expect(outcome).to_contain_text("L_i∩L_k")
                widths = []
                for width, height in [(1440, 1000), (390, 844)]:
                    page.set_viewport_size({"width": width, "height": height})
                    dimensions = page.evaluate(
                        "({width:innerWidth,scrollWidth:document.documentElement.scrollWidth})"
                    )
                    assert dimensions["scrollWidth"] <= width, dimensions
                    widths.append(dimensions)
                    if name in ("archive", "incomplete"):
                        outcome.locator(".outcome-conclusion").scroll_into_view_if_needed()
                        page.screenshot(path=str(EVIDENCE / f"{name}-{width}.png"))
                page.set_viewport_size({"width": 1440, "height": 1000})
                observed.append(
                    {
                        "record": name,
                        "label": label,
                        "dimensions": widths,
                        "kind": "unchanged historical archive"
                        if name == "archive"
                        else "synthetic declaration variant only",
                    }
                )
            page.goto(ui_url + "/")
            tab = page.get_by_role("tab", name="Samples", exact=True)
            if tab.get_attribute("aria-selected") != "true":
                tab.click()
            page.get_by_role(
                "button", name="Open Nonconsecutive Subset Sums Modulo 3", exact=True
            ).click()
            rows = page.locator("li[data-session-id]")
            expect(rows).to_have_count(5)
            for row in rows.all():
                if row.locator(".session-row-disclosure").get_attribute("aria-expanded") != "true":
                    row.locator(".session-row-disclosure").click()
                expect(row.locator(".outcome-verification")).to_have_text(
                    "Verification: Incomplete"
                )
                evidence = row.locator(".outcome-evidence-subsection")
                if evidence.get_attribute("open") is None:
                    evidence.locator(":scope > summary").click()
                expect(evidence.locator(".solution-review")).to_contain_text(
                    "Verification: Incomplete"
                )
                row.get_by_role("button", name="Render outcome as Markdown", exact=True).click()
                expect(row.locator(".session-outcome > .outcome-markdown")).to_contain_text(
                    "Verification: Incomplete"
                )
            for width, height in [(1440, 1000), (390, 844)]:
                page.set_viewport_size({"width": width, "height": height})
                assert page.evaluate("document.documentElement.scrollWidth <= innerWidth")
                rows.first.locator(".outcome-conclusion").scroll_into_view_if_needed()
                page.screenshot(path=str(EVIDENCE / f"nonconsecutive-{width}.png"))
            assert not errors, errors
            assert not inference_requests, inference_requests
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
        hashlib.sha256((root / name).read_bytes()).hexdigest() == value
        for name, value in record_hashes.items()
    )
assert all(
    hashlib.sha256((REPO / name).read_bytes()).hexdigest() == value
    for name, value in source_hashes.items()
)
(EVIDENCE / "observations.json").write_text(
    json.dumps(
        {
            "browser": browser_version,
            "observed": observed,
            "nonconsecutive_fixture_sessions": 5,
            "source_hashes": source_hashes,
            "source_records_unchanged": True,
            "page_errors": errors,
            "inference_requests": inference_requests,
            "provider_calls": 0,
        },
        indent=2,
    )
)
print(
    "PASS real Chrome: conservative status matrix, unchanged historical narrative, five deterministic subset fixtures, Conclusion/Outcome source/rendered modes, desktop/narrow, no inference"
)
