"""User-scoped, credential-free transport to the private Personal ChatGPT worker.

SIGMA only sends a bounded Responses API payload and an opaque account binding.
Only the isolated credential worker may ever hold, refresh or use OpenAI tokens.
The shipped worker deliberately rejects real inference until authorization and
provider-eligibility gates are satisfied. No provider URL is caller-controlled.
"""

from __future__ import annotations

import hmac
import json
import os
import re
from typing import Any

import httpx

from sigma import cloud_auth, cloud_workspaces, personal_browser
from sigma.model_catalog import CATALOG
from sigma.projects import ProjectError

_BINDING = re.compile(r"[0-9a-f]{64}\Z")
_MAX_REQUEST = 256_000
_MAX_REPLY = 2_000_000


class PersonalInferenceUnavailable(ProjectError):
    """A user's private model worker cannot verify or execute this request."""


def _current_principal() -> cloud_auth.Principal:
    """Both independently verified context bindings must identify the same user."""
    principal = cloud_auth.current_principal()
    workspace = cloud_workspaces.current()
    local_admin_preview = (
        workspace is None
        and isinstance(principal, cloud_auth.Principal)
        and principal.role == "admin"
        and principal.subject.startswith("local-admin:")
        and personal_browser.sign_in_preview_enabled()
    )
    if (
        not isinstance(principal, cloud_auth.Principal)
        or principal.role not in {"admin", "member"}
        or principal.subject.startswith("mock:")
        or (
            not local_admin_preview
            and (
                workspace is None
                or workspace.guest
                or workspace.verified_subject != principal.subject
            )
        )
    ):
        raise PersonalInferenceUnavailable("A verified personal workspace is required.")
    try:
        if cloud_auth.model_access_for_subject(principal.subject) != "personal":
            raise PersonalInferenceUnavailable("Personal ChatGPT is not selected.")
    except (OSError, RuntimeError) as exc:
        raise PersonalInferenceUnavailable("Personal access could not be verified.") from exc
    return principal


async def _socket(principal: cloud_auth.Principal) -> str:
    try:
        # User -> workspace ID -> mode socket comes exclusively from SIGMA's
        # authenticated workspace mapping, never a request body or URL.
        return await personal_browser.model_socket(principal)
    except (PermissionError, personal_browser.PersonalBrowserUnavailable) as exc:
        raise PersonalInferenceUnavailable("Personal model worker is unavailable.") from exc


async def _request(
    principal: cloud_auth.Principal, method: str, endpoint: str, body: dict[str, Any] | None = None
) -> dict[str, Any]:
    if (method, endpoint) not in {
        ("GET", "/v1/account"),
        ("POST", "/v1/response"),
        ("POST", "/v1/disconnect"),
    }:
        raise PersonalInferenceUnavailable("Unsupported model operation.")
    socket_path = await _socket(principal)
    headers: dict[str, str] = {}
    if personal_browser.sign_in_preview_enabled():
        seed = os.environ.get("SIGMA_AUTH_POC_RPC_SEED", "")
        if not _BINDING.fullmatch(seed):
            raise PersonalInferenceUnavailable(
                "Local Personal worker authentication is unavailable."
            )
        try:
            workspace_id = await personal_browser._workspace_id(principal)
        except personal_browser.PersonalBrowserUnavailable as exc:
            raise PersonalInferenceUnavailable("Personal model worker is unavailable.") from exc
        headers["X-Sigma-Worker-Key"] = hmac.digest(
            bytes.fromhex(seed), workspace_id.encode("ascii"), "sha256"
        ).hex()
    transport = httpx.AsyncHTTPTransport(uds=socket_path)
    try:
        async with httpx.AsyncClient(
            transport=transport,
            base_url="http://private-personal-worker",
            trust_env=False,
            follow_redirects=False,
            timeout=65,
            headers=headers,
        ) as client:
            if method == "GET":
                response = await client.get(endpoint)
            else:
                encoded = json.dumps(body, separators=(",", ":"), ensure_ascii=False).encode()
                if len(encoded) > _MAX_REQUEST:
                    raise PersonalInferenceUnavailable("Personal request is too large.")
                response = await client.post(
                    endpoint,
                    content=encoded,
                    headers={"Content-Type": "application/json"},
                )
            if response.status_code != 200 or len(response.content) > _MAX_REPLY:
                raise PersonalInferenceUnavailable("Personal model worker denied the request.")
            data = response.json()
    except (httpx.HTTPError, OSError, ValueError, TypeError) as exc:
        raise PersonalInferenceUnavailable("Personal model worker is unavailable.") from exc
    if not isinstance(data, dict):
        raise PersonalInferenceUnavailable("Invalid worker response.")
    # Never accept a token, OAuth code, or other credential in any worker reply.
    if any(k in data for k in ("token", "access_token", "refresh_token", "id_token", "api_key")):
        raise PersonalInferenceUnavailable("Unexpected credential in worker response.")
    return data


