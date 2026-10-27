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
from pathlib import Path
from urllib.error import URLError
from urllib.request import urlopen
from uuid import uuid4

from sigma.local_config import load_local_config
from sigma.projects import ROOT
from sigma.ui_instance import Instance, stop_registered_instances
from sigma.ui_orphans import listener_details, recover_orphans

API_URL = "http://127.0.0.1:8000"
URL = "http://127.0.0.1:5173"


def check_ports() -> None:
    for port in (8000, 5173):
        with socket.socket() as listener:
            listener.setsockopt(socket.SOL_SOCKET, socket.SO_REUSEADDR, 1)
            try:
                listener.bind(("127.0.0.1", port))
            except OSError as exc:
                occupants = listener_details(port) or [
                    "PID unavailable (listener process details could not be read)"
                ]
                raise RuntimeError(
                    f"Port {port} is occupied by {', '.join(occupants)}. "
                    "SIGMA could not verify ownership and left it untouched. Stop it using its own controls, "
                    "then retry ./sigma start."
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


def local_google_configuration_warning() -> str | None:
    """Explain a partial local OAuth setup without reading or evaluating shell files."""
    has_client_setting = any(
        os.environ.get(key, "").strip()
        for key in ("GOOGLE_OIDC_CLIENT_ID", "GOOGLE_OIDC_CLIENT_SECRET")
    )
    if has_client_setting and not os.environ.get("SIGMA_CLOUD_ADMIN_CONTACT_EMAIL", "").strip():
        return (
            "Google OAuth client settings were found, but local Google sign-in is disabled "
            "because SIGMA_CLOUD_ADMIN_CONTACT_EMAIL is missing from this launch "
            "environment. Export the designated administrator's actual Gmail address before starting SIGMA; "
            "if it is in ~/.bashrc, run `source ~/.bashrc` in the launching shell, then "
            "restart with `./sigma start --nav`."
        )
    return None


def ready(url: str, instance_id: str | None = None) -> bool:
    try:
        with urlopen(url, timeout=0.3) as response:
            return response.status == 200 and (
                instance_id is None or json.loads(response.read(1024)) == {"instance": instance_id}
            )
    except (URLError, OSError, ValueError):
        return False


def run_ui(*, navigate: bool = False, signin: bool = False, mock_auth: bool = False) -> int:
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
        if signin and mock_auth:
            print("--signin and --mock-auth cannot be combined.", file=sys.stderr)
            return 2
        admin_email = os.environ.get("SIGMA_CLOUD_ADMIN_CONTACT_EMAIL", "").strip()
        if signin and not admin_email:
            print(
                "Cannot start SIGMA with --signin.\n\n"
                "SIGMA_CLOUD_ADMIN_CONTACT_EMAIL is not configured.\n"
                "Set it to your local SIGMA administrator email and retry.\n\n"
                'Example:\n  export SIGMA_CLOUD_ADMIN_CONTACT_EMAIL="you@gmail.com"\n'
                "  ./sigma start --signin --navigate",
                file=sys.stderr,
            )
            return 2
        print("Checking SIGMA UI instance and stopping any previous launcher…", flush=True)
        with Instance(register_owner=True) as instance:
            try:
                failures = stop_registered_instances(exclude_identity=instance.identity)
                if failures:
                    raise RuntimeError(" ".join(failures))
                if orphan_failures := recover_orphans():
                    raise RuntimeError(" ".join(orphan_failures))
                wait_for_ports()
                print("Starting SIGMA backend and frontend…", flush=True)
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
                child_env["SIGMA_CLOUD_AUTH_ENABLED"] = "true"
                child_env["SIGMA_CLOUD_AUTH_LOCAL"] = "true"
                child_env["SIGMA_CLOUD_PUBLIC_ORIGIN"] = URL
                child_env["SIGMA_LOCAL_AUTO_ADMIN"] = "true" if signin else "false"
                child_env["SIGMA_MOCK_AUTH"] = "1" if mock_auth else "0"
                child_env.setdefault(
                    "SIGMA_CLOUD_AUTH_HOME", str(Path.home() / ".sigma" / "local-cloud-auth")
                )
                for command in commands:
                    children.append(
                        subprocess.Popen(
                            [sys.executable, "-m", "sigma.ui_child", *command],
                            cwd=ROOT,
                            env={
                                key: value
                                for key, value in child_env.items()
                                if (
                                    command[0] != "npm"
                                    or key
                                    not in {
                                        "OPENAI_API_KEY",
                                        "ACCESS_TOKEN",
                                        "REFRESH_TOKEN",
                                        "ID_TOKEN",
                                        "GOOGLE_OIDC_CLIENT_SECRET",
                                        "SIGMA_CLOUD_AUTH_HOME",
                                        "SIGMA_CLOUD_ADMIN_CONTACT_EMAIL",
                                    }
                                )
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
                            if navigate:
                                try:
                                    if not webbrowser.open(URL, new=2):
                                        print(f"Open {URL} in your browser.", flush=True)
                                except (OSError, webbrowser.Error):
                                    print(f"Open {URL} in your browser.", flush=True)
                            else:
                                print(
                                    f"Use your existing browser tab at {URL} (reload if needed).",
                                    flush=True,
                                )
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


def run_shutdown() -> int:
    """Stop all verifiable local SIGMA UI instances; never start servers."""
    try:
        failures = stop_registered_instances()
        if orphan_failures := recover_orphans():
            failures.extend(orphan_failures)
        if failures:
            raise RuntimeError(" ".join(failures))
        print("SIGMA UI shutdown complete.", flush=True)
        return 0
    except (OSError, RuntimeError) as exc:
        print(f"Cannot shut down SIGMA UI: {exc}", file=sys.stderr)
        return 1
