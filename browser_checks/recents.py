"""Real Chrome: Samples/Recent Home tabs, direct sample opens, and responsive layout."""

import json
import os
import re
from pathlib import Path

from playwright.sync_api import expect, sync_playwright

SOURCE = Path("samples/nonconsecutive-subset-sums/project.json")
original = SOURCE.read_bytes()
UI_ORIGIN = os.environ.get("SIGMA_RECENTS_UI_ORIGIN", "http://127.0.0.1:5173").rstrip("/")
API_ORIGIN = os.environ.get("SIGMA_RECENTS_API_ORIGIN", "http://127.0.0.1:8001").rstrip("/")
running_project_ids: set[str] = set()

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
        response = route.fetch(url=route.request.url.replace(UI_ORIGIN, API_ORIGIN))
        if route.request.url.split("?", 1)[0] == f"{UI_ORIGIN}/api/projects/recent":
            data = response.json()
            for entry in data["projects"]:
                entry["research_running"] = entry["id"] in running_project_ids
            route.fulfill(response=response, body=json.dumps(data))
            return
        route.fulfill(response=response)

    page.route("**/api/**", forward)
    page.goto("http://127.0.0.1:5173/")
    page.get_by_role("button", name="New", exact=True).hover()
    expect(page.get_by_role("tooltip")).to_have_text("Create a project")
    page.get_by_role("button", name="Open", exact=True).hover()
    expect(page.get_by_role("tooltip")).to_have_text("Open an existing project")
    page.get_by_role("button", name="Open", exact=True).click()
    open_dialog = page.get_by_role("dialog", name="Open Project")
    open_header = open_dialog.locator(".entry-dialog-header")
    open_cancel = open_header.get_by_role("button", name="Cancel", exact=True)
    expect(open_cancel).to_be_visible()
    open_dialog.get_by_role("heading", name="Open Project", exact=True).evaluate(
        "h => { const cancel = h.nextElementSibling; if (!cancel || !cancel.matches('button.entry-cancel') || cancel.getBoundingClientRect().left < h.getBoundingClientRect().right) throw new Error('Cancel must flow immediately after the Open Project title'); }"
    )
    assert open_cancel.bounding_box()["y"] < open_dialog.get_by_role("button", name="Open Project", exact=True).bounding_box()["y"]
    expect(open_dialog.locator(".entry-dialog-actions").get_by_role("button", name="Cancel")).to_have_count(0)
    open_cancel.click()
    expect(open_dialog).to_have_count(0)
    samples_tab = page.get_by_role("tab", name="Samples", exact=True)
    recent_tab = page.get_by_role("tab", name="Recent", exact=True)
    assert page.get_by_role("tab").all_text_contents() == ["Samples", "Recent"]
    expect(samples_tab).to_have_attribute("aria-selected", "true")
    recent_tab.hover()
    expect(page.get_by_role("tooltip")).to_have_text(
        "Show recent projects. Click again to collapse or expand all."
    )
    samples_tab.hover()
    expect(page.get_by_role("tooltip")).to_have_text(
        "Show sample projects. Click again to collapse or expand all."
    )
    samples_panel = page.get_by_role("tabpanel", name="Samples")
    expect(samples_panel.get_by_text("Nonconsecutive Subset Sums Modulo 3")).to_be_visible()
    expect(samples_panel.get_by_text("Did Jesus Use Cannabis?")).to_be_visible()
    expect(
        samples_panel.get_by_role("button", name="Open Maximum Regions Formed by Lines").locator(
            "small span"
        )
    ).to_have_text("1 strategy · Easy difficulty")
    sample_title_box = samples_panel.locator(".sample-open strong").first.bounding_box()
    sample_meta_box = samples_panel.locator(".sample-open small span").first.bounding_box()
    assert sample_title_box and sample_meta_box and abs(sample_title_box["x"] - sample_meta_box["x"]) < 1
    sample_type = samples_panel.locator(".sample-open strong").first.evaluate(
        "e => [getComputedStyle(e).fontSize, getComputedStyle(e).fontFamily]"
    )
    sample_meta_style = samples_panel.locator(".sample-open small span").first.evaluate(
        "e => [getComputedStyle(e).fontSize, getComputedStyle(e).fontFamily]"
    )
    type_groups = samples_panel.locator(".sample-type-group")
    type_labels = type_groups.locator("summary > span").all_text_contents()
    assert type_labels == sorted(type_labels, key=str.casefold), type_labels
    group_controls = type_groups.locator("summary").evaluate_all(
        "items => items.map(e => { const boxes = [...e.children].map(child => child.getBoundingClientRect()); return boxes.map(r => ({x:r.x,y:r.y,right:r.right,width:r.width})); })"
    )
    assert all(
        max(box["y"] for box in row) - min(box["y"] for box in row) < 2 for row in group_controls
    )
    count_x = [row[-1]["x"] for row in group_controls]
    assert max(count_x) - min(count_x) < 2, group_controls
    assert all(row[-1]["x"] - row[1]["right"] < 155 for row in group_controls), group_controls
    first_type = type_groups.first
    first_sample = first_type.locator(".sample-open").first
    first_type.locator("summary").click()
    expect(first_sample).to_be_hidden()
    first_type.locator("summary").click()
    expect(first_sample).to_be_visible()
    samples_tab.hover()
    expect(page.get_by_role("tooltip")).to_be_visible()
    samples_tab.click()
    assert type_groups.evaluate_all("groups => groups.every(group => !group.open)")
    expect(page.get_by_role("tooltip")).to_have_count(0)
    page.mouse.move(4, 4)
    samples_tab.hover()
    expect(page.get_by_role("tooltip")).to_be_visible()
    samples_tab.click()
    assert type_groups.evaluate_all("groups => groups.every(group => group.open)")
    expect(page.get_by_role("tooltip")).to_have_count(0)
    expect(first_sample).to_be_visible()
    scroller = samples_panel.locator(".home-samples")
    scroll_metrics = scroller.evaluate(
        "e=>({overflow:getComputedStyle(e).overflowY,scrollHeight:e.scrollHeight,clientHeight:e.clientHeight})"
    )
    assert scroll_metrics["overflow"] == "auto"
    # The complete catalog may fit exactly at this viewport with Linux fonts.
    # Exercise scrolling only when there is actual overflow.
    if scroll_metrics["scrollHeight"] > scroll_metrics["clientHeight"]:
        scroller.evaluate("e=>e.scrollTop=e.scrollHeight")
        assert scroller.evaluate("e=>e.scrollTop") > 0
        scroller.evaluate("e=>e.scrollTop=0")
    assert (
        samples_panel.locator(".sample-open strong").all_text_contents()[-1]
        == "Did Jesus Use Cannabis?"
    )
    assert "Stock" not in page.locator("body").inner_text()
    assert samples_panel.get_by_text("Shipped template").count() == 0
    row = samples_panel.locator(".sample-open").first
    base_color = row.evaluate("e=>getComputedStyle(e).backgroundColor")
    row.hover()
    assert row.evaluate("e=>getComputedStyle(e).backgroundColor") != base_color

    samples_tab.focus()
    page.keyboard.press("ArrowRight")
    expect(recent_tab).to_be_focused()
    recent_tab.click()
    expect(recent_tab).to_have_attribute("aria-selected", "true")
    recent_panel = page.get_by_role("tabpanel", name="Recent")
    expect(recent_panel.get_by_text("No recent projects yet.", exact=False)).to_be_visible()
    page.keyboard.press("ArrowLeft")
    expect(samples_tab).to_be_focused()

    samples_panel.get_by_role("button", name="Open Nonconsecutive Subset Sums Modulo 3").click()
    expect(
        page.get_by_role("heading", name="Nonconsecutive Subset Sums Modulo 3 v1")
    ).to_be_visible()
    assert page.get_by_role("dialog").count() == 0
    expect(page.locator(".strategy-row")).to_have_count(3)
    path = page.evaluate("new URL(location.href).searchParams.get('path')")
    assert Path(path, "project.json").read_bytes() != original

    # The strategy disclosure shows and hides the complete approach.
    first_row = page.locator(".strategy-row").first
    expanded = first_row.locator(".strategy-expanded")
    disclosure = first_row.locator(".strategy-row-disclosure")
    expect(expanded).to_be_visible()
    disclosure.click()
    expect(expanded).to_be_hidden()
    source = json.loads(Path(path, "project.json").read_text())
    expect(first_row.locator(".strategy-expanded .strategy-approach")).to_have_text(
        source["strategies"][0]["approach"]
    )
    disclosure.click()
    expect(expanded).to_be_visible()
    saved = page.request.post(
        f"{API_ORIGIN}/api/projects/strategies",
        data={"path": path, "title": "Browser sample addition", "approach": "Keep this strategy"},
    )
    assert saved.status == 201
    page.get_by_role("button", name="Back to home", exact=True).click()
    # A Sample is copied into working projects; return to Recent automatically.
    expect(recent_tab).to_have_attribute("aria-selected", "true")
    first_copy = recent_panel.get_by_role(
        "button", name="Nonconsecutive Subset Sums Modulo 3 v1", exact=True
    )
    expect(first_copy).to_be_visible()
    recent_meta = first_copy.locator("xpath=../..").locator(".recent-meta-row small span")
    expect(recent_meta).to_contain_text("strategies · ")
    expect(recent_meta).to_contain_text("Hard difficulty")
    assert "Mathematics" not in recent_meta.inner_text()
    recent_title_box = first_copy.bounding_box()
    recent_meta_box = recent_meta.bounding_box()
    assert recent_title_box and recent_meta_box and abs(recent_title_box["x"] - recent_meta_box["x"]) < 1
    recent_meta_style = recent_meta.evaluate(
        "e => [getComputedStyle(e).fontSize, getComputedStyle(e).fontFamily]"
    )
    assert sample_meta_style == recent_meta_style
    idle_metadata = recent_meta.inner_text()
    assert idle_metadata.count(" · ") == 1 and "Running" not in idle_metadata
    running_project_ids.add(json.loads(Path(path, "project.json").read_text())["id"])
    expect(recent_meta).to_contain_text(" · Running · ", timeout=10000)
    running_label = recent_meta.locator(".recent-running")
    assert running_label.evaluate("e => getComputedStyle(e).color") == "rgb(143, 189, 154)"
    for width, height in ((390, 844), (320, 700)):
        page.set_viewport_size({"width": width, "height": height})
        expect(running_label).to_be_visible()
        assert page.evaluate("document.documentElement.scrollWidth <= innerWidth")
    page.set_viewport_size({"width": 1280, "height": 720})
    running_project_ids.clear()
    expect(recent_meta).to_have_text(idle_metadata, timeout=10000)
    recent_groups = recent_panel.locator(".recent-type-group")
    recent_labels = recent_groups.locator("summary > span").all_text_contents()
    assert recent_labels == sorted(recent_labels, key=str.casefold), recent_labels
    recent_tab.hover()
    expect(page.get_by_role("tooltip")).to_have_text(
        "Show recent projects. Click again to collapse or expand all."
    )
    recent_tab.click()
    assert recent_groups.evaluate_all("groups => groups.every(group => !group.open)")
    recent_tab.click()
    assert recent_groups.evaluate_all("groups => groups.every(group => group.open)")
    copy_group = recent_groups.filter(has_text="Mathematics")
    group_box = copy_group.locator("summary").bounding_box()
    project_box = first_copy.bounding_box()
    assert group_box and project_box and project_box["x"] >= group_box["x"] + 14
    copy_group.locator("summary").click()
    expect(first_copy).to_be_hidden()
    copy_group.locator("summary").click()
    expect(first_copy).to_be_visible()

    # Project navigation unmounts Home; tab state should survive that and reload.
    recent_panel.locator(".recent-open").first.click()
    expect(
        page.get_by_role("heading", name=re.compile(r"Nonconsecutive Subset Sums Modulo 3"))
    ).to_be_visible()
    page.get_by_role("button", name="Back to home", exact=True).click()
    expect(recent_tab).to_have_attribute("aria-selected", "true")
    page.reload()
    expect(recent_tab).to_have_attribute("aria-selected", "true")
    samples_tab.hover()
    expect(page.get_by_role("tooltip")).to_have_text(
        "Show sample projects. Click again to collapse or expand all."
    )
    samples_tab.click()
    expect(samples_tab).to_have_attribute("aria-selected", "true")

    # A second successful Sample copy must select Recent again.
    samples_panel.get_by_role("button", name="Open Nonconsecutive Subset Sums Modulo 3").click()
    page.get_by_role("button", name="Back to home", exact=True).click()
    expect(recent_tab).to_have_attribute("aria-selected", "true")
    second_copy = recent_panel.get_by_role(
        "button", name="Nonconsecutive Subset Sums Modulo 3 v2", exact=True
    )
    expect(second_copy).to_be_visible()
    expect(second_copy.locator("strong.is-most-recent-project")).to_be_visible()
    assert second_copy.locator("strong").evaluate("e => getComputedStyle(e).fontWeight") == "700"
    expect(first_copy.locator("strong")).to_have_count(0)
    normal_recent_type = first_copy.evaluate(
        "e => [getComputedStyle(e).fontSize, getComputedStyle(e).fontFamily]"
    )
    normal_recent_meta = first_copy.locator("xpath=../..").locator(".recent-meta-row small span")
    normal_recent_meta_style = normal_recent_meta.evaluate(
        "e => [getComputedStyle(e).fontSize, getComputedStyle(e).fontFamily]"
    )
    assert sample_type == normal_recent_type and sample_meta_style == normal_recent_meta_style
    second_project_path = second_copy.locator("xpath=../..")
    project_path = second_project_path.locator(":scope > span").get_attribute("title")
    assert project_path and Path(project_path, "project.json").is_file()
    row = second_copy.locator("xpath=../../..")
    row_before = row.bounding_box()
    remove = row.get_by_role("button", name=re.compile("Remove .* from Recent Projects"))
    remove.click()
    confirmation = row.get_by_role(
        "group", name="Confirm remove Nonconsecutive Subset Sums Modulo 3 v2"
    )
    expect(confirmation).to_be_visible()
    row_after = row.bounding_box()
    assert row_before and row_after and abs(row_before["height"] - row_after["height"]) < 1
    confirmation.get_by_role("button", name="Cancel", exact=True).click()
    expect(confirmation).to_have_count(0)
    remove.click()
    confirmation = row.get_by_role(
        "group", name="Confirm remove Nonconsecutive Subset Sums Modulo 3 v2"
    )
    confirmation.get_by_role("button", name="Confirm", exact=True).click()
    expect(second_copy).to_have_count(0)
    assert Path(project_path, "project.json").is_file(), (
        "Removing from Recent must keep research data"
    )
    samples_tab.click()

    for width, height in ((1280, 720), (390, 844), (320, 700)):
        page.set_viewport_size({"width": width, "height": height})
        if samples_tab.get_attribute("aria-selected") != "true":
            samples_tab.click()
        expect(samples_panel.get_by_text("Did Jesus Use Cannabis?")).to_be_visible()
        assert page.evaluate("document.documentElement.scrollWidth <= innerWidth")
        panel_box = samples_panel.bounding_box()
        scroller_box = scroller.bounding_box()
        scroller_bottom = scroller_box["y"] + scroller_box["height"] if scroller_box else 0
        assert panel_box and scroller_box and height - 24 <= scroller_bottom <= height + 1, (
            width,
            panel_box,
            scroller_box,
        )
        assert page.evaluate("document.documentElement.scrollHeight <= innerHeight + 1")
        page.screenshot(path=f"/tmp/sigma-samples-{width}.png", full_page=True)

    assert SOURCE.read_bytes() == original
    assert not errors, errors
    page.unroute_all(behavior="ignoreErrors")
    browser.close()
    print(
        "PASS Chrome Recent after Sample copies, manual tab persistence, full strategy expansion, and source immutability"
    )
