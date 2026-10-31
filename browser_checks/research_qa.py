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
    page.on("pageerror", lambda error: errors.append(str(error)))

    def forward(route):
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
    samples = page.get_by_role("tab", name="Samples", exact=True)
    samples.click()
    page.locator("button.sample-open").filter(has_text="Maximum Regions Formed by Lines").click()
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
    qa_button.click()
    dialog = page.get_by_role("dialog", name="Research Q/A")
    expect(dialog).to_contain_text("Ask a question about the research performed in this project")
    expect(dialog.locator("input[type=checkbox]")).to_have_count(0)
    expect(dialog.get_by_role("button", name="Ask", exact=True)).to_be_disabled(timeout=20000)
    question = "What did the saved research conclude?"
    dialog.get_by_label("Question").fill(question)
    dialog.get_by_role("button", name="Ask", exact=True).click()
    card = dialog.locator(".saved-paper-card").first
    expect(card).to_be_visible(timeout=30000)
    expect(card.locator(".saved-paper-expand")).to_contain_text(question)
    card.locator(".saved-paper-expand").click()
    expect(card.locator(".saved-paper-expand")).to_have_attribute("aria-expanded", "false")
    card.locator(".saved-paper-expand").click()
    expect(card.locator(".saved-paper-expand")).to_have_attribute("aria-expanded", "true")
    expect(card.locator(".ai-paper-preview")).to_contain_text("The saved research answers")
    citation = card.locator(".ai-paper-preview a").first
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

    copy_button = card.get_by_role("button", name="Copy answer")
    copy_button.click()
    expect(card.get_by_role("button", name="Copied answer to clipboard")).to_be_visible(
        timeout=3000
    )
    copied = page.evaluate("navigator.clipboard.readText()")
    assert question in copied and "The saved research answers" in copied and "Session #1" in copied
    page.evaluate(
        "Object.defineProperty(navigator.clipboard, 'writeText', {configurable:true,value:() => Promise.reject(new Error('blocked'))})"
    )
    card.get_by_role("button", name="Copied answer to clipboard").click()
    expect(dialog.get_by_role("alert")).to_contain_text("Clipboard access failed")

    with page.expect_popup() as popup:
        card.get_by_role("link", name="Open in browser").click()
    browser_page = popup.value
    expect(browser_page.get_by_role("heading", name="Research Q/A")).to_be_visible()
    expect(browser_page.get_by_text(question, exact=True)).to_be_visible()
    expect(browser_page.locator("a").first).to_have_attribute("href", re.compile("reveal_session="))
    browser_page.screenshot(path=str(OUT / "research-qa-browser-desktop.png"), full_page=True)
    browser_page.set_viewport_size({"width": 390, "height": 844})
    browser_page.screenshot(path=str(OUT / "research-qa-browser-mobile.png"), full_page=True)
    assert browser_page.evaluate("document.documentElement.scrollWidth <= innerWidth")
    browser_page.close()

    citation.click()
    page.wait_for_function("new URL(location.href).searchParams.has('reveal_session')")
    session = page.locator("li[data-session-id]").first
    expect(session.locator(".session-row-disclosure")).to_have_attribute("aria-expanded", "true")

    page.go_back()
    page.get_by_role("button", name="Research Q/A", exact=True).click()
    dialog = page.get_by_role("dialog", name="Research Q/A")
    expect(dialog.locator(".saved-paper-card")).to_have_count(1)
    page.set_viewport_size({"width": 390, "height": 844})
    page.screenshot(path=str(OUT / "research-qa-mobile.png"), full_page=True)
    mobile_dialog = page.get_by_role("dialog", name="Research Q/A")
    assert mobile_dialog.bounding_box()["width"] <= 390
    remove = mobile_dialog.locator(".saved-paper-meta").get_by_role("button", name="Remove")
    remove.click()
    mobile_dialog.get_by_role("button", name="Confirm", exact=True).click()
    expect(mobile_dialog.locator(".saved-paper-card")).to_have_count(0)
    assert not errors, errors
    print(
        "Research Q/A Chrome acceptance passed: dialog, bounded fixture answer, archive reopen, citations, browser view, copy, remove, mobile layout, and no new research session."
    )
    browser.close()
