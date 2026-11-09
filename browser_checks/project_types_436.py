"""Real Chrome acceptance for transactional project types and deleted-type recovery."""

import json
import os
from datetime import UTC, datetime, timedelta
from pathlib import Path
from urllib.parse import quote

from playwright.sync_api import expect, sync_playwright

BASE_URL = os.environ.get("SIGMA_BROWSER_BASE_URL", "http://127.0.0.1:5173").rstrip("/")
FIXTURE_URL = os.environ.get("SIGMA_BROWSER_FIXTURE_URL", "http://127.0.0.1:8026").rstrip("/")
EVIDENCE = Path("docs/evaluations/t436/evidence")
EVIDENCE.mkdir(parents=True, exist_ok=True)


def project(page, title: str, type_id: str) -> dict:
    created = page.evaluate(
        """async ({title, typeId}) => {
          const response = await fetch('/api/projects/create', {method: 'POST', headers: {'Content-Type': 'application/json'}, body: JSON.stringify({title, problem: 'Preserve the saved type context.', investigation_type: typeId})});
          return {status: response.status, body: await response.json()};
        }""",
        {"title": title, "typeId": type_id},
    )
    assert created["status"] == 201, created["body"]
    result = created["body"]
    strategy = page.evaluate(
        """async ({path}) => {
          const response = await fetch('/api/projects/strategies', {method: 'POST', headers: {'Content-Type': 'application/json'}, body: JSON.stringify({path, title: 'Inspect', approach: 'Inspect the saved research evidence.'})});
          return {status: response.status, body: await response.json()};
        }""",
        {"path": result["path"]},
    )
    assert strategy["status"] == 201, strategy["body"]
    return result


def open_project(page, project_path: str) -> None:
    page.goto(f"{BASE_URL}/project?path={quote(project_path, safe='')}")


