"""Focused real-Chrome layout check for multi-strategy session selection."""

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
    )
    page = browser.new_page(viewport={"width": 1440, "height": 900})
    errors = []
    page.on("pageerror", lambda error: errors.append(str(error)))
    page.route(
        "**/api/**",
        lambda route: route.fulfill(
            response=route.fetch(url=route.request.url.replace(base, fixture))
        ),
    )
    page.goto(base)
    project = page.evaluate(
        """async () => { const r=await fetch('/api/projects/create',{method:'POST',headers:{'Content-Type':'application/json'},body:JSON.stringify({title:'T43.1 Strategy Layout '+Date.now(),problem:'Check a focused mathematical question.',investigation_type:'default',difficulty:'easy'})}); if(!r.ok) throw new Error(await r.text()); return r.json(); }"""
    )
    path = project["path"]
    for title in (
        "Establish the known-mechanism frontier",
        "Find a novel temporal coupling, not another marker",
        "Design a decisive rescue-versus-block perturbation",
    ):
        result = page.evaluate(
            """async ({path,title}) => { const r=await fetch('/api/projects/strategies',{method:'POST',headers:{'Content-Type':'application/json'},body:JSON.stringify({path,title,approach:'Test the bounded approach and record evidence.'})}); if(!r.ok) throw new Error(await r.text()); return r.json(); }""",
            {"path": path, "title": title},
        )
    page.goto(base + "/project?path=" + quote(path, safe=""))
    page.get_by_role("button", name="Start a new research session", exact=True).click()
    picker = page.locator(".research-strategy-selection")
    expect(picker).to_be_visible()
    picker.locator("summary").click()
    expect(picker.get_by_role("checkbox")).to_have_count(3)

    def inspect_layout(width):
        page.set_viewport_size({"width": width, "height": 900})
        assert page.evaluate("document.documentElement.scrollWidth <= window.innerWidth")
        measurements = picker.evaluate(
            """node => { const rows=[...node.querySelectorAll('fieldset label')].map(label=>({input:label.querySelector('input').getBoundingClientRect(),title:label.querySelector('span').getBoundingClientRect()})); const box=node.getBoundingClientRect(); const actions=document.querySelector('.session-selection-actions').getBoundingClientRect(); return {rows:rows.map(row=>({inputWidth:row.input.width,titleLeft:row.title.left})),box:{x:box.x,width:box.width,bottom:box.bottom},actions:{x:actions.x,y:actions.y}}; }"""
        )
        assert all(abs(row["inputWidth"] - 16) < 1 for row in measurements["rows"]), measurements
        assert (
            max(row["titleLeft"] for row in measurements["rows"])
            - min(row["titleLeft"] for row in measurements["rows"])
            < 2
        ), measurements
        assert measurements["box"]["x"] < 80, measurements
        assert measurements["actions"]["y"] >= measurements["box"]["bottom"] - 1, measurements
        if width == 1440:
            page.screenshot(path="/tmp/sigma-t43-1-strategy-selection-desktop.png", full_page=True)
        else:
            page.screenshot(path="/tmp/sigma-t43-1-strategy-selection-mobile.png", full_page=True)

    inspect_layout(1440)
    inspect_layout(390)
    expect(page.get_by_role("button", name="Cancel", exact=True)).to_be_visible()
    assert not errors, errors
    print(
        "PASS real Chrome T43.1 strategy selection: compact aligned checkbox rows and stacked actions at 1440px and 390px; screenshots in /tmp"
    )
    browser.close()
