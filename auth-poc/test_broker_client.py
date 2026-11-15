"""Synthetic, real Unix-socket tests for the SIGMA user-bound browser client."""

from __future__ import annotations

import asyncio
import json
import os
import tempfile
from pathlib import Path
from types import SimpleNamespace
from urllib.parse import parse_qs, urlsplit
from unittest.mock import patch

from sigma import cloud_auth, cloud_workspaces, personal_browser

A = "a" * 32
B = "b" * 32


async def main() -> None:
    sessions: dict[str, str] = {}
    requests: list[tuple[str, str]] = []
    wrong_worker = False

    async def handle(reader: asyncio.StreamReader, writer: asyncio.StreamWriter) -> None:
        nonlocal wrong_worker
        try:
            head = await asyncio.wait_for(reader.readuntil(b"\r\n\r\n"), 4)
            first = head.split(b"\r\n", 1)[0].decode("ascii")
            method, target, _version = first.split(" ")
            headers = {}
            for line in head.decode().split("\r\n")[1:]:
                if ":" in line:
                    key, value = line.split(":", 1)
                    headers[key.lower()] = value.strip()
            if method == "GET":
                assert urlsplit(target).path == "/v1/status"
                workspace_id = parse_qs(urlsplit(target).query)["workspace_id"][0]
                action = "status"
            else:
                length = int(headers["content-length"])
                payload = json.loads(await reader.readexactly(length))
                assert set(payload) == {"workspace_id"}, "No caller-supplied path or host"
                workspace_id = payload["workspace_id"]
                action = target.removeprefix("/v1/")
                if action == "start":
                    sessions[workspace_id] = "ready"
                elif action == "stop":
                    sessions[workspace_id] = "stopped"
                else:
                    raise AssertionError("Unknown supervisor action")
            requests.append((action, workspace_id))
            body = json.dumps({
                "status": sessions.get(workspace_id, "stopped"),
                "worker": ("sigma-personal-" + B if wrong_worker else
                           "sigma-personal-" + workspace_id),
            }).encode()
            writer.write(
                b"HTTP/1.1 200 OK\r\nContent-Type: application/json\r\n"
                + b"Connection: close\r\nContent-Length: "
                + str(len(body)).encode() + b"\r\n\r\n" + body
            )
            await writer.drain()
        finally:
            writer.close()
            await writer.wait_closed()

    with tempfile.TemporaryDirectory(prefix="sigma-browser-uds-") as directory:
        socket_path = str(Path(directory) / "broker.sock")
        with patch.dict(os.environ, {
            "SIGMA_PERSONAL_BROWSER_LAB_ENABLED": "1",
            "SIGMA_PERSONAL_BROWSER_BROKER_SOCKET": socket_path,
            "SIGMA_AUTH_POC_REAL_SIGNIN": "0",
        }):
            with patch.object(cloud_auth, "config", return_value=SimpleNamespace(enabled=True)):
                with patch.object(
                    cloud_workspaces, "workspace_for_subject",
                    side_effect=lambda subject: SimpleNamespace(
                        workspace_id=A if subject == "test-user-a" else B
                    ),
                ):
                    async with await asyncio.start_unix_server(handle, socket_path):
                        os.chmod(socket_path, 0o600)
                        user_a = cloud_auth.Principal("test-user-a", "a@example.test", "member")
                        user_b = cloud_auth.Principal("test-user-b", "b@example.test", "member")
                        assert (await personal_browser.session(user_a, "start"))[
                            "browser_status"
                        ] == "ready"
                        assert (await personal_browser.session(user_b, "start"))[
                            "browser_status"
                        ] == "ready"
                        assert (await personal_browser.session(user_a, "stop"))[
                            "browser_status"
                        ] == "stopped"
                        assert (await personal_browser.session(user_b))[
                            "browser_status"
                        ] == "ready"
                        assert requests == [
                            ("start", A), ("start", B), ("stop", A), ("status", B)
                        ]
                        try:
                            await personal_browser.session(
                                cloud_auth.Principal("mock:unsafe", "fake@example.test", "member"),
                                "start",
                            )
                        except PermissionError:
                            pass
                        else:
                            raise AssertionError("Mock identity was authorized")
                        try:
                            await personal_browser.session(
                                cloud_auth.Principal("guest", "guest@example.test", "guest"),
                                "start",
                            )
                        except PermissionError:
                            pass
                        else:
                            raise AssertionError("Guest controlled containers")
                        wrong_worker = True
                        try:
                            await personal_browser.session(user_a)
                        except personal_browser.PersonalBrowserUnavailable:
                            pass
                        else:
                            raise AssertionError("Mismatched browser worker accepted")
                        with patch.dict(os.environ, {"SIGMA_AUTH_POC_REAL_SIGNIN": "1"}):
                            try:
                                await personal_browser.session(user_a)
                            except personal_browser.PersonalBrowserUnavailable:
                                pass
                            else:
                                raise AssertionError("Real OAuth guard was bypassed")
    print("PASS authenticated-user Unix broker binding, cross-user isolation and guards")


if __name__ == "__main__":
    asyncio.run(main())
