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
    samples = page.get_by_role("tabpanel", name="Samples")
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
    project_title = project_heading.inner_text()
    project_path = page.evaluate("new URL(location.href).searchParams.get('path')")
    project_id = json.loads(Path(project_path, "project.json").read_text())["id"]
    page.locator(".project-art-header .project-header-art").click()
    recent = page.get_by_role("tabpanel", name="Saved")
    recent_group = recent.locator("details.recent-type-group").filter(has_text="Mathematics")
    if not recent_group.evaluate("group => group.open"):
        recent_group.locator("summary").click()
    entry = recent.get_by_role("button", name=project_title, exact=True)
    expect(entry).to_be_visible()
    metadata = entry.locator("xpath=../..").locator(".recent-meta-row > small > span")
    initial = metadata.inner_text()
    assert "Running" not in initial and initial.count(" · ") == 1, initial

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
    recent = page.get_by_role("tabpanel", name="Saved")
    recent_group = recent.locator("details.recent-type-group").filter(has_text="Mathematics")
    if not recent_group.evaluate("group => group.open"):
        recent_group.locator("summary").click()
    entry = recent.get_by_role("button", name=project_title, exact=True)
    metadata = entry.locator("xpath=../..").locator(".recent-meta-row > small > span")
    expect(metadata).to_contain_text(" · Running · ", timeout=10000)
    running.clear()
    expect(metadata).to_have_text(initial, timeout=10000)

    # Another version in the same family stays visible until one is pinned.
    sibling_title = re.sub(r" v[0-9]+$", " v2", project_title)
    assert sibling_title != project_title
    siblings.update(enabled=True, project_id=project_id, sibling_title=sibling_title)
    page.reload()
    recent = page.get_by_role("tabpanel", name="Saved")
    recent_group = recent.locator("details.recent-type-group").filter(has_text="Mathematics")
    if not recent_group.evaluate("group => group.open"):
        recent_group.locator("summary").click()
    expect(recent.get_by_role("button", name=sibling_title, exact=True)).to_be_visible()

    pin = recent.get_by_role("button", name=f"Pin {project_title}")
    remove = recent.get_by_role("button", name=f"Remove {project_title} from Saved Projects")
    pin_color = pin.evaluate("node => getComputedStyle(node).color")
    assert pin_color == remove.evaluate("node => getComputedStyle(node).color")
    pin.click()

    # Stay in the same category and retain the same order after pinning.
    expect(recent.locator("details.pinned-type-group")).to_have_count(0)
    pinned = recent.locator("details.recent-type-group").filter(has_text="Mathematics")
    expect(pinned.get_by_role("button", name=project_title, exact=True)).to_be_visible()
    expect(recent.get_by_role("button", name=sibling_title, exact=True)).to_have_count(0)
    expect(pinned.locator(".recent-title-pin")).to_be_visible()
    expect(recent.get_by_role("button", name=sibling_title, exact=True)).to_have_count(0)
    expect(pinned.get_by_role("button", name=f"Remove {project_title} from Saved Projects")).to_have_count(0)
    unpin = pinned.get_by_role("button", name=f"Unpin {project_title}")
    expect(unpin).to_be_visible()
    assert unpin.evaluate("node => getComputedStyle(node).color") == pin_color
    unpin.hover()
    assert unpin.evaluate("node => getComputedStyle(node).color") == pin_color

    page.reload()
    recent = page.get_by_role("tabpanel", name="Saved")
    pinned = recent.locator("details.recent-type-group").filter(has_text="Mathematics")
    if not pinned.evaluate("group => group.open"):
        pinned.locator("summary").click()
    expect(pinned.locator(".recent-title-pin")).to_be_visible()
    expect(pinned.get_by_role("button", name=f"Remove {project_title} from Saved Projects")).to_have_count(0)
    pinned.get_by_role("button", name=f"Unpin {project_title}").click()
    expect(pinned.locator(".recent-title-pin")).to_have_count(0)
    expect(pinned.get_by_role("button", name=project_title, exact=True)).to_be_visible()
    expect(recent.get_by_role("button", name=sibling_title, exact=True)).to_be_visible()
    expect(pinned.get_by_role("button", name=f"Remove {project_title} from Saved Projects")).to_be_visible()
    expect(pinned.locator("details.pinned-type-group")).to_have_count(0)
    assert not errors, errors
    browser.close()
    print("PASS T92 real Chrome: live status, in-category pins, hidden Remove, reload, 1280/390/320px")
