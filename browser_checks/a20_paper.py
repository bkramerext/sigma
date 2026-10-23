"""Real Chrome A20 paper workflow using the isolated provider fixture."""

import base64
import json
import os
from pathlib import Path

from playwright.sync_api import expect, sync_playwright

UI_ORIGIN = os.environ.get("SIGMA_A20_UI_ORIGIN", "http://127.0.0.1:5174")
FIXTURE_PORT = os.environ.get("SIGMA_A20_FIXTURE_PORT", "8012")

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
    page.get_by_role("tab", name="Samples", exact=True).click()
    page.get_by_role("tabpanel", name="Samples").get_by_role(
        "button", name="Open Maximum Regions Formed by Lines"
    ).click()
    page.wait_for_url("**/project?*")
    path = page.evaluate("new URL(location.href).searchParams.get('path')")
    page.locator("li[data-strategy-id]").first.locator(".strategy-row-disclosure").click()
    page.get_by_role("button", name="Start a new research session", exact=True).click()
    page.get_by_role("button", name="Start new session #1", exact=True).click()
    session = page.locator("li[data-session-id]").first
    expect(session.locator(".session-status")).to_have_text("ended", timeout=20000)
    record = page.evaluate(
        "async path => (await (await fetch('/api/projects/export?' + new URLSearchParams({path}))).json())",
        path,
    )
    assert record["research_sessions"][0]["artifacts"]
    assert "R(n)" in json.dumps(record["research_sessions"][0]["artifacts"], ensure_ascii=False)

    expect(page.get_by_role("button", name="Author AI paper", exact=True)).to_have_count(0)
    page.get_by_role("button", name="Export project", exact=True).click()
    export_dialog = page.get_by_role("dialog", name="Export Project")
    export_dialog.get_by_label("Academic paper using LaTeX").check()
    export_dialog.get_by_label("Filename").fill("maximum-regions-paper")
    export_dialog.get_by_label("Open in browser tab").check()
    export_dialog.get_by_role("button", name="Continue", exact=True).click()
    dialog = page.get_by_role("dialog", name="Academic paper using LaTeX")
    expect(dialog).to_be_visible()
    expect(dialog).to_contain_text("gpt-6.1-sol")
    expect(dialog).to_contain_text("one provider call")
    dialog.get_by_role("button", name="Generate paper", exact=True).click()
    expect(dialog).to_contain_text("Line Arrangements: A Saved Unverified Argument", timeout=30000)
    expect(dialog).to_contain_text("labels the full argument unverified")
    expect(dialog).to_contain_text("upper bound")
    expect(dialog).to_contain_text("Attainability")
    expect(dialog).to_contain_text("artifact:")
    expect(dialog).to_contain_text("Conclusion claim links: C1")
    expect(dialog).to_contain_text("Abstract claim links: C1")
    expect(dialog.get_by_role("link", name="Open compiled PDF in new tab")).to_be_visible()
    article = dialog.locator(".ai-paper-preview")
    article.screenshot(path="/tmp/sigma-a20-paper-preview.png")
    pdf_link = dialog.get_by_role("link", name="Open compiled PDF in new tab")
    assert "/pdf?" in pdf_link.get_attribute("href")
    assert pdf_link.get_attribute("target") == "_blank"
    pdf_result = page.evaluate(
        "async href => { const response = await fetch(href); const bytes = new Uint8Array(await response.arrayBuffer()); let binary=''; for (const byte of bytes) binary += String.fromCharCode(byte); return {status:response.status,type:response.headers.get('content-type'),bytes:btoa(binary)}; }",
        pdf_link.get_attribute("href"),
    )
    assert pdf_result["status"] == 200 and "application/pdf" in pdf_result["type"]
    pdf_path = Path("/tmp/sigma-a20-paper.pdf")
    pdf_path.write_bytes(base64.b64decode(pdf_result["bytes"]))
    pdf = pdf_path.read_bytes()
    assert pdf.startswith(b"%PDF-") and len(pdf) > 1000
    paper_id = dialog.locator("#ai-paper-version").input_value()
    detail = page.evaluate(
        "async ({path,id}) => await (await fetch('/api/projects/papers/' + id + '?' + new URLSearchParams({path}))).json()",
        {"path": path, "id": paper_id},
    )
    assert detail["snapshot"]["project_id"] == record["project"]["id"]
    assert detail["draft"]["claims"][0]["evidence_refs"]
    source_ids = {item["id"] for item in detail["snapshot"]["sources"]}
    assert all(
        ref in source_ids for claim in detail["draft"]["claims"] for ref in claim["evidence_refs"]
    )
    expect(page.locator("body")).not_to_contain_text("internal server error")

    page.set_viewport_size({"width": 390, "height": 844})
    box = dialog.bounding_box()
    assert box and box["x"] >= 0 and box["y"] >= 0
    assert box["x"] + box["width"] <= 390 and box["y"] + box["height"] <= 844
    page.screenshot(path="/tmp/sigma-a20-paper-mobile.png", full_page=True)
    page.keyboard.press("Escape")
    expect(dialog).to_be_hidden()
    expect(export_dialog).to_be_visible()
    expect(export_dialog.get_by_label("Filename")).to_have_value("maximum-regions-paper")
    expect(export_dialog.get_by_label("Open in browser tab")).to_be_checked()
    expect(export_dialog.get_by_label("Academic paper using LaTeX")).to_be_checked()
    export_dialog.get_by_label("Open in browser tab").uncheck()
    export_dialog.get_by_role("button", name="Continue", exact=True).click()
    dialog = page.get_by_role("dialog", name="Academic paper using LaTeX")
    download_link = dialog.get_by_role("link", name="Download compiled PDF")
    expect(download_link).to_be_visible()
    assert download_link.get_attribute("download") == "maximum-regions-paper.pdf"
    page.keyboard.press("Escape")
    expect(dialog).to_be_hidden()
    expect(export_dialog).to_be_visible()
    page.keyboard.press("Escape")
    expect(export_dialog).to_be_hidden()
    assert not errors, errors
    context.close()
    browser.close()

print(
    "PASS real Chrome A20: saved evidence, Export Project authoring entry, remembered export choices, traceable claims, durable version and compiled PDF."
)
