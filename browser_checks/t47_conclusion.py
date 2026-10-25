"""Real Chrome checks for saved session Conclusions at desktop and phone widths."""

import json
import hashlib
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
    ai_formatted_conclusion = (
        "### Preliminary finding\n\n"
        "For the meromorphic continuation\n\n"
        "$$\n"
        r"\zeta(s)=\frac{s}{s-1}-s\int_1^\infty\{x\}^{-s-1}\,dx"
        "\n$$\n\n"
        "on $\\operatorname{Re}(s)>0$,\n\n"
        "$$\n"
        r"\zeta(\sigma+it)\ne 0,\quad T=|t|\ge 1,\quad "
        r"\sigma\ge 1-\frac{1}{256(4T+9)^4(2T+4)}"
        "\n$$\n\n"
        "This does not prove or disprove the Riemann Hypothesis.\n\n"
        "The investigation is paused; this is not a completed conclusion.\n\n"
        "The Euler-product logarithm and $3+4\\cos\\theta+\\cos(2\\theta)\\ge0$ imply\n\n"
        "$$\n"
        r"\zeta(1+it)^3|\zeta(1+2it)|\ge1"
        "\n$$\n\n"
        "A zero at $\\beta+it$ with $\\beta\\ge1-\\epsilon$ would imply "
        "$|\\zeta(1+it)|\\le2rM(T)$, where $M(T)=4T+9$. "
        "Choosing $\\epsilon=1/[256(4T+9)^4(2T+4)]$ forces the product to be at most $1/2$."
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
    latest_artifact["reasoning_steps"] = session["outcome"]["solution_review"][
        "argument_steps"
    ]
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
            conversion_requests: list[dict] = []
            pending_conclusion_responses: list[tuple[object, dict]] = []
            pending_text_routes: list[object] = []

            def mock_conversion_settings(route):
                route.fulfill(
                    status=200,
                    content_type="application/json",
                    body=json.dumps({"available": True, "binding": "fixture-binding"}),
                )

            def mock_conclusion_conversion(route):
                request = json.loads(route.request.post_data or "{}")
                if request.get("scope") != "research-conclusion":
                    pending_text_routes.append(route)
                    return
                assert request["scope"] == "research-conclusion", request
                assert request["session_id"] == session["id"], request
                assert request["target"] == "markdown", request
                assert request["expected_digest"] == hashlib.sha256(
                    session["outcome"]["conclusion"].encode("utf-8")
                ).hexdigest(), request
                conversion_requests.append(request)
                pending_conclusion_responses.append((route, {
                    "status": 200,
                    "content_type": "application/json",
                    "body": json.dumps(
                        {
                            "body": ai_formatted_conclusion,
                            "warnings": [],
                            "source_digest": request["expected_digest"],
                            "provenance": {
                                "provider": "openai",
                                "model": "fixture-model",
                                "reasoning_effort": "high",
                            },
                        }
                    ),
                }))

            page.route("**/api/projects/proposals/config**", mock_conversion_settings)
            page.route("**/api/projects/text/convert", mock_conclusion_conversion)
            page.goto(f"{ui_url}/project?path={quote(str(project_path), safe='')}")
            project_markdown = page.locator("#project-markdown-slot .sigma-render-toggle")
            expect(project_markdown).to_be_visible()
            project_markdown.click()
            project_status = page.locator("#project-markdown-slot .text-view-format-status")
            expect(project_status).to_be_visible()
            assert project_status.evaluate(
                "element => getComputedStyle(element.parentElement).gap"
            ) == "6px"
            page.locator(".project-pane-title-line").screenshot(
                path="/tmp/sigma-project-markdown-formatting.png"
            )
            page.set_viewport_size({"width": 390, "height": 844})
            assert page.evaluate("document.documentElement.scrollWidth <= innerWidth")
            expect(project_status).to_be_visible()
            page.screenshot(path="/tmp/sigma-project-markdown-formatting-mobile.png")
            page.set_viewport_size({"width": 1440, "height": 1000})
            pending_text_routes.pop(0).fulfill(
                status=503,
                content_type="application/json",
                body='{"error":"Mock provider unavailable"}',
            )
            expect(page.locator(".project-intro .error")).to_contain_text(
                "Mock provider unavailable"
            )
            strategy_markdown = page.locator(".strategy-markdown-slot .sigma-render-toggle").first
            expect(strategy_markdown).to_be_visible()
            strategy_markdown.click()
            strategy_status = page.locator(".strategy-markdown-slot .text-view-format-status").first
            expect(strategy_status).to_be_visible()
            assert strategy_status.evaluate(
                "element => getComputedStyle(element.parentElement).gap"
            ) == "6px"
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
            assert latex_hover["width"] == 34 and latex_hover["height"] == 34, latex_hover
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
            while dismiss_errors.count():
                dismiss_errors.first.click()
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
            detail_setting = dialog.get_by_role(
                "checkbox", name="Show advanced Outcome details"
            )
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
                expect(prelude).to_contain_text("0 reported completed of 0 identified saved executions")
                expect(prelude).to_contain_text("No persisted Python/SageMath execution records")
                assert prelude.evaluate(
                    "element => element.nextElementSibling.classList.contains('outcome-subsections')"
                ), "Saved computation provenance must precede the Advanced Outcome narrative"
                expect(conclusion).to_contain_text("The investigation is paused")
                toggle = outcome.get_by_role("button", name="Format Conclusion with AI")
                toggle.hover()
                toggle_style = toggle.evaluate(
                    "e => ({rect:e.getBoundingClientRect().toJSON(), "
                    "border:getComputedStyle(e).borderTopWidth, "
                    "background:getComputedStyle(e).backgroundColor, "
                    "color:getComputedStyle(e).color, "
                    "icon:e.querySelector('svg').getBoundingClientRect().toJSON()})"
                )
                assert toggle_style["rect"]["width"] == 28, toggle_style
                assert toggle_style["rect"]["height"] == 28, toggle_style
                assert toggle_style["border"] == "0px", toggle_style
                assert toggle_style["background"] == "rgba(0, 0, 0, 0)", toggle_style
                assert toggle_style["color"] == "rgb(170, 180, 186)", toggle_style
                assert toggle_style["icon"]["width"] == 24, toggle_style
                assert toggle_style["icon"]["height"] == 20, toggle_style
                expect(toggle).to_have_attribute("aria-pressed", "false")
                expect(conclusion.locator(".outcome-conclusion-source")).to_contain_text(
                    "ζ(s)=s/(s−1)−s∫_1^∞{x}^{−s−1}"
                )
                toggle.click()
                format_status = outcome.locator(".text-view-format-status")
                expect(format_status).to_be_visible()
                assert format_status.evaluate(
                    "element => getComputedStyle(element.parentElement).gap"
                ) == "6px"
                response_route, response = pending_conclusion_responses.pop(0)
                response_route.fulfill(**response)
                source_toggle = conclusion.locator(".outcome-conclusion-actions .sigma-render-toggle")
                expect(source_toggle).to_have_attribute("aria-pressed", "true", timeout=15000)
                expect(source_toggle).to_have_attribute("aria-label", "Show saved Conclusion")
                assert source_toggle.evaluate("e => getComputedStyle(e).color") == "rgb(241, 197, 141)"
                assert len(conversion_requests) == 1
                finding = conclusion.locator(".outcome-markdown h3").first
                expect(finding).to_be_visible()
                expect(finding).to_have_text("Preliminary finding")
                expect(conclusion.locator(".outcome-markdown .katex").first).to_be_visible()
                assert conclusion.locator(".outcome-markdown .katex-display").count() == 3
                assert conclusion.locator(".outcome-markdown .katex").count() >= 8
                expect(conclusion.locator(".outcome-markdown .katex-error")).to_have_count(0)
                expect(conclusion.locator(".outcome-markdown img")).to_have_count(0)
                expect(conclusion.locator(".outcome-markdown")).not_to_contain_text(
                    "### Preliminary finding"
                )
                expect(conclusion.locator(".outcome-markdown .katex-display").first).to_be_visible()
                expect(conclusion.locator(".outcome-markdown")).to_contain_text(
                    "The investigation is paused; this is not a completed conclusion."
                )
                conclusion.screenshot(path="/tmp/sigma-conclusion-ai-desktop.png")
                source_toggle.click()
                expect(conclusion.locator(".outcome-conclusion-source")).to_be_visible()
                expect(source_toggle).to_have_attribute("aria-pressed", "false")
                assert source_toggle.evaluate("e => getComputedStyle(e).color") == "rgb(170, 180, 186)", (
                    "Plain-text state must remain visibly gray even while the pointer hovers over the toggle"
                )
                expect(conclusion.locator(".outcome-conclusion-source")).to_contain_text("ζ(s)=s/(s−1)")
                expect(conclusion.locator(".outcome-conclusion-source")).not_to_contain_text("$$")
                source_toggle.click()
                expect(source_toggle).to_have_attribute("aria-pressed", "true")
                assert source_toggle.evaluate("e => getComputedStyle(e).color") == "rgb(241, 197, 141)"
                assert len(conversion_requests) == 1, "Toggling to saved AI Markdown must not call the provider again"
                expect(conclusion.locator(".outcome-markdown h3").first).to_have_text(
                    "Preliminary finding"
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
            mobile_toggle = mobile_conclusion.locator(
                ".outcome-conclusion-actions .sigma-render-toggle"
            )
            mobile_toggle.click()
            mobile_status = mobile_conclusion.locator(".text-view-format-status")
            expect(mobile_status).to_be_visible()
            mobile_route, mobile_response = pending_conclusion_responses.pop(0)
            mobile_route.fulfill(**mobile_response)
            expect(mobile_toggle).to_have_attribute("aria-pressed", "true")
            expect(mobile_conclusion.locator(".outcome-markdown .katex-display")).to_have_count(3)
            for width in (375, 320):
                page.set_viewport_size({"width": width, "height": 812})
                overflow = page.evaluate(
                    "({width: document.documentElement.clientWidth, "
                    "scroll: document.documentElement.scrollWidth})"
                )
                assert overflow["scroll"] <= overflow["width"], overflow
                assert mobile_conclusion.locator(".outcome-markdown .katex-display").count() == 3
                mobile_conclusion.screenshot(path=f"/tmp/sigma-conclusion-ai-{width}.png")
            page.mouse.move(1400, 10)
            # Switch to Simple Outcome and verify the same provenance is above the narrative.
            settings = page.get_by_role("button", name="Project settings", exact=True)
            settings.click()
            dialog = page.get_by_role("dialog", name="Settings")
            dialog.get_by_role("tab", name="Preferences").click()
            detail_setting = dialog.get_by_role(
                "checkbox", name="Show advanced Outcome details"
            )
            expect(detail_setting).to_be_checked()
            detail_setting.uncheck()
            dialog.get_by_role("button", name="Save", exact=True).click()
            expect(dialog).to_be_hidden()
            row = page.locator(f'li[data-session-id="{sessions[0]["id"]}"]')
            expect(row.locator(".outcome-simple")).to_be_visible()
            expect(row.locator(".advanced-outcome-hint")).to_contain_text(
                "Want more detail? Turn on Advanced Outcome to see the full research findings and evidence."
            )
            expect(row.locator(".outcome-simple .katex").first).to_be_visible()
            expect(row.get_by_role("button", name="Show plain outcome text")).to_have_attribute(
                "aria-pressed", "true"
            )
            prelude = row.locator(".outcome-evidence-prelude")
            expect(prelude).to_contain_text("0 reported completed of 0 identified saved executions")
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

            # Adversarial, no-provider record: one saved timeout must never count as success.
            inspected = sessions[0]
            inspected["artifacts"][-1].setdefault("investigator_output", {})[
                "python_execution"
            ] = {
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

print("Real Chrome passed: AI-formatted historical Conclusion, gray/copper toggle, raw/rendered modes and KaTeX at desktop/mobile widths; Outcome provenance, zero and timed-out executions; mocked conversion only.")
