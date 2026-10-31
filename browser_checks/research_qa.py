"""Real Chrome Q/A workflow using the deterministic local provider fixture."""

import os
import re
from pathlib import Path

from playwright.sync_api import expect, sync_playwright

UI = os.environ.get("SIGMA_QA_UI", "http://127.0.0.1:5174").rstrip("/")
FIXTURE = os.environ.get("SIGMA_QA_FIXTURE", "http://127.0.0.1:8012").rstrip("/")
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
        route.fulfill(
            response=route.fetch(
                url=route.request.url.replace(
                    UI.replace("http://", ""), FIXTURE.replace("http://", "")
                ),
                headers={**route.request.headers, "origin": "http://127.0.0.1:5173"},
            )
        )

    context.route("**/api/**", forward)
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
    page.get_by_role("button", name="Start a new research session", exact=True).click()
    page.get_by_role("button", name="Start new session #1", exact=True).click()
    expect(page.locator("li[data-session-id]").first.locator(".session-status")).to_have_text(
        "ended", timeout=30000
    )
    audit_before = page.evaluate(
        "async path => (await (await fetch('/api/projects/audit?' + new URLSearchParams({path}))).json())",
        path,
    )

    tex = page.get_by_role("button", name="LaTeX research paper", exact=True)
    qa_button = page.get_by_role("button", name="Research Q/A", exact=True)
    expect(tex).to_be_visible()
    expect(qa_button).to_be_visible()
    assert qa_button.bounding_box()["x"] > tex.bounding_box()["x"]
    assert (
        page.evaluate("el => parseFloat(getComputedStyle(el).fontSize)", qa_button.element_handle())
        >= 16
    )
    assert page.evaluate("el => getComputedStyle(el).fontWeight", qa_button.element_handle()) in (
        "600",
        "700",
        "800",
        "900",
    )
    lean = page.get_by_role("button", name="Generate Lean proof (coming soon)", exact=True)
    assert (
        qa_button.bounding_box()["height"]
        == tex.bounding_box()["height"]
        == lean.bounding_box()["height"]
    )
    page.screenshot(path=str(OUT / "research-qa-toolbar.png"), full_page=False)
    qa_button.click()
    dialog = page.get_by_role("dialog", name="Research Q/A")
    expect(dialog).to_contain_text("Ask a question about the research performed in this project")
    expect(dialog.locator("input[type=checkbox]")).to_have_count(0)
    expect(dialog.get_by_role("button", name="Ask", exact=True)).to_be_disabled(timeout=20000)
    state_before = page.evaluate(
        "async () => (await (await fetch('/api/__fixture/qa-state')).json())"
    )
    page.evaluate(
        "async () => fetch('/api/__fixture/qa-control', {method:'POST',headers:{'Content-Type':'application/json'},body:JSON.stringify({delay_seconds:2})})"
    )
    question = "Can this saved research be used to explain the relationship between the investigators’ evidence, the skeptic’s objections, and the unresolved conclusions in this project?"
    dialog.get_by_label("Question").fill(question)
    dialog.get_by_role("button", name="Ask", exact=True).click()
    dialog.get_by_role("button", name="Cancel", exact=True).click()
    expect(dialog.get_by_role("alert")).to_contain_text("Request stopped")
    dialog.get_by_role("button", name="Close", exact=True).click()
    expect(dialog).not_to_be_visible()
    page.get_by_role("button", name="Research Q/A", exact=True).click()
    dialog = page.get_by_role("dialog", name="Research Q/A")
    expect(dialog.get_by_role("textbox", name="Question", exact=True)).to_have_value(question)
    recovery = dialog.get_by_role("group", name="Recover interrupted Q/A request")
    missing_archive_reads[0] = 1
    recovery.get_by_role("button", name="Check saved answers").click()
    expect(dialog.get_by_role("alert")).to_contain_text("archive is missing")
    expect(dialog.get_by_role("group", name="Confirm a fresh Q/A request")).to_have_count(0)
    fail_archive_reads[0] = 1
    recovery.get_by_role("button", name="Check saved answers").click()
    expect(dialog.get_by_role("alert")).to_contain_text("fixture archive unavailable")
    expect(dialog.get_by_role("group", name="Confirm a fresh Q/A request")).to_have_count(0)
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
    recovery.get_by_role("button", name="Check saved answers").click()
    expect(
        dialog.get_by_text("The previous request completed and its saved answer is open.")
    ).to_be_visible()
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
    recovery = dialog.get_by_role("group", name="Recover interrupted Q/A request")
    recovery.get_by_role("button", name="Start over / Ask again").click()
    confirmation = dialog.get_by_role("group", name="Confirm a fresh Q/A request")
    expect(confirmation).to_contain_text("may incur another charge")
    failed_state_before_retry = page.evaluate(
        "async () => (await (await fetch('/api/__fixture/qa-state')).json())"
    )
    fail_archive_reads[0] = 1
    confirmation.get_by_role("button", name="Confirm Start over").click()
    expect(dialog.get_by_role("alert")).to_contain_text("fixture archive unavailable")
    expect(dialog.get_by_role("group", name="Confirm a fresh Q/A request")).to_have_count(0)
    failed_state_after_archive_error = page.evaluate(
        "async () => (await (await fetch('/api/__fixture/qa-state')).json())"
    )
    assert failed_state_after_archive_error["started"] == failed_state_before_retry["started"]
    recovery.get_by_role("button", name="Start over / Ask again").click()
    confirmation = dialog.get_by_role("group", name="Confirm a fresh Q/A request")
    confirmation.get_by_role("button", name="Confirm Start over").click()
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
    title_rects = title_line.locator(".saved-paper-title").evaluate(
        "el => { const r=document.createRange(); r.selectNodeContents(el); return [...r.getClientRects()].map(x=>({x:x.x,y:x.y,right:x.right,height:x.height})); }"
    )
    assert len(title_rects) >= 2, title_rects
    title_line.screenshot(path=str(OUT / "research-qa-title-normal.png"))
    normal_copy_button = title_line.get_by_role("button", name="Copy Markdown answer")
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
    assert copied_icon_box and copied_icon_box["x"] >= last_title_rect["right"] - 1
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
    expect(card.locator(".ai-paper-preview")).to_contain_text("The saved research answers")
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
    version = card.locator(".research-qa-version span")
    expect(version).to_contain_text("Research version:")
    expect(version).to_have_attribute(
        "title",
        "Identifies the research used to generate this answer. If the research changes, the answer still refers to the original version.",
    )
    expect(card.locator(".research-qa-technical")).not_to_have_attribute("open", "")
    card.locator(".research-qa-technical summary").click()
    fingerprint = saved_answers[0]["snapshot_sha256"]
    expect(card.locator(".research-qa-technical")).to_contain_text(fingerprint)
    card.locator(".research-qa-technical").get_by_role(
        "button", name="Copy research version fingerprint"
    ).click()
    assert page.evaluate("navigator.clipboard.readText()") == fingerprint
    expect(
        card.locator(".research-qa-technical").get_by_role(
            "button", name="Copied research version fingerprint to clipboard"
        )
    ).to_be_visible()
    page.evaluate(
        "Object.defineProperty(navigator.clipboard, 'writeText', {configurable:true,value:() => Promise.reject(new Error('blocked'))})"
    )
    title_line.get_by_role("button", name="Copied Markdown answer to clipboard").click()
    expect(dialog.get_by_role("alert")).to_contain_text("Clipboard access failed")

    with page.expect_popup() as markdown_popup:
        card.get_by_role("link", name="Markdown", exact=True).click()
    markdown_page = markdown_popup.value
    expect(markdown_page.locator("body")).to_contain_text("## Question")
    expect(markdown_page.locator("body")).to_contain_text("## Sources")
    expect(markdown_page.locator("body")).to_contain_text("[Session #1]")
    markdown_page.screenshot(path=str(OUT / "research-qa-markdown-source.png"), full_page=True)
    markdown_page.close()
    with page.expect_popup() as popup:
        card.get_by_role("link", name="Open in browser").click()
    browser_page = popup.value
    expect(browser_page.get_by_role("heading", name="Research Q/A")).to_be_visible()
    expect(browser_page.get_by_role("heading", name="Evidence-based answer")).to_be_visible()
    expect(browser_page.locator(".katex")).to_be_visible()
    expect(browser_page.locator("main")).to_contain_text("Generation duration:")
    forged_link = browser_page.locator("main a").filter(has_text="forged citation")
    assert forged_link.count() <= 1 and (
        not forged_link.count() or forged_link.first.get_attribute("href") in {None, ""}
    )
    assert browser_page.evaluate("window.__sigmaInjected !== true")
    expect(browser_page.get_by_text(question, exact=True)).to_be_visible()
    citation_links = browser_page.locator("main ul a")
    expect(citation_links).to_have_count(5)
    expect(citation_links.nth(0)).to_have_text(re.compile("Project ·"))
    expect(citation_links.nth(0)).to_have_attribute("href", re.compile("reveal_project=1"))
    expect(citation_links.nth(1)).to_have_text(re.compile("Strategy ·"))
    expect(citation_links.nth(1)).to_have_attribute("href", re.compile("reveal_strategy="))
    expect(citation_links.nth(2)).to_have_attribute("href", re.compile("reveal_session="))
    expect(citation_links.nth(3)).to_have_attribute("href", re.compile("reveal_artifact="))
    expect(citation_links.nth(4)).to_have_text("Current Understanding")
    browser_page.screenshot(path=str(OUT / "research-qa-browser-desktop.png"), full_page=True)
    browser_page.set_viewport_size({"width": 390, "height": 844})
    browser_page.screenshot(path=str(OUT / "research-qa-browser-mobile.png"), full_page=True)
    assert browser_page.evaluate("document.documentElement.scrollWidth <= innerWidth")
    with browser_page.expect_navigation():
        citation_links.nth(0).click()
    browser_page.wait_for_function(
        "new URL(location.href).searchParams.get('reveal_project') === '1'"
    )
    expect(browser_page.locator(".project-overview-card")).to_have_class(
        re.compile("citation-highlight")
    )
    browser_page.go_back()
    browser_page.wait_for_function("new URL(location.href).searchParams.has('qa_browser')")
    browser_page.locator("main ul a").filter(has_text="Strategy ·").click()
    browser_page.wait_for_function("new URL(location.href).searchParams.has('reveal_strategy')")
    strategy_target = browser_page.locator(
        "#strategy-"
        + browser_page.evaluate("new URL(location.href).searchParams.get('reveal_strategy')")
    )
    expect(strategy_target).to_be_visible()
    browser_page.go_back()
    browser_page.wait_for_function("new URL(location.href).searchParams.has('qa_browser')")
    citation_links = browser_page.locator("main ul a")
    artifact_link = citation_links.nth(3)
    with browser_page.expect_navigation():
        artifact_link.click()
    browser_page.wait_for_function("new URL(location.href).searchParams.has('reveal_artifact')")
    artifact = browser_page.locator("[id^='research-artifact-']")
    expect(artifact).to_be_visible()
    expect(artifact).to_have_class(re.compile("citation-highlight"))
    browser_page.close()

    with page.expect_popup() as understanding_popup:
        card.get_by_role("link", name="Open in browser").click()
    understanding_page = understanding_popup.value
    with understanding_page.expect_navigation():
        understanding_page.locator("main ul a").filter(has_text="Current Understanding").click()
    understanding_page.wait_for_function(
        "new URL(location.href).searchParams.get('reveal_understanding') === '1'"
    )
    understanding = understanding_page.locator(".current-understanding")
    expect(understanding).to_be_visible()
    expect(understanding).to_have_attribute("open", "")
    expect(understanding).to_have_class(re.compile("citation-highlight"))
    understanding_page.close()

    citation.click()
    page.wait_for_function("new URL(location.href).searchParams.has('reveal_session')")
    session = page.locator("li[data-session-id]").first
    expect(session.locator(".session-row-disclosure")).to_have_attribute("aria-expanded", "true")
    expect(session).to_have_class(re.compile("citation-highlight"))
    page.wait_for_function(
        """() => {
          const row = document.querySelector('li[data-session-id]');
          if (!row) return false;
          const rect = row.querySelector('.session-row-disclosure').getBoundingClientRect();
          return rect.top >= 0 && rect.bottom <= innerHeight;
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
    remove = mobile_dialog.locator(".saved-paper-card").first.get_by_role(
        "button", name="Remove", exact=True
    )
    remove.click()
    mobile_dialog.get_by_role("button", name="Confirm", exact=True).click()
    expect(mobile_dialog.locator(".saved-paper-card")).to_have_count(1)
    assert not errors, errors
    print(
        "Research Q/A Chrome acceptance passed: recovery, archive actions, Markdown copy/source/rendering and math, safe output, Research version/copy, all five citation types and reveal routes, desktop/mobile layout, clipboard errors, and no new research session."
    )
    browser.close()
