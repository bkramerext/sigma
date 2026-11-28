"""Real Chrome Q/A workflow using the deterministic local provider fixture."""

import json
import os
import re
from pathlib import Path
from uuid import uuid4

from playwright.sync_api import expect, sync_playwright

UI = os.environ.get("SIGMA_QA_UI", "http://127.0.0.1:5174").rstrip("/")
OUT = Path("docs/evaluations/research_qa")
OUT.mkdir(parents=True, exist_ok=True)
EVIDENCE_PREFIX = f"fresh-{uuid4().hex}-"
print(f"Fresh Q/A screenshot evidence prefix: {EVIDENCE_PREFIX}", flush=True)


def evidence_path(name):
    return str(OUT / (EVIDENCE_PREFIX + name))


def title_geometry(title_line):
    """Measure one layout, in one DOM turn, relative to the card title anchor."""
    return title_line.evaluate("""anchor => {
        const title = anchor.querySelector('.saved-paper-title-toggle');
        const heading = anchor.querySelector('.saved-paper-title');
        const origin = anchor.getBoundingClientRect();
        const rect = r => ({
            x: r.x - origin.x, y: r.y - origin.y,
            right: r.right - origin.x, bottom: r.bottom - origin.y,
            width: r.width, height: r.height
        });
        const textRects = node => {
            const range = document.createRange();
            range.selectNodeContents(node);
            return [...range.getClientRects()].map(rect);
        };
        const tools = anchor.querySelector('.saved-paper-title-tools');
        const buttons = [...tools.querySelectorAll('button')].map(button => ({
            label: button.getAttribute('aria-label'),
            box: rect(button.getBoundingClientRect()),
            glyph: rect(button.querySelector('svg').getBoundingClientRect())
        }));
        const copy = tools.querySelector('button.text-copy-button svg');
        const bounds = copy.getBBox();
        const body = anchor.closest('.settings-body.ai-paper-body');
        return {
            anchor: {x: origin.x, y: origin.y, width: origin.width, height: origin.height},
            scroll: {
                x: body.scrollLeft, y: body.scrollTop,
                maxY: body.scrollHeight - body.clientHeight,
                windowX: window.scrollX, windowY: window.scrollY
            },
            title: textRects(title),
            heading: textRects(heading),
            buttons,
            copyBounds: {
                x: bounds.x, y: bounds.y, right: bounds.x + bounds.width,
                bottom: bounds.y + bounds.height, overflow: getComputedStyle(copy).overflow
            },
            expanded: title.getAttribute('aria-expanded')
        };
    }""")


def assert_same_title_geometry(before, after):
    # The clipboard checkmark may change the SVG path, never its viewport,
    # hit target, or location relative to the title and adjacent actions.
    assert before["title"] == after["title"], (before, after)
    assert before["expanded"] == after["expanded"], (before, after)
    assert len(before["buttons"]) == len(after["buttons"]), (before, after)
    for normal, current in zip(before["buttons"], after["buttons"], strict=True):
        assert normal["box"] == current["box"], (before, after)
        assert normal["glyph"] == current["glyph"], (before, after)


