"""End-to-end in-container security smoke without real provider credentials.

Invoked inside the one shared Docker service under worker UID 10001.
"""
from __future__ import annotations

import asyncio
import hmac
import http.client
import json
import os
import time
from pathlib import Path

from sigma import ai_store

A = "a" * 32
B = "b" * 32


def call(workspace: str, method: str, path: str, *, key_override: str | None = None):
    seed = bytes.fromhex(os.environ["SIGMA_AUTH_POC_RPC_SEED"])
    key = hmac.digest(seed, workspace.encode("ascii"), "sha256").hex()
    conn = http.client.HTTPConnection("127.0.0.1", 8001, timeout=30)
    try:
        conn.request(
            method, path, headers={
                "X-Sigma-Workspace": workspace,
                "X-Sigma-Worker-Key": key_override or key,
                "Content-Length": "0",
            },
        )
        resp = conn.getresponse()
        raw = resp.read(3000)
        try:
            obj = json.loads(raw)
        except ValueError:
            obj = {}
        return resp.status, obj
    finally:
        conn.close()


async def storage_check() -> None:
    root = Path(os.environ["SIGMA_PERSONAL_SHARED_WORKSPACES"])
    vault_root = Path(os.environ["SIGMA_PERSONAL_SHARED_RECORDS"])
    for workspace, marker in ((A, "A-UNIQUE"), (B, "B-UNIQUE")):
        directory = root / workspace
        directory.mkdir(mode=0o700, exist_ok=True)
        with ai_store.use_directory(directory):
            async with ai_store.transaction() as record:
                record["welcome_seen"] = marker
        sealed = (vault_root / (workspace + ".sealed")).read_bytes()
        assert marker.encode() not in sealed, "Plaintext leaked from encrypted account store"
        assert b"access_token" not in sealed
    for workspace, marker in ((A, "A-UNIQUE"), (B, "B-UNIQUE")):
        with ai_store.use_directory(root / workspace):
            async with ai_store.transaction() as record:
                assert record["welcome_seen"] == marker
    assert not (root / A / "credentials.json").exists()
    assert not (root / B / "credentials.json").exists()

    # AES authentication is necessary but not sufficient: a validly sealed
    # malformed record must fail closed, not silently replace a user's
    # stored account with an empty default.
    from sigma.personal_vault import Vault

    invalid_workspace = "c" * 32
    invalid_dir = root / invalid_workspace
    invalid_dir.mkdir(mode=0o700, exist_ok=True)
    vault = Vault(vault_root, Path(os.environ["SIGMA_PERSONAL_SHARED_KEY_FILE"]))
    vault.write(invalid_workspace, {})
    with ai_store.use_directory(invalid_dir):
        try:
            ai_store.read(invalid_dir / "credentials.json")
        except ValueError:
            pass
        else:
            raise AssertionError("Malformed encrypted account was silently accepted")


def assert_no_browser_processes() -> None:
    """Chromium, X11 and noVNC must not consume memory when the viewer is closed."""
    names = {"chromium", "chrome", "xvfb", "x11vnc", "websockify"}
    for _ in range(30):
        active: list[str] = []
        for entry in Path("/proc").iterdir():
            if not entry.name.isdecimal():
                continue
            try:
                name = (entry / "comm").read_text(encoding="utf-8").strip().lower()
                state = (entry / "stat").read_text(encoding="utf-8").split(") ", 1)[1][0]
            except (OSError, IndexError, UnicodeError):
                continue
            if state != "Z" and (name in names or name.startswith("chromium")):
                active.append(name)
        if not active:
            return
        time.sleep(0.2)
    raise AssertionError("Transient GUI processes remained after browser shutdown")


def main() -> None:
    assert os.geteuid() == 10001, "Vault test must not run as root"
    asyncio.run(storage_check())
    assert call(A, "GET", "/v1/account", key_override="0"*64)[0] == 403
    assert call(A, "GET", "/v1/account")[0] == 200
    assert call(B, "GET", "/v1/account")[0] == 200
    assert call(A, "GET", "/v1/browser/status")[1]["status"] == "stopped"
    assert_no_browser_processes()
    assert call(B, "GET", "/v1/browser/status")[1]["status"] == "stopped"
    try:
        status, result = call(A, "POST", "/v1/browser/start")
        assert status == 200 and result["status"] == "ready", (status, result)
        assert call(B, "POST", "/v1/browser/start")[0] == 409
        assert call(B, "GET", "/v1/browser/status")[1]["status"] == "stopped"
        assert call(B, "POST", "/v1/browser/password")[0] == 403
        assert call(B, "GET", "/v1/preview-state")[1] == {"phase": "unavailable"}
        assert call(A, "POST", "/v1/browser/password")[1]["status"] == "ready"
    finally:
        assert call(A, "POST", "/v1/browser/stop")[1]["status"] == "stopped"
    assert call(A, "GET", "/v1/browser/status")[1]["status"] == "stopped"
    assert_no_browser_processes()
    assert call(A, "GET", "/v1/account")[0] == 200
    assert not Path("/tmp/sigma-browser").exists(), "Closed browser retained its profile"
    # A closed login must not poison the next user's Chrome/X11 startup,
    # and the first user must never control the second user's browser.
    try:
        status, result = call(B, "POST", "/v1/browser/start")
        assert status == 200 and result["status"] == "ready", (status, result)
        assert call(A, "POST", "/v1/browser/start")[0] == 409
        assert call(A, "POST", "/v1/browser/password")[0] == 403
        assert call(B, "POST", "/v1/browser/password")[1]["status"] == "ready"
    finally:
        assert call(B, "POST", "/v1/browser/stop")[1]["status"] == "stopped"
    assert_no_browser_processes()
    assert not Path("/tmp/sigma-browser").exists()
    print("PASS shared worker, two encrypted users, sequential disposable browsers, no idle GUI")


if __name__ == "__main__":
    main()
