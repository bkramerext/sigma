"""Supervise the two localhost development servers as one foreground command."""

import json
import os
import shutil
import signal
import socket
import subprocess
import sys
import time
import webbrowser
from urllib.error import URLError
from urllib.request import urlopen
from uuid import uuid4

from sigma.local_config import load_local_config
from sigma.projects import ROOT
from sigma.ui_instance import Instance

API_URL = "http://127.0.0.1:8000"
URL = "http://127.0.0.1:5173"


def check_ports() -> None:
    for port in (8000, 5173):
        with socket.socket() as listener:
            listener.setsockopt(socket.SOL_SOCKET, socket.SO_REUSEADDR, 1)
            try:
                listener.bind(("127.0.0.1", port))
            except OSError as exc:
                raise RuntimeError(
                    f"Port {port} is occupied by an unrelated or unverifiable service. "
                    "SIGMA cannot safely replace it. Close that service using its own controls, "
                    "then retry ./sigma ui. No process was signalled."
                ) from exc


def wait_for_ports() -> None:
    # A crashed owner's guardians may still be finishing bounded cleanup.
    deadline = time.monotonic() + 6
    while True:
        try:
            check_ports()
            return
        except RuntimeError:
            if time.monotonic() >= deadline:
                raise
            time.sleep(0.1)


def stop_servers(children: list[subprocess.Popen[bytes]]) -> None:
    # EOF is a capability held only by this parent. Guardians own and stop their
    # actual groups, so no supervisor signal ever depends on a recorded PID.
    for child in children:
        if child.stdin is not None:
            child.stdin.close()
    for child in children:
        try:
            child.wait(timeout=8)
        except subprocess.TimeoutExpired:
            raise RuntimeError(
                "Owned server did not confirm shutdown; refusing unsafe takeover."
            ) from None


def ready(url: str, instance_id: str | None = None) -> bool:
    try:
        with urlopen(url, timeout=0.3) as response:
            return response.status == 200 and (
                instance_id is None or json.loads(response.read(1024)) == {"instance": instance_id}
            )
    except (URLError, OSError, ValueError):
        return False


def run_ui() -> int:
    if not (ROOT / "frontend/node_modules/vite").is_dir():
        print("UI dependencies are missing. Run ./sigma setup first.", file=sys.stderr)
        return 2
    if shutil.which("npm") is None:
        print("npm is missing. Install Node/npm, then run ./sigma setup.", file=sys.stderr)
        return 2
    children: list[subprocess.Popen[bytes]] = []
    replacement: socket.socket | None = None

    def interrupted(signum: int, frame: object) -> None:
        raise KeyboardInterrupt

    previous = signal.signal(signal.SIGTERM, interrupted)
    try:
        load_local_config()
        with Instance() as instance:
            try:
                wait_for_ports()
                commands = [
                    [
                        sys.executable,
                        "-m",
                        "uvicorn",
                        "sigma.server:create_app",
                        "--factory",
                        "--host",
                        "127.0.0.1",
                        "--port",
                        "8000",
                    ],
                    ["npm", "--prefix", "frontend", "run", "dev"],
                ]
                instance_id = uuid4().hex
                child_env = {**os.environ, "SIGMA_UI_INSTANCE_ID": instance_id}
                for command in commands:
                    children.append(
                        subprocess.Popen(
                            [sys.executable, "-m", "sigma.ui_child", *command],
                            cwd=ROOT,
                            env={
                                key: value
                                for key, value in child_env.items()
                                if command[0] != "npm"
                                or key
                                not in {
                                    "OPENAI_API_KEY",
                                    "ACCESS_TOKEN",
                                    "REFRESH_TOKEN",
                                    "ID_TOKEN",
                                }
                            },
                            start_new_session=True,
                            stdin=subprocess.PIPE,
                        )
                    )
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
                        if (
                            ready(API_URL + "/api/ui-instance", instance_id)
                            and ready(URL + "/api/ui-instance", instance_id)
                            and ready(URL)
                        ):
                            print(
                                "\nSIGMA servers ready:\n"
                                f"  FastAPI API server: {API_URL}\n"
                                f"  Vite UI server:    {URL}\n"
                                "Press Ctrl+C to stop both servers.\n",
                                flush=True,
                            )
                            announced = True
                            instance.unlock()
                            try:
                                if not webbrowser.open(URL, new=2):
                                    print(f"Open {URL} in your browser.", flush=True)
                            except (OSError, webbrowser.Error):
                                print(f"Open {URL} in your browser.", flush=True)
                        elif time.monotonic() >= deadline:
                            raise RuntimeError("Servers did not become ready within 30 seconds.")
                    replacement = instance.replacement_request()
                    if replacement is not None:
                        break
                    time.sleep(0.1)
            finally:
                prior_int = signal.signal(signal.SIGINT, signal.SIG_IGN)
                signal.signal(signal.SIGTERM, signal.SIG_IGN)
                try:
                    stop_servers(list(children))
                    children.clear()
                finally:
                    signal.signal(signal.SIGINT, prior_int)
                    signal.signal(signal.SIGTERM, previous)
        if replacement is not None:
            replacement.sendall(
                (json.dumps({"identity": instance.identity, "status": "stopped"}) + "\n").encode()
            )
            replacement.close()
        return 0
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
            if children:
                stop_servers(children)
        finally:
            signal.signal(signal.SIGINT, prior_int)
            signal.signal(signal.SIGTERM, previous)
