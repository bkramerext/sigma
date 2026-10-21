"""Opt-in real-process launcher checks; requires free ports 8000/5173 and Node.

Run: uv run --with playwright python scenarios/ui_lifecycle.py
All checkouts/configuration/provider responses are disposable controlled fixtures.
"""

import hashlib
import json
import os
import shutil
import signal
import socket
import subprocess
import tempfile
import time
from pathlib import Path
from urllib.request import Request, urlopen

from sigma.projects import ROOT
from sigma.ui import check_ports
from sigma.ui_instance import Instance, identity

FIXTURE = """import os
try:
    import httpx
except ImportError:
    pass
else:
    real_client = httpx.AsyncClient
    def handler(request):
        assert request.method == "GET" and str(request.url) == "https://api.openai.com/v1/models"
        expected = {"Bearer launcher-fixture-one": "gpt-6.1-sol", "Bearer launcher-fixture-two": "gpt-6-luna"}
        model = expected.get(request.headers.get("Authorization"))
        assert model is not None
        with open(os.environ["SIGMA_FIXTURE_LOG"], "a") as stream:
            stream.write(model + "\\n")
        return httpx.Response(200, json={"object": "list", "data": [{"id": model}]})
    def client(**kwargs):
        return real_client(transport=httpx.MockTransport(handler), **kwargs)
    httpx.AsyncClient = client
"""


def until(predicate, timeout=35):
    deadline = time.monotonic() + timeout
    while time.monotonic() < deadline:
        if predicate():
            return
        time.sleep(0.1)
    raise AssertionError("Timed out waiting for isolated UI lifecycle fixture")


def process_table():
    data = subprocess.check_output(["ps", "-axo", "pid=,ppid=,pgid="], text=True)
    return [tuple(map(int, line.split())) for line in data.splitlines()]


def descendants(pid):
    result = {pid}
    for _ in range(10):
        result |= {child for child, parent, _ in process_table() if parent in result}
    return result - {pid}


def gone(pids):
    return not (pids & {pid for pid, _, _ in process_table()})


def get(path, origin=None):
    with urlopen(
        Request("http://127.0.0.1:5173" + path, headers={"Origin": origin} if origin else {})
    ) as response:
        return json.load(response)


def snapshot():
    return {
        str(p.relative_to(ROOT)): hashlib.sha256(p.read_bytes()).hexdigest()
        for p in (ROOT / "projects").rglob("*")
        if p.is_file()
    }


