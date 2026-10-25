"""Real-Chrome launch check for the minimal LaTeX paper dialog."""

import os
import re
from urllib.parse import quote

from playwright.sync_api import expect, sync_playwright

UI_ORIGIN = os.environ.get("SIGMA_T45_UI_ORIGIN", "http://127.0.0.1:5181")
FIXTURE_PORT = os.environ.get("SIGMA_T45_FIXTURE_PORT", "8015")

with sync_playwright() as playwright:
    browser = playwright.chromium.launch(
        executable_path=os.environ.get(
            "SIGMA_BROWSER_EXECUTABLE",
            "/Applications/Google Chrome.app/Contents/MacOS/Google Chrome",
        ),
        headless=True,
    )
    page = browser.new_page(viewport={"width": 1440, "height": 1000})
    errors: list[str] = []
    failed_once = [True]
    paper_posts = [0]
    long_form_preflights: list[bool] = []
    page.on("pageerror", lambda error: errors.append(str(error)))

    def forward(route):
        request = route.request
        if request.method == "POST" and request.url.split("?", 1)[0].endswith(
            "/api/projects/papers"
        ):
            paper_posts[0] += 1
            if failed_once[0]:
                failed_once[0] = False
                route.fulfill(
                    status=503,
                    json={"error": "Simulated temporary paper service failure."},
                )
                return
        response = route.fetch(
            url=request.url.replace(
                UI_ORIGIN.replace("http://", ""), f"127.0.0.1:{FIXTURE_PORT}"
            ),
            headers={**request.headers, "origin": "http://127.0.0.1:5173"},
        )
        if "/api/projects/papers/preflight?" in request.url and response.ok:
            long_form_preflights.append(response.json()["long_form"])
        route.fulfill(response=response)

    page.context.route("**/api/**", forward)
    page.goto(UI_ORIGIN + "/")
    created = page.evaluate(
        """async () => {
          const body = {title: `Automatic long-form paper UI ${Date.now()}`,
            problem: 'Investigate this bounded research question. ' + 'saved evidence '.repeat(1300),
            investigation_type: 'mathematical', difficulty: 'easy'};
          const response = await fetch('/api/projects/create', {method:'POST',
            headers:{'Content-Type':'application/json'}, body:JSON.stringify(body)});
          const created = await response.json();
          if (response.ok) {
            for (let index = 1; index <= 2; index++) {
              const strategy = await fetch('/api/projects/strategies', {method:'POST',
                headers:{'Content-Type':'application/json'}, body:JSON.stringify({
                  path:created.path, title:`Long evidence strategy ${index}`,
                  approach:'A saved approach with relevant evidence. '.repeat(1100)} )});
              if (!strategy.ok) return {status:strategy.status, body:await strategy.json()};
            }
          }
          return {status:response.status, body:created};
        }"""
    )
    assert created["status"] == 201, created
    page.goto(UI_ORIGIN + "/project?path=" + quote(created["body"]["path"], safe=""))
    page.get_by_role("button", name="LaTeX research paper", exact=True).click()
    dialog = page.get_by_role("dialog", name="Academic paper using LaTeX")
    expect(dialog).to_be_visible()
    assert dialog.evaluate("element => element.contains(document.activeElement)")
    expect(dialog.get_by_role("button", name="Close", exact=True)).to_be_visible()
    expect(dialog).to_contain_text(
        "Create a LaTeX paper from this project’s saved research"
    )
    expect(dialog).to_contain_text("AI-generated and has not been independently verified")
    expect(dialog).to_contain_text("Selected model:")
    expect(dialog.locator("input[type=checkbox]")).to_have_count(0)
    expect(dialog.locator(".ai-paper-controls button")).to_have_count(1)
    for implementation_detail in (
        "Advanced options",
        "checkpoint",
        "reduction group",
        "evidence batches",
        "provider calls",
        "Generation bounds",
    ):
        expect(dialog).not_to_contain_text(implementation_detail)

    page.set_viewport_size({"width": 390, "height": 844})
    expect(dialog).to_be_visible()
    assert page.evaluate("document.documentElement.scrollWidth <= innerWidth")
    page.set_viewport_size({"width": 1440, "height": 1000})

    generate = dialog.get_by_role("button", name="Generate paper", exact=True)
    expect(generate).to_be_enabled(timeout=20000)
    generate.click()
    expect(dialog.get_by_role("alert")).to_contain_text(
        "Simulated temporary paper service failure.", timeout=10000
    )
    expect(dialog.get_by_role("alert")).to_contain_text(
        "provider request may have completed or consumed allowance"
    )
    assert paper_posts[0] == 1, paper_posts
    expect(generate).to_be_enabled()

    generate.click()
    expect(dialog.get_by_role("button", name="Generating paper…")).to_be_disabled(
        timeout=10000
    )
    expect(dialog.locator(".ai-paper-status")).to_be_visible()
    card = dialog.locator(".saved-paper-card").first
    expect(card).to_be_visible(timeout=60000)
    expect(dialog.locator(".ai-paper-status")).to_contain_text(
        "Paper saved in Saved versions."
    )
    assert long_form_preflights and all(long_form_preflights), long_form_preflights
    expect(card).to_contain_text("A Long-Form Experimental Research Synthesis")

    expand = card.locator("button.saved-paper-expand")
    expand.click()
    preview = card.locator(".ai-paper-preview")
    expect(preview).to_be_visible()
    expect(preview).to_contain_text("Experimental question and prior context")
    pdf_link = card.get_by_role("link", name="Open PDF in browser")
    expect(pdf_link).to_be_visible()
    with page.expect_popup() as popup_info:
        pdf_link.click()
    pdf_page = popup_info.value
    expect(pdf_page).to_have_url(re.compile(r"/api/projects/papers/[^/]+/pdf\?"))
    pdf_response = page.evaluate(
        "async href => { const response=await fetch(href); return {status:response.status, type:response.headers.get('content-type'), disposition:response.headers.get('content-disposition')}; }",
        pdf_page.url,
    )
    assert pdf_response["status"] == 200 and "application/pdf" in pdf_response["type"]
    assert pdf_response["disposition"].startswith("inline;")
    pdf_page.close()

    expect(dialog.get_by_role("link", name="Download TeX file")).to_be_visible()
    expect(dialog.get_by_role("link", name="Download PDF")).to_be_visible()
    expect(dialog.get_by_role("link", name="Open PDF in browser")).to_be_visible()
    assert not errors, errors
    dialog.get_by_role("button", name="Close", exact=True).click()
    expect(dialog).not_to_be_visible()
    expect(page.get_by_role("button", name="LaTeX research paper", exact=True)).to_be_focused()
    page.context.unroute_all(behavior="ignoreErrors")
    browser.close()

print(
    "PASS real Chrome T45: minimal desktop/mobile dialog, automatic long-form selection, no automatic retry after failure, active and success feedback, saved versions and inline PDF."
)
