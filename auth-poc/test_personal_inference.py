"""No-provider two-user routing test for the private Personal model RPC channel.

The worker's production model endpoint is blocked. This test substitutes only
an in-process synthetic Unix server; no OAuth account or OpenAI token is used.
"""

from __future__ import annotations

import asyncio
import json
import os
import tempfile
from pathlib import Path
from types import SimpleNamespace
from unittest.mock import patch

import httpx

from sigma import cloud_auth, cloud_workspaces, personal_browser, personal_inference
from sigma.model_catalog import DEFAULT_MODEL

A = "a" * 32
B = "b" * 32
BIND_A = "a" * 64
BIND_B = "b" * 64
MODEL = DEFAULT_MODEL


async def main() -> None:
    from model_gateway import app as worker_app

    # Even direct access to the real worker's RPC endpoint cannot infer.
    async with httpx.AsyncClient(
        transport=httpx.ASGITransport(app=worker_app), base_url="http://private-worker"
    ) as client:
        account = await client.get("/v1/account")
        assert account.status_code == 200
        assert account.json() == {
            "status": "disabled", "binding": None, "models": [], "account_label": None
        }
        request = {
            "request_id": "f" * 32,
            "expected_binding": BIND_A,
            "payload": {"model": MODEL, "store": False, "stream": True, "input": "test"},
        }
        blocked = await client.post("/v1/response", json=request)
        assert blocked.status_code == 403
        malformed = await client.post(
            "/v1/response", json={**request, "token": "MUST-NOT-ACCEPT"}
        )
        assert malformed.status_code == 422

    principal_a = cloud_auth.Principal("subject-a", "a@example.test", "member")
    principal_b = cloud_auth.Principal("subject-b", "b@example.test", "member")
    current = [principal_a]
    mode = ["personal"]
    statuses = {"subject-a": "verified", "subject-b": "verified"}
    calls: list[tuple[str, str]] = []

    with tempfile.TemporaryDirectory(prefix="sigma-personal-rpc-") as temp:
        root = Path(temp)
        root.chmod(0o711)
        paths = {}
        servers = []
        for name in (A, B):
            parent = root / name
            parent.mkdir(mode=0o700)
            paths[name] = parent / "model.sock"

        async def run_worker(identifier: str) -> None:
            binding = BIND_A if identifier == A else BIND_B
            subject = "subject-a" if identifier == A else "subject-b"
            label = "a@example.test" if identifier == A else "b@example.test"

            async def handle(reader: asyncio.StreamReader, writer: asyncio.StreamWriter) -> None:
                try:
                    head = await reader.readuntil(b"\r\n\r\n")
                    first = head.split(b"\r\n", 1)[0].decode("ascii")
                    method, target, _ = first.split()
                    length = 0
                    for line in head.decode().split("\r\n"):
                        if line.lower().startswith("content-length:"):
                            length = int(line.split(":", 1)[1].strip())
                    assert length < 256_000
                    data = (
                        json.loads(await reader.readexactly(length)) if length else None
                    )
                    if target == "/v1/account" and method == "GET":
                        result = (
                            {
                                "status": "verified",
                                "binding": binding,
                                "models": [MODEL],
                                "account_label": label,
                            }
                            if statuses[subject] == "verified"
                            else {
                                "status": "disabled",
                                "binding": None,
                                "models": [],
                                "account_label": None,
                            }
                        )
                        status_code = 200
                    elif target == "/v1/response" and method == "POST":
                        assert set(data) == {"expected_binding", "request_id", "payload"}
                        assert data["expected_binding"] == binding
                        assert data["payload"]["store"] is False
                        assert data["payload"]["stream"] is True
                        assert "token" not in data and "authorization" not in data
                        calls.append((subject, data["request_id"]))
                        result = {
                            "binding": binding,
                            "response": {
                                "status": "completed",
                                "model": MODEL,
                                "output": [{"type": "message", "content": [
                                    {"type": "output_text", "text": "synthetic " + subject}
                                ]}],
                            },
                        }
                        status_code = 200
                    else:
                        status_code = 404
                        result = {"status": "unavailable"}
                    body = json.dumps(result).encode()
                    writer.write(
                        ("HTTP/1.1 " + str(status_code) + " OK\r\n"
                         "Content-Type: application/json\r\nConnection: close\r\n"
                         "Content-Length: " + str(len(body)) + "\r\n\r\n").encode()
                        + body
                    )
                    await writer.drain()
                finally:
                    writer.close()
                    await writer.wait_closed()

            server = await asyncio.start_unix_server(handle, str(paths[identifier]))
            paths[identifier].chmod(0o600)
            servers.append(server)

        await run_worker(A)
        await run_worker(B)

        async def workspace_id(principal: cloud_auth.Principal) -> str:
            return A if principal.subject == "subject-a" else B

        try:
            with (
                patch.dict(os.environ, {"SIGMA_PERSONAL_BROWSER_GATEWAY_ROOT": str(root)}),
                patch.object(personal_browser, "_workspace_id", new=workspace_id),
                patch.object(personal_browser, "_socket", return_value="/test/broker.sock"),
                patch.object(cloud_auth, "current_principal", side_effect=lambda: current[0]),
                patch.object(
                    cloud_workspaces, "current",
                    side_effect=lambda: SimpleNamespace(
                        guest=False, verified_subject=current[0].subject
                    ),
                ),
                patch.object(cloud_auth, "model_access_for_subject", side_effect=lambda _: mode[0]),
            ):
                payload = {
                    "model": MODEL,
                    "store": False,
                    "stream": True,
                    "input": [{"role": "user", "content": "synthetic request"}],
                }
                a = await personal_inference.respond(
                    payload, expected_binding=BIND_A, request_id="1" * 32
                )
                assert a["output"][0]["content"][0]["text"] == "synthetic subject-a"
                current[0] = principal_b
                b = await personal_inference.respond(
                    payload, expected_binding=BIND_B, request_id="2" * 32
                )
                assert b["output"][0]["content"][0]["text"] == "synthetic subject-b"
                assert calls == [("subject-a", "1" * 32), ("subject-b", "2" * 32)]
                for binding in (BIND_A, "0" * 64):
                    try:
                        await personal_inference.respond(
                            payload, expected_binding=binding, request_id="3" * 32
                        )
                    except personal_inference.PersonalInferenceUnavailable:
                        pass
                    else:
                        raise AssertionError("Cross-user or stale binding accepted")
                assert len(calls) == 2
                mode[0] = "sponsored"
                try:
                    await personal_inference.respond(
                        payload, expected_binding=BIND_B, request_id="4" * 32
                    )
                except personal_inference.PersonalInferenceUnavailable:
                    pass
                else:
                    raise AssertionError("Sponsored user reached Personal worker")
                mode[0] = "personal"
                statuses["subject-b"] = "disabled"
                try:
                    await personal_inference.respond(
                        payload, expected_binding=BIND_B, request_id="5" * 32
                    )
                except personal_inference.PersonalInferenceUnavailable:
                    pass
                else:
                    raise AssertionError("Disconnected worker accepted inference")
                # A lost or mismatched Google context fails before any socket I/O.
                current[0] = principal_a
                with patch.object(
                    cloud_workspaces, "current",
                    return_value=SimpleNamespace(
                        guest=False, verified_subject="subject-b"
                    ),
                ):
                    try:
                        await personal_inference.respond(
                            payload, expected_binding=BIND_A, request_id="6" * 32
                        )
                    except personal_inference.PersonalInferenceUnavailable:
                        pass
                    else:
                        raise AssertionError("Mismatched SIGMA session reached worker")
                assert len(calls) == 2
        finally:
            for server in servers:
                server.close()
                await server.wait_closed()
    print("PASS: independent Personal RPC routes, opaque binding, no credentials, fail-closed live gate")


if __name__ == "__main__":
    asyncio.run(main())
