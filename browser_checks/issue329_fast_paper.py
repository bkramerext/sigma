"""Mock-provider browser acceptance for fast paper progress and recovery."""

import os
from urllib.parse import quote

from playwright.sync_api import expect, sync_playwright

UI_ORIGIN = os.environ.get("SIGMA_T329_UI_ORIGIN", "http://127.0.0.1:5182").rstrip("/")
LONG_TEXT = "Compare saved research evidence, preserve uncertainty, and report limitations. " * 210


with sync_playwright() as playwright:
    browser = playwright.chromium.launch(
        executable_path=os.environ.get(
            "SIGMA_BROWSER_EXECUTABLE",
            "/Applications/Google Chrome.app/Contents/MacOS/Google Chrome",
        ),
        headless=True,
    )
    context = browser.new_context(viewport={"width": 1440, "height": 960})
    page = context.new_page()
    errors: list[str] = []
    page.on("pageerror", lambda error: errors.append(str(error)))
    page.goto(UI_ORIGIN + "/")

    def create_long_project(label: str) -> str:
        result = page.evaluate(
            """async ({label, longText}) => {
              const response = await fetch('/api/projects/create', {method:'POST',
                headers:{'Content-Type':'application/json'}, body:JSON.stringify({
                  title:`${label} ${Date.now()}`,
                  problem:`Investigate the recorded evidence and its unresolved limits. ${longText}`,
                  investigation_type:'mathematical', difficulty:'hard'} )});
              if (!response.ok) return {status:response.status, body:await response.json()};
              const project = await response.json();
              for (let index = 1; index <= 7; index++) {
                const strategy = await fetch('/api/projects/strategies', {method:'POST',
                  headers:{'Content-Type':'application/json'}, body:JSON.stringify({
                    path:project.path, title:`${label} evidence strategy ${index}`,
                    approach:longText})});
                if (!strategy.ok) return {status:strategy.status, body:await strategy.json()};
              }
              return {status:response.status, body:project};
            }""",
            {"label": label, "longText": LONG_TEXT},
        )
        assert result["status"] == 201, result
        return result["body"]["path"]

    def configure_failure(schema_name: str, mode: str, count: int = 1) -> None:
        result = page.evaluate(
            """async body => {
              const response = await fetch('/api/__fixture/paper-failure', {method:'POST',
                headers:{'Content-Type':'application/json'}, body:JSON.stringify(body)});
              return {status:response.status, body:await response.json()};
            }""",
            {"schema_name": schema_name, "mode": mode, "count": count},
        )
        assert result["status"] == 200, result

    def open_paper(path: str):
        page.goto(UI_ORIGIN + "/project?path=" + quote(path, safe=""))
        page.get_by_role("button", name="LaTeX research paper", exact=True).click()
        dialog = page.get_by_role("dialog", name="Academic paper using LaTeX")
        expect(dialog.get_by_role("button", name="Generate", exact=True)).to_be_enabled(
            timeout=20_000
        )
        return dialog

    # Observe the regular fast path while the mock provider deliberately holds
    # each remote stage open long enough for the UI to display it.
    progress_path = create_long_project("T329 granular fast progress")
    dialog = open_paper(progress_path)
    dialog.get_by_role("button", name="Generate", exact=True).click()
    progress = dialog.locator(".ai-paper-progress")
    expect(progress).to_contain_text("Planning the paper", timeout=30_000)
    assert "Planning the paper" in progress.inner_text()
    expect(progress).to_contain_text("Writing sections", timeout=30_000)
    expect(progress).to_contain_text("Compiling PDF", timeout=60_000)
    progress_card = dialog.locator(".saved-paper-card").first
    expect(progress_card).to_be_visible(timeout=60_000)
    expect(progress_card.get_by_role("link", name="Download PDF")).to_be_visible()

    # A connection failure before dispatch must produce a truthful retry
    # status, then continue to completion without a billing fallback.
    retry_path = create_long_project("T329 safe connection retry")
    configure_failure("sigma_long_paper_plan", "pre_dispatch")
    dialog = open_paper(retry_path)
    dialog.get_by_role("button", name="Generate", exact=True).click()
    progress = dialog.locator(".ai-paper-progress")
    expect(progress).to_contain_text("Retrying provider connection (1 of 3)", timeout=20_000)
    expect(progress).to_contain_text("Writing sections", timeout=30_000)
    retry_card = dialog.locator(".saved-paper-card").first
    expect(retry_card).to_be_visible(timeout=60_000)
    expect(retry_card.get_by_role("link", name="Download PDF")).to_be_visible()

    # An explicit provider failure after dispatch must leave a responsive
    # compatible checkpoint with Continue. Check this at a narrow viewport.
    continue_path = create_long_project("T329 compatible continuation")
    configure_failure("sigma_long_paper_plan", "provider_error")
    page.set_viewport_size({"width": 390, "height": 844})
    dialog = open_paper(continue_path)
    dialog.get_by_role("button", name="Generate", exact=True).click()
    expect(dialog.get_by_role("alert")).to_contain_text(
        "Deterministic fixture provider returned HTTP 500", timeout=30_000
    )
    expect(dialog.get_by_role("button", name="Retry paper planning", exact=True)).to_be_enabled(
        timeout=10_000
    )
    expect(dialog.locator(".ai-paper-progress")).to_contain_text(
        "Total active time across attempts"
    )
    expect(dialog.get_by_role("button", name="Start over", exact=True)).to_be_enabled()
    expect(dialog).to_contain_text("Retry makes another AI request")
    assert page.evaluate("document.documentElement.scrollWidth <= window.innerWidth")
    dialog.get_by_role("button", name="Retry paper planning", exact=True).click()
    expect(dialog.locator(".saved-paper-card").first).to_be_visible(timeout=60_000)
    expect(
        dialog.locator(".saved-paper-card").first.get_by_role("link", name="Download PDF")
    ).to_be_visible()

    # A failed plan must also provide a no-AI Start over path, independent of
    # whether a retry might repeat the failure. Reset does not publish a paper
    # or dispatch another provider request.
    restart_path = create_long_project("T329 no-AI start over")
    configure_failure("sigma_long_paper_plan", "provider_error")
    page.set_viewport_size({"width": 1440, "height": 960})
    dialog = open_paper(restart_path)
    dialog.get_by_role("button", name="Generate", exact=True).click()
    expect(dialog.get_by_role("alert")).to_contain_text(
        "Deterministic fixture provider returned HTTP 500", timeout=30_000
    )
    expect(dialog.get_by_role("button", name="Retry paper planning", exact=True)).to_be_enabled()
    dialog.get_by_role("button", name="Start over", exact=True).click()
    expect(dialog.get_by_role("button", name="Keep unfinished work", exact=True)).to_be_enabled()
    dialog.get_by_role("button", name="Keep unfinished work", exact=True).click()
    expect(dialog.get_by_role("button", name="Retry paper planning", exact=True)).to_be_enabled()
    dialog.get_by_role("button", name="Start over", exact=True).click()
    dialog.get_by_role("button", name="Confirm Start over", exact=True).click()
    expect(dialog.get_by_role("button", name="Generate", exact=True)).to_be_enabled(timeout=20_000)
    expect(dialog.locator(".saved-paper-card")).to_have_count(0)
    expect(dialog).to_contain_text("No generation has started")

    # A changed source snapshot invalidates Continue. The dialog must identify
    # the mismatch and offer a deliberate Start over, without auto-dispatching.
    incompatible_path = create_long_project("T329 incompatible restart")
    configure_failure("sigma_long_paper_plan", "provider_error")
    page.set_viewport_size({"width": 1440, "height": 960})
    dialog = open_paper(incompatible_path)
    dialog.get_by_role("button", name="Generate", exact=True).click()
    expect(dialog.get_by_role("alert")).to_contain_text(
        "Deterministic fixture provider returned HTTP 500", timeout=30_000
    )
    changed = page.evaluate(
        """async path => {
          const openedResponse = await fetch('/api/projects/open', {method:'POST',
            headers:{'Content-Type':'application/json'}, body:JSON.stringify({path})});
          const opened = await openedResponse.json();
          if (!openedResponse.ok) return {status:openedResponse.status, body:opened};
          const project = opened.project;
          const settings = {title:project.title, problem:project.problem + '\\nFresh post-run evidence.',
            investigation_type:project.investigation_type, ai_model:project.ai_model,
            reasoning_effort:project.reasoning_effort, difficulty:project.difficulty,
            show_advanced_outcome_details:project.show_advanced_outcome_details};
          const response = await fetch('/api/projects/update', {method:'POST',
            headers:{'Content-Type':'application/json'}, body:JSON.stringify({path, ...settings,
              expected:{title:project.title, problem:project.problem,
                investigation_type:project.investigation_type, ai_model:project.ai_model,
                reasoning_effort:project.reasoning_effort, difficulty:project.difficulty,
                show_advanced_outcome_details:project.show_advanced_outcome_details}})});
          return {status:response.status, body:await response.json()};
        }""",
        incompatible_path,
    )
    assert changed["status"] == 200, changed
    page.reload()
    page.get_by_role("button", name="LaTeX research paper", exact=True).click()
    dialog = page.get_by_role("dialog", name="Academic paper using LaTeX")
    expect(dialog.locator(".ai-paper-restart-notice")).to_contain_text(
        "research or AI settings changed", timeout=20_000
    )
    expect(
        dialog.get_by_role("button", name="Clear outdated paper work", exact=True)
    ).to_be_enabled()
    expect(dialog.get_by_role("button", name="Generate", exact=True)).to_be_disabled()
    dialog.get_by_role("button", name="Clear outdated paper work", exact=True).click()
    expect(dialog.locator(".ai-paper-status:not(.ai-paper-progress)")).to_contain_text(
        "Unfinished paper work cleared. No generation has started", timeout=20_000
    )
    expect(dialog.get_by_role("button", name="Generate", exact=True)).to_be_enabled()
    assert not errors, errors

    page.screenshot(path="/tmp/sigma-329-incompatible-restart.png", full_page=True)
    context.close()
    browser.close()

print(
    "PASS T329 Chrome with deterministic provider fixtures: retry, granular long-form progress, "
    "small-screen failure/Continue, incompatible snapshot restart and local PDF completion."
)
