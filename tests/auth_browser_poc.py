"""Offline tests for the opt-in containerized OpenAI login experiment."""

from __future__ import annotations

import os
import tempfile
from pathlib import Path
from types import SimpleNamespace
from typing import cast
from unittest.mock import patch

import test_environment as _test_environment  # noqa: F401
from fastapi import HTTPException, Request
from pydantic import ValidationError

from sigma import auth_browser_poc_api as proxy
from sigma import auth_browser_poc_worker as worker
from sigma.api import app
from sigma.auth_browser_poc_worker import Pointer


def rejected(code: int, callback) -> None:
    try:
        callback()
    except HTTPException as exc:
        assert exc.status_code == code, exc
    else:
        raise AssertionError("Unauthorized auth-browser request was accepted")


def main() -> None:
    admin = SimpleNamespace(role="admin", subject="google-admin")
    member = SimpleNamespace(role="member", subject="google-member")

    def request(principal: object) -> Request:
        return cast(Request, SimpleNamespace(state=SimpleNamespace(cloud_principal=principal)))

    with patch.dict(os.environ, {}, clear=False):
        os.environ.pop("SIGMA_AUTH_BROWSER_POC_ENABLED", None)
        rejected(404, lambda: proxy._authorize(request(admin)))
    with patch.dict(os.environ, {"SIGMA_AUTH_BROWSER_POC_ENABLED": "true"}):
        assert proxy._authorize(request(admin)) is None
        rejected(403, lambda: proxy._authorize(request(member)))
        rejected(403, lambda: proxy._authorize(request(None)))
        rejected(
            403,
            lambda: proxy._authorize(request(SimpleNamespace(role="admin", subject="mock:admin"))),
        )
    with tempfile.TemporaryDirectory() as directory:
        secret = Path(directory) / "key"
        secret.write_text("a" * 64)
        with patch.dict(
            os.environ,
            {
                "SIGMA_AUTH_BROWSER_POC_ORIGIN": "http://127.0.0.1:18765",
                "SIGMA_AUTH_BROWSER_POC_KEY_FILE": str(secret),
            },
        ):
            assert proxy._upstream() == ("http://127.0.0.1:18765", "a" * 64)
            worker._require_key("a" * 64)
            rejected(403, lambda: worker._require_key("b" * 64))
            rejected(403, lambda: worker._require_key(None))
            for origin in (
                "https://127.0.0.1:18765",
                "http://127.0.0.1:8080",
                "http://localhost:18765",
                "http://evil.example:8765",
                "http://user@127.0.0.1:18765",
            ):
                with patch.dict(os.environ, {"SIGMA_AUTH_BROWSER_POC_ORIGIN": origin}):
                    rejected(503, proxy._upstream)
        with patch.dict(
            os.environ,
            {
                "SIGMA_AUTH_BROWSER_POC_ORIGIN": "http://auth-browser-poc:8765",
                "SIGMA_AUTH_BROWSER_POC_KEY_FILE": str(secret),
            },
        ):
            assert proxy._upstream()[0] == "http://auth-browser-poc:8765"
    assert Pointer(kind="click", x=1279, y=799)
    for coords in ({"x": -1}, {"y": 800}, {"value": "x" * 201}):
        try:
            Pointer.model_validate({"kind": "click", **coords})
        except ValidationError:
            continue
        raise AssertionError("Unbounded remote browser action was accepted")
    routes = {getattr(route, "path", "") for route in app.routes}
    for suffix in ("/ui", "/begin", "/status", "/frame", "/input", "/test"):
        assert "/api/auth-browser-poc" + suffix in routes
    root = Path(__file__).resolve().parents[1]
    overlay = (root / "deploy/compose.auth-browser-poc.yaml").read_text()
    assert "ports:" not in overlay
    assert 'expose: ["8765"]' in overlay
    assert "auth_browser_poc_key" in overlay
    assert 'SIGMA_AUTH_BROWSER_POC_ENABLED: "true"' in overlay
    assert "--network=none" in (root / "src/sigma/python_sandbox.py").read_text()
    assert "python -m uvicorn" in (root / "auth-browser-poc/entrypoint.sh").read_text()
    assert "--auth-browser-poc" in (root / "deploy/release_image.py").read_text()
    assert "compose.auth-browser-poc.yaml" in (root / "deploy/start-gce.sh").read_text()
    print(
        "PASS opt-in admin authorization, private worker origin/key, constrained display, portable compose wiring"
    )


if __name__ == "__main__":
    main()
