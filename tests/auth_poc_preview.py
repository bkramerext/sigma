"""Fail-closed tests for the admin-only, path-scoped synthetic browser preview."""

from __future__ import annotations

import importlib.util
import os
import sys
import unittest
from pathlib import Path
from typing import Any, cast
from unittest.mock import AsyncMock, patch

from fastapi.testclient import TestClient
from starlette.responses import Response
from starlette.websockets import WebSocketDisconnect

ROOT = Path(__file__).resolve().parents[1]
sys.path.insert(0, str(ROOT / "src"))
sys.path.insert(0, str(ROOT / "auth-poc"))
os.environ.update(
    {
        "SIGMA_AUTH_POC_PREVIEW_ENABLED": "1",
        "SIGMA_AUTH_POC_REAL_SIGNIN": "0",
        "SIGMA_PERSONAL_LAB_HOST": "sigma.example.test",
        "SIGMA_PERSONAL_LAB_EDGE_KEY": "test-only-edge-key-" + "x" * 40,
        "SIGMA_PERSONAL_LAB_SUBJECT": "auth-poc-synthetic-admin",
        "SIGMA_PERSONAL_LAB_ADMIN_EMAIL": "preview-admin@example.invalid",
    }
)

PREVIEW_SPEC = importlib.util.spec_from_file_location(
    "preview_server", ROOT / "auth-poc/preview_server.py"
)
assert PREVIEW_SPEC and PREVIEW_SPEC.loader
preview = cast(Any, importlib.util.module_from_spec(PREVIEW_SPEC))
PREVIEW_SPEC.loader.exec_module(preview)

ROUTE_SPEC = importlib.util.spec_from_file_location(
    "auth_poc_preview_caddy_route", ROOT / "deploy/auth-poc-preview-caddy-route.py"
)
assert ROUTE_SPEC and ROUTE_SPEC.loader
caddy_route = importlib.util.module_from_spec(ROUTE_SPEC)
ROUTE_SPEC.loader.exec_module(caddy_route)

EDGE = os.environ["SIGMA_PERSONAL_LAB_EDGE_KEY"]
HOST = os.environ["SIGMA_PERSONAL_LAB_HOST"]
PREFIX = preview.PREFIX
EDGE_HEADERS = {
    "X-Sigma-Personal-Lab-Edge": EDGE,
    "Host": HOST,
}


