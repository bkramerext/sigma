"""Real Chrome acceptance for Current Understanding strategy inference."""

import os
from urllib.parse import quote

from playwright.sync_api import expect, sync_playwright

UI = os.environ.get("SIGMA_BROWSER_BASE_URL", "http://127.0.0.1:5173").rstrip("/")
API = os.environ.get("SIGMA_BROWSER_FIXTURE_URL", "http://127.0.0.1:8002").rstrip("/")
PROVIDER = os.environ.get("SIGMA_FAKE_PROVIDER_URL", "http://127.0.0.1:8003").rstrip("/")
CHROME = os.environ.get(
    "SIGMA_BROWSER_EXECUTABLE",
    "/Applications/Google Chrome.app/Contents/MacOS/Google Chrome",
)
INFERRED = {
    "title": "Test intersections near the extremal arrangement",
    "summary": "Check whether intersection structure constrains arrangements near the known bound.",
    "approach": "Compare line arrangements that differ by one intersection from the extremal pattern. Derive a local counting invariant and test small cases; treat computations as exploratory evidence rather than proof.",
}

with sync_playwright() as playwright:
    browser = playwright.chromium.launch(executable_path=CHROME, headless=True)
    page = browser.new_page(viewport={"width": 1280, "height": 850})
    errors = []
    inference_requests = []
    page.on("pageerror", lambda error: errors.append(str(error)))

    def forward(route):
        request = route.request
        if request.method == "POST" and request.url.endswith("/api/projects/strategy-inference"):
            inference_requests.append(request.post_data_json)
        response = route.fetch(url=request.url.replace(UI, API))
        route.fulfill(response=response)

    page.route("**/api/**", forward)
    page.goto(UI, wait_until="networkidle")
    mock_identity = page.get_by_label("Mock authentication identity")
    if mock_identity.count():
        mock_identity.select_option("member-a")
    else:
        mode_result = page.evaluate(
            """async () => { const response = await fetch('/api/ai/mode', { method: 'POST', headers: { 'Content-Type': 'application/json' }, body: JSON.stringify({ mode: 'api_key' }) }); return { ok: response.ok, body: await response.json() }; }"""
        )
        assert mode_result["ok"], mode_result
    samples = page.get_by_role("tab", name="Samples", exact=True)
    if samples.get_attribute("aria-selected") != "true":
        samples.click()
    panel = page.get_by_role("tabpanel", name="Samples", exact=True)
    math_group = panel.locator("details.sample-type-group").filter(has_text="Mathematics")
    if math_group.get_attribute("open") is None:
        math_group.locator(":scope > summary").click()
    panel.get_by_role("button", name="Open Maximum Regions Formed by Lines").click()
    page.wait_for_url("**/project?*")
    understanding = page.locator(".current-understanding")
    understanding.wait_for()
    project_path = page.evaluate("new URL(location.href).searchParams.get('path')")
    assert project_path
    before = page.request.get(
        API + "/api/projects/inspect?path=" + quote(project_path, safe="")
    ).json()
    old_total = len(before["project"]["strategies"])
    action = understanding.get_by_role("button", name=f"Infer strategy #{old_total + 1}")
    expect(action).to_be_visible()
    assert "Uses current findings and unresolved research questions" in action.get_attribute(
        "data-tooltip"
    )
    action.evaluate("el => el.focus({ focusVisible: true })")
    expect(page.locator("#sigma-ui-tooltip")).to_contain_text(
        "identify and save a new strategy automatically"
    )
    action.press("Enter")
    expect(page.get_by_role("status").filter(has_text="Saved strategy:")).to_be_visible()
    expect(page.locator(".strategies-pane .section-count")).to_contain_text(
        str(len(before["project"]["active_order"]) + 1)
    )
    row = page.locator(".strategy-row").filter(has_text=INFERRED["title"])
    expect(row).to_be_visible()
    assert len(inference_requests) == 1
    assert inference_requests[0]["expected_project_id"] == before["project"]["id"]
    page.get_by_role("button", name="Generate", exact=True).evaluate(
        "button => { if (!button.dataset.tooltip.includes('review or edit it before saving')) throw Error('Generate tooltip missing'); if (button.title) throw Error('native tooltip used'); }"
    )
    page.set_viewport_size({"width": 390, "height": 844})
    expect(
        understanding.get_by_role("button", name=f"Infer strategy #{old_total + 2}")
    ).to_be_visible()
    row.get_by_role("button", name="Remove", exact=True).click()
    page.get_by_role("group", name=f"Confirm remove strategy {INFERRED['title']}").get_by_role(
        "button", name="Confirm"
    ).click()
    expect(page.locator(".strategies-pane .section-count")).to_contain_text(
        str(len(before["project"]["active_order"]))
    )
    replay = page.request.post(API + "/api/projects/strategy-inference", data=inference_requests[0])
    assert replay.ok, replay.text()
    replay_data = replay.json()
    assert replay_data["status"] == "completed"
    assert replay_data["strategy"]["title"] == INFERRED["title"]
    assert replay_data["strategy"]["removed_at"]
    assert any(
        item["id"] == replay_data["strategy"]["id"] and item["removed_at"]
        for item in replay_data["project"]["project"]["strategies"]
    )
    assert page.request.get(PROVIDER + "/__test/count").json()["responses"] == 1
    # Account/project binding rejection must happen before provider dispatch.
    mismatched = dict(inference_requests[0])
    mismatched["expected_project_id"] = "00000000-0000-0000-0000-000000000001"
    rejected = page.request.post(API + "/api/projects/strategy-inference", data=mismatched)
    assert rejected.status in (400, 404, 409), rejected.text()
    assert page.request.get(PROVIDER + "/__test/count").json()["responses"] == 1

    # A provider error is ambiguous and remains terminal across response retries.
    assert page.request.get(PROVIDER + "/__test/fail-next").ok
    failed_request = dict(inference_requests[0])
    failed_request["request_id"] = "f2222222-2222-4222-8222-222222222222"
    first_failure = page.request.post(API + "/api/projects/strategy-inference", data=failed_request)
    assert first_failure.status >= 400, first_failure.text()
    retry_failure = page.request.post(API + "/api/projects/strategy-inference", data=failed_request)
    assert retry_failure.status >= 400, retry_failure.text()
    assert page.request.get(PROVIDER + "/__test/count").json()["responses"] == 2
    page.reload()
    expect(page.locator(".current-understanding")).to_be_visible()
    expect(
        page.locator(".current-understanding").get_by_role(
            "button", name=f"Infer strategy #{old_total + 2}"
        )
    ).to_be_visible()
    expect(page.locator(".strategy-row").filter(has_text=INFERRED["title"])).to_have_count(0)
    after = page.request.get(
        API + "/api/projects/inspect?path=" + quote(project_path, safe="")
    ).json()
    assert any(
        item["title"] == INFERRED["title"] and item["removed_at"]
        for item in after["project"]["strategies"]
    )
    assert not errors, errors
    print(
        "PASS real Chrome issue #332 real inference endpoint, deterministic mock provider, binding rejection, terminal provider failure retry, durable replay after removal, count, reveal, remove/reopen, tooltips, keyboard and mobile visibility"
    )
    browser.close()
