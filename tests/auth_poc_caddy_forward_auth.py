"""Exercise the preview Caddy route against credential-free local fixtures."""

from __future__ import annotations

import base64
import hashlib
import http.server
import os
import socket
import subprocess
import tempfile
import threading
import time
import urllib.error
import urllib.request
import uuid
from pathlib import Path
from typing import ClassVar

ROOT = Path(__file__).resolve().parents[1]
EDGE = "ci-edge-key-" + "x" * 40
AUTH_GRANTS_BODY = b"PRIVATE_ADMIN_GRANTS_MUST_NOT_LEAK"


class FixtureHandler(http.server.BaseHTTPRequestHandler):
    protocol_version = "HTTP/1.1"
    auth_records: ClassVar[list[tuple[str, str]]] = []
    preview_records: ClassVar[list[dict[str, str]]] = []

    def log_message(self, format: str, *args: object) -> None:
        pass

    def do_GET(self) -> None:
        if self.path == "/api/cloud-auth/admin/grants":
            cookie = self.headers.get("Cookie", "")
            self.auth_records.append((self.path, cookie))
            if cookie != "sigma_admin=ok":
                body = b"Admin authentication required."
                self.send_response(401)
            else:
                body = AUTH_GRANTS_BODY
                self.send_response(200)
            self.send_header("Content-Length", str(len(body)))
            self.send_header("Content-Type", "application/json")
            self.end_headers()
            self.wfile.write(body)
            return

        self.preview_records.append(dict(self.headers.items()))
        if self.headers.get("Upgrade", "").lower() == "websocket":
            key = self.headers.get("Sec-WebSocket-Key", "")
            accepted = base64.b64encode(
                hashlib.sha1(
                    (key + "258EAFA5-E914-47DA-95CA-C5AB0DC85B11").encode("ascii")
                ).digest()
            ).decode("ascii")
            self.send_response(101, "Switching Protocols")
            self.send_header("Upgrade", "websocket")
            self.send_header("Connection", "Upgrade")
            self.send_header("Sec-WebSocket-Accept", accepted)
            self.end_headers()
            return
        body = b"PRIVATE_PREVIEW_OK"
        self.send_response(200)
        self.send_header("Content-Length", str(len(body)))
        self.end_headers()
        self.wfile.write(body)


def _fixture_server() -> tuple[http.server.ThreadingHTTPServer, threading.Thread, int]:
    server = http.server.ThreadingHTTPServer(("0.0.0.0", 0), FixtureHandler)
    thread = threading.Thread(target=server.serve_forever, daemon=True)
    thread.start()
    return server, thread, server.server_address[1]


def _assert_http(url: str, *, headers: dict[str, str] | None = None, expected: int) -> bytes:
    request = urllib.request.Request(url, headers=headers or {})
    try:
        response = urllib.request.urlopen(request, timeout=4)
    except urllib.error.HTTPError as error:
        assert error.code == expected, (error.code, error.read())
        return error.read()
    with response:
        assert response.status == expected, response.status
        return response.read()


