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

    # A new project inherits personal Model/Thinking, not its own editable pair.
    page.get_by_role("button", name="New project", exact=True).click()
    new_dialog = page.get_by_role("dialog", name="New Project")
    expect(new_dialog).to_be_visible()
    assert new_dialog.get_by_role("combobox", name="Model", exact=True).count() == 0
    assert new_dialog.locator(".settings-model-row").count() == 0
    new_dialog.get_by_role("button", name="Cancel project settings").click()
    expect(new_dialog).not_to_be_visible()

    # User Settings is the authoritative second tab for both header pills.
    page.get_by_role("button", name="Settings", exact=True).click()
    user_dialog = page.get_by_role("dialog", name="User Settings")
    tabs = user_dialog.get_by_role("tab")
    assert tabs.nth(1).inner_text() == "Model/Thinking"
    tabs.nth(1).click()
    model_choice = user_dialog.get_by_role("combobox", name="Model", exact=True)
    thinking_choice = user_dialog.get_by_role("combobox", name="Thinking", exact=True)
    expect(model_choice).to_be_visible()
    expect(thinking_choice).to_be_visible()
    model_choice.click()
    model_options = page.get_by_role("listbox", name="Model", exact=True)
    expect(model_options.get_by_role("option").filter(has_text="GPT-6-Luna · $")).to_be_visible()
    expect(model_options.get_by_role("option").filter(has_text="GPT-6.1-Sol · $$")).to_be_visible()
    expect(model_options.get_by_role("option").filter(has_text="GPT-6-Astra · $$$")).to_be_visible()
    page.keyboard.press("Escape")
    thinking_choice.click()
    expect(page.get_by_role("listbox", name="Thinking")).to_be_visible()
    page.keyboard.press("Escape")
    user_dialog.get_by_role("button", name="Close Settings").click()
    expect(user_dialog).not_to_be_visible()

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
    dialog = page.get_by_role("dialog", name="User Settings")
    expect(dialog).to_be_visible()
    expect(dialog.locator("header").get_by_role("button", name="Save")).to_have_count(0)
    expect(dialog.get_by_role("heading", name="User Settings", exact=True)).to_be_visible()
    for tab in ("Limits", "Preferences", "Research Ethos", "Project Types"):
        dialog.get_by_role("tab", name=tab, exact=True).click()
        expect(dialog).to_be_visible()
    common = dialog.locator(".pt-common-references")
    expect(common.locator(".pt-reference-link")).to_have_count(4)
    expect(common.locator(".pt-reference-toggle[aria-pressed='true']")).to_have_count(4)
    original = page.request.get(f"{FIXTURE_URL}/api/project-types").json()
    assert original["revision"]

    def project_types_put(response):
        return response.url.endswith("/api/project-types") and response.request.method == "PUT"

    # Toggle a curated reference, verify automatic persistence, then restore.
    with page.expect_response(project_types_put, timeout=15000):
        common.locator(".pt-reference-toggle[aria-pressed='true']").first.click()
    expect(common.locator(".pt-reference-toggle[aria-pressed='false']")).to_have_count(1)
    with page.expect_response(project_types_put, timeout=15000):
        common.locator(".pt-reference-toggle[aria-pressed='false']").first.click()
    expect(common.locator(".pt-reference-toggle[aria-pressed='false']")).to_have_count(0)
    assert (
        page.request.get(f"{FIXTURE_URL}/api/project-types").json()["revision"]
        != original["revision"]
    )

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
    parent_record = next(
        item for item in catalog["project_types"] if item["name"] == "CI Browser Parent"
    )
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
    child_record = next(
        item for item in catalog["project_types"] if item["name"] == "CI Browser Derived"
    )
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
        lambda response: (
            response.url.endswith("/api/user-preferences/unattended-execution")
            and response.request.method == "PUT"
        ),
        timeout=15000,
    ):
        unattended.set_checked(not before_unattended)
    with page.expect_response(
        lambda response: (
            response.url.endswith("/api/user-preferences/unattended-execution")
            and response.request.method == "PUT"
        ),
        timeout=15000,
    ):
        unattended.set_checked(before_unattended)
    dialog.get_by_role("button", name="Close Settings").click()
    expect(dialog).not_to_be_visible()
    settings.click()
    dialog = page.get_by_role("dialog", name="User Settings")
    expect(dialog.get_by_role("tab", name="Preferences")).to_have_attribute("aria-selected", "true")
    expect(dialog.locator("header").get_by_role("button", name="Save")).to_have_count(0)
    dialog.get_by_role("button", name="Close Settings").click()
    expect(dialog).not_to_be_visible()
    page.set_viewport_size({"width": 1440, "height": 1000})

    # Preserve deleted-type continuation and saved-paper recovery coverage.
    # The editor saves each valid custom type automatically before Close.
    types_button = settings
    parent_type = parent_record
    child_type = child_record

    types_button.click()
    dialog = page.get_by_role("dialog", name="User Settings")
    dialog.get_by_role("tab", name="Project Types").click()
    dialog.locator(".project-types-section-heading").first.get_by_role(
        "button", name="New project type"
    ).click()
    second_card = dialog.locator(".project-types-body > section").first.locator(
        ".project-type-card[open]"
    )
    second_card.get_by_label("Name").fill("CI Browser Second")
    with page.expect_response(project_types_put, timeout=15000):
        second_card.get_by_label("Scope").fill("Second saved scope")
        second_card.get_by_label("Scope").press("Tab")
    second_type = next(
        item
        for item in page.request.get(f"{FIXTURE_URL}/api/project-types").json()["project_types"]
        if item["name"] == "CI Browser Second"
    )
    dialog.get_by_role("button", name="Close Settings").click()

    affected = project(page, "Deleted custom parent", parent_type["id"])
    project(page, "Deleted second custom type", second_type["id"])
    types_button.click()
    dialog = page.get_by_role("dialog", name="User Settings")
    dialog.get_by_role("tab", name="Project Types").click()
    for type_name in ("CI Browser Parent", "CI Browser Second"):
        card = dialog.locator(f'.project-type-card:has(> summary strong:text-is("{type_name}"))')
        card.locator("summary").click()
        with page.expect_response(project_types_put, timeout=15000):
            card.get_by_role("button", name="Remove project type").click()
    confirmations = page.evaluate("window.__projectTypeConfirmations")
    assert any("CI Browser Parent" in text and "1 project" in text for text in confirmations)
    assert any("CI Browser Second" in text and "1 project" in text for text in confirmations)
    catalog_after_delete = page.request.get(f"{FIXTURE_URL}/api/project-types").json()[
        "project_types"
    ]
    assert all(
        item["id"] not in {parent_type["id"], second_type["id"]} for item in catalog_after_delete
    )
    derived = next(item for item in catalog_after_delete if item["id"] == child_type["id"])
    assert derived["based_on"] == parent_type["id"]
    assert derived["scope"] == "Independent derived scope"
    dialog.get_by_role("button", name="Close Settings").click()

    # This acceptance proves deleted-type recovery, not a long research run.
    # Bound the deterministic provider fixture to one Investigator/Skeptic pair
    # so slow CI runners cannot time out while executing unrelated turns.
    limits_url = f"{FIXTURE_URL}/api/projects/research-limits"
    current_limits = page.request.get(limits_url, params={"path": affected["path"]})
    assert current_limits.ok, current_limits.text()
    bounded_limits = {
        **current_limits.json(),
        "path": affected["path"],
        "scheduler_version": 2,
        "research_rounds": 1,
        "turns_per_round": 1,
        "model_calls": 2,
    }
    saved_limits = page.request.put(limits_url, data=bounded_limits)
    assert saved_limits.ok, saved_limits.text()

    open_project(page, affected["path"])
    expect(page.get_by_role("heading", name="Deleted custom parent")).to_be_visible()
    expect(page.get_by_text("PROJECT DESCRIPTION", exact=True)).to_be_visible()
    expect(page.get_by_text("Project type unavailable", exact=True).first).to_be_visible()
    expect(page.get_by_role("button", name="Export project")).to_be_visible()
    with page.expect_download() as download_info:
        page.get_by_role("button", name="Export project").click()
        page.get_by_role("dialog", name="Export Project").get_by_role(
            "button", name="Download", exact=True
        ).click()
    exported = json.loads(Path(download_info.value.path()).read_text())
    snapshot = exported["files"]["project.json"]["project_type_snapshot"]
    assert snapshot["id"] == parent_type["id"] and snapshot["scope"] == "Shared research scope"

    # The warning copy and native modal depend on snapshot completeness. No
    # project configuration or session request is made before an explicit choice.
    page.set_viewport_size({"width": 390, "height": 844})
    page.screenshot(path=str(EVIDENCE / "deleted-project-mobile.png"), full_page=True)
    starts_before = len(
        [
            (url, payload)
            for url, payload in api_requests
            if url.endswith("/research-sessions/start")
        ]
    )
    configs_before = len(
        [(url, payload) for url, payload in api_requests if "/proposals/config?" in url]
    )
    play = page.locator(".sessions-pane-heading").get_by_role(
        "button", name="New session", exact=True
    )
    play.click()
    warning = page.get_by_role("alertdialog", name="Project type unavailable")
    expect(warning).to_be_visible()
    expect(warning.get_by_role("button", name="Continue with saved settings")).to_be_visible()
    expect(warning.get_by_role("button", name="Choose a replacement")).to_be_visible()
    page.keyboard.press("Escape")
    expect(warning).not_to_be_visible()
    expect(play).to_be_focused()
    play.click()
    expect(warning).to_be_visible()
    assert (
        len(
            [
                (url, payload)
                for url, payload in api_requests
                if url.endswith("/research-sessions/start")
            ]
        )
        == starts_before
    )
    assert (
        len([(url, payload) for url, payload in api_requests if "/proposals/config?" in url])
        == configs_before
    )
    page.screenshot(path=str(EVIDENCE / "missing-type-start-warning.png"), full_page=True)

    warning.get_by_role("button", name="Continue with saved settings").click()
    expect(warning).not_to_be_visible()
    start_button = page.locator(".sessions-pane-heading").get_by_role(
        "button", name="Start Session 1"
    )
    expect(start_button).to_be_visible(timeout=15000)
    expect(start_button).to_be_visible()
    page.set_viewport_size({"width": 390, "height": 844})
    bounds = start_button.bounding_box()
    assert bounds and bounds["x"] >= 0 and bounds["x"] + bounds["width"] <= 390, bounds
    page.set_viewport_size({"width": 1440, "height": 1000})
    start_button.click()
    row = page.locator(".session-row").filter(has_text="Session 1")
    expect(row).to_be_visible(timeout=15000)
    expect(row.locator(".session-status")).to_have_text("ended", timeout=60000)
    start_payloads = [
        payload for url, payload in api_requests if url.endswith("/research-sessions/start")
    ]
    assert len(start_payloads) == starts_before + 1, start_payloads
    assert start_payloads[-1]["continue_using_saved_type_settings"] is True, start_payloads[-1]

    # A legacy default project is still importable/exportable, but the UI says
    # clearly that its incomplete snapshot requires an explicit replacement.
    legacy = project(page, "Legacy default project", "default")
    open_project(page, legacy["path"])
    expect(page.get_by_role("heading", name="Legacy default project")).to_be_visible()
    header = page.locator(".project-art-header")
    expect(header.get_by_role("button", name="About SIGMA")).to_have_text("About SIGMA")
    # New Paper offers two side-by-side underline actions (not an X), with
    # both controls vertically centered against the Paper heading.
    paper_header = page.locator(".papers-pane-heading")
    new_paper = paper_header.get_by_role("button", name="New paper")
    expect(new_paper).to_be_visible()
    new_paper.click()
    start_paper = paper_header.get_by_role("button", name="Start Paper", exact=False)
    cancel_paper = paper_header.get_by_role("button", name="Cancel", exact=True)
    expect(start_paper).to_be_visible()
    expect(cancel_paper).to_be_visible()
    assert paper_header.locator(".sigma-dialog-dismiss").count() == 0
    first_box = start_paper.bounding_box()
    second_box = cancel_paper.bounding_box()
    assert first_box and second_box
    assert abs(first_box["y"] - second_box["y"]) <= 2
    assert (
        abs(first_box["y"] + first_box["height"] / 2 - (second_box["y"] + second_box["height"] / 2))
        <= 2
    )
    for action in (start_paper, cancel_paper):
        assert (
            action.evaluate("(button) => getComputedStyle(button).textDecorationLine")
            == "underline"
        )
    cancel_paper.click()
    expect(new_paper).to_be_visible()

    # Include popup's dismiss X aligns to the actual outer popup corner,
    # not to the padded title row (which used to move it down and inward).
    page.get_by_role("button", name="Include in paper").click()
    paper_options = page.get_by_role("dialog", name="Include in paper")
    expect(paper_options).to_be_visible()
    paper_close = paper_options.get_by_role("button", name="Close paper inclusion options")
    popup_box = paper_options.bounding_box()
    close_box = paper_close.bounding_box()
    assert popup_box and close_box
    assert (
        abs((popup_box["x"] + popup_box["width"]) - (close_box["x"] + close_box["width"]) - 11) <= 2
    ), (popup_box, close_box)
    assert abs(close_box["y"] - popup_box["y"] - 9) <= 2, (popup_box, close_box)
    paper_close.click()
    expect(paper_options).to_have_count(0)
    # Regression: editing the Project description swaps the toolbar pencil for
    # Save / Cancel and keeps those actions mounted after React re-renders.
    project_edit = page.locator(".project-pane-actions").get_by_role(
        "button", name="Edit project fields"
    )
    expect(project_edit).to_be_visible()
    project_edit.click()
    toolbar = page.locator(".project-pane-actions")
    save_project_fields = toolbar.get_by_role("button", name="Save", exact=True)
    expect(save_project_fields).to_be_visible()
    expect(save_project_fields).to_be_disabled()
    expect(toolbar.get_by_role("button", name="Cancel", exact=True)).to_be_visible()
    expect(toolbar.get_by_role("button", name="Edit project fields")).to_have_count(0)
    expect(page.get_by_role("textbox", name="Project title")).to_be_visible()
    # All four fields participate in dirty state, including reverting an edit.
    outcomes = page.get_by_role("textbox", name="Desired Outcomes")
    original_outcomes = outcomes.input_value()
    outcomes.fill(original_outcomes + " Temporary test edit.")
    expect(save_project_fields).to_be_enabled()
    outcomes.fill(original_outcomes)
    expect(save_project_fields).to_be_disabled()
    page.wait_for_timeout(300)
    expect(save_project_fields).to_be_disabled()
    expect(toolbar.get_by_role("button", name="Cancel", exact=True)).to_be_visible()
    toolbar.get_by_role("button", name="Cancel", exact=True).click()
    expect(project_edit).to_be_visible()

    expect(page.get_by_role("button", name="Project settings")).to_be_visible()
    assert header.get_by_role("button", name="Project Types").count() == 0

    with page.expect_download() as legacy_download:
        page.get_by_role("button", name="Export project").click()
        page.get_by_role("dialog", name="Export Project").get_by_role(
            "button", name="Download", exact=True
        ).click()
    legacy_export = json.loads(Path(legacy_download.value.path()).read_text())
    assert legacy_export["files"]["project.json"]["investigation_type"] == "default"
    assert legacy_export["files"]["project.json"]["project_type_snapshot"] is None
    play = page.locator(".sessions-pane-heading").get_by_role(
        "button", name="New session", exact=True
    )
    play.click()
    unsafe_warning = page.get_by_role("alertdialog", name="Project type unavailable")
    expect(unsafe_warning).to_be_visible()
    expect(
        unsafe_warning.get_by_text("does not have a complete saved type snapshot")
    ).to_be_visible()
    expect(unsafe_warning.get_by_role("button", name="Continue with saved settings")).to_have_count(
        0
    )
    unsafe_warning.get_by_role("button", name="Choose a replacement").click()
    settings = page.get_by_role("dialog", name="Project Settings")
    expect(settings).to_be_visible()
    settings.locator("#project-mode").click()
    project_type_menu = settings.locator("#project-mode-options")
    expect(project_type_menu).to_be_visible()
    assert project_type_menu.evaluate('node => node.matches(":popover-open")')
    assert project_type_menu.evaluate("node => getComputedStyle(node).position") == "fixed"
    with page.expect_response(
        lambda response: (
            response.url.endswith("/api/projects/update") and response.request.method == "POST"
        ),
        timeout=15000,
    ):
        settings.get_by_role("option", name="Mathematics").click()
    settings.get_by_role("button", name="Close Project Settings").click()
    expect(settings).not_to_be_visible()
    replaced = page.request.get(
        f"{FIXTURE_URL}/api/projects/inspect?path={quote(legacy['path'], safe='')}"
    ).json()
    assert replaced["project"]["investigation_type"] == "mathematical"
    assert replaced["project"]["project_type_snapshot"]["id"] == "mathematical"

    # Saving a changed project field persists it and switches back to the pencil.
    project_edit = page.locator(".project-pane-actions").get_by_role(
        "button", name="Edit project fields"
    )
    project_edit.click()
    save_project_fields = page.locator(".project-pane-actions").get_by_role(
        "button", name="Save", exact=True
    )
    expect(save_project_fields).to_be_disabled()
    outcomes = page.get_by_role("textbox", name="Desired Outcomes")
    original_outcomes = outcomes.input_value()
    updated_outcomes = (original_outcomes + "\nBrowser save check.").strip()
    outcomes.fill(updated_outcomes)
    expect(save_project_fields).to_be_enabled()
    save_project_fields.click()
    expect(project_edit).to_be_visible()
    expect(
        page.locator(".project-pane-actions").get_by_role("button", name="Save", exact=True)
    ).to_have_count(0)
    assert (
        page.request.get(
            f"{FIXTURE_URL}/api/projects/inspect?path={quote(legacy['path'], safe='')}"
        ).json()["project"]["desired_outcomes"]
        == updated_outcomes
    )
    # The toolbar must really relinquish edit mode after Save, not merely
    # hide the fields during the update response. A second edit must work.
    expect(project_edit).to_be_enabled()
    project_edit.click()
    toolbar = page.locator(".project-pane-actions")
    expect(toolbar.get_by_role("button", name="Save", exact=True)).to_be_disabled()
    expect(page.get_by_role("textbox", name="Desired Outcomes")).to_have_value(updated_outcomes)
    toolbar.get_by_role("button", name="Cancel", exact=True).click()
    expect(project_edit).to_be_visible()

    # Project Settings contains only project type and difficulty.
    page.get_by_role("button", name="Project settings", exact=True).click()
    project_settings = page.get_by_role("dialog", name="Project Settings")
    # The modal is vertically centered. Wait for async collaboration/model
    # loading before measuring two independent rectangles.
    expect(project_settings.get_by_text("Loading shared settings…", exact=True)).not_to_be_visible()
    expect(project_settings.get_by_role("tab", name="Preferences")).to_have_count(0)
    expect(project_settings.get_by_label("Difficulty")).to_be_visible()
    # The close X uses the shared dialog header's upper-right inset,
    # not the former unusually deep 48px offset.
    close_button = project_settings.get_by_role("button", name="Close Project Settings")
    dialog_box = project_settings.bounding_box()
    close_box = close_button.bounding_box()
    assert dialog_box and close_box
    right_inset = dialog_box["x"] + dialog_box["width"] - (close_box["x"] + close_box["width"] / 2)
    top_inset = close_box["y"] + close_box["height"] / 2 - dialog_box["y"]
    assert 18 <= right_inset <= 35, (dialog_box, close_box)
    assert 18 <= top_inset <= 35, (dialog_box, close_box)
    assert close_box["x"] >= dialog_box["x"]
    assert close_box["x"] + close_box["width"] <= dialog_box["x"] + dialog_box["width"]
    close_button.click()

    # User-wide Settings automatically persists Outcome preferences and
    # Project Types reference switches, without a global Save control.
    page.goto(BASE_URL)
    page.get_by_role("button", name="Settings", exact=True).click()
    settings_dialog = page.get_by_role("dialog", name="User Settings")
    expect(settings_dialog.get_by_role("button", name="Save", exact=True)).to_have_count(0)
    settings_dialog.get_by_role("tab", name="Preferences").click()
    advanced = settings_dialog.get_by_role("checkbox", name="Show advanced Outcome details")
    original_advanced = advanced.is_checked()
    with page.expect_response(
        lambda response: (
            response.url.endswith("/api/user-preferences/research-settings")
            and response.request.method == "PUT"
        ),
        timeout=15000,
    ):
        advanced.set_checked(not original_advanced)
    settings_dialog.get_by_role("tab", name="Project Types").click()
    math = settings_dialog.locator(
        '.project-type-card:has(> summary strong:text-is("Mathematics"))'
    )
    math.locator("summary").click()
    with page.expect_response(project_types_put, timeout=15000):
        math.get_by_role("button", name="Disable research reference", exact=False).first.click()
    settings_dialog.get_by_role("button", name="Close Settings").click()
    expect(settings_dialog).not_to_be_visible()
    saved_preferences = page.request.get(f"{FIXTURE_URL}/api/project-types").json()
    assert "mathematical" in saved_preferences["reference_preferences"]

    page.get_by_role("button", name="Settings", exact=True).click()
    restored = page.get_by_role("dialog", name="User Settings")
    restored.get_by_role("tab", name="Preferences").click()
    assert (
        restored.get_by_role("checkbox", name="Show advanced Outcome details").is_checked()
        != original_advanced
    )
    with page.expect_response(
        lambda response: (
            response.url.endswith("/api/user-preferences/research-settings")
            and response.request.method == "PUT"
        ),
        timeout=15000,
    ):
        restored.get_by_role("checkbox", name="Show advanced Outcome details").set_checked(
            original_advanced
        )
    restored.get_by_role("button", name="Close Settings").click()

    # Long project titles must align every wrapped line after the independent
    # discipline icon track, not restart subsequent lines beneath that icon.
    long_name = (
        "Why Do Xenopus Tadpoles Temporarily Lose Tail Regeneration? "
        "A Long-Running Investigation of Stage-Dependent Recovery v1 (continued)"
    )
    long_project = project(page, long_name, "mathematical")
    open_project(page, long_project["path"])
    title_row = page.locator(".project-header-title-row")
    title = title_row.locator(".project-header-title")
    expect(title).to_have_text(long_name)
    geometry = title_row.evaluate(
        """row => {
          const title = row.querySelector('.project-header-title');
          const range = document.createRange();
          range.selectNodeContents(title);
          const lines = [...range.getClientRects()].filter(rect => rect.width > 25)
            .map(rect => ({x: rect.x, y: rect.y}));
          const icon = row.querySelector('.research-type-icon').getBoundingClientRect();
          return {lines, iconRight: icon.right};
        }"""
    )
    assert len(geometry["lines"]) >= 2, geometry
    assert all(abs(line["x"] - geometry["lines"][0]["x"]) < 3 for line in geometry["lines"]), (
        geometry
    )
    assert geometry["lines"][0]["x"] > geometry["iconRight"], geometry

    # The same hanging indent applies to the live title button. In particular,
    # the pulsing dot must be vertically centered on the last wrapped line.
    recent_output_at = datetime.now(UTC).isoformat()
    page.route(
        "**/api/projects/papers/progress?*",
        lambda route: route.fulfill(
            json={
                "progress": {
                    "status": "active",
                    "stage": "sections",
                    "current": 1,
                    "total": 3,
                    "started_at": "2026-11-05T01:00:00+00:00",
                    "elapsed_seconds": 90,
                    "last_progress_at": recent_output_at,
                }
            }
        ),
    )
    page.reload()
    active_title = page.locator(".project-header-title-action")
    expect(active_title).to_be_visible(timeout=10000)
    active_geometry = active_title.evaluate(
        """node => {
          const text = node.querySelector('.project-header-title-text');
          const range = document.createRange();
          range.selectNodeContents(text.firstChild);
          const lines = [...range.getClientRects()].filter(rect => rect.width > 25)
            .map(rect => ({x:rect.x, midY:rect.y + rect.height / 2}));
          const dot = text.querySelector('.research-running-indicator').getBoundingClientRect();
          return {lines, dotMidY: dot.y + dot.height / 2};
        }"""
    )
    assert len(active_geometry["lines"]) >= 2, active_geometry
    assert all(
        abs(line["x"] - active_geometry["lines"][0]["x"]) < 3 for line in active_geometry["lines"]
    ), active_geometry
    assert abs(active_geometry["lines"][-1]["midY"] - active_geometry["dotMidY"]) < 6

    # Paper steps display real completed/total sections and do not duplicate
    # the heartbeat in the Paper N heading. The mocked active project remains
    # provider-free; refreshing tests durable progress exactly as a reconnect.
    step = page.locator(".paper-stage-list [data-paper-step='Write sections']")
    expect(step.locator("strong")).to_have_text("Writing sections (1/3)", timeout=10000)
    expect(step.locator(".paper-activity-line")).to_contain_text("Writing in progress ·")
    expect(page.locator(".paper-draft-card .paper-draft-pulse")).to_have_count(0)
    page.unroute("**/api/projects/papers/progress?*")
    stale_output_at = (datetime.now(UTC) - timedelta(minutes=6)).isoformat()
    page.route(
        "**/api/projects/papers/progress?*",
        lambda route: route.fulfill(
            json={
                "progress": {
                    "status": "active",
                    "stage": "sections",
                    "current": 2,
                    "total": 3,
                    "sections_total": 3,
                    "started_at": "2026-11-05T01:00:00+00:00",
                    "elapsed_seconds": 91,
                    "last_progress_at": stale_output_at,
                }
            }
        ),
    )
    page.reload()
    step = page.locator(".paper-stage-list [data-paper-step='Write sections']")
    expect(step.locator("strong")).to_have_text("Writing sections (2/3)", timeout=10000)
    expect(step.locator(".paper-activity-line")).to_contain_text("No recent writing activity for")
    page.unroute("**/api/projects/papers/progress?*")
    page.route(
        "**/api/projects/papers/progress?*",
        lambda route: route.fulfill(
            json={
                "progress": {
                    "status": "active",
                    "stage": "validation",
                    "current": None,
                    "total": None,
                    "sections_total": 3,
                    "started_at": "2026-11-05T01:00:00+00:00",
                    "elapsed_seconds": 92,
                }
            }
        ),
    )
    page.reload()
    step = page.locator(".paper-stage-list [data-paper-step='Write sections']")
    expect(step.locator("strong")).to_have_text("Wrote sections (3)", timeout=10000)
    expect(step.locator(".paper-activity-line")).to_have_count(0)

    # The Papers list has individual session-style cards, not one shared
    # border with internal separators. The grid gap applies equally to all
    # drafts and saved versions.
    cards_style = page.locator(".papers-pane .saved-paper-library").evaluate(
        """library => {
          const card = library.querySelector(':scope > .saved-paper-card');
          const outer = getComputedStyle(library);
          const inner = getComputedStyle(card);
          return {
            display: outer.display,
            gap: Number.parseFloat(outer.rowGap),
            outerBorder: outer.borderTopWidth,
            cardBorder: inner.borderTopWidth,
            cardRadius: Number.parseFloat(inner.borderTopLeftRadius),
            cardBackground: inner.backgroundColor
          };
        }"""
    )
    assert cards_style["display"] == "grid", cards_style
    assert cards_style["gap"] >= 8, cards_style
    assert cards_style["outerBorder"] == "0px", cards_style
    assert cards_style["cardBorder"] == "1px", cards_style
    assert cards_style["cardRadius"] >= 5, cards_style
    assert cards_style["cardBackground"] != "rgba(0, 0, 0, 0)", cards_style

    # Stop -> Play: a compatible checkpoint must offer BOTH Resume and
    # provider-free Start over. No tooltip should claim a generation conflict
    # while Play is enabled. All paper endpoints below are local fixtures.
    paper_fixture = {
        "checkpoint": True,
        "stopped": True,
        "reset_ready": False,
        "resume": True,
        "pdf": True,
        "scored": False,
    }
    saved_paper = {
        "paper_id": "fixture-paper-1",
        "paper_version": 1,
        "download_basename": "fixture-paper",
        "title": "Saved fixture paper",
        "created_at": "2026-11-05T01:00:00+00:00",
        "snapshot_sha256": "a" * 64,
        "validation_warnings": [],
        "pdf_available": True,
        "generation": {
            "mode": "api_key",
            "model": "fixture-model",
            "reasoning_effort": "high",
            "call_limit": 1,
            "publication_status": "proofreading_complete",
        },
    }
    page.route(
        "**/api/projects/proposals/config?*",
        lambda route: route.fulfill(
            json={
                "available": True,
                "binding": "fixture:account",
                "mode": "api_key",
                "model": "fixture-model",
                "reasoning_effort": "high",
            }
        ),
    )
    page.route(
        "**/api/projects/papers/preflight?*",
        lambda route: route.fulfill(
            json={
                "checkpoint_exists": paper_fixture["checkpoint"],
                "checkpoint_can_restart": paper_fixture["checkpoint"],
                "restart_ready": paper_fixture["reset_ready"],
                "resume_available": paper_fixture["checkpoint"] and paper_fixture["resume"],
                "incomplete_one_shot": paper_fixture["checkpoint"] and not paper_fixture["resume"],
                "snapshot_sha256": "a" * 64,
                "outline_complete": False,
                "draft_recovery_available": False,
                "completed_sections": 0,
            }
        ),
    )
    page.unroute("**/api/projects/papers/progress?*")

    def stopped_progress(route):
        route.fulfill(
            json={
                "progress": (
                    {
                        "status": "cancelled",
                        "stage": "sections",
                        "current": 1,
                        "total": 3,
                        "started_at": "2026-11-05T01:00:00+00:00",
                        "elapsed_seconds": 93,
                    }
                    if paper_fixture["stopped"]
                    else None
                )
            }
        )

    page.route("**/api/projects/papers/progress?*", stopped_progress)

    def paper_list(route):
        paper = {**saved_paper, "pdf_available": paper_fixture["pdf"]}
        if paper_fixture["scored"]:
            paper["score"] = {
                "total": 82,
                "rubric_id": "fixture",
                "rubric_version": 3,
                "pdf_sha256": "c" * 64,
                "provisional": True,
            }
        route.fulfill(json={"papers": [paper], "paper_count": 1})

    page.route("**/api/projects/papers?*", paper_list)
    page.route(
        "**/api/projects/papers/fixture-paper-1?*",
        lambda route: route.fulfill(
            json={
                **saved_paper,
                "pdf_sha256": "c" * 64,
                "draft": {
                    "title": "Saved fixture paper",
                    "abstract": "Test document",
                    "abstract_claim_ids": [],
                    "problem_framing": [],
                    "problem_framing_claim_ids": [],
                    "methods": [],
                    "methods_claim_ids": [],
                    "claims": [],
                    "sections": [],
                    "limitations": [],
                    "open_obligations": [],
                    "conclusions": [],
                    "conclusion_claim_ids": [],
                },
                "snapshot": {"sources": []},
            }
        ),
    )
    page.reload()
    play = page.get_by_role("button", name="Resume Paper 2")
    expect(play).to_be_enabled(timeout=10000)
    assert play.locator("xpath=..").get_attribute("data-tooltip") == "Resume paper generation"
    restart = page.get_by_role("button", name="Start over on paper generation")
    expect(restart).to_be_enabled()

    # Saved-paper score actions follow the metadata rather than floating
    # right, and do not inherit the busy/generation disable state.
    meta = page.locator('[data-paper-id="fixture-paper-1"] .saved-paper-meta')
    score = meta.get_by_role("button", name="Score", exact=True)
    expect(score).to_be_enabled()
    score_position = meta.evaluate(
        """node => {
          const text = node.querySelector('p').getBoundingClientRect();
          const button = node.querySelector('button').getBoundingClientRect();
          return {gap: button.left - text.right, baseline: Math.abs(
            button.bottom - text.bottom)};
        }"""
    )
    assert 0 <= score_position["gap"] <= 30, score_position
    assert score_position["baseline"] < 12, score_position

    # Verify a real Play dispatch (locally intercepted, never sent to AI).
    dispatched: list[str] = []

    def simulate_generation(route):
        dispatched.append(route.request.method)
        route.fulfill(status=409, json={"error": "Fixture paper dispatch intercepted"})

    page.route("**/api/projects/papers", simulate_generation)
    play.click()
    expect(page.get_by_role("button", name="Resume Paper 2")).to_be_enabled(timeout=10000)
    assert dispatched == ["POST"], dispatched
    assert play.locator("xpath=..").get_attribute("data-tooltip") == "Resume paper generation"

    # Start over clears a resumable checkpoint without playing automatically.
    reset_calls: list[str] = []

    def simulate_restart(route):
        reset_calls.append(route.request.method)
        payload = route.request.post_data_json
        assert payload["long_form"] is False, payload
        paper_fixture["checkpoint"] = False
        paper_fixture["stopped"] = False
        paper_fixture["reset_ready"] = True
        route.fulfill(json={"snapshot_sha256": "a" * 64})

    page.route("**/api/projects/papers/restart", simulate_restart)
    restart.click()
    confirm_restart = page.get_by_role("group", name="Confirm start over on paper generation")
    expect(confirm_restart).to_be_visible()
    assert reset_calls == [], reset_calls
    confirm_restart.get_by_role("button", name="Cancel").click()
    expect(confirm_restart).to_have_count(0)
    assert reset_calls == [], reset_calls
    restart.click()
    page.keyboard.press("Escape")
    expect(confirm_restart).to_have_count(0)
    assert reset_calls == [], reset_calls
    restart.click()
    expect(confirm_restart).to_be_visible()
    page.locator("#paper-draft-content").click(position={"x": 5, "y": 5})
    expect(confirm_restart).to_have_count(0)
    assert reset_calls == [], reset_calls
    restart.click()
    confirm_restart.get_by_role("button", name="Confirm").click()
    expect(page.get_by_role("button", name="Generate Paper 2")).to_be_enabled(timeout=10000)
    assert reset_calls == ["POST"], reset_calls
    assert dispatched == ["POST"], dispatched
    expect(page.get_by_role("button", name="Start over on paper generation")).to_have_count(0)
    # A real reload must not resurrect Start over from the reset receipt.
    page.reload()
    expect(page.get_by_role("button", name="Generate Paper 2")).to_be_enabled(timeout=10000)
    expect(page.get_by_role("button", name="Start over on paper generation")).to_have_count(0)
    # Play and subsequent Stop can create new discardable work.
    page.get_by_role("button", name="Generate Paper 2").click()
    # The frontend refreshes preflight before dispatch; wait for the
    # intercepted request rather than racing React's async handler.
    for _ in range(50):
        if len(dispatched) == 2:
            break
        page.wait_for_timeout(100)
    assert dispatched == ["POST", "POST"], dispatched
    expect(page.get_by_role("button", name="Generate Paper 2")).to_be_enabled(timeout=10000)
    paper_fixture["reset_ready"] = False
    paper_fixture["checkpoint"] = True
    paper_fixture["stopped"] = True
    page.reload()
    expect(page.get_by_role("button", name="Start over on paper generation")).to_be_enabled(
        timeout=10000
    )
    paper_fixture["checkpoint"] = False

    # Queue cancellation may leave only a stopped receipt (no saved checkpoint).
    # Start over must still clear it without sending another provider request.
    paper_fixture["stopped"] = True
    page.reload()
    start_over = page.get_by_role("button", name="Start over on paper generation")
    expect(start_over).to_be_enabled(timeout=10000)
    discard_calls: list[str] = []

    def simulate_discard(route):
        discard_calls.append(route.request.method)
        paper_fixture["stopped"] = False
        route.fulfill(json={"discarded": True})

    page.route("**/api/projects/papers/discard", simulate_discard)
    start_over.click()
    queued_confirm = page.get_by_role("group", name="Confirm start over on paper generation")
    expect(queued_confirm).to_be_visible()
    assert discard_calls == [], discard_calls
    queued_confirm.get_by_role("button", name="Confirm").click()
    expect(page.get_by_role("button", name="Generate Paper 2")).to_be_enabled(timeout=10000)
    assert discard_calls == ["POST"], discard_calls
    assert dispatched == ["POST", "POST"], dispatched

    # A stopped paid one-shot call with no saved draft cannot resume. Play
    # remains enabled but requires confirmation before restarting and making
    # another potentially billable provider request. Start over is unchanged.
    paper_fixture["checkpoint"] = True
    paper_fixture["resume"] = False
    paper_fixture["stopped"] = True
    paper_fixture["reset_ready"] = False
    page.reload()
    fresh_play = page.get_by_role("button", name="Generate Paper 2")
    expect(fresh_play).to_be_enabled(timeout=10000)
    expect(page.get_by_role("button", name="Start over on paper generation")).to_be_enabled()
    assert "confirmation required" in fresh_play.locator("xpath=..").get_attribute("data-tooltip")
    fresh_play.click()
    play_confirm = page.get_by_role("group", name="Confirm new paper generation attempt")
    expect(play_confirm).to_be_visible()
    assert reset_calls == ["POST"], reset_calls
    assert dispatched == ["POST", "POST"], dispatched
    play_confirm.get_by_role("button", name="Cancel").click()
    expect(play_confirm).to_have_count(0)
    fresh_play.click()
    page.keyboard.press("Escape")
    expect(play_confirm).to_have_count(0)
    assert reset_calls == ["POST"], reset_calls
    # Switching to Start over dismisses Play's popup without changing the
    # original Start over confirmation or causing provider requests.
    fresh_play.click()
    expect(play_confirm).to_be_visible()
    page.get_by_role("button", name="Start over on paper generation").click()
    expect(play_confirm).to_have_count(0)
    original_confirm = page.get_by_role("group", name="Confirm start over on paper generation")
    expect(original_confirm).to_be_visible()
    original_confirm.get_by_role("button", name="Cancel").click()
    assert reset_calls == ["POST"], reset_calls
    fresh_play.click()
    actions = play_confirm.locator(".session-remove-confirm-actions button")
    assert actions.count() == 2
    first_box, second_box = actions.nth(0).bounding_box(), actions.nth(1).bounding_box()
    assert first_box and second_box and abs(first_box["y"] - second_box["y"]) < 3
    assert (
        actions.nth(0).evaluate("(button) => getComputedStyle(button).textDecorationLine")
        == "underline"
    )
    assert (
        actions.nth(1).evaluate("(button) => getComputedStyle(button).textDecorationLine")
        == "underline"
    )
    play_confirm.get_by_role("button", name="Confirm", exact=True).click()
    for _ in range(80):
        if len(dispatched) == 3:
            break
        page.wait_for_timeout(100)
    assert reset_calls == ["POST", "POST"], reset_calls
    assert dispatched == ["POST", "POST", "POST"], dispatched
    expect(page.get_by_role("button", name="Generate Paper 2")).to_be_enabled(timeout=10000)
    expect(page.get_by_role("button", name="Start over on paper generation")).to_have_count(0)

    # Score stays clickable even when the PDF is unavailable; the user gets
    # an actionable explanation instead of an inert control.
    paper_fixture["pdf"] = False
    page.reload()
    score = page.locator('[data-paper-id="fixture-paper-1"] .saved-paper-meta').get_by_role(
        "button", name="Score", exact=True
    )
    expect(score).to_be_enabled()
    score.click()
    expect(
        page.locator(".papers-pane")
        .get_by_role("alert")
        .filter(has_text="A saved PDF is required before this paper can be scored.")
    ).to_be_visible()

    paper_fixture["pdf"] = True
    paper_fixture["scored"] = True
    page.reload()
    scored = page.locator('[data-paper-id="fixture-paper-1"] .saved-paper-meta')
    expect(scored.get_by_role("button", name="See score")).to_be_enabled()
    paper_row = page.locator('[data-paper-id="fixture-paper-1"]')
    star_box = paper_row.locator(".paper-title-star").bounding_box()
    paper_title_box = paper_row.locator(".saved-paper-second-line").bounding_box()
    assert star_box and paper_title_box
    assert abs(star_box["x"] - paper_title_box["x"]) <= 2, (star_box, paper_title_box)
    scored_position = scored.evaluate(
        """node => node.querySelector('button').getBoundingClientRect().left -
          node.querySelector('p').getBoundingClientRect().right"""
    )
    assert 0 <= scored_position <= 30, scored_position

    assert not errors, errors
    browser.close()

print(
    "PASS Project Types autosave, references, deleted-type recovery, papers, "
    "responsive Settings, and no global Save button."
)
