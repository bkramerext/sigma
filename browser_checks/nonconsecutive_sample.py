"""Real-Chrome review of the enriched Nonconsecutive Subset Sums sample."""

import json
import os

from playwright.sync_api import expect, sync_playwright

UI_ORIGIN = os.environ.get("SIGMA_SAMPLE_UI_ORIGIN", "http://127.0.0.1:5173").rstrip("/")
API_ORIGIN = os.environ.get("SIGMA_SAMPLE_API_ORIGIN", "http://127.0.0.1:8000").rstrip("/")
STRATEGIES = (
    "Periodic transfer matrix",
    "Roots-of-unity weighted Fibonacci polynomials",
    "Gap removal and Gaussian binomial sums",
)

with sync_playwright() as playwright:
    browser = playwright.chromium.launch(
        executable_path=os.environ.get(
            "SIGMA_BROWSER_EXECUTABLE",
            "/Applications/Google Chrome.app/Contents/MacOS/Google Chrome",
        ),
        headless=True,
    )
    page = browser.new_page(viewport={"width": 1440, "height": 1000})
    page.set_default_timeout(10000)
    errors: list[str] = []
    page.on("pageerror", lambda error: errors.append(str(error)))

    def forward(route):
        route.fulfill(
            response=route.fetch(
                url=route.request.url.replace(UI_ORIGIN, API_ORIGIN),
                headers={**route.request.headers, "origin": "http://127.0.0.1:5173"},
            )
        )

    page.route("**/api/**", forward)
    page.goto(UI_ORIGIN + "/")
    panel = page.get_by_role("tabpanel", name="Samples")
    sample = panel.get_by_role(
        "button", name="Open Nonconsecutive Subset Sums Modulo 3", exact=True
    )
    sample.click()
    page.wait_for_url("**/project?*")

    # This check inspects all saved reasoning and execution artifacts, so opt into
    # the project-level advanced Outcome presentation through Project Settings.
    page.get_by_role("button", name="Project settings", exact=True).click()
    settings = page.get_by_role("dialog", name="Settings")
    settings.get_by_role("tab", name="Preferences").click()
    advanced = settings.get_by_role("checkbox", name="Show advanced Outcome details")
    expect(advanced).not_to_be_checked()
    advanced.check()
    settings.get_by_role("button", name="Save", exact=True).click()
    expect(settings).to_be_hidden()

    research = page.locator(".sessions-pane")
    rows = research.locator("li[data-session-id]")
    expect(rows).to_have_count(5)
    expect(research).to_contain_text("5 sessions, 0 running")
    results = []
    for index in range(5):
        row = rows.nth(index)
        disclosure = row.locator(".session-row-disclosure")
        if disclosure.get_attribute("aria-expanded") != "true":
            disclosure.click()
        expect(row.locator(".session-row-content")).to_be_visible()
        expect(row.locator(".session-outcome-inline")).to_be_visible()
        summary = row.locator(".session-row-content").inner_text()
        if index == 0:
            expect(row.locator(".session-outcome-inline")).to_contain_text(
                "Mixed · partial progress, unresolved"
            )
            assert "Negative · counterexample reported" not in summary
        for subsection in row.locator(".outcome-subsection").all():
            label = subsection.locator(":scope > summary").inner_text().strip()
            if label in ("Status", "Strategy Assessments", "Metrics", "Session history and provenance", "Conclusion", "Reasoning / proof", "Citations, evidence & obligations"):
                if subsection.get_attribute("open") is None:
                    subsection.locator(":scope > summary").click()
                assert subsection.get_attribute("open") is not None, (index + 1, label)
                if index == 0 and label == "Metrics":
                    assert "Negative · counterexample reported" not in subsection.inner_text()
        evidence = row.locator(".outcome-evidence-subsection")
        if evidence.count():
            if evidence.get_attribute("open") is None:
                evidence.locator(":scope > summary").click()
            expect(evidence).to_be_visible()
            if index in (0, 4):
                artifact = evidence.locator(".research-artifacts > ol > li > details")
                expect(artifact).to_have_count(1)
                artifact.locator(":scope > summary").click()
                artifact_text = artifact.inner_text()
                if index == 0:
                    assert "deterministic" in artifact_text.lower()
                    assert "a_(n+3)=a_(n+2)+a_n" in artifact_text
                    assert "a_5=5" in artifact_text
                    assert "a_4+a_2=3+1=4" in artifact_text
                else:
                    assert "k(k+1)/2" in artifact_text
                    assert "earlier explanation" in artifact_text
        expect(row).to_contain_text("Python runs by status")
        expect(row).to_contain_text("completed")
        results.append(
            {
                "session": row.locator(".session-row-title").inner_text().strip(),
                "outcome": row.locator(".session-outcome-inline").inner_text().strip(),
            }
        )

    page.screenshot(path="/tmp/sigma-nonconsecutive-desktop.png", full_page=True)
    path = page.evaluate("new URL(location.href).searchParams.get('path')")
    report = page.evaluate(
        "async path => await (await fetch('/api/projects/export/report?' + "
        "new URLSearchParams({path, format:'txt'}))).text()",
        path,
    )
    for strategy in STRATEGIES:
        assert strategy in report, strategy
    assert "Deterministic fixture result (not live-model output)" in report
    assert "Open proof obligations" in report
    assert "Negative · counterexample reported" not in report
    assert len(report) > 30000, len(report)

    mobile_dimensions = []
    for width, height in ((390, 844), (320, 700)):
        page.set_viewport_size({"width": width, "height": height})
        page.wait_for_timeout(250)
        dimensions = page.evaluate(
            "({width: innerWidth, scrollWidth: document.documentElement.scrollWidth, "
            "bodyWidth: document.body.scrollWidth})"
        )
        assert (
            dimensions["scrollWidth"] <= dimensions["width"]
            and dimensions["bodyWidth"] <= dimensions["width"]
        ), dimensions
        mobile_dimensions.append(dimensions)
    page.screenshot(path="/tmp/sigma-nonconsecutive-mobile.png", full_page=True)
    assert not errors, errors
    print(
        json.dumps(
            {
                "sessions": results,
                "report_chars": len(report),
                "mobile_dimensions": mobile_dimensions,
                "screenshots": [
                    "/tmp/sigma-nonconsecutive-desktop.png",
                    "/tmp/sigma-nonconsecutive-mobile.png",
                ],
                "page_errors": errors,
            },
            ensure_ascii=False,
            indent=2,
        )
    )
    browser.close()
