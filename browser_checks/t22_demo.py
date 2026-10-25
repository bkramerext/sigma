"""Real Chrome UI checks for the read-only Demo and all report exports.

The checks use deterministic mocked API responses, including report bodies; they
cover browser rendering and interactions, not live browser-to-backend behavior.
Backend authorization and snapshot boundaries are covered by tests/cloud_demo.py.
No Google or model call is made.
"""

import json
import os
from pathlib import Path
from urllib.parse import parse_qs, urlsplit

from playwright.sync_api import expect, sync_playwright

from sigma.project_reports import render_report

BASE_URL = os.environ.get("SIGMA_BROWSER_BASE_URL", "http://127.0.0.1:5173")
AUDIT_PATH = Path(__file__).resolve().parents[1] / "cloud-demo/handshake-demo-audit.json"
AUDIT = json.loads(AUDIT_PATH.read_text(encoding="utf-8"))

with sync_playwright() as playwright:
    browser = playwright.chromium.launch(
        executable_path=os.environ.get(
            "SIGMA_BROWSER_EXECUTABLE",
            "/Applications/Google Chrome.app/Contents/MacOS/Google Chrome",
        ),
        headless=True,
    )
    page = browser.new_page(viewport={"width": 1440, "height": 1000}, accept_downloads=True)
    api_requests: list[str] = []
    page.on(
        "request",
        lambda request: api_requests.append(request.url) if "/api/" in request.url else None,
    )
    page.on(
        "console",
        lambda message: (
            print(f"browser console: {message.text}") if message.type == "error" else None
        ),
    )
    page.route(
        "**/api/cloud-auth/status",
        lambda route: route.fulfill(
            status=200,
            content_type="application/json",
            body=json.dumps(
                {
                    "enabled": True,
                    "ready": True,
                    "authenticated": False,
                    "user": None,
                    "admin_contact_email": "access@example.org",
                }
            ),
        ),
    )
    page.route(
        "**/api/cloud-demo/",
        lambda route: route.fulfill(
            status=200, content_type="application/json", body=json.dumps(AUDIT)
        ),
    )

    def report(route):
        output_format = parse_qs(urlsplit(route.request.url).query).get("format", ["txt"])[0]
        body, media_type = render_report(AUDIT, output_format)
        route.fulfill(status=200, content_type=media_type, body=body)

    page.route("**/api/cloud-demo/report**", report)
    page.goto(f"{BASE_URL}/demo", wait_until="networkidle")
    expect(page.get_by_role("heading", name="Explore a SIGMA research project")).to_be_visible()
    expect(page.get_by_role("heading", name="Counting Pairwise Handshakes")).to_be_visible()
    expect(page.get_by_role("heading", name="Strategies")).to_be_visible()
    expect(page.get_by_text("Direct counting", exact=True)).to_be_visible()
    expect(page.get_by_role("heading", name="Research sessions")).to_be_visible()
    page.get_by_text("Session #1: Direct counting", exact=False).click()
    expect(page.get_by_text("n(n − 1)/2", exact=False)).to_be_visible()
    expect(page.get_by_text("Inspect saved computation")).to_be_visible()
    page.get_by_text("Inspect saved computation").click()
    expect(page.get_by_text("Captured artifact: handshake-counts.csv")).to_be_visible()
    for forbidden in (
        "New",
        "Generate",
        "Edit",
        "Fork",
        "Remove",
        "Start",
        "Stop",
        "Resume",
        "Settings",
    ):
        expect(page.get_by_role("button", name=forbidden, exact=True)).to_have_count(0)

    page.get_by_role("button", name="Export project").first.click()
    dialog = page.get_by_role("dialog")
    for label, extension, expected in (
        ("Project Audit", ".json", '"export_version": 2'),
        ("Text file", ".txt", "Research problem:"),
        ("HTML report", ".html", "<!doctype html>"),
        ("LaTeX report", ".tex", "\\documentclass"),
    ):
        dialog.get_by_label(label).check()
        try:
            with page.expect_download(timeout=8000) as pending:
                dialog.get_by_role("button", name="Download").click()
        except Exception:
            print("export dialog after failure:", dialog.inner_text())
            print("API requests:", api_requests)
            raise
        download = pending.value
        assert download.suggested_filename.endswith(extension), download.suggested_filename
        target = Path("/tmp") / download.suggested_filename
        download.save_as(target)
        assert expected in target.read_text(encoding="utf-8")
        target.unlink()
        if label != "LaTeX report":
            page.get_by_role("button", name="Export project").first.click()
            dialog = page.get_by_role("dialog")

    assert not any("/api/projects/" in url or "/api/ai/" in url for url in api_requests), (
        api_requests
    )
    for width, height in ((1440, 1000), (390, 844)):
        page.set_viewport_size({"width": width, "height": height})
        if not page.evaluate("document.documentElement.scrollWidth <= window.innerWidth"):
            print(
                "horizontal overflow:",
                page.evaluate(
                    "Array.from(document.querySelectorAll('*')).filter(el => el.scrollWidth > el.clientWidth + 1).map(el => [el.tagName, el.className, el.scrollWidth, el.clientWidth]).slice(0, 12)"
                ),
            )
            raise AssertionError(f"horizontal overflow at {width}px")
    browser.close()

print(
    "PASS real Chrome hosted Demo, saved evidence, read-only controls, four exports, and desktop/mobile layout"
)
