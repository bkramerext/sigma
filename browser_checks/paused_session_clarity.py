"""Real Chrome pause persistence and next-action guidance check."""

import os
from urllib.parse import quote

from playwright.sync_api import expect, sync_playwright

ui = os.environ.get("SIGMA_PAUSED_UI", "http://127.0.0.1:5195").rstrip("/")
fixture = os.environ.get("SIGMA_PAUSED_FIXTURE", "http://127.0.0.1:8025").rstrip("/")

with sync_playwright() as playwright:
    browser = playwright.chromium.launch(
        executable_path=os.environ.get(
            "SIGMA_BROWSER_EXECUTABLE",
            "/Applications/Google Chrome.app/Contents/MacOS/Google Chrome",
        ),
        headless=True,
    )
    context = browser.new_context(viewport={"width": 1440, "height": 900})

    def new_page():
        page = context.new_page()

        def forward(route):
            route.fulfill(
                response=route.fetch(
                    url=route.request.url.replace(
                        ui.replace("http://", ""), fixture.replace("http://", "")
                    ),
                    headers={**route.request.headers, "origin": "http://127.0.0.1:5173"},
                )
            )

        page.route("**/api/**", forward)
        return page

    page = new_page()
    page.goto(ui + "/")
    created = page.evaluate(
        "async () => { const response=await fetch('/api/projects/create',{method:'POST',headers:{'Content-Type':'application/json'},body:JSON.stringify({title:'Paused check '+crypto.randomUUID(),problem:'Inspect a bounded local research question.',investigation_type:'mathematical',difficulty:'easy'})}); return {status:response.status,body:await response.json()}; }"
    )
    assert created["status"] == 201, created
    path = created["body"]["path"]
    project_id = created["body"]["project"]["id"]
    strategy = page.evaluate(
        "async path => { const response=await fetch('/api/projects/strategies',{method:'POST',headers:{'Content-Type':'application/json'},body:JSON.stringify({path,title:'Pause clarity fixture',approach:'Inspect the saved objective and report one bounded observation.'})}); return {status:response.status,body:await response.json()}; }",
        path,
    )
    assert strategy["status"] == 201, strategy
    page.goto(ui + "/project?path=" + quote(path, safe=""))
    page.get_by_role("button", name="Start a new research session", exact=True).click()
    page.get_by_role("button", name="Start new session #1", exact=True).click()
    row = page.locator("li[data-session-id]").first
    expect(row.locator(".session-status")).to_have_text("running", timeout=15000)
    session_id = row.get_attribute("data-session-id")
    paused = page.evaluate(
        "async ({id,path}) => { const response=await fetch(`/api/projects/research-sessions/${id}/control`,{method:'POST',headers:{'Content-Type':'application/json'},body:JSON.stringify({path,action:'pause'})}); return {status:response.status,body:await response.json()}; }",
        {"id": session_id, "path": path},
    )
    assert paused["status"] == 200 and paused["body"]["status"] == "paused", paused
    url = page.url
    page.close()
    page = new_page()
    page.goto(url)
    row = page.locator(f"li[data-session-id='{session_id}']")
    expect(row.locator(".session-status")).to_have_text("paused", timeout=15000)
    guidance = row.get_by_role("note", name="Why session 1 paused and what to do next")
    expect(guidance).to_contain_text("Paused by user")
    expect(guidance).to_contain_text("Resume when you are ready")
    assert project_id == created["body"]["project"]["id"]
    page.set_viewport_size({"width": 390, "height": 844})
    assert page.evaluate("document.documentElement.scrollWidth <= innerWidth")
    row.get_by_role("button", name="Resume", exact=True).click()
    expect(row.locator(".session-status")).to_contain_text("running", timeout=15000)
    context.close()
    browser.close()

print(
    "PASS real Chrome pause/reopen/resume: recorded manual pause reason, next action, and narrow layout."
)
