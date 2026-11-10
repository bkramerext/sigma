"""Real Chrome Source Material link, attachment, collapse and persistence check."""

from __future__ import annotations

import os
from pathlib import Path
from urllib.parse import quote
from uuid import uuid4

from playwright.sync_api import expect, sync_playwright

ROOT = Path(__file__).resolve().parents[1]
BASE = os.environ.get("SIGMA_BROWSER_BASE_URL", "http://127.0.0.1:5173").rstrip("/")
FIXTURE = os.environ.get("SIGMA_BROWSER_FIXTURE_URL", "http://127.0.0.1:8026").rstrip("/")


def main() -> None:
    with sync_playwright() as playwright:
        browser = playwright.chromium.launch(
            executable_path=os.environ.get(
                "SIGMA_BROWSER_EXECUTABLE",
                "/Applications/Google Chrome.app/Contents/MacOS/Google Chrome",
            ),
            headless=True,
        )
        page = browser.new_page()
        errors: list[str] = []
        page.on("pageerror", lambda error: errors.append(str(error)))

        def proxy(route):
            route.fulfill(
                response=route.fetch(
                    url=route.request.url.replace(BASE, FIXTURE),
                    headers={**route.request.headers, "origin": "http://127.0.0.1:5173"},
                )
            )

        page.route("**/api/**", proxy)
        page.route("**/api/projects/research-presence?*", lambda route: route.fulfill(status=204))
        page.goto(BASE)
        created = page.evaluate(
            """async title => {
              const response = await fetch('/api/projects/create', {
                method: 'POST', headers: {'Content-Type': 'application/json'},
                body: JSON.stringify({title, problem: 'Inspect supplied premises.',
                  investigation_type: 'mathematical'})
              });
              return {status: response.status, body: await response.json()};
            }""",
            "Source Material browser " + uuid4().hex[:8],
        )
        assert created["status"] == 201, created
        path = created["body"]["path"]
        page.goto(BASE + "/project?path=" + quote(path, safe=""))
        project_toggle = page.get_by_role("button", name="Project", exact=True).first
        expect(project_toggle).to_be_visible()
        if project_toggle.get_attribute("aria-expanded") == "false":
            project_toggle.click()
        section = page.locator(".sigma-supplied-evidence")
        heading = section.get_by_role("button", name="Source Material", exact=True)
        expect(heading).to_be_visible()
        assert section.get_by_role("button", name="Add link").get_attribute("title") is None
        section.get_by_role("button", name="Add link").click()
        editor = section.get_by_role("textbox", name="Evidence link")
        editor.fill("https://example.org/source-735")
        editor.press("Tab")
        expect(section.get_by_role("link", name="https://example.org/source-735")).to_be_visible()
        section.locator('input[type="file"]').set_input_files(
            ROOT / "tests/fixtures/sigma-valid-sample-paper.pdf"
        )
        expect(
            section.get_by_role("link", name="Attached: sigma-valid-sample-paper.pdf")
        ).to_be_visible()
        heading.click()
        assert heading.get_attribute("aria-expanded") == "false"
        heading.click()
        assert heading.get_attribute("aria-expanded") == "true"
        page.reload()
        expect(section.get_by_role("link", name="https://example.org/source-735")).to_be_visible()
        expect(
            section.get_by_role("link", name="Attached: sigma-valid-sample-paper.pdf")
        ).to_be_visible()
        section.get_by_role("button", name="Remove https://example.org/source-735").click()
        expect(section.get_by_role("link", name="https://example.org/source-735")).to_have_count(0)
        assert not errors, errors
        browser.close()


if __name__ == "__main__":
    main()
    print("PASS real Chrome Source Material link, PDF, collapse, refresh and removal")