def main():
    check_ports()  # Refuse to disturb an existing service, including the developer UI.
    before = snapshot()
    with tempfile.TemporaryDirectory(prefix="sigma-launch-check-") as temporary:
        base = Path(temporary)
        root = base / "checkout"
        root.mkdir()
        for name in ("src", "frontend", "assets", "examples"):
            shutil.copytree(
                ROOT / name,
                root / name,
                ignore=shutil.ignore_patterns("node_modules", "dist", "__pycache__"),
            )
        (root / "frontend/node_modules").symlink_to(
            ROOT / "frontend/node_modules", target_is_directory=True
        )
        for name in ("sigma", "pyproject.toml", "uv.lock"):
            shutil.copy2(ROOT / name, root / name)
        (root / "projects").mkdir()
        (root / "projects/untouched.txt").write_text("research sentinel")
        fixtures = base / "fixtures"
        fixtures.mkdir()
        (fixtures / "sitecustomize.py").write_text(FIXTURE)
        env = {
            key: value
            for key, value in os.environ.items()
            if not key.startswith(("OPENAI_", "SIGMA_", "UV_"))
            and key not in {"VIRTUAL_ENV", "PYTHONPATH"}
        }
        env.update(
            PYTHONPATH=str(fixtures),
            SIGMA_FIXTURE_LOG=str(base / "provider.log"),
            SIGMA_AUTH_HOME=str(base / "auth"),
            SIGMA_STATE_DIR=str(base / "state"),
        )
        subprocess.run(
            ["uv", "sync", "--locked", "--project", str(root)],
            env=env,
            check=True,
            stdout=subprocess.DEVNULL,
            stderr=subprocess.DEVNULL,
        )
        processes = []
        logs = []

        def configure(key):
            (root / ".env").write_text(
                f'export OPENAI_API_KEY="{key}"\nexport SIGMA_AI_ENABLED=1\n'
            )

        def launch(checkout=root, direct=False):
            log = base / f"launch-{len(processes)}.log"
            stream = log.open("w")
            command = (
                [str(root / ".venv/bin/sigma"), "ui"] if direct else [str(checkout / "sigma"), "ui"]
            )
            proc = subprocess.Popen(
                command, cwd=base, env=env, stdout=stream, stderr=stream, start_new_session=True
            )
            stream.close()
            processes.append(proc)
            logs.append(log)
            return proc, log

        def ready(proc, log):
            until(lambda: "SIGMA servers ready:" in log.read_text() or proc.poll() is not None)
            assert proc.poll() is None, log.read_text()

        def stop(proc, sig=signal.SIGINT):
            proc.send_signal(sig)
            assert proc.wait(timeout=15) == 0

        try:
            configure("launcher-fixture-one")
            first, log1 = launch()
            ready(first, log1)
            old_children = descendants(first.pid)
            # A8.2: merely configuring a key no longer selects separate billing.
            assert get("/api/ai/connection")["status"] == "disconnected"
            with urlopen(
                Request(
                    "http://127.0.0.1:5173/api/ai/mode",
                    data=b'{"mode":"api_key"}',
                    headers={"Origin": "http://127.0.0.1:5173", "Content-Type": "application/json"},
                )
            ) as selected:
                assert selected.status == 200
            assert get("/api/ai/connection")["status"] == "connected"
            assert get("/api/ai/models")["default_model"] == "gpt-6.1-sol"
            configure("launcher-fixture-two")
            second, log2 = launch()
            ready(second, log2)
            assert first.wait(timeout=10) == 0
            until(lambda: gone(old_children))
            assert "Stopping existing SIGMA instance" in log2.read_text()
            assert get("/api/ai/models")["default_model"] == "gpt-6-luna"
            assert get("/api/ai/connection", "http://127.0.0.1:5173")["status"] == "connected"
            from urllib.error import HTTPError

            try:
                get("/api/ai/connection", "https://unrelated.example")
                raise AssertionError("Untrusted origin accepted")
            except HTTPError as error:
                assert error.code == 403
            from playwright.sync_api import expect, sync_playwright  # pyright: ignore[reportMissingImports]

            with sync_playwright() as playwright:
                browser = playwright.chromium.launch(
                    executable_path="/Applications/Google Chrome.app/Contents/MacOS/Google Chrome",
                    headless=True,
                )
                page = browser.new_page()
                page.goto("http://127.0.0.1:5173/")
                expect(page.get_by_text("OpenAI API · key billing", exact=True)).to_be_visible()
                page.get_by_role("button", name="New Project", exact=True).click()
                expect(
                    page.get_by_role("dialog").get_by_role(
                        "heading", name="New Project", exact=True
                    )
                ).to_be_visible()
                browser.close()
            children2 = descendants(second.pid)
            stop(second)
            until(lambda: gone(children2))
            check_ports()
            print(
                "PASS fresh-shell ./sigma ui, quoted export dotenv reload, verified fixture status/proxy/origin, Chrome, old owner/groups gone and Ctrl+C cleanup"
            )

            # A launcher suspended with Ctrl+Z/SIGSTOP must be resumed and
            # safely replaced without manual PID cleanup.
            suspended, suspendedlog = launch(direct=True)
            ready(suspended, suspendedlog)
            os.kill(suspended.pid, signal.SIGSTOP)
            replacement, replacementlog = launch()
            ready(replacement, replacementlog)
            until(lambda: suspended.poll() is not None)
            assert "Cleaning up 1 suspended SIGMA launcher" in replacementlog.read_text()
            assert "Stopping existing SIGMA instance" in replacementlog.read_text()
            # Explicit shutdown uses the same verified control channel.
            command = subprocess.run(
                [str(root / ".venv/bin/sigma"), "shutdown"],
                check=False,
                cwd=base,
                env=env,
                capture_output=True,
                text=True,
                timeout=20,
            )
            assert command.returncode == 0, command.stderr
            assert "shutdown complete" in command.stdout
            until(lambda: replacement.poll() is not None)
            check_ports()
            print("PASS suspended-launcher recovery and explicit sigma shutdown")

            # A different canonical checkout must never replace this one's instance.
            owner, ownerlog = launch(direct=True)
            ready(owner, ownerlog)
            other = base / "different-checkout"
            other.mkdir()
            for name in ("sigma", "pyproject.toml", "uv.lock"):
                shutil.copy2(root / name, other / name)
            shutil.copytree(root / "src", other / "src")
            (other / "frontend").symlink_to(root / "frontend", target_is_directory=True)
            subprocess.run(
                ["uv", "sync", "--locked", "--project", str(other)],
                env=env,
                check=True,
                stdout=subprocess.DEVNULL,
                stderr=subprocess.DEVNULL,
            )
            conflict, conflictlog = launch(other)
            assert conflict.wait(timeout=20) == 1
            assert "cannot safely replace" in conflictlog.read_text()
            assert owner.poll() is None and get("/api/ai/connection")["status"] == "connected"
            stop(owner, signal.SIGTERM)
            for port in (8000, 5173):
                with socket.socket() as listener:
                    listener.setsockopt(socket.SOL_SOCKET, socket.SO_REUSEADDR, 1)
                    listener.bind(("127.0.0.1", port))
                    listener.listen()
                    conflict, conflictlog = launch()
                    assert conflict.wait(timeout=20) == 1
                    assert f"Port {port}" in conflictlog.read_text()
                    assert listener.getsockname()[1] == port  # Our process/listener survived.
            print(
                "PASS different checkout and unrelated listeners survive safe conflicts; SIGTERM cleanup"
            )

            # Hard-kill only our own directly launched supervisor. Pipe EOF owns cleanup.
            crashed, crashlog = launch(direct=True)
            ready(crashed, crashlog)
            crashed_children = descendants(crashed.pid)
            crashed.kill()
            crashed.wait(timeout=5)
            recovered, recoveredlog = launch()
            ready(recovered, recoveredlog)
            until(lambda: gone(crashed_children))
            stop(recovered)
            # Both fresh invocations overlap; serialized replacement leaves one owner.
            rapid1, rapidlog1 = launch()
            rapid2, rapidlog2 = launch()
            until(
                lambda: (
                    sum("SIGMA servers ready:" in log.read_text() for log in (rapidlog1, rapidlog2))
                    == 2
                )
            )
            until(lambda: (rapid1.poll() is None) != (rapid2.poll() is None))
            survivor = rapid1 if rapid1.poll() is None else rapid2
            assert get("/api/ai/connection")["status"] == "connected"
            stop(survivor)
            check_ports()
            print(
                "PASS SIGKILL crash/stale socket recovery, pipe-guardian cleanup and rapid simultaneous launches"
            )
            assert (root / "projects/untouched.txt").read_text() == "research sentinel"
            for log in logs:
                assert (
                    "launcher-fixture-one" not in log.read_text()
                    and "launcher-fixture-two" not in log.read_text()
                )
            assert set((base / "provider.log").read_text().splitlines()) == {
                "gpt-6.1-sol",
                "gpt-6-luna",
            }
        finally:
            for proc in reversed(processes):
                if proc.poll() is None:
                    proc.terminate()
                    proc.wait(timeout=20)
            # Remove only these disposable checkout records, once all owned processes stopped.
            for checkout in (root, base / "different-checkout"):
                if checkout.exists():
                    state = Instance(checkout).directory
                    assert state.name == identity(checkout)[:24]
                    shutil.rmtree(state)
    assert snapshot() == before
    print("PASS no key output, provider fixture GET-only, no project changes")


if __name__ == "__main__":
    main()
