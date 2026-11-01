"""Real-Chrome Outcome modes using copies of the saved local research projects."""

import json
import os
from pathlib import Path
from urllib.parse import urlencode

from playwright.sync_api import expect, sync_playwright

UI_ORIGIN = os.environ.get("SIGMA_OUTCOME_UI_ORIGIN", "http://127.0.0.1:5174").rstrip("/")
PROJECT_ROOT = Path(os.environ["SIGMA_OUTCOME_PROJECTS_ROOT"]).resolve()
API_ORIGIN = os.environ.get("SIGMA_OUTCOME_API_ORIGIN", "http://127.0.0.1:8178").rstrip("/")
BROWSER = os.environ.get(
    "SIGMA_BROWSER_EXECUTABLE",
    "/Applications/Google Chrome.app/Contents/MacOS/Google Chrome",
)
PROJECTS = (
    (
        "Nonconsecutive Subset Sums Modulo 3 v8",
        PROJECT_ROOT / "nonconsecutive-subset-sums-8.sigma",
        5,
    ),
    ("Maximum Regions Formed by Lines v3", PROJECT_ROOT / "maximum-regions-by-lines-3.sigma", 1),
)


def open_project(page, project_path: Path):
    page.goto(f"{UI_ORIGIN}/project?{urlencode({'path': str(project_path)})}")
    rows = page.locator(".sessions-pane li[data-session-id]")
    expect(rows.first).to_be_visible(timeout=15000)
    return rows


def expand(row):
    disclosure = row.locator(".session-row-disclosure")
    if disclosure.get_attribute("aria-expanded") != "true":
        disclosure.click()
    expect(row.locator(".session-outcome")).to_be_visible()


