"""Actual Chromium diagnostics display and error-reporting acceptance."""

from __future__ import annotations

import os
import socket
import subprocess
import tempfile
import time
from pathlib import Path

import httpx
from playwright.sync_api import expect, sync_playwright

ROOT = Path(__file__).resolve().parents[1]


def free_port() -> int:
    with socket.socket() as listener:
        listener.bind(("127.0.0.1", 0))
        return int(listener.getsockname()[1])


def main() -> None:
    port = free_port()
    base = f"http://127.0.0.1:{port}"
    with tempfile.TemporaryDirectory(prefix="sigma-diagnostics-browser-") as temp:
        logfile = Path(temp) / "vite.log"
        with logfile.open("w") as output:
            process = subprocess.Popen(
                [
                    "npm",
                    "--prefix",
                    str(ROOT / "frontend"),
                    "run",
                    "dev",
                    "--",
                    "--host",
                    "127.0.0.1",
                    "--port",
                    str(port),
                    "--strictPort",
                ],
                cwd=ROOT,
                stdout=output,
                stderr=subprocess.STDOUT,
            )
            try:
                for _ in range(150):
                    try:
                        if httpx.get(base, timeout=0.4).status_code == 200:
                            break
                    except httpx.HTTPError:
                        pass
                    if process.poll() is not None:
                        raise AssertionError("Vite exited: " + logfile.read_text())
                    time.sleep(0.2)
                else:
                    raise AssertionError("Vite did not become ready: " + logfile.read_text())

                with sync_playwright() as playwright:
                    browser = playwright.chromium.launch(
                        executable_path=os.environ.get(
                            "SIGMA_BROWSER_EXECUTABLE",
                            "/Applications/Google Chrome.app/Contents/MacOS/Google Chrome",
                        ),
                        headless=True,
                    )
                    context = browser.new_context()
                    page = context.new_page()
                    page.goto(base, wait_until="domcontentloaded")
                    page.evaluate(
                        """async () => {
                          const React = (await import('/node_modules/.vite/deps/react.js')).default;
                          const { createRoot } = (await import('/node_modules/.vite/deps/react-dom_client.js')).default;
                          const { default: ProjectDiagnosticsPanel } = await import('/src/ProjectDiagnosticsPanel.tsx');
                          const host = document.createElement('main');
                          document.body.replaceChildren(host);
                          createRoot(host).render(React.createElement(ProjectDiagnosticsPanel, {
                            path: '/fixture/project.json',
                            status: '',
                            diagnostics: [{
                              id: 'diagnostic-525',
                              timestamp: '2026-11-03T20:00:00+00:00',
                              stage: 'admission',
                              code: 'reference_http_404',
                              message: 'Source retrieval failed with HTTP 404.',
                              session_id: null,
                              correlation_id: null,
                            }],
                          }));
                        }"""
                    )
                    panel = page.get_by_role("region", name="Diagnostics", exact=True)
                    summary = panel.locator("summary")
                    expect(summary).to_have_text("Diagnostics (1)")
                    expect(panel.locator("details")).not_to_have_attribute("open")
                    summary.click()
                    expect(panel).to_contain_text("pre-session")
                    expect(panel).to_contain_text("reference_http_404")
                    expect(panel.get_by_role("button", name="Copy project diagnostics")).to_have_count(0)
                    expect(panel.get_by_role("link", name="Download project diagnostics")).to_have_count(0)
                    # Exercise the actual browser reporter on a transient
                    # HTTP request error, then with its backend unreachable.
                    requests: list[dict] = []

                    def report_route(route):
                        requests.append(route.request.post_data_json)
                        route.fulfill(
                            status=200,
                            content_type="application/json",
                            body='{"recorded":true,"diagnostic":{"message":"Session state unavailable.","correlation_id":"network-525"}}',
                        )

                    page.route("**/api/projects/diagnostics", report_route)
                    accepted = page.evaluate(
                        """async () => {
                          const { reportProjectDiagnostic } = await import('/src/project-diagnostic-report.ts');
                          return await reportProjectDiagnostic(
                            '/fixture/project.json', 'Session state unavailable.',
                            'session_read', 'network-525'
                          );
                        }"""
                    )
                    assert accepted["recorded"] is True
                    assert requests[0]["message"] == "Session state unavailable."
                    assert requests[0]["stage"] == "session_read"
                    page.unroute("**/api/projects/diagnostics", report_route)
                    page.route("**/api/projects/diagnostics", lambda route: route.abort("failed"))
                    unreachable = page.evaluate(
                        """async () => {
                          const { reportProjectDiagnostic } = await import('/src/project-diagnostic-report.ts');
                          return await reportProjectDiagnostic(
                            '/fixture/project.json', 'Session control failed offline.',
                            'session_control', 'offline-525'
                          );
                        }"""
                    )
                    assert unreachable["recorded"] is False
                    assert "not recorded" in unreachable["status"]
                    assert "offline-525" in unreachable["status"]
                    # Real failed deletion transport used by ResearchWorkspace:
                    # the visible alert and persisted export must agree.
                    deleted_message = "Session removal failed: stale project revision."
                    captured_error = {}

                    page.route(
                        "**/api/projects/research-sessions/session-525",
                        lambda route: route.fulfill(
                            status=409,
                            content_type="application/json",
                            body='{"error":"Session removal failed: stale project revision."}',
                        ),
                    )
                    page.unroute("**/api/projects/diagnostics")

                    def report_deletion(route):
                        captured_error.update(route.request.post_data_json)
                        route.fulfill(
                            status=200,
                            content_type="application/json",
                            body='{"recorded":true,"diagnostic":{"message":"Session removal failed: stale project revision.","code":"browser_request_failed","correlation_id":"delete-525"}}',
                        )

                    page.route("**/api/projects/diagnostics", report_deletion)
                    page.evaluate(
                        """async () => {
                          const host = document.createElement('div');
                          host.innerHTML = '<button id="delete-fixture">Remove saved session</button><p role="alert" id="delete-error"></p>';
                          document.body.appendChild(host);
                          const { removeResearchSession } = await import('/src/session-removal-request.ts');
                          const { reportProjectDiagnostic } = await import('/src/project-diagnostic-report.ts');
                          host.querySelector('button').addEventListener('click', async () => {
                            try {
                              await removeResearchSession('/fixture/project.json', 'session-525', 'stale-revision');
                            } catch (cause) {
                              const message = cause.message;
                              host.querySelector('#delete-error').textContent = message;
                              const reported = await reportProjectDiagnostic(
                                '/fixture/project.json', message, 'session_delete', 'delete-525'
                              );
                              if (reported.message) host.querySelector('#delete-error').textContent = reported.message;
                            }
                          });
                        }"""
                    )
                    with page.expect_response(
                        lambda response: (
                            "/api/projects/diagnostics" in response.url
                            and response.request.method == "POST"
                        )
                    ) as deletion_report:
                        page.get_by_role("button", name="Remove saved session").click()
                    assert deletion_report.value.ok
                    expect(page.locator("#delete-error")).to_have_text(deleted_message)
                    assert captured_error["message"] == deleted_message
                    assert captured_error["stage"] == "session_delete"
                    expect(panel).to_contain_text("reference_http_404")
                    browser.close()
            finally:
                process.terminate()
                try:
                    process.wait(timeout=10)
                except subprocess.TimeoutExpired:
                    process.kill()
                    process.wait()
    print("PASS: real Chromium project diagnostic display, no export controls, and reporting.")


if __name__ == "__main__":
    main()
