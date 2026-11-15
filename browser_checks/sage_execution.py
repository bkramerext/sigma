"""Real Chrome Investigator → real Sage → Skeptic, artifact and metrics checks."""

import json
import os
import time
from pathlib import Path
from tempfile import TemporaryDirectory
from urllib.parse import urlencode
from uuid import uuid4

from playwright.sync_api import expect, sync_playwright

browser_url = os.environ.get("SIGMA_BROWSER_BASE_URL", "http://127.0.0.1:5187")
fixture_url = os.environ.get("SIGMA_BROWSER_FIXTURE_URL", "http://127.0.0.1:8017")

with TemporaryDirectory(prefix="sigma-sage-browser-") as temporary, sync_playwright() as p:
    browser = p.chromium.launch(
        executable_path=os.environ.get(
            "SIGMA_BROWSER_EXECUTABLE",
            "/Applications/Google Chrome.app/Contents/MacOS/Google Chrome",
        ),
        headless=True,
        args=["--disable-web-security"],
    )
    page = browser.new_page(viewport={"width": 1440, "height": 1000})
    errors = []
    page.on("pageerror", lambda error: errors.append(str(error)))
    page.route(
        "**/api/**",
        lambda route: route.fulfill(
            response=route.fetch(url=route.request.url.replace(browser_url, fixture_url))
        ),
    )
    path = str(Path(temporary) / "sage.sigma")
    response = page.request.post(
        fixture_url + "/api/projects/init",
        data={
            "path": path,
            "title": "SageMath finite counterexample",
            "problem": "Sage fixture: Does passing the base-2 Fermat test certify primality?",
            "ai_model": "gpt-6.1-sol",
            "reasoning_effort": "medium",
        },
    )
    assert response.ok, response.text()
    project = response.json()["project"]
    response = page.request.post(
        fixture_url + "/api/projects/strategies",
        data={
            "path": path,
            "title": "Search exact composite witnesses",
            "approach": "Use SageMath exact modular arithmetic, then inspect any counterexample.",
        },
    )
    assert response.ok, response.text()
    strategy = response.json()["project"]["strategies"][0]
    limits = page.request.get(
        fixture_url + "/api/projects/research-limits", params={"path": path}
    ).json()
    limits["research_rounds"] = 1
    assert page.request.put(
        fixture_url + "/api/projects/research-limits", data={"path": path, **limits}
    ).ok
    config = page.request.get(
        fixture_url + "/api/projects/proposals/config", params={"path": path}
    ).json()
    response = page.request.post(
        fixture_url + "/api/projects/research-sessions/start",
        data={
            "path": path,
            "strategy_id": strategy["id"],
            "idempotency_key": str(uuid4()),
            "expected_project_id": project["id"],
            "expected_binding": config["binding"],
        },
    )
    assert response.ok, response.text()
    session_id = response.json()["id"]
    deadline = time.monotonic() + 90
    while time.monotonic() < deadline:
        session = page.request.get(
            fixture_url + f"/api/projects/research-sessions/{session_id}", params={"path": path}
        ).json()
        if session["status"] not in {"queued", "running"}:
            break
        page.wait_for_timeout(200)
    assert session["status"] == "ended", session
    assert session["calls_used"] == 2 and len(session["artifacts"]) == 1
    evidence = session["artifacts"][0]["investigator_output"]["sage_execution"]
    assert evidence["status"] == "completed" and evidence["runtime_version"] == "10.8"
    assert evidence["agent"]["step_id"] == session["steps"][0]["id"]
    raw = page.request.get(
        fixture_url
        + f"/api/projects/research-executions/{evidence['id']}/artifacts/witnesses.json",
        params={"path": path},
    )
    assert raw.ok and 341 in raw.json()
    page.goto(browser_url + "/project?" + urlencode({"path": path}))
    row = page.locator("li[data-session-id]").filter(has_text="Session #1")
    expect(row).to_be_visible()
    toggle = row.get_by_role("button", name="Session #1", exact=False)
    if not row.locator(".session-row-content").is_visible():
        toggle.click()
    outcome = row.get_by_role("region", name="Research outcome", exact=True)
    outcome.locator("details.outcome-subsection").filter(
        has=page.locator("summary", has_text="Metrics")
    ).locator("summary").first.click()
    expect(outcome).to_contain_text("SageMath runs by status")
    assert outcome.locator(".outcome-metric-group dl").evaluate_all(
        "elements => elements.every(e => getComputedStyle(e).display === 'block')"
    )
    expect(outcome).to_contain_text("1 completed")
    provenance = outcome.locator("details.outcome-subsection").filter(
        has=page.locator("summary", has_text="Provenance")
    )
    provenance.locator("summary").first.click()
    expect(provenance).to_contain_text(evidence["id"])
    obligations = outcome.locator(".outcome-evidence-subsection")
    obligations.locator("summary").first.click()
    cycle = obligations.locator(".research-artifacts ol > li > details").first
    cycle.locator("summary").first.click()
    expect(cycle).to_contain_text("SageMath execution · completed")
    expect(cycle).to_contain_text("witnesses.json")
    expect(cycle).to_contain_text(evidence["artifacts"][0]["sha256"])
    expect(cycle).to_contain_text("not proof of a mathematical claim")
    cycle.get_by_text("Execution source and output", exact=True).click()
    record_view = cycle.locator(".research-execution-record pre")
    expect(record_view).to_contain_text("COUNTEREXAMPLE: 341")
    expect(record_view).to_contain_text(evidence["source_sha256"])
    expect(record_view).to_contain_text("srange(3,1000,2)")
    exported = page.request.get(fixture_url + "/api/projects/audit", params={"path": path}).json()
    assert exported["research_sessions"][0]["outcome"]["metrics"] == session["outcome"]["metrics"]
    for fmt in ("txt", "html"):
        report = page.request.get(
            fixture_url + "/api/projects/export/report", params={"path": path, "format": fmt}
        )
        assert report.ok and "SageMath runs by status" in report.text()
    page.screenshot(path="/tmp/sigma-t26-sage-desktop.png", full_page=True)
    page.set_viewport_size({"width": 320, "height": 844})
    assert page.evaluate("document.documentElement.scrollWidth <= innerWidth")
    page.screenshot(path="/tmp/sigma-t26-sage-mobile.png", full_page=True)
    assert not errors, errors
    print(
        json.dumps(
            {
                "result": "PASS real Chrome Investigator→real Sage→Skeptic",
                "duration_ms": evidence["duration_ms"],
                "image_id": evidence["environment"]["image_id"],
                "source_sha256": evidence["source_sha256"],
                "artifact_sha256": evidence["artifacts"][0]["sha256"],
                "answer": evidence["stdout"].strip(),
            }
        ),
        flush=True,
    )
    page.unroute_all(behavior="ignoreErrors")
    browser.close()
