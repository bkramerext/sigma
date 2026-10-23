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
    provider_calls = []
    legacy_titleless = {"enabled": False}
    legacy_outcome = {"enabled": False}
    chatgpt_connection = {"enabled": False}
    fail_export = {"enabled": False}
    page.on("pageerror", lambda error: errors.append(str(error)))
    page.on(
        "request",
        lambda request: (
            starts.append(request.url)
            if request.url.endswith("/api/projects/research-sessions/start")
            else None
        ),
    )
    page.on(
        "request",
        lambda request: (
            provider_calls.append(request.url)
            if request.url.endswith("/api/projects/text/convert")
            else None
        ),
    )

    def forward(route):
        if fail_export["enabled"] and "/api/projects/export" in route.request.url:
            route.fulfill(status=503, json={"error": "fixture export failure"})
            return
        response = route.fetch(url=route.request.url.replace("127.0.0.1:5173", "127.0.0.1:8002"))
        if legacy_titleless["enabled"] and route.request.url.endswith("/api/projects/open"):
            data = response.json()
            data["project"]["strategies"][0].pop("title", None)
            route.fulfill(response=response, json=data)
        elif legacy_outcome["enabled"] and "/api/projects/research-sessions?" in route.request.url:
            data = response.json()
            for item in data.get("sessions", []):
                item.get("outcome", {}).pop("summary", None)
            route.fulfill(response=response, json=data)
        elif chatgpt_connection["enabled"] and "/api/ai/connection" in route.request.url:
            data = response.json()
            data.update(
                mode="chatgpt", active_account="fixture-account", account_label="Fixture account"
            )
            route.fulfill(response=response, json=data)
        else:
            route.fulfill(response=response)

    page.route("**/api/**", forward)

    def text_baseline(locator):
        return locator.evaluate(
            """e => {
          const s=getComputedStyle(e), r=e.getBoundingClientRect(), c=document.createElement('canvas').getContext('2d');
          const size=parseFloat(s.fontSize), line=s.lineHeight==='normal' ? size*1.2 : parseFloat(s.lineHeight);
          c.font=`${s.fontSize} ${s.fontFamily}`;
          const m=c.measureText((e.value || e.textContent || 'Ag').trim() || 'Ag');
          return r.top + parseFloat(s.borderTopWidth) + parseFloat(s.paddingTop) + (line-size)/2 + m.actualBoundingBoxAscent;
        }"""
        )

    page.goto("http://127.0.0.1:5173")
    home_credit = page.locator(".home-art-credit")
    expect(home_credit.locator("span")).to_have_text("By Brian Kramer, ChatGPT & Codex")
    expect(home_credit.locator("time")).to_have_text("October 2026")
    credit_box = home_credit.bounding_box()
    assert credit_box and credit_box["x"] + credit_box["width"] <= 1440
    assert credit_box["y"] + credit_box["height"] <= 900
    assert home_credit.evaluate("e => getComputedStyle(e).userSelect") == "none"
    page.screenshot(path="/tmp/sigma-a1771-home-credit.png")
    page.get_by_role("tab", name="Samples", exact=True).click()
    page.get_by_role("tabpanel", name="Samples", exact=True).get_by_role(
        "button", name="Open Counting Constrained Binary Strings"
    ).click()
    page.wait_for_url("**/project?*")
    expect(page.get_by_role("heading", name="Project")).to_be_visible()
    expect(page.get_by_role("button", name="Back to home", exact=True)).to_be_visible()
    header_title = page.locator(".project-header-title")
    back_row = page.locator(".project-back-row")
    title_box = header_title.bounding_box()
    back_box = back_row.bounding_box()
    assert title_box and back_box and back_box["y"] >= title_box["y"] + title_box["height"]
    back_button_box = page.get_by_role("button", name="Back to home", exact=True).bounding_box()
    back_caption = page.get_by_role("button", name="Back to home caption", exact=True)
    expect(back_caption).to_be_visible()
    expect(back_caption).to_have_css("text-decoration-line", "underline")
    back_label_box = back_caption.bounding_box()
    assert back_button_box and back_label_box
    assert (
        abs(
            (back_button_box["y"] + back_button_box["height"] / 2)
            - (back_label_box["y"] + back_label_box["height"] / 2)
        )
        < 2
    )
    back_caption.hover()
    expect(page.get_by_role("tooltip")).to_have_text("Back to home caption")
    back_caption.click()
    page.wait_for_url("http://127.0.0.1:5173/")
    expect(page.get_by_role("tooltip")).to_have_count(0)
    page.get_by_role("tab", name="Samples", exact=True).click()
    page.get_by_role("tabpanel", name="Samples", exact=True).get_by_role(
        "button", name="Open Counting Constrained Binary Strings"
    ).click()
    page.wait_for_url("**/project?*")
    untitled_controls = page.locator(
        ".project-pane button:not([data-tooltip-disabled]), .strategies-pane button:not([data-tooltip-disabled]), .sessions-pane button:not([data-tooltip-disabled])"
    ).evaluate_all(
        "buttons => buttons.filter(button => !button.disabled && !button.title.trim()).map(button => `${button.textContent.trim()} [${button.getAttribute('aria-label') || button.className}]`)"
    )
    assert not untitled_controls, (
        f"Actionable workspace buttons need native hover titles: {untitled_controls}"
    )
    project_header = page.locator(".project-pane-heading")
    edit_pencil = page.locator(".project-title-pencil")
    project_gear = project_header.get_by_role("button", name="Project settings", exact=True)
    project_gear.hover()
    tooltip = page.get_by_role("tooltip")
    expect(tooltip).to_have_text("Project settings")
    tooltip_box = tooltip.bounding_box()
    assert tooltip_box and tooltip_box["x"] >= 0 and tooltip_box["x"] + tooltip_box["width"] <= 1440
    gear_hover = project_gear.evaluate(
        "element => { const s = getComputedStyle(element); return [s.backgroundImage, s.color, s.borderTopColor, s.boxShadow]; }"
    )
    edit_pencil.hover()
    page.wait_for_timeout(150)
    pencil_hover = edit_pencil.evaluate(
        "element => { const s = getComputedStyle(element); return [s.backgroundImage, s.color, s.borderTopColor, s.boxShadow]; }"
    )
    assert gear_hover == pencil_hover, (gear_hover, pencil_hover)
    expect(edit_pencil).not_to_have_attribute("title", re.compile(".+"))
    expect(edit_pencil).to_have_attribute("data-tooltip-disabled", "true")
    page.get_by_role("tooltip").wait_for(state="hidden")
    page.screenshot(path="/tmp/sigma-a177-after-icon-tooltip.png")
    project_markdown = page.locator("#project-markdown-slot .sigma-render-toggle")
    project_edit_icon = edit_pencil
    markdown_box = project_markdown.bounding_box()
    edit_icon_box = project_edit_icon.bounding_box()
    assert markdown_box and edit_icon_box
    markdown_gap = edit_icon_box["x"] - (markdown_box["x"] + markdown_box["width"])
    assert 5 <= markdown_gap <= 16, markdown_gap
    edit_pencil.focus()
    expect(page.get_by_role("tooltip")).to_have_count(0)
    project_disclosure = project_header.get_by_role("button", name="Project", exact=True)
    project_disclosure.click()
    expect(page.locator("#project-pane-content")).to_be_hidden()
    project_header.get_by_role("button", name="Export project", exact=True).click()
    first_export = page.get_by_role("dialog", name="Export Project")
    expect(first_export).to_be_visible()
    expect(first_export.get_by_role("radio", name="Project Audit")).to_be_checked()
    expect(first_export.get_by_label("Format")).to_be_disabled()
    expect(first_export.get_by_label("Format")).to_have_value("json")
    expect(first_export.get_by_label("Format").locator("option")).to_have_count(1)
    expect(first_export.get_by_label("Open in browser tab")).not_to_be_checked()
    export_title_box = first_export.locator("#export-project-heading").bounding_box()
    export_cancel_box = first_export.get_by_role("button", name="Cancel", exact=True).bounding_box()
    export_download_box = first_export.get_by_role(
        "button", name="Download", exact=True
    ).bounding_box()
    export_field_box = first_export.get_by_label("Filename").bounding_box()
    assert export_title_box and export_cancel_box and export_download_box and export_field_box
    assert 0 <= export_cancel_box["x"] - (export_title_box["x"] + export_title_box["width"]) < 24
    assert (
        abs(
            (export_cancel_box["y"] + export_cancel_box["height"])
            - (export_title_box["y"] + export_title_box["height"])
        )
        < 3
    )
    assert abs(export_download_box["x"] - export_field_box["x"]) < 2
    expect(first_export.get_by_label("Filename")).to_be_focused()
    stem_visible = first_export.get_by_label("Filename").evaluate(
        "e => { const c=document.createElement('canvas').getContext('2d'); const s=getComputedStyle(e); c.font=`${s.fontSize} ${s.fontFamily}`; return c.measureText(e.value).width <= e.clientWidth - 24; }"
    )
    assert stem_visible, "The complete project-derived filename stem must fit beside its extension."
    page.screenshot(path="/tmp/sigma-a177-after-export-desktop.png")
    page.keyboard.press("Escape")
    expect(first_export).to_be_hidden()
    expect(project_header.get_by_role("button", name="Export project", exact=True)).to_be_focused()
    project_header.get_by_role("button", name="Export project", exact=True).click()
    first_export = page.get_by_role("dialog", name="Export Project")
    page.get_by_role("button", name="Cancel", exact=True).click()
    expect(page.locator("#project-pane-content")).to_be_hidden()
    page.evaluate("window.scrollTo(0, 400)")
    page.set_viewport_size({"width": 520, "height": 430})
    page.get_by_role("button", name="Project settings", exact=True).click()
    settings = page.get_by_role("dialog", name="Settings")
    main_box = settings.bounding_box()
    settings_heading = settings.locator("#project-settings-heading").bounding_box()
    save_settings = settings.get_by_role("button", name="Save", exact=True)
    cancel_settings = settings.get_by_role("button", name="Cancel", exact=True)
    save_box = save_settings.bounding_box()
    cancel_box = cancel_settings.bounding_box()
    assert settings_heading and save_box and cancel_box
    assert save_box["x"] >= settings_heading["x"] + settings_heading["width"]
    assert (
        abs(
            (save_box["y"] + save_box["height"])
            - (settings_heading["y"] + settings_heading["height"])
        )
        < 3
    )
    assert (
        abs(
            (cancel_box["y"] + cancel_box["height"])
            - (settings_heading["y"] + settings_heading["height"])
        )
        < 3
    )
    expect(settings.locator(".settings-footer")).to_have_count(0)
    expect(settings.get_by_role("tab", name="Main")).to_have_attribute("aria-selected", "true")
    settings.get_by_role("tab", name="Limits").focus()
    page.keyboard.press("ArrowRight")
    expect(settings.get_by_role("tab", name="Limits")).to_have_attribute("aria-selected", "true")
    expect(settings.get_by_role("tabpanel", name="Limits")).to_be_visible()
    expect(settings.get_by_label("Research rounds")).to_have_value("3")
    expect(settings.get_by_label("Model calls")).to_have_value("6")
    page.screenshot(path="/tmp/sigma-a177-after-settings-short-desktop.png")
    locked_scroll = page.evaluate("window.scrollY")
    rounds_input = settings.get_by_label("Research rounds")
    assert rounds_input.evaluate("element => getComputedStyle(element).appearance") == "textfield"
    rounds_input.fill("4")
    expect(
        settings.get_by_role("alert").filter(has_text="two model calls per round")
    ).to_be_visible()
    expect(save_settings).to_be_disabled()
    rounds_input.fill("0")
    expect(
        settings.get_by_role("alert").filter(has_text="whole number from 1 to 10")
    ).to_be_visible()
    rounds_input.fill("3")
    limits_panel = settings.locator("#settings-panel-limits")
    limits_panel_box = limits_panel.bounding_box()
    assert limits_panel_box
    page.mouse.move(
        limits_panel_box["x"] + limits_panel_box["width"] / 2,
        limits_panel_box["y"] + limits_panel_box["height"] / 2,
    )
    page.mouse.wheel(0, 1500)
    page.wait_for_timeout(100)
    assert page.evaluate("window.scrollY") == locked_scroll
    assert limits_panel.evaluate("e => e.scrollTop") > 0
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
    page.set_viewport_size({"width": 390, "height": 420})
    limits_panel_box = limits_panel.bounding_box()
    assert limits_panel_box
    page.mouse.move(
        limits_panel_box["x"] + limits_panel_box["width"] / 2,
        limits_panel_box["y"] + limits_panel_box["height"] / 2,
    )
    page.mouse.wheel(0, 1500)
    page.wait_for_timeout(100)
    assert page.evaluate("window.scrollY") == locked_scroll
    page.screenshot(path="/tmp/sigma-a177-after-settings-mobile.png")
    mobile_settings_box = settings.bounding_box()
    assert (
        mobile_settings_box
        and mobile_settings_box["x"] >= 0
        and mobile_settings_box["x"] + mobile_settings_box["width"] <= 390
    )
    save_box = save_settings.bounding_box()
    assert save_box and save_box["y"] >= 0 and save_box["y"] + save_box["height"] <= 420
    settings.get_by_role("tab", name="Main", exact=True).click()
    page.screenshot(path="/tmp/sigma-a177-after-settings-main-mobile.png")
    settings.get_by_role("button", name="Cancel", exact=True).click()
    assert page.evaluate("getComputedStyle(document.documentElement).overflow") != "hidden"
    page.set_viewport_size({"width": 1440, "height": 900})
    expect(page.locator("#project-pane-content")).to_be_hidden()
    project_disclosure.click()
    expect(page.locator("#project-pane-content")).to_be_visible()
    connection = page.locator(".api-connection")
    connection.locator("summary").click()
    connection_dialog = page.get_by_role("dialog", name="AI connection settings")
    expect(connection_dialog).to_be_visible()
    chatgpt_connection["enabled"] = True
    connection_dialog.get_by_role("button", name="Retry connection").click()
    expect(connection_dialog.locator(".connection-usage-actions")).to_be_visible()
    assert (
        page.locator(".connection-backdrop").evaluate("node => getComputedStyle(node).zIndex")
        == "1199"
    )
    usage_actions = connection_dialog.locator(".connection-usage-actions")
    usage_link_box = usage_actions.get_by_role("link", name="Manage usage").bounding_box()
    disconnect_box = usage_actions.get_by_role("button", name="Disconnect").bounding_box()
    assert usage_link_box and disconnect_box
    assert disconnect_box["x"] - (usage_link_box["x"] + usage_link_box["width"]) >= 10
    connection_dialog.get_by_role("link", name="Manage usage").focus()
    page.keyboard.press("Tab")
    expect(connection_dialog.get_by_role("button", name="Disconnect")).to_be_focused()
    assert (
        connection_dialog.get_by_role("button", name="Disconnect").evaluate(
            "e => getComputedStyle(e).outlineStyle"
        )
        != "none"
    )
    project_title_button = page.get_by_role("button", name=re.compile("Edit project title and description:"))
    box = project_title_button.bounding_box()
    assert box
    page.mouse.click(box["x"] + box["width"] / 2, box["y"] + box["height"] / 2)
    expect(connection_dialog).to_be_hidden()
    chatgpt_connection["enabled"] = False
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
    page.get_by_role("button", name=re.compile("Edit project title and description:")).focus()
    page.keyboard.press("Enter")
    expect(page.locator(".project-title-edit-form")).to_be_visible()
    expect(page.locator(".project-title-pencil")).to_have_count(0)
    project_input_box = page.get_by_label("Project title", exact=True).bounding_box()
    project_save_box = (
        page.locator(".project-title-edit-form").get_by_role("button", name="Save").bounding_box()
    )
    assert project_input_box and project_save_box
    assert (
        page.locator(".project-title-edit-form").evaluate("e => getComputedStyle(e).alignItems")
        == "baseline"
    )
    assert (
        abs(
            text_baseline(page.get_by_label("Project title", exact=True))
            - text_baseline(
                page.locator(".project-title-edit-form").get_by_role("button", name="Save")
            )
        )
        < 3
    )
    page.get_by_label("Project title", exact=True).fill("still editing after outside click")
    page.get_by_role("button", name="Strategies", exact=True).click()
    expect(page.locator(".project-title-edit-form")).to_be_visible()
    expect(page.get_by_label("Project title", exact=True)).to_have_value(
        "still editing after outside click"
    )
    page.locator(".project-title-edit-form").get_by_role(
        "button", name="Cancel", exact=True
    ).click()
    expect(page.locator(".project-pane-title-line .current-project")).to_have_text(
        original_project_title
    )
    page.get_by_role("button", name="Strategies", exact=True).click()
    page.get_by_role("button", name=re.compile("Edit project title and description:")).click()
    page.get_by_label("Project title", exact=True).fill(workspace_title)
    page.get_by_role("button", name="Save", exact=True).click()
    expect(page.locator(".project-pane-title-line .current-project")).to_have_text(workspace_title)
    title_box = page.locator(".project-pane-title-line .current-project").bounding_box()
    markdown_box = page.locator("#project-markdown-slot .sigma-render-toggle").bounding_box()
    pencil_box = page.locator(".project-title-pencil").bounding_box()
    assert title_box and markdown_box and pencil_box
    assert title_box["x"] + title_box["width"] <= markdown_box["x"] < pencil_box["x"]
    expect(page.locator(".project-pane-heading")).not_to_contain_text("For each integer n")
    page.screenshot(path="/tmp/sigma-a174-desktop.png", full_page=True)
    page.reload()
    expect(page.locator(".project-pane-title-line .current-project")).to_have_text(workspace_title)
    page.get_by_role("button", name=re.compile("Edit project title and description:")).click()
    page.get_by_label("Project title", exact=True).fill("   ")
    page.get_by_role("button", name="Save", exact=True).click()
    expect(page.get_by_role("alert")).to_have_text("Enter a project title.")
    expect(page.locator("#project-pane-title-input")).to_be_visible()
    page.get_by_role("button", name="Cancel", exact=True).click()
    project_before = project_file.read_bytes()
    page.get_by_role("button", name=re.compile("Edit project title and description:")).click()
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
    expect(page.get_by_role("button", name=re.compile("Edit project title and description:")).first).to_be_disabled()
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
    strategy_header = page.locator(".strategies-pane > .workspace-pane-heading")
    page.get_by_role("button", name="Strategies", exact=True).click()
    expect(page.locator("#strategies-pane-content")).to_be_hidden()
    expect(strategy_header).to_have_css("border-bottom-width", "1px")
    page.locator(".strategy-heading-actions button:first-child").evaluate(
        "button => { button.click(); button.parentElement.querySelectorAll('button')[1].click(); }"
    )
    expect(page.locator("#strategy-composer form.strategy-form")).to_have_count(1)
    expect(page.locator(".inline-proposal")).to_have_count(0)
    expect(page.locator("#strategies-pane-content")).to_be_visible()
    expect(strategy_header).to_have_css("border-bottom-width", "0px")
    new_form = page.locator("#strategy-composer form.strategy-form")
    expect(page.locator("#strategy-title")).to_be_focused()
    expect(page.get_by_role("button", name="Generate", exact=True)).to_be_disabled()
    expect(page.get_by_role("button", name=re.compile("Edit project title and description:")).first).to_be_disabled()
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
    expect(page.get_by_role("button", name=re.compile("Edit project title and description:")).first).to_be_enabled()
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
    expect(first_row.get_by_role("menu")).to_have_count(0)
    expect(first_row.get_by_role("button", name="More actions", exact=False)).to_have_count(0)
    expect(first_row.get_by_role("button", name="Fork", exact=True)).to_have_attribute(
        "title", "Fork strategy"
    )
    expect(first_row.get_by_role("button", name="Remove", exact=True)).to_have_attribute(
        "title", "Remove strategy"
    )
    assert page.locator(".strategy-columns span").all_text_contents() == ["Strategy"]
    expect(first_row).not_to_contain_text("Change stage")
    title_bounds = first_row.locator(".strategy-title-line h3").bounding_box()
    grip_bounds = first_row.locator(".drag-grip").bounding_box()
    assert title_bounds and grip_bounds and grip_bounds["x"] < title_bounds["x"]
    page.get_by_role(
        "button", name="Edit strategy title: Saved research approach", exact=True
    ).click()
    expect(first_row.locator(".strategy-title-pencil")).to_have_count(0)
    expect(first_row.locator(".strategy-rename-form")).to_be_visible()
    expect(first_row.locator(".strategy-expanded")).to_be_visible()
    strategy_input_box = first_row.locator(".strategy-rename-form input").bounding_box()
    strategy_save_box = (
        first_row.locator(".strategy-rename-form").get_by_role("button", name="Save").bounding_box()
    )
    strategy_cancel_box = (
        first_row.locator(".strategy-rename-form")
        .get_by_role("button", name="Cancel")
        .bounding_box()
    )
    assert strategy_input_box and strategy_save_box and strategy_cancel_box
    assert (
        first_row.locator(".strategy-rename-form").evaluate("e => getComputedStyle(e).alignItems")
        == "baseline"
    )
    assert (
        abs(
            text_baseline(first_row.locator(".strategy-rename-form input"))
            - text_baseline(
                first_row.locator(".strategy-rename-form").get_by_role("button", name="Save")
            )
        )
        < 3
    )
    assert (
        abs(
            text_baseline(first_row.locator(".strategy-rename-form input"))
            - text_baseline(
                first_row.locator(".strategy-rename-form").get_by_role("button", name="Cancel")
            )
        )
        < 3
    )
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
    play = page.get_by_role("button", name="Start a new research session", exact=True)
    expect(play).to_be_enabled()
    play.click()
    start_first = page.get_by_role("button", name="Start new session #1", exact=True)
    expect(start_first).to_be_visible()
    expect(page.get_by_role("button", name="Cancel", exact=True)).to_have_attribute(
        "title", "Cancel starting a research session"
    )
    start_first.dblclick(delay=5)
    first_session = research.locator("li[data-session-id]")
    expect(first_session).to_have_count(1, timeout=15000)
    expect(first_session.locator(".session-row-title")).to_have_text("Session #1")
    expect(first_session.locator(".session-status")).to_have_text("ended")
    page.wait_for_function(
        """id => { const row = document.querySelector(`[data-session-id="${CSS.escape(id)}"]`); if (!row) return false; const rect = row.getBoundingClientRect(); return rect.top < innerHeight && rect.bottom > 0; }""",
        arg=first_session.get_attribute("data-session-id"),
    )
    expect(research.locator(".section-count")).to_have_text("1 session, 0 running")
    expect(page.locator(".api-connection .connection-dot")).not_to_have_class(
        re.compile("connection-active")
    )
    expect(first_session.locator(".session-outcome-inline")).to_contain_text("Mixed")
    expect(first_session.locator(".session-status-row")).to_have_count(0)
    expect(first_session.locator(".session-row-content .session-status")).to_have_count(0)
    title_rect = first_session.locator(".session-row-title").evaluate(
        "e => e.getBoundingClientRect().left"
    )
    for summary_selector in (
        ".session-status",
        ".session-outcome-inline",
        ".session-progress-inline",
    ):
        summary_rect = first_session.locator(summary_selector).evaluate(
            "e => e.getBoundingClientRect().left"
        )
        assert abs(summary_rect - title_rect) < 1.5, (summary_selector, title_rect, summary_rect)
    page.screenshot(path="/tmp/sigma-a177-after-session-card.png")
    expect(research).to_contain_text("Cycle 3 of 3")
    expect(research).to_contain_text("6/6 calls")
    expect(first_session.locator(".session-status")).to_have_text("ended")
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
    page.get_by_role("button", name="Start a new research session", exact=True).click()
    page.get_by_role("button", name="Start new session #2", exact=True).click()
    pause_row = research.locator("li[data-session-id]").filter(has_text="Session #2")
    expect(pause_row.locator(".session-status")).to_contain_text("running", timeout=10000)
    expect(pause_row.locator(".session-row-content")).to_be_visible()
    page.get_by_role("button", name="Sessions", exact=True).click()
    expect(page.locator("#sessions-pane-content")).to_be_hidden()
    expect(research.locator(":scope > .workspace-pane-heading")).to_have_css(
        "border-bottom-width", "1px"
    )
    expect(research.locator(".section-count")).to_contain_text("1 running")
    page.get_by_role("button", name="Sessions", exact=True).click()
    expect(research.locator(":scope > .workspace-pane-heading")).to_have_css(
        "border-bottom-width", "0px"
    )
    expect(pause_row.locator(".session-status")).to_contain_text("running")
    dot = page.locator(".api-connection .connection-dot")
    expect(dot).to_have_class(re.compile("connection-active"), timeout=10000)
    page.emulate_media(reduced_motion="reduce")
    expect(dot).to_have_css("animation-name", "none")
    expect(dot).to_have_css("background-color", "rgb(117, 177, 140)")
    page.emulate_media(reduced_motion="no-preference")
    expect(dot).to_have_css("animation-name", "connection-dot-pulse")
    page.get_by_role("button", name="Stop research session", exact=True).click()
    expect(pause_row.locator(".session-status")).to_contain_text("stopped", timeout=5000)
    expect(pause_row.get_by_role("button", name="Remove", exact=True)).to_be_visible()
    pause_row.get_by_role("button", name="Resume", exact=True).click()
    expect(pause_row.locator(".session-status")).to_contain_text(re.compile("queued|running"), timeout=5000)
    expect(page.get_by_role("group", name="Confirm resume Session 2")).to_have_count(0)
    pause_row.get_by_role("button", name="Stop", exact=True).click()
    expect(pause_row.locator(".session-status")).to_contain_text("stopped", timeout=5000)
    expect(pause_row.get_by_role("button", name="Remove", exact=True)).to_be_visible()
    page.set_viewport_size({"width": 390, "height": 844})
    actions_box = pause_row.locator(".session-heading-actions")
    resume_box = actions_box.get_by_role("button", name="Resume", exact=True).bounding_box()
    remove_box = actions_box.get_by_role("button", name="Remove", exact=True).bounding_box()
    assert resume_box and remove_box and resume_box["y"] < remove_box["y"]
    assert (
        abs((resume_box["x"] + resume_box["width"]) - (remove_box["x"] + remove_box["width"])) < 2
    )
    actions_box.get_by_role("button", name="Resume", exact=True).hover()
    expect(page.get_by_role("tooltip")).to_have_text("Resume Session 2")
    pause_row.locator(".session-row-heading").screenshot(
        path="/tmp/sigma-a177-after-session-stopped-actions-mobile.png"
    )
    page.set_viewport_size({"width": 1440, "height": 900})

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
    page.get_by_role("button", name="Start a new research session", exact=True).click()
    page.get_by_role("button", name="Start new session #3", exact=True).click()
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
    outcome_toggle = first_session.get_by_role("button", name="Render outcome as Markdown")
    conversion_count = len(provider_calls)
    outcome_toggle.click()
    expect(first_session.get_by_role("button", name="Show plain outcome text")).to_have_attribute(
        "aria-pressed", "true"
    )
    assert len(provider_calls) == conversion_count
    first_session.get_by_role("button", name="Show plain outcome text").click()
    expect(
        first_session.get_by_role("button", name="Render outcome as Markdown")
    ).to_have_attribute("aria-pressed", "false")
    artifact_section = first_session.get_by_label("Research artifacts")
    artifact_markdown_toggle = artifact_section.get_by_role(
        "button", name="Render research artifacts as Markdown"
    )
    artifact_markdown_toggle.click()
    expect(
        artifact_section.get_by_role("button", name="Show plain research artifacts")
    ).to_have_attribute("aria-pressed", "true")
    expect(artifact_section.locator(".research-artifact-markdown")).to_have_count(3)
    for cycle in range(1, 4):
        expect(artifact_section).to_contain_text(f"Cycle {cycle}:")
    artifact_section.get_by_role("button", name="Show plain research artifacts").click()
    expect(artifact_section.locator(":scope > ol > li > details")).to_have_count(3)
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
    session_row_box = stopped_session.bounding_box()
    stopped_session.get_by_role("button", name="Remove", exact=True).click()
    confirm_remove = stopped_session.get_by_role("group", name="Confirm remove Session 2")
    expect(confirm_remove.get_by_role("button", name="Confirm", exact=True)).to_have_css(
        "text-decoration-line", "underline"
    )
    expect(confirm_remove.get_by_role("button", name="Cancel", exact=True)).to_have_css(
        "text-decoration-line", "underline"
    )
    confirm_box = stopped_session.bounding_box()
    assert session_row_box and confirm_box
    assert abs(confirm_box["height"] - session_row_box["height"]) < 1
    assert confirm_box["width"] == session_row_box["width"]
    page.screenshot(path="/tmp/sigma-a1771-remove-session-confirm.png")
    confirm_remove.get_by_role("button", name="Cancel", exact=True).click()
    expect(stopped_session.get_by_role("group", name="Confirm remove Session 2")).to_have_count(0)
    cancelled_box = stopped_session.bounding_box()
    assert cancelled_box and abs(cancelled_box["height"] - session_row_box["height"]) < 1
    stopped_session.get_by_role("button", name="Remove", exact=True).click()
    confirm_remove = stopped_session.get_by_role("group", name="Confirm remove Session 2")
    confirm_remove.get_by_role("button", name="Confirm", exact=True).click()
    expect(research.locator("li[data-session-id]")).to_have_count(2)
    remaining = page.evaluate(
        "async path => (await (await fetch('/api/projects/research-sessions?' + new URLSearchParams({path}))).json()).sessions.map(session => session.session_number)",
        path,
    )
    assert sorted(remaining) == [1, 3], remaining
    page.get_by_role("button", name="Project", exact=True).click()
    expect(page.locator("#project-pane-content")).to_be_hidden()
    page.get_by_role("button", name="Export project", exact=True).click()
    export_dialog = page.get_by_role("dialog", name="Export Project")
    expect(export_dialog).to_be_visible()
    filename_field = export_dialog.get_by_label("Filename")
    filename_field.fill("")
    export_dialog.get_by_role("button", name="Download", exact=True).click()
    expect(export_dialog.get_by_role("alert")).to_have_text(
        "Enter a filename stem without path separators or reserved characters."
    )
    filename_field.fill("a17-audit.json")
    expect(filename_field).to_have_value("a17-audit")
    fail_export["enabled"] = True
    export_dialog.get_by_role("button", name="Download", exact=True).click()
    expect(export_dialog.get_by_role("alert")).to_have_text("fixture export failure")
    expect(export_dialog).to_be_visible()
    fail_export["enabled"] = False
    with page.expect_download() as download_info:
        export_dialog.get_by_role("button", name="Download", exact=True).click()
    export_data = json.loads(Path(download_info.value.path()).read_text(encoding="utf-8"))
    assert download_info.value.suggested_filename == "a17-audit.json"
    assert export_data["export_version"] == 2
    assert [session["session_number"] for session in export_data["research_sessions"]] == [1, 3]
    assert export_data["research_sessions"][0]["artifacts"]
    assert export_data["research_sessions"][0]["outcome"]["assessment"] == "mixed"
    assert "fixture-token" not in json.dumps(export_data)
    for toast in page.locator(".request-toast").all():
        dismiss = toast.get_by_role("button", name="Dismiss request error")
        if dismiss.is_visible():
            dismiss.click()
    expect(export_dialog).to_be_hidden()
    expect(page.locator("#project-pane-content")).to_be_hidden()

    page.get_by_role("button", name="Export project", exact=True).click()
    export_dialog = page.get_by_role("dialog", name="Export Project")
    filename_field = export_dialog.get_by_label("Filename")
    filename_field.fill("a17 unsafe/report.html")
    expect(filename_field).to_have_value("a17 unsafe-report")
    export_dialog.get_by_role("radio", name="Research Report").check()
    format_select = export_dialog.get_by_label("Format")
    expect(format_select).to_be_enabled()
    expect(format_select).to_have_value("txt")
    expect(filename_field).to_have_value("a17 unsafe-report")
    expect(export_dialog.locator(".export-filename-field span")).to_have_text(".txt")
    format_select.select_option("html")
    expect(filename_field).to_have_value("a17 unsafe-report")
    expect(export_dialog.locator(".export-filename-field span")).to_have_text(".html")
    export_dialog.get_by_role("radio", name="Project Audit").check()
    expect(format_select).to_be_disabled()
    expect(format_select).to_have_value("json")
    expect(format_select.locator("option")).to_have_count(1)
    expect(filename_field).to_have_value("a17 unsafe-report")
    expect(export_dialog.locator(".export-filename-field span")).to_have_text(".json")
    export_dialog.get_by_role("radio", name="Research Report").check()
    expect(format_select).to_be_enabled()
    expect(format_select).to_have_value("html")
    expect(export_dialog.locator(".export-filename-field span")).to_have_text(".html")
    format_select.select_option("txt")
    expect(export_dialog.get_by_label("Open in browser tab")).not_to_be_checked()
    with page.expect_download() as report_download:
        export_dialog.get_by_role("button", name="Download", exact=True).click()
    assert report_download.value.suggested_filename == "a17 unsafe-report.txt"
    text_report = Path(report_download.value.path()).read_text(encoding="utf-8")
    assert "Research sessions" in text_report and "Session #1" in text_report
    expect(export_dialog).to_be_hidden()

    page.get_by_role("button", name="Export project", exact=True).click()
    export_dialog = page.get_by_role("dialog", name="Export Project")
    export_dialog.get_by_role("radio", name="Research Report").check()
    export_dialog.get_by_label("Filename").fill("a17-html")
    export_dialog.get_by_label("Format").select_option("html")
    export_dialog.get_by_label("Open in browser tab").check()
    with page.expect_popup() as report_tab, page.expect_download() as html_download:
        export_dialog.get_by_role("button", name="Download", exact=True).click()
    popup = report_tab.value
    popup.wait_for_load_state("domcontentloaded")
    assert "a17-html.html" == html_download.value.suggested_filename
    html_report = Path(html_download.value.path()).read_text(encoding="utf-8")
    assert "<!doctype html>" in html_report.lower() and "Research Report" in html_report
    expect(popup.locator("h1")).to_be_visible()
    expect(popup.locator("h2", has_text="Research sessions")).to_be_visible()
    assert popup.locator("pre").count() == 0
    popup.emulate_media(media="print")
    assert popup.locator("body").evaluate("e => getComputedStyle(e).maxWidth") == "none"
    popup.emulate_media(media="screen")
    popup.set_viewport_size({"width": 390, "height": 844})
    assert popup.evaluate("document.documentElement.scrollWidth <= innerWidth")
    popup.screenshot(path="/tmp/sigma-a1771-after-report-html-mobile.png", full_page=True)
    popup.close()
    expect(export_dialog).to_be_hidden()

    page.get_by_role("button", name="Export project", exact=True).click()
    export_dialog = page.get_by_role("dialog", name="Export Project")
    export_dialog.get_by_role("radio", name="Research Report").check()
    expect(export_dialog.get_by_label("Format").locator("option")).to_have_text(
        ["Text", "HTML", "LaTeX"]
    )
    expect(export_dialog.locator(".export-filename-field span")).to_have_text(".txt")
    export_dialog.get_by_label("Filename").fill("a17-blocked-tab")
    export_dialog.get_by_label("Open in browser tab").check()
    page.evaluate("() => { window.__originalOpen = window.open; window.open = () => null; }")
    with page.expect_download() as blocked_download:
        export_dialog.get_by_role("button", name="Download", exact=True).click()
    page.evaluate("() => { window.open = window.__originalOpen; delete window.__originalOpen; }")
    assert blocked_download.value.suggested_filename == "a17-blocked-tab.txt"
    expect(export_dialog).to_be_visible()
    expect(export_dialog.get_by_role("alert")).to_have_text(
        "The browser blocked or closed the new tab. The file was still downloaded."
    )
    export_dialog.get_by_role("button", name="Cancel", exact=True).click()

    page.get_by_role("button", name="Export project", exact=True).click()
    export_dialog = page.get_by_role("dialog", name="Export Project")
    export_dialog.get_by_role("radio", name="Project Audit").check()
    expect(export_dialog.get_by_label("Format")).to_have_value("json")
    expect(export_dialog.get_by_label("Format").locator("option")).to_have_text("JSON")
    expect(export_dialog.locator(".export-filename-field span")).to_have_text(".json")
    export_dialog.get_by_role("radio", name="Research Report").check()
    export_dialog.get_by_label("Filename").fill("a17-latex")
    export_dialog.get_by_label("Format").select_option("pdf")
    expect(export_dialog.locator(".export-filename-field span")).to_have_text(".pdf")
    export_dialog.get_by_label("Open in browser tab").check()
    with page.expect_popup() as pdf_tab, page.expect_download() as pdf_download:
        export_dialog.get_by_role("button", name="Download", exact=True).click()
    pdf_popup = pdf_tab.value
    pdf_popup.wait_for_url(re.compile(r"^(blob:|chrome-extension:|file:)"), timeout=10000)
    pdf_bytes = Path(pdf_download.value.path()).read_bytes()
    assert pdf_download.value.suggested_filename == "a17-latex.pdf"
    assert pdf_bytes.startswith(b"%PDF-") and len(pdf_bytes) > 1000
    assert pdf_popup.url.startswith("blob:") or "pdf" in pdf_popup.url.lower(), pdf_popup.url
    pdf_popup.screenshot(path="/tmp/sigma-a1771-after-pdf-preview.png")
    pdf_popup.close()
    expect(export_dialog).to_be_hidden()
    page.set_viewport_size({"width": 390, "height": 844})
    assert page.evaluate("document.documentElement.scrollWidth <= window.innerWidth")
    assert (
        page.locator(".strategies-heading-right").evaluate(
            "node => getComputedStyle(node).marginLeft"
        )
        == "0px"
    )
    expect(page.get_by_role("button", name="Back to home", exact=True)).to_be_visible()
    page.get_by_role("button", name="Export project", exact=True).click()
    mobile_export = page.get_by_role("dialog", name="Export Project")
    mobile_box = mobile_export.bounding_box()
    assert mobile_box and mobile_box["x"] >= 0 and mobile_box["y"] >= 0
    assert mobile_box["x"] + mobile_box["width"] <= 390
    assert mobile_box["y"] + mobile_box["height"] <= 844
    mobile_input = mobile_export.get_by_label("Filename")
    mobile_value = mobile_input.input_value()
    assert mobile_value.startswith("sigma-") and len(mobile_value) > 20
    mobile_input.press("End")
    mobile_input.press("Home")
    assert mobile_input.evaluate("e => e.scrollLeft === 0")
    page.screenshot(path="/tmp/sigma-a177-after-export-mobile.png")
    page.keyboard.press("Escape")
    expect(mobile_export).to_be_hidden()
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
    page.set_viewport_size({"width": 1440, "height": 900})
    page.get_by_role("button", name="Back to home", exact=True).click()
    page.wait_for_url("http://127.0.0.1:5173/")
    page.get_by_role("tab", name="Samples", exact=True).click()
    page.get_by_role("tabpanel", name="Samples", exact=True).get_by_role(
        "button", name="Open Maximum Regions Formed by Lines"
    ).click()
    page.wait_for_url("**/project?*")
    max_regions_path = page.evaluate("new URL(location.href).searchParams.get('path')")
    max_regions_strategy = page.locator("li[data-strategy-id]").first
    max_regions_strategy.locator(".strategy-row-disclosure").click()
    page.get_by_role("button", name="Start a new research session", exact=True).click()
    page.get_by_role("button", name="Start new session #1", exact=True).click()
    max_session = page.locator("li[data-session-id]").first
    expect(max_session.locator(".session-status")).to_have_text("ended", timeout=15000)
    expect(max_session.locator(".session-outcome-inline")).to_contain_text(
        "Positive · solution candidate (unverified)"
    )
    expect(max_session.locator(".strategy-assessments")).to_contain_text("Contributed to solution")
    expect(max_session.locator(".strategy-assessments")).to_contain_text("Artifact 1")
    expect(max_session.locator(".solution-review")).to_contain_text("R(n) = 1 + n(n+1)/2")
    page.mouse.move(1435, 895)
    page.wait_for_timeout(150)
    page.screenshot(path="/tmp/sigma-a177-after-maximum-regions.png", full_page=True)
    max_session.screenshot(path="/tmp/sigma-a177-after-session-card.png")
    page.reload()
    max_session = page.locator("li[data-session-id]").first
    expect(max_session.locator(".strategy-assessments")).to_contain_text("Contributed to solution")
    expect(max_session.locator(".session-outcome")).to_contain_text("no formal proof checker")
    max_math_toggle = max_session.get_by_role("button", name="Render outcome as Markdown")
    calls_before_math_toggle = len(provider_calls)
    max_math_toggle.focus()
    expect(page.get_by_role("tooltip")).to_have_text("Render outcome as Markdown")
    max_math_toggle.click()
    expect(max_session.get_by_role("button", name="Show plain outcome text")).to_have_attribute(
        "aria-pressed", "true"
    )
    markdown_outcome = max_session.locator(".outcome-markdown")
    expect(markdown_outcome.locator(".katex").first).to_be_visible()
    for label in (
        "Solution claim:",
        "Argument:",
        "Assumptions:",
        "Proof obligations:",
        "Evidence:",
        "Verification:",
        "Caveats",
    ):
        expect(markdown_outcome).to_contain_text(label)
    expect(max_session.locator(".outcome-content")).to_have_count(0)
    assert len(provider_calls) == calls_before_math_toggle
    max_session.get_by_role("button", name="Show plain outcome text").click()
    expect(max_session.locator(".outcome-content .solution-review")).to_contain_text(
        "Solution claim:"
    )
    expect(max_session.locator(".outcome-markdown")).to_have_count(0)
    maximum_strategy = page.locator("li[data-strategy-id]").first
    maximum_strategy.get_by_role("button", name="Disable", exact=True).click()
    expect(maximum_strategy.locator(".strategy-disabled-label")).to_have_text("Disabled")
    expect(page.get_by_role("button", name="Start a new research session")).to_be_disabled()
    expect(max_session.locator(".strategy-assessments")).to_contain_text("Contributed to solution")
    page.reload()
    maximum_strategy = page.locator("li[data-strategy-id]").first
    expect(maximum_strategy.locator(".strategy-disabled-label")).to_have_text("Disabled")
    maximum_strategy.get_by_role("button", name="Enable", exact=True).click()
    expect(maximum_strategy.locator(".strategy-disabled-label")).to_have_count(0)
    expect(page.get_by_role("button", name="Start a new research session")).to_be_enabled()
    expect(
        page.locator("li[data-session-id]").first.locator(".strategy-assessments")
    ).to_contain_text("Contributed to solution")
    max_record = page.evaluate(
        "async path => (await (await fetch('/api/projects/research-sessions?' + new URLSearchParams({path}))).json()).sessions[0]",
        max_regions_path,
    )
    assert max_record["terminal_reason"] == "stop_productive_conclusion", max_record[
        "terminal_reason"
    ]
    assert max_record["artifacts"][-1]["next_question"] == ""
    assert max_record["outcome"]["assessment"] == "positive"
    assert (
        max_record["outcome"]["solution_review"]["verification_status"] == "convincing_unverified"
    )
    audit = page.evaluate(
        "async path => await (await fetch('/api/projects/export?' + new URLSearchParams({path}))).json()",
        max_regions_path,
    )
    exported_max = audit["research_sessions"][0]
    assert exported_max["outcome"]["assessment"] == "positive"
    assert exported_max["strategy_assessments"][0]["assessment"] == "contributed_to_solution"
    assert exported_max["strategy_assessments"][0]["basis_artifact_ids"] == [
        max_record["artifacts"][0]["id"]
    ]
    report = page.evaluate(
        "async path => await (await fetch('/api/projects/export/report?' + new URLSearchParams({path,format:'txt'}))).text()",
        max_regions_path,
    )
    assert (
        "Positive" in report
        and "Contributed to solution" in report
        and "unverified" in report.lower()
    )
    page.get_by_role("button", name="Export project", exact=True).click()
    max_export = page.get_by_role("dialog", name="Export Project")
    max_export.get_by_role("radio", name="Research Report").check()
    max_format = max_export.get_by_label("Format")
    max_filename = max_export.get_by_label("Filename")
    max_report_title = page.locator(".project-header-title").inner_text()
    max_filename_stem = "sigma-" + re.sub(
        r"[^a-z0-9_-]+", "-", max_report_title, flags=re.IGNORECASE
    ).strip("-")
    expect(max_filename).to_have_value(max_filename_stem)
    assert max_filename.evaluate("e => e.clientWidth") > 300
    max_filename.press("End")
    assert max_filename.evaluate("e => e.scrollLeft > 0") is False
    max_format.select_option("html")
    expect(max_export.locator(".export-filename-field span")).to_have_text(".html")
    max_export.get_by_label("Open in browser tab").check()
    with page.expect_popup() as max_html_tab, page.expect_download() as max_html_download:
        max_export.get_by_role("button", name="Download", exact=True).click()
    html_popup = max_html_tab.value
    html_popup.wait_for_load_state("domcontentloaded")
    html_text = Path(max_html_download.value.path()).read_text(encoding="utf-8")
    assert max_html_download.value.suggested_filename == f"{max_filename_stem}.html"
    assert f"<h1>{max_report_title}</h1>" in html_text
    assert "<h2>Research sessions</h2>" in html_text and "<math" in html_text
    assert "<script>" not in html_text and "<pre>" not in html_text
    expect(html_popup.locator("h1")).to_have_text(max_report_title)
    expect(html_popup.locator("math.report-math").first).to_be_visible()
    html_popup.screenshot(path="/tmp/sigma-a1771-after-maximum-regions-html.png", full_page=True)
    html_popup.set_viewport_size({"width": 390, "height": 844})
    assert html_popup.evaluate("document.documentElement.scrollWidth <= innerWidth")
    html_popup.emulate_media(media="print")
    assert html_popup.locator("body").evaluate("e => getComputedStyle(e).maxWidth") == "none"
    html_popup.emulate_media(media="screen")
    html_popup.close()

    page.get_by_role("button", name="Export project", exact=True).click()
    max_export = page.get_by_role("dialog", name="Export Project")
    max_export.get_by_role("radio", name="Research Report").check()
    max_filename = max_export.get_by_label("Filename")
    expect(max_filename).to_have_value(max_filename_stem)
    max_format = max_export.get_by_label("Format")
    max_format.select_option("pdf")
    expect(max_export.locator(".export-filename-field span")).to_have_text(".pdf")
    max_export.get_by_label("Open in browser tab").check()
    with page.expect_popup() as max_pdf_tab, page.expect_download() as max_pdf_download:
        max_export.get_by_role("button", name="Download", exact=True).click()
    max_pdf_popup = max_pdf_tab.value
    max_pdf_popup.wait_for_url(re.compile(r"^(blob:|chrome-extension:|file:)"), timeout=10000)
    maximum_pdf = Path(max_pdf_download.value.path()).read_bytes()
    assert max_pdf_download.value.suggested_filename == f"{max_filename_stem}.pdf"
    assert maximum_pdf.startswith(b"%PDF-") and 1000 < len(maximum_pdf) < 20_000_000
    assert max_pdf_popup.url.startswith("blob:")
    max_pdf_popup.screenshot(path="/tmp/sigma-a1771-after-maximum-regions-pdf.png")
    max_pdf_popup.close()
    expect(max_export).to_be_hidden()

    page.set_viewport_size({"width": 390, "height": 420})
    page.get_by_role("button", name="Export project", exact=True).click()
    narrow_export = page.get_by_role("dialog", name="Export Project")
    narrow_title = narrow_export.locator("#export-project-heading").bounding_box()
    narrow_cancel = narrow_export.get_by_role("button", name="Cancel", exact=True).bounding_box()
    narrow_download = narrow_export.get_by_role(
        "button", name="Download", exact=True
    ).bounding_box()
    narrow_filename = narrow_export.get_by_label("Filename")
    assert narrow_title and narrow_cancel and narrow_download
    assert 0 <= narrow_cancel["x"] - (narrow_title["x"] + narrow_title["width"]) < 24
    assert abs(narrow_download["x"] - narrow_filename.bounding_box()["x"]) < 2
    narrow_filename.fill("sigma-Maximum-Regions-Formed-by-Lines-" + "Maximum-Regions-" * 4)
    narrow_filename.press("End")
    assert narrow_filename.evaluate("e => e.scrollLeft > 0")
    expect(narrow_export.locator(".export-filename-field span")).to_have_text(".json")
    page.screenshot(path="/tmp/sigma-a1771-after-maximum-regions-export-mobile.png")
    page.keyboard.press("Escape")
    expect(narrow_export).to_be_hidden()

    legacy_outcome["enabled"] = True
    page.reload()
    max_session = page.locator("li[data-session-id]").first
    session_disclosure = max_session.get_by_role("button", name=re.compile("Session #1"))
    if session_disclosure.get_attribute("aria-expanded") != "true":
        session_disclosure.click()
    expect(max_session.locator(".session-row-content")).to_be_visible()
    expect(max_session.locator(".outcome-content .outcome-summary-text")).to_contain_text(
        "No outcome summary was recorded."
    )
    max_session.get_by_role("button", name="Render outcome as Markdown").click()
    expect(max_session.locator(".outcome-markdown")).to_contain_text(
        "No outcome summary was recorded."
    )
    expect(max_session.locator(".outcome-markdown")).to_contain_text("Solution claim:")
    max_session.get_by_role("button", name="Show plain outcome text").click()
    expect(max_session.locator(".outcome-content .outcome-summary-text")).to_contain_text(
        "No outcome summary was recorded."
    )
    legacy_outcome["enabled"] = False
    assert not errors, errors
    assert len(starts) == 4, starts
    print(
        "PASS real Chrome A17.7.1: dialogs, title action geometry, outcome Markdown/math, HTML and compiled PDF publication exports, and A17.6 Maximum Regions persistence"
    )
    page.unroute_all(behavior="ignoreErrors")
    browser.close()
