"""Real-Chrome, no-provider checks for the original-project checkpoint copies.

Set SIGMA_P0_FIXTURE_ROOT to the isolated provider fixture's project root.
This script only reads papers and progress; it never starts generation.
"""

import os
from pathlib import Path
from urllib.parse import quote

from playwright.sync_api import expect, sync_playwright

ui = os.environ.get("SIGMA_P0_UI_ORIGIN", "http://127.0.0.1:5181").rstrip("/")
root = Path(os.environ["SIGMA_P0_FIXTURE_ROOT"])

with sync_playwright() as playwright:
    browser = playwright.chromium.launch(
        executable_path=os.environ.get(
            "SIGMA_BROWSER_EXECUTABLE",
            "/Applications/Google Chrome.app/Contents/MacOS/Google Chrome",
        ),
        headless=True,
    )
    page = browser.new_page(viewport={"width": 1440, "height": 960})

    maximum = str(root / "maximum-regions-by-lines-2.sigma")
    page.goto(ui + "/project?path=" + quote(maximum, safe=""))
    expect(page.get_by_text("6 papers", exact=True)).to_be_visible()
    link = page.get_by_role("link", name="Maximum Regions Formed by Lines v2").last
    result = page.evaluate(
        """async href => { const response = await fetch(href);
        const bytes = new Uint8Array(await response.arrayBuffer());
        return {status: response.status, type: response.headers.get('content-type'),
          size: bytes.length, header: [...bytes.slice(0, 5)]}; }""",
        link.get_attribute("href"),
    )
    assert result["status"] == 200 and "application/pdf" in result["type"], result
    assert result["size"] > 10_000 and result["header"] == [37, 80, 68, 70, 45], result
    page.reload()
    expect(page.get_by_text("6 papers", exact=True)).to_be_visible()

    sovereign = str(root / "sovereign-ai-federation.sigma")
    page.goto(ui + "/project?path=" + quote(sovereign, safe=""))
    expect(page.get_by_text("Generation stopped", exact=True)).to_be_visible()
    progress = page.evaluate(
        """async path => { const response = await fetch('/api/projects/papers/progress?path=' +
        encodeURIComponent(path)); return await response.json(); }""",
        sovereign,
    )
    assert progress["progress"]["status"] == "cancelled", progress
    assert "Retrying section" not in progress["progress"].get("detail", ""), progress
    page.reload()
    expect(page.get_by_text("Generation stopped", exact=True)).to_be_visible()
    browser.close()

print(
    "PASS original-project copies: Chrome PDF fetch, refresh persistence, and terminal retry state"
)
