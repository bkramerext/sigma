"""Supervise the two localhost development servers as one foreground command."""

import os
import shutil
import signal
import socket
import subprocess
import sys
import time
from urllib.error import URLError
from urllib.request import urlopen

from sigma.projects import ROOT

URL = "http://127.0.0.1:5173"


def check_ports() -> None:
    for port in (8000, 5173):
        with socket.socket() as listener:
            listener.setsockopt(socket.SOL_SOCKET, socket.SO_REUSEADDR, 1)
            try:
                listener.bind(("127.0.0.1", port))
            except OSError as exc:
                raise RuntimeError(
                    f"Port {port} is unavailable. Stop the server using it and retry ./sigma ui."
                ) from exc


def stop_servers(children: list[subprocess.Popen[bytes]]) -> None:
    # Each child owns a process group so npm's Vite descendants also stop.
    for child in children:
        try:
            os.killpg(child.pid, signal.SIGTERM)
        except ProcessLookupError:
            pass
    for child in children:
        try:
            child.wait(timeout=5)
        except subprocess.TimeoutExpired:
            try:
                os.killpg(child.pid, signal.SIGKILL)
            except ProcessLookupError:
                pass
            child.wait()


def ready(url: str) -> bool:
    try:
        with urlopen(url, timeout=0.3) as response:
            return response.status == 200
    except (URLError, OSError):
        return False


def run_ui() -> int:
    if not (ROOT / "frontend/node_modules/vite").is_dir():
        print("UI dependencies are missing. Run ./sigma setup first.", file=sys.stderr)
        return 2
    if shutil.which("npm") is None:
        print("npm is missing. Install Node/npm, then run ./sigma setup.", file=sys.stderr)
        return 2
    children: list[subprocess.Popen[bytes]] = []

    def interrupted(signum: int, frame: object) -> None:
        raise KeyboardInterrupt

    previous = signal.signal(signal.SIGTERM, interrupted)
    try:
        check_ports()
        commands = [
            [
                sys.executable,
                "-m",
                "uvicorn",
                "sigma.api:app",
                "--host",
                "127.0.0.1",
                "--port",
                "8000",
            ],
            ["npm", "--prefix", "frontend", "run", "dev"],
        ]
        for command in commands:
            children.append(subprocess.Popen(command, cwd=ROOT, start_new_session=True))
        deadline = time.monotonic() + 30
        announced = False
        while True:
            for name, child in zip(("API", "frontend"), children, strict=True):
                code = child.poll()
                if code is not None:
                    raise RuntimeError(
                        f"{name} server exited (status {code}); stopping both servers."
                    )
            if not announced:
                if ready("http://127.0.0.1:8000/openapi.json") and ready(URL):
                    print(
                        f"\nSIGMA UI ready: {URL}\nPress Ctrl+C to stop both servers.\n", flush=True
                    )
                    announced = True
                elif time.monotonic() >= deadline:
                    raise RuntimeError("Servers did not become ready within 30 seconds.")
            time.sleep(0.2)
    except KeyboardInterrupt:
        print("\nStopping SIGMA UI…", flush=True)
        return 0
    except (OSError, RuntimeError) as exc:
        print(f"Cannot launch SIGMA UI: {exc}", file=sys.stderr)
        return 1
    finally:
        # Ignore repeated stop requests while cleaning up the process groups.
        prior_int = signal.signal(signal.SIGINT, signal.SIG_IGN)
        signal.signal(signal.SIGTERM, signal.SIG_IGN)
        try:
            stop_servers(children)
        finally:
            signal.signal(signal.SIGINT, prior_int)
            signal.signal(signal.SIGTERM, previous)
