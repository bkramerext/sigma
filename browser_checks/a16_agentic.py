"""Real-Chrome A16 notebook flow against the isolated deterministic provider."""

import json
import os
import re
import time
from pathlib import Path

from playwright.sync_api import expect, sync_playwright

source = Path("samples/counting-constrained-binary-strings/project.json")
original = source.read_bytes()
fixture_url = os.environ.get("SIGMA_BROWSER_FIXTURE_URL", "http://127.0.0.1:8002")
ui_url = os.environ.get("SIGMA_BROWSER_BASE_URL", "http://127.0.0.1:5173")
with sync_playwright() as playwright:
    browser = playwright.chromium.launch(
        executable_path=os.environ.get(
            "SIGMA_BROWSER_EXECUTABLE",
            "/Applications/Google Chrome.app/Contents/MacOS/Google Chrome",
        ),
        headless=True,
        args=["--disable-web-security"],
    )
    context = browser.new_context(viewport={"width": 1440, "height": 900}, reduced_motion="reduce")
    page = context.new_page()
    errors = []
    page.on("pageerror", lambda error: errors.append(str(error)))

    def select_samples():
        tab = page.get_by_role("tab", name="Samples", exact=True)
        if tab.get_attribute("aria-selected") != "true":
            tab.click()

    page.route(
        "**/api/**",
        lambda route: route.continue_(url=route.request.url.replace(ui_url, fixture_url)),
    )
    page.goto(ui_url)
    select_samples()
    page.get_by_role("tabpanel", name="Samples", exact=True).get_by_role(
        "button", name="Open Maximum Regions Formed by Lines"
    ).click()
    expect(
        page.get_by_role("heading", name=re.compile(r"Maximum Regions Formed by Lines,? v\d+"))
    ).to_be_visible()
    expect(page.locator(".strategy-row")).to_have_count(1)
    maximum_path = page.evaluate("new URL(location.href).searchParams.get('path')")
    maximum_state = Path(maximum_path) / "project.json"
    maximum_before = maximum_state.read_bytes()
    assert len(json.loads(maximum_before)["strategies"]) == 1
    page.get_by_role("button", name="Generate", exact=True).click()
    maximum_composer = page.locator(".inline-proposal")
    maximum_composer.get_by_role("button", name="Generate", exact=True).click()
    expect(maximum_composer.get_by_label("Title", exact=True)).to_have_value(
        "Planar graph Euler count"
    )
    expect(maximum_composer.get_by_label("Plan", exact=True)).to_contain_text("Euler's formula")
    expect(maximum_composer.get_by_label("Independent review")).to_contain_text(
        "saved baseline adds lines"
    )
    assert maximum_state.read_bytes() == maximum_before
    maximum_export = page.evaluate(
        "async path => (await (await fetch('/api/projects/export?' + new URLSearchParams({path}))).json())",
        maximum_path,
    )
    assert len(maximum_export["agentic_runs"]) == 1
    assert maximum_export["agentic_runs"][0]["terminal"]["status"] == "completed"
    maximum_composer.get_by_role("button", name="Cancel", exact=True).click()
    page.get_by_role("button", name="Back to home", exact=True).click()
    select_samples()
    page.get_by_role("tabpanel", name="Samples", exact=True).get_by_role(
        "button", name="Open Counting Constrained Binary Strings"
    ).click()
    expect(
        page.get_by_role("heading", name=re.compile(r"Counting Constrained Binary Strings,? v\d+"))
    ).to_be_visible()
    expect(page.locator(".strategy-row")).to_have_count(0)
    path = page.evaluate("new URL(location.href).searchParams.get('path')")
    project_file = Path(path) / "project.json"
    baseline = project_file.read_bytes()
    assert json.loads(baseline)["strategies"] == []

    def export():
        return page.evaluate(
            "async path => (await (await fetch('/api/projects/export?' + new URLSearchParams({path}))).json())",
            path,
        )

    before = export()
    assert before["agentic_runs"] == []
    page.get_by_role("button", name="Generate", exact=True).click()
    composer = page.locator(".inline-proposal")
    expect(composer).to_be_visible()
    composer.get_by_label("Starting point (optional)").fill("error-fixture")
    composer.get_by_role("button", name="Generate", exact=True).click()
    expect(composer.locator('[role="alert"]')).to_contain_text("HTTP 500")
    expect(page.locator(".request-toast")).to_have_count(1)
    failed = export()
    assert len(failed["agentic_runs"]) == 1
    assert failed["agentic_runs"][0]["terminal"]["status"] == "failed"
    page.get_by_role("button", name="Dismiss request error").click()
    invalid_stream = {
        "type": "run.started",
        "sequence": 1,
        "run_id": "a" * 32,
        "max_calls": 6,
        "summary": "fixture start",
    }
    page.route(
        "**/api/projects/proposals/agentic",
        lambda route: route.fulfill(
            status=200,
            headers={"Content-Type": "text/event-stream"},
            body=f"data: {json.dumps(invalid_stream)}\n\n",
        ),
    )
    composer.get_by_role("button", name="Generate", exact=True).click()
    expect(composer.locator('[role="alert"]')).to_contain_text("without a final result")
    expect(page.locator(".request-toast")).to_have_count(1)
    assert project_file.read_bytes() == baseline
    page.get_by_role("button", name="Dismiss request error").click()
    page.unroute("**/api/projects/proposals/agentic")
    composer.get_by_label("Starting point (optional)").fill("")
    composer.get_by_label("Starting point (optional)").fill("delay-fixture")
    composer.get_by_role("button", name="Generate", exact=True).click()
    expect(composer.locator(".agentic-current")).to_contain_text("Exploring a candidate")
    composer.get_by_role("button", name="Cancel request", exact=True).click()
    expect(composer.locator('[role="alert"]')).to_contain_text("Run cancelled")
    assert project_file.read_bytes() == baseline
    composer.get_by_label("Starting point (optional)").fill("")
    composer.get_by_role("button", name="Generate", exact=True).click()
    expect(composer.get_by_label("Title", exact=True)).to_have_value("Terminal-symbol recurrence")
    cancelled = export()
    deadline = time.monotonic() + 5
    while (
        cancelled["agentic_runs"]
        and cancelled["agentic_runs"][-1]["terminal"] is None
        and time.monotonic() < deadline
    ):
        time.sleep(0.05)
        cancelled = export()
    assert len(cancelled["agentic_runs"]) >= 2
    assert cancelled["agentic_runs"][0]["terminal"]["status"] == "failed"
    assert cancelled["agentic_runs"][1]["terminal"]["status"] == "cancelled"
    assert cancelled["project"]["strategies"] == []

    expect(composer.locator(".agentic-activity")).to_contain_text("Exploring a candidate")
    expect(composer.locator(".agentic-activity")).to_contain_text("Independent challenge")
    expect(composer.get_by_label("Independent review")).to_contain_text(
        "The proposed mechanism is distinct"
    )
    expect(composer.get_by_label("Title", exact=True)).to_have_value("Terminal-symbol recurrence")
    expect(composer.get_by_label("Plan", exact=True)).to_contain_text("Mechanism")
    assert (
        composer.evaluate(
            "e => { const filament = document.createElement('span'); filament.className = 'agentic-filament'; e.append(filament); const duration = getComputedStyle(filament).animationDuration; filament.remove(); return duration; }"
        )
        == "0s"
    )
    assert project_file.read_bytes() == baseline
    completed = export()
    assert len(completed["agentic_runs"]) == 3
    assert completed["agentic_runs"][-1]["terminal"]["status"] == "completed"
    assert [step["role"] for step in completed["agentic_runs"][-1]["steps"]] == [
        "explore",
        "challenge",
    ]
    composer.get_by_label("Title", exact=True).fill("Human reviewed recurrence")
    composer.get_by_role("button", name="Accept", exact=True).click()
    expect(page.locator(".strategy-row")).to_have_count(1)
    saved = json.loads(project_file.read_bytes())
    assert saved["strategies"][0]["title"] == "Human reviewed recurrence"
    page.reload()
    expect(page.locator(".strategy-row")).to_have_count(1)

    page.get_by_role("button", name="Generate", exact=True).click()
    composer = page.locator(".inline-proposal")
    composer.get_by_role("button", name="Generate", exact=True).click()
    expect(composer.get_by_label("Title", exact=True)).to_have_value("Position-shift subset count")
    export_after = export()
    assert len(export_after["agentic_runs"]) == 4
    assert export_after["agentic_runs"][-1]["terminal"]["status"] == "completed"
    composer.get_by_role("button", name="Cancel", exact=True).click()
    expect(page.locator(".strategy-row")).to_have_count(1)
    page.get_by_role("button", name="Generate", exact=True).click()
    composer = page.locator(".inline-proposal")
    composer.get_by_label("Starting point (optional)").fill("long-fixture")
    composer.get_by_role("button", name="Generate", exact=True).click()
    expect(composer.get_by_label("Title", exact=True)).to_have_value(
        "Long strategy field regression"
    )
    long_approach = composer.get_by_label("Plan", exact=True).input_value()
    assert len(long_approach) > 10_000
    composer.get_by_role("button", name="Accept", exact=True).click()
    expect(page.locator(".strategy-row")).to_have_count(2)
    long_saved = json.loads(project_file.read_bytes())["strategies"][-1]["approach"]
    assert long_saved == long_approach
    assert source.read_bytes() == original
    assert not errors, errors
    print(
        "PASS real Chrome A16: Maximum Regions baseline gets a distinct Euler mechanism; ordered Explore/Challenge progress, reduced motion, disconnect cancellation and retained evidence, error recovery, unsaved editable draft, explicit save/reopen, distinct follow-up candidate, >10k strategy editing and save/reopen, project export, immutable Sample sources"
    )
    page.unroute_all(behavior="ignoreErrors")
    browser.close()
