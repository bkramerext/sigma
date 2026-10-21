"""A9 real Chrome: four recents and measured fixed dialog actions on laptop/mobile."""

import json
import os
from pathlib import Path
from uuid import uuid4

from playwright.sync_api import expect, sync_playwright

with sync_playwright() as p:
    browser = p.chromium.launch(
        executable_path=os.environ.get(
            "SIGMA_BROWSER_EXECUTABLE",
            "/Applications/Google Chrome.app/Contents/MacOS/Google Chrome",
        ),
        headless=True,
    )
    page = browser.new_page(viewport={"width": 1280, "height": 720})
    page.set_default_timeout(10000)
    errors, requests = [], []
    page.on("pageerror", lambda error: errors.append(str(error)))

    def forward(route):
        requests.append((route.request.method, route.request.url))
        route.fulfill(
            response=route.fetch(url=route.request.url.replace("127.0.0.1:5173", "127.0.0.1:8001"))
        )

    page.route("**/api/**", forward)

    def close_project():
        page.get_by_role("button", name="Close project", exact=True).click()
        expect(page.get_by_role("heading", name="Open a Project", exact=True)).to_be_visible()
        expect(recents.locator(".recent-open").first).to_be_visible()

    def listing():
        return page.request.get("http://127.0.0.1:8001/api/projects/recent").json()["projects"]

    def hold_requests(held):
        def handle(route):
            held.append(route)

        return handle

    def visible_actions(dialog):
        header = dialog.locator(".settings-header")
        for button in header.get_by_role("button").all():
            expect(button).to_be_visible()
            box = button.bounding_box()
            assert box and box["x"] >= 0 and box["y"] >= 0
            assert box["x"] + box["width"] <= page.viewport_size["width"]
            assert box["y"] + box["height"] <= page.viewport_size["height"]
        assert dialog.locator(".settings-actions").count() == 1
        assert page.evaluate("document.documentElement.scrollWidth <= innerWidth")
        assert dialog.evaluate("e=>e.scrollHeight<=e.clientHeight+1")

    page.goto("http://127.0.0.1:5173/")
    recents = page.get_by_role("region", name="Recent Projects", exact=True)
    expect(
        recents.locator(".recent-open").filter(has_text="Nonconsecutive Subset Sums Modulo 3")
    ).to_be_visible()
    expect(recents.get_by_text("Mathematical · Included example", exact=True)).to_be_visible()
    seed = listing()[0]
    source = Path("examples/nonconsecutive-subset-sums/project.json").read_bytes()
    assert Path(seed["path"]).joinpath("project.json").read_bytes() == source
    recents.locator(".recent-open").first.click()
    expect(page.locator(".strategy-row")).to_have_count(3)
    assert (
        all(stage == "Draft" for stage in page.locator(".strategy-stage").all_text_contents())
        if page.locator(".strategy-stage").count()
        else True
    )
    close_project()
    expect(recents.locator(".recent-open")).to_have_count(1)
    assert not listing()[0]["included_example"]

    # Each create/edit mode keeps title-adjacent controls visible while only body scrolls.
    for width, height in ((1280, 720), (1440, 900), (390, 844), (320, 700)):
        page.set_viewport_size({"width": width, "height": height})
        page.get_by_role("button", name="New Project", exact=True).click()
        dialog = page.get_by_role("dialog")
        expect(dialog.get_by_role("heading", name="New Project", exact=True)).to_be_visible()
        visible_actions(dialog)
        dialog.get_by_label("Project name", exact=True).fill("Viewport " + uuid4().hex[:8])
        dialog.get_by_label("Research problem", exact=True).fill(
            "Bounded mathematical question. " * 300
        )
        body = dialog.locator(".settings-body")
        body.evaluate(
            "e=>{const p=document.createElement('p');p.textContent='Expanded model and validation explanation. '.repeat(80);e.appendChild(p);e.scrollTop=e.scrollHeight;}"
        )
        visible_actions(dialog)
        primary = dialog.locator('.settings-actions button[type="submit"]')
        primary.evaluate("e=>e.textContent='Create investigation with a longer localized label'")
        visible_actions(dialog)
        primary.evaluate("e=>e.textContent='Create'")
        page.screenshot(path=f"/tmp/sigma-a9-create-{width}.png")
        pending = []
        page.route("**/api/projects/create", hold_requests(pending))
        before_open = sum(url.split("?")[0].endswith("/api/projects/open") for _, url in requests)
        primary.click()
        expect(dialog.get_by_role("button", name="Saving…", exact=True)).to_be_visible()
        expect(dialog.get_by_role("button", name="Cancel", exact=True)).to_be_disabled()
        page.keyboard.press("Escape")
        expect(dialog).to_be_visible()
        visible_actions(dialog)
        dialog.locator("form").evaluate("e=>{e.requestSubmit();e.requestSubmit();}")
        assert len(pending) == 1
        pending[0].fulfill(
            response=pending[0].fetch(
                url=pending[0].request.url.replace("127.0.0.1:5173", "127.0.0.1:8001")
            )
        )
        page.unroute("**/api/projects/create")
        expect(page.get_by_role("heading", name="Strategies", exact=True)).to_be_visible()
        assert (
            sum(url.split("?")[0].endswith("/api/projects/open") for _, url in requests)
            == before_open
        )
        page.get_by_role("button", name="Edit Project", exact=True).click()
        expect(dialog.get_by_role("heading", name="Edit Project", exact=True)).to_be_visible()
        visible_actions(dialog)
        body = dialog.locator(".settings-body")
        body.evaluate("e=>e.scrollTop=e.scrollHeight")
        visible_actions(dialog)
        page.screenshot(path=f"/tmp/sigma-a9-edit-{width}.png")
        # Save failure keeps draft and visible header; retry preserves settings/history.
        name = "Edited " + uuid4().hex[:8]
        dialog.get_by_label("Project name", exact=True).fill(name)
        page.route(
            "**/api/projects/update",
            lambda route: route.fulfill(
                status=400,
                content_type="application/json",
                body=json.dumps({"error": "Injected save failure. " * 60}),
            ),
        )
        dialog.get_by_role("button", name="Save Changes", exact=True).click()
        expect(dialog.get_by_role("alert")).to_be_visible()
        expect(dialog.get_by_label("Project name", exact=True)).to_have_value(name)
        visible_actions(dialog)
        page.screenshot(path=f"/tmp/sigma-a9-error-{width}.png")
        page.unroute("**/api/projects/update")
        dialog.get_by_role("button", name="Save Changes", exact=True).click()
        expect(page.get_by_role("heading", name=name, exact=True)).to_be_visible()
        close_project()
        expect(recents.locator(".recent-open").first).to_contain_text(name)
    assert len(listing()) == 4
    print(
        "PASS measured fixed Create/Edit header actions at 1280/1440/390/320, long problem/help/localized labels, scroll, busy/Escape/duplicate guard, retained failure/retry and no duplicate post-create open"
    )

    # Open an evicted entry by directory, click a recent, dedup, rename and close.
    page.set_viewport_size({"width": 1280, "height": 720})
    for number in range(5):
        page.get_by_role("button", name="New Project", exact=True).click()
        dialog = page.get_by_role("dialog")
        dialog.get_by_label("Project name", exact=True).fill(f"LRU {number} " + uuid4().hex[:6])
        dialog.get_by_label("Research problem", exact=True).fill("A new investigation")
        dialog.get_by_role("button", name="Create", exact=True).click()
        expect(page.get_by_role("heading", name="Strategies", exact=True)).to_be_visible()
        if number == 0:
            first = listing()[0]
        close_project()
        expect(recents.locator(".recent-open")).to_have_count(4)
    assert first["id"] not in {entry["id"] for entry in listing()}
    page.get_by_role("button", name="Open Project", exact=True).click()
    dialog = page.get_by_role("dialog")
    dialog.get_by_label("Project directory", exact=True).fill(first["path"])
    dialog.get_by_role("button", name="Open Project", exact=True).click()
    expect(page.get_by_role("heading", name=first["title"], exact=True)).to_be_visible()
    close_project()
    expect(recents.locator(".recent-open").first).to_contain_text(first["title"])
    before = listing()
    recents.locator(".recent-open").first.click()
    expect(page.get_by_role("heading", name=first["title"], exact=True)).to_be_visible()
    close_project()
    assert [entry["id"] for entry in listing()] == [entry["id"] for entry in before]
    Path(first["path"]).joinpath("project.json").write_text("fixture corruption")
    page.reload()
    expect(recents.locator(".recent-open").first).to_be_disabled()
    recents.locator(".recent-forget").first.click()
    expect(recents.locator(".recent-open")).to_have_count(3)
    assert Path(first["path"]).joinpath("project.json").read_text() == "fixture corruption"
    for width, height in ((1280, 720), (1440, 900), (768, 1024), (390, 844), (320, 700)):
        page.set_viewport_size({"width": width, "height": height})
        assert page.evaluate("document.documentElement.scrollWidth <= innerWidth")
        page.screenshot(path=f"/tmp/sigma-a9-home-{width}.png", full_page=True)
    assert Path("examples/nonconsecutive-subset-sums/project.json").read_bytes() == source
    assert not errors, errors
    print(
        "PASS exact included v5 sample opens three Draft strategies, five creations/eviction, Open/recent click dedup, unavailable/forget behavior, honest metadata, responsive Home and no JS errors; template unchanged"
    )
    browser.close()
