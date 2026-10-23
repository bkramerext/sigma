"""A8 real browser: settings transactions and truthful connection surfaces.

Requires the separate no-network provider_fixture API described in README.
"""

import json
import os
import re
from dataclasses import asdict
from pathlib import Path
from uuid import uuid4

from playwright.sync_api import expect, sync_playwright

from sigma.projects import create_strategy, inspect_project, project_settings, update_project


def choose_research_type(dialog, label, field_label="Research type"):
    picker = dialog.get_by_role("combobox", name=re.compile(f"^{field_label}"))
    picker.click()
    dialog.get_by_role("option", name=label, exact=True).click()
    return picker


def status_handler(data):
    def handle(route):
        route.fulfill(status=200, content_type="application/json", body=json.dumps(data))

    return handle


with sync_playwright() as p:
    browser = p.chromium.launch(
        executable_path=os.environ.get(
            "SIGMA_BROWSER_EXECUTABLE",
            "/Applications/Google Chrome.app/Contents/MacOS/Google Chrome",
        ),
        headless=True,
    )
    page = browser.new_page(viewport={"width": 1672, "height": 941})
    errors = []
    page.on("pageerror", lambda error: errors.append(str(error)))
    page.route(
        "**/api/**",
        lambda route: route.fulfill(
            response=route.fetch(url=route.request.url.replace("127.0.0.1:5173", "127.0.0.1:8001"))
        ),
    )
    held_connection = []
    page.route("**/api/ai/connection?*", lambda route: held_connection.append(route))
    page.goto("http://127.0.0.1:5173/")
    expect(page.get_by_text("Checking AI…", exact=True)).to_be_visible()
    assert not page.locator(".connection-connected").count()
    held_connection[0].fulfill(
        response=held_connection[0].fetch(
            url=held_connection[0].request.url.replace("127.0.0.1:5173", "127.0.0.1:8001")
        )
    )
    page.unroute("**/api/ai/connection?*")
    expect(page.get_by_text("OpenAI API · key billing", exact=True)).to_be_visible()
    assert (
        page.locator(".connection-dot").evaluate("e=>getComputedStyle(e).backgroundColor")
        == "rgb(117, 177, 140)"
    )
    page.get_by_label("AI connection settings", exact=True).click()
    expect(
        page.get_by_text("API authentication/reachability verified only.", exact=False)
    ).to_be_visible()
    page.keyboard.press("Escape")
    page.get_by_role("button", name="New", exact=True).click()
    dialog = page.get_by_role("dialog")
    expect(dialog.get_by_role("heading", name="New Project", exact=True)).to_be_visible()
    expect(dialog.get_by_label("Project name", exact=True)).to_be_focused()
    labels = ["Project name", "Research problem", "Research category", "LLM Model", "Thinking level"]
    assert dialog.locator("label").all_text_contents() == labels
    expect(dialog.get_by_label("LLM Model", exact=True)).to_have_value("gpt-6.1-sol")
    expect(dialog.get_by_label("Thinking level", exact=True)).to_have_value("high")
    assert dialog.get_by_label("LLM Model", exact=True).locator("option").count() == 3
    title = "Settings browser " + uuid4().hex[:6]
    dialog.get_by_label("Project name", exact=True).fill(title)
    dialog.get_by_label("Research problem", exact=True).fill(
        "Preserve the complete research problem.\nTest assumptions critically."
    )
    research_type = dialog.get_by_role("combobox", name=re.compile("^Research category"))
    research_type.click()
    options = dialog.get_by_role("listbox", name="Research category").get_by_role("option")
    assert options.locator("span").all_text_contents() == [
        "Biology",
        "Chemistry",
        "Computer Science",
        "Economics",
        "Engineering",
        "Law",
        "Mathematics",
        "Military",
        "Philosophy",
        "Physics",
        "Religion",
        "Other",
    ]
    assert dialog.locator(".research-type-icon").count() == 13
    dialog.get_by_role("heading", name="New Project").evaluate(
        "h => { const actions=h.parentElement.querySelector('.settings-actions'); if (!actions || !actions.textContent.includes('Create') || !actions.textContent.includes('Cancel') || !(h.compareDocumentPosition(actions) & Node.DOCUMENT_POSITION_FOLLOWING) || actions.getBoundingClientRect().left < h.getBoundingClientRect().right) throw new Error('Create and Cancel must follow the title'); }"
    )
    expect(dialog.get_by_role("button", name="Create", exact=True)).to_have_css(
        "text-decoration-line", "underline"
    )
    expect(dialog.get_by_role("button", name="Cancel", exact=True)).to_have_css(
        "text-decoration-line", "underline"
    )
    dialog.get_by_role("option", name="Mathematics", exact=True).click()
    expect(research_type).to_contain_text("Mathematics")
    expect(dialog.get_by_role("button", name="Create", exact=True)).to_be_enabled()
    destination = Path(dialog.locator(".project-destination code").inner_text())
    assert not destination.exists()
    for width in (1672, 768, 390, 320):
        page.set_viewport_size({"width": width, "height": 941 if width == 1672 else 844})
        assert dialog.evaluate("(d)=>d.scrollWidth<=d.clientWidth")
        assert page.evaluate("document.documentElement.scrollWidth<=innerWidth")
        page.screenshot(path=f"/tmp/sigma-a8-create-{width}.png", full_page=True)
    page.route(
        "**/api/projects/create",
        lambda route: route.fulfill(
            status=400, content_type="application/json", body='{"error":"Injected create failure"}'
        ),
    )
    dialog.get_by_role("button", name="Create", exact=True).click()
    expect(dialog.get_by_role("alert")).to_have_text("Injected create failure")
    expect(dialog.get_by_label("Project name", exact=True)).to_have_value(title)
    assert not destination.exists()
    page.unroute("**/api/projects/create")
    creates = []
    page.route("**/api/projects/create", lambda route: creates.append(route))
    dialog.locator("form").evaluate(
        '(form) => { for (let i=0;i<2;i++) form.dispatchEvent(new Event("submit", {bubbles:true,cancelable:true})); }'
    )
    expect(dialog.get_by_role("button", name="Creating…", exact=True)).to_be_disabled()
    expect(dialog.get_by_role("button", name="Cancel", exact=True)).to_be_disabled()
    dialog.press("Escape")
    expect(dialog).to_be_visible()
    assert len(creates) == 1 and not destination.exists()
    creates[0].fulfill(
        response=creates[0].fetch(
            url=creates[0].request.url.replace("127.0.0.1:5173", "127.0.0.1:8001")
        )
    )
    page.unroute("**/api/projects/create")
    expect(page.get_by_role("heading", name=title, exact=True)).to_be_visible()
    header_icon = page.locator(".project-header-title-row .research-type-icon")
    title_row = page.locator(".project-header-title-row")
    for width in (1672, 390, 320):
        page.set_viewport_size({"width": width, "height": 941 if width == 1672 else 844})
        expect(header_icon).to_have_class(re.compile("research-type-icon-mathematical"))
        assert title_row.evaluate(
            "e => e.firstElementChild.getBoundingClientRect().right <= e.lastElementChild.getBoundingClientRect().left"
        )
        assert float(title_row.evaluate("e => parseFloat(getComputedStyle(e).columnGap)")) <= 6
        assert page.evaluate("document.documentElement.scrollWidth<=innerWidth")
        page.screenshot(path=f"/tmp/sigma-project-header-type-{width}.png", full_page=True)
    page.set_viewport_size({"width": 1672, "height": 941})
    state = destination / "project.json"
    raw = json.loads(state.read_bytes())
    identity = raw["id"]
    assert (
        raw["schema_version"] == 6
        and raw["ai_model"] == "gpt-6.1-sol"
        and raw["reasoning_effort"] == "high"
    )
    added = create_strategy(
        destination, "Existing research", "Full existing approach.\nDo not reset this research."
    )
    strategy_id = added.project.strategies[-1].id
    page.reload()
    expect(page.get_by_role("heading", name="Existing research", exact=True)).to_be_visible()
    before = state.read_bytes()
    title_button = page.get_by_role("button", name=f"Edit project title: {title}")
    title_button.focus()
    title_button.press("Enter")
    title_input = page.get_by_role("textbox", name="Project title")
    expect(title_input).to_be_focused()
    title_input.fill("Cancelled changes")
    title_input.press("Escape")
    expect(title_button).to_be_focused()
    assert state.read_bytes() == before
    title_button.click()
    title_input.fill("Renamed browser investigation")
    page.locator(".project-title-actions").get_by_role("button", name="Save").click()
    expect(page.get_by_role("heading", name="Renamed browser investigation")).to_be_visible()
    description_button = page.get_by_role("button", name="Edit Plain description")
    description_button.click()
    description = page.get_by_label("Edit Plain source")
    description.fill("A revised problem.\nKeep uncertainty explicit.")
    description.press("Escape")
    assert "A revised problem" not in state.read_text()
    description_button.click()
    description.fill("A revised problem.\nKeep uncertainty explicit.")
    page.locator(".project-intro").get_by_role("button", name="Save text").click()
    expect(page.get_by_role("button", name="Edit Plain description")).to_contain_text(
        "A revised problem"
    )
    settings_button = page.get_by_role("button", name="Project Settings", exact=True)
    settings_button.click()
    expect(dialog.get_by_role("heading", name="Project Settings", exact=True)).to_be_visible()
    assert dialog.locator("label").all_text_contents() == [
        "Research type",
        "LLM Model",
        "Thinking level",
    ]
    dialog.press("Escape")
    expect(settings_button).to_be_focused()
    constrained = {
        "models": [
            {
                "id": "gpt-6.1-sol",
                "label": "Sol",
                "description": "Reviewed",
                "efforts": ["low", "medium", "high", "xhigh"],
                "availability": "available",
            },
            {
                "id": "gpt-6-luna",
                "label": "Luna",
                "description": "Reviewed test compatibility restriction",
                "efforts": ["low"],
                "availability": "available",
            },
        ],
        "message": "Controlled effort restriction fixture",
    }
    page.route("**/api/ai/models", status_handler(constrained))
    settings_button.click()
    dialog.get_by_label("LLM Model", exact=True).select_option("gpt-6-luna")
    expect(dialog.get_by_role("alert")).to_contain_text("Choose a supported level explicitly")
    expect(dialog.get_by_role("button", name="Save Changes", exact=True)).to_be_disabled()
    dialog.get_by_label("Thinking level", exact=True).select_option("low")
    expect(dialog.get_by_role("button", name="Save Changes", exact=True)).to_be_enabled()
    dialog.press("Escape")
    page.unroute("**/api/ai/models")
    settings_button.click()
    choose_research_type(dialog, "Other")
    dialog.get_by_label("LLM Model", exact=True).select_option("gpt-6-luna")
    dialog.get_by_label("Thinking level", exact=True).select_option("xhigh")
    page.route(
        "**/api/projects/update",
        lambda route: route.fulfill(
            status=400, content_type="application/json", body='{"error":"Injected save failure"}'
        ),
    )
    dialog.get_by_role("button", name="Save Changes", exact=True).click()
    expect(dialog.get_by_role("alert")).to_have_text("Injected save failure")
    expect(dialog.get_by_label("Thinking level", exact=True)).to_have_value("xhigh")
    page.unroute("**/api/projects/update")
    dialog.get_by_role("button", name="Save Changes", exact=True).click()
    expect(settings_button).to_be_focused()
    raw = json.loads(state.read_bytes())
    assert (
        raw["id"] == identity
        and raw["ai_model"] == "gpt-6-luna"
        and raw["reasoning_effort"] == "xhigh"
    )
    assert (
        raw["strategies"][0]["id"] == strategy_id and raw["events"][-1]["kind"] == "project.updated"
    )
    assert inspect_project(destination).path == str(destination)
    page.reload()
    settings_button = page.get_by_role("button", name="Project Settings", exact=True)
    settings_button.click()
    expect(dialog.get_by_label("LLM Model", exact=True)).to_have_value("gpt-6-luna")
    expect(dialog.get_by_label("Thinking level", exact=True)).to_have_value("xhigh")
    dialog.get_by_role("button", name="Cancel", exact=True).click()
    expect(settings_button).to_be_focused()
    page.get_by_label("New Strategy options", exact=True).click()
    page.get_by_role("button", name="Generate with AI", exact=True).click()
    expect(dialog.locator(".provider-context")).to_have_text(
        "OpenAI API · billed separately · gpt-6-luna · Extra high"
    )
    dialog.press("Escape")
    settings_button.click()
    research_type = choose_research_type(dialog, "Mathematics")
    latest = inspect_project(destination)
    prior = asdict(project_settings(latest.project))
    update_project(
        destination, **{**prior, "title": "Another editor changed this name"}, expected=prior
    )
    conflict_bytes = state.read_bytes()
    dialog.get_by_role("button", name="Save Changes", exact=True).click()
    expect(dialog.get_by_role("alert")).to_contain_text("changed elsewhere")
    expect(research_type).to_contain_text("Mathematics")
    assert state.read_bytes() == conflict_bytes
    dialog.press("Escape")
    page.reload()
    settings_button = page.get_by_role("button", name="Project Settings", exact=True)
    expect(settings_button).to_be_visible()
    no_models = {
        "models": [],
        "default_model": "gpt-6.1-sol",
        "default_effort": "high",
        "message": "Provider is offline; stored choices are retained.",
    }
    page.route("**/api/ai/models", status_handler(no_models))
    settings_button.click()
    expect(dialog.get_by_label("LLM Model", exact=True)).to_have_value("gpt-6-luna")
    expect(dialog.get_by_text("Provider is offline;", exact=False)).to_be_visible()
    expect(dialog.get_by_role("button", name="Save Changes", exact=True)).to_be_enabled()
    dialog.get_by_role("button", name="Save Changes", exact=True).click()
    expect(settings_button).to_be_focused()
    assert json.loads(state.read_bytes())["ai_model"] == "gpt-6-luna"
    page.unroute("**/api/ai/models")
    # Truthful header alternatives and Retry on both Home/workspace; no status colors alone.
    for status, label, guidance in [
        (
            "unauthorized",
            "Can't connect to OpenAI API · Check API key",
            "401 authentication failed",
        ),
        ("forbidden", "OpenAI API access denied", "403 permissions denied"),
        ("limited", "OpenAI API rate/quota limited", "429 rate/quota limited"),
        ("unavailable", "OpenAI API unavailable", "Check connection"),
        ("unconfigured", "OpenAI API not configured", "Set OPENAI_API_KEY"),
        ("connected", "OpenAI API · key billing", "Authentication only, not generation or billing"),
    ]:
        data = {
            "mode": "api_key",
            "accounts": [],
            "status": status,
            "label": label,
            "guidance": guidance,
            "checked_at": "2026-01-01T00:00:00+00:00" if status == "connected" else None,
            "ttl_seconds": 60,
        }
        page.route(
            "**/api/ai/connection?*",
            status_handler(data),
        )
        page.reload()
        expect(page.get_by_role("button", name="Project Settings", exact=True)).to_be_visible()
        expect(
            page.get_by_text(
                "OpenAI API · key billing" if status == "connected" else label, exact=True
            )
        ).to_be_visible()
        page.get_by_label("AI connection settings", exact=True).click()
        expect(page.get_by_role("button", name="Retry connection", exact=True)).to_be_enabled()
        assert page.evaluate("document.documentElement.scrollWidth<=innerWidth")
        page.screenshot(path=f"/tmp/sigma-a8-status-{status}-320.png", full_page=True)
        page.unroute("**/api/ai/connection?*")
    page.get_by_role("button", name="Back to home", exact=True).click()
    expect(page.get_by_role("button", name="New", exact=True)).to_be_visible()
    page.wait_for_timeout(150)
    page.go_back()
    expect(page.get_by_role("button", name="Project Settings", exact=True)).to_be_visible()
    assert (
        state.read_bytes() == json.dumps(json.loads(state.read_bytes()), indent=2).encode() + b"\n"
    )
    assert not errors, errors
    page.unroute_all(behavior="ignoreErrors")
    browser.close()
print(
    "PASS shared Create/Edit labels, defaults, offline selection retention, atomic save/no-op/error/retry/focus, UUID/path/history, per-project AI settings, responsive layouts and truthful status alternatives"
)
