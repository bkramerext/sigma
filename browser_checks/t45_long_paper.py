"""Real-Chrome check of long-paper preflight, consent, and streamed failures."""

import base64
import os
import re
from pathlib import Path

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
    page.on("pageerror", lambda error: errors.append(str(error)))

    def forward(route):
        route.fulfill(
            response=route.fetch(
                url=route.request.url.replace(
                    UI_ORIGIN.replace("http://", ""), f"127.0.0.1:{FIXTURE_PORT}"
                ),
                headers={**route.request.headers, "origin": "http://127.0.0.1:5173"},
            )
        )

    page.context.route("**/api/**", forward)
    page.goto(UI_ORIGIN + "/")
    samples_tab = page.get_by_role("tab", name="Samples", exact=True)
    if samples_tab.get_attribute("aria-selected") != "true":
        samples_tab.click()
    page.locator(".sample-open").filter(
        has_text="Why Do Xenopus Tadpoles Temporarily Lose Tail Regeneration?"
    ).click()
    page.wait_for_url("**/project?*")
    page.get_by_role("button", name="LaTeX research paper", exact=True).click()
    dialog = page.get_by_role("dialog", name="Academic paper using LaTeX")
    expect(dialog).to_be_visible()
    assert dialog.evaluate("element => element.contains(document.activeElement)")
    expect(dialog.get_by_role("button", name="Cancel", exact=True)).to_be_visible()
    expect(dialog.get_by_role("button", name="Close", exact=True)).to_have_count(0)
    expect(dialog).to_contain_text("593 provider calls")
    expect(dialog).to_contain_text(
        "SIGMA uses the project's complete research history to prepare a paper, including supporting evidence, unsuccessful approaches, contradictions, and unresolved questions."
    )
    expect(dialog).to_contain_text(
        "It distinguishes established findings from conjectures and identifies gaps rather than inventing missing proof steps."
    )
    expect(dialog).to_contain_text(
        "The resulting paper is AI-generated and has not been independently verified. Readers should examine its evidence and limitations before relying on its conclusions."
    )
    expect(dialog).to_contain_text("Selected model:")
    expect(dialog).to_contain_text("Generation bounds:")
    desktop_layout = dialog.evaluate(
        "element => ({height: element.getBoundingClientRect().height, textSize: parseFloat(getComputedStyle(element.querySelector('.ai-paper-body > p.settings-hint')).fontSize)})"
    )
    assert desktop_layout["height"] < 600, desktop_layout
    assert desktop_layout["textSize"] >= 14, desktop_layout
    page.screenshot(path="/tmp/sigma-ai-paper-dialog-desktop.png")

    page.set_viewport_size({"width": 390, "height": 844})
    expect(dialog).to_be_visible()
    mobile_height = dialog.evaluate("element => element.getBoundingClientRect().height")
    assert mobile_height <= 0.9 * 844, mobile_height
    page.screenshot(path="/tmp/sigma-ai-paper-dialog-mobile.png")
    page.set_viewport_size({"width": 1440, "height": 1000})

    def dismiss_test_toasts():
        page.locator(".request-toast button[aria-label='Dismiss request error']").evaluate_all(
            "buttons => buttons.forEach(button => button.click())"
        )

    long_form = dialog.get_by_role(
        "checkbox", name="Use expanded multi-section authoring for a more detailed paper"
    )
    open_in_tab = dialog.get_by_role("checkbox", name="Open in browser tab", exact=True)
    expect(long_form).not_to_be_checked()
    expect(open_in_tab).not_to_be_checked()
    long_form.check()

    confirmations: list[str] = []

    def accept_confirmation(event):
        confirmations.append(event.message)
        event.accept()

    page.once("dialog", accept_confirmation)
    dialog.get_by_role("button", name="Generate paper", exact=True).click()
    progress = dialog.locator(".ai-paper-status")
    expect(progress).to_be_visible(timeout=10_000)
    expect(progress.get_by_role("button", name="Cancel", exact=True)).to_be_visible()
    expect(dialog.get_by_role("button", name="Authoring…", exact=True)).to_have_count(0)
    dismiss_test_toasts()
    page.screenshot(path="/tmp/sigma-ai-paper-dialog-authoring.png")
    progress.get_by_role("button", name="Cancel", exact=True).click()
    expect(dialog).to_be_visible()
    expect(dialog.locator(".ai-paper-status")).to_contain_text(
        "Generation cancelled.", timeout=10_000
    )
    open_in_tab.check()
    expect(open_in_tab).to_be_checked()
    page.once("dialog", accept_confirmation)
    dialog.get_by_role("button", name="Generate paper", exact=True).click()
    expect(dialog).to_contain_text("Long-Form Experimental Research Synthesis", timeout=60_000)
    expect(dialog.locator(".ai-paper-open-tab")).to_contain_text("Open in browser tab")
    scroll_layout = dialog.evaluate(
        "element => { const body = element.querySelector('.ai-paper-body'); return {dialogHeight: element.getBoundingClientRect().height, bodyHeight: body.clientHeight, bodyScrollHeight: body.scrollHeight, bodyBottom: body.getBoundingClientRect().bottom, viewportHeight: innerHeight}; }"
    )
    assert scroll_layout["dialogHeight"] <= 0.9 * 1000, scroll_layout
    assert scroll_layout["bodyScrollHeight"] > scroll_layout["bodyHeight"], scroll_layout
    assert scroll_layout["bodyBottom"] <= scroll_layout["viewportHeight"], scroll_layout
    dismiss_test_toasts()
    page.screenshot(path="/tmp/sigma-ai-paper-dialog-complete.png")
    pdf_link = dialog.get_by_role("link", name="Open compiled PDF in new tab")
    expect(pdf_link).to_be_visible()
    expect(dialog).to_contain_text("evidence batches")
    expect(dialog).to_contain_text("calls this run")
    expect(dialog).to_contain_text("Experimental question and prior context")
    pdf_result = page.evaluate(
        "async href => { const response = await fetch(href); const bytes = new Uint8Array(await response.arrayBuffer()); let binary=''; for (const byte of bytes) binary += String.fromCharCode(byte); const url = new URL(href, location.href); url.searchParams.delete('open_in_browser'); const downloadResponse = await fetch(url); return {status:response.status,type:response.headers.get('content-type'),disposition:response.headers.get('content-disposition'),defaultDisposition:downloadResponse.headers.get('content-disposition'),bytes:btoa(binary)}; }",
        pdf_link.get_attribute("href"),
    )
    pdf_bytes = base64.b64decode(pdf_result["bytes"])
    assert pdf_result["status"] == 200 and "application/pdf" in pdf_result["type"]
    assert pdf_result["disposition"].startswith("inline;"), pdf_result["disposition"]
    assert pdf_result["defaultDisposition"].startswith("attachment;"), pdf_result["defaultDisposition"]
    assert pdf_bytes.startswith(b"%PDF-") and len(pdf_bytes) > 1000
    Path("/tmp/sigma-t45-xenopus.pdf").write_bytes(pdf_bytes)
    with page.expect_popup(timeout=10_000) as popup_info:
        pdf_link.click()
    pdf_tab = popup_info.value
    expect(pdf_tab).to_have_url(
        re.compile(rf"^{re.escape(UI_ORIGIN)}/api/projects/papers/[^/]+/pdf\?"),
        timeout=10_000,
    )
    open_in_tab.uncheck()
    download_link = dialog.get_by_role("link", name="Download compiled PDF")
    expect(download_link).to_be_visible()
    assert download_link.get_attribute("download") == "sigma-paper.pdf"
    assert len(confirmations) == 2 and all("calls" in item for item in confirmations)
    assert not errors, errors
    dialog.get_by_role("button", name="Cancel", exact=True).click()
    expect(dialog).not_to_be_visible()
    expect(page.get_by_role("button", name="LaTeX research paper", exact=True)).to_be_focused()
    browser.close()

print(
    "PASS real Chrome T45: compact paper dialog at desktop/mobile, inline generation cancellation, long-form authoring, saved version, and compiled PDF retrieval."
)