def assert_copy_geometry(snapshot, *, mobile=False):
    title_rects = snapshot["title"]
    assert len(title_rects) >= 2, snapshot
    last_title_rect = title_rects[-1]
    markdown, copy, *others = snapshot["buttons"]
    assert others, snapshot
    assert markdown["label"] == "Render answer as Markdown", snapshot
    markdown_box, copy_box = markdown["box"], copy["box"]
    assert markdown_box["width"] == markdown_box["height"] == 28, snapshot
    assert copy_box["width"] == copy_box["height"] == 28, snapshot
    assert copy_box["x"] > markdown_box["x"], snapshot
    assert copy_box["x"] - markdown_box["right"] == 12, snapshot
    assert abs(copy_box["y"] - markdown_box["y"]) <= 2, snapshot
    bounds = snapshot["copyBounds"]
    assert bounds["x"] >= 0 and bounds["y"] >= 0, snapshot
    assert bounds["right"] <= 24 and bounds["bottom"] <= 24, snapshot
    assert bounds["overflow"] == "visible", snapshot
    if mobile:
        assert len(snapshot["heading"]) >= 2, snapshot
        same_line = abs(markdown_box["y"] - last_title_rect["y"]) < 15
        if same_line:
            assert markdown_box["x"] >= last_title_rect["right"] - 1, snapshot
            assert markdown_box["x"] - last_title_rect["right"] <= 18, snapshot
        else:
            assert markdown_box["y"] >= last_title_rect["y"] + 10, snapshot
    else:
        same_line = (
            abs(
                (markdown_box["y"] + markdown_box["height"] / 2)
                - (last_title_rect["y"] + last_title_rect["height"] / 2)
            )
            < 14
        )
        if same_line:
            assert markdown_box["x"] >= last_title_rect["right"] - 1, snapshot
            assert abs(markdown_box["x"] - last_title_rect["right"] - 14) <= 2, snapshot
            left_glyph_gap = markdown["glyph"]["x"] - last_title_rect["right"]
            right_glyph_gap = copy["glyph"]["x"] - markdown["glyph"]["right"]
            assert abs(left_glyph_gap - right_glyph_gap) <= 3, snapshot
            assert (
                abs(
                    (copy_box["y"] + copy_box["height"] / 2)
                    - (last_title_rect["y"] + last_title_rect["height"] / 2)
                )
                < 14
            ), snapshot
        else:
            assert markdown_box["y"] >= last_title_rect["bottom"] - 1, snapshot
            assert abs(markdown_box["x"] - last_title_rect["x"] - 14) <= 2, snapshot
            assert copy_box["y"] >= last_title_rect["bottom"] - 1, snapshot

    # A title may wrap, but neither control may cover any actual text line.
    # Retain the original one-pixel edge allowance.
    for text_rect in title_rects:
        for box in (markdown_box, copy_box):
            overlap_x = min(box["right"], text_rect["right"]) - max(box["x"], text_rect["x"])
            overlap_y = min(box["bottom"], text_rect["bottom"]) - max(box["y"], text_rect["y"])
            assert overlap_x <= 1 or overlap_y <= 1, snapshot


def verify_scroll_invariance(title_line, before):
    # Scroll the real nested dialog scrollport, not a synthetic coordinate
    # offset. One endpoint must differ from the measured starting position.
    title_line.evaluate("""anchor => {
        const body = anchor.closest('.settings-body.ai-paper-body');
        const max = body.scrollHeight - body.clientHeight;
        body.scrollTop = body.scrollTop < max / 2 ? max : 0;
    }""")
    shifted = title_geometry(title_line)
    print(
        "Q/A deliberate scroll geometry: "
        + json.dumps(
            {
                "before": {"anchor": before["anchor"], "scroll": before["scroll"]},
                "after": {"anchor": shifted["anchor"], "scroll": shifted["scroll"]},
            },
            sort_keys=True,
        ),
        flush=True,
    )
    assert shifted["scroll"]["y"] != before["scroll"]["y"], (before, shifted)
    assert shifted["anchor"]["y"] != before["anchor"]["y"], (before, shifted)
    assert_same_title_geometry(before, shifted)
    title_line.scroll_into_view_if_needed()
    restored = title_geometry(title_line)
    assert_same_title_geometry(before, restored)
    return restored


