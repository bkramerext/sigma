"""Real Chrome A17 session workflow against the isolated provider fixture."""

import os
import re
from pathlib import Path
from urllib.parse import urlencode

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
    page.on("pageerror", lambda error: errors.append(str(error)))
    page.route(
        "**/api/**",
        lambda route: route.continue_(
            url=route.request.url.replace("127.0.0.1:5173", "127.0.0.1:8002")
        ),
    )
    page.goto("http://127.0.0.1:5173")
    page.get_by_role("tab", name="Samples", exact=True).click()
    page.get_by_role("tabpanel", name="Samples", exact=True).get_by_role(
        "button", name="Open Counting Constrained Binary Strings"
    ).click()
    expect(
        page.get_by_role(
            "heading", name=re.compile("Counting Constrained Binary Strings - Working")
        )
    ).to_be_visible()
    expect(page.locator(".strategy-row")).to_have_count(0)
    path = page.evaluate("new URL(location.href).searchParams.get('path')")
    result = page.evaluate(
        """async path => {
      const response = await fetch('/api/projects/strategies', { method: 'POST', headers: {'Content-Type':'application/json'}, body: JSON.stringify({path, title:'Saved research approach', approach:'Derive a recurrence and inspect boundary cases.', summary:'Use a terminal decomposition.'}) });
      return {status: response.status, body: await response.json()};
    }""",
        path,
    )
    assert result["status"] == 201, result
    page.reload()
    expect(page.locator(".strategy-row")).to_have_count(1)
    page.locator(".strategy-detail > summary").click()
    page.get_by_role("button", name="Investigate", exact=True).click()
    consent = page.get_by_role("group", name="Confirm research session")
    expect(consent).to_contain_text("Up to 3 cycles and 6 provider calls")
    expect(consent).to_contain_text("Usage may accrue")
    consent.get_by_role("button", name="Start investigation").click()
    panel = page.locator(".research-session")
    expect(panel).to_contain_text("Investigation · completed", timeout=15000)
    expect(panel).to_contain_text("6/6 calls · 3/3 cycles")
    expect(panel.locator(".research-artifacts li")).to_have_count(3)
    expect(panel).to_contain_text("Independent fixture review for cycle 1")
    expect(panel).to_contain_text("Unverified research note")
    project_file = Path(path) / "project.json"
    before = project_file.read_bytes()
    session_id = page.evaluate(
        "async path => (await (await fetch('/api/projects/research-sessions?' + new URLSearchParams({path}))).json()).sessions[0].id",
        path,
    )
    page.goto("http://127.0.0.1:5173")
    page.goto(f"http://127.0.0.1:5173/project?{urlencode({'path': path})}")
    page.locator(".strategy-detail > summary").click()
    expect(page.locator(".research-session")).to_contain_text("Investigation · completed")
    restored = page.evaluate(
        "async ({path, id}) => await (await fetch('/api/projects/research-sessions/' + id + '?' + new URLSearchParams({path}))).json()",
        {"path": path, "id": session_id},
    )
    assert len(restored["artifacts"]) == 3
    assert project_file.read_bytes() == before

    async_add = """async ({path, title}) => {
      const response = await fetch('/api/projects/strategies', { method:'POST', headers:{'Content-Type':'application/json'}, body:JSON.stringify({path, title, approach:'A separate bounded fixture strategy.', summary:'Exercise session controls.'}) });
      return response.status;
    }"""
    assert page.evaluate(async_add, {"path": path, "title": "Stop fixture strategy"}) == 201
    page.reload()
    page.locator(".strategy-detail > summary").nth(1).click()
    page.locator(".research-session").nth(1).get_by_role("button", name="Investigate", exact=True).click()
    page.locator(".research-session").nth(1).get_by_role("button", name="Start investigation").click()
    stop_panel = page.locator(".research-session").nth(1)
    expect(stop_panel).to_contain_text("Investigation · running", timeout=5000)
    stop_panel.get_by_role("button", name="Stop", exact=True).click()
    expect(stop_panel).to_contain_text("Investigation · stopped")

    assert page.evaluate(async_add, {"path": path, "title": "Failure fixture strategy"}) == 201
    page.reload()
    page.locator(".strategy-detail > summary").nth(2).click()
    failed_panel = page.locator(".research-session").nth(2)
    failed_panel.get_by_role("button", name="Investigate", exact=True).click()
    failed_panel.get_by_role("button", name="Start investigation").click()
    expect(failed_panel).to_contain_text("Investigation · failed", timeout=10000)
    expect(page.locator(".request-toast")).to_have_count(1)
    page.get_by_role("button", name="Dismiss request error").click()
    page.set_viewport_size({"width": 390, "height": 844})
    assert page.evaluate("document.documentElement.scrollWidth <= window.innerWidth")
    assert not errors, errors
    print(
        "PASS real Chrome A17: explicit consent, three-cycle research, artifacts/reopen, stop, provider failure toast/recovery, mobile overflow and unchanged strategy"
    )
    page.unroute_all(behavior="ignoreErrors")
    browser.close()
