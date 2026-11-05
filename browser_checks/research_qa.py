"""Real Chrome Q/A workflow using the deterministic local provider fixture."""

import os
import re
from pathlib import Path

from playwright.sync_api import expect, sync_playwright

UI = os.environ.get("SIGMA_QA_UI", "http://127.0.0.1:5174").rstrip("/")
OUT = Path("docs/evaluations/research_qa")
OUT.mkdir(parents=True, exist_ok=True)

with sync_playwright() as playwright:
    browser = playwright.chromium.launch(
        executable_path=os.environ.get(
            "SIGMA_BROWSER_EXECUTABLE",
            "/Applications/Google Chrome.app/Contents/MacOS/Google Chrome",
        ),
        headless=True,
    )
    context = browser.new_context(
        viewport={"width": 1440, "height": 1000}, permissions=["clipboard-read", "clipboard-write"]
    )
    page = context.new_page()
    errors = []
    fail_archive_reads = [0]
    missing_archive_reads = [0]
    page.on("pageerror", lambda error: errors.append(str(error)))

    def forward(route):
        if "/api/projects/research-qa?" in route.request.url and missing_archive_reads[0]:
            missing_archive_reads[0] -= 1
            route.fulfill(
                status=200,
                content_type="application/json",
                body='{"answers":[],"archive_available":false}',
            )
            return
        if "/api/projects/research-qa?" in route.request.url and fail_archive_reads[0]:
            fail_archive_reads[0] -= 1
            route.fulfill(
                status=503,
                content_type="application/json",
                body='{"error":"fixture archive unavailable"}',
            )
            return
        route.continue_()

    # Intercept only the two intentional archive failure injections. All other
    # requests, especially the browser-presence SSE stream, use Vite's proxy.
    context.route(re.compile(r"/api/projects/research-qa\?"), forward)
    page.goto(UI + "/")
    welcome = page.locator("#invitation-welcome-dialog")
    if welcome.count() and welcome.is_visible():
        welcome.get_by_role("button", name="Let's get started", exact=True).click()
        expect(welcome).to_be_hidden()
    samples = page.get_by_role("tab", name="Samples", exact=True)
    samples.click()
    mathematics = page.locator("details.sample-type-group").filter(has_text="Mathematics")
    mathematics.evaluate(
        "node => { node.open = true; localStorage.setItem('sigma.home.sampleGroup:mathematical', 'true'); }"
    )
    page.locator("button.sample-open:visible").filter(
        has_text="Maximum Regions Formed by Lines"
    ).click()
    page.wait_for_url("**/project?*")
    path = page.evaluate("new URL(location.href).searchParams.get('path')")
    page.wait_for_function(
        """async path => {
            const response = await fetch('/api/__fixture/browser-presence?' + new URLSearchParams({path}));
            return response.ok && (await response.json()).connected;
        }""",
        arg=path,
        timeout=20000,
    )
    page.locator(".sessions-pane-heading").get_by_role("button", name="New", exact=True).click()
    page.locator(".sessions-pane-heading").get_by_role("button", name="Start Session 1").click()
    expect(page.locator("li[data-session-id]").first.locator(".session-status")).to_have_text(
        "ended", timeout=30000
    )
    audit_before = page.evaluate(
        "async path => (await (await fetch('/api/projects/audit?' + new URLSearchParams({path}))).json())",
        path,
    )

    qa_button = page.get_by_role("button", name="Research Q/A", exact=True)
    expect(qa_button).to_be_visible()
    assert (
        page.evaluate("el => parseFloat(getComputedStyle(el).fontSize)", qa_button.element_handle())
        >= 16
    )
    # The retired Lean action must not be reintroduced to the project header.
    expect(
        page.get_by_role("button", name="Generate Lean proof (coming soon)", exact=True)
    ).to_have_count(0)
    expect(page.locator(".papers-pane").get_by_role("heading", name="Papers")).to_be_visible()
    page.screenshot(path=str(OUT / "research-qa-toolbar.png"), full_page=False)
    qa_button.click()
    dialog = page.get_by_role("dialog", name="Research Q/A")
    expect(dialog).to_contain_text("Ask a question about the research performed in this project")
    expect(dialog.locator("input[type=checkbox]")).to_have_count(0)
    expect(dialog.get_by_role("button", name="Ask", exact=True)).to_be_disabled(timeout=20000)
    # Submit is inline with Question; textarea remains on the next line.
    heading = dialog.locator(".research-qa-question-heading")
    expect(heading.get_by_text("Question", exact=True)).to_be_visible()
    expect(heading.get_by_role("button", name="Ask", exact=True)).to_be_visible()
    heading_bounds = heading.bounding_box()
    submit_bounds = heading.get_by_role("button", name="Ask", exact=True).bounding_box()
    question_bounds = heading.get_by_text("Question", exact=True).bounding_box()
    assert heading_bounds and submit_bounds and question_bounds
    assert abs(submit_bounds["y"] - question_bounds["y"]) <= 6
    assert submit_bounds["x"] > question_bounds["x"] + question_bounds["width"]
    state_before = page.evaluate(
        "async () => (await (await fetch('/api/__fixture/qa-state')).json())"
    )
    page.evaluate(
        "async () => fetch('/api/__fixture/qa-control', {method:'POST',headers:{'Content-Type':'application/json'},body:JSON.stringify({delay_seconds:2})})"
    )
    question = "Can this saved research be used to explain the relationship between the investigators’ evidence, the skeptic’s objections, and the unresolved conclusions in this project?"
    dialog.get_by_label("Question").fill(question)
    dialog.get_by_role("button", name="Ask", exact=True).click()
    expect(dialog.get_by_role("button", name="Answering")).to_be_disabled()
    expect(dialog.get_by_role("button", name="Answering")).to_contain_text("⌛ Answering…")
    dialog.get_by_role("button", name="Cancel", exact=True).click()
    expect(dialog.get_by_role("alert")).to_have_count(0)
    expect(dialog.get_by_role("button", name="Ask", exact=True)).to_be_enabled()
    dialog.get_by_role("button", name="Close", exact=True).click()
    expect(dialog).not_to_be_visible()
    page.get_by_role("button", name="Research Q/A", exact=True).click()
    dialog = page.get_by_role("dialog", name="Research Q/A")
    expect(dialog.get_by_role("textbox", name="Question", exact=True)).to_have_value(question)
    expect(dialog.get_by_role("group", name="Recover interrupted Q/A request")).to_have_count(0)
    ask_button = dialog.get_by_role("button", name="Ask", exact=True)
    expect(ask_button).to_be_enabled()
    fail_archive_reads[0] = 1
    ask_button.click()
    expect(dialog.get_by_role("alert")).to_contain_text("fixture archive unavailable")
    expect(ask_button).to_be_enabled()
    saved_answers = []
    for _ in range(120):
        saved_answers = page.evaluate(
            "async path => (await (await fetch('/api/projects/research-qa?' + new URLSearchParams({path}))).json()).answers",
            path,
        )
        if any(answer["question"] == question for answer in saved_answers):
            break
        page.wait_for_timeout(250)
    assert any(answer["question"] == question for answer in saved_answers), saved_answers
    # A cancelled browser fetch can still have finished at the provider.
    # Ask checks the durable request ID before making a second paid call.
    ask_button.click()
    expect(dialog.get_by_text("Answer saved.", exact=True)).to_have_count(0)
    expect(dialog.locator(".saved-paper-card").first).to_contain_text(question)
    state_after_cancel = page.evaluate(
        "async () => (await (await fetch('/api/__fixture/qa-state')).json())"
    )
    assert state_after_cancel["started"] == state_before["started"] + 1

    failed_question = "After the repeated provider failure, can the saved research still support a useful answer about the investigators’ evidence and the skeptic’s unresolved objections?"
    page.evaluate(
        "async () => fetch('/api/__fixture/qa-control', {method:'POST',headers:{'Content-Type':'application/json'},body:JSON.stringify({fail_next:1})})"
    )
    dialog.get_by_role("textbox", name="Question", exact=True).fill(failed_question)
    dialog.get_by_role("button", name="Ask", exact=True).click()
    expect(dialog.get_by_role("alert")).to_be_visible(timeout=30000)
    expect(dialog.get_by_role("group", name="Recover interrupted Q/A request")).to_have_count(0)
    expect(dialog.get_by_role("group", name="Confirm a fresh Q/A request")).to_have_count(0)
    ask_button = dialog.get_by_role("button", name="Ask", exact=True)
    expect(ask_button).to_be_enabled()
    failed_state_before_retry = page.evaluate(
        "async () => (await (await fetch('/api/__fixture/qa-state')).json())"
    )
    # Failure display is a single dismissible toast; dismissal is not a retry.
    dialog.get_by_role("button", name="Dismiss").click()
    expect(dialog.get_by_role("alert")).to_have_count(0)
    expect(ask_button).to_be_enabled()
    fail_archive_reads[0] = 1
    ask_button.click()
    expect(dialog.get_by_role("alert")).to_contain_text("fixture archive unavailable")
    expect(ask_button).to_be_enabled()
    failed_state_after_archive_error = page.evaluate(
        "async () => (await (await fetch('/api/__fixture/qa-state')).json())"
    )
    assert failed_state_after_archive_error["started"] == failed_state_before_retry["started"]
    ask_button.click()
    expect(dialog.get_by_role("button", name="Answering")).to_be_disabled()
    expect(dialog.locator(".saved-paper-card").first).to_contain_text(
        failed_question, timeout=30000
    )
    state_after_retry = page.evaluate(
        "async () => (await (await fetch('/api/__fixture/qa-state')).json())"
    )
    assert state_after_retry["started"] == state_after_cancel["started"] + 2

    card = dialog.locator(".saved-paper-card").first
    expect(card).to_be_visible(timeout=30000)
    question = failed_question
    title_line = card.locator(".saved-paper-title-line")
    expect(title_line.locator(".saved-paper-title")).to_have_text(question)
    expect(title_line.locator(".saved-paper-title")).to_have_count(1)
    expect(title_line.locator("button button")).to_have_count(0)
    expanded_before_copy = card.locator(".saved-paper-expand").get_attribute("aria-expanded")
    title_toggle = title_line.locator(".saved-paper-title-toggle")
    title_toggle.click()
    expect(title_toggle).to_have_attribute(
        "aria-expanded", "false" if expanded_before_copy == "true" else "true"
    )
    title_toggle.focus()
    page.keyboard.press("Enter")
    expect(title_toggle).to_have_attribute("aria-expanded", expanded_before_copy)
    title_rects = title_toggle.evaluate(
        "el => { const r=document.createRange(); r.selectNodeContents(el); return [...r.getClientRects()].map(x=>({x:x.x,y:x.y,right:x.right,height:x.height})); }"
    )
    assert len(title_rects) >= 2, title_rects
    title_toggle.evaluate("el => el.blur()")
    page.mouse.move(1, 1)
    title_line.screenshot(path=str(OUT / "research-qa-title-normal.png"))
    markdown_icon = title_line.get_by_role("button", name="Render answer as Markdown")
    expect(markdown_icon).to_be_visible()
    expect(markdown_icon).to_have_attribute("data-tooltip", "Convert to Markdown")
    markdown_box = markdown_icon.bounding_box()
    assert markdown_box and markdown_icon.locator("svg.markdown-logo").count() == 1
    normal_copy_button = title_line.get_by_role("button", name="Copy Markdown answer")
    assert (
        normal_copy_button.bounding_box()["x"] - (markdown_box["x"] + markdown_box["width"]) == 12
    )
    normal_copy_box = normal_copy_button.bounding_box()
    normal_icon_box = normal_copy_button.locator("svg").bounding_box()
    normal_icon_bounds = normal_copy_button.locator("svg").evaluate(
        "svg => { const b=svg.getBBox(); return {x:b.x,y:b.y,right:b.x+b.width,bottom:b.y+b.height,overflow:getComputedStyle(svg).overflow}; }"
    )
    assert normal_icon_bounds["x"] >= 0 and normal_icon_bounds["y"] >= 0
    assert normal_icon_bounds["right"] <= 24 and normal_icon_bounds["bottom"] <= 24
    assert normal_icon_bounds["overflow"] == "visible"
    title_line.get_by_role("button", name="Copy Markdown answer").click()
    expect(card.get_by_role("button", name="Copied Markdown answer to clipboard")).to_be_visible(
        timeout=3000
    )
    copied_icon_box = title_line.get_by_role(
        "button", name="Copied Markdown answer to clipboard"
    ).bounding_box()
    last_title_rect = title_rects[-1]
    assert copied_icon_box and copied_icon_box["x"] > markdown_box["x"]
    assert markdown_box["x"] >= last_title_rect["right"] - 1, (markdown_box, last_title_rect)
    assert abs(markdown_box["x"] - last_title_rect["right"] - 14) <= 2, (
        markdown_box,
        last_title_rect,
    )
    markdown_glyph = markdown_icon.locator("svg.markdown-logo").bounding_box()
    assert markdown_glyph and normal_icon_box
    left_glyph_gap = markdown_glyph["x"] - last_title_rect["right"]
    right_glyph_gap = normal_icon_box["x"] - (markdown_glyph["x"] + markdown_glyph["width"])
    assert abs(left_glyph_gap - right_glyph_gap) <= 3, (
        left_glyph_gap,
        right_glyph_gap,
    )
    assert normal_copy_box and normal_icon_box
    assert copied_icon_box == normal_copy_box
    assert (
        title_line.get_by_role("button", name="Copied Markdown answer to clipboard")
        .locator("svg")
        .bounding_box()
        == normal_icon_box
    )
    assert (
        abs(
            (copied_icon_box["y"] + copied_icon_box["height"] / 2)
            - (last_title_rect["y"] + last_title_rect["height"] / 2)
        )
        < 14
    )
    expect(card.locator(".saved-paper-expand")).to_have_attribute(
        "aria-expanded", expanded_before_copy
    )
    title_line.screenshot(path=str(OUT / "research-qa-title-copied.png"))
    if expanded_before_copy != "true":
        card.locator(".saved-paper-expand").click()
    expect(card.locator(".saved-paper-expand")).to_have_attribute("aria-expanded", "true")
    preview = card.locator(".ai-paper-preview")
    expect(preview).to_contain_text("The saved research answers")
    assert preview.evaluate("el => getComputedStyle(el).paddingBottom") == "40px"
    assert (
        dialog.locator(".research-qa-library").evaluate("el => getComputedStyle(el).paddingBottom")
        == "40px"
    )
    assert (
        dialog.locator(".settings-body.ai-paper-body").evaluate(
            "el => getComputedStyle(el).paddingBottom"
        )
        == "40px"
    )
    preview.evaluate("el => { el.scrollTop = el.scrollHeight; }")
    assert preview.evaluate("el => el.scrollHeight - el.clientHeight - el.scrollTop < 2"), (
        "The last answer content must be reachable through its scrollport"
    )
    citation = card.locator(".ai-paper-preview a").filter(has_text="Session #1").first
    expect(citation).to_be_visible()
    citation_url = citation.get_attribute("href")
    assert "reveal_session=" in citation_url
    audit_after = page.evaluate(
        "async path => (await (await fetch('/api/projects/audit?' + new URLSearchParams({path}))).json())",
        path,
    )
    assert len(audit_after["research_sessions"]) == len(audit_before["research_sessions"]), (
        "Q/A must not create research sessions"
    )

    expect(
        card.locator(".research-qa-answer-heading").get_by_role("heading", name="Answer")
    ).to_be_visible()
    copied = page.evaluate("navigator.clipboard.readText()")
    assert copied.startswith("# Research Q/A") and "## Question" in copied and question in copied
    assert (
        "## Answer" in copied
        and "The saved research answers" in copied
        and "## Sources" in copied
        and "Session #1" in copied
    )
    expect(card.locator(".research-qa-version")).to_have_count(0)
    expect(card.locator(".research-qa-technical")).to_have_count(0)
    page.evaluate(
        "Object.defineProperty(navigator.clipboard, 'writeText', {configurable:true,value:() => Promise.reject(new Error('blocked'))})"
    )
    title_line.get_by_role("button", name="Copied Markdown answer to clipboard").click()
    expect(dialog.get_by_role("alert")).to_contain_text("Clipboard access failed")

    # The Markdown control formats this saved answer with the same AI text
    # conversion path as Project and Strategy, then toggles the cached view.
    expect(card.locator(".research-qa-answer-plain")).to_contain_text("The saved research answers")
    conversion_requests = []
    page.on(
        "request",
        lambda request: (
            conversion_requests.append(request.url)
            if "/api/projects/text/convert" in request.url
            else None
        ),
    )
    markdown_icon.click()
    expect(title_line.get_by_role("status")).to_have_text("Formatting with AI…")
    expect(title_line.get_by_role("button", name="Show plain answer")).to_be_visible(timeout=30000)
    expect(title_line.get_by_role("status")).to_have_count(0)
    expect(card.locator(".outcome-markdown")).to_contain_text("The saved research answers")
    title_line.get_by_role("button", name="Show plain answer").click()
    expect(card.locator(".research-qa-answer-plain")).to_contain_text("The saved research answers")
    title_line.get_by_role("button", name="Render answer as Markdown").click()
    expect(card.locator(".outcome-markdown")).to_contain_text("The saved research answers")
    # The conversion is saved on the answer, not recomputed on a second toggle.
    stored = page.evaluate(
        "async path => (await (await fetch('/api/projects/research-qa?' + new URLSearchParams({path}))).json()).answers",
        path,
    )
    assert stored[0]["markdown_answer"]
    assert len(conversion_requests) == 1, conversion_requests

    with page.expect_popup() as popup:
        card.get_by_role("button", name="Open in browser").click()
    browser_page = popup.value
    expect(browser_page.get_by_role("heading", name="Research Q/A")).to_be_visible()
    expect(browser_page.get_by_role("heading", name="Evidence-based answer")).to_be_visible()
    expect(browser_page.locator(".katex")).to_be_visible()
    expect(browser_page.locator("main")).to_contain_text("Created:")
    expect(browser_page.locator("main")).to_contain_text("Model:")
    expect(browser_page.locator("main")).to_contain_text("thinking")
    expect(browser_page.locator("main")).not_to_contain_text("Generation duration:")
    expect(browser_page.locator("main")).not_to_contain_text("Research version:")
    expect(browser_page.locator("main")).not_to_contain_text("Thinking level:")
    forged_link = browser_page.locator("main a").filter(has_text="forged citation")
    assert forged_link.count() <= 1 and (
        not forged_link.count() or forged_link.first.get_attribute("href") in {None, ""}
    )
    assert browser_page.evaluate("window.__sigmaInjected !== true")
    expect(browser_page.get_by_text(question, exact=True)).to_be_visible()
    citation_links = browser_page.locator("main ul a")
    # Different questions select different subsets of frozen research. Test
    # the links actually returned, never demand five fixed citation categories.
    link_specs = citation_links.evaluate_all(
        "nodes => nodes.map(a => ({href:a.getAttribute('href'),label:a.textContent.trim()}))"
    )
    assert link_specs, "The fixture answer should include a verified session citation"
    assert all(
        isinstance(link["href"], str) and link["href"].startswith("/project?")
        for link in link_specs
    ), link_specs
    assert any("reveal_session=" in link["href"] for link in link_specs), link_specs
    browser_page.screenshot(path=str(OUT / "research-qa-browser-desktop.png"), full_page=True)
    browser_page.set_viewport_size({"width": 390, "height": 844})
    browser_page.screenshot(path=str(OUT / "research-qa-browser-mobile.png"), full_page=True)
    assert browser_page.evaluate("document.documentElement.scrollWidth <= innerWidth")
    # A long standalone Q/A must scroll as an ordinary page, not inherit the
    # fixed 100dvh/overflow:hidden workspace shell. Exercise actual wheel input
    # on desktop and mobile, not just a full-page screenshot.
    for width in (1280, 390):
        browser_page.set_viewport_size({"width": width, "height": 320})
        browser_page.wait_for_function("() => document.scrollingElement.scrollHeight > innerHeight")
        browser_page.evaluate("window.scrollTo(0, 0)")
        browser_page.mouse.move(170, 120)
        browser_page.mouse.wheel(0, 900)
        browser_page.wait_for_function("window.scrollY > 0")
    browser_page.set_viewport_size({"width": 390, "height": 844})
    browser_page.evaluate("window.scrollTo(0, 0)")
    # Navigate every kind of citation that was actually returned. In particular,
    # session-level links must open a highlighted session and its Outcome.
    for param in ("reveal_understanding", "reveal_strategy", "reveal_artifact", "reveal_session"):
        available = [link for link in link_specs if param + "=" in link["href"]]
        if not available:
            continue
        with browser_page.expect_navigation():
            browser_page.locator("main ul a").filter(has_text=available[0]["label"]).first.click()
        browser_page.wait_for_function(
            "key => new URL(location.href).searchParams.has(key)", arg=param
        )
        if param == "reveal_understanding":
            expect(browser_page.locator(".current-understanding")).to_have_class(
                re.compile("citation-highlight")
            )
        elif param == "reveal_strategy":
            expect(browser_page.locator("[id^='strategy-']")).to_be_visible()
        elif param == "reveal_artifact":
            expect(
                browser_page.locator("[id^='research-artifact-'].citation-highlight")
            ).to_be_visible()
        else:
            expect(browser_page.locator("li[data-session-id].citation-highlight")).to_be_visible()
        browser_page.go_back()
        browser_page.wait_for_function("new URL(location.href).searchParams.has('qa_browser')")
    browser_page.close()

    citation.click()
    page.wait_for_function("new URL(location.href).searchParams.has('reveal_session')")
    session = page.locator("li[data-session-id]").first
    expect(session.locator(".session-row-disclosure")).to_have_attribute("aria-expanded", "true")
    expect(session).to_have_class(re.compile("citation-highlight"))
    page.wait_for_function(
        """() => {
          const row = document.querySelector('li[data-session-id]');
          if (!row) return false;
          const rect = row.querySelector('.session-outcome').getBoundingClientRect();
          return rect.top >= 0 && rect.top <= innerHeight - 40;
        }"""
    )

    page.go_back()
    page.get_by_role("button", name="Research Q/A", exact=True).click()
    dialog = page.get_by_role("dialog", name="Research Q/A")
    expect(dialog.locator(".saved-paper-card")).to_have_count(2)
    page.set_viewport_size({"width": 390, "height": 844})
    page.screenshot(path=str(OUT / "research-qa-mobile.png"), full_page=True)
    mobile_dialog = page.get_by_role("dialog", name="Research Q/A")
    assert mobile_dialog.bounding_box()["width"] <= 390
    mobile_title = mobile_dialog.locator(".saved-paper-card").first.locator(
        ".saved-paper-title-line"
    )
    mobile_title_rects = mobile_title.locator(".saved-paper-title").evaluate(
        "el => { const r=document.createRange(); r.selectNodeContents(el); return [...r.getClientRects()].map(x=>({x:x.x,y:x.y,right:x.right,height:x.height})); }"
    )
    assert len(mobile_title_rects) >= 2, mobile_title_rects
    mobile_title.screenshot(path=str(OUT / "research-qa-title-mobile.png"))
    mobile_title_toggle = mobile_title.locator(".saved-paper-title-toggle")
    mobile_toggle_before_copy = mobile_title.locator(".saved-paper-expand").get_attribute(
        "aria-expanded"
    )
    mobile_last_line = mobile_title_toggle.evaluate(
        "el => { const r=document.createRange(); r.selectNodeContents(el); const a=[...r.getClientRects()]; const x=a.at(-1); return {right:x.right,y:x.y,height:x.height}; }"
    )
    mobile_copy = mobile_title.get_by_role("button", name="Copy Markdown answer")
    mobile_copy.click()
    expect(
        mobile_title.get_by_role("button", name="Copied Markdown answer to clipboard")
    ).to_be_visible(timeout=3000)
    mobile_copy_box = mobile_title.get_by_role(
        "button", name="Copied Markdown answer to clipboard"
    ).bounding_box()
    mobile_markdown = mobile_title.get_by_role("button", name="Render answer as Markdown")
    mobile_markdown_box = mobile_markdown.bounding_box()
    assert mobile_markdown_box and mobile_copy_box
    # A long title may wrap its controls to the next line on mobile.
    # Check readable separation, then verify the controls keep their standard gap.
    same_line = abs(mobile_markdown_box["y"] - mobile_last_line["y"]) < 15
    if same_line:
        assert mobile_markdown_box["x"] >= mobile_last_line["right"] - 1
        assert mobile_markdown_box["x"] - mobile_last_line["right"] <= 18
    else:
        assert mobile_markdown_box["y"] >= mobile_last_line["y"] + 10
    assert mobile_copy_box["x"] - (mobile_markdown_box["x"] + mobile_markdown_box["width"]) == 12
    assert abs(mobile_copy_box["y"] - mobile_markdown_box["y"]) <= 2
    assert (
        mobile_title.locator(".saved-paper-expand").get_attribute("aria-expanded")
        == mobile_toggle_before_copy
    )
    mobile_copied = page.evaluate("navigator.clipboard.readText()")
    assert mobile_copied.startswith("# Research Q/A") and question in mobile_copied
    mobile_title.screenshot(path=str(OUT / "research-qa-title-mobile-copied.png"))
    remove = mobile_dialog.locator(".saved-paper-card").first.get_by_role(
        "button", name="Remove", exact=True
    )
    remove.click()
    mobile_dialog.get_by_role("button", name="Confirm", exact=True).click()
    expect(mobile_dialog.locator(".saved-paper-card")).to_have_count(1)
    assert not errors, errors
    print(
        "Research Q/A Chrome acceptance passed: recovery, archive actions, Markdown and copy icon alignment, browser/remove actions, 40px nested scroll padding, granular session Outcome/artifact citations, research version, desktop/mobile layout, clipboard errors, and no new research session."
    )
    browser.close()