class PreviewTests(unittest.TestCase):
    def setUp(self) -> None:
        self.client = TestClient(preview.app, base_url="https://" + HOST)

    def test_only_trusted_edge_reaches_preview_and_browser_auth_is_stripped(self) -> None:
        self.assertEqual(self.client.get(PREFIX + "/").status_code, 403)
        self.assertEqual(
            self.client.get(
                PREFIX + "/", headers=EDGE_HEADERS | {"Cookie": "sigma_session=bad"}
            ).status_code,
            403,
        )
        self.assertEqual(
            self.client.get(
                PREFIX + "/", headers=EDGE_HEADERS | {"Authorization": "Bearer bad"}
            ).status_code,
            403,
        )
        self.assertEqual(
            self.client.get(
                PREFIX + "/", headers=EDGE_HEADERS | {"Host": "attacker.example"}
            ).status_code,
            403,
        )
        response = self.client.get(PREFIX + "/", headers=EDGE_HEADERS)
        self.assertEqual(response.status_code, 200)
        self.assertIn("Synthetic preview only", response.text)
        self.assertIn("ChatGPT", response.text)
        self.assertIn("fetch(prefix+", response.text)
        self.assertNotIn("fetch('/api/", response.text)
        self.assertNotIn('fetch("/api/', response.text)
        self.assertNotIn("auth.openai.com", response.text)
        self.assertEqual(response.headers["cache-control"], "no-store")
        self.assertEqual(
            self.client.get("/api/cloud-auth/admin/grants", headers=EDGE_HEADERS).status_code, 404
        )

    def test_lifecycle_uses_only_the_fixed_server_principal_and_same_origin(self) -> None:
        result = {"browser_status": "ready", "personal_chatgpt_connected": False, "account": None}
        with patch.object(
            preview.personal_browser, "session", new=AsyncMock(return_value=result)
        ) as session:
            denied = self.client.post(
                PREFIX + "/api/start",
                headers=EDGE_HEADERS | {"Origin": "https://evil.example"},
            )
            self.assertEqual(denied.status_code, 403)
            session.assert_not_awaited()
            started = self.client.post(
                PREFIX + "/api/start", headers=EDGE_HEADERS | {"Origin": "https://" + HOST}
            )
            self.assertEqual(started.status_code, 200)
            session.assert_awaited_once()
            principal, action = session.await_args_list[0].args
            self.assertEqual(principal.subject, "auth-poc-synthetic-admin")
            self.assertEqual(principal.role, "admin")
            self.assertEqual(action, "start")

    def test_lifecycle_rejects_request_bodies_before_broker_dispatch(self) -> None:
        with patch.object(preview.personal_browser, "session", new=AsyncMock()) as session:
            body = self.client.post(
                PREFIX + "/api/start",
                content=b"{}",
                headers=EDGE_HEADERS | {"Origin": "https://" + HOST},
            )
            chunked = self.client.post(
                PREFIX + "/api/stop",
                content=b"{}",
                headers=EDGE_HEADERS
                | {"Origin": "https://" + HOST, "Transfer-Encoding": "chunked"},
            )
            self.assertEqual(body.status_code, 400)
            self.assertEqual(chunked.status_code, 400)
            session.assert_not_awaited()

    def test_window_and_assets_stay_inside_preview_prefix(self) -> None:
        with (
            patch.object(
                preview.personal_browser_proxy,
                "_ready",
                new=AsyncMock(return_value="/run/vnc.sock"),
            ),
            patch.object(
                preview.personal_browser, "browser_password", new=AsyncMock(return_value="A1B2C3D4")
            ),
            patch.object(
                preview.personal_browser_proxy,
                "asset",
                new=AsyncMock(
                    return_value=Response(b"synthetic-asset", media_type="text/javascript")
                ),
            ) as asset,
        ):
            window = self.client.get(PREFIX + "/window", headers=EDGE_HEADERS)
            self.assertEqual(window.status_code, 200)
            self.assertIn(PREFIX + "/assets/app/rfb.js", window.text)
            self.assertIn(PREFIX + "/ws", window.text)
            self.assertNotIn("/api/", window.text)
            self.assertIn("do not sign in to OpenAI", window.text)
            self.assertEqual(window.headers["cache-control"], "no-store")
            response = self.client.get(PREFIX + "/assets/app/rfb.js", headers=EDGE_HEADERS)
            self.assertEqual(response.content, b"synthetic-asset")
            asset.assert_awaited_once()

    def test_websocket_rejects_bad_origin_before_opening_worker(self) -> None:
        with (
            patch.object(preview.personal_browser, "session", new=AsyncMock()) as session,
            self.assertRaises(WebSocketDisconnect) as closed,
            self.client.websocket_connect(
                PREFIX + "/ws",
                headers=EDGE_HEADERS | {"Origin": "https://evil.example"},
            ),
        ):
            pass
        self.assertEqual(closed.exception.code, 1008)
        session.assert_not_awaited()

    def test_websocket_has_short_reauthentication_lifetime(self) -> None:
        self.assertEqual(preview._MAX_WS_SECONDS, 60)


