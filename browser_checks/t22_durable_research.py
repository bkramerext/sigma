"""Real Chrome disconnect and server-kill recovery with deterministic provider."""

from __future__ import annotations

import os
import socket
import subprocess
import time
from pathlib import Path
from tempfile import TemporaryDirectory
from uuid import uuid4

import httpx
from playwright.sync_api import sync_playwright

ROOT = Path(__file__).resolve().parents[1]


def free_port() -> int:
    with socket.socket() as sock:
        sock.bind(("127.0.0.1", 0))
        return int(sock.getsockname()[1])


def wait_for(url: str, process: subprocess.Popen, log: Path) -> None:
    deadline = time.monotonic() + 20
    while time.monotonic() < deadline and process.poll() is None:
        try:
            if httpx.get(url, timeout=0.5).status_code < 500:
                return
        except httpx.HTTPError:
            time.sleep(0.1)
    raise RuntimeError(f"Fixture server failed to start:\n{log.read_text(errors='replace')}")


def main() -> None:
    port = free_port()
    api_url = f"http://127.0.0.1:{port}"
    api_process: subprocess.Popen | None = None
    with TemporaryDirectory(prefix="sigma-t22-durable-browser-") as temporary:
        root = Path(temporary)
        root.chmod(0o700)
        env = os.environ.copy()
        env.update(
            {
                "SIGMA_CLOUD_AUTH_ENABLED": "true",
                "SIGMA_CLOUD_PUBLIC_ORIGIN": api_url,
                "SIGMA_CLOUD_WORKSPACES_ROOT": str(root / "workspaces"),
                "SIGMA_PROJECTS_ROOT": str(root / "local-projects"),
                "SIGMA_STATE_DIR": str(root / "local-state"),
                "SIGMA_CLOUD_OPENAI_API_KEY": "deterministic-browser-fixture",
                "SIGMA_CLOUD_GLOBAL_SPEND_CEILING_USD": "1.00",
                "SIGMA_CLOUD_USER_MAX_CONCURRENT": "1",
                "SIGMA_CLOUD_GLOBAL_MAX_CONCURRENT": "2",
                "SIGMA_CLOUD_USER_MAX_QUEUED": "2",
                "SIGMA_CLOUD_GLOBAL_MAX_QUEUED": "4",
                "SIGMA_CLOUD_USER_TOKEN_BUDGET": "1000000",
                "SIGMA_CLOUD_TEST_DISPATCH_LOG": str(root / "dispatches.txt"),
                "PYTHONPATH": os.pathsep.join(
                    (str(ROOT / "tests"), str(ROOT / "src"), os.environ.get("PYTHONPATH", ""))
                ),
            }
        )
        log_path = root / "api.log"

        def start_server(log_file) -> subprocess.Popen:
            process = subprocess.Popen(
                [
                    os.environ.get("SIGMA_PYTHON", str(ROOT / ".venv/bin/python")),
                    "-m",
                    "uvicorn",
                    "cloud_research_browser_app:app",
                    "--host",
                    "127.0.0.1",
                    "--port",
                    str(port),
                    "--log-level",
                    "error",
                ],
                cwd=ROOT,
                env=env,
                stdout=log_file,
                stderr=subprocess.STDOUT,
            )
            wait_for(f"{api_url}/api/ui-instance", process, log_path)
            return process

        with log_path.open("w") as log_file:
            api_process = start_server(log_file)
            try:
                with sync_playwright() as playwright:
                    browser = playwright.chromium.launch(
                        executable_path=os.environ.get(
                            "SIGMA_BROWSER_EXECUTABLE",
                            "/Applications/Google Chrome.app/Contents/MacOS/Google Chrome",
                        ),
                        headless=True,
                    )
                    try:
                        user_a = browser.new_context(
                            extra_http_headers={"X-Test-Subject": "durable-a"}
                        )
                        page_a = user_a.new_page()
                        page_a.goto(f"{api_url}/docs", wait_until="domcontentloaded")
                        made = page_a.evaluate(
                            """async () => {
                              const r = await fetch('/api/projects/create', {method:'POST',
                                headers:{'Content-Type':'application/json'},
                                body:JSON.stringify({title:'Durable research', problem:'Check a recurrence'})});
                              return {status:r.status, body:await r.json()};
                            }"""
                        )
                        assert made["status"] == 201, made
                        path = made["body"]["path"]
                        project_id = made["body"]["project"]["id"]
                        strategy_response = page_a.evaluate(
                            """async path => {
                              const r = await fetch('/api/projects/strategies', {method:'POST',
                                headers:{'Content-Type':'application/json'},
                                body:JSON.stringify({path, title:'Induction', approach:'Check the base case.'})});
                              return {status:r.status, body:await r.json()};
                            }""",
                            path,
                        )
                        assert strategy_response["status"] == 201, strategy_response
                        strategies = page_a.evaluate(
                            """async path => (await (await fetch('/api/projects/strategies?path=' +
                              encodeURIComponent(path))).json()).strategies""",
                            path,
                        )
                        strategy_id = strategies[0]["id"]
                        limits = {
                            "research_rounds": 1,
                            "model_calls": 2,
                            "session_duration_minutes": 5,
                            "output_tokens_per_call": 256,
                            "maximum_estimated_cost_usd": 1.0,
                        }
                        saved_limits = page_a.evaluate(
                            """async ({path, limits}) => {
                              const r = await fetch('/api/projects/research-limits', {method:'PUT',
                                headers:{'Content-Type':'application/json'}, body:JSON.stringify({path,...limits})});
                              return {status:r.status, body:await r.json()};
                            }""",
                            {"path": path, "limits": limits},
                        )
                        assert saved_limits["status"] == 200, saved_limits
                        start = {
                            "path": path,
                            "strategy_id": strategy_id,
                            "idempotency_key": str(uuid4()),
                            "expected_project_id": project_id,
                            "expected_binding": "cloud_service_api_key",
                            "expected_limits": limits,
                        }
                        started = page_a.evaluate(
                            """async body => {
                              const r = await fetch('/api/projects/research-sessions/start', {method:'POST',
                                headers:{'Content-Type':'application/json'}, body:JSON.stringify(body)});
                              return {status:r.status, body:await r.json()};
                            }""",
                            start,
                        )
                        assert started["status"] == 200, started
                        session_id = started["body"]["id"]
                        marker = root / "dispatches.txt"
                        deadline = time.monotonic() + 10
                        while time.monotonic() < deadline and not marker.exists():
                            time.sleep(0.05)
                        assert marker.exists(), "fake provider was not dispatched"
                        assert len(marker.read_text().splitlines()) == 1

                        # Closing this browser context must not end the saved job.
                        user_a.close()
                        user_b = browser.new_context(
                            extra_http_headers={"X-Test-Subject": "durable-b"}
                        )
                        try:
                            page_b = user_b.new_page()
                            page_b.goto(f"{api_url}/docs", wait_until="domcontentloaded")
                            denied = page_b.evaluate(
                                """async ({path, id}) => {
                                  const r = await fetch('/api/projects/research-sessions/' + id +
                                    '?path=' + encodeURIComponent(path));
                                  return r.status;
                                }""",
                                {"path": path, "id": session_id},
                            )
                            assert denied == 404, denied
                        finally:
                            user_b.close()

                        # Hard kill leaves the call at its durable reservation
                        # boundary. Restart and owner reconnect must report it
                        # as unknown/interrupted, with exactly one dispatch.
                        api_process.kill()
                        api_process.wait(timeout=10)
                        with log_path.open("a") as restarted_log:
                            api_process = start_server(restarted_log)
                            context = browser.new_context(
                                extra_http_headers={"X-Test-Subject": "durable-a"}
                            )
                            try:
                                page = context.new_page()
                                page.goto(f"{api_url}/docs", wait_until="domcontentloaded")
                                recovered = page.evaluate(
                                    """async ({path, id}) => {
                                      const r = await fetch('/api/projects/research-sessions/' + id +
                                        '?path=' + encodeURIComponent(path));
                                      return {status:r.status, body:await r.json()};
                                    }""",
                                    {"path": path, "id": session_id},
                                )
                                assert recovered["status"] == 200, recovered
                                assert recovered["body"]["status"] == "paused", recovered
                                assert recovered["body"]["steps"][0]["attempt_status"] == "unknown"
                                assert len(marker.read_text().splitlines()) == 1
                                duplicate = page.evaluate(
                                    """async body => {
                                      const r = await fetch('/api/projects/research-sessions/start', {method:'POST',
                                        headers:{'Content-Type':'application/json'}, body:JSON.stringify(body)});
                                      return {status:r.status, body:await r.json()};
                                    }""",
                                    start,
                                )
                                assert duplicate["status"] == 200, duplicate
                                assert duplicate["body"]["id"] == session_id
                                assert len(marker.read_text().splitlines()) == 1
                            finally:
                                context.close()
                    finally:
                        browser.close()
            finally:
                if api_process is not None and api_process.poll() is None:
                    api_process.terminate()
                    api_process.wait(timeout=10)
    print(
        "PASS Chrome disconnect, cross-user denial, hard backend restart, unknown attempt recovery and duplicate-start suppression"
    )


if __name__ == "__main__":
    main()
