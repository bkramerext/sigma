"""Real Chrome A17 three-pane workspace against the isolated provider fixture."""

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
    expect(
        page.get_by_role(
            "heading", name=re.compile("Project: Counting Constrained Binary Strings - Working")
        )
    ).to_be_visible()
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

    panes = page.locator(".project-pane, .research-workspace, .strategies-pane")
    expect(panes).to_have_count(3)
    assert panes.evaluate_all("nodes => nodes.map(node => node.className)") == [
        "workspace-pane project-pane",
        "research-workspace",
        "pool workspace-pane strategies-pane",
    ]
    page.get_by_role("button", name=re.compile("Edit project title:")).click()
    expect(page.locator("#project-pane-content")).to_be_visible()
    page.get_by_label("Project title", exact=True).fill(workspace_title)
    page.get_by_role("button", name="Save", exact=True).click()
    expect(page.get_by_role("heading", name=f"Project: {workspace_title}")).to_be_visible()
    expect(page.locator(".project-pane-heading")).not_to_contain_text("For each integer n")
    page.screenshot(path="/tmp/sigma-a171-desktop.png", full_page=True)
    page.reload()
    expect(page.get_by_role("heading", name=f"Project: {workspace_title}")).to_be_visible()
    page.get_by_role("button", name=re.compile("Edit project title:")).click()
    page.get_by_label("Project title", exact=True).fill("   ")
    page.get_by_role("button", name="Save", exact=True).click()
    expect(page.get_by_role("alert")).to_have_text("Enter a project title.")
    expect(page.locator("#project-pane-title-input")).to_be_visible()
    page.get_by_role("button", name="Cancel", exact=True).click()
    project_before = project_file.read_bytes()

    # Collapse does not unmount the editor or discard its unsaved draft.
    page.get_by_role("button", name="Edit research problem").click()
    description = page.locator("#text-editor-project-project")
    description.fill("unsaved project description draft")
    page.locator(".project-pane-title-line").get_by_role(
        "button", name=re.compile("^Project:")
    ).click()
    assert description.input_value() == "unsaved project description draft"
    expect(page.locator(".research-workspace")).to_be_visible()
    page.locator(".project-pane-title-line").get_by_role(
        "button", name=re.compile("^Project:")
    ).click()
    page.get_by_role("button", name="Cancel", exact=True).click()

    # The Strategies pane is independently collapsible and keeps its open draft mounted.
    page.locator(".strategies-pane-heading").get_by_role("button", name="New", exact=True).click()
    new_form = page.locator("#strategy-composer form.strategy-form")
    page.locator("#strategy-title").fill("Unfinished strategy draft")
    page.get_by_role("button", name="Strategies", exact=True).click()
    expect(new_form).to_be_attached()
    assert page.locator("#strategy-title").input_value() == "Unfinished strategy draft"
    page.get_by_role("button", name="Strategies", exact=True).click()
    new_form.get_by_role("button", name="Cancel", exact=True).click()

    # Generation title remains explicit through review, acceptance, and rendering.
    page.get_by_role("button", name="Generate", exact=True).click()
    proposal = page.locator(".inline-proposal")
    proposal.get_by_role("button", name="Generate", exact=True).click()
    expect(proposal.get_by_label("Title", exact=True)).to_have_value("Position-shift subset count")
    proposal.get_by_role("button", name="Accept", exact=True).click()
    expect(page.locator(".strategy-row")).to_have_count(2)

    first_strategy_id = result["body"]["project"]["strategies"][0]["id"]
    first_detail = page.locator(
        f"li[data-strategy-id='{first_strategy_id}'] details.strategy-detail"
    )
    first_detail.locator("summary").click()
    assert first_detail.evaluate("details => details.open")
    page.get_by_role(
        "button", name="Edit strategy title: Saved research approach", exact=True
    ).click()
    assert first_detail.evaluate("details => details.open")
    page.locator(f"#strategy-title-{first_strategy_id}").fill("A17.1 saved approach")
    page.locator(f"li[data-strategy-id='{first_strategy_id}']").get_by_role(
        "button", name="Save", exact=True
    ).click()
    expect(page.locator(f"summary#strategy-{first_strategy_id}")).to_contain_text(
        "Strategy: A17.1 saved approach"
    )
    assert first_detail.evaluate("details => details.open")
    project_before = project_file.read_bytes()

    research = page.locator(".research-workspace")
    expect(research.get_by_role("heading", name="Research session")).to_be_visible()
    play = page.get_by_role("button", name="Start research session", exact=True)
    expect(play).to_be_enabled()
    play.click()
    expect(research.locator(".research-consent")).to_contain_text("API key billing")
    expect(research.locator(".research-consent")).to_contain_text(
        "Up to 3 cycles and 6 provider calls"
    )
    expect(research.locator(".research-consent")).to_contain_text("Usage may accrue")
    research.get_by_role("button", name="Confirm and start", exact=True).dblclick(delay=5)
    expect(research.get_by_role("heading", name="Session #1")).to_be_visible(timeout=15000)
    expect(research).to_contain_text("completed")
    expect(research).to_contain_text("Cycle 3 of 3")
    expect(research).to_contain_text("6 of 6 calls used (0 remaining)")
    expect(research).to_contain_text("Completed · budget exhausted")
    artifacts = research.get_by_label("Research artifacts")
    expect(artifacts.locator("li")).to_have_count(3)
    expect(artifacts).to_contain_text("Independent fixture review for cycle 1")
    expect(artifacts).to_contain_text("Unverified research note")
    events = research.get_by_label("Recent session activity")
    expect(events.locator("li").last).to_contain_text("artifact committed")
    research.get_by_role("button", name="View strategy", exact=True).click()
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
    expect(
        page.locator(".research-workspace").get_by_role("heading", name="Session #1")
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
    research = page.locator(".research-workspace")
    page.get_by_role("button", name="Start research session", exact=True).click()
    research.get_by_role("button", name="Confirm and start", exact=True).click()
    expect(research.locator(".research-session-subtitle")).to_contain_text("running", timeout=10000)
    page.get_by_role("button", name="Pause research session", exact=True).click()
    expect(research.locator(".research-session-subtitle")).to_contain_text("paused", timeout=5000)
    expect(page.get_by_role("button", name="Resume research session", exact=True)).to_be_enabled()
    page.get_by_role("button", name="Resume research session", exact=True).click()
    expect(research.locator(".research-session-subtitle")).to_contain_text("running", timeout=5000)
    research.get_by_role("button", name="Stop", exact=True).click()
    confirm_stop = research.get_by_role("group", name="Confirm stop session")
    confirm_stop.get_by_role("button", name="Confirm stop", exact=True).click()
    expect(research.locator(".research-session-subtitle")).to_contain_text("stopped", timeout=5000)

    # A background provider failure is reconciled into the history and a toast.
    page.get_by_role(
        "button", name="Edit strategy title: Pause and stop fixture strategy", exact=True
    ).click()
    page.locator(f"#strategy-title-{first_strategy_id}").fill("Failure fixture strategy")
    page.locator(f"li[data-strategy-id='{first_strategy_id}']").get_by_role(
        "button", name="Save", exact=True
    ).click()
    page.reload()
    research = page.locator(".research-workspace")
    expect(research.get_by_label("Research session history")).to_contain_text(
        "#2 · Pause and stop fixture strategy · stopped"
    )
    page.get_by_role("button", name="Start research session", exact=True).click()
    research.get_by_role("button", name="Confirm and start", exact=True).click()
    expect(research.locator(".research-session-subtitle")).to_contain_text("failed", timeout=10000)
    expect(page.locator(".request-toast")).to_have_count(1)
    page.get_by_role("button", name="Dismiss request error").click()
    expect(research.get_by_label("Research session history")).to_contain_text(
        "#3 · Failure fixture strategy · failed"
    )

    saved_before_fallback = project_file.read_bytes()
    legacy_titleless["enabled"] = True
    page.goto("http://127.0.0.1:5173")
    page.goto(f"http://127.0.0.1:5173/project?{urlencode({'path': path})}")
    expect(
        page.locator("summary").filter(
            has_text="Strategy: Derive a recurrence and inspect boundary cases."
        )
    ).to_be_visible()
    assert project_file.read_bytes() == saved_before_fallback
    legacy_titleless["enabled"] = False

    # Pane collapse is independent; the research session remains available.
    page.locator(".project-pane-title-line").get_by_role(
        "button", name=re.compile("^Project:")
    ).click()
    expect(page.locator("#project-pane-content")).to_be_hidden()
    expect(research).to_be_visible()
    expect(page.locator("#strategies-pane-content")).to_be_visible()
    page.get_by_role("button", name="Strategies", exact=True).click()
    expect(page.locator("#strategies-pane-content")).to_be_hidden()
    expect(research).to_be_visible()
    page.set_viewport_size({"width": 390, "height": 844})
    assert page.evaluate("document.documentElement.scrollWidth <= window.innerWidth")
    page.screenshot(path="/tmp/sigma-a171-mobile.png", full_page=True)
    assert not errors, errors
    assert len(starts) == 3, starts
    print(
        "PASS real Chrome A17.1: project/strategy title editing and persistence, generated title acceptance, non-destructive legacy title fallback, pencil/disclosure isolation, bounded Play/Pause, session history/artifacts, pane collapse, failure recovery and mobile overflow"
    )
    page.unroute_all(behavior="ignoreErrors")
    browser.close()