class CaddyRouteTests(unittest.TestCase):
    def test_render_adds_only_admin_gated_same_host_path(self) -> None:
        baseline = (ROOT / "deploy/Caddyfile").read_bytes()
        snippet = (ROOT / "deploy/auth-poc.preview.caddy").read_bytes()
        rendered = caddy_route.render(baseline, snippet, EDGE)
        self.assertEqual(rendered.count(b"@personal_lab path"), 1)
        self.assertIn(b"uri /api/cloud-auth/admin/grants", rendered)
        self.assertIn(b"/api /api/*", rendered)
        self.assertIn(EDGE.encode(), rendered)
        self.assertNotIn(b"{$SIGMA_PERSONAL_LAB_EDGE_KEY}", rendered)

    def test_render_rejects_unreviewed_or_duplicate_baseline(self) -> None:
        baseline = (ROOT / "deploy/Caddyfile").read_bytes()
        snippet = (ROOT / "deploy/auth-poc.preview.caddy").read_bytes()
        with self.assertRaises(ValueError):
            caddy_route.render(baseline + baseline, snippet, EDGE)
        with self.assertRaises(ValueError):
            caddy_route.render(baseline.replace(b"/api /api/*", b"/api/*"), snippet, EDGE)
        with self.assertRaises(ValueError):
            caddy_route.render(baseline, snippet, "short")


def deployment_invariants() -> None:
    snippet = (ROOT / "deploy/auth-poc.preview.caddy").read_text(encoding="utf-8")
    assert "@personal_lab path /__personal_lab__ /__personal_lab__/*" in snippet
    assert "uri /api/cloud-auth/admin/grants" in snippet
    assert "copy_headers" not in snippet
    assert "header_up -Cookie" in snippet
    assert "header_up -Authorization" in snippet
    assert "header_up -Proxy-Authorization" in snippet
    assert "header_up -X-Forwarded-Authorization" in snippet
    assert "header_up -X-Api-Key" in snippet
    assert "header_up -X-OpenAI-Api-Key" in snippet
    assert "header_down -Set-Cookie" in snippet
    assert "stream_timeout 60s" in snippet
    compose = (ROOT / "deploy/auth-poc.preview.compose.yaml").read_text(encoding="utf-8")
    assert "ports:" not in compose
    assert "docker.sock" not in compose
    assert 'SIGMA_AUTH_POC_REAL_SIGNIN: "0"' in compose
    assert "personal-lab:\n    external: true\n    name: sigma_personal_lab" in compose
    unit = (ROOT / "deploy/auth-poc-preview-broker.service").read_text(encoding="utf-8")
    for expected in (
        "Restart=on-failure",
        "ProtectSystem=strict",
        "RestrictAddressFamilies=AF_UNIX",
        "ReadWritePaths=/run/sigma-personal-broker /run/sigma-personal-gateways /srv/sigma-state/auth/personal-lab",
        "CapabilityBoundingSet=CAP_CHOWN",
        "Environment=SIGMA_AUTH_BROKER_ISOLATED_NETWORK=1",
    ):
        assert expected in unit, expected
    worker_network = (ROOT / "deploy/auth-poc.preview.worker.gce.yaml").read_text(encoding="utf-8")
    assert "default:\n    internal: true" in worker_network
    production_caddy = (ROOT / "deploy/Caddyfile").read_bytes()
    rendered = caddy_route.render(
        production_caddy,
        (ROOT / "deploy/auth-poc.preview.caddy").read_bytes(),
        "test-edge-key-" + "x" * 40,
    )
    assert rendered != production_caddy
    assert b"@personal_lab path" in rendered
    assert b"SIGMA_PERSONAL_LAB_EDGE_KEY" not in rendered
    assert b"header_up X-Sigma-Personal-Lab-Edge test-edge-key-" in rendered
    assert rendered.index(b"@personal_lab path") < rendered.index(b"@api path /api /api/*")
    assert b"handle @api" in rendered
    try:
        caddy_route.render(
            rendered,
            (ROOT / "deploy/auth-poc.preview.caddy").read_bytes(),
            "x" * 40,
        )
    except ValueError:
        pass
    else:
        raise AssertionError("Duplicate private route was accepted")


def main() -> None:
    suite = unittest.defaultTestLoader.loadTestsFromModule(sys.modules[__name__])
    result = unittest.TextTestRunner(verbosity=2).run(suite)
    if not result.wasSuccessful():
        raise SystemExit(1)
    deployment_invariants()
    print(
        "PASS isolated route, edge gate, credential stripping, WebSocket bounds, and deploy invariants"
    )


if __name__ == "__main__":
    main()