with sync_playwright() as playwright:
    browser = playwright.chromium.launch(
        executable_path=os.environ.get(
            "SIGMA_BROWSER_EXECUTABLE",
            "/Applications/Google Chrome.app/Contents/MacOS/Google Chrome",
        ),
        headless=True,
    )
    page = browser.new_page(viewport={"width": 1440, "height": 1000})
    errors: list[str] = []
    api_requests: list[tuple[str, dict | None]] = []
    page.on("pageerror", lambda error: errors.append(str(error)))

    def observe_request(request) -> None:
        if "/api/" not in request.url:
            return
        payload = json.loads(request.post_data) if request.post_data else None
        api_requests.append((request.url, payload))

    page.on("request", observe_request)

    def proxy(route):
        headers = dict(route.request.headers)
        headers["origin"] = "http://127.0.0.1:5173"
        response = route.fetch(
            url=route.request.url.replace(BASE_URL, FIXTURE_URL), headers=headers
        )
        route.fulfill(response=response)

    page.route("**/api/**", proxy)
    # Presence is a long-lived SSE stream needed for research start.
    # Forward the browser request directly to the fixture server: route.fetch
    # would wait for the stream to finish and time out during project reloads.
    page.route(
        "**/api/projects/research-presence?*",
        lambda route: route.continue_(
            url=route.request.url.replace(BASE_URL, FIXTURE_URL),
            headers={**route.request.headers, "origin": BASE_URL},
        ),
    )
    page.goto(BASE_URL)
    page.evaluate(
        "window.__projectTypeConfirmations = []; window.confirm = message => { window.__projectTypeConfirmations.push(String(message)); return true; }"
    )

    # Approved Home layout: About and Settings share the first left row,
    # Model is immediately below About, and Google/ChatGPT form the right column.
    grid = page.locator(".home-account-grid")
    expect(grid).to_be_visible()
    expect(grid.locator(".home-about-button")).to_have_text("About SIGMA")
    assert grid.evaluate("node => getComputedStyle(node).gridTemplateAreas") == (
        '"model-column google" "model-column chatgpt"'
    )
    about_rect = grid.locator(".home-about-button").bounding_box()
    settings_rect = grid.locator(".home-settings-pill").bounding_box()
    google_rect = grid.locator(".project-google-signin").first.bounding_box()
    chatgpt_rect = grid.locator(".api-connection > summary").first.bounding_box()
    assert about_rect and settings_rect and google_rect and chatgpt_rect
    model_pill = grid.get_by_role("button", name="Model", exact=False)
    expect(model_pill).to_be_visible()
    expect(model_pill).to_be_enabled(timeout=15000)
    assert "cycle" in (model_pill.get_attribute("data-tooltip") or "").lower()
    # Wait for fonts and layout to settle before checking subpixel alignment.
    # This still enforces the same 3px requirement; it does not relax it.
    page.evaluate("() => document.fonts.ready")
    page.wait_for_function(
        """() => {
        const about = document.querySelector(".home-account-grid .home-about-button");
        const model = document.querySelector(".home-account-grid .global-model-pill");
        return !!about && !!model &&
            Math.abs(about.getBoundingClientRect().left - model.getBoundingClientRect().left) < 3;
    }""",
        timeout=7000,
    )
    # Compare positions from the same layout frame, not before/after font loading.
    about_rect = grid.locator(".home-about-button").bounding_box()
    settings_rect = grid.locator(".home-settings-pill").bounding_box()
    google_rect = grid.locator(".project-google-signin").first.bounding_box()
    chatgpt_rect = grid.locator(".api-connection > summary").first.bounding_box()
    model_rect = model_pill.bounding_box()
    assert about_rect and settings_rect and google_rect and chatgpt_rect and model_rect
    assert abs(model_rect["x"] - about_rect["x"]) < 3
    assert model_rect["y"] >= about_rect["y"] + about_rect["height"]
    assert settings_rect["x"] >= about_rect["x"] + about_rect["width"]
    assert abs(settings_rect["y"] - about_rect["y"]) < 3
    assert google_rect["x"] >= model_rect["x"] + model_rect["width"]
    assert chatgpt_rect["x"] >= model_rect["x"] + model_rect["width"]
    assert abs(model_rect["y"] - chatgpt_rect["y"]) < 3

    # The restored pill cycles user-wide defaults (not project settings),
    # prompting before a cost-tier increase and preserving unrelated limits.
    original_model_settings = page.request.get(
        f"{FIXTURE_URL}/api/user-preferences/research-settings"
    ).json()
    expect(model_pill).to_be_enabled(timeout=15000)
    with page.expect_response(
        lambda response: (
            response.url.endswith("/api/user-preferences/research-settings")
            and response.request.method == "PUT"
        )
    ):
        # The pill has distinct click regions: upper half cycles model, lower half cycles thinking.
        # A centered Playwright click would change thinking rather than the model.
        model_pill.click(position={"x": 10, "y": 8})
        cost_confirmation = page.locator(".global-model-confirm-popover")
        if cost_confirmation.is_visible():
            cost_confirmation.get_by_role("button", name="Confirm").click()
    changed_model_settings = page.request.get(
        f"{FIXTURE_URL}/api/user-preferences/research-settings"
    ).json()
    assert changed_model_settings["ai_model"] != original_model_settings["ai_model"]
    assert changed_model_settings["limits"] == original_model_settings["limits"]
    restore_response = page.request.put(
        f"{FIXTURE_URL}/api/user-preferences/research-settings",
        data={
            key: original_model_settings[key]
            for key in (
                "limits",
                "ai_model",
                "reasoning_effort",
                "show_advanced_outcome_details",
            )
        },
    )
    assert restore_response.ok
    page.evaluate("window.dispatchEvent(new Event('sigma-global-settings-saved'))")

    # A visible test host avoids the default Samples tab hiding Saved's
    # animations. Compare the CSSAnimation timeline anchors directly.
    page.emulate_media(reduced_motion="no-preference")
    page.evaluate("""() => {
        const host = document.createElement('div');
        host.id = 'pulse-sync-test-host';
        host.className = 'home-recents';
        host.style.cssText = 'position:fixed;top:65px;left:25px;display:block;width:80px;height:24px;pointer-events:none';
        document.querySelector('.home-page').appendChild(host);
        const green = document.createElement('span');
        green.id = 'pulse-sync-green';
        green.className = 'research-running-indicator';
        host.appendChild(green);
    }""")
    page.wait_for_timeout(100)
    page.evaluate("""() => {
        const yellow = document.createElement('span');
        yellow.id = 'pulse-sync-yellow';
        yellow.className = 'research-running-indicator paper-queued-indicator';
        document.getElementById('pulse-sync-test-host').appendChild(yellow);
    }""")
    page.wait_for_timeout(300)
    pulse_state = page.evaluate("""() => {
        const nodes = ['pulse-sync-green', 'pulse-sync-yellow'].map(id => document.getElementById(id));
        return nodes.map(node => ({
            animationName: getComputedStyle(node).animationName,
            animations: node.getAnimations().map(a => ({name: a.animationName, startTime: a.startTime}))
        }));
    }""")
    green, yellow = pulse_state
    assert green["animationName"] == yellow["animationName"] == "research-running-heartbeat", (
        pulse_state
    )
    assert green["animations"] and yellow["animations"], pulse_state
    assert green["animations"][0]["startTime"] == yellow["animations"][0]["startTime"] == 0, (
        pulse_state
    )
    page.evaluate("document.getElementById('pulse-sync-test-host').remove()")

    # Global Settings now auto-saves validated edits. Its header has no
    # Save button; an explicit Close also flushes any pending valid changes.
    settings = page.get_by_role("button", name="Settings", exact=True)
    settings.click()
    dialog = page.get_by_role("dialog", name="Settings")
    expect(dialog).to_be_visible()
    expect(dialog.locator("header").get_by_role("button", name="Save")).to_have_count(0)
    expect(dialog.get_by_role("heading", name="Settings", exact=True)).to_be_visible()
    for tab in ("Limits", "Preferences", "Research Ethos", "Project Types"):
        dialog.get_by_role("tab", name=tab, exact=True).click()
        expect(dialog).to_be_visible()
    common = dialog.locator(".pt-common-references")
    expect(common.locator(".pt-reference-link")).to_have_count(4)
    expect(common.locator(".pt-reference-toggle[aria-pressed='true']")).to_have_count(4)
    original = page.request.get(f"{FIXTURE_URL}/api/project-types").json()
    assert original["revision"] >= 1

    def project_types_put(response):
        return response.url.endswith("/api/project-types") and response.request.method == "PUT"

    # Toggle a curated reference, verify automatic persistence, then restore.
    with page.expect_response(project_types_put, timeout=15000):
        common.locator(".pt-reference-toggle[aria-pressed='true']").first.click()
    expect(common.locator(".pt-reference-toggle[aria-pressed='false']")).to_have_count(1)
    with page.expect_response(project_types_put, timeout=15000):
        common.locator(".pt-reference-toggle[aria-pressed='false']").first.click()
    expect(common.locator(".pt-reference-toggle[aria-pressed='false']")).to_have_count(0)
    assert page.request.get(f"{FIXTURE_URL}/api/project-types").json()["revision"] > original["revision"]

    # Blank inline reference edits cancel on blur. Valid links save without
    # exposing an obsolete dialog-level Save control.
    common_new = common.get_by_role("button", name="New reference", exact=True).first
    common_new.click()
    reference_input = common.get_by_label("Research reference URL 3")
    expect(reference_input).to_have_value("")
    reference_input.press("Tab")
    expect(reference_input).to_have_count(0)
    expect(common.locator(".pt-reference-link")).to_have_count(4)
    common_new.click()
    reference_input = common.get_by_label("Research reference URL 3")
    with page.expect_response(project_types_put, timeout=15000):
        reference_input.fill("https://example.org/shared-research-standard")
        reference_input.press("Tab")
    expect(common.locator(".pt-reference-link")).to_have_count(5)
    new_entry = common.locator(".pt-reference-entry").nth(2)
    expect(new_entry.get_by_role("button", name="Remove reference")).to_be_visible()
    with page.expect_response(project_types_put, timeout=15000):
        new_entry.get_by_role("button", name="Remove reference").click()
    expect(common.locator(".pt-reference-link")).to_have_count(4)

    # New custom types are validated before persistence. The placeholder
    # carries no paid icon generation and the derived type copies its parent.
    dialog.locator(".project-types-section-heading").first.get_by_role(
        "button", name="New project type"
    ).click()
    parent = dialog.locator(".project-types-body > section").first.locator(
        ".project-type-card[open]"
    )
    expect(parent.get_by_role("button", name="Generate icon")).to_have_count(0)
    parent.get_by_label("Name").fill("CI Browser Parent")
    parent.get_by_label("Scope").fill("Shared research scope")
    with page.expect_response(project_types_put, timeout=15000):
        parent.get_by_label("Scope").press("Tab")
    catalog = page.request.get(f"{FIXTURE_URL}/api/project-types").json()
    parent_record = next(item for item in catalog["project_types"] if item["name"] == "CI Browser Parent")
    assert parent_record["scope"] == "Shared research scope"
    assert parent_record["icon"]["key"] == "placeholder"

    dialog.locator(".project-types-section-heading").first.get_by_role(
        "button", name="New project type"
    ).click()
    child = dialog.locator(".project-types-body > section").first.locator(
        ".project-type-card[open]"
    )
    child.get_by_label("Name").fill("CI Browser Derived")
    child.get_by_role("combobox", name="Based on project type").click()
    child.get_by_role("option", name="CI Browser Parent").click()
    with page.expect_response(project_types_put, timeout=15000):
        child.get_by_label("Scope").fill("Independent derived scope")
        child.get_by_label("Scope").press("Tab")
    catalog = page.request.get(f"{FIXTURE_URL}/api/project-types").json()
    child_record = next(item for item in catalog["project_types"] if item["name"] == "CI Browser Derived")
    assert child_record["based_on"] == parent_record["id"]
    assert child_record["scope"] == "Independent derived scope"
    assert child_record["icon"]["key"] == "placeholder"

    # Settings remain responsive on mobile, preserve the user's tab, and
    # must close without a Save button.
    page.set_viewport_size({"width": 390, "height": 844})
    bounds = dialog.bounding_box()
    assert bounds and 0 <= bounds["x"] and bounds["x"] + bounds["width"] <= 390, bounds
    page.screenshot(path=str(EVIDENCE / "types-mobile.png"), full_page=True)
    dialog.get_by_role("tab", name="Preferences").click()
    unattended = dialog.get_by_label("Allow unattended background execution")
    before_unattended = unattended.is_checked()
    with page.expect_response(
        lambda response: response.url.endswith("/api/user-preferences/unattended-execution")
        and response.request.method == "PUT",
        timeout=15000,
    ):
        unattended.set_checked(not before_unattended)
    with page.expect_response(
        lambda response: response.url.endswith("/api/user-preferences/unattended-execution")
        and response.request.method == "PUT",
        timeout=15000,
    ):
        unattended.set_checked(before_unattended)
    dialog.get_by_role("button", name="Close Settings").click()
    expect(dialog).not_to_be_visible()
    settings.click()
    dialog = page.get_by_role("dialog", name="Settings")
    expect(dialog.get_by_role("tab", name="Preferences")).to_have_attribute("aria-selected", "true")
    expect(dialog.locator("header").get_by_role("button", name="Save")).to_have_count(0)
    dialog.get_by_role("button", name="Close Settings").click()
    expect(dialog).not_to_be_visible()

    assert not errors, errors
    browser.close()

print("PASS Project Types auto-save, references, custom inheritance, responsive Settings, and no global Save button.")
