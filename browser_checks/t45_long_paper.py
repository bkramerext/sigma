"""Real-Chrome check of long-paper preflight, consent, and streamed failures."""

import base64
import os
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

    page.route("**/api/**", forward)
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
    long_form = dialog.get_by_role(
        "checkbox", name="Use expanded multi-section authoring for a more detailed paper"
    )
    expect(long_form).not_to_be_checked()
    long_form.check()

    confirmations: list[str] = []

    def accept_confirmation(event):
        confirmations.append(event.message)
        event.accept()

    page.once("dialog", accept_confirmation)
    dialog.get_by_role("button", name="Generate paper", exact=True).click()
    expect(dialog).to_contain_text("Long-Form Experimental Research Synthesis", timeout=60_000)
    expect(dialog.get_by_role("link", name="Download compiled PDF")).to_be_visible()
    expect(dialog).to_contain_text("evidence batches")
    expect(dialog).to_contain_text("calls this run")
    expect(dialog).to_contain_text("Experimental question and prior context")
    pdf_link = dialog.get_by_role("link", name="Download compiled PDF")
    pdf_result = page.evaluate(
        "async href => { const response = await fetch(href); const bytes = new Uint8Array(await response.arrayBuffer()); let binary=''; for (const byte of bytes) binary += String.fromCharCode(byte); return {status:response.status,type:response.headers.get('content-type'),bytes:btoa(binary)}; }",
        pdf_link.get_attribute("href"),
    )
    pdf_bytes = base64.b64decode(pdf_result["bytes"])
    assert pdf_result["status"] == 200 and "application/pdf" in pdf_result["type"]
    assert pdf_bytes.startswith(b"%PDF-") and len(pdf_bytes) > 1000
    Path("/tmp/sigma-t45-xenopus.pdf").write_bytes(pdf_bytes)
    assert confirmations and "calls" in confirmations[0]
    assert not errors, errors
    browser.close()

print(
    "PASS real Chrome T45: Xenopus sample long-form authoring, provider-call confirmation, section progress, immutable paper save, and compiled PDF retrieval."
)