def verify_negative_geometry_controls(title_line, before):
    # Use actual DOM perturbations, then restore the exact prior inline style.
    # A genuine relative position or size regression must not pass the new
    # invariant just because the enclosing card or scrollport also moved.
    button = title_line.locator("button.text-copy-button")
    original_style = button.get_attribute("style")
    for property_name, value in (
        ("transform", "translateX(4px)"),
        ("height", "32px"),
    ):
        try:
            button.evaluate(
                "(el, pair) => el.style.setProperty(pair[0], pair[1], 'important')",
                [property_name, value],
            )
            changed = title_geometry(title_line)
            assert changed["buttons"][1]["box"] != before["buttons"][1]["box"], changed
            try:
                assert_same_title_geometry(before, changed)
            except AssertionError:
                print(f"Q/A negative control rejected actual {property_name} change", flush=True)
            else:
                raise AssertionError(f"Q/A relative geometry missed {property_name} change")
        finally:
            button.evaluate(
                "(el, style) => style === null ? el.removeAttribute('style') "
                ": el.setAttribute('style', style)",
                original_style,
            )
        assert_same_title_geometry(before, title_geometry(title_line))


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
    fail_background_archive_reads = [0]
    missing_archive_reads = [0]
    page.on("pageerror", lambda error: errors.append(str(error)))

    def forward(route):
        # Never let background refresh consume a user-action failure injection.
        if route.request.headers.get("x-sigma-error-handled") == "true":
            if fail_background_archive_reads[0]:
                fail_background_archive_reads[0] -= 1
                route.fulfill(
                    status=503,
                    content_type="application/json",
                    body='{"error":"fixture background archive outage"}',
                )
                return
            route.continue_()
            return
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

    # Intercept only intentional archive failure injections. All other
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
    page.get_by_role("button", name="New session").click()

    # The removed top-level Settings action is not available during Start.
    # Limit this deterministic one-pair fixture through request interception;
    # the actual Start Session UI and backend admission path are still exercised.
    def one_pair_start(route):
        payload = route.request.post_data_json
        payload["session_settings"]["turn_limit"] = 1
        route.continue_(post_data=json.dumps(payload))

    page.route("**/api/projects/research-sessions/start", one_pair_start)
    page.get_by_role("button", name="Start Session").click()
    expect(page.locator("li[data-session-id]").first.locator(".session-status")).to_have_text(
        "ended", timeout=30000
    )
    audit_before = page.evaluate(
        "async path => (await (await fetch('/api/projects/audit?' + new URLSearchParams({path}))).json())",
        path,
    )

    # Current Understanding: a second click with the same cached Model/Thinking
    # must not show AI formatting, even transiently, or dispatch a new request.
    current_panel = page.locator(".current-understanding")
    expect(current_panel).to_have_count(1)
    current_button = current_panel.locator("button.current-understanding-markdown")
    expect(current_button).to_have_attribute(
        "aria-label", "Format Current Understanding as Markdown"
    )
    current_requests = []

    def current_markdown_fixture(route):
        payload = route.request.post_data_json
        if payload.get("scope") != "current-understanding":
            route.continue_()
            return
        current_requests.append(payload["field_path"])
        route.fulfill(
            status=200,
            content_type="application/json",
            body=json.dumps(
                {
                    "body": "Cached preview fixture for " + payload["field_path"],
                    "source_digest": payload["expected_digest"],
                }
            ),
        )

    context.route("**/api/projects/text/convert", current_markdown_fixture)
    current_button.click()
    expect(current_panel.locator(".current-understanding-rendered").first).to_contain_text(
        "Cached preview fixture", timeout=30000
    )
    expect(current_panel.locator(".text-view-format-status")).to_have_count(0, timeout=30000)
    assert current_requests, "The initial Current Understanding formatting must convert text"
    initial_request_count = len(current_requests)
    current_button.click()
    expect(current_button).to_have_attribute("aria-pressed", "false")
    expect(current_panel.locator(".text-view-format-status")).to_have_count(0)
    current_panel.evaluate("""node => {
        node.dataset.cachedFormattingShown = 'false';
        const observer = new MutationObserver(() => {
            if (node.querySelector('.text-view-format-status, .sigma-unified-hourglass'))
                node.dataset.cachedFormattingShown = 'true';
        });
        observer.observe(node, {subtree: true, childList: true});
        node.__markdownCacheObserver = observer;
    }""")
    current_button.click()
    expect(current_button).to_have_attribute("aria-pressed", "true")
    expect(current_panel.locator(".current-understanding-rendered").first).to_contain_text(
        "Cached preview fixture"
    )
    assert current_panel.get_attribute("data-cached-formatting-shown") == "false"
    assert len(current_requests) == initial_request_count, current_requests
    current_panel.evaluate("node => node.__markdownCacheObserver.disconnect()")
    context.unroute("**/api/projects/text/convert", current_markdown_fixture)

    qa_button = page.get_by_role("button", name="Research Q/A", exact=True)
    expect(qa_button).to_be_visible()
    assert qa_button.bounding_box() is not None
    assert qa_button.get_attribute("aria-label") == "Research Q/A"
    lean = page.get_by_role("button", name="Lean proof verification", exact=True)
    expect(lean).to_be_visible()
    expect(lean).to_be_enabled()
    assert qa_button.bounding_box()["x"] < lean.bounding_box()["x"]
    # LEAN's larger artwork requires a larger hover surface than the Q/A glyph.
    lean_box = lean.bounding_box()
    qa_box = qa_button.bounding_box()
    assert lean_box is not None and qa_box is not None
    assert lean_box["height"] >= qa_box["height"]
    assert lean_box["width"] >= qa_box["width"]
    icon_box = lean.locator("img").bounding_box()
    assert icon_box is not None
    assert icon_box["x"] >= lean_box["x"]
    assert icon_box["x"] + icon_box["width"] <= lean_box["x"] + lean_box["width"]
    expect(lean.locator("img")).to_have_attribute("src", "/lean-logo.svg")
    lean.click()
    lean_dialog = page.get_by_role("dialog", name="Lean proof verification")
    expect(lean_dialog.locator(".settings-body p")).to_contain_text(
        "Yeah, I'd love to see this too."
    )
    expect(lean_dialog.locator(".settings-body p br")).to_have_count(1)
    expect(lean_dialog).to_contain_text("Still under consideration!")
    lean_dialog.get_by_role("button", name="Close Lean dialog").click()
    expect(lean_dialog).to_be_hidden()
    expect(lean).to_be_focused()
    expect(page.locator(".papers-pane").get_by_role("heading", name="Papers")).to_be_visible()
    page.screenshot(path=evidence_path("research-qa-toolbar.png"), full_page=False)

    # One transient model configuration failure must not permanently disable
    # Ask. Archive reads remain independent; no provider call is retried.
    fail_model_config = [1]

    def fail_config_once(route):
        if fail_model_config[0]:
            fail_model_config[0] -= 1
            route.fulfill(
                status=503,
                content_type="application/json",
                body='{"error":"fixture transient model configuration outage"}',
            )
            return
        route.continue_()

    context.route(re.compile(r"/api/projects/proposals/config\?"), fail_config_once)
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
    expect(dialog.get_by_role("button", name="Ask", exact=True)).to_be_enabled(timeout=15000)
    assert fail_model_config[0] == 0, "Transient model configuration failure was not exercised"
    expect(dialog.get_by_text("Could not load model settings", exact=False)).to_have_count(0)
    dialog.get_by_role("button", name="Ask", exact=True).click()
    expect(dialog.locator(".sigma-inert-progress")).to_contain_text("⌛ Answering…")
    expect(dialog.get_by_role("button", name="Answering")).to_have_count(0)
    dialog.get_by_role("button", name="Cancel", exact=True).click()
    expect(dialog.get_by_role("alert")).to_have_count(0)
    expect(dialog.get_by_role("button", name="Ask", exact=True)).to_be_enabled()
    dialog.get_by_role("button", name="Close research Q/A", exact=True).click()
    expect(dialog).not_to_be_visible()
    page.get_by_role("button", name="Research Q/A", exact=True).click()
    dialog = page.get_by_role("dialog", name="Research Q/A")
    expect(dialog.get_by_role("textbox", name="Question", exact=True)).to_have_value(question)
    expect(dialog.get_by_role("group", name="Recover interrupted Q/A request")).to_have_count(0)
    ask_button = dialog.get_by_role("button", name="Ask", exact=True)
    expect(ask_button).to_be_enabled()
    with page.expect_response(
        lambda response: (
            "/api/projects/research-qa?" in response.url
            and response.status == 503
            and response.request.headers.get("x-sigma-error-handled") == "true"
        ),
        timeout=15000,
    ):
        fail_background_archive_reads[0] = 1
    expect(dialog.get_by_role("alert")).to_have_count(0)
    expect(dialog.get_by_role("textbox", name="Question", exact=True)).to_have_value(question)
    fail_archive_reads[0] = 1
    ask_button.click()
    expect(dialog.get_by_role("alert")).to_contain_text("fixture archive unavailable")
    assert fail_archive_reads[0] == 0
    expect(ask_button).to_be_enabled()
    expect(dialog.get_by_role("textbox", name="Question", exact=True)).to_have_value(question)
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
    # An unrelated archive/polling toast may be visible while the provider
    # request is still in flight. Only the injected HTTP 500 proves that this
    # failure/retry scenario reached the provider; a generic alert does not.
    expect(dialog.get_by_role("alert")).to_contain_text(
        "Research Q/A provider request failed", timeout=30000
    )
    expect(dialog.get_by_role("group", name="Recover interrupted Q/A request")).to_have_count(0)
    expect(dialog.get_by_role("group", name="Confirm a fresh Q/A request")).to_have_count(0)
    ask_button = dialog.get_by_role("button", name="Ask", exact=True)
    expect(ask_button).to_be_enabled()
    failed_state_before_retry = page.evaluate(
        "async () => (await (await fetch('/api/__fixture/qa-state')).json())"
    )
    assert failed_state_before_retry["started"] == state_after_cancel["started"] + 1, (
        "Injected HTTP 500 must have dispatched exactly one provider request",
        state_after_cancel,
        failed_state_before_retry,
    )
    # Failure display is a single dismissible toast; dismissal is not a retry.
    dialog.get_by_role("button", name="Dismiss").click()
    expect(dialog.get_by_role("alert")).to_have_count(0)
    expect(ask_button).to_be_enabled()
    fail_archive_reads[0] = 1
    ask_button.click()
    expect(dialog.get_by_role("alert")).to_contain_text("fixture archive unavailable")
    expect(ask_button).to_be_enabled()
    assert fail_archive_reads[0] == 0
    expect(dialog.get_by_role("textbox", name="Question", exact=True)).to_have_value(
        failed_question
    )
    failed_state_after_archive_error = page.evaluate(
        "async () => (await (await fetch('/api/__fixture/qa-state')).json())"
    )
    assert failed_state_after_archive_error["started"] == failed_state_before_retry["started"]
    ask_button.click()
    expect(dialog.locator(".sigma-inert-progress")).to_contain_text("⌛ Answering…")
    expect(dialog.locator(".saved-paper-card").first).to_contain_text(
        failed_question, timeout=30000
    )
    state_after_retry = page.evaluate(
        "async () => (await (await fetch('/api/__fixture/qa-state')).json())"
    )
    assert state_after_retry["started"] == failed_state_before_retry["started"] + 1, (
        "Explicit retry must dispatch exactly once, without automatic replay",
        failed_state_before_retry,
        state_after_retry,
    )

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
    title_toggle.evaluate("el => el.blur()")
    page.mouse.move(1, 1)
    title_line.screenshot(path=evidence_path("research-qa-title-normal.png"))
    markdown_icon = title_line.get_by_role("button", name="Render answer as Markdown")
    expect(markdown_icon).to_be_visible()
    expect(markdown_icon).to_have_attribute("data-tooltip", "Convert to markdown")
    expect(markdown_icon.locator("svg.markdown-logo")).to_have_count(1)
    normal = title_geometry(title_line)
    assert normal["buttons"][1]["label"] == "Copy Markdown answer", normal
    assert_copy_geometry(normal)
    normal = verify_scroll_invariance(title_line, normal)
    verify_negative_geometry_controls(title_line, normal)

    title_line.get_by_role("button", name="Copy Markdown answer").click()
    copied_button = title_line.get_by_role("button", name="Copied Markdown answer to clipboard")
    expect(copied_button).to_be_visible(timeout=3000)
    title_line.screenshot(path=evidence_path("research-qa-title-copied.png"))
    copied_geometry = title_geometry(title_line)
    assert copied_geometry["buttons"][1]["label"] == "Copied Markdown answer to clipboard"
    assert_copy_geometry(copied_geometry)
    assert_same_title_geometry(normal, copied_geometry)
    print(
        "Q/A desktop normal/copied geometry: "
        + json.dumps({"normal": normal, "copied": copied_geometry}, sort_keys=True),
        flush=True,
    )
    expect(card.locator(".saved-paper-expand")).to_have_attribute(
        "aria-expanded", expanded_before_copy
    )
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
    # The feedback label is transient; the same copy control must report an
    # error even if its earlier successful feedback has already expired.
    title_line.locator("button.text-copy-button").click()
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
    # Switching from Markdown to plain is purely local: no AI formatting,
    # no hourglass, and no provider conversion request.
    expect(title_line.get_by_role("status")).to_have_count(0)
    expect(title_line.locator(".sigma-unified-hourglass")).to_have_count(0)
    assert len(conversion_requests) == 1, conversion_requests
    title_line.evaluate("""node => {
        node.dataset.cachedFormattingShown = 'false';
        const observer = new MutationObserver(() => {
            if (node.querySelector('.text-view-format-status, .sigma-unified-hourglass'))
                node.dataset.cachedFormattingShown = 'true';
        });
        observer.observe(node, {subtree: true, childList: true});
        node.__markdownCacheObserver = observer;
    }""")
    title_line.get_by_role("button", name="Render answer as Markdown").click()
    expect(card.locator(".outcome-markdown")).to_contain_text("The saved research answers")
    assert title_line.get_attribute("data-cached-formatting-shown") == "false"
    expect(title_line.get_by_role("status")).to_have_count(0)
    title_line.evaluate("node => node.__markdownCacheObserver.disconnect()")
    # The conversion is saved on the answer, not recomputed on a second toggle.
    stored = page.evaluate(
        "async path => (await (await fetch('/api/projects/research-qa?' + new URLSearchParams({path}))).json()).answers",
        path,
    )
    assert stored[0]["markdown_answer"]
    assert len(conversion_requests) == 1, conversion_requests

    with page.expect_popup() as popup:
        card.get_by_role("button", name="View answer in a new browser tab").click()
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
    browser_page.screenshot(path=evidence_path("research-qa-browser-desktop.png"), full_page=True)
    browser_page.set_viewport_size({"width": 390, "height": 844})
    browser_page.screenshot(path=evidence_path("research-qa-browser-mobile.png"), full_page=True)
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
            expect(
                browser_page.locator("button.strategy-row-disclosure[id^='strategy-']").first
            ).to_be_visible(timeout=15000)
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
    page.screenshot(path=evidence_path("research-qa-mobile.png"), full_page=True)
    mobile_dialog = page.get_by_role("dialog", name="Research Q/A")
    assert mobile_dialog.bounding_box()["width"] <= 390
    mobile_title = mobile_dialog.locator(".saved-paper-card").first.locator(
        ".saved-paper-title-line"
    )
    mobile_title.screenshot(path=evidence_path("research-qa-title-mobile.png"))
    mobile_toggle_before_copy = mobile_title.locator(".saved-paper-expand").get_attribute(
        "aria-expanded"
    )
    mobile_normal = title_geometry(mobile_title)
    assert mobile_normal["buttons"][1]["label"] == "Copy Markdown answer", mobile_normal
    assert_copy_geometry(mobile_normal, mobile=True)
    mobile_title.get_by_role("button", name="Copy Markdown answer").click()
    expect(
        mobile_title.get_by_role("button", name="Copied Markdown answer to clipboard")
    ).to_be_visible(timeout=3000)
    mobile_title.screenshot(path=evidence_path("research-qa-title-mobile-copied.png"))
    mobile_copied_geometry = title_geometry(mobile_title)
    assert mobile_copied_geometry["buttons"][1]["label"] == "Copied Markdown answer to clipboard"
    assert_copy_geometry(mobile_copied_geometry, mobile=True)
    assert_same_title_geometry(mobile_normal, mobile_copied_geometry)
    print(
        "Q/A mobile normal/copied geometry: "
        + json.dumps({"normal": mobile_normal, "copied": mobile_copied_geometry}, sort_keys=True),
        flush=True,
    )
    assert (
        mobile_title.locator(".saved-paper-expand").get_attribute("aria-expanded")
        == mobile_toggle_before_copy
    )
    mobile_copied = page.evaluate("navigator.clipboard.readText()")
    assert mobile_copied.startswith("# Research Q/A") and question in mobile_copied
    remove = mobile_dialog.locator(".saved-paper-card").first.get_by_role(
        "button", name="Remove answer", exact=True
    )
    remove.click()
    mobile_dialog.get_by_role("button", name="Confirm", exact=True).click()
    expect(mobile_dialog.locator(".saved-paper-card")).to_have_count(1)
    assert not errors, errors
    print(
        "Research Q/A Chrome acceptance passed: recovery, archive actions, Markdown and copy icon alignment, browser/remove actions, 40px nested scroll padding, granular session Outcome/artifact citations, research version, desktop/mobile layout, clipboard errors, and no new research session."
    )
    browser.close()
