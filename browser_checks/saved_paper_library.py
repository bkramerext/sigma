"""Focused real-Chrome acceptance for saved AI paper versions."""

import os

from playwright.sync_api import expect, sync_playwright

ui = os.environ.get("SIGMA_PAPER_UI", "http://127.0.0.1:5174").rstrip("/")
fixture = os.environ.get("SIGMA_PAPER_FIXTURE", "http://127.0.0.1:8012").rstrip("/")

with sync_playwright() as playwright:
    browser = playwright.chromium.launch(
        executable_path=os.environ.get(
            "SIGMA_BROWSER_EXECUTABLE",
            "/Applications/Google Chrome.app/Contents/MacOS/Google Chrome",
        ),
        headless=True,
    )
    context = browser.new_context(viewport={"width": 1440, "height": 1000}, accept_downloads=True)
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

    context.route("**/api/**", forward)
    page.goto(ui + "/")
    created = page.evaluate(
        "async () => { const response = await fetch('/api/projects/create', {method:'POST',headers:{'Content-Type':'application/json'},body:JSON.stringify({title:'Paper library ' + crypto.randomUUID(),problem:'Describe the saved research question without inventing results.',investigation_type:'mathematical',difficulty:'easy'})}); return {status:response.status,body:await response.json()}; }"
    )
    assert created["status"] == 201, created
    path = created["body"]["path"]
    page.goto(ui + "/project?path=" + __import__("urllib.parse").parse.quote(path, safe=""))
    page.get_by_role("button", name="LaTeX research paper", exact=True).click()
    dialog = page.get_by_role("dialog", name="Academic paper using LaTeX")
    generate = dialog.get_by_role("button", name="Generate paper", exact=True)
    expect(generate).to_be_enabled(timeout=20000)
    generate.click()
    card = dialog.locator(".saved-paper-card").first
    expect(card).to_be_visible(timeout=60000)
    expect(card.get_by_role("link", name="Download .txt")).to_be_visible()
    pdf_download = card.get_by_role("link", name="Download .pdf")
    expect(pdf_download).to_be_visible()
    with page.expect_download() as download_event:
        pdf_download.click()
    downloaded = download_event.value
    assert downloaded.suggested_filename.endswith(".pdf")
    paper_id = page.evaluate(
        "href => new URL(href, location.href).pathname.split('/').at(-2)",
        pdf_download.get_attribute("href"),
    )
    pdf_response = page.evaluate(
        "async href => { const response=await fetch(href); return {status:response.status,type:response.headers.get('content-type'),disposition:response.headers.get('content-disposition'),bytes:[...new Uint8Array(await response.arrayBuffer()).slice(0,5)]}; }",
        pdf_download.get_attribute("href"),
    )
    assert pdf_response["status"] == 200 and "application/pdf" in pdf_response["type"]
    assert "attachment" in pdf_response["disposition"] and pdf_response["bytes"] == [
        37,
        80,
        68,
        70,
        45,
    ]
    txt_link = card.get_by_role("link", name="Download .txt")
    txt_response = page.evaluate(
        "async href => { const response=await fetch(href); return {status:response.status,type:response.headers.get('content-type'),disposition:response.headers.get('content-disposition'),text:await response.text()}; }",
        txt_link.get_attribute("href"),
    )
    assert txt_response["status"] == 200 and "text/plain" in txt_response["type"]
    assert "attachment" in txt_response["disposition"] and txt_response["text"].strip()
    with page.expect_popup() as popup_event:
        card.get_by_role("link", name="Open .pdf in browser").click()
    pdf_page = popup_event.value
    assert "/pdf?" in pdf_page.url
    assert "open_in_browser=true" in pdf_page.url
    inline = page.evaluate(
        "async href => { const response=await fetch(href); return {status:response.status,disposition:response.headers.get('content-disposition')}; }",
        pdf_page.url,
    )
    assert inline["status"] == 200 and "inline" in inline["disposition"]
    pdf_page.close()
    expand = card.get_by_role("button", name="Read saved paper")
    assert expand.get_attribute("aria-controls")
    expand.click()
    article = card.locator(".ai-paper-preview")
    expect(article).to_be_visible()
    expect(article).to_contain_text("Abstract.")
    assert not article.locator("script").count()

    page.set_viewport_size({"width": 390, "height": 844})
    assert page.evaluate("document.documentElement.scrollWidth <= innerWidth")
    actions = card.locator(".saved-paper-actions")
    assert actions.is_visible()
    card.get_by_role("button", name="Remove").click()
    expect(card.get_by_role("group", name="Confirm removal of")).to_be_visible()
    card.get_by_role("button", name="Cancel").click()
    expect(card).to_be_visible()
    card.get_by_role("button", name="Remove").click()
    card.get_by_role("button", name="Confirm remove").click()
    expect(dialog.locator(".saved-paper-card")).to_have_count(0)
    missing = page.evaluate(
        "async ({path,id}) => (await fetch(`/api/projects/papers/${id}?${new URLSearchParams({path})}`)).status",
        {"path": path, "id": paper_id},
    )
    assert missing == 400
    assert not page.locator(".error").count()
    context.close()
    browser.close()

print(
    "PASS real Chrome saved-paper library: TXT/PDF headers and payloads, new-tab inline PDF, accessible saved-content disclosure, mobile layout, confirmed version deletion."
)
