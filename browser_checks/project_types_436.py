"""Real Chrome acceptance for unified types, deletion snapshots and start warning."""

import json
import os
from pathlib import Path

from playwright.sync_api import expect, sync_playwright

BASE_URL = os.environ.get("SIGMA_BROWSER_BASE_URL", "http://127.0.0.1:5173").rstrip("/")
FIXTURE_URL = os.environ.get("SIGMA_BROWSER_FIXTURE_URL", "http://127.0.0.1:8026").rstrip("/")
EVIDENCE = Path("docs/evaluations/t436/evidence")
EVIDENCE.mkdir(parents=True, exist_ok=True)

with sync_playwright() as playwright:
    browser = playwright.chromium.launch(
        executable_path=os.environ.get(
            "SIGMA_BROWSER_EXECUTABLE",
            "/Applications/Google Chrome.app/Contents/MacOS/Google Chrome",
        ),
        headless=True,
    )
    page = browser.new_page(viewport={"width": 1440, "height": 1000})
    errors: list[str] = []
    requests: list[str] = []
    page.on("pageerror", lambda error: errors.append(str(error)))
    page.on(
        "request", lambda request: requests.append(request.url) if "/api/" in request.url else None
    )
    page.on("dialog", lambda dialog: dialog.accept())

    def proxy(route):
        headers = dict(route.request.headers)
        headers["origin"] = "http://127.0.0.1:5173"
        response = route.fetch(
            url=route.request.url.replace(BASE_URL, FIXTURE_URL), headers=headers
        )
        route.fulfill(response=response)

    page.route("**/api/**", proxy)

    page.goto(BASE_URL)
    page.get_by_role("button", name="Project Types", exact=True).click()
    dialog = page.get_by_role("dialog", name="Project Types")
    expect(dialog).to_be_visible()
    expect(dialog.get_by_role("checkbox", name="Show built-in project types")).to_be_checked()
    expect(dialog.get_by_text("Literature", exact=True).first).to_be_visible()
    assert dialog.get_by_text("Other", exact=True).count() == 0
    builtin_names = (
        dialog.locator(".project-types-body > section")
        .nth(0)
        .locator(".project-type-card > summary strong")
        .all_text_contents()
    )
    assert builtin_names == sorted(builtin_names, key=str.casefold)
    dialog.locator(".project-type-card").filter(has_text="Literature").locator("summary").click()
    page.screenshot(path=str(EVIDENCE / "types-desktop.png"), full_page=True)

    page.get_by_role("button", name="Add project type").click()
    custom = dialog.locator(".project-type-card").last
    custom.get_by_label("Name").fill("Browser Literature")
    custom.locator("label").filter(has_text="Based on").locator("select").select_option(
        "literature"
    )
    custom.get_by_label("Scope").fill("An independent study of literary works.")
    expect(custom.locator(".project-type-card-icon svg")).to_be_visible()
    table_ratio = custom.locator(".pt-reference-table").first.evaluate(
        "table => { const rect = table.getBoundingClientRect(); const columns = [...table.querySelectorAll('col')].map(col => col.getBoundingClientRect().width); return columns[0] / rect.width; }"
    )
    assert 0.78 <= table_ratio <= 0.82, table_ratio
    expect(dialog.get_by_role("button", name="Save", exact=True)).to_be_enabled()
    dialog.get_by_role("button", name="Save", exact=True).click()
    expect(dialog).not_to_be_visible()
    types = page.request.get(f"{FIXTURE_URL}/api/project-types").json()["project_types"]
    custom_type = next(item for item in types if item["name"] == "Browser Literature")
    assert custom_type["icon"]["key"] == "literature"
    assert custom_type["based_on"] == "literature"
    assert custom_type["scope"] == "An independent study of literary works."

    created = page.request.post(
        f"{FIXTURE_URL}/api/projects/create",
        data={
            "title": "Deleted custom type",
            "problem": "Preserve and warn",
            "investigation_type": custom_type["id"],
        },
    )
    assert created.status == 201, created.text()
    project = created.json()
    strategy = page.request.post(
        f"{FIXTURE_URL}/api/projects/strategies",
        data={"path": project["path"], "title": "Inspect", "approach": "Inspect source evidence."},
    )
    assert strategy.status == 201, strategy.text()
    page.goto(f"{BASE_URL}/project?path={project['path']}")
    expect(page.get_by_role("heading", name="Deleted custom type")).to_be_visible()

    page.get_by_role("button", name="Project Types", exact=True).click()
    dialog = page.get_by_role("dialog", name="Project Types")
    custom = dialog.locator(".project-type-card").filter(has_text="Browser Literature")
    custom.locator("summary").click()
    custom.get_by_role("button", name="Remove", exact=True).click()
    expect(custom).to_have_count(0)
    dialog.get_by_role("button", name="Cancel", exact=True).click()
    warning = page.get_by_text("Project type unavailable", exact=True).first
    expect(warning).to_be_visible()
    expect(page.get_by_role("button", name="Export project")).to_be_visible()
    page.get_by_role("button", name="Export project").click()
    export_dialog = page.get_by_role("dialog", name="Export Project")
    with page.expect_download() as download_info:
        export_dialog.get_by_role("button", name="Download", exact=True).click()
    exported = json.loads(Path(download_info.value.path()).read_text())
    assert (
        exported["files"]["project.json"]["project_type_snapshot"]["scope"]
        == "An independent study of literary works."
    )

    page.set_viewport_size({"width": 390, "height": 844})
    page.screenshot(path=str(EVIDENCE / "deleted-project-mobile.png"), full_page=True)
    dispatches_before = len(
        [
            url
            for url in requests
            if "/api/projects/research-sessions/start" in url
            or "/api/projects/proposals/config" in url
        ]
    )
    page.get_by_role("button", name="Start a new research session").click()
    start_warning = page.get_by_role("alertdialog", name="Project type unavailable")
    expect(start_warning).to_be_visible()
    expect(start_warning.get_by_role("button", name="Continue with saved settings")).to_be_visible()
    expect(start_warning.get_by_role("button", name="Choose a replacement")).to_be_visible()
    dispatches_after = len(
        [
            url
            for url in requests
            if "/api/projects/research-sessions/start" in url
            or "/api/projects/proposals/config" in url
        ]
    )
    assert dispatches_before == dispatches_after, "start warning appeared after dispatch"
    page.screenshot(path=str(EVIDENCE / "missing-type-start-warning.png"), full_page=True)
    assert not errors, errors
    browser.close()

print(
    f"PASS real Chrome Project Types create/delete, responsive missing-type presentation and pre-dispatch warning; evidence {EVIDENCE}"
)
