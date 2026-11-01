"""Real Chrome checks for saved session Conclusions at desktop and phone widths."""

import hashlib
import json
import os
import socket
import subprocess
import tempfile
import time
from pathlib import Path
from urllib.parse import quote

from playwright.sync_api import expect, sync_playwright

REPO = Path(__file__).resolve().parents[1]
SCREENSHOT_DIR = Path(os.environ.get("SIGMA_OUTCOME_SCREENSHOT_DIR", "/tmp"))
SCREENSHOT_DIR.mkdir(parents=True, exist_ok=True)
ARCHIVE = (
    REPO
    / "docs/evaluations/fixtures/t17-8-answer-free/live-session-91e96112-27ce-412e-841f-5cbf67cbba75.json"
)
CHROME = os.environ.get(
    "SIGMA_BROWSER_EXECUTABLE", "/Applications/Google Chrome.app/Contents/MacOS/Google Chrome"
)


def free_port() -> int:
    with socket.socket() as listener:
        listener.bind(("127.0.0.1", 0))
        return int(listener.getsockname()[1])


def wait_for(url: str, process: subprocess.Popen, timeout: float = 30) -> None:
    import urllib.error
    import urllib.request

    deadline = time.monotonic() + timeout
    while time.monotonic() < deadline:
        if process.poll() is not None:
            raise AssertionError(f"Isolated server exited with status {process.returncode}")
        try:
            with urllib.request.urlopen(url, timeout=1):
                return
        except (OSError, urllib.error.URLError):
            time.sleep(0.1)
    raise AssertionError(f"Isolated server did not become ready: {url}")


