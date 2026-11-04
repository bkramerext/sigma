"""Actual Chromium copy/download acceptance for Issue #525 project diagnostics."""
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
    export_body = (
        "# Project diagnostics\n\n"
        "Sanitized exportable errors (not the full append-only provider wire log).\n\n"
        "## 2026-11-03T20:00:00+00:00 · admission · reference_http_404\n"
        "Event ID: diagnostic-525\nSession ID: none (pre-session)\n"
        "Message: Source retrieval failed with HTTP 404.\n"
    )
    with tempfile.TemporaryDirectory(prefix="sigma-diagnostics-browser-") as temp:
        logfile = Path(temp) / "vite.log"
        with logfile.open("w") as output:
            process = subprocess.Popen(
                [
                    "npm", "--prefix", str(ROOT / "frontend"), "run", "dev",
                    "--", "--host", "127.0.0.1", "--port", str(port), "--strictPort",
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
                    context = browser.new_context(accept_downloads=True)
                    context.grant_permissions(["clipboard-read", "clipboard-write"])
                    page = context.new_page()
                    page.route(
                        "**/api/projects/diagnostics/download?**",
                        lambda route: route.fulfill(
                            status=200,
                            content_type="text/markdown",
                            body=export_body,
                            headers={
                                "Content-Disposition": 'attachment; filename="project-diagnostics.log"'
                            },
                        ),
                    )
                    page.goto(base, wait_until="domcontentloaded")
                    page.evaluate(
                        """async () => {
                          const React = (await import('/node_modules/.vite/deps/react.js')).default;
                          const { createRoot } = await import('/node_modules/.vite/deps/react-dom_client.js');
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
                    panel = page.get_by_role("region", name="Project diagnostics")
                    panel.locator("summary").click()
                    expect(panel).to_contain_text("pre-session")
                    expect(panel).to_contain_text("reference_http_404")
                    panel.get_by_role("button", name="Copy project diagnostics").click()
                    expect(panel.get_by_role("status")).to_contain_text("copied")
                    copied = page.evaluate("navigator.clipboard.readText()")
                    assert copied == export_body
                    with page.expect_download() as download:
                        panel.get_by_role("link", name="Download project diagnostics").click()
                    received = download.value
                    assert received.suggested_filename == "project-diagnostics.log"
                    assert Path(received.path()).read_text() == copied
                    browser.close()
            finally:
                process.terminate()
                try:
                    process.wait(timeout=10)
                except subprocess.TimeoutExpired:
                    process.kill()
                    process.wait()
    print("PASS: real Chromium project diagnostic display and exact copy/download parity.")


if __name__ == "__main__":
    main()
