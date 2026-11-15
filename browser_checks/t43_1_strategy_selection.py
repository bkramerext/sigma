"""Real-Chrome check that strategy row enablement controls each session."""

import json
import os
from urllib.parse import quote

from playwright.sync_api import expect, sync_playwright

base = os.environ.get("SIGMA_BROWSER_BASE_URL", "http://127.0.0.1:5173").rstrip("/")
fixture = os.environ.get("SIGMA_BROWSER_FIXTURE_URL", "http://127.0.0.1:8022").rstrip("/")
with sync_playwright() as p:
    browser = p.chromium.launch(
        executable_path=os.environ.get(
            "SIGMA_BROWSER_EXECUTABLE",
            "/Applications/Google Chrome.app/Contents/MacOS/Google Chrome",
        ),
        headless=True,
        args=["--disable-web-security"],
    )
    page = browser.new_page(viewport={"width": 1440, "height": 900})
    errors = []
    render_loop_errors = []
    page.on("pageerror", lambda error: errors.append(str(error)))
    page.on(
        "console",
        lambda message: (
            render_loop_errors.append(message.text)
            if message.type == "error" and "Maximum update depth exceeded" in message.text
            else None
        ),
    )

    def forward(route):
        route.fulfill(response=route.fetch(url=route.request.url.replace(base, fixture)))

    page.route("**/api/**", forward)
    # Exercise project/session controls without a real account or provider call.
    page.route(
        "**/api/ai/connection*",
        lambda route: route.fulfill(
            status=200,
            content_type="application/json",
            body=json.dumps(
                {
                    "mode": "chatgpt",
                    "status": "connected",
                    "label": "ChatGPT connected (browser fixture)",
                    "accounts": [],
                    "active_account": None,
                }
            ),
        ),
    )
    page.route(
        "**/api/projects/proposals/config*",
        lambda route: route.fulfill(
            status=200,
            content_type="application/json",
            body=json.dumps(
                {
                    "available": True,
                    "provider": "openai",
                    "mode": "chatgpt",
                    "binding": "chatgpt:browser-fixture",
                    "project_id": "browser-fixture-project",
                    "model": "gpt-6.1-sol",
                    "reasoning_effort": "high",
                    "message": "Browser fixture; no provider call is made.",
                }
            ),
        ),
    )
    page.goto(base)
    project = page.evaluate(
        """async () => {
          const response = await fetch('/api/projects/create', {
            method: 'POST', headers: {'Content-Type':'application/json'},
            body: JSON.stringify({title:'Enabled Strategies ' + Date.now(),
              problem:'Check that enabled strategy rows define a research session.',
              investigation_type:'default', difficulty:'easy'})
          });
          if (!response.ok) throw new Error(await response.text());
          return response.json();
        }"""
    )
    path = project["path"]
    for title in ("Strategy one", "Strategy two", "Strategy three"):
        created = page.evaluate(
            """async ({path,title}) => {
              const response = await fetch('/api/projects/strategies', {
                method: 'POST', headers: {'Content-Type':'application/json'},
                body: JSON.stringify({path, title, approach:'Test the enabled strategy set.'})
              });
              if (!response.ok) throw new Error(await response.text());
              return response.json();
            }""",
            {"path": path, "title": title},
        )
    all_strategy_ids = [strategy["id"] for strategy in created["project"]["strategies"]]
    page.evaluate(
        """async path => {
          const query = new URLSearchParams({path});
          const current = await (await fetch('/api/projects/research-limits?' + query)).json();
          const response = await fetch('/api/projects/research-limits', {
            method: 'PUT', headers: {'Content-Type':'application/json'},
            body: JSON.stringify({...current, path, research_rounds:2, model_calls:4})
          });
          if (!response.ok) throw new Error(await response.text());
        }""",
        path,
    )

    page.goto(base + "/project?path=" + quote(path, safe=""))
    rows = page.locator(".strategy-list > li")
    expect(rows).to_have_count(3)
    page.wait_for_timeout(1500)
    assert not render_loop_errors, render_loop_errors
    third_row = rows.nth(2)
    page.get_by_role("button", name="Start a new research session", exact=True).click()
    expect(page.get_by_role("region", name="Sessions").get_by_role("alert")).to_contain_text(
        "The 3 enabled strategies need at least 6 model calls"
    )
    assert page.locator(".research-strategy-selection").count() == 0
    third_row.get_by_role("button", name="Disable", exact=True).click()
    expect(third_row.get_by_role("button", name="Enable", exact=True)).to_be_visible()
    enabled_strategy_ids = all_strategy_ids[:2]
    page.get_by_role("button", name="Start a new research session", exact=True).click()
    start = page.get_by_role("button", name="Start new session #1", exact=True)
    expect(start).to_be_visible()
    expect(page.locator(".research-strategy-selection")).to_have_count(0)
    expect(page.locator(".strategies-session-selection")).to_have_count(0)
    assert (
        start.locator("xpath=ancestor::div[contains(@class,'strategies-heading-right')]").count()
        == 1
    )
    expect(third_row.get_by_role("button", name="Enable", exact=True)).to_be_disabled()

    for width in (1440, 390):
        page.set_viewport_size({"width": width, "height": 900})
        assert page.evaluate("document.documentElement.scrollWidth <= window.innerWidth")
        expect(start).to_be_visible()
        expect(page.get_by_role("button", name="Cancel", exact=True)).to_be_visible()

    start_payloads = []

    def capture_start(route):
        start_payloads.append(json.loads(route.request.post_data or "{}"))
        route.fulfill(
            status=503,
            content_type="application/json",
            body=json.dumps({"error": "Captured test request; session was not started."}),
        )

    page.route("**/api/projects/research-sessions/start", capture_start)
    start.click()
    expect(page.locator(".error")).to_contain_text("Captured test request", timeout=5000)
    assert len(start_payloads) == 1, start_payloads
    assert start_payloads[0]["strategy_ids"] == enabled_strategy_ids, start_payloads[0]
    assert start_payloads[0]["strategy_id"] == enabled_strategy_ids[0]
    assert page.locator("li[data-session-id]").count() == 0
    assert not errors, errors
    assert not render_loop_errors, render_loop_errors
    print(
        "PASS Chrome strategy rows define the session set; over-budget prevention, no duplicate selector, same-slot confirmation, and no provider session"
    )
    browser.close()
