"""Deterministic real-Chrome acceptance for the Maximum Regions research lifecycle."""

import json
import os
import re
from urllib.parse import urlencode

from playwright.sync_api import expect, sync_playwright

base = os.environ.get("SIGMA_BROWSER_BASE_URL", "http://127.0.0.1:5173").rstrip("/")
fixture = os.environ.get("SIGMA_BROWSER_FIXTURE_URL", "http://127.0.0.1:8002").rstrip("/")

with sync_playwright() as playwright:
    browser = playwright.chromium.launch(
        executable_path=os.environ.get(
            "SIGMA_BROWSER_EXECUTABLE",
            "/Applications/Google Chrome.app/Contents/MacOS/Google Chrome",
        ),
        headless=True,
        args=["--disable-web-security"],
    )
    page = browser.new_page(viewport={"width": 1440, "height": 900})
    errors = []
    page.on("pageerror", lambda error: errors.append(str(error)))

    def forward(route):
        if route.request.url.endswith("/api/cloud-auth/status"):
            route.fulfill(
                status=200,
                content_type="application/json",
                body=json.dumps(
                    {
                        "target": "local",
                        "enabled": True,
                        "ready": True,
                        "authenticated": True,
                        "user": {"email": "happy-path@example.test", "role": "member"},
                        "admin_contact_email": None,
                    }
                ),
            )
            return
        response = route.fetch(url=route.request.url.replace(base, fixture))
        route.fulfill(response=response)

    page.route("**/api/**", forward)
    page.goto(base, wait_until="networkidle")
    samples = page.get_by_role("tab", name="Samples", exact=True)
    if samples.get_attribute("aria-selected") != "true":
        samples.click()
    panel = page.get_by_role("tabpanel", name="Samples", exact=True)
    groups = panel.locator("details.sample-type-group")
    math_group = next(
        group
        for group in groups.all()
        if "Mathematics" in group.locator(":scope > summary").inner_text()
    )
    if math_group.get_attribute("open") is None:
        math_group.locator(":scope > summary").click()
    panel.get_by_role("button", name="Open Maximum Regions Formed by Lines").click()
    page.wait_for_url("**/project?*")
    project_path = page.evaluate("new URL(location.href).searchParams.get('path')")
    expect(
        page.get_by_role("heading", name=re.compile(r"Maximum Regions Formed by Lines v\d+"))
    ).to_be_visible()
    expect(page.get_by_label("Research rounds")).to_have_count(0)
    page.get_by_role("button", name="Project settings", exact=True).click()
    settings = page.get_by_role("dialog", name="Settings")
    settings.get_by_role("tab", name="Limits", exact=True).click()
    expect(settings.get_by_label("Research rounds")).to_have_value("2")
    expect(settings.get_by_label("Maximum agent turns")).to_have_value("12")
    cost_input = settings.get_by_label("Maximum estimated session cost (USD)")
    cost_input.fill("  $2.00  ")
    save = settings.get_by_role("button", name="Save", exact=True)
    expect(save).to_be_enabled()
    save.click()
    expect(settings).to_be_hidden()
    saved_limits = page.evaluate(
        """async path => await (await fetch('/api/projects/research-limits?' + new URLSearchParams({path}))).json()""",
        project_path,
    )
    assert saved_limits["maximum_estimated_cost_usd"] == 2
    strategy = page.locator("li[data-strategy-id]").first
    strategy.locator(".strategy-row-disclosure").click()
    page.get_by_role("button", name="Start a new research session", exact=True).click()
    page.get_by_role("button", name="Start new session #1", exact=True).click()
    session = page.locator("li[data-session-id]").first
    expect(session.locator(".session-status")).to_have_text("ended", timeout=30000)
    expect(session.locator(".session-outcome-inline")).to_contain_text(
        "solution candidate (unverified)"
    )
    opened = page.evaluate(
        """async path => (await (await fetch('/api/projects/research-sessions?' + new URLSearchParams({path}))).json()).sessions[0]""",
        project_path,
    )
    assert opened["status"] == "ended", opened["status"]
    assert opened["calls_used"] == 4 and opened["calls_used"] <= opened["call_limit"]
    assert [step["role"] for step in opened["steps"]] == [
        "investigator",
        "skeptic",
        "investigator",
        "skeptic",
    ]
    assert [step["cycle"] for step in opened["steps"]] == [1, 1, 2, 2]
    assert len(opened["artifacts"]) == 2
    first, final = opened["artifacts"]
    assert "n^2+1" in first["investigator_output"]["claim"]
    assert first["skeptic_output"]["objections"]
    assert "R(n) = 1 + n(n+1)/2" in final["objective_review"]["claim"]
    assert final["sequence"] == 2 and final["strategy_cycle"] == 2
    assert "two-line" in final["skeptic_response"]
    assert opened["outcome"]["solution_review"]["status"] == "achieved"
    assert opened["estimated_cost_usd"] is not None and opened["cost_status"] == "available"
    usage = [step["token_usage"] for step in opened["steps"]]
    assert sum(item["input_tokens"] for item in usage) == 3600
    assert sum(item["cached_input_tokens"] for item in usage) == 400
    assert sum(item["output_tokens"] for item in usage) == 4800
    assert 0 < opened["estimated_cost_usd"] < 2
    project_json_bytes = page.evaluate(
        """async path => {
          const response = await fetch('/api/projects/audit?' + new URLSearchParams({path}));
          const audit = await response.json();
          return new TextEncoder().encode(JSON.stringify(audit.project)).length;
        }""",
        project_path,
    )
    context_bytes = opened["steps"][0]["context_manifest"]["assembled_context_bytes"]
    assert project_json_bytes < 1_000_000 and context_bytes < 256_000
    report = page.evaluate(
        """async path => await (await fetch('/api/projects/export/report?' + new URLSearchParams({path,format:'txt'}))).text()""",
        project_path,
    )
    assert "R(n) = 1 + n(n+1)/2" in report and "unverified" in report.lower()
    page.reload(wait_until="networkidle")
    page.goto(f"{base}/project?{urlencode({'path': project_path})}", wait_until="networkidle")
    reopened = page.evaluate(
        """async path => (await (await fetch('/api/projects/research-sessions?' + new URLSearchParams({path}))).json()).sessions[0]""",
        project_path,
    )
    assert reopened["id"] == opened["id"] and reopened["artifacts"] == opened["artifacts"]
    assert (
        reopened["steps"] == opened["steps"]
        and reopened["estimated_cost_usd"] == opened["estimated_cost_usd"]
    )
    assert not errors, errors
    browser.close()

print(
    "PASS deterministic Maximum Regions lifecycle: sample copy, flawed result, objection, revised result, final review, accounting, terminal outcome, report, reload and reopen"
)
print(
    f"MEASURED Maximum Regions copy: project payload {project_json_bytes} bytes; assembled provider context {context_bytes} bytes"
)
