"""Real Chromium check for the separate live session log window and polling UI."""

from __future__ import annotations

import os

from playwright.sync_api import expect, sync_playwright

BASE_URL = os.environ.get("SIGMA_BROWSER_BASE_URL", "http://127.0.0.1:5193")
SESSION_ID = "d0231c99-5425-4a20-8ff2-fc52c1800b8c"
PROJECT_PATH = "/fixture/project.json"


def main() -> None:
    state = {"polls": 0}
    request = {
        "model": "fixture-model",
        "input": "Investigator prompt\n```\nmultiline request\n```",
    }

    with sync_playwright() as playwright:
        browser = playwright.chromium.launch(
            executable_path=os.environ.get(
                "SIGMA_BROWSER_EXECUTABLE",
                "/Applications/Google Chrome.app/Contents/MacOS/Google Chrome",
            ),
            headless=True,
        )
        context = browser.new_context(viewport={"width": 1200, "height": 900})
        opener = context.new_page()
        opener.goto(BASE_URL, wait_until="domcontentloaded")

        def api(route):
            state["polls"] += 1
            after = int(route.request.url.split("after=")[-1])
            events = [
                {
                    "seq": 1,
                    "timestamp": "2026-10-29T12:00:00+00:00",
                    "type": "provider_request",
                    "request_id": "fixture-request-1",
                    "role": "investigator",
                    "round": 1,
                    "status": "in_flight",
                    "request": request,
                    "model": "fixture-model",
                }
            ]
            if state["polls"] >= 4:
                events.append(
                    {
                        "seq": 2,
                        "timestamp": "2026-10-29T12:00:01+00:00",
                        "type": "provider_response",
                        "request_id": "fixture-request-1",
                        "role": "investigator",
                        "status": "completed",
                        "response": {"output_text": "Fixture result"},
                        "duration_seconds": 1.25,
                        "usage": {"input_tokens": 123, "output_tokens": 9},
                    }
                )
            if after == 0:
                new_events = events
                cursor = 200 if len(events) > 1 else 100
            elif state["polls"] >= 4 and after < 200:
                new_events = events[1:]
                cursor = 200
            else:
                new_events = []
                cursor = after
            route.fulfill(
                json={
                    "events": new_events,
                    "cursor": cursor,
                    "short_name": "Xenopus Tadpoles",
                    "session": {"number": 1, "status": "running"},
                }
            )

        context.route("**/api/projects/research-sessions/*/log?**", api)
        context.route(
            "**/api/projects/research-sessions/*/log/download?**",
            lambda route: route.fulfill(
                status=200,
                content_type="text/markdown",
                body="# Xenopus Tadpoles, Session 1\n",
                headers={"Content-Disposition": 'attachment; filename="session-fixture.md"'},
            ),
        )
        opener.evaluate(
            """async ({id, path}) => {
              const React = (await import('/node_modules/.vite/deps/react.js')).default;
              const { createRoot } = (await import('/node_modules/.vite/deps/react-dom_client.js')).default;
              const { default: SessionLogButton } = await import('/src/SessionLogButton.tsx');
              const host = document.createElement('main');
              document.body.replaceChildren(host);
              createRoot(host).render(React.createElement(SessionLogButton, { sessionId:id, sessionNumber:1, path }));
            }""",
            {"id": SESSION_ID, "path": PROJECT_PATH},
        )
        with opener.expect_popup() as popup_info:
            opener.get_by_role("button", name="Open Session 1 log").click()
        page = popup_info.value
        page.wait_for_load_state("domcontentloaded")
        expect(page.locator("h1")).to_have_text("Xenopus Tadpoles, Session 1")
        expect(page).to_have_title("Xenopus Tadpoles, Session 1")
        details = page.locator(".session-log-events details").first
        expect(details.locator("summary")).to_contain_text("in flight")
        expect(details.locator("summary")).to_contain_text("1.25s", timeout=5000)
        details.locator("summary").click()
        expect(details.locator("pre").nth(0)).to_contain_text("multiline request")
        expect(details.locator("pre").nth(1)).to_contain_text("Fixture result")
        with page.expect_download() as download_info:
            page.get_by_role("link", name="Download Log").click()
        assert download_info.value.suggested_filename == "session-fixture.md"
        page.reload(wait_until="domcontentloaded")
        expect(page.locator("h1")).to_have_text("Xenopus Tadpoles, Session 1")
        expect(page.locator(".session-log-events details summary")).to_contain_text("1.25s")
        page.screenshot(path="docs/evaluations/issue301/session-log-chromium.png", full_page=True)
        assert state["polls"] >= 2
        page.close()
        expect(opener.locator("body")).to_be_visible()
        browser.close()

    print(
        "PASS real Chromium: separate window, title, pending-to-paired live update, multiline request and independent close"
    )


if __name__ == "__main__":
    main()
