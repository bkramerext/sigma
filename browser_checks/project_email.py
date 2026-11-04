"""Browser acceptance for sticky Email Project attachment choices and retry safety."""

from __future__ import annotations

import os
from urllib.parse import quote
from uuid import uuid4

from playwright.sync_api import expect, sync_playwright

BASE = os.environ.get("SIGMA_BROWSER_BASE_URL", "http://127.0.0.1:5173").rstrip("/")
FIXTURE = os.environ.get("SIGMA_BROWSER_FIXTURE_URL", "http://127.0.0.1:8026").rstrip("/")


def paper(identifier: str, version: int, score: int) -> dict:
    return {
        "paper_id": identifier,
        "paper_version": version,
        "title": "Saved " + identifier,
        "created_at": f"2026-11-0{version}T12:00:00+00:00",
        "download_basename": "paper-" + identifier,
        "pdf_available": True,
        "score": {"total": score},
    }


def main() -> None:
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
        page.on("pageerror", lambda error: errors.append(str(error)))

        def proxy(route):
            route.fulfill(
                response=route.fetch(
                    url=route.request.url.replace(BASE, FIXTURE),
                    headers={**route.request.headers, "origin": BASE},
                )
            )

        page.route("**/api/**", proxy)
        page.goto(BASE)
        created = page.evaluate(
            """async title => {
              const response = await fetch('/api/projects/create', {
                method: 'POST', headers: {'Content-Type': 'application/json'},
                body: JSON.stringify({
                  title, problem:'Test Email Project dialog and importable attachments.',
                  investigation_type:'mathematical'
                })
              });
              return {status:response.status, body:await response.json()};
            }""",
            "Email Acceptance " + str(uuid4()),
        )
        assert created["status"] == 201, created
        path = created["body"]["path"]
        project_id = created["body"]["project"]["id"]
        stars = [paper("new", 3, 20), paper("star", 2, 70), paper("old", 1, 52)]
        state = {"papers": stars, "fail": True, "fail_email": False}
        requests: list[dict] = []

        def paper_route(route):
            if state["fail"]:
                route.fulfill(status=503, json={"error": "Temporary paper-list failure"})
            else:
                route.fulfill(
                    status=200,
                    json={
                        "papers": state["papers"],
                        "paper_count": len(state["papers"]),
                        "best_paper_score": 70,
                    },
                )

        def email_route(route):
            requests.append(route.request.post_data_json)
            if len(requests) == 1 or state["fail_email"]:
                state["fail_email"] = False
                route.fulfill(status=503, json={"error": "SMTP was unavailable; nothing sent."})
            else:
                route.fulfill(status=200, json={"sent": 2})

        page.route("**/api/projects/papers?**", paper_route)
        page.route("**/api/projects/email", email_route)
        page.goto(BASE + "/project?path=" + quote(path, safe=""))
        page.get_by_role("button", name="Email project").click()
        dialog = page.get_by_role("dialog", name="Email Project")
        expect(dialog).to_be_visible()
        expect(dialog).to_contain_text("Paper list unavailable")
        expect(dialog).not_to_contain_text("No papers generated.")
        dialog.locator("#email-project-recipients").fill("first@example.org second@example.org")
        dialog.locator("#email-project-body").fill("Here is the research.")
        state["fail"] = False
        dialog.get_by_role("button", name="Retry").click()
        select = dialog.locator("#email-project-paper")
        expect(select).to_be_visible()
        # Newest starred paper is preferred to a newer unstarred version.
        expect(select).to_have_value("star")
        assert "★" in select.locator("option[value=star]").inner_text()
        dialog.get_by_label("Also attach paper as PDF and its source LaTeX").check()
        select.select_option("new")
        dialog.get_by_role("button", name="Cancel").click()
        page.get_by_role("button", name="Email project").click()
        expect(dialog.locator("#email-project-recipients")).to_have_value(
            "first@example.org second@example.org"
        )
        expect(dialog.locator("#email-project-body")).to_have_value("Here is the research.")
        expect(dialog.get_by_label("Also attach paper as PDF and its source LaTeX")).to_be_checked()
        expect(dialog.locator("#email-project-paper")).to_have_value("new")
        # A temporary list failure must not reset the sticky attachment mode.
        dialog.get_by_role("button", name="Cancel").click()
        state["fail"] = True
        page.get_by_role("button", name="Email project").click()
        expect(dialog).to_contain_text("Paper list unavailable")
        expect(dialog.get_by_label("Also attach paper as PDF and its source LaTeX")).to_be_checked()
        expect(dialog.get_by_role("button", name="Send")).to_be_disabled()
        state["fail"] = False
        dialog.get_by_role("button", name="Retry").click()
        expect(dialog.locator("#email-project-paper")).to_have_value("new")
        expect(dialog.get_by_role("button", name="Send")).to_be_enabled()
        dialog.get_by_role("button", name="Send").click()
        expect(dialog).to_contain_text("SMTP was unavailable; nothing sent.")
        dialog.get_by_role("button", name="Send").click()
        expect(dialog).not_to_be_visible()
        assert len(requests) == 2
        assert requests[0]["request_id"] == requests[1]["request_id"]
        assert requests[0]["mode"] == "pdf_tex"
        assert requests[0]["paper_id"] == "new"
        assert requests[0]["recipients"] == "first@example.org second@example.org"
        # Project-only Send must work when the paper-list endpoint is down.
        state["fail"] = True
        page.get_by_role("button", name="Email project").click()
        expect(dialog).to_contain_text("Paper list unavailable")
        dialog.get_by_label("Just attach project").check()
        expect(dialog.get_by_role("button", name="Send")).to_be_enabled()
        dialog.get_by_role("button", name="Send").click()
        expect(dialog).not_to_be_visible()
        assert requests[-1]["mode"] == "project"
        state["fail"] = False
        # A removed paper falls back to the first starred available version.
        state["papers"] = stars[1:]
        page.get_by_role("button", name="Email project").click()
        expect(dialog.locator("#email-project-paper")).to_have_value("star")
        dialog.get_by_role("button", name="Cancel").click()
        state["papers"] = []
        page.get_by_role("button", name="Email project").click()
        expect(dialog).to_contain_text("No papers generated.")
        expect(dialog.get_by_label("Also attach paper as PDF", exact=True)).to_be_disabled()
        expect(
            dialog.get_by_label("Also attach paper as PDF and its source LaTeX")
        ).to_be_disabled()
        expect(dialog.locator("#email-project-paper")).to_have_count(0)
        # Changing content after a definite no-send starts a new idempotent request.
        state["fail_email"] = True
        dialog.get_by_role("button", name="Send").click()
        expect(dialog).to_contain_text("SMTP was unavailable; nothing sent.")
        failed_request_id = requests[-1]["request_id"]
        dialog.locator("#email-project-body").fill("A revised, explicit request.")
        dialog.get_by_role("button", name="Send").click()
        expect(dialog).not_to_be_visible()
        assert requests[-1]["request_id"] != failed_request_id
        assert any(project_id in key for key in page.evaluate("Object.keys(localStorage)"))
        assert not errors, errors
        browser.close()


if __name__ == "__main__":
    main()
