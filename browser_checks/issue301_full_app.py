"""Real Chromium through the running FastAPI app and production log store.

The only fixtures are manually persisted events and a test-only response delay /
duplicate page wrapper. No research or provider call is initiated.
"""

from __future__ import annotations

import os
import socket
import subprocess
import tempfile
import threading
import time
from pathlib import Path

import uvicorn
from playwright.sync_api import expect, sync_playwright

REPO = Path(__file__).resolve().parents[1]
CHROME = os.environ.get(
    "SIGMA_BROWSER_EXECUTABLE",
    "/Applications/Google Chrome.app/Contents/MacOS/Google Chrome",
)


def free_port() -> int:
    with socket.socket() as sock:
        sock.bind(("127.0.0.1", 0))
        return int(sock.getsockname()[1])


def main() -> None:
    with tempfile.TemporaryDirectory(prefix="sigma-issue301-full-app-") as temporary:
        root = Path(temporary) / "projects"
        root.mkdir()
        os.environ["SIGMA_PROJECTS_ROOT"] = str(root)
        from sigma import research_sessions, session_log
        from sigma.api import app
        from sigma.projects import create_strategy, initialize_project

        project = initialize_project(
            root / "xenopus-tadpoles.json",
            "Why do Xenopus tadpoles temporarily lose tail regeneration?",
            "Why do Xenopus tadpoles temporarily lose tail regeneration?",
        )
        strategy = create_strategy(
            project.path, "Regeneration", "Review tail regeneration evidence."
        )
        session = research_sessions.mock_session(
            project.path, strategy.project.strategies[0].id, "issue301-browser-fixture", "completed"
        )
        session_id = session["id"]
        project_id = project.project.id
        session_log.record_ai_name(
            project.path,
            project_id,
            project.project.title,
            project.project.problem,
            "The evidence suggests Xenopus tadpoles can regenerate a tail after injury.",
        )
        request_event = {
            "type": "provider_request",
            "request_id": "full-app-fixture-request",
            "role": "investigator",
            "round": 1,
            "strategy_id": strategy.project.strategies[0].id,
            "turn": 1,
            "status": "in_flight",
            "model": "deterministic-fixture",
            "request": {"input": "Actual request fixture\nline two"},
        }
        response_event = {
            "type": "provider_response",
            "request_id": "full-app-fixture-request",
            "role": "investigator",
            "status": "completed",
            "response": {"output_text": "Actual response fixture"},
            "duration_seconds": 1.7,
            "usage": {"input_tokens": 20, "output_tokens": 5},
            "estimated_cost_usd": 0.0001,
        }
        session_log.append(project.path, session, request_event)
        session_log.flush()

        read = session_log.read
        state = {"reads": 0, "active": 0, "maximum_active": 0}
        guard = threading.Lock()
        response_timer: threading.Timer | None = None

        def delayed_read(path: str, sid: str, after: int = 0):
            nonlocal response_timer
            with guard:
                state["reads"] += 1
                state["active"] += 1
                state["maximum_active"] = max(state["maximum_active"], state["active"])
                number = state["reads"]
            try:
                if number == 1:
                    response_timer = threading.Timer(
                        2.0,
                        lambda: (
                            session_log.append(project.path, session, response_event),
                            session_log.flush(),
                        ),
                    )
                    response_timer.start()
                    time.sleep(1.25)
                payload = read(path, sid, after)
                if after > 0 and payload["events"]:
                    payload["events"] = [read(path, sid, 0)["events"][0], *payload["events"]]
                return payload
            finally:
                with guard:
                    state["active"] -= 1

        session_log.read = delayed_read
        api_port = free_port()
        ui_port = free_port()
        api_server = uvicorn.Server(
            uvicorn.Config(app, host="127.0.0.1", port=api_port, log_level="error")
        )
        api_thread = threading.Thread(target=api_server.run, daemon=True)
        api_thread.start()
        vite = subprocess.Popen(
            [
                "npm",
                "run",
                "dev",
                "--",
                "--host",
                "127.0.0.1",
                "--port",
                str(ui_port),
                "--strictPort",
            ],
            cwd=REPO / "frontend",
            env={**os.environ, "SIGMA_API_TARGET": f"http://127.0.0.1:{api_port}"},
            stdout=subprocess.DEVNULL,
            stderr=subprocess.DEVNULL,
        )
        try:
            deadline = time.monotonic() + 20
            while time.monotonic() < deadline and not api_server.started:
                time.sleep(0.05)
            if not api_server.started:
                raise TimeoutError("SIGMA FastAPI app did not start")
            ui_url = f"http://127.0.0.1:{ui_port}"
            while time.monotonic() < deadline:
                try:
                    import urllib.request

                    urllib.request.urlopen(ui_url, timeout=0.5).close()
                    break
                except OSError:
                    if vite.poll() is not None:
                        raise RuntimeError("Vite exited before full-app browser check")
                    time.sleep(0.1)
            else:
                raise TimeoutError("SIGMA frontend did not start")

            with sync_playwright() as playwright:
                browser = playwright.chromium.launch(executable_path=CHROME, headless=True)
                context = browser.new_context(viewport={"width": 1200, "height": 900})
                opener = context.new_page()
                opener.goto(ui_url, wait_until="domcontentloaded")
                opener.evaluate(
                    """async ({id, number, path}) => {
                      const React = (await import('/node_modules/.vite/deps/react.js')).default;
                      const { createRoot } = (await import('/node_modules/.vite/deps/react-dom_client.js')).default;
                      const { default: SessionLogButton } = await import('/src/SessionLogButton.tsx');
                      const host = document.createElement('main'); document.body.replaceChildren(host);
                      const icon = d => React.createElement('svg', {viewBox:'0 0 20 20', 'aria-hidden':true}, React.createElement('path',{d}));
                      const controls = React.createElement('div',{className:'session-heading-actions','aria-label':'Session 1 actions'},
                        React.createElement('button',{type:'button',className:'text-view-link text-view-icon workspace-icon-button process-control session-mini-process-control','aria-label':'Resume Session 1',title:'Resume session #1'},icon('M6 3.8v12.4L16 10 6 3.8Z')),
                        React.createElement('button',{type:'button',className:'text-view-link text-view-icon workspace-icon-button process-control session-mini-process-control','aria-label':'Stop Session 1',title:'Stop Session 1; it can be resumed later'},icon('M5 5h10v10H5z')),
                        React.createElement(SessionLogButton, { sessionId:id, sessionNumber:number, path }));
                      const shell=React.createElement('main',{className:'workspace-page'},React.createElement('div',{className:'session-summary'},React.createElement('div',{className:'session-title-line'},controls)));
                      createRoot(host).render(shell);
                    }""",
                    {"id": session_id, "number": session["session_number"], "path": project.path},
                )
                resume_button = opener.get_by_role("button", name="Resume Session 1")
                stop_button = opener.get_by_role("button", name="Stop Session 1")
                resume_box = resume_button.bounding_box()
                stop_box = stop_button.bounding_box()
                assert resume_box and stop_box
                assert (
                    (resume_box["width"], resume_box["height"])
                    == (
                        stop_box["width"],
                        stop_box["height"],
                    )
                    == (28, 28)
                )
                expect(resume_button).to_have_attribute("title", "Resume session #1")
                stop_button.focus()
                opener.keyboard.press("Tab")
                link = opener.get_by_role(
                    "link", name=f"Open Session {session['session_number']} log"
                )
                expect(link).to_be_focused()
                assert link.evaluate("element => getComputedStyle(element).outlineWidth") == "2px"
                opener.screenshot(
                    path="docs/evaluations/issue301/session-log-project-controls-review.png"
                )
                with context.expect_page() as page_info:
                    link.click()
                page = page_info.value
                page.wait_for_load_state("domcontentloaded")
                title = "Xenopus Tadpoles, Session 1"
                expect(page).to_have_title(title)
                expect(page.locator("h1")).to_have_text(title)
                call = page.locator(".session-log-events details").first
                expect(call.locator("summary")).to_contain_text("in flight", timeout=5000)
                expect(call.locator("summary")).to_contain_text("1.7s", timeout=10000)
                call.locator("summary").click()
                expect(call.locator("pre").nth(0)).to_contain_text("line two")
                expect(call.locator("pre").nth(1)).to_contain_text("Actual response fixture")
                expect(page.locator(".session-log-events details")).to_have_count(1)
                page.wait_for_timeout(1200)
                item_count = page.locator(".session-log-events > li").count()
                with guard:
                    assert state["reads"] >= 2, state
                    assert state["maximum_active"] == 1, state
                assert item_count >= 1
                with page.expect_download() as download:
                    page.get_by_role("link", name="Download", exact=True).click()
                assert download.value.suggested_filename == f"session-{session_id}.md"
                downloaded_markdown = Path(download.value.path()).read_text(encoding="utf-8")
                assert "Investigator · Round 1 · Turn 1 · Request + response" in downloaded_markdown
                assert "Actual response fixture" in downloaded_markdown
                assert "## Canonical event records" in downloaded_markdown
                page.reload(wait_until="domcontentloaded")
                expect(page.locator("h1")).to_have_text(title)
                expect(page.locator(".session-log-events > li")).to_have_count(item_count)
                page.screenshot(
                    path="docs/evaluations/issue301/session-log-full-app-review.png",
                    full_page=True,
                )
                browser.close()
        finally:
            if response_timer is not None:
                response_timer.cancel()
            session_log.read = read
            vite.terminate()
            vite.wait(timeout=5)
            api_server.should_exit = True
            api_thread.join(timeout=5)
            session_log.flush()

    print(
        "PASS real Chromium through SIGMA FastAPI routes and production storage; deterministic delayed/duplicate event fixture, no provider calls"
    )


if __name__ == "__main__":
    main()
