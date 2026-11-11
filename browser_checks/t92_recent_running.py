"""T92 real-Chromium acceptance: active Saved status, polling, mobile and reload.

Uses an isolated local fixture API; status alone is controlled at the transport
boundary. No provider requests or research work are dispatched.
"""

import json
import os
import re
from pathlib import Path

from playwright.sync_api import expect, sync_playwright

UI = os.environ.get("SIGMA_RECENTS_UI_ORIGIN", "http://127.0.0.1:5173").rstrip("/")
API = os.environ.get("SIGMA_RECENTS_API_ORIGIN", "http://127.0.0.1:8001").rstrip("/")
REQUEST_ORIGIN = os.environ.get("SIGMA_BROWSER_REQUEST_ORIGIN", UI)
running: set[str] = set()
siblings = {"enabled": False, "project_id": "", "sibling_title": ""}
unavailable_fixture = {"enabled": False}
most_recent_activity = {"enabled": False, "active": True}

with sync_playwright() as playwright:
    browser = playwright.chromium.launch(
        executable_path=os.environ.get(
            "SIGMA_BROWSER_EXECUTABLE",
            "/Applications/Google Chrome.app/Contents/MacOS/Google Chrome",
        ),
        headless=True,
    )
    page = browser.new_page(viewport={"width": 1280, "height": 720})
    errors: list[str] = []
    page.on("pageerror", lambda error: errors.append(str(error)))

    def forward(route):
        headers = dict(route.request.headers)
        headers["origin"] = REQUEST_ORIGIN
        response = route.fetch(url=route.request.url.replace(UI, API), headers=headers)
        if route.request.url.split("?", 1)[0] == f"{UI}/api/projects/recent":
            data = response.json()
            for entry in data["projects"]:
                entry["research_running"] = entry["id"] in running
            if most_recent_activity["enabled"]:
                # Ten ordinary recent projects plus two older active entries.
                template = next(entry for entry in data["projects"] if entry["available"])
                data["projects"] = [
                    {
                        **template,
                        "id": f"00000000-0000-4000-8000-{index:012d}",
                        "title": f"Most Recent Fixture {index}",
                        "path": f"/fixture-{index}.sigma",
                        "research_running": most_recent_activity["active"] and index == 11,
                        "paper_activity": (
                            "queued" if most_recent_activity["active"] and index == 12 else None
                        ),
                        "paper_generating": False,
                        "pinned": False,
                    }
                    for index in range(1, 13)
                ]
            if unavailable_fixture["enabled"]:
                data["projects"].append(
                    {
                        "id": "00000000-0000-4000-8000-000000000124",
                        "path": "/unavailable-placeholder.sigma",
                        "title": "Unfindable Ghost Project",
                        "investigation_type": None,
                        "strategy_count": None,
                        "difficulty": None,
                        "research_running": False,
                        "available": False,
                        "pinned": False,
                        "error": "Unavailable or changed identity",
                    }
                )
                data["projects"].append(
                    {
                        "id": "00000000-0000-4000-8000-000000000125",
                        "path": "/valid-but-no-project-type.sigma",
                        "title": "Valid Untyped Project",
                        "investigation_type": "default",
                        "strategy_count": 1,
                        "difficulty": "medium",
                        "research_running": False,
                        "available": True,
                        "pinned": False,
                        "error": None,
                    }
                )
            if siblings["enabled"]:
                original = next(
                    (entry for entry in data["projects"] if entry["id"] == siblings["project_id"]),
                    None,
                )
                if original:
                    # Fixture-only second version; project state is untouched.
                    sibling = {
                        **original,
                        "id": "00000000-0000-4000-8000-000000000123",
                        "title": siblings["sibling_title"],
                        "pinned": False,
                        "research_running": False,
                    }
                    data["projects"].insert(data["projects"].index(original) + 1, sibling)
            route.fulfill(response=response, body=json.dumps(data))
        else:
            route.fulfill(response=response)

    page.route("**/api/**", forward)
    page.goto(UI)
    # Projects header mirrors the active Samples / My Work tab's group toggle.
    project_groups_title = page.get_by_role("button", name="Collapse or expand project type groups")
    samples = page.get_by_role("tabpanel", name="Samples")
    expect(samples.locator("details.sample-type-group").first).to_be_visible()
    sample_groups = samples.locator("details.sample-type-group")
    sample_initially_closed = sample_groups.evaluate_all(
        "groups => groups.every(group => !group.open)"
    )
    project_groups_title.click()
    assert sample_groups.evaluate_all(
        "groups => groups.every(group => group.open)"
        if sample_initially_closed else "groups => groups.every(group => !group.open)"
    )
    project_groups_title.click()
    assert sample_groups.evaluate_all(
        "groups => groups.every(group => !group.open)"
        if sample_initially_closed else "groups => groups.every(group => group.open)"
    )
    sample_group = samples.locator("details.sample-type-group").filter(has_text="Mathematics")
    if not sample_group.evaluate("group => group.open"):
        sample_group.locator("summary").click()
    sample = samples.get_by_role(
        "button", name="Open Nonconsecutive Subset Sums Modulo 3", exact=True
    )
    sample.click()
    project_heading = page.get_by_role(
        "heading", name=re.compile(r"^Nonconsecutive Subset Sums Modulo 3 v\d+$")
    )
    expect(project_heading).to_be_visible()
    # Export actions are beside Cancel in the header, never below the form.
    page.locator('.project-pane-actions [aria-label="Export project"]').click()
    export_dialog = page.get_by_role("dialog", name="Export Project")
    expect(export_dialog).to_be_visible()
    header_actions = export_dialog.locator(".settings-header .settings-actions > button")
    assert header_actions.first.inner_text() == "Download"
    expect(export_dialog.get_by_role("button", name="Cancel export")).to_be_visible()
    assert export_dialog.locator(".export-footer").count() == 0
    filename_field = export_dialog.get_by_label("Filename")
    download_action = export_dialog.get_by_role("button", name="Download")
    expect(download_action).to_be_enabled()
    filename_field.fill("")
    expect(download_action).to_be_disabled()
    filename_field.fill("   ")
    expect(download_action).to_be_disabled()
    filename_field.fill("named-export")
    expect(download_action).to_be_enabled()
    export_dialog.get_by_role("button", name="Cancel").click()
    expect(export_dialog).not_to_be_visible()
    project_title = project_heading.inner_text()
    project_path = page.evaluate("new URL(location.href).searchParams.get('path')")
    project_id = json.loads(Path(project_path, "project.json").read_text())["id"]
    page.locator(".project-art-header .project-header-art").click()
    recent = page.get_by_role("tabpanel", name="My Work")
    recent_group = recent.locator("details.recent-type-group").filter(has_text="Mathematics")
    if not recent_group.evaluate("group => group.open"):
        recent_group.locator("summary").click()
    entry = recent.get_by_role("button", name=project_title, exact=True)
    expect(entry).to_be_visible()
    recent_groups = recent.locator("details.recent-type-group")
    recent_initially_closed = recent_groups.evaluate_all(
        "groups => groups.every(group => !group.open)"
    )
    project_groups_title.click()
    assert recent_groups.evaluate_all(
        "groups => groups.every(group => group.open)"
        if recent_initially_closed else "groups => groups.every(group => !group.open)"
    )
    project_groups_title.click()
    assert recent_groups.evaluate_all(
        "groups => groups.every(group => !group.open)"
        if recent_initially_closed else "groups => groups.every(group => group.open)"
    )
    # Most Recent has no grouped hierarchy and Projects is not a toggle there.
    page.get_by_role("tab", name="Most Recent").click()
    expect(page.locator(".home-projects-title-toggle")).to_have_count(0)
    page.get_by_role("tab", name="My Work").click()
    expect(project_groups_title).to_be_visible()
    metadata = entry.locator("xpath=../..").locator(".recent-meta-row > small > span")
    initial = metadata.inner_text()
    assert "Running" not in initial and initial.count(" · ") == 2, initial
    assert "0 papers" in initial, initial

    running.add(project_id)
    expect(metadata).to_contain_text(" · Running · ", timeout=10000)
    label = metadata.locator(".recent-running")
    assert label.evaluate("e => getComputedStyle(e).color") == "rgb(143, 189, 154)"
    category_indicator = recent_group.locator("summary .research-running-indicator")
    expect(category_indicator).to_have_count(0)
    recent_group.locator("summary").click()
    expect(category_indicator).to_be_visible()
    assert category_indicator.evaluate("e => getComputedStyle(e).top") == "-2px"
    assert (
        category_indicator.evaluate("e => getComputedStyle(e).backgroundColor")
        == "rgb(85, 189, 112)"
    )
    recent_group.locator("summary").click()
    expect(category_indicator).to_have_count(0)
    for width, height in ((1280, 720), (390, 844), (320, 700)):
        page.set_viewport_size({"width": width, "height": height})
        expect(label).to_be_visible()
        assert page.evaluate("document.documentElement.scrollWidth <= innerWidth"), width

    page.reload()
    recent = page.get_by_role("tabpanel", name="My Work")
    recent_group = recent.locator("details.recent-type-group").filter(has_text="Mathematics")
    if not recent_group.evaluate("group => group.open"):
        recent_group.locator("summary").click()
    entry = recent.get_by_role("button", name=project_title, exact=True)
    metadata = entry.locator("xpath=../..").locator(".recent-meta-row > small > span")
    expect(metadata).to_contain_text(" · Running · ", timeout=10000)
    running.clear()
    expect(metadata).to_have_text(initial, timeout=10000)

    # Unavailable records remain in storage but never reach the Saved UI.
    unavailable_fixture["enabled"] = True
    page.reload()
    recent = page.get_by_role("tabpanel", name="My Work")
    expect(recent.get_by_text("Unfindable Ghost Project")).to_have_count(0)
    expect(recent.get_by_text("Valid Untyped Project")).to_have_count(0)
    expect(
        recent.locator("details.recent-type-group").filter(has_text="Unavailable")
    ).to_have_count(0)
    unavailable_fixture["enabled"] = False

    # All project versions stay visible, latest numbered version first.
    assert recent.locator(".recent-pin").count() == 0
    sibling_title = re.sub(r" v[0-9]+$", " v2", project_title)
    assert sibling_title != project_title
    siblings.update(enabled=True, project_id=project_id, sibling_title=sibling_title)
    page.reload()
    recent = page.get_by_role("tabpanel", name="My Work")
    recent_group = recent.locator("details.recent-type-group").filter(has_text="Mathematics")
    if not recent_group.evaluate("group => group.open"):
        recent_group.locator("summary").click()
    original = recent.get_by_role("button", name=project_title, exact=True)
    sibling = recent.get_by_role("button", name=sibling_title, exact=True)
    expect(original).to_be_visible()
    expect(sibling).to_be_visible()
    visible_titles = recent_group.locator("button.recent-open").all_text_contents()
    assert visible_titles.index(sibling_title) < visible_titles.index(project_title), visible_titles
    expect(recent_group.get_by_role("button", name="Remove this project").first).to_be_visible()
    pinned = recent_group

    # Both Saved and Samples show the standard inline hourglass plus text
    # while loading, without replacing the ordinary hand cursor. Hold the
    # request locally so the pending state can be inspected deterministically.
    page.evaluate(
        """() => {
          const originalFetch = window.fetch.bind(window);
          window.fetch = (input, options) => {
            const raw = typeof input === 'string' ? input : input.url;
            const path = new URL(raw, location.href).pathname;
            if (path === '/api/projects/open' || path === '/api/projects/samples/open') {
              return new Promise(resolve => {
                window.__finishProjectOpen = () => resolve(new Response(
                  JSON.stringify({error: 'Simulated delayed project open'}),
                  {status: 503, headers: {'Content-Type': 'application/json'}}
                ));
              });
            }
            return originalFetch(input, options);
          };
        }"""
    )
    saved_button = pinned.locator("button.recent-open").filter(has_text=project_title).first
    saved_button.click()
    expect(saved_button).to_have_attribute("aria-busy", "true")
    expect(saved_button).to_be_disabled()
    expect(saved_button.locator(".project-opening-hourglass")).to_be_visible()
    expect(saved_button.locator(".project-opening-label")).to_have_text("Opening...")
    saved_opening_style = saved_button.evaluate(
        """button => ({
          gap: parseFloat(getComputedStyle(button.querySelector('.project-opening-hourglass')).marginLeft),
          label: getComputedStyle(button.querySelector('.project-opening-label')).color,
          title: getComputedStyle(button.querySelector('strong') || button).color
        })"""
    )
    assert saved_opening_style["gap"] >= 11, saved_opening_style
    assert saved_opening_style["label"] == saved_opening_style["title"], saved_opening_style
    expect(saved_button).to_have_css("cursor", "pointer")
    page.evaluate("window.__finishProjectOpen()")
    expect(saved_button).to_have_attribute("aria-busy", "false")

    page.get_by_role("tab", name="Samples", exact=True).click()
    samples_panel = page.get_by_role("tabpanel", name="Samples")
    sample_group = samples_panel.locator("details.sample-type-group").filter(has_text="Mathematics")
    if not sample_group.evaluate("group => group.open"):
        sample_group.locator("summary").click()
    sample_button = (
        samples_panel.locator("button.sample-open")
        .filter(has_text="Nonconsecutive Subset Sums Modulo 3")
        .first
    )
    sample_button.click()
    expect(sample_button).to_have_attribute("aria-busy", "true")
    expect(sample_button).to_be_disabled()
    expect(sample_button.locator(".project-opening-hourglass")).to_be_visible()
    expect(sample_button.locator(".project-opening-label")).to_have_text("Opening...")
    sample_opening_style = sample_button.evaluate(
        """button => ({
          gap: parseFloat(getComputedStyle(button.querySelector('.project-opening-hourglass')).marginLeft),
          label: getComputedStyle(button.querySelector('.project-opening-label')).color,
          title: getComputedStyle(button.querySelector('strong')).color
        })"""
    )
    assert sample_opening_style["gap"] >= 11, sample_opening_style
    assert sample_opening_style["label"] == sample_opening_style["title"], sample_opening_style
    expect(sample_button).to_have_css("cursor", "pointer")
    page.evaluate("window.__finishProjectOpen()")
    expect(sample_button).to_have_attribute("aria-busy", "false")

    most_recent_activity["enabled"] = True
    page.get_by_role("tab", name="Most Recent", exact=True).click()
    recent_flat = page.locator("#most-recent-panel")
    expect(recent_flat.locator("li")).to_have_count(12, timeout=8000)
    expect(recent_flat.get_by_text("Most Recent Fixture 11")).to_be_visible()
    expect(recent_flat.get_by_text("Most Recent Fixture 12")).to_be_visible()
    expect(recent_flat.locator(".recent-running")).to_have_count(2)
    most_recent_activity["active"] = False
    page.reload()
    page.get_by_role("tab", name="Most Recent", exact=True).click()
    expect(recent_flat.locator("li")).to_have_count(10, timeout=8000)
    expect(recent_flat.get_by_text("Most Recent Fixture 11")).to_have_count(0)
    expect(recent_flat.get_by_text("Most Recent Fixture 12")).to_have_count(0)

    assert not errors, errors
    browser.close()
    print(
        "PASS T92 real Chrome: live status, in-category pins, hidden Remove, reload, 1280/390/320px"
    )
