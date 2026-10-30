"""Real-Chrome paper progress, reconnect, retry and PDF check using local fixtures."""

import os
import re
from urllib.parse import quote

from playwright.sync_api import expect, sync_playwright

UI_ORIGIN = os.environ.get("SIGMA_T328_UI_ORIGIN", "http://127.0.0.1:5173").rstrip("/")

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

    created = page.evaluate(
        """async () => {
          const body = {title: `T328 live paper progress ${Date.now()}`,
            problem: 'Prepare an evidence-bound research note from this saved question.',
            investigation_type: 'mathematical', difficulty: 'hard'};
          const response = await fetch('/api/projects/create', {method:'POST',
            headers:{'Content-Type':'application/json'}, body:JSON.stringify(body)});
          return {status:response.status, body:await response.json()};
        }"""
    )
    assert created["status"] == 201, created
    path = created["body"]["path"]
    page.goto(UI_ORIGIN + "/project?path=" + quote(path, safe=""))
    page.get_by_role("button", name="LaTeX research paper", exact=True).click()
    dialog = page.get_by_role("dialog", name="Academic paper using LaTeX")
    generate = dialog.get_by_role("button", name="Generate", exact=True)
    expect(generate).to_be_enabled(timeout=20000)
    expect(generate).to_have_css("text-decoration-line", "underline")
    expect(dialog.get_by_role("button", name="Close", exact=True)).to_have_css(
        "text-decoration-line", "underline"
    )
    generate.click()
    status = dialog.locator(".ai-paper-progress")
    expect(status).to_contain_text("Writing the paper", timeout=10000)
    expect(dialog.get_by_role("button", name="Generate", exact=True)).to_have_count(0)
    expect(dialog.get_by_role("button", name="Cancel", exact=True)).to_have_css(
        "text-decoration-line", "underline"
    )
    expect(status).to_contain_text(re.compile(r"· \d+s"))
    page.screenshot(path="/tmp/sigma-issue328-short-progress.png", full_page=True)
    dialog.get_by_role("button", name="Cancel", exact=True).click()
    expect(status).to_contain_text("Generation cancelled", timeout=10000)
    expect(status).to_contain_text("Writing the paper")
    expect(dialog).to_contain_text("last writing attempt did not save a draft")
    dialog.get_by_role("button", name="Start over", exact=True).click()
    expect(dialog.locator(".ai-paper-status:not(.ai-paper-progress)")).to_contain_text(
        "Unfinished paper work cleared", timeout=10000
    )
    generate = dialog.get_by_role("button", name="Generate", exact=True)
    expect(generate).to_be_enabled(timeout=10000)
    generate.click()
    expect(status).to_contain_text("Writing the paper", timeout=10000)
    card = dialog.locator(".saved-paper-card").first
    expect(card).to_be_visible(timeout=60000)
    expect(dialog.get_by_role("status")).to_contain_text("Paper saved in Saved versions.")
    expect(card.get_by_role("link", name="Download PDF")).to_be_visible()

    page.goto(UI_ORIGIN + "/")
    created = page.evaluate(
        """async () => {
          const body = {title: `T328 long progress recovery ${Date.now()}`,
            problem: 'Review the saved observations and preserve uncertainty. '.repeat(200),
            investigation_type: 'mathematical', difficulty: 'hard'};
          const response = await fetch('/api/projects/create', {method:'POST',
            headers:{'Content-Type':'application/json'}, body:JSON.stringify(body)});
          if (!response.ok) return {status:response.status, body:await response.json()};
          const project = await response.json();
          for (let index = 1; index <= 6; index++) {
            const strategy = await fetch('/api/projects/strategies', {method:'POST',
              headers:{'Content-Type':'application/json'}, body:JSON.stringify({
                path:project.path, title:`Long evidence strategy ${index}`,
                approach:'Compare the complete observation set, limitations, and next tests. '.repeat(280)})});
            if (!strategy.ok) return {status:strategy.status, body:await strategy.json()};
          }
          return {status:response.status, body:project};
        }"""
    )
    assert created["status"] == 201, created
    long_path = created["body"]["path"]
    preflight = page.evaluate(
        """async path => {
          const query = new URLSearchParams({path, long_form:'false'});
          const response = await fetch('/api/projects/papers/preflight?' + query);
          return {status:response.status, body:await response.json()};
        }""",
        long_path,
    )
    assert preflight["status"] == 200 and preflight["body"]["long_form"], preflight
    page.goto(UI_ORIGIN + "/project?path=" + quote(long_path, safe=""))
    page.get_by_role("button", name="LaTeX research paper", exact=True).click()
    dialog = page.get_by_role("dialog", name="Academic paper using LaTeX")
    generate = dialog.get_by_role("button", name="Generate", exact=True)
    expect(generate).to_be_enabled(timeout=20000)
    generate.click()
    progress = dialog.locator(".ai-paper-progress")
    expect(progress).to_contain_text("Planning the paper", timeout=20000)
    page.screenshot(path="/tmp/sigma-issue328-long-progress.png", full_page=True)

    # Closing the original tab drops its SSE connection. A fresh tab reads the
    # durable checkpoint and recovers the active operation independently.
    page.close()
    page = context.new_page()
    page.on("pageerror", lambda error: errors.append(str(error)))
    page.goto(UI_ORIGIN + "/project?path=" + quote(long_path, safe=""))
    # An active durable checkpoint should open the recovery dialog automatically.
    dialog = page.get_by_role("dialog", name="Academic paper using LaTeX")
    progress = dialog.locator(".ai-paper-progress")
    expect(progress).to_be_visible(timeout=10000)
    # The server owns generation independently of the browser stream. Reconnect
    # must recover the live operation, not mark it cancelled or replay it.
    expect(progress).to_contain_text("Generating paper", timeout=10000)
    expect(progress).to_contain_text(re.compile(r"· \d+s"))
    page.screenshot(path="/tmp/sigma-issue328-reconnected.png", full_page=True)

    card = dialog.locator(".saved-paper-card").first
    expect(card).to_be_visible(timeout=60000)
    expect(card.get_by_role("link", name="Download PDF")).to_be_visible()
    page.screenshot(path="/tmp/sigma-issue328-complete.png", full_page=True)
    assert not errors, errors
    context.close()
    browser.close()

print(
    "PASS T328 real Chrome: one-shot progress/cancel/retry, active long-form progress after reload, and detached completion with a saved PDF; provider calls were served by the local deterministic fixture."
)
