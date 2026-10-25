"""Real Chrome A20 paper workflow using the isolated provider fixture."""

import base64
import json
import os
from itertools import pairwise
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
    samples_tab = page.get_by_role("tab", name="Samples", exact=True)
    if samples_tab.get_attribute("aria-selected") != "true":
        samples_tab.click()
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

    # The copper TeX wordmark follows Project Download and opens paper authoring directly.
    latex_button = page.get_by_role("button", name="LaTeX research paper", exact=True)
    expect(latex_button).to_be_visible()
    assert latex_button.evaluate("element => getComputedStyle(element).color") == "rgb(228, 181, 124)"
    expect(latex_button.locator(".latex-wordmark")).to_have_text("TEX")
    page.evaluate("window.scrollTo(0, 0)")

    def assert_project_actions():
        page.evaluate("() => document.fonts.ready.then(() => new Promise(resolve => requestAnimationFrame(() => requestAnimationFrame(resolve))))")
        actions = page.locator(".project-pane-actions")
        expect(actions.locator(".project-latex-button")).to_have_count(1)
        expect(actions.locator(".project-lean-button")).to_have_count(1)
        action_buttons = actions.get_by_role("button")
        expect(action_buttons.nth(0)).to_have_attribute("aria-label", "LaTeX research paper")
        expect(action_buttons.nth(1)).to_have_attribute("aria-label", "Generate Lean proof (coming soon)")
        expect(action_buttons.nth(1)).to_be_disabled()
        expect(action_buttons.nth(1)).to_have_attribute("title", "Generate Lean proof (coming soon)")
        expect(action_buttons.nth(2)).to_have_attribute("aria-label", "Export project")
        expect(action_buttons.nth(3)).to_have_attribute("aria-label", "Project settings")
        expect(action_buttons.nth(0)).to_have_attribute("title", "Generate a LaTeX research paper")
        expect(action_buttons.nth(0)).to_have_attribute("data-tooltip", "Generate a LaTeX research paper")
        expect(action_buttons.nth(1)).to_have_attribute("title", "Generate Lean proof (coming soon)")
        expect(action_buttons.nth(1)).to_have_attribute("data-tooltip", "Generate Lean proof (coming soon)")
        expect(page.locator(".project-difficulty-badge")).to_have_attribute("title", "This project is considered easy. Click to cycle through easy, medium, and hard.")
        expect(page.locator(".project-difficulty-badge")).to_have_attribute("data-tooltip", "This project is considered easy. Click to cycle through easy, medium, and hard.")
        expect(page.locator(".project-google-signin")).to_have_attribute("aria-label", "Google sign-in setup required")
        expect(page.locator(".project-google-signin")).to_have_attribute("data-tooltip-disabled", "")
        expect(page.locator(".project-google-signin")).not_to_have_attribute("data-tooltip")
        expect(page.locator(".project-google-signin")).to_have_text("Google sign-in setup required")
        expect(page.locator(".project-google-signin")).to_be_enabled()
        model_tooltip = page.locator(".project-model-pill").get_attribute("data-tooltip")
        assert model_tooltip and model_tooltip.startswith("The selected model is ") and ". Its relative published API token cost is " in model_tooltip and model_tooltip.endswith(" Click to cycle through available models."), model_tooltip
        expect(page.locator(".project-thinking-pill")).to_have_attribute("data-tooltip", "The thinking level is set to high. Click to cycle through levels supported by this model.")
        expect(page.locator(".project-chatgpt-signin summary")).to_have_attribute("data-tooltip-disabled", "")
        expect(page.locator(".project-chatgpt-signin summary")).not_to_have_attribute("title")
        expect(page.locator(".project-chatgpt-signin summary")).not_to_have_attribute("data-tooltip")
        expect(actions.locator(".latex-wordmark")).to_have_text("TEX")
        logo = actions.locator(".project-lean-button img")
        expect(logo).to_have_attribute("src", "/lean-logo.svg")
        assert logo.evaluate("e => [e.naturalWidth, e.naturalHeight]") == [300, 150]
        assert logo.evaluate("e => getComputedStyle(e).filter") == "none"
        assert logo.evaluate("e => [getComputedStyle(e).width, getComputedStyle(e).height]") == ["42px", "21px"]
        svg = page.evaluate("async () => await (await fetch('/lean-logo.svg')).text()")
        assert 'id="path188"' in svg and 'stroke-width:18' in svg
        assert 'fill:#e0c4a0' in svg
        assert 'id="path75"' in svg and 'stroke-width:6' in svg
        action_boxes = actions.evaluate("e => [...e.children].map(b => { const r = b.getBoundingClientRect(); return {x:r.x,y:r.y,width:r.width,height:r.height}; })")
        assert [box["width"] for box in action_boxes] == [34, 50, 34, 34], action_boxes
        assert all(box["height"] == 34 for box in action_boxes), action_boxes
        tex_box = action_boxes[0]
        assert all(abs(box["y"] + box["height"] / 2 - tex_box["y"] - tex_box["height"] / 2) <= 3 for box in action_boxes), action_boxes
        gaps = [
            next_box["x"] - box["x"] - box["width"]
            for box, next_box in pairwise(action_boxes)
        ]
        assert [round(gap) for gap in gaps] == [16, 11, 6], gaps
        visual_boxes = [
            actions.locator(".latex-wordmark").bounding_box(),
            logo.bounding_box(),
            actions.locator("button").nth(2).locator("svg").bounding_box(),
            actions.locator("button").nth(3).locator("svg").bounding_box(),
        ]
        assert all(visual_boxes), visual_boxes
        visual_gaps = [
            next_box["x"] - box["x"] - box["width"]
            for box, next_box in pairwise(visual_boxes)
        ]
        assert max(visual_gaps) - min(visual_gaps) <= 1, visual_gaps

    assert_project_actions()
    difficulty_box = page.locator(".project-difficulty-badge").bounding_box()
    model_pill_box = page.locator(".project-model-pill").bounding_box()
    google_pill_box = page.locator(".project-google-signin").bounding_box()
    assert difficulty_box and model_pill_box and google_pill_box
    assert abs(difficulty_box["y"] - model_pill_box["y"]) <= 1, (difficulty_box, model_pill_box, google_pill_box)
    assert abs(
        difficulty_box["y"] + difficulty_box["height"] / 2
        - google_pill_box["y"] - google_pill_box["height"] / 2
    ) <= 1, (difficulty_box, model_pill_box, google_pill_box)
    assert abs(model_pill_box["x"] - difficulty_box["x"] - difficulty_box["width"] - 8) <= 1, (difficulty_box, model_pill_box, google_pill_box)
    assert abs(google_pill_box["x"] - model_pill_box["x"] - model_pill_box["width"] - 8) <= 1, (difficulty_box, model_pill_box, google_pill_box)
    latex_button.hover()
    expect(page.get_by_role("tooltip")).to_have_text("Generate a LaTeX research paper")
    lean_button = page.locator(".project-lean-button")
    lean_button.hover()
    expect(page.get_by_role("tooltip")).to_have_text("Generate Lean proof (coming soon)")
    page.locator(".project-google-signin").hover()
    expect(page.get_by_role("tooltip")).to_have_count(0)
    page.locator(".project-google-signin").click()
    setup_notice = page.get_by_role("alert").filter(
        has_text="Google sign-in is not configured."
    )
    expect(setup_notice).to_contain_text("SIGMA_CLOUD_BOOTSTRAP_ADMIN_EMAIL")
    expect(page.locator(".google-connection-details")).to_have_count(0)
    page.get_by_role("button", name="Dismiss request error").click()
    page.locator(".project-difficulty-badge").hover()
    expect(page.get_by_role("tooltip")).to_have_text("This project is considered easy. Click to cycle through easy, medium, and hard.")
    page.locator(".project-chatgpt-signin summary").hover()
    expect(page.get_by_role("tooltip")).to_have_count(0)
    page.locator(".project-thinking-pill").hover()
    expect(page.get_by_role("tooltip")).to_have_text("The thinking level is set to high. Click to cycle through levels supported by this model.")
    model_tooltip = page.locator(".project-model-pill").get_attribute("data-tooltip")
    page.locator(".project-model-pill").hover()
    expect(page.get_by_role("tooltip")).to_have_text(model_tooltip)
    lean_button.focus()
    expect(lean_button).not_to_be_focused()
    page.keyboard.press("Enter")
    expect(page.get_by_role("dialog", name="Academic paper using LaTeX")).to_be_hidden()
    expect(page.get_by_role("dialog", name="Export Project")).to_be_hidden()
    page.mouse.move(0, 0)
    page.screenshot(path="/tmp/sigma-t20-project-download-desktop.png", full_page=True)
    for width, height in ((1280, 800), (390, 844), (320, 700)):
        page.set_viewport_size({"width": width, "height": height})
        page.evaluate("window.scrollTo(0, 0)")
        assert_project_actions()
        assert page.evaluate("document.documentElement.scrollWidth <= innerWidth"), width
    page.set_viewport_size({"width": 390, "height": 844})
    page.screenshot(path="/tmp/sigma-t20-project-download-mobile.png", full_page=True)
    project_url = page.url
    lean_button = page.locator(".project-lean-button")
    page.set_viewport_size({"width": 1440, "height": 1000})
    page.locator(".project-pane-actions").screenshot(path="/tmp/sigma-lean-copper-closeup.png")
    page.screenshot(path="/tmp/sigma-t20-lean-copper-desktop.png", full_page=True)
    page.set_viewport_size({"width": 390, "height": 844})
    page.screenshot(path="/tmp/sigma-t20-lean-copper-mobile.png", full_page=True)
    # The Lean action is only relevant to mathematical projects.
    page.goto(UI_ORIGIN + "/")
    samples_tab = page.get_by_role("tab", name="Samples", exact=True)
    if samples_tab.get_attribute("aria-selected") != "true":
        samples_tab.click()
    page.locator(".sample-type-group").filter(has_text="Engineering").evaluate("element => { element.open = true; }")
    page.locator(".sample-open").filter(has_text="Warp Drive Feasibility").click()
    page.wait_for_url("**/project?*")
    expect(page.locator(".project-lean-button")).to_have_count(0)
    page.goto(project_url)
    page.set_viewport_size({"width": 1440, "height": 1000})
    latex_button.click()
    direct_dialog = page.get_by_role("dialog", name="Academic paper using LaTeX")
    expect(direct_dialog).to_be_visible()
    expect(page.get_by_role("dialog", name="Export Project")).to_be_hidden()
    direct_dialog.get_by_role("button", name="Close", exact=True).click()
    expect(direct_dialog).to_be_hidden()
    expect(latex_button).to_be_focused()

    latex_button.focus()
    page.keyboard.press("Enter")
    expect(direct_dialog).to_be_visible()
    direct_dialog.get_by_role("button", name="Close", exact=True).click()
    expect(direct_dialog).to_be_hidden()
    expect(latex_button).to_be_focused()

    # Project export contains only audit and deterministic report formats.
    expect(page.get_by_role("button", name="Author AI paper", exact=True)).to_have_count(0)
    page.get_by_role("button", name="Export project", exact=True).click()
    export_dialog = page.get_by_role("dialog", name="Export Project")
    expect(export_dialog.get_by_role("radio")).to_have_count(4)
    expect(export_dialog).not_to_contain_text("Academic paper using LaTeX")
    expect(export_dialog.get_by_role("radio", name="Project Audit")).to_be_visible()
    expect(export_dialog.get_by_role("radio", name="Text file")).to_be_visible()
    expect(export_dialog.get_by_role("radio", name="HTML report")).to_be_visible()
    expect(export_dialog.get_by_role("radio", name="LaTeX report")).to_be_visible()
    export_dialog.get_by_role("button", name="Cancel", exact=True).click()
    expect(export_dialog).to_be_hidden()
    latex_button.click()
    dialog = page.get_by_role("dialog", name="Academic paper using LaTeX")
    expect(dialog).to_be_visible()
    expect(dialog.get_by_role("button", name="Close", exact=True)).to_be_visible()
    expect(dialog).to_contain_text("gpt-6.1-sol")
    expect(dialog).to_contain_text("complete snapshot is archived up to 20 MB")
    expect(dialog).to_contain_text("48 KB evidence batches")
    expect(dialog).to_contain_text("at most 512 batches, 48 sections, and 593 provider calls")
    expect(dialog).to_contain_text("1 MB response cap")
    expect(dialog).to_contain_text("TeX compilation allows 50 MB and 300 seconds")

    def reject_provider(route):
        route.fulfill(
            status=502,
            content_type="application/json",
            body=json.dumps({"error": "Fixture provider rejected the request."}),
        )

    page.route("**/api/projects/papers", reject_provider)
    dialog.get_by_role("button", name="Generate paper", exact=True).click()
    expect(dialog.get_by_role("alert")).to_contain_text("Fixture provider rejected the request")
    expect(dialog.locator(".ai-paper-preview")).to_have_count(0)
    page.unroute("**/api/projects/papers", reject_provider)

    def malformed_response(route):
        route.fulfill(status=200, content_type="application/json", body="not-json")

    page.route("**/api/projects/papers", malformed_response)
    dialog.get_by_role("button", name="Generate paper", exact=True).click()
    expect(dialog.get_by_role("alert")).to_contain_text("invalid server response")
    expect(dialog.locator(".ai-paper-preview")).to_have_count(0)
    page.unroute("**/api/projects/papers", malformed_response)

    dialog.get_by_role("button", name="Generate paper", exact=True).click()
    expect(dialog).to_contain_text("The Maximum Number of Regions Formed by Lines", timeout=30000)
    expect(dialog).to_contain_text("not a formally certified theorem")
    expect(dialog).to_contain_text("upper bound")
    expect(dialog).to_contain_text("Notation and a cell lemma")
    expect(dialog).to_contain_text("Main result (unverified proof candidate)")
    expect(dialog).to_contain_text("Proof of attainability")
    expect(dialog).to_contain_text("small disk around it contains points on both sides")
    expect(dialog).to_contain_text("distinct x-coordinates")
    expect(dialog).to_contain_text("with no lines, the plane has one region")
    expect(dialog).to_contain_text("artifact:")
    expect(dialog).to_contain_text("Conclusion claim links: C1")
    expect(dialog).to_contain_text("Abstract claim links: C1")
    expect(dialog).to_contain_text("Frozen obligation reconciliation")
    expect(dialog).to_contain_text("not presumed resolved")
    expect(dialog).to_contain_text("artifact:")
    expect(dialog.get_by_role("link", name="Download compiled PDF")).to_be_visible()
    article = dialog.locator(".ai-paper-preview")
    article.screenshot(path="/tmp/sigma-a20-paper-preview.png")
    pdf_link = dialog.get_by_role("link", name="Download compiled PDF")
    assert "/pdf?" in pdf_link.get_attribute("href")
    assert pdf_link.get_attribute("download") == "sigma-paper.pdf"
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
    assert len(detail["obligation_reconciliation"]) == 12
    assert all(
        item["status"] == "Not listed by author; not presumed resolved" and item["source_refs"]
        for item in detail["obligation_reconciliation"]
    )
    source_ids = {item["id"] for item in detail["snapshot"]["sources"]}
    assert all(
        ref in source_ids for claim in detail["draft"]["claims"] for ref in claim["evidence_refs"]
    )
    expect(page.locator("body")).not_to_contain_text("internal server error")

    page.set_viewport_size({"width": 390, "height": 844})
    assert_project_actions()
    assert page.evaluate("document.documentElement.scrollWidth <= innerWidth")
    box = dialog.bounding_box()
    assert box and box["x"] >= 0 and box["y"] >= 0
    assert box["x"] + box["width"] <= 390 and box["y"] + box["height"] <= 844
    page.screenshot(path="/tmp/sigma-a20-paper-mobile.png", full_page=True)
    page.keyboard.press("Escape")
    expect(dialog).to_be_hidden()
    expect(export_dialog).to_be_hidden()
    expect(latex_button).to_be_focused()
    assert not errors, errors
    context.close()
    browser.close()

print(
    "PASS real Chrome A20: copper TeX and disabled Lean Project actions, tooltips, keyboard behavior, three-format Export Project, saved evidence, traceable claims, durable version and compiled PDF."
)
