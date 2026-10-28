"""Real Chrome: Home Saved reflects persisted session activity without reload."""

import fcntl
import json
import os
from pathlib import Path
from uuid import uuid4

from playwright.sync_api import expect, sync_playwright

UI_ORIGIN = os.environ.get("SIGMA_HOME_RUNNING_UI_ORIGIN", "http://127.0.0.1:5173").rstrip("/")
API_ORIGIN = os.environ.get("SIGMA_HOME_RUNNING_API_ORIGIN", "http://127.0.0.1:8001").rstrip("/")
SESSION_FIXTURE = (
    Path(__file__).resolve().parents[1]
    / "docs/evaluations/fixtures/t17-8-answer-free/live-session-91e96112-27ce-412e-841f-5cbf67cbba75.json"
)

with sync_playwright() as playwright:
    browser = playwright.chromium.launch(
        executable_path=os.environ.get(
            "SIGMA_BROWSER_EXECUTABLE",
            "/Applications/Google Chrome.app/Contents/MacOS/Google Chrome",
        ),
        headless=True,
    )
    page = browser.new_page(viewport={"width": 1280, "height": 720})

    response = page.request.post(
        f"{API_ORIGIN}/api/projects/samples/open",
        data={"sample_id": "nonconsecutive-subset-sums"},
    )
    assert response.status == 200, response.text()
    project = response.json()
    project_path = Path(project["path"])
    project_id = project["project"]["id"]
    fixture = json.loads(SESSION_FIXTURE.read_text(encoding="utf-8"))["research_sessions"][0]
    fixture.update(
        {
            "id": "",
            "project_id": project_id,
            "project_path": str(project_path.resolve()),
            "status": "running",
            "estimated_cost_usd": 0.14372,
            "cost_status": "available",
            "session_number": 1,
            "strategy_id": project["project"]["strategies"][0]["id"],
            "strategy_ids": [project["project"]["strategies"][0]["id"]],
            "strategy_title": project["project"]["strategies"][0]["title"],
        }
    )

    def forward(route):
        if "/api/projects/research-sessions?" in route.request.url:
            session = dict(fixture, id=session_id)
            route.fulfill(
                status=200,
                content_type="application/json",
                body=json.dumps({"sessions": [session], "current_understanding": None}),
            )
            return
        headers = route.request.all_headers()
        headers.pop("origin", None)
        route.fulfill(
            response=route.fetch(
                url=route.request.url.replace(UI_ORIGIN, API_ORIGIN), headers=headers
            )
        )

    def expand_recent_groups(panel) -> None:
        for group in panel.locator(".recent-type-group").all():
            group.evaluate("element => { element.open = true; }")

    page.route("**/api/**", forward)
    page.goto(UI_ORIGIN + "/")
    recent_tab = page.get_by_role("tab", name="Saved", exact=True)
    recent_tab.click()
    recent_panel = page.get_by_role("tabpanel", name="Saved")
    expand_recent_groups(recent_panel)
    project_button = (
        recent_panel.locator(".recent-open").filter(has_text=project["project"]["title"]).first
    )
    expect(project_button).to_be_visible()
    metadata = project_button.locator("xpath=../..").locator(".recent-meta-row > small > span")
    expect(metadata).not_to_contain_text("Running")
    SCREENSHOTS = Path(__file__).resolve().parents[1] / "docs/evaluations/t257/screenshots"
    SCREENSHOTS.mkdir(parents=True, exist_ok=True)

    session_id = str(uuid4())
    session_file = project_path / "research-sessions" / f"{session_id}.json"
    session_file.parent.mkdir(exist_ok=True)
    session_file.write_text(
        json.dumps(
            {
                "id": session_id,
                "project_id": project_id,
                "project_path": str(project_path.resolve()),
                "status": "running",
            }
        )
    )
    lock_path = session_file.with_name(f"{session_id}.worker.lock")
    with lock_path.open("a") as worker_lock:
        fcntl.flock(worker_lock.fileno(), fcntl.LOCK_EX)
        expect(metadata).to_contain_text(" · Running", timeout=10_000)
        recent_running_dot = project_button.locator(".research-running-indicator")
        expect(recent_running_dot).to_be_visible()
        assert (
            recent_running_dot.evaluate("element => getComputedStyle(element).animationName")
            == "research-running-heartbeat"
        )
        project_button.scroll_into_view_if_needed()
        home_pill_gap = page.locator(".identity-pill-stack").evaluate(
            "element => getComputedStyle(element).rowGap"
        )
        assert home_pill_gap == "13px", home_pill_gap
        home_pill_padding = page.evaluate("""() => {
          const google = getComputedStyle(document.querySelector('.identity-pill-stack > .project-google-signin'));
          const chatgpt = getComputedStyle(document.querySelector('.identity-pill-stack .api-connection > summary'));
          return [google.paddingTop, google.paddingRight, google.paddingBottom, google.paddingLeft,
            chatgpt.paddingTop, chatgpt.paddingRight, chatgpt.paddingBottom, chatgpt.paddingLeft];
        }""")
        assert home_pill_padding[:4] == home_pill_padding[4:], home_pill_padding
        page.screenshot(path=str(SCREENSHOTS / "green-next-home-running.png"), full_page=True)
        assert recent_panel.locator(".home-runnable-state").count() == 0

        project_button.click()
        expect(page.locator(".workspace-layout")).to_be_visible(timeout=10_000)
        expect(page.locator(".workspace-page .site-header")).to_be_visible(timeout=10_000)
        header_stacking = page.evaluate("""() => {
          const header = document.querySelector('.workspace-page .site-header');
          const pane = document.querySelector('.workspace-layout');
          return [Number(getComputedStyle(header).zIndex), Number(getComputedStyle(pane).zIndex)];
        }""")
        assert header_stacking[0] > header_stacking[1], header_stacking
        project_running_dot = page.locator(".project-header-title .research-running-indicator")
        expect(project_running_dot).to_be_visible(timeout=10_000)
        assert (
            project_running_dot.evaluate("element => getComputedStyle(element).animationName")
            == "research-running-heartbeat"
        )
        running_status = page.locator(".session-running.session-status")
        expect(running_status).to_contain_text("running")
        expect(page.locator(".session-progress-inline")).to_contain_text(
            "API-rate equivalent $0.14"
        )
        fixture["cost_status"] = "unavailable"
        fixture["estimated_cost_usd"] = None
        page.reload()
        expect(page.locator(".session-progress-inline")).to_contain_text(
            "API-rate equivalent unavailable"
        )
        fixture["mode"] = "api_key"
        fixture["cost_status"] = "available"
        fixture["estimated_cost_usd"] = 0.14372
        page.reload()
        expect(page.locator(".session-progress-inline")).to_contain_text("Est. cost $0.14")
        fixture["mode"] = "chatgpt"
        assert running_status.locator("i").evaluate(
            "element => element === element.parentElement.lastElementChild"
        )
        project_pill_gap = page.locator(".project-identity-pill-stack").evaluate(
            "element => getComputedStyle(element).rowGap"
        )
        assert project_pill_gap == home_pill_gap, (project_pill_gap, home_pill_gap)
        project_pill_padding = page.evaluate("""() => {
          const google = getComputedStyle(document.querySelector('.project-identity-pill-stack > .project-google-signin'));
          const chatgpt = getComputedStyle(document.querySelector('.project-identity-pill-stack .api-connection > summary'));
          return [google.paddingTop, google.paddingRight, google.paddingBottom, google.paddingLeft,
            chatgpt.paddingTop, chatgpt.paddingRight, chatgpt.paddingBottom, chatgpt.paddingLeft];
        }""")
        assert project_pill_padding[:4] == project_pill_padding[4:], project_pill_padding
        assert project_pill_padding[:4] == home_pill_padding[:4], (
            project_pill_padding,
            home_pill_padding,
        )
        page.screenshot(path=str(SCREENSHOTS / "green-next-project-running.png"), full_page=True)
        page.set_viewport_size({"width": 390, "height": 844})
        expect(project_running_dot).to_be_visible()
        assert page.evaluate("document.documentElement.scrollWidth <= innerWidth")
        narrow_pill_gap = page.locator(".project-identity-pill-stack").evaluate(
            "element => getComputedStyle(element).rowGap"
        )
        assert narrow_pill_gap == home_pill_gap, (narrow_pill_gap, home_pill_gap)
        narrow_pill_padding = page.evaluate("""() => {
          const google = getComputedStyle(document.querySelector('.project-identity-pill-stack > .project-google-signin'));
          const chatgpt = getComputedStyle(document.querySelector('.project-identity-pill-stack .api-connection > summary'));
          return [google.paddingTop, google.paddingRight, google.paddingBottom, google.paddingLeft,
            chatgpt.paddingTop, chatgpt.paddingRight, chatgpt.paddingBottom, chatgpt.paddingLeft];
        }""")
        assert narrow_pill_padding[:4] == narrow_pill_padding[4:], narrow_pill_padding

        page.goto(UI_ORIGIN + "/")
        recent_tab = page.get_by_role("tab", name="Saved", exact=True)
        recent_tab.click()
        recent_panel = page.get_by_role("tabpanel", name="Saved")
        expand_recent_groups(recent_panel)
        narrow_home_gap = page.locator(".identity-pill-stack").evaluate(
            "element => getComputedStyle(element).rowGap"
        )
        assert narrow_home_gap == home_pill_gap, (narrow_home_gap, home_pill_gap)
        narrow_home_padding = page.evaluate("""() => {
          const google = getComputedStyle(document.querySelector('.identity-pill-stack > .project-google-signin'));
          const chatgpt = getComputedStyle(document.querySelector('.identity-pill-stack .api-connection > summary'));
          return [google.paddingTop, google.paddingRight, google.paddingBottom, google.paddingLeft,
            chatgpt.paddingTop, chatgpt.paddingRight, chatgpt.paddingBottom, chatgpt.paddingLeft];
        }""")
        assert narrow_home_padding[:4] == narrow_home_padding[4:], narrow_home_padding
        assert narrow_pill_padding[:4] == narrow_home_padding[:4], (
            narrow_pill_padding,
            narrow_home_padding,
        )
        assert page.evaluate("document.documentElement.scrollWidth <= innerWidth")
        project_button = (
            recent_panel.locator(".recent-open").filter(has_text=project["project"]["title"]).first
        )
        metadata = project_button.locator("xpath=../..").locator(".recent-meta-row > small > span")

        session_file.write_text(session_file.read_text().replace('"running"', '"stopped"'))
        expect(metadata).not_to_contain_text("Running", timeout=10_000)
        fcntl.flock(worker_lock.fileno(), fcntl.LOCK_UN)
    assert not page.locator("[role=alert]").count()
    print(
        "PASS real Chrome Home Saved updates inline Running status as the persisted session starts and stops"
    )
    browser.close()
