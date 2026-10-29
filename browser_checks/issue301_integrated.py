"""Browser-to-backend session log integration using real log storage and HTTP."""

from __future__ import annotations

import json
import os
import subprocess
import tempfile
import threading
import time
from http.server import BaseHTTPRequestHandler, ThreadingHTTPServer
from pathlib import Path
from types import SimpleNamespace
from unittest.mock import patch
from urllib.parse import parse_qs, urlsplit

from playwright.sync_api import expect, sync_playwright

PROJECT_ID = "a12ca401-2210-4c88-8fe6-84a33b1e5eea"
SESSION_ID = "d0231c99-5425-4a20-8ff2-fc52c1800b8c"
VITE_URL = "http://127.0.0.1:5197"


def main() -> None:
    from sigma import research_sessions, session_log

    with tempfile.TemporaryDirectory(prefix="sigma-session-log-browser-") as folder:
        project_file = Path(folder) / "project.json"
        project_file.touch()
        session = {
            "id": SESSION_ID,
            "project_id": PROJECT_ID,
            "session_number": 2,
            "status": "running",
        }
        view = SimpleNamespace(
            project=SimpleNamespace(
                id=PROJECT_ID,
                title="Why do Xenopus tadpoles temporarily lose tail regeneration?",
                problem="Why do Xenopus tadpoles temporarily lose tail regeneration?",
            )
        )
        state = {"requests": 0, "active": 0, "maximum_active": 0, "cursors": []}
        guard = threading.Lock()

        request_event = {
            "type": "provider_request",
            "request_id": "fixture-live-request",
            "role": "investigator",
            "round": 2,
            "strategy_id": "strategy-fixture",
            "turn": 3,
            "status": "in_flight",
            "model": "fixture-model",
            "request": {"input": "Prompt line one\nPrompt line two"},
        }
        response_event = {
            "type": "provider_response",
            "request_id": "fixture-live-request",
            "role": "investigator",
            "status": "completed",
            "response": {"output_text": "Fixture answer"},
            "response_wire": '{"output_text":"Fixture answer"}',
            "duration_seconds": 2.5,
            "usage": {"input_tokens": 30, "output_tokens": 8},
            "estimated_cost_usd": 0.0001,
        }

        def add_response() -> None:
            session_log.append(str(project_file), session, response_event)
            session_log.flush()

        class Handler(BaseHTTPRequestHandler):
            def log_message(self, *_args) -> None:
                return

            def _send(self, status: int, body: bytes, content_type: str, headers=None) -> None:
                self.send_response(status)
                self.send_header("Content-Type", content_type)
                self.send_header("Content-Length", str(len(body)))
                self.send_header("Access-Control-Allow-Origin", VITE_URL)
                self.send_header("Access-Control-Allow-Credentials", "true")
                self.send_header("Vary", "Origin")
                for key, value in (headers or {}).items():
                    self.send_header(key, value)
                self.end_headers()
                self.wfile.write(body)

            def do_GET(self) -> None:
                parsed = urlsplit(self.path)
                if parsed.path.endswith("/log/download"):
                    trace_path = session_log.log_path(str(project_file), PROJECT_ID, SESSION_ID)
                    self._send(
                        200,
                        trace_path.read_bytes(),
                        "text/markdown; charset=utf-8",
                        {"Content-Disposition": 'attachment; filename="session-integration.md"'},
                    )
                    return
                with guard:
                    state["requests"] += 1
                    state["active"] += 1
                    state["maximum_active"] = max(state["maximum_active"], state["active"])
                    request_number = state["requests"]
                query = parse_qs(parsed.query)
                after = int(query.get("after", ["0"])[0])
                with guard:
                    state["cursors"].append(after)
                try:
                    if request_number == 1:
                        threading.Timer(2.7, add_response).start()
                        time.sleep(1.35)
                    payload = session_log.read(str(project_file), SESSION_ID, after)
                    # Deliberately replay an old record on incremental reads. The UI
                    # must deduplicate even if a backend/proxy retries a page.
                    if after > 0 and payload["events"]:
                        first, *_rest = session_log.read(str(project_file), SESSION_ID, 0)["events"]
                        payload["events"] = [first, *payload["events"]]
                    self._send(200, json.dumps(payload).encode(), "application/json")
                except Exception as exc:  # noqa: BLE001 - surfaced as a browser HTTP failure
                    self._send(500, str(exc).encode(), "text/plain")
                finally:
                    with guard:
                        state["active"] -= 1

        server = ThreadingHTTPServer(("127.0.0.1", 0), Handler)
        server_thread = threading.Thread(target=server.serve_forever, daemon=True)
        server_thread.start()
        backend_url = f"http://127.0.0.1:{server.server_port}"

        # Give the test session an AI-derived label and one real persisted request.
        session_log.record_ai_name(
            str(project_file),
            PROJECT_ID,
            "Why do Xenopus tadpoles temporarily lose tail regeneration?",
            "Why do Xenopus tadpoles temporarily lose tail regeneration?",
            "The analysis demonstrates Xenopus tadpole tail regeneration after injury.",
        )
        session_log.append(str(project_file), session, request_event)
        session_log.flush()

        vite = subprocess.Popen(
            ["npm", "run", "dev", "--", "--host", "127.0.0.1", "--port", "5197", "--strictPort"],
            cwd=Path(__file__).resolve().parents[1] / "frontend",
            stdout=subprocess.DEVNULL,
            stderr=subprocess.DEVNULL,
        )
        try:
            deadline = time.monotonic() + 20
            while time.monotonic() < deadline:
                try:
                    import urllib.request

                    urllib.request.urlopen(VITE_URL, timeout=0.5).close()
                    break
                except OSError:
                    if vite.poll() is not None:
                        raise RuntimeError("Vite exited before the integrated browser check")
                    time.sleep(0.15)
            else:
                raise TimeoutError("Vite did not become ready")

            with (
                patch.object(session_log, "inspect_project", return_value=view),
                patch.object(session_log, "project_path", return_value=project_file),
                patch.object(research_sessions, "get_session", return_value=session),
                sync_playwright() as playwright,
            ):
                browser = playwright.chromium.launch(
                    executable_path=os.environ.get(
                        "SIGMA_BROWSER_EXECUTABLE",
                        "/Applications/Google Chrome.app/Contents/MacOS/Google Chrome",
                    ),
                    headless=True,
                )
                context = browser.new_context(viewport={"width": 1200, "height": 900})

                def forward(route) -> None:
                    source = urlsplit(route.request.url)
                    destination = f"{backend_url}{source.path}"
                    if source.query:
                        destination += f"?{source.query}"
                    route.continue_(url=destination)

                context.route("**/api/projects/research-sessions/*/log**", forward)
                opener = context.new_page()
                opener.goto(VITE_URL, wait_until="domcontentloaded")
                opener.evaluate(
                    """async ({id, path}) => {
                      const React = (await import('/node_modules/.vite/deps/react.js')).default;
                      const { createRoot } = (await import('/node_modules/.vite/deps/react-dom_client.js')).default;
                      const { default: SessionLogButton } = await import('/src/SessionLogButton.tsx');
                      const host = document.createElement('main');
                      document.body.replaceChildren(host);
                      createRoot(host).render(React.createElement(SessionLogButton, { sessionId:id, sessionNumber:2, path }));
                    }""",
                    {"id": SESSION_ID, "path": str(project_file)},
                )
                with opener.expect_popup() as popup_info:
                    opener.get_by_role("button", name="Open Session 2 log").click()
                page = popup_info.value
                page.wait_for_load_state("domcontentloaded")
                expect(page).to_have_title("Xenopus Tadpoles, Session 2")
                expect(page.locator("h1")).to_have_text("Xenopus Tadpoles, Session 2")
                details = page.locator(".session-log-events details").first
                expect(details.locator("summary").first).to_contain_text("in flight", timeout=5000)
                expect(details.locator("summary").first).to_contain_text("2.5s", timeout=10000)
                with guard:
                    assert state["requests"] >= 3
                    assert state["maximum_active"] == 1, state
                    assert state["cursors"][0] == 0
                    assert state["cursors"] == sorted(state["cursors"]), state["cursors"]
                details.locator("summary").first.click()
                expect(details.locator("pre").nth(0)).to_contain_text("Prompt line two")
                expect(details.locator("pre").nth(1)).to_contain_text("Fixture answer")
                expect(page.locator(".session-log-events > li")).to_have_count(1)
                with page.expect_download() as download_info:
                    page.get_by_role("link", name="Download Log").click()
                assert download_info.value.suggested_filename == "session-integration.md"
                page.reload(wait_until="domcontentloaded")
                expect(page.locator("h1")).to_contain_text("Xenopus Tadpoles")
                expect(page.locator(".session-log-events > li")).to_have_count(1)
                page.screenshot(
                    path="docs/evaluations/issue301/session-log-integrated-chromium.png",
                    full_page=True,
                )
                page.close()
                expect(opener.locator("body")).to_be_visible()
                browser.close()
        finally:
            vite.terminate()
            vite.wait(timeout=5)
            server.shutdown()
            server.server_close()
            session_log.flush()

    print(
        "PASS integrated Chromium/backend: real HTTP polling, serialized append/read/download, AI-derived title, delayed response, duplicate-event defense, reload"
    )


if __name__ == "__main__":
    main()