with tempfile.TemporaryDirectory(prefix="sigma-t47-browser-") as temporary:
    root = Path(temporary)
    project_path = root / "conclusions.sigma"
    archived = json.loads(ARCHIVE.read_text(encoding="utf-8"))
    project = archived["project"]
    session = archived["research_sessions"][0]
    # Reuse an archived record to exercise the pause explanation without
    # starting or fabricating provider work.
    session["status"] = "paused"
    session["message"] = (
        "Paused by user. A dispatched provider request may still consume allowance."
    )
    sessions_path = project_path / "research-sessions"
    sessions_path.mkdir(parents=True)
    (project_path / "project.json").write_text(json.dumps(project), encoding="utf-8")
    session["project_path"] = str(project_path.resolve())
    session["outcome"]["conclusion"] = (
        "### Preliminary finding\n\n"
        "For the meromorphic continuation ζ(s)=s/(s−1)−s∫_1^∞{x}^{−s−1} dx on Re(s)>0, "
        "ζ(σ+it)≠0 whenever T=|t|≥1 and σ≥1−1/[256(4T+9)^4(2T+4)]. "
        "This does not prove or disprove the Riemann Hypothesis.\n\n"
        "The investigation is paused; this is not a completed conclusion.\n\n"
        "The Euler-product logarithm and 3+4cosθ+cos(2θ)≥0 imply ζ(1+it)^3|ζ(1+2it)|≥1. "
        "A zero at β+it with β≥1−ε would imply |ζ(1+it)|≤2rM(T), "
        "where M(T)=4T+9. Choosing ε=1/[256(4T+9)^4(2T+4)] forces the product to be at most 1/2."
    )
    session["outcome"]["conclusion"] += (
        "\n\nA model_output label remains ordinary prose, while a_n is indexed notation.\n\n"
        + (
            "Display fixture only: this saved notation is used to check presentation, not to claim a verified result. "
            * 12
        )
    )
    # Exact AI Agents proof excerpt reproducing fused commands and bad fractions.
    session["outcome"]["conclusion"] += (
        "\n\n"
        "Let X_hi=(1/r_h)Σ_j(S_Ahij−S_Bhij), so X_hi∈[−1,1], and D=Σ_h(w_h/n_h)Σ_i "
        "X_hi. Under independent clusters, E[D]=d. A centered variable supported on an "
        "interval of length 2 has moment-generating function at most exp(λ²/2). "
        "Applying this bound to the weighted independent X_hi gives "
        "E[exp(λ(D−d))]≤exp(λ²V/2), where V=Σ_h w_h²/n_h. Markov's inequality and "
        "minimization at λ=t/V give Pr(D−d≥t)≤exp(−t²/(2V)). Taking t=sqrt(2V log(1/α)) "
        "shows d≥D−t with probability at least 1−α. Repetition count r_h does not enter "
        "the worst-case radius: perfectly correlated repeats cannot create additional "
        "independent tasks."
        "\n\n"
        "**Skeptic review:** accepted — Each cluster average has range length two. The "
        "centered bounded-variable inequality therefore contributes exp(λ²a_hi²/2) for "
        "weight a_hi=w_h/n_h. Independence across complete clusters gives Σ_hi "
        "a_hi²=Σ_h w_h²/n_h and the stated one-sided tail radius. No independence among "
        "repeated runs is required."
    )
    session["outcome"]["solution_review"] = {
        "status": "achieved",
        "claim": "Conditional on general position, R(n) = 1 + n(n+1)/2.",
        "claim_scope": "conditional",
        "argument_summary": "The insertion bound and attaining construction match under the premise.",
        "assumptions": ["The lines are in general position."],
        "proof_obligations": [],
        "open_obligations": [],
        "argument_steps": [
            {
                "number": 1,
                "title": "Bound the pieces made by the new line",
                "argument": "At most n−1 crossings divide the new line into at most n pieces.",
                "epistemic_status": "deduction",
                "basis_artifact_ids": [],
                "research_artifact_id": session["artifacts"][0]["id"],
                "review": {
                    "disposition": "accepted",
                    "rationale": "The intersection bound yields at most n pieces.",
                    "objection": "",
                    "basis_artifact_ids": [],
                },
            }
        ],
        "strategy_findings": [],
        "skeptic_response": "The local insertion inference is sound under the stated premise.",
        "skeptic_objections": [],
        "unresolved_objections": [],
        "resolved_objections": [],
        "basis_artifact_ids": [],
    }
    latest_artifact = session["artifacts"][-1]
    latest_artifact["reasoning_steps"] = session["outcome"]["solution_review"]["argument_steps"]
    latest_artifact["objective_review"] = {
        key: value
        for key, value in session["outcome"]["solution_review"].items()
        if key
        in {
            "status",
            "claim",
            "claim_scope",
            "argument_summary",
            "assumptions",
            "proof_obligations",
            "open_obligations",
            "unresolved_objections",
            "resolved_objections",
            "basis_artifact_ids",
            "argument_steps",
        }
    }
    session["outcome_conclusion_version"] = 1
    (sessions_path / f"{session['id']}.json").write_text(
        json.dumps(session, ensure_ascii=False), encoding="utf-8"
    )
    sessions = [session]

    api_port, ui_port = free_port(), free_port()
    while ui_port == api_port:
        ui_port = free_port()
    api_url, ui_url = f"http://127.0.0.1:{api_port}", f"http://127.0.0.1:{ui_port}"
    environment = os.environ.copy()
    environment["SIGMA_PROJECTS_ROOT"] = str(root)
    api = subprocess.Popen(
        [
            "uv",
            "run",
            "--project",
            str(REPO),
            "python",
            "-m",
            "uvicorn",
            "sigma.server:create_app",
            "--factory",
            "--host",
            "127.0.0.1",
            "--port",
            str(api_port),
        ],
        cwd=REPO,
        env=environment,
        stdout=subprocess.DEVNULL,
        stderr=subprocess.DEVNULL,
    )
    environment["SIGMA_API_TARGET"] = api_url
    ui = subprocess.Popen(
        [
            "npm",
            "--prefix",
            str(REPO / "frontend"),
            "run",
            "dev",
            "--",
            "--host",
            "127.0.0.1",
            "--port",
            str(ui_port),
        ],
        cwd=REPO,
        env=environment,
        stdout=subprocess.DEVNULL,
        stderr=subprocess.DEVNULL,
    )
    try:
        wait_for(api_url + "/openapi.json", api)
        wait_for(ui_url, ui)
        with sync_playwright() as playwright:
            browser = playwright.chromium.launch(
                executable_path=CHROME, headless=True, args=["--disable-web-security"]
            )
            page = browser.new_page(viewport={"width": 1440, "height": 1000})
            page.context.grant_permissions(["clipboard-read", "clipboard-write"], origin=ui_url)
            errors: list[str] = []
            starts: list[str] = []
            page.on("pageerror", lambda error: errors.append(str(error)))
            page.on(
                "request",
                lambda request: (
                    starts.append(request.url)
                    if request.url.endswith("/api/projects/research-sessions/start")
                    else None
                ),
            )
            pending_text_routes: list[object] = []

            def mock_conversion_settings(route):
                route.fulfill(
                    status=200,
                    content_type="application/json",
                    body=json.dumps({"available": True, "binding": "fixture-binding"}),
                )

            def queue_text_conversion(route):
                pending_text_routes.append(route)

            page.route("**/api/projects/proposals/config**", mock_conversion_settings)
            page.route("**/api/projects/text/convert", queue_text_conversion)
            page.goto(f"{ui_url}/project?path={quote(str(project_path), safe='')}")
            project_markdown = page.locator("#project-markdown-slot .sigma-render-toggle")
            expect(project_markdown).to_be_visible()
            project_copy = page.locator("#project-markdown-slot-copy .text-copy-button")
            expect(project_copy).to_be_enabled()
            page.locator(".project-pane-title-line").screenshot(
                path="/tmp/sigma-copy-buttons-desktop.png"
            )
            project_copy.click()
            expect(project_copy).to_have_accessible_name("Copied research problem to clipboard")
            assert page.evaluate("navigator.clipboard.readText()") == project["problem"]
            # The confirmation checkmark does not disable the button; a second click copies again.
            project_copy.click()
            assert page.evaluate("navigator.clipboard.readText()") == project["problem"]
            project_markdown.click()
            project_status = page.locator("#project-markdown-slot .text-view-format-status")
            expect(project_status).to_be_visible()
            assert (
                project_status.evaluate("element => getComputedStyle(element.parentElement).gap")
                == "6px"
            )
            page.locator(".project-pane-title-line").screenshot(
                path="/tmp/sigma-project-markdown-formatting.png"
            )
            page.set_viewport_size({"width": 390, "height": 844})
            assert page.evaluate("document.documentElement.scrollWidth <= innerWidth")
            expect(project_status).to_be_visible()
            page.screenshot(path="/tmp/sigma-project-markdown-formatting-mobile.png")
            page.locator(".project-pane-title-line").screenshot(
                path="/tmp/sigma-copy-buttons-mobile.png"
            )
            page.set_viewport_size({"width": 1440, "height": 1000})
            project_copy_response = {
                "scope": "project",
                "strategy_id": None,
                "source_format": "plain",
                "source_digest": hashlib.sha256(project["problem"].encode("utf-8")).hexdigest(),
                "plain": {"body": project["problem"], "current": True},
                "markdown": {
                    "body": "## Fixture\n\nThis **description** has regular text.",
                    "current": True,
                },
            }
            pending_text_routes.pop(0).fulfill(
                status=200,
                content_type="application/json",
                body=json.dumps(project_copy_response),
            )
            expect(page.locator(".project-intro .rendered-text")).to_contain_text(
                "This description has regular text."
            )
            project_markdown = page.locator("#project-markdown-slot .sigma-render-toggle")
            expect(project_markdown).to_have_attribute("aria-pressed", "true")
            project_copy.click()
            expect(project_copy).to_have_accessible_name("Copied research problem to clipboard")
            copied_rendered_text = page.evaluate("navigator.clipboard.readText()")
            assert copied_rendered_text == "Fixture\n\nThis description has regular text.", repr(
                copied_rendered_text
            )
            assert "**" not in copied_rendered_text
            strategy_markdown = page.locator(".strategy-markdown-slot .sigma-render-toggle").first
            expect(strategy_markdown).to_be_visible()
            strategy_copy = page.locator(".strategy-copy-slot .text-copy-button").first
            expect(strategy_copy).to_be_enabled()
            strategy_copy.click()
            expect(strategy_copy).to_have_accessible_name("Copied strategy approach to clipboard")
            assert (
                page.evaluate("navigator.clipboard.readText()")
                == project["strategies"][0]["approach"]
            )
            strategy_copy.click()
            assert (
                page.evaluate("navigator.clipboard.readText()")
                == project["strategies"][0]["approach"]
            )
            strategy_markdown.click()
            strategy_status = page.locator(".strategy-markdown-slot .text-view-format-status").first
            expect(strategy_status).to_be_visible()
            assert (
                strategy_status.evaluate("element => getComputedStyle(element.parentElement).gap")
                == "6px"
            )
            page.locator(".strategy-title-line").first.screenshot(
                path="/tmp/sigma-strategy-markdown-formatting.png"
            )
            pending_text_routes.pop(0).fulfill(
                status=503,
                content_type="application/json",
                body='{"error":"Mock provider unavailable"}',
            )
            latex_button = page.get_by_role("button", name="LaTeX research paper")
            expect(latex_button).to_be_visible()
            latex_button.hover()
            latex_hover = latex_button.evaluate(
                "el => ({width: el.getBoundingClientRect().width, "
                "height: el.getBoundingClientRect().height, "
                "backgroundImage: getComputedStyle(el).backgroundImage})"
            )
            assert latex_hover["width"] == 50 and latex_hover["height"] == 34, latex_hover
            assert "gradient" in latex_hover["backgroundImage"], latex_hover
            expect(page.locator(".sessions-pane-heading .section-count")).to_contain_text(
                "1 session", timeout=15000
            )
            # The simplified Outcome hint directly enables the saved project preference.
            first_row = page.locator(f'li[data-session-id="{session["id"]}"]')
            first_disclosure = first_row.locator("button.session-row-disclosure")
            if first_disclosure.get_attribute("aria-expanded") != "true":
                first_disclosure.click()
            simple_outcome = first_row.get_by_role("region", name="Research outcome")
            hint = simple_outcome.locator(".advanced-outcome-hint")
            expect(hint).to_contain_text(
                "Want more detail? Turn on Advanced Outcome to see the full research findings and evidence."
            )
            dismiss_errors = page.get_by_role("button", name="Dismiss request error")
            for _ in range(4):
                if not dismiss_errors.count():
                    break
                # Animated toasts can move or expire before Playwright sees a
                # stable click target. Dispatch directly and allow exit removal.
                dismiss_errors.first.evaluate("button => button.click()")
                page.wait_for_timeout(350)
            expect(dismiss_errors).to_have_count(0, timeout=5000)
            simple_outcome.screenshot(path="/tmp/sigma-advanced-outcome-hint.png")
            preference_link = hint.get_by_role("button", name="Advanced Outcome")
            preference_link.focus()
            expect(preference_link).to_be_focused()
            preference_link.press("Enter")
            expect(hint).to_have_count(0)
            expect(simple_outcome.locator(".outcome-subsections")).to_be_visible()
            # Confirm the preference was persisted in the project settings.
            settings = page.get_by_role("button", name="Project settings", exact=True)
            settings.click()
            dialog = page.get_by_role("dialog", name="Settings")
            dialog.get_by_role("tab", name="Preferences").click()
            detail_setting = dialog.get_by_role("checkbox", name="Show advanced Outcome details")
            expect(detail_setting).to_be_checked()
            dialog.get_by_role("button", name="Cancel", exact=True).click()
            for session in sessions:
                row = page.locator(f'li[data-session-id="{session["id"]}"]')
                expect(row).to_be_visible(timeout=15000)
                disclosure = row.locator("button.session-row-disclosure")
                if disclosure.get_attribute("aria-expanded") != "true":
                    disclosure.click()
                outcome = row.get_by_role("region", name="Research outcome")
                conclusion = outcome.locator("details.outcome-conclusion")
                expect(conclusion).to_be_visible()
                assert conclusion.get_attribute("open") is not None
                assert conclusion.locator("summary").inner_text().strip() == "Conclusion"
                prelude = outcome.locator(".outcome-evidence-prelude")
                expect(prelude).to_be_visible()
                pause_notice = outcome.locator(".research-pause-guidance")
                expect(pause_notice).to_be_visible()
                expect(pause_notice).to_contain_text("Session paused")
                expect(pause_notice).to_contain_text(
                    "A dispatched provider request may still consume allowance."
                )
                expect(pause_notice).to_contain_text(
                    "Resume when you are ready for new provider work."
                )
                expect(row.get_by_role("button", name="Resume")).to_be_visible()
                expect(prelude).to_contain_text(
                    "0 reported completed of 0 identified saved executions"
                )
                expect(prelude).to_contain_text(
                    "No local Python or Sage computation is recorded for this session."
                )
                expect(prelude).to_contain_text(
                    "Computational claims in the agent-authored conclusion are not supported"
                )
                expect(prelude).to_contain_text("No persisted Python/SageMath execution records")
                assert prelude.evaluate(
                    "element => (element.compareDocumentPosition(element.parentElement.querySelector('.outcome-subsections')) & Node.DOCUMENT_POSITION_FOLLOWING) !== 0"
                ), "Saved computation provenance must precede the Advanced Outcome narrative"
                expect(conclusion).to_contain_text("The investigation is paused")
                # Conclusion has no duplicate Markdown action. The Outcome
                # heading controls formatting for research sections.
                expect(conclusion.locator(":scope > .sigma-render-toggle")).to_have_count(0)
                source_toggle = outcome.locator(".outcome-heading-title > .sigma-render-toggle")
                expect(source_toggle).to_be_visible()
                expect(source_toggle).to_have_attribute("aria-pressed", "false")
                expect(conclusion.locator(".outcome-markdown .katex").first).to_be_visible()
                expect(conclusion.locator(".outcome-markdown .katex-error")).to_have_count(0)
                finding = conclusion.locator(".outcome-markdown h3").first
                expect(finding).to_be_visible()
                expect(finding).to_have_text("Preliminary finding")
                expect(conclusion.locator(".outcome-markdown .katex").first).to_be_visible()
                math_nodes = conclusion.locator(".outcome-markdown .katex")
                annotations = math_nodes.evaluate_all(
                    'nodes => nodes.map(node => node.querySelector("annotation")?.textContent || "")'
                )
                # Inline Unicode comparisons must not fuse TeX control words,
                # and quotients must not replace only the subscript's operand.
                assert not any(
                    fragment in annotation
                    for annotation in annotations
                    for fragment in ("\\leexp", "\\get", "w_\\frac")
                ), annotations
                assert any("\\le exp" in value for value in annotations), annotations
                assert math_nodes.count() >= 8, (
                    f"Expected at least eight mathematical spans, got {math_nodes.count()}: "
                    f"{annotations}"
                )
                fraction_count = conclusion.locator(".outcome-markdown .katex mfrac").count()
                assert fraction_count >= 2, (
                    f"Expected two rendered fractions, got {fraction_count}: {annotations}"
                )
                assert any(
                    "\\zeta(s)" in value and "\\frac{s}{s-1}" in value for value in annotations
                ), annotations
                assert any("\\ne0" in value for value in annotations), annotations
                assert any("\\sigma\\ge1" in value for value in annotations), annotations
                assert any("\\frac{1}{256(4T+9)^4(2T+4)}" in value for value in annotations), (
                    annotations
                )
                assert conclusion.locator(".outcome-markdown .katex msup").count() >= 1
                assert conclusion.locator(".outcome-markdown .katex msub").count() >= 1
                expect(conclusion.locator(".outcome-markdown .katex-error")).to_have_count(0)
                expect(conclusion.locator(".outcome-markdown img")).to_have_count(0)
                expect(conclusion.locator(".outcome-markdown")).to_contain_text(
                    "A model_output label remains ordinary prose"
                )
                assert all(
                    "model_output" not in text
                    for text in conclusion.locator(".outcome-markdown .katex").all_inner_texts()
                )
                expect(conclusion.locator(".outcome-markdown")).not_to_contain_text(
                    "### Preliminary finding"
                )
                expect(conclusion.locator(".outcome-markdown .katex").first).to_be_visible()
                expect(conclusion.locator(".outcome-markdown")).to_contain_text(
                    "The investigation is paused; this is not a completed conclusion."
                )
                page.mouse.move(1300, 900)
                conclusion.screenshot(path="/tmp/sigma-conclusion-typeset-desktop.png")
                # First click turns on all research sections; second returns
                # to saved text, including Conclusion.
                source_toggle.click()
                expect(source_toggle).to_have_attribute("aria-pressed", "true")
                source_toggle.click()
                expect(conclusion.locator(".outcome-conclusion-source")).to_be_visible()
                expect(source_toggle).to_have_attribute("aria-pressed", "false")
                expect(conclusion.locator(".outcome-conclusion-source")).to_contain_text(
                    "ζ(s)=s/(s−1)"
                )
                assert (
                    conclusion.locator(".outcome-conclusion-source").evaluate(
                        "element => element.textContent"
                    )
                    == session["outcome"]["conclusion"]
                )
                expect(conclusion.locator(".outcome-conclusion-source")).not_to_contain_text("$$")
                source_toggle.click()
                expect(source_toggle).to_have_attribute("aria-pressed", "true")
                expect(conclusion.locator(".outcome-markdown h3").first).to_have_text(
                    "Preliminary finding"
                )
                # Markdown headings belong inside the compact research
                # disclosure, not at document-cover typography sizes.
                reasoning = outcome.locator(".outcome-reasoning-subsection")
                reasoning.locator(":scope > summary").click()
                heading = reasoning.locator(".outcome-markdown h1").first
                subheading = reasoning.locator(".outcome-markdown h2").first
                expect(heading).to_have_text("Reasoning / proof")
                expect(subheading).to_have_text("Investigated problem")
                assert (
                    heading.evaluate(
                        "element => Number.parseFloat(getComputedStyle(element).fontSize)"
                    )
                    <= 20
                )
                assert (
                    subheading.evaluate(
                        "element => Number.parseFloat(getComputedStyle(element).fontSize)"
                    )
                    <= 17
                )
                outcome.locator(".outcome-evidence-subsection > summary").click()
                expect(outcome.locator(".outcome-evidence-subsection")).to_be_visible()
                expect(outcome).to_contain_text("Bound the pieces made by the new line")
                expect(outcome).to_contain_text("The intersection bound yields at most n pieces.")
                page.screenshot(
                    path=str(SCREENSHOT_DIR / "sigma-increment13-advanced-desktop.png"),
                    full_page=True,
                )

            page.reload()
            first_row = page.locator(f'li[data-session-id="{sessions[0]["id"]}"]')
            if (
                first_row.locator("button.session-row-disclosure").get_attribute("aria-expanded")
                != "true"
            ):
                first_row.locator("button.session-row-disclosure").click()
            expect(first_row.locator("details.outcome-conclusion")).to_have_attribute("open", "")
            expect(first_row.locator("details.outcome-conclusion")).to_contain_text(
                "The investigation is paused"
            )
            expect(first_row.locator(".advanced-outcome-hint")).to_have_count(0)

            page.set_viewport_size({"width": 375, "height": 812})
            for session in sessions:
                row = page.locator(f'li[data-session-id="{session["id"]}"]')
                if (
                    row.locator("button.session-row-disclosure").get_attribute("aria-expanded")
                    != "true"
                ):
                    row.locator("button.session-row-disclosure").click()
                conclusion = row.locator("details.outcome-conclusion")
                expect(conclusion).to_be_visible()
                assert conclusion.get_attribute("open") is not None
            page.screenshot(
                path=str(SCREENSHOT_DIR / "sigma-increment13-advanced-mobile.png"),
                full_page=True,
            )
            mobile_row = page.locator(f'li[data-session-id="{sessions[0]["id"]}"]')
            mobile_conclusion = mobile_row.locator("details.outcome-conclusion")
            expect(mobile_conclusion.locator(":scope > .sigma-render-toggle")).to_have_count(0)
            expect(
                mobile_row.locator(".outcome-heading-title > .sigma-render-toggle")
            ).to_be_visible()
            expect(mobile_conclusion.locator(".outcome-markdown .katex").first).to_be_visible()
            expect(mobile_conclusion.locator(".outcome-markdown .katex-error")).to_have_count(0)
            for width in (375, 320):
                page.set_viewport_size({"width": width, "height": 812})
                overflow = page.evaluate(
                    "({width: document.documentElement.clientWidth, "
                    "scroll: document.documentElement.scrollWidth})"
                )
                assert overflow["scroll"] <= overflow["width"], overflow
                assert mobile_conclusion.locator(".outcome-markdown .katex").count() >= 8
                mobile_conclusion.screenshot(path=f"/tmp/sigma-conclusion-typeset-{width}.png")
            page.mouse.move(1400, 10)
            # Switch to Simple Outcome and verify the same provenance is above the narrative.
            settings = page.get_by_role("button", name="Project settings", exact=True)
            settings.click()
            dialog = page.get_by_role("dialog", name="Settings")
            dialog.get_by_role("tab", name="Preferences").click()
            detail_setting = dialog.get_by_role("checkbox", name="Show advanced Outcome details")
            expect(detail_setting).to_be_checked()
            detail_setting.uncheck()
            dialog.get_by_role("button", name="Save", exact=True).click()
            expect(dialog).to_be_hidden()
            row = page.locator(f'li[data-session-id="{sessions[0]["id"]}"]')
            expect(row.locator(".outcome-simple")).to_be_visible()
            expect(row.locator(".research-pause-guidance")).to_contain_text(
                "Resume when you are ready for new provider work."
            )
            expect(row.locator(".advanced-outcome-hint")).to_contain_text(
                "Want more detail? Turn on Advanced Outcome to see the full research findings and evidence."
            )
            expect(row.locator(".outcome-simple .katex").first).to_be_visible()
            expect(row.locator(".outcome-simple .outcome-markdown")).to_contain_text(
                "meromorphic continuation"
            )
            expect(row.locator(".outcome-simple .outcome-summary-text")).to_contain_text("…")
            expect(row.locator(".outcome-simple .outcome-markdown .katex").first).to_be_visible()
            expect(row.locator(".outcome-simple .outcome-markdown .katex-error")).to_have_count(0)
            expect(row.locator(".outcome-conclusion-format-note")).to_have_count(0)
            # Simple Outcome is controlled by its heading Markdown button alone.
            # Advanced Conclusion has its own control; simple mode must not duplicate it.
            expect(row.locator(".outcome-simple .sigma-render-toggle")).to_have_count(0)
            expect(row.locator(".outcome-heading-title > .sigma-render-toggle")).to_be_visible()
            expect(
                row.get_by_role("button", name="Format all research sections as Markdown")
            ).to_have_attribute("aria-pressed", "false")
            prelude = row.locator(".outcome-evidence-prelude")
            expect(prelude).to_contain_text("0 reported completed of 0 identified saved executions")
            expect(prelude).to_contain_text(
                "No local Python or Sage computation is recorded for this session."
            )
            expect(prelude).to_contain_text(
                "Computational claims in the agent-authored conclusion are not supported"
            )
            assert prelude.evaluate(
                "element => (element.compareDocumentPosition("
                "element.parentElement.querySelector('.outcome-simple')) & "
                "Node.DOCUMENT_POSITION_FOLLOWING) !== 0"
            ), "Simple Outcome must not put authored prose before the saved ledger"

            for width in (375, 320):
                page.set_viewport_size({"width": width, "height": 812})
                expect(prelude).to_be_visible()
                if width == 375:
                    row.locator(".session-outcome").screenshot(
                        path="/tmp/sigma-advanced-outcome-hint-mobile.png"
                    )
                overflow = page.evaluate(
                    "({width: document.documentElement.clientWidth, "
                    "scroll: document.documentElement.scrollWidth})"
                )
                assert overflow["scroll"] <= overflow["width"], overflow
                page.screenshot(
                    path=str(SCREENSHOT_DIR / f"sigma-increment13-simple-{width}.png"),
                    full_page=True,
                )

            saved_record = json.loads(
                (sessions_path / f"{session['id']}.json").read_text(encoding="utf-8")
            )
            assert saved_record["outcome"]["conclusion"] == session["outcome"]["conclusion"]
            # Adversarial, no-provider record: one saved timeout must never count as success.
            inspected = sessions[0]
            inspected["artifacts"][-1].setdefault("investigator_output", {})["python_execution"] = {
                "id": "offline-timeout",
                "runtime": "python",
                "status": "timeout",
                "source": "print('nothing measured')",
                "stderr": "Timed out before producing a measurement",
            }
            # A metadata-only completed status is not evidence of a recorded
            # measurement. Check the warning alongside a distinct timeout.
            inspected.setdefault("steps", []).append(
                {
                    "id": "missing-output-step",
                    "output": {
                        "python_execution": {
                            "id": "offline-reported-only",
                            "runtime": "python",
                            "status": "completed",
                        }
                    },
                }
            )
            (sessions_path / f"{inspected['id']}.json").write_text(
                json.dumps(inspected, ensure_ascii=False), encoding="utf-8"
            )
            page.reload()
            saved_row = page.locator(f'li[data-session-id="{inspected["id"]}"]')
            expect(saved_row).to_be_visible(timeout=15000)
            disclosure = saved_row.locator("button.session-row-disclosure")
            if disclosure.get_attribute("aria-expanded") != "true":
                disclosure.click()
            prelude = saved_row.locator(".outcome-evidence-prelude")
            expect(prelude).to_contain_text("1 reported completed of 2 identified saved executions")
            expect(prelude).to_contain_text(
                "1 completed-status record(s) do not include saved source and output"
            )
            prelude.locator("summary").click()
            expect(prelude).to_contain_text("offline-timeout")
            expect(prelude).to_contain_text("timeout")
            expect(prelude).to_contain_text("offline-reported-only")
            expect(prelude).to_contain_text("source unavailable, output unavailable")
            expect(saved_row.locator(".outcome-simple")).to_be_visible()
            page.screenshot(
                path=str(SCREENSHOT_DIR / "sigma-increment13-timeout-mobile.png"),
                full_page=True,
            )
            # Closed historical sessions must not construct full hidden
            # provider-input/provenance DOM trees. The real project snapshot
            # can accumulate many megabytes of saved agent input.
            if disclosure.get_attribute("aria-expanded") != "false":
                disclosure.click()
            expect(disclosure).to_have_attribute("aria-expanded", "false")
            expect(saved_row.locator(".outcome-provenance-list")).to_have_count(0)
            disclosure.click()
            expect(saved_row.get_by_role("region", name="Research outcome")).to_be_visible()

            # One malformed historical Outcome must leave the project shell
            # and saved session controls accessible, not blank the app.
            diagnostic = browser.new_page(viewport={"width": 1280, "height": 880})

            def malformed_saved_outcome(route):
                original = route.fetch()
                response = original.json()
                if response.get("sessions"):
                    item = response["sessions"][0]
                    item["outcome"]["solution_review"]["strategy_findings"] = [
                        {
                            "strategy_title": "Malformed saved review",
                            "reasoning_steps": None,
                        }
                    ]
                route.fulfill(
                    status=original.status,
                    content_type="application/json",
                    body=json.dumps(response),
                )

            diagnostic.route("**/api/projects/research-sessions?*", malformed_saved_outcome)
            diagnostic.goto(f"{ui_url}/project?path={quote(str(project_path), safe='')}")
            expect(diagnostic.get_by_role("heading", name="Strategies")).to_be_visible()
            diagnostic_row = diagnostic.locator(f'li[data-session-id="{session["id"]}"]')
            expect(diagnostic_row).to_be_visible()
            diagnostic_disclosure = diagnostic_row.locator("button.session-row-disclosure")
            if diagnostic_disclosure.get_attribute("aria-expanded") != "true":
                diagnostic_disclosure.click()
            expect(
                diagnostic.get_by_role("alert").filter(
                    has_text="Session #"
                )
            ).to_contain_text("could not be displayed")
            expect(diagnostic.get_by_role("heading", name="Strategies")).to_be_visible()
            diagnostic.close()

            assert not starts, "Fixtures must not start provider sessions"
            assert not errors, errors
            browser.close()
    finally:
        for process in (ui, api):
            process.terminate()
        for process in (ui, api):
            try:
                process.wait(timeout=5)
            except subprocess.TimeoutExpired:
                process.kill()
                process.wait(timeout=5)

print(
    "Real Chrome passed: saved plain-text RH Conclusion typeset by KaTeX by default in Simple and Advanced views; source toggle, actionable pause guidance, evidence order and desktop/mobile layouts checked; no provider calls."
)