def _account(result: dict[str, Any]) -> dict[str, Any]:
    status = result.get("status")
    if status not in {"disabled", "disconnected", "unavailable", "verified"}:
        raise PersonalInferenceUnavailable("Invalid worker account status.")
    binding = result.get("binding")
    models = result.get("models")
    label = result.get("account_label")
    if not isinstance(models, list) or len(models) > len(CATALOG):
        raise PersonalInferenceUnavailable("Invalid personal model catalog.")
    if any(not isinstance(model, str) or model not in CATALOG for model in models):
        raise PersonalInferenceUnavailable("Invalid personal model catalog.")
    if label is not None and (not isinstance(label, str) or len(label) > 254):
        raise PersonalInferenceUnavailable("Invalid account identity.")
    if status == "verified":
        if not isinstance(binding, str) or not _BINDING.fullmatch(binding) or not models:
            raise PersonalInferenceUnavailable("Unverified account binding.")
    elif binding is not None or models or label is not None:
        raise PersonalInferenceUnavailable("Disconnected worker exposed an account.")
    return {"status": status, "binding": binding, "models": models, "account_label": label}


async def account(principal: cloud_auth.Principal | None = None) -> dict[str, Any]:
    verified = _current_principal() if principal is None else personal_browser._principal(principal)
    # An explicit principal is used only for already-authenticated SIGMA status
    # surfaces. Inference itself always requires the two matching context bindings.
    return _account(await _request(verified, "GET", "/v1/account"))


async def disconnect(principal: cloud_auth.Principal) -> None:
    if not personal_browser.sign_in_preview_enabled():
        raise PersonalInferenceUnavailable("Personal ChatGPT disconnect is unavailable.")
    verified = personal_browser._principal(principal)
    if (await _request(verified, "POST", "/v1/disconnect")).get("disconnected") is not True:
        raise PersonalInferenceUnavailable("The Personal worker did not confirm disconnect.")


async def respond(
    payload: dict[str, Any], *, expected_binding: str, request_id: str
) -> dict[str, Any]:
    """Execute only for the exact, still-selected Google user and model account."""
    principal = _current_principal()
    if (
        not isinstance(expected_binding, str)
        or not _BINDING.fullmatch(expected_binding)
        or not isinstance(request_id, str)
        or not re.fullmatch(r"[0-9a-f]{32}", request_id)
        or not isinstance(payload, dict)
        or payload.get("store") is not False
        or payload.get("stream") is not True
        or payload.get("model") not in CATALOG
        or any(key in payload for key in ("url", "token", "headers", "authorization", "api_key"))
    ):
        raise PersonalInferenceUnavailable("Invalid personal model request.")
    account_state = await account(principal)
    if (
        account_state["status"] != "verified"
        or account_state["binding"] != expected_binding
        or payload["model"] not in account_state["models"]
    ):
        raise PersonalInferenceUnavailable(
            "The selected ChatGPT account changed or is unavailable."
        )
    result = await _request(
        principal,
        "POST",
        "/v1/response",
        {"request_id": request_id, "expected_binding": expected_binding, "payload": payload},
    )
    if (
        result.get("binding") != expected_binding
        or not isinstance(result.get("response"), dict)
        or result["response"].get("model") != payload["model"]
        or result["response"].get("status") != "completed"
    ):
        raise PersonalInferenceUnavailable("Personal model response did not match the request.")
    return result["response"]