with sync_playwright() as playwright:
    browser = playwright.chromium.launch(executable_path=BROWSER, headless=True)
    page = browser.new_page(viewport={"width": 1440, "height": 1000})
    page.set_default_timeout(10000)
    errors: list[str] = []
    page.on("pageerror", lambda error: errors.append(str(error)))

    def forward(route):
        response = route.fetch(
            url=route.request.url.replace(UI_ORIGIN, API_ORIGIN),
            headers={**route.request.headers, "origin": "http://127.0.0.1:5173"},
        )
        route.fulfill(response=response)

    page.route("**/api/**", forward)
    observations = []

    for title, project_path, expected_sessions in PROJECTS:
        assert project_path.is_dir(), project_path
        rows = open_project(page, project_path)
        expect(rows).to_have_count(expected_sessions)
        row = rows.first
        for index in range(expected_sessions):
            current_row = rows.nth(index)
            expand(current_row)
            outcome = current_row.locator(".session-outcome")
            simple = outcome.locator(".outcome-simple")
            expect(simple).to_be_visible()
            expect(outcome.locator(".outcome-subsection")).to_have_count(0)
            expect(simple.locator(".outcome-summary-kicker")).to_contain_text(
                "Historical session summary"
            )
            expect(simple).to_contain_text("Verification:")
            expect(simple).to_contain_text("Supporting evidence:")
            expect(simple).not_to_contain_text("No Conclusion was saved")
        simple = row.locator(".outcome-simple")
        summary_text = simple.inner_text()

        if "Nonconsecutive" in title:
            expect(simple).to_contain_text("remains open")
            expect(simple).to_contain_text("Qualifications and unresolved questions")
            expect(simple).to_contain_text("No general recurrence or asymptotic proof")
            assert "five-session" not in summary_text.lower()

            settings = page.get_by_role("button", name="Project settings", exact=True)
            settings.click()
            dialog = page.get_by_role("dialog", name="Settings")
            preferences = dialog.get_by_role("tab", name="Preferences")
            preferences.click()
            checkbox = dialog.get_by_role("checkbox", name="Show advanced Outcome details")
            expect(checkbox).not_to_be_checked()
            checkbox.check()
            save = dialog.get_by_role("button", name="Save", exact=True)
            expect(save).to_be_enabled(timeout=10000)
            save.click()
            expect(dialog).to_be_hidden()
            expect(row.locator(".outcome-subsections")).to_be_visible()
            sections = row.locator(".outcome-subsection > summary").all_text_contents()
            labels = [label.strip() for label in sections]
            assert labels[:4] == [
                "Conclusion",
                "Reasoning / proof",
                "Citations, evidence & obligations",
                "Metrics",
            ], labels
            conclusion = row.locator(".outcome-conclusion")
            expect(conclusion).to_have_attribute("open", "")
            expect(conclusion).to_contain_text("Historical session summary")
            expect(conclusion).to_contain_text(summary_text.splitlines()[1])

            reasoning = row.locator(".outcome-reasoning-subsection")
            reasoning.locator(":scope > summary").click()
            reasoning_markdown = reasoning.get_by_role(
                "button", name="Format Reasoning / proof as Markdown"
            )
            expect(reasoning_markdown).to_be_visible()
            reasoning_markdown.click()
            expect(
                reasoning.locator(".outcome-markdown").get_by_role(
                    "heading", name="Reasoning / proof", level=1
                )
            ).to_be_visible()
            expect(
                reasoning.get_by_role("button", name="Show saved Reasoning / proof text")
            ).to_have_attribute("aria-pressed", "true")
            reasoning.get_by_role("button", name="Show saved Reasoning / proof text").click()

            evidence = row.locator(".outcome-evidence-subsection")
            evidence.locator(":scope > summary").click()
            artifact = evidence.locator(".research-artifacts > ol > li > details").first
            artifact.locator(":scope > summary").click()
            execution = artifact.locator(".research-execution-record")
            execution.locator(":scope > summary").click()
            source_output = execution.locator("pre")
            expect(source_output).to_contain_text('"source"')
            expect(source_output).to_contain_text('"stdout"')

            for width, height in ((390, 844), (320, 700)):
                page.set_viewport_size({"width": width, "height": height})
                dims = page.evaluate(
                    "({width: innerWidth, scrollWidth: document.documentElement.scrollWidth, "
                    "bodyWidth: document.body.scrollWidth})"
                )
                assert dims["scrollWidth"] <= width and dims["bodyWidth"] <= width, dims
                expect(row.locator(".outcome-conclusion")).to_be_visible()
                expect(row.locator(".outcome-conclusion-content")).to_contain_text(
                    "Historical session summary"
                )
                page.screenshot(path=f"/tmp/sigma-outcome-advanced-{width}.png", full_page=True)
            page.set_viewport_size({"width": 1440, "height": 1000})

            # Reload proves persistence. Then ensure the preference is scoped to this project.
            rows = open_project(page, project_path)
            row = rows.first
            expand(row)
            expect(row.locator(".outcome-conclusion")).to_be_visible()
            other_rows = open_project(page, PROJECTS[1][1])
            expand(other_rows.first)
            expect(other_rows.first.locator(".outcome-simple")).to_be_visible()
            expect(other_rows.first.locator(".outcome-subsection")).to_have_count(0)
            settings.click()
            dialog = page.get_by_role("dialog", name="Settings")
            dialog.get_by_role("tab", name="Preferences").click()
            expect(
                dialog.get_by_role("checkbox", name="Show advanced Outcome details")
            ).not_to_be_checked()
            dialog.get_by_role("button", name="Cancel", exact=True).click()

        else:
            expect(simple).to_contain_text("For every integer n")
            expect(simple).to_contain_text("Convincing but unverified")
            settings = page.get_by_role("button", name="Project settings", exact=True)
            settings.click()
            dialog = page.get_by_role("dialog", name="Settings")
            main_tab = dialog.get_by_role("tab", name="Research")
            expect(main_tab).to_have_attribute("aria-selected", "true")
            expect(dialog.get_by_label("Model", exact=True)).to_be_visible()
            controls = dialog.locator(".settings-model-row > div")
            desktop_positions = [item.bounding_box() for item in controls.all()]
            assert desktop_positions[1]["x"] > desktop_positions[0]["x"]
            assert desktop_positions[1]["y"] == desktop_positions[0]["y"]
            model_value = dialog.locator("#project-model").input_value()
            for width, height in ((390, 844), (320, 700)):
                page.set_viewport_size({"width": width, "height": height})
                mobile_positions = [item.bounding_box() for item in controls.all()]
                assert (
                    mobile_positions[1]["y"]
                    >= mobile_positions[0]["y"] + mobile_positions[0]["height"] - 1
                )
                assert dialog.locator("#project-model").input_value() == model_value
                dims = page.evaluate(
                    "({width: innerWidth, scrollWidth: document.documentElement.scrollWidth, "
                    "bodyWidth: document.body.scrollWidth})"
                )
                assert dims["scrollWidth"] <= width and dims["bodyWidth"] <= width, dims
                page.screenshot(path=f"/tmp/sigma-settings-model-{width}.png", full_page=True)
            page.set_viewport_size({"width": 1440, "height": 1000})
            dialog.get_by_role("button", name="Cancel", exact=True).click()

        page.set_viewport_size({"width": 1440, "height": 1000})
        page.screenshot(path=f"/tmp/sigma-outcome-{len(observations)}-desktop.png", full_page=True)
        observations.append({"project": title, "summary": summary_text[:240]})

    assert not errors, errors
    print(json.dumps({"projects": observations, "page_errors": errors}, indent=2))
    browser.close()
