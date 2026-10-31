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
    context = browser.new_context(
        viewport={"width": 1440, "height": 1000},
        accept_downloads=True,
        permissions=["clipboard-read", "clipboard-write"],
    )
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
        "async () => { const response = await fetch('/api/projects/create', {method:'POST',headers:{'Content-Type':'application/json'},body:JSON.stringify({title:'Maximum Regions Formed by Lines ' + crypto.randomUUID(),problem:'What is the maximum number of regions formed by lines?',investigation_type:'mathematical',difficulty:'easy'})}); return {status:response.status,body:await response.json()}; }"
    )
    assert created["status"] == 201, created
    path = created["body"]["path"]
    page.goto(ui + "/project?path=" + __import__("urllib.parse").parse.quote(path, safe=""))
    page.get_by_role("button", name="LaTeX research paper", exact=True).click()
    dialog = page.get_by_role("dialog", name="Academic paper using LaTeX")
    expect(dialog).to_contain_text("Create a LaTeX paper from this project’s saved research")
    expect(dialog).to_contain_text("Per project settings, AI model is gpt-6.1-sol")
    expect(dialog.locator("input[type=checkbox]")).to_have_count(3)
    expect(dialog.locator(".ai-paper-controls button")).to_have_count(1)
    for implementation_detail in (
        "Advanced options",
        "checkpoint",
        "reduction group",
        "evidence batches",
        "calls remain",
    ):
        expect(dialog).not_to_contain_text(implementation_detail)
    generate = dialog.get_by_role("button", name="Generate", exact=True)
    expect(generate).to_be_enabled(timeout=20000)
    generate.click()
    expect(dialog.get_by_role("button", name="Cancel", exact=True)).to_be_enabled(timeout=10000)
    expect(dialog.get_by_role("status")).to_be_visible()
    card = dialog.locator(".saved-paper-card").first
    expect(card).to_be_visible(timeout=60000)
    expect(dialog.get_by_role("status")).to_contain_text("Paper saved in Saved versions.")
    tex_download = card.get_by_role("link", name="Download TeX file")
    expect(tex_download).to_be_visible()
    with page.expect_download() as tex_download_event:
        tex_download.click()
    assert tex_download_event.value.suggested_filename.endswith(".tex")
    tex_response = page.evaluate(
        "async href => { const response=await fetch(href); return {status:response.status,type:response.headers.get('content-type'),disposition:response.headers.get('content-disposition'),text:await response.text()}; }",
        tex_download.get_attribute("href"),
    )
    assert tex_response["status"] == 200 and "application/x-tex" in tex_response["type"]
    assert "attachment" in tex_response["disposition"] and tex_response["text"].startswith(
        "\\documentclass"
    )
    text_download = card.get_by_role("link", name="Download text file")
    text_response = page.evaluate(
        "async href => { const response=await fetch(href); return {status:response.status,text:await response.text()}; }",
        text_download.get_attribute("href"),
    )
    assert text_response["status"] == 200 and "\n\n" in text_response["text"]
    pdf_download = card.get_by_role("link", name="Download PDF")
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
    actions = card.locator(".saved-paper-actions")
    expect(actions.get_by_role("link", name="Download TeX file")).to_be_visible()
    expect(actions.get_by_role("link", name="Download PDF")).to_be_visible()
    expect(actions.get_by_role("link", name="Open PDF in browser")).to_be_visible()
    title_line = card.locator(".saved-paper-title-line")
    title = title_line.locator(".saved-paper-title")
    expect(title_line.locator("button button")).to_have_count(0)
    title_toggle = title_line.locator(".saved-paper-title-toggle")
    expect(title).to_have_text(
        "The Maximum Number of Regions Formed by Lines: An Evidence-Bound Mathematical Framework with Explicit Construction and Unverified Claims"
    )
    title_rects = title_toggle.evaluate(
        "el => { const r=document.createRange(); r.selectNodeContents(el); return [...r.getClientRects()].map(x=>({x:x.x,y:x.y,right:x.right,height:x.height})); }"
    )
    assert len(title_rects) >= 2, title_rects
    expanded_before_copy = card.locator(".saved-paper-expand").get_attribute("aria-expanded")
    title_toggle.click()
    expect(title_toggle).to_have_attribute(
        "aria-expanded", "false" if expanded_before_copy == "true" else "true"
    )
    title_toggle.focus()
    page.keyboard.press("Space")
    expect(title_toggle).to_have_attribute("aria-expanded", expanded_before_copy)
    title_toggle.evaluate("el => el.blur()")
    page.mouse.move(1, 1)
    title_line.screenshot(path="docs/evaluations/research_qa/tex-title-normal.png")
    copy_button = title_line.get_by_role("button", name="Copy paper text")
    normal_copy_box = copy_button.bounding_box()
    normal_icon_box = copy_button.locator("svg").bounding_box()
    copy_button.click()
    copied_button = title_line.get_by_role("button", name="Copied paper text to clipboard")
    expect(copied_button).to_be_visible()
    copied_paper = page.evaluate("navigator.clipboard.readText()")
    assert copied_paper == text_response["text"]
    copied_box = copied_button.bounding_box()
    assert copied_box and copied_box["x"] >= title_rects[-1]["right"] - 1
    assert copied_box["x"] - title_rects[-1]["right"] <= 8, (copied_box, title_rects[-1])
    assert copied_box == normal_copy_box
    assert copied_button.locator("svg").bounding_box() == normal_icon_box
    assert (
        card.locator(".saved-paper-expand").get_attribute("aria-expanded") == expanded_before_copy
    )
    assert (
        abs(
            (copied_box["y"] + copied_box["height"] / 2)
            - (title_rects[-1]["y"] + title_rects[-1]["height"] / 2)
        )
        < 14
    )
    title_line.screenshot(path="docs/evaluations/research_qa/tex-title-copied.png")
    page.evaluate(
        "window.__sigmaClipboardWrite = navigator.clipboard.writeText.bind(navigator.clipboard); Object.defineProperty(navigator.clipboard, 'writeText', {configurable:true,value:() => Promise.reject(new Error('blocked'))})"
    )
    title_line.locator(".text-copy-button").click()
    expect(card.locator(".error")).to_contain_text("Could not copy the saved paper")
    page.evaluate(
        "Object.defineProperty(navigator.clipboard, 'writeText', {configurable:true,value:window.__sigmaClipboardWrite})"
    )
    dialog.get_by_role("button", name="Close").click()
    page.get_by_role("button", name="LaTeX research paper", exact=True).click()
    expect(dialog.locator(".saved-paper-card")).to_have_count(1)
    card = dialog.locator(".saved-paper-card").first
    actions = card.locator(".saved-paper-actions")
    metadata_line = card.locator(".saved-paper-meta")
    remove_button = metadata_line.get_by_role("button", name="Remove")
    title_box = title_line.bounding_box()
    actions_box = actions.bounding_box()
    metadata_box = metadata_line.locator("p").bounding_box()
    remove_box = remove_button.bounding_box()
    assert title_box and actions_box and actions_box["x"] >= title_box["x"] + title_box["width"] - 1
    assert metadata_box and remove_box and abs(metadata_box["y"] - remove_box["y"]) < 4
    action_boxes = actions.locator("a").evaluate_all(
        "items => items.map(item => item.getBoundingClientRect().y)"
    )
    assert action_boxes == sorted(action_boxes)
    with page.expect_popup() as popup_event:
        card.get_by_role("link", name="Open PDF in browser").click()
    pdf_page = popup_event.value
    assert "/pdf?" in pdf_page.url
    assert "open_in_browser=true" in pdf_page.url
    inline = page.evaluate(
        "async href => { const response=await fetch(href); return {status:response.status,disposition:response.headers.get('content-disposition')}; }",
        pdf_page.url,
    )
    assert inline["status"] == 200 and "inline" in inline["disposition"]
    pdf_page.close()
    expand = card.locator("button.saved-paper-expand")
    assert expand.get_attribute("aria-controls")
    expand.click()
    article = card.locator(".ai-paper-preview")
    expect(article).to_be_visible()
    expect(article).to_contain_text("Abstract.")
    assert not article.locator("script").count()
    expect(actions.get_by_role("link", name="Download TeX file")).to_be_visible()
    expect(actions.get_by_role("link", name="Download PDF")).to_be_visible()
    expect(actions.get_by_role("link", name="Open PDF in browser")).to_be_visible()
    expand.click()
    expect(article).to_be_hidden()
    expect(actions.get_by_role("link", name="Download TeX file")).to_be_visible()

    page.set_viewport_size({"width": 390, "height": 844})
    assert page.evaluate("document.documentElement.scrollWidth <= innerWidth")
    expect(actions).to_be_visible()
    expect(title).to_be_visible()
    mobile_title_rects = title.evaluate(
        "el => { const r=document.createRange(); r.selectNodeContents(el); return [...r.getClientRects()].map(x=>({x:x.x,y:x.y,right:x.right,height:x.height})); }"
    )
    assert len(mobile_title_rects) >= 2, mobile_title_rects
    title_line.screenshot(path="docs/evaluations/research_qa/tex-title-mobile.png")
    mobile_toggle_before_copy = expand.get_attribute("aria-expanded")
    mobile_last_line = title_toggle.evaluate(
        "el => { const r=document.createRange(); r.selectNodeContents(el); const a=[...r.getClientRects()]; const x=a.at(-1); return {right:x.right,y:x.y,height:x.height}; }"
    )
    title_line.get_by_role("button", name="Copy paper text").click()
    mobile_copied_button = title_line.get_by_role("button", name="Copied paper text to clipboard")
    expect(mobile_copied_button).to_be_visible()
    mobile_copied_box = mobile_copied_button.bounding_box()
    assert mobile_copied_box and mobile_copied_box["x"] >= mobile_last_line["right"] - 1
    assert mobile_copied_box["x"] - mobile_last_line["right"] <= 8
    assert (
        abs(
            (mobile_copied_box["y"] + mobile_copied_box["height"] / 2)
            - (mobile_last_line["y"] + mobile_last_line["height"] / 2)
        )
        < 14
    )
    assert expand.get_attribute("aria-expanded") == mobile_toggle_before_copy
    assert page.evaluate("navigator.clipboard.readText()") == text_response["text"]
    title_line.screenshot(path="docs/evaluations/research_qa/tex-title-mobile-copied.png")
    mobile_action_lefts = actions.locator("a").evaluate_all(
        "items => items.map(item => item.getBoundingClientRect().left)"
    )
    assert max(mobile_action_lefts) - min(mobile_action_lefts) < 1
    page.set_viewport_size({"width": 1440, "height": 1000})
    card.get_by_role("button", name="Remove").scroll_into_view_if_needed()
    card.get_by_role("button", name="Remove").click()
    expect(card.get_by_role("group", name="Confirm removal of")).to_be_visible()
    card.get_by_role("button", name="Cancel").click()
    expect(card).to_be_visible()
    card.get_by_role("button", name="Remove").click()
    card.locator(".saved-paper-confirm").get_by_role("button", name="Confirm", exact=True).click()
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
    "PASS real Chrome saved-paper library: TeX text clipboard success/failure, TeX/PDF payloads, persistent actions, new-tab inline PDF, mobile layout, and confirmed version deletion."
)
