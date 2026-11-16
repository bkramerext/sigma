"""End-to-end in-container security smoke without real provider credentials.

Invoked inside the one shared Docker service under worker UID 10001.
"""
from __future__ import annotations

import asyncio
import hmac
import http.client
import json
import os
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


def main() -> None:
    assert os.geteuid() == 10001, "Vault test must not run as root"
    asyncio.run(storage_check())
    assert call(A, "GET", "/v1/account", key_override="0"*64)[0] == 403
    assert call(A, "GET", "/v1/account")[0] == 200
    assert call(B, "GET", "/v1/account")[0] == 200
    assert call(A, "GET", "/v1/browser/status")[1]["status"] == "stopped"
    assert call(B, "GET", "/v1/browser/status")[1]["status"] == "stopped"
    try:
        status, result = call(A, "POST", "/v1/browser/start")
        assert status == 200 and result["status"] == "ready", (status, result)
        assert call(B, "POST", "/v1/browser/start")[0] == 409
        assert call(B, "GET", "/v1/browser/status")[1]["status"] == "stopped"
        assert call(A, "POST", "/v1/browser/password")[1]["status"] == "ready"
    finally:
        assert call(A, "POST", "/v1/browser/stop")[1]["status"] == "stopped"
    assert call(A, "GET", "/v1/browser/status")[1]["status"] == "stopped"
    assert call(A, "GET", "/v1/account")[0] == 200
    print("PASS one shared worker, two encrypted users, one disposable browser, no idle GUI")


if __name__ == "__main__":
    main()