def main() -> None:
    FixtureHandler.auth_records = []
    FixtureHandler.preview_records = []
    auth, _auth_thread, fixture_port = _fixture_server()
    preview, _preview_thread, preview_port = _fixture_server()
    caddy_name = "sigma-preview-fixture-" + uuid.uuid4().hex[:10]
    with tempfile.TemporaryDirectory(prefix="sigma-preview-caddy-") as directory:
        temp = Path(directory)
        snippet = (ROOT / "deploy/auth-poc.preview.caddy").read_text(encoding="utf-8")
        snippet = snippet.replace("backend:8000", f"host.docker.internal:{fixture_port}")
        snippet = snippet.replace(
            "sigma-personal-lab-preview:8002", f"host.docker.internal:{preview_port}"
        )
        (temp / "Caddyfile").write_text(
            ":8080 {\n"
            + snippet
            + "\n@api path /api /api/*\nhandle @api {\nrespond production-api 200\n}\n}\n",
            encoding="utf-8",
        )
        command = [
            "docker",
            "run",
            "--detach",
            "--rm",
            "--name",
            caddy_name,
            "--publish",
            "127.0.0.1::8080",
            "--add-host",
            "host.docker.internal:host-gateway",
            "--env",
            "SIGMA_PERSONAL_LAB_EDGE_KEY=" + EDGE,
            "--volume",
            f"{temp / 'Caddyfile'}:/etc/caddy/Caddyfile:ro",
            "caddy:2.9.1-alpine",
        ]
        try:
            subprocess.run(command, check=True, capture_output=True, text=True, timeout=30)
            mapping = subprocess.run(
                ["docker", "port", caddy_name, "8080/tcp"],
                check=True,
                capture_output=True,
                text=True,
                timeout=10,
            ).stdout.strip()
            port = int(mapping.rsplit(":", 1)[1])
            base = f"http://127.0.0.1:{port}"
            for _ in range(80):
                try:
                    with socket.create_connection(("127.0.0.1", port), timeout=1):
                        pass
                except OSError:
                    time.sleep(0.25)
                else:
                    break
            else:
                raise AssertionError("Caddy fixture did not become ready")

            _assert_http(base + "/__personal_lab__/", expected=401)
            assert not FixtureHandler.preview_records, "Unauthenticated request reached preview"
            assert (
                _assert_http(
                    base + "/__personal_lab__/",
                    headers={"Cookie": "sigma_admin=ok", "Authorization": "Bearer private"},
                    expected=200,
                )
                == b"PRIVATE_PREVIEW_OK"
            )
            seen = FixtureHandler.preview_records[-1]
            normalized = {name.lower(): value for name, value in seen.items()}
            assert "cookie" not in normalized, normalized
            assert "authorization" not in normalized, normalized
            assert normalized.get("x-sigma-personal-lab-edge") == EDGE, normalized
            assert AUTH_GRANTS_BODY.decode() not in str(seen)

            before = len(FixtureHandler.preview_records)
            _assert_http(
                base + "/__personal_lab__/ws",
                headers={"Upgrade": "websocket", "Connection": "Upgrade"},
                expected=401,
            )
            assert len(FixtureHandler.preview_records) == before

            key = base64.b64encode(os.urandom(16)).decode("ascii")
            with socket.create_connection(("127.0.0.1", port), timeout=4) as client:
                client.sendall(
                    (
                        "GET /__personal_lab__/ws HTTP/1.1\r\n"
                        f"Host: 127.0.0.1:{port}\r\n"
                        "Cookie: sigma_admin=ok\r\n"
                        "Authorization: Bearer private\r\n"
                        "Upgrade: websocket\r\n"
                        "Connection: Upgrade\r\n"
                        f"Sec-WebSocket-Key: {key}\r\n"
                        "Sec-WebSocket-Version: 13\r\n\r\n"
                    ).encode("ascii")
                )
                handshake = client.recv(2048)
                assert b"101 Switching Protocols" in handshake, handshake
            ws_headers = {
                name.lower(): value for name, value in FixtureHandler.preview_records[-1].items()
            }
            assert "cookie" not in ws_headers and "authorization" not in ws_headers, ws_headers
            assert ws_headers.get("x-sigma-personal-lab-edge") == EDGE, ws_headers

            assert _assert_http(base + "/api/status", expected=200) == b"production-api"
            assert FixtureHandler.auth_records[0] == ("/api/cloud-auth/admin/grants", "")
            assert FixtureHandler.auth_records[1] == (
                "/api/cloud-auth/admin/grants",
                "sigma_admin=ok",
            )
            assert AUTH_GRANTS_BODY.decode() not in "".join(
                str(record) for record in FixtureHandler.preview_records
            )
            print(
                "PASS live Caddy admin gate, HTTP/WebSocket credential stripping, hidden grants, and API isolation"
            )
        finally:
            subprocess.run(
                ["docker", "stop", caddy_name], check=False, capture_output=True, timeout=15
            )
            auth.shutdown()
            preview.shutdown()


if __name__ == "__main__":
    main()
