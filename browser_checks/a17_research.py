"""Real Chrome A17 three-pane workspace against the isolated provider fixture."""

import json
import os
import re
from pathlib import Path
from urllib.parse import urlencode
from uuid import uuid4

from playwright.sync_api import expect, sync_playwright

with sync_playwright() as playwright:
    browser = playwright.chromium.launch(
        executable_path=os.environ.get(
            "SIGMA_BROWSER_EXECUTABLE",
            "/Applications/Google Chrome.app/Contents/MacOS/Google Chrome",
        ),
        headless=True,
        args=["--disable-web-security"],
    )
    context = browser.new_context(viewport={"width": 1440, "height": 900})
    page = context.new_page()
    errors = []
    starts = []
    legacy_titleless = {"enabled": False}
    page.on("pageerror", lambda error: errors.append(str(error)))
    page.on(
        "request",
        lambda request: (
            starts.append(request.url)
            if request.url.endswith("/api/projects/research-sessions/start")
            else None
        ),
    )

    def forward(route):
        response = route.fetch(url=route.request.url.replace("127.0.0.1:5173", "127.0.0.1:8002"))
        if legacy_titleless["enabled"] and route.request.url.endswith("/api/projects/open"):
            data = response.json()
            data["project"]["strategies"][0].pop("title", None)
            route.fulfill(response=response, json=data)
        else:
            route.fulfill(response=response)

    page.route("**/api/**", forward)
    page.goto("http://127.0.0.1:5173")
    page.get_by_role("tab", name="Samples", exact=True).click()
    page.get_by_role("tabpanel", name="Samples", exact=True).get_by_role(
        "button", name="Open Counting Constrained Binary Strings"
    ).click()
    page.wait_for_url("**/project?*")
    expect(page.get_by_role("heading", name="Project")).to_be_visible()
    expect(page.get_by_role("button", name="Back to Home", exact=True)).to_be_visible()
    project_header = page.locator(".project-pane-heading")
    project_disclosure = project_header.get_by_role("button", name="Project", exact=True)
    project_disclosure.click()
    expect(page.locator("#project-pane-content")).to_be_hidden()
    project_header.get_by_role("button", name="Download project", exact=True).click()
    expect(page.get_by_role("dialog", name="Export")).to_be_visible()
    page.get_by_role("button", name="Cancel", exact=True).click()
    expect(page.locator("#project-pane-content")).to_be_hidden()
    page.get_by_role("button", name="Project settings", exact=True).click()
    settings = page.get_by_role("dialog", name="Settings")
    main_box = settings.bounding_box()
    expect(settings.get_by_role("tab", name="Main")).to_have_attribute("aria-selected", "true")
    settings.get_by_role("tab", name="Limits").focus()
    page.keyboard.press("ArrowRight")
    expect(settings.get_by_role("tab", name="Limits")).to_have_attribute("aria-selected", "true")
    expect(settings.get_by_role("tabpanel", name="Limits")).to_be_visible()
    expect(settings.get_by_label("Research rounds")).to_have_value("3")
    expect(settings.get_by_label("Model calls")).to_have_value("6")
    rounds_input = settings.get_by_label("Research rounds")
    assert rounds_input.evaluate("element => getComputedStyle(element).appearance") == "textfield"
    rounds_input.fill("4")
    expect(
        settings.get_by_role("alert").filter(has_text="two model calls per round")
    ).to_be_visible()
    save_settings = settings.get_by_role("button", name="Save", exact=True)
    expect(save_settings).to_be_disabled()
    rounds_input.fill("0")
    expect(
        settings.get_by_role("alert").filter(has_text="whole number from 1 to 10")
    ).to_be_visible()
    rounds_input.fill("3")
    cost_input = settings.get_by_label("Maximum estimated session cost (USD)")
    cost_input.fill("0")
    expect(settings.get_by_role("alert").filter(has_text="$0.01 to $100.00")).to_be_visible()
    expect(save_settings).to_be_disabled()
    cost_input.fill("")
    expect(save_settings).to_be_enabled()
    limits_box = settings.bounding_box()
    assert (
        main_box
        and limits_box
        and abs(main_box["width"] - limits_box["width"]) < 1
        and abs(main_box["height"] - limits_box["height"]) < 1
    )
    settings.get_by_role("button", name="Cancel", exact=True).click()
    expect(page.locator("#project-pane-content")).to_be_hidden()
    project_disclosure.click()
    expect(page.locator("#project-pane-content")).to_be_visible()
    connection = page.locator(".api-connection")
    connection.locator("summary").click()
    connection_dialog = page.get_by_role("dialog", name="AI connection settings")
    expect(connection_dialog).to_be_visible()
    assert (
        page.locator(".connection-backdrop").evaluate("node => getComputedStyle(node).zIndex")
        == "1199"
    )
    project_title_button = page.get_by_role("button", name=re.compile("Edit project title:"))
    box = project_title_button.bounding_box()
    assert box
    page.mouse.click(box["x"] + box["width"] / 2, box["y"] + box["height"] / 2)
    expect(connection_dialog).to_be_hidden()
    expect(page.locator("#project-pane-title-input")).to_have_count(0)
    connection.locator("summary").click()
    connection_dialog = page.get_by_role("dialog", name="AI connection settings")
    page.keyboard.press("Escape")
    expect(connection_dialog).to_be_hidden()
    expect(connection.locator("summary")).to_be_focused()
    path = page.evaluate("new URL(location.href).searchParams.get('path')")
    workspace_title = f"A17.1 Workspace {uuid4().hex[:8]}"
    project_file = Path(path) / "project.json"
    result = page.evaluate(
        """async path => {
      const response = await fetch('/api/projects/strategies', { method:'POST', headers:{'Content-Type':'application/json'}, body:JSON.stringify({path, title:'Saved research approach', approach:'Derive a recurrence and inspect boundary cases.', summary:'Use a terminal decomposition.'}) });
      return {status:response.status, body:await response.json()};
    }""",
        path,
    )
    assert result["status"] == 201, result
    page.reload()

    panes = page.locator(".project-pane, .strategies-pane, .sessions-pane")
    expect(panes).to_have_count(3)
    assert panes.evaluate_all("nodes => nodes.map(node => node.className)") == [
        "workspace-pane project-pane",
        "pool workspace-pane strategies-pane",
        "sessions-pane workspace-pane",
    ]
    expect(page.get_by_role("heading", name="Project")).to_be_visible()
    expect(page.locator(".project-pane-title-line")).not_to_contain_text("Project:")
    expect(page.locator(".project-pane").locator("details")).to_have_count(0)
    original_project_title = page.locator(".project-pane-title-line .current-project").inner_text()
    page.get_by_role("button", name=re.compile("Edit project title:")).focus()
    page.keyboard.press("Enter")
    expect(page.locator(".project-title-edit-form")).to_be_visible()
    expect(page.locator(".project-title-pencil")).to_have_count(0)
    page.get_by_label("Project title", exact=True).fill("cancelled by outside click")
    page.get_by_role("button", name="Strategies", exact=True).click()
    expect(page.locator(".project-title-edit-form")).to_have_count(0)
    expect(page.locator(".project-pane-title-line .current-project")).to_have_text(
        original_project_title
    )
    page.get_by_role("button", name="Strategies", exact=True).click()
    page.get_by_role("button", name=re.compile("Edit project title:")).click()
    page.get_by_label("Project title", exact=True).fill(workspace_title)
    page.get_by_role("button", name="Save", exact=True).click()
    expect(page.locator(".project-pane-title-line .current-project")).to_have_text(workspace_title)
    title_box = page.locator(".project-pane-title-line .current-project").bounding_box()
    pencil_box = page.locator(".project-title-pencil").bounding_box()
    assert title_box and pencil_box and pencil_box["x"] < title_box["x"] + title_box["width"] + 20
    expect(page.locator(".project-pane-heading")).not_to_contain_text("For each integer n")
    page.screenshot(path="/tmp/sigma-a174-desktop.png", full_page=True)
    page.reload()
    expect(page.locator(".project-pane-title-line .current-project")).to_have_text(workspace_title)
    page.get_by_role("button", name=re.compile("Edit project title:")).click()
    page.get_by_label("Project title", exact=True).fill("   ")
    page.get_by_role("button", name="Save", exact=True).click()
    expect(page.get_by_role("alert")).to_have_text("Enter a project title.")
    expect(page.locator("#project-pane-title-input")).to_be_visible()
    page.get_by_role("button", name="Cancel", exact=True).click()
    project_before = project_file.read_bytes()
    page.get_by_role("button", name=re.compile("Edit project title:")).click()
    expect(page.get_by_role("button", name="Edit research problem")).to_be_disabled()
    expect(page.get_by_role("button", name="Generate", exact=True)).to_be_disabled()
    page.get_by_role("button", name="Edit research problem").evaluate("button => button.click()")
    assert page.locator("#text-editor-project-project").count() == 0
    page.locator(".project-title-edit-form").get_by_role(
        "button", name="Cancel", exact=True
    ).click()

    # A project description draft excludes every other edit/creation entry point.
    page.get_by_role("button", name="Edit research problem").click()
    description = page.locator("#text-editor-project-project")
    description.fill("unsaved project description draft")
    expect(page.get_by_role("button", name="Edit project title:")).to_be_disabled()
    expect(page.get_by_role("button", name="Generate", exact=True)).to_be_disabled()
    first_title_button = page.locator("li[data-strategy-id]").first.get_by_role(
        "button", name=re.compile("Edit strategy title:")
    )
    expect(first_title_button).to_be_disabled()
    # Pointer and keyboard attempts cannot start a second mode; the active draft remains.
    first_title_button.evaluate("button => button.click()")
    page.keyboard.press("Tab")
    assert page.locator(".strategy-rename-form").count() == 0
    assert description.input_value() == "unsaved project description draft"
    page.locator(".project-intro").get_by_role("button", name="Cancel", exact=True).click()

    # The Strategies pane is independently collapsible and keeps its open draft mounted.
    page.get_by_role("button", name="Strategies", exact=True).click()
    expect(page.locator("#strategies-pane-content")).to_be_hidden()
    page.locator(".strategy-heading-actions button:first-child").evaluate(
        "button => { button.click(); button.parentElement.querySelectorAll('button')[1].click(); }"
    )
    expect(page.locator("#strategy-composer form.strategy-form")).to_have_count(1)
    expect(page.locator(".inline-proposal")).to_have_count(0)
    expect(page.locator("#strategies-pane-content")).to_be_visible()
    new_form = page.locator("#strategy-composer form.strategy-form")
    expect(page.locator("#strategy-title")).to_be_focused()
    expect(page.get_by_role("button", name="Generate", exact=True)).to_be_disabled()
    expect(page.get_by_role("button", name="Edit project title:")).to_be_disabled()
    expect(connection.locator("summary")).to_have_attribute("aria-disabled", "true")
    connection.locator("summary").evaluate("node => node.click()")
    expect(connection.locator(".connection-details")).to_have_count(0)
    page.locator("#strategy-title").fill("Unfinished strategy draft")
    page.get_by_role("button", name="Strategies", exact=True).click()
    expect(new_form).to_be_attached()
    assert page.locator("#strategy-title").input_value() == "Unfinished strategy draft"
    page.get_by_role("button", name="Strategies", exact=True).click()
    new_form.get_by_role("button", name="Cancel", exact=True).click()
    expect(page.get_by_role("button", name="Generate", exact=True)).to_be_enabled()

    # Generate also restores a collapsed section and focuses its creation surface.
    page.get_by_role("button", name="Strategies", exact=True).click()
    page.get_by_role("button", name="Generate", exact=True).focus()
    page.keyboard.press("Enter")
    expect(page.locator("#strategies-pane-content")).to_be_visible()
    expect(page.locator("#proposal-seed")).to_be_focused()
    expect(
        page.locator(".strategies-pane-heading").get_by_role("button", name="New", exact=True)
    ).to_have_count(0)
    expect(page.get_by_role("button", name=re.compile("Edit project title:")).first).to_be_enabled()
    page.locator(".inline-proposal").get_by_role("button", name="Cancel", exact=True).click()
    expect(page.get_by_role("button", name="Generate", exact=True)).to_be_enabled()

    header_order = page.locator(".strategies-heading-right").evaluate(
        "node => Array.from(node.children).map(child => child.className)"
    )
    assert header_order[:3] == [
        "strategy-heading-actions",
        "section-count",
        "strategy-process-controls",
    ], header_order
    assert (
        page.locator(".strategies-heading-right").evaluate(
            "node => getComputedStyle(node).marginLeft"
        )
        == "0px"
    )

    # Generation title remains explicit through review, acceptance, and rendering.
    page.get_by_role("button", name="Generate", exact=True).click()
    proposal = page.locator(".inline-proposal")
    page.locator("#proposal-seed").fill("delay-fixture")
    dot = page.locator(".api-connection .connection-dot")
    proposal.get_by_role("button", name="Generate", exact=True).click()
    expect(dot).to_have_class(re.compile("connection-active"), timeout=10000)
    page.get_by_role("button", name="Render research problem as Markdown", exact=True).click()
    expect(
        page.get_by_role("button", name="Show plain research problem", exact=True)
    ).to_be_visible(timeout=10000)
    expect(dot).to_have_class(re.compile("connection-active"))
    expect(proposal.get_by_label("Title", exact=True)).to_have_value(
        "Position-shift subset count", timeout=45000
    )
    expect(dot).not_to_have_class(re.compile("connection-active"))
    proposal.get_by_role("button", name="Accept", exact=True).click()
    expect(page.locator(".strategy-row")).to_have_count(2)

    first_strategy_id = result["body"]["project"]["strategies"][0]["id"]
    first_row = page.locator(f"li[data-strategy-id='{first_strategy_id}']")
    expect(first_row.locator(".strategy-title-line h3")).to_have_text("Saved research approach")
    expect(first_row.locator(".strategy-expanded")).to_be_visible()
    expect(first_row.locator("details.strategy-detail")).to_have_count(0)
    more = first_row.get_by_role(
        "button", name="More actions for Saved research approach", exact=True
    )
    more.click()
    expect(more).to_have_attribute("aria-expanded", "true")
    menu = first_row.get_by_role("menu")
    expect(menu.locator("[role=menuitem]")).to_have_count(5)
    assert menu.locator("[role=menuitem]").all_text_contents() == [
        "Schedule",
        "Fork",
        "Report artifact",
        "Change stage",
        "Remove",
    ]
    expect(menu.get_by_role("menuitem", name="Schedule")).to_be_disabled()
    menu.get_by_role("menuitem", name="Fork").focus()
    page.keyboard.press("ArrowDown")
    expect(menu.get_by_role("menuitem", name="Change stage")).to_be_focused()
    page.keyboard.press("Escape")
    expect(more).to_be_focused()
    expect(more).to_have_attribute("aria-expanded", "false")
    page.get_by_role(
        "button", name="Edit strategy title: Saved research approach", exact=True
    ).click()
    expect(first_row.locator(".strategy-title-pencil")).to_have_count(0)
    expect(first_row.locator(".strategy-rename-form")).to_be_visible()
    expect(first_row.locator(".strategy-expanded")).to_be_visible()
    page.locator(f"#strategy-title-{first_strategy_id}").fill("cancelled strategy title")
    page.get_by_role("button", name="Sessions", exact=True).click()
    expect(first_row.locator(".strategy-rename-form")).to_have_count(0)
    expect(first_row.locator(".strategy-title-line h3")).to_have_text("Saved research approach")
    page.get_by_role("button", name="Sessions", exact=True).click()
    page.get_by_role(
        "button", name="Edit strategy title: Saved research approach", exact=True
    ).click()
    page.locator(f"#strategy-title-{first_strategy_id}").fill("A17.1 saved approach")
    page.locator(f"li[data-strategy-id='{first_strategy_id}']").get_by_role(
        "button", name="Save", exact=True
    ).click()
    expect(page.locator(f"button#strategy-{first_strategy_id} h3")).to_have_text(
        "A17.1 saved approach"
    )
    expect(first_row.locator(".strategy-expanded")).to_be_visible()

    def fail_strategy_edit(route):
        route.fulfill(status=503, json={"error": "fixture save failure"})

    page.route("**/api/projects/strategies/edit", fail_strategy_edit)
    page.get_by_role("button", name="Edit strategy title: A17.1 saved approach", exact=True).click()
    failed_title = page.locator(f"#strategy-title-{first_strategy_id}")
    failed_title.fill("Unsaved after server failure")
    first_row.get_by_role("button", name="Save", exact=True).click()
    expect(first_row.get_by_role("alert")).to_contain_text("fixture save failure")
    expect(failed_title).to_have_value("Unsaved after server failure")
    first_row.get_by_role("button", name="Cancel", exact=True).click()
    page.unroute("**/api/projects/strategies/edit", fail_strategy_edit)
    project_before = project_file.read_bytes()

    research = page.locator(".sessions-pane")
    expect(research.get_by_role("heading", name="Sessions")).to_be_visible()
    expect(research.locator(".section-count")).to_have_text("0 sessions, 0 running")
    expect(research.locator(".session-columns")).to_contain_text("Session")
    assert (
        research.locator(".session-columns").evaluate(
            "node => getComputedStyle(node).textTransform"
        )
        == "uppercase"
    )
    assert research.get_by_role("button", name=re.compile("start", re.IGNORECASE)).count() == 0
    play = page.get_by_role("button", name="Start research session", exact=True)
    expect(play).to_be_enabled()
    play.click()
    expect(research.locator(".research-consent")).to_contain_text("API key billing")
    expect(research.locator(".research-consent")).to_contain_text("3 research rounds")
    expect(research.locator(".research-consent")).to_contain_text("6 model calls")
    expect(research.locator(".research-consent")).to_contain_text("Usage may accrue")
    research.get_by_role("button", name="Confirm and start", exact=True).dblclick(delay=5)
    first_session = research.locator("li[data-session-id]")
    expect(first_session).to_have_count(1, timeout=15000)
    expect(first_session.locator(".session-row-title")).to_have_text("Session #1")
    expect(first_session.locator(".session-status")).to_contain_text("completed")
    page.wait_for_function(
        """id => { const row = document.querySelector(`[data-session-id="${CSS.escape(id)}"]`); if (!row) return false; const rect = row.getBoundingClientRect(); return rect.top < innerHeight && rect.bottom > 0; }""",
        arg=first_session.get_attribute("data-session-id"),
    )
    expect(research.locator(".section-count")).to_have_text("1 session, 0 running")
    expect(page.locator(".api-connection .connection-dot")).not_to_have_class(
        re.compile("connection-active")
    )
    expect(first_session).to_contain_text("completed")
    expect(research).to_contain_text("Cycle 3 of 3")
    expect(research).to_contain_text("6 of 6 calls used (0 remaining)")
    expect(research).to_contain_text("Completed · budget exhausted")
    expect(first_session.locator(".session-row-content")).to_be_visible()
    artifacts = research.get_by_label("Research artifacts")
    expect(artifacts.locator("li")).to_have_count(3)
    expect(artifacts).to_contain_text("Independent fixture review for cycle 1")
    expect(artifacts).to_contain_text("Unverified research note")
    events = research.get_by_label("Recent session activity")
    expect(events.locator("li").last).to_contain_text("artifact committed")
    expect(events.get_by_role("button", name="Recent activity")).to_have_attribute(
        "aria-expanded", "false"
    )
    strategy_navigation = first_session.get_by_role(
        "link", name="Go to strategy: A17.1 saved approach", exact=True
    )
    expect(strategy_navigation).to_be_visible()
    strategy_navigation.click()
    expect(page.locator("#strategy-" + first_strategy_id)).to_be_focused()
    assert project_file.read_bytes() == project_before

    session_list = page.evaluate(
        "async path => (await (await fetch('/api/projects/research-sessions?' + new URLSearchParams({path}))).json()).sessions",
        path,
    )
    assert len(session_list) == 1, session_list
    session_one = session_list[0]
    page.goto("http://127.0.0.1:5173")
    page.goto(f"http://127.0.0.1:5173/project?{urlencode({'path': path})}")
    expect(page.locator("li[data-session-id]")).to_have_count(1)
    expect(page.locator("li[data-session-id]").first.locator(".session-row-title")).to_have_text(
        "Session #1"
    )
    expect(
        page.locator("li[data-session-id]").first.locator(".session-row-content")
    ).to_be_visible()
    expect(page.locator(".research-artifacts li")).to_have_count(3)
    restored = page.evaluate(
        "async ({path,id}) => await (await fetch('/api/projects/research-sessions/' + id + '?' + new URLSearchParams({path}))).json()",
        {"path": path, "id": session_one["id"]},
    )
    assert len(restored["artifacts"]) == 3 and restored["session_number"] == 1

    # Exercise Pause, Resume, and terminal Stop while a local provider request is delayed.
    page.get_by_role("button", name="Edit strategy title: A17.1 saved approach", exact=True).click()
    page.locator(f"#strategy-title-{first_strategy_id}").fill("Pause and stop fixture strategy")
    page.locator(f"li[data-strategy-id='{first_strategy_id}']").get_by_role(
        "button", name="Save", exact=True
    ).click()
    page.reload()
    research = page.locator(".sessions-pane")
    page.get_by_role("button", name="Start research session", exact=True).click()
    research.get_by_role("button", name="Confirm and start", exact=True).click()
    pause_row = research.locator("li[data-session-id]").filter(has_text="Session #2")
    expect(pause_row.locator(".session-status")).to_contain_text("running", timeout=10000)
    expect(pause_row.locator(".session-row-content")).to_be_visible()
    page.get_by_role("button", name="Sessions", exact=True).click()
    expect(page.locator("#sessions-pane-content")).to_be_hidden()
    expect(research.locator(".section-count")).to_contain_text("1 running")
    page.get_by_role("button", name="Sessions", exact=True).click()
    expect(pause_row.locator(".session-status")).to_contain_text("running")
    dot = page.locator(".api-connection .connection-dot")
    expect(dot).to_have_class(re.compile("connection-active"), timeout=10000)
    page.emulate_media(reduced_motion="reduce")
    expect(dot).to_have_css("animation-name", "none")
    expect(dot).to_have_css("background-color", "rgb(117, 177, 140)")
    page.emulate_media(reduced_motion="no-preference")
    expect(dot).to_have_css("animation-name", "connection-dot-pulse")
    page.get_by_role("button", name="Pause research session", exact=True).click()
    expect(pause_row.locator(".session-status")).to_contain_text("paused", timeout=5000)
    expect(pause_row.get_by_role("button", name="Remove session", exact=True)).to_have_count(0)
    resume = page.get_by_role("button", name=re.compile("Resume unavailable"))
    expect(resume).to_be_disabled()
    expect(pause_row).to_contain_text("completion is ambiguous")
    pause_row.get_by_role("button", name="Stop", exact=True).click()
    confirm_stop = research.get_by_role("group", name="Confirm stop session")
    confirm_stop.get_by_role("button", name="Confirm stop", exact=True).click()
    expect(pause_row.locator(".session-status")).to_contain_text("stopped", timeout=5000)
    expect(pause_row.get_by_role("button", name="Remove session", exact=True)).to_be_visible()

    # A background provider failure is reconciled into the history and a toast.
    page.get_by_role(
        "button", name="Edit strategy title: Pause and stop fixture strategy", exact=True
    ).click()
    page.locator(f"#strategy-title-{first_strategy_id}").fill("Failure fixture strategy")
    page.locator(f"li[data-strategy-id='{first_strategy_id}']").get_by_role(
        "button", name="Save", exact=True
    ).click()
    page.reload()
    research = page.locator(".sessions-pane")
    expect(research.locator("li[data-session-id]")).to_have_count(2)
    assert research.locator(".session-row-title").all_text_contents() == [
        "Session #1",
        "Session #2",
    ]
    expect(research).to_contain_text("Session #2")
    expect(research).to_contain_text("Pause and stop fixture strategy")
    expect(research.locator(".section-count")).to_have_text("2 sessions, 0 running")
    page.get_by_role("button", name="Start research session", exact=True).click()
    research.get_by_role("button", name="Confirm and start", exact=True).click()
    failure_row = research.locator("li[data-session-id]").filter(has_text="Session #3")
    expect(failure_row.locator(".session-status")).to_contain_text("failed", timeout=10000)
    expect(page.locator(".request-toast")).to_have_count(1)
    page.get_by_role("button", name="Dismiss request error").click()
    expect(research.locator(".section-count")).to_have_text("3 sessions, 0 running")
    assert research.locator(".session-row-title").all_text_contents() == [
        "Session #1",
        "Session #2",
        "Session #3",
    ]
    expect(failure_row).to_contain_text("Failure fixture strategy")

    saved_before_fallback = project_file.read_bytes()
    legacy_titleless["enabled"] = True
    page.goto("http://127.0.0.1:5173")
    page.goto(f"http://127.0.0.1:5173/project?{urlencode({'path': path})}")
    expect(
        page.locator(".strategy-title-line h3").filter(
            has_text="Derive a recurrence and inspect boundary cases."
        )
    ).to_be_visible()
    assert project_file.read_bytes() == saved_before_fallback
    legacy_titleless["enabled"] = False

    # All workspace sections and rows use independent accessible disclosures.
    expect(page.locator(".project-pane").locator("details")).to_have_count(0)
    expect(research).to_be_visible()
    first_session = research.locator("li[data-session-id]").first
    expect(first_session.locator(":scope > details")).to_have_count(0)
    first_session.get_by_role("button", name=re.compile("Session #1")).click()
    expect(first_session.locator(".session-row-content")).to_be_visible()
    first_session.get_by_role("button", name=re.compile("Session #1")).press("Enter")
    expect(first_session.locator(".session-row-content")).to_be_hidden()
    first_session.get_by_role("button", name=re.compile("Session #1")).press("Space")
    expect(first_session.locator(".session-row-content")).to_be_visible()
    expect(first_session.locator(".session-outcome")).to_contain_text("Outcome:")
    expect(
        first_session.get_by_label("Research artifacts").locator(":scope > ol > li > details")
    ).to_have_count(3)
    expect(page.locator("#strategies-pane-content")).to_be_visible()
    page.get_by_role("button", name="Strategies", exact=True).click()
    expect(page.locator("#strategies-pane-content")).to_be_hidden()
    expect(research).to_be_visible()
    page.get_by_role("button", name="Strategies", exact=True).click()
    expect(page.locator("#strategies-pane-content")).to_be_visible()
    first_strategy_row = page.locator("li[data-strategy-id]").first
    first_strategy_row.locator(".strategy-row-disclosure").click()
    expect(first_strategy_row.locator(".strategy-expanded")).to_be_hidden()
    first_strategy_row.locator(".strategy-row-disclosure").press("Enter")
    expect(first_strategy_row.locator(".strategy-expanded")).to_be_visible()
    stopped_session = research.locator("li[data-session-id]").filter(has_text="Session #2")
    expect(stopped_session.locator(".session-row-content")).to_be_hidden()
    stopped_session.get_by_role("button", name="Remove session", exact=True).click()
    confirm_remove = stopped_session.get_by_role("group", name="Confirm remove Session 2")
    confirm_remove.get_by_role("button", name="Confirm remove", exact=True).click()
    expect(research.locator("li[data-session-id]")).to_have_count(2)
    remaining = page.evaluate(
        "async path => (await (await fetch('/api/projects/research-sessions?' + new URLSearchParams({path}))).json()).sessions.map(session => session.session_number)",
        path,
    )
    assert sorted(remaining) == [1, 3], remaining
    page.get_by_role("button", name="Project", exact=True).click()
    expect(page.locator("#project-pane-content")).to_be_hidden()
    page.get_by_role("button", name="Download project", exact=True).click()
    export_dialog = page.get_by_role("dialog", name="Export")
    expect(export_dialog).to_be_visible()
    with page.expect_download() as download_info:
        export_dialog.get_by_role("button", name="Download project", exact=True).click()
    export_data = json.loads(Path(download_info.value.path()).read_text(encoding="utf-8"))
    assert export_data["export_version"] == 2
    assert [session["session_number"] for session in export_data["research_sessions"]] == [1, 3]
    assert export_data["research_sessions"][0]["artifacts"]
    assert export_data["research_sessions"][0]["outcome"]["assessment"] == "mixed"
    assert "fixture-token" not in json.dumps(export_data)
    expect(export_dialog).to_be_hidden()
    expect(page.locator("#project-pane-content")).to_be_hidden()
    page.set_viewport_size({"width": 390, "height": 844})
    assert page.evaluate("document.documentElement.scrollWidth <= window.innerWidth")
    assert (
        page.locator(".strategies-heading-right").evaluate(
            "node => getComputedStyle(node).marginLeft"
        )
        == "0px"
    )
    expect(page.get_by_role("button", name="Back to Home", exact=True)).to_be_visible()
    connection.locator("summary").click()
    mobile_dialog = page.get_by_role("dialog", name="AI connection settings")
    expect(mobile_dialog).to_be_visible()
    dialog_box = mobile_dialog.bounding_box()
    assert dialog_box and dialog_box["x"] >= 0 and dialog_box["y"] >= 0
    assert dialog_box["x"] + dialog_box["width"] <= 390
    assert dialog_box["y"] + dialog_box["height"] <= 844
    page.keyboard.press("Escape")
    expect(mobile_dialog).to_be_hidden()
    page.screenshot(path="/tmp/sigma-a174-mobile.png", full_page=True)
    assert not errors, errors
    assert len(starts) == 3, starts
    print(
        "PASS real Chrome A17.4: stable Settings frame, Project actions while collapsed, keyboard menu, project/strategy/session disclosures, launch scroll, outcome/artifact visibility, activity collapse, confirmed deletion, export round-trip and mobile overflow"
    )
    page.unroute_all(behavior="ignoreErrors")
    browser.close()
