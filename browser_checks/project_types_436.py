"""Real Chrome acceptance for transactional project types and deleted-type recovery."""

import json
import os
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
    page.goto(BASE_URL)
    page.evaluate(
        "window.__projectTypeConfirmations = []; window.confirm = message => { window.__projectTypeConfirmations.push(String(message)); return true; }"
    )

    # The native Project Types dialog traps keyboard focus, closes on Escape,
    # restores focus, and keeps the Literature/open-book catalog read-only.
    types_button = page.get_by_role("button", name="Project Types", exact=True)
    types_button.click()
    dialog = page.get_by_role("dialog", name="Project Types")
    expect(dialog).to_be_visible()
    expect(dialog.locator("header").get_by_role("button", name="Save")).to_be_disabled()
    expect(dialog.get_by_role("checkbox", name="Show built-in project types")).to_have_count(0)
    expect(dialog.get_by_text("(cannot be modified)", exact=True)).to_be_visible()
    page.set_viewport_size({"width": 1440, "height": 1000})
    expect(dialog.get_by_text("Literature", exact=True).first).to_be_visible()
    assert dialog.get_by_text("Other", exact=True).count() == 0
    literature = dialog.locator('.project-type-card:has(> summary strong:text-is("Literature"))')
    literature.locator("summary").click()
    expect(literature).to_have_attribute("open", "")
    literature.locator("summary").click()
    expect(literature).not_to_have_attribute("open", "")
    literature.locator("summary").click()
    expect(literature).to_have_attribute("open", "")
    expect(literature.locator(".project-type-card-icon svg")).to_be_visible()
    # Empty reference sections disappear on read-only built-ins.
    expect(literature.get_by_text("Research standards references")).to_have_count(0)
    expect(literature.get_by_text("Publication standards references")).to_have_count(0)
    expect(literature.get_by_text("http://temp.com/style.html")).to_have_count(0)
    expect(literature.get_by_role("columnheader", name="URL")).to_have_count(0)
    builtin_names = (
        dialog.locator(".project-types-body > section")
        .nth(1)
        .locator(".project-type-card > summary strong")
        .all_text_contents()
    )
    assert builtin_names == sorted(builtin_names, key=str.casefold)
    page.screenshot(path=str(EVIDENCE / "types-desktop.png"), full_page=True)
    page.set_viewport_size({"width": 390, "height": 844})
    mobile_box = dialog.bounding_box()
    assert mobile_box and mobile_box["x"] >= 0 and mobile_box["x"] + mobile_box["width"] <= 390, (
        mobile_box
    )
    page.screenshot(path=str(EVIDENCE / "types-mobile.png"), full_page=True)
    page.keyboard.press("Escape")
    expect(dialog).not_to_be_visible()
    expect(types_button).to_be_focused()
    page.set_viewport_size({"width": 1440, "height": 1000})
    types_button.click()
    dialog = page.get_by_role("dialog", name="Project Types")
    add_button = dialog.locator(".project-types-section-heading").first.get_by_role("button", name="New")
    expect(add_button).to_be_enabled()
    add_button.focus()
    page.keyboard.press("Tab")
    assert dialog.evaluate("dialog => dialog.contains(document.activeElement)")
    page.keyboard.press("Shift+Tab")
    expect(add_button).to_be_focused()
    page.keyboard.press("Escape")
    expect(dialog).not_to_be_visible()
    expect(types_button).to_be_focused()

    # Create two custom types in one Save. The child uses an unsaved parent as
    # a one-time copy; the placeholder is free and replaceable with a catalog icon.
    types_button.click()
    dialog = page.get_by_role("dialog", name="Project Types")
    dialog.locator(".project-types-section-heading").first.get_by_role("button", name="New").click()
    parent = dialog.locator(".project-types-body > section").first.locator(".project-type-card[open]")
    save = dialog.locator("header").get_by_role("button", name="Save", exact=True)
    expect(parent.get_by_role("button", name="Remove project type")).to_have_count(0)
    expect(dialog.locator(".project-types-section-heading").first.get_by_role("button", name="Save")).to_have_count(0)
    expect(save).to_be_disabled()
    parent.get_by_label("Name").fill("Browser Parent")
    expect(save).to_be_disabled()  # New type still needs a scope.
    parent.get_by_label("Scope").fill("Original copied research scope")
    expect(save).to_be_enabled()  # The only Save is the header action.
    # A built-in or custom name collision must block saving without rewriting it.
    parent.get_by_label("Name").fill("  physics  ")
    expect(parent.get_by_text("Duplicate project type name")).to_be_visible()
    expect(dialog.locator("header").get_by_role("button", name="Save")).to_be_disabled()
    parent.get_by_label("Name").fill("Browser Parent")
    expect(parent.get_by_text("Duplicate project type name")).to_have_count(0)
    expect(parent.locator(".project-type-card-icon svg")).to_be_visible()
    # The new type shows its icon in the header immediately, without an icon
    # editor or any image-generation controls / provider calls.
    expect(parent.locator(".project-type-card-icon svg")).to_be_visible()
    expect(parent.locator(".project-type-icon-edit")).to_have_count(0)
    expect(parent.get_by_role("button", name="Generate icon")).to_have_count(0)
    expect(parent.get_by_role("button", name="Remove project type")).to_have_count(0)
    expect(parent.get_by_role("columnheader", name="URL")).to_have_count(0)
    expect(parent.get_by_text("http://temp.com/style.html")).to_have_count(0)
    parent.get_by_role("button", name="New", exact=True).first.click()
    # The next New remains unavailable until the just-created row contains a URL.
    expect(parent.get_by_role("button", name="New", exact=True).first).to_be_disabled()
    url_input = parent.get_by_label("Research reference URL 1")
    url_input.fill("https://example.org/research-standard")
    expect(url_input).to_have_value("https://example.org/research-standard")
    expect(parent.get_by_role("button", name="New", exact=True).first).to_be_enabled()
    assert url_input.evaluate("element => document.activeElement === element"), (
        "URL input remounted during typing"
    )
    parent.get_by_role("button", name="New", exact=True).first.click()
    parent.get_by_label("Research reference URL 2").fill(
        "HTTPS://EXAMPLE.ORG:443/research-standard"
    )
    parent.get_by_role("button", name="New", exact=True).first.click()
    expect(parent.get_by_label("Research reference URL 3")).to_have_value("")
    expect(save).to_be_enabled()
    reference_layout = parent.locator(".pt-reference-entry").first.evaluate(
        """row => {
          const input = row.querySelector('input').getBoundingClientRect();
          const remove = row.querySelector('button').getBoundingClientRect();
          return {gap: remove.left - input.right, sameLine: Math.abs(remove.top - input.top) < 16};
        }"""
    )
    assert 0 <= reference_layout["gap"] <= 20 and reference_layout["sameLine"], reference_layout
    # A new draft uses local Cancel, not Remove or a second Save.
    expect(dialog.locator(".project-types-section-heading").first.get_by_role("button", name="Cancel")).to_be_visible()
    save.click()
    expect(dialog).not_to_be_visible()

    types_button.click()
    dialog = page.get_by_role("dialog", name="Project Types")
    dialog.locator(".project-types-section-heading").first.get_by_role("button", name="New").click()
    custom_section = dialog.locator(".project-types-body > section").nth(0)
    child = custom_section.locator(".project-type-card[open]")
    child.get_by_label("Name").fill("Browser Derived")
    child.get_by_role("combobox", name="Based on project type").click()
    child.get_by_role("option", name="Browser Parent").click()
    child.get_by_label("Scope").fill("Independent copied scope")
    expect(child.get_by_role("button", name="Generate icon")).to_have_count(0)
    expect(child.get_by_role("button", name="Remove project type")).to_have_count(0)
    expect(child.locator(".project-type-card-icon svg")).to_be_visible()
    save = dialog.locator("header").get_by_role("button", name="Save", exact=True)
    expect(save).to_be_enabled()
    save.click()
    expect(dialog).not_to_be_visible()
    catalog = page.request.get(f"{FIXTURE_URL}/api/project-types").json()
    parent_type = next(
        item for item in catalog["project_types"] if item["name"] == "Browser Parent"
    )
    child_type = next(
        item for item in catalog["project_types"] if item["name"] == "Browser Derived"
    )
    assert parent_type["icon"]["key"] == "placeholder"
    assert child_type["icon"]["key"] == "placeholder"
    assert child_type["based_on"] == parent_type["id"]
    assert child_type["scope"] == "Independent copied scope"
    assert child_type["research_standards_references"] == ["https://example.org/research-standard"]
    assert not [url for url, _ in api_requests if url.endswith("/project-types/icon")]

    # Edit/add/remove are all drafts. Cancel discards all three, and Remove
    # makes no write until Save.
    before = page.request.get(f"{FIXTURE_URL}/api/project-types").json()
    types_button.click()
    dialog = page.get_by_role("dialog", name="Project Types")
    parent_card = dialog.locator(
        '.project-type-card:has(> summary strong:text-is("Browser Parent"))'
    )
    parent_card.locator("summary").click()
    parent_card.get_by_label("Scope").fill("Uncommitted scope")
    expect(dialog.locator("header").get_by_role("button", name="Save")).to_be_enabled()
    title_order = parent_card.locator("summary").evaluate(
        "summary => [...summary.children].map(item => item.tagName.toLowerCase())"
    )
    assert title_order == ["span", "strong", "button", "small"], title_order
    parent_card.locator(".project-type-remove").click()
    dialog.locator(".project-types-section-heading").first.get_by_role("button", name="New").click()
    pending = dialog.locator(".project-types-body > section").first.locator(".project-type-card[open]")
    pending.get_by_label("Name").fill("Discarded addition")
    pending = dialog.locator(
        '.project-type-card:has(> summary strong:text-is("Discarded addition"))'
    )
    pending.get_by_label("Scope").fill("Discarded scope")
    expect(pending.locator(".project-type-remove")).to_have_count(0)
    dialog.locator(".project-types-section-heading").first.get_by_role("button", name="Cancel").click()
    expect(pending).to_have_count(0)
    # Canceling the new type leaves other unsaved edits in the dialog.
    expect(dialog.locator("header").get_by_role("button", name="Save")).to_be_enabled()
    dialog.locator("header").get_by_role("button", name="Cancel", exact=True).click()
    expect(dialog).not_to_be_visible()
    after_cancel = page.request.get(f"{FIXTURE_URL}/api/project-types").json()
    assert after_cancel["revision"] == before["revision"]
    assert {item["id"] for item in after_cancel["project_types"]} == {
        item["id"] for item in before["project_types"]
    }
    parent_after_cancel = next(
        item for item in after_cancel["project_types"] if item["id"] == parent_type["id"]
    )
    assert parent_after_cancel["scope"] == "Original copied research scope"

    # Remove multiple referenced types in one Save and retain each original name.
    types_button.click()
    dialog = page.get_by_role("dialog", name="Project Types")
    dialog.locator(".project-types-section-heading").first.get_by_role("button", name="New").click()
    second_card = dialog.locator(".project-type-card[open]")
    second_card.get_by_label("Name").fill("Browser Second")
    second_card.get_by_label("Scope").fill("Second saved scope")
    with page.expect_response(
        lambda response: (
            response.url.endswith("/api/project-types") and response.request.method == "PUT"
        )
    ):
        dialog.locator("header").get_by_role("button", name="Save", exact=True).click()
    expect(dialog).not_to_be_visible()
    second_type = next(
        item
        for item in page.request.get(f"{FIXTURE_URL}/api/project-types").json()["project_types"]
        if item["name"] == "Browser Second"
    )

    # Project owns a frozen snapshot. Removing its type at Save warns about use,
    # but the derived custom type remains independent from its removed origin.
    affected = project(page, "Deleted custom parent", parent_type["id"])
    project(page, "Deleted second custom type", second_type["id"])
    before = page.request.get(f"{FIXTURE_URL}/api/project-types").json()
    types_button.click()
    dialog = page.get_by_role("dialog", name="Project Types")
    parent_card = dialog.locator(
        '.project-type-card:has(> summary strong:text-is("Browser Parent"))'
    )
    parent_card.locator("summary").click()
    parent_card.locator(".project-type-remove").click()
    second_type_card = dialog.locator(
        '.project-type-card:has(> summary strong:text-is("Browser Second"))'
    )
    second_type_card.locator("summary").click()
    second_type_card.locator(".project-type-remove").click()
    assert (
        page.request.get(f"{FIXTURE_URL}/api/project-types").json()["revision"]
        == before["revision"]
    )
    assert (
        page.request.get(f"{FIXTURE_URL}/api/project-types/{parent_type['id']}/usage").json()[
            "project_count"
        ]
        == 1
    )
    assert (
        page.request.get(f"{FIXTURE_URL}/api/project-types/{second_type['id']}/usage").json()[
            "project_count"
        ]
        == 1
    )
    with page.expect_response(
        lambda response: (
            response.url.endswith("/api/project-types") and response.request.method == "PUT"
        )
    ):
        page.get_by_role("button", name="Save", exact=True).click()
    confirmations = page.evaluate("window.__projectTypeConfirmations")
    assert any(
        "Browser Parent" in message and "1 project" in message for message in confirmations
    ), confirmations
    assert any(
        "Browser Second" in message and "1 project" in message for message in confirmations
    ), confirmations
    expect(dialog).not_to_be_visible()
    catalog_after_delete = page.request.get(f"{FIXTURE_URL}/api/project-types").json()[
        "project_types"
    ]
    assert all(item["id"] != parent_type["id"] for item in catalog_after_delete)
    assert all(item["id"] != second_type["id"] for item in catalog_after_delete)
    derived_after_delete = next(
        item for item in catalog_after_delete if item["id"] == child_type["id"]
    )
    assert derived_after_delete["based_on"] == parent_type["id"]
    assert derived_after_delete["scope"] == "Independent copied scope"

    open_project(page, affected["path"])
    expect(page.get_by_role("heading", name="Deleted custom parent")).to_be_visible()
    expect(page.get_by_text("DESCRIPTION AND ACCEPTANCE CRITERIA", exact=True)).to_be_visible()
    expect(page.get_by_text("Project type unavailable", exact=True).first).to_be_visible()
    expect(page.get_by_role("button", name="Export project")).to_be_visible()
    with page.expect_download() as download_info:
        page.get_by_role("button", name="Export project").click()
        page.get_by_role("dialog", name="Export Project").get_by_role(
            "button", name="Download", exact=True
        ).click()
    exported = json.loads(Path(download_info.value.path()).read_text())
    snapshot = exported["files"]["project.json"]["project_type_snapshot"]
    assert (
        snapshot["id"] == parent_type["id"]
        and snapshot["scope"] == "Original copied research scope"
    )

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
    play = page.get_by_role("button", name="Start a new research session")
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
    expect(page.locator(".session-start-limits")).to_be_visible(timeout=15000)
    start_button = page.get_by_role("button", name="Start Session #1")
    expect(start_button).to_be_visible()
    page.set_viewport_size({"width": 390, "height": 844})
    bounds = start_button.bounding_box()
    assert bounds and bounds["x"] >= 0 and bounds["x"] + bounds["width"] <= 390, bounds
    page.set_viewport_size({"width": 1440, "height": 1000})
    start_button.click()
    row = page.locator(".session-row").filter(has_text="Session #1")
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
    with page.expect_download() as legacy_download:
        page.get_by_role("button", name="Export project").click()
        page.get_by_role("dialog", name="Export Project").get_by_role(
            "button", name="Download", exact=True
        ).click()
    legacy_export = json.loads(Path(legacy_download.value.path()).read_text())
    assert legacy_export["files"]["project.json"]["investigation_type"] == "default"
    assert legacy_export["files"]["project.json"]["project_type_snapshot"] is None
    play = page.get_by_role("button", name="Start a new research session")
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
    settings.get_by_role("option", name="Mathematics").click()
    settings.get_by_role("button", name="Save", exact=True).click()
    expect(settings).not_to_be_visible()
    replaced = page.request.get(
        f"{FIXTURE_URL}/api/projects/inspect?path={quote(legacy['path'], safe='')}"
    ).json()
    assert replaced["project"]["investigation_type"] == "mathematical"
    assert replaced["project"]["project_type_snapshot"]["id"] == "mathematical"
    assert not errors, errors
    browser.close()

print(
    f"PASS real Chrome transactional Save/Cancel, placeholders, draft based-on, stable URL input, deleted-type continuation/replacement, legacy round-trip, keyboard/focus and mobile behavior; evidence {EVIDENCE}"
)
