"""Bounded, coalesced, non-generating authentication/model discovery."""

import asyncio
import hashlib
import json
import os
import time
from collections import OrderedDict
from collections.abc import Iterator, Mapping
from dataclasses import dataclass, field
from datetime import UTC, datetime
from typing import Any

import httpx

from sigma import chatgpt_auth
from sigma.model_catalog import CATALOG, DEFAULT_MODEL
from sigma.projects import ProjectError

TTL = 60
RETRY_COOLDOWN = 3
TIMEOUT = 8
MAX_BYTES = 1000000


class AuthContext(Mapping[str, Any]):
    """Internal auth snapshot whose bearer credential is inaccessible to dumps/logs."""

    __slots__ = ("_safe", "_token")

    def __init__(
        self, *, token: str, mode: str, status: str, identity: str, account_label: str | None = None
    ):
        self._safe = {"mode": mode, "status": status, "identity": identity}
        if account_label is not None:
            self._safe["account_label"] = account_label
        self._token = token

    def __getitem__(self, key: str) -> Any:
        if key == "token":
            return self._token
        return self._safe[key]

    def __iter__(self) -> Iterator[str]:
        return iter(self._safe)

    def __len__(self) -> int:
        return len(self._safe)

    def __repr__(self) -> str:
        return f"AuthContext(mode={self._safe['mode']!r}, status={self._safe['status']!r})"


@dataclass
class _CredentialState:
    result: dict[str, Any] | None = None
    checked_at: float = 0.0
    pending: asyncio.Task | None = None
    generation: int = 0
    known: set[str] = field(default_factory=set)
    labels: dict[str, str] = field(default_factory=dict)
    order: list[str] = field(default_factory=list)


_MAX_CREDENTIAL_STATES = 128
_credential_states: OrderedDict[str, _CredentialState] = OrderedDict()


def clear_cache_for_tests() -> None:
    """Clear completed provider snapshots without cancelling live requests."""
    for identity, state in list(_credential_states.items()):
        if state.pending is None or state.pending.done():
            _credential_states.pop(identity, None)


def _credential_state(identity: str) -> _CredentialState | None:
    state = _credential_states.get(identity)
    if state is None:
        # Never evict an in-flight check: a temporary capacity excess is safer
        # than cancelling one user's provider request for another user.
        while len(_credential_states) >= _MAX_CREDENTIAL_STATES:
            victim = next(
                (
                    key
                    for key, value in _credential_states.items()
                    if value.pending is None or value.pending.done()
                ),
                None,
            )
            if victim is None:
                break
            _credential_states.pop(victim, None)
        if len(_credential_states) >= _MAX_CREDENTIAL_STATES:
            return None
        state = _CredentialState()
        _credential_states[identity] = state
    _credential_states.move_to_end(identity)
    return state


MESSAGES = {
    "connected": (
        "OpenAI API · key billing",
        "API authentication/reachability verified only. This does not verify selected-model generation, credits, quota or billing.",
    ),
    "unconfigured": (
        "OpenAI API not configured",
        "API key not configured. Set OPENAI_API_KEY in the checkout .env (or server environment), then run ./sigma start. This optional mode uses separate API billing; manual work remains available.",
    ),
    "unauthorized": (
        "Can't connect to OpenAI API · Check API key",
        "OpenAI rejected API authentication (401). Check the server's OPENAI_API_KEY.",
    ),
    "forbidden": (
        "OpenAI API access denied",
        "OpenAI denied key/account permissions (403). Check account and API-key permissions.",
    ),
    "limited": (
        "OpenAI API rate/quota limited",
        "OpenAI returned 429. Check API rate limits or quota/billing; this is not evidence of an invalid key.",
    ),
    "unavailable": (
        "OpenAI API unavailable",
        "Check the server connection or try again. Provider/network/timeout failure; credentials have not been judged invalid.",
    ),
    "invalid_response": (
        "OpenAI API status unknown",
        "OpenAI returned an invalid or oversized model list. Authentication could not be verified safely.",
    ),
}


def _result(status: str, checked: str | None) -> dict[str, Any]:
    label, guidance = MESSAGES[status]
    return {
        "status": status,
        "label": label,
        "guidance": guidance,
        "checked_at": checked,
        "ttl_seconds": TTL,
    }


@dataclass
class _CatalogResult:
    result: dict[str, Any]
    known: set[str] = field(default_factory=set)
    labels: dict[str, str] = field(default_factory=dict)
    order: list[str] = field(default_factory=list)


async def _check(key: str, mode: str = "api_key") -> _CatalogResult:
    status = "unavailable"
    known: set[str] = set()
    labels: dict[str, str] = {}
    order: list[str] = []
    try:
        async with (
            asyncio.timeout(TIMEOUT),
            httpx.AsyncClient(timeout=TIMEOUT, trust_env=False, follow_redirects=False) as client,
            client.stream(
                "GET",
                "https://api.openai.com/v1/models",
                headers={"Authorization": "Bearer " + key},
            ) as response,
        ):
            if response.status_code == 200:
                data = bytearray()
                async for chunk in response.aiter_bytes():
                    data.extend(chunk)
                    if len(data) > MAX_BYTES:
                        raise ValueError()
                raw = json.loads(data)
                if not isinstance(raw, dict):
                    raise ValueError()
                records = raw.get("models") if mode == "chatgpt" else raw.get("data")
                if (
                    not isinstance(records, list)
                    or len(records) > 10000
                    or (mode == "api_key" and raw.get("object") != "list")
                ):
                    raise ValueError()
                ids = []
                labels = {}
                for model in records:
                    identifier = (
                        model.get("slug" if mode == "chatgpt" else "id")
                        if isinstance(model, dict)
                        else None
                    )
                    if not isinstance(identifier, str) or not 1 <= len(identifier) <= 200:
                        raise ValueError()
                    if mode == "chatgpt" and (
                        not isinstance(model.get("display_name"), str)
                        or model.get("visibility") not in {"list", "hide", "hidden"}
                    ):
                        raise ValueError()
                    if identifier in ids:
                        raise ValueError()
                    if mode != "chatgpt" or model.get("visibility") == "list":
                        ids.append(identifier)
                        if mode == "chatgpt":
                            label = model["display_name"]
                            if not 1 <= len(label) <= 100 or any(ord(char) < 32 for char in label):
                                raise ValueError()
                            labels[identifier] = label
                known = set(ids) & set(CATALOG)
                order = [identifier for identifier in ids if identifier in CATALOG]
                status = "connected"
            else:
                status = {401: "unauthorized", 403: "forbidden", 429: "limited"}.get(
                    response.status_code, "unavailable"
                )
    except (TimeoutError, httpx.HTTPError):
        status = "unavailable"
    except (ValueError, TypeError):
        status = "invalid_response"
    return _CatalogResult(_result(status, datetime.now(UTC).isoformat()), known, labels, order)


async def _cloud_sponsored_context(subject_hash: str | None) -> AuthContext:
    from sigma import cloud_auth
    from sigma.config_secrets import SecretConfigurationError, secret_value

    if not cloud_auth.sponsored_access_enabled():
        return AuthContext(
            token="", mode="chatgpt", status="unavailable", identity="cloud_sponsor_disabled"
        )

    if subject_hash is None:
        return AuthContext(token="", mode="chatgpt", status="unavailable", identity="cloud_unbound")
    from sigma.cloud_sponsor import inference_provider

    provider = inference_provider()
    if provider == "chatgpt":
        from sigma.cloud_sponsor import sponsor_session

        selected = await sponsor_session()
        account = selected.get("account") or {}
        return AuthContext(
            token=account.get("access_token", ""),
            mode="chatgpt",
            status=selected["status"],
            identity=f"cloud_sponsor:{subject_hash}:" + str(selected.get("account_id", "")),
            account_label=account.get("email") or account.get("name"),
        )
    if provider != "api_key":
        return AuthContext(token="", mode="chatgpt", status="unavailable", identity="cloud_invalid")
    try:
        token = secret_value("SIGMA_CLOUD_OPENAI_API_KEY") or ""
    except SecretConfigurationError:
        token = ""
    return AuthContext(
        token=token,
        mode="api_key",
        status="connected" if token else "unconfigured",
        identity=f"cloud_service_api_key:{subject_hash}" if token else "cloud_unconfigured",
    )


async def auth_context() -> AuthContext:
    # Google OIDC identifies a cloud workspace; it does not grant use of the
    # local operator's account or API key. Hosted personal access remains behind
    # an unavailable adapter. Sponsor access requires an explicit stored choice.
    from sigma import cloud_workspaces

    if cloud_workspaces.enabled():
        from sigma import cloud_auth, cloud_personal

        workspace = cloud_workspaces.current()
        subject = workspace.verified_subject if workspace else None
        subject_hash = workspace.subject_hash if workspace else None
        if not subject:
            return AuthContext(
                token="", mode="chatgpt", status="unavailable", identity="cloud_unbound"
            )
        try:
            selected_mode = cloud_auth.model_access_for_subject(subject)
        except (RuntimeError, OSError):
            return AuthContext(
                token="", mode="chatgpt", status="unavailable", identity="cloud_state_unavailable"
            )
        if selected_mode == "personal":
            return await cloud_personal.auth_context(subject_hash)
        return await _cloud_sponsored_context(subject_hash)
    from sigma import cloud_auth

    local_principal = cloud_auth.local_sponsored_principal(require_selected=False)
    local_google_principal = cloud_auth.current_principal()
    if (
        local_principal is not None
        and cloud_auth.model_access_for_subject(local_principal.subject) == "sponsored"
    ):
        workspace = cloud_workspaces.workspace_for_subject(local_principal.subject)
        return await _cloud_sponsored_context(workspace.subject_hash)
    selected = await chatgpt_auth.session()
    mode = selected["mode"]
    if mode == "api_key":
        token = os.environ.get("OPENAI_API_KEY", "").strip()
        return AuthContext(
            token=token,
            mode=mode,
            status="connected" if token else "unconfigured",
            identity="api_key",
        )
    account = selected.get("account") or {}
    if cloud_auth.config().local and local_google_principal is None:
        from sigma.cloud_sponsor import expected_email

        try:
            designated_sponsor_email = expected_email()
        except ProjectError:
            designated_sponsor_email = None
        sponsor_account_selected = bool(designated_sponsor_email) and (
            account.get("email", "").casefold() == designated_sponsor_email
        )
    else:
        sponsor_account_selected = False
    if sponsor_account_selected:
        # The local credential store predates Google accounts and is shared.
        # A member's personal choice must never spend the sponsor's ChatGPT plan.
        return AuthContext(
            token="", mode="chatgpt", status="disconnected", identity="local_personal_unconnected"
        )
    return AuthContext(
        token=account.get("access_token", ""),
        mode=mode,
        status=selected.get("status", "disconnected"),
        identity="chatgpt:" + str(selected.get("account_id", "")),
        account_label=account.get("email") or account.get("name"),
    )


def cloud_credential(context: Mapping[str, Any]) -> bool:
    """Accept only the explicitly selected server provider; never a local account."""
    from sigma import cloud_auth

    if not cloud_auth.sponsored_access_enabled():
        return False
    from sigma.cloud_sponsor import inference_provider

    provider = inference_provider()
    return (
        bool(context.get("token"))
        and context.get("status") == "connected"
        and (
            (
                provider == "api_key"
                and context.get("mode") == "api_key"
                and str(context.get("identity", "")).startswith("cloud_service_api_key:")
            )
            or (
                provider == "chatgpt"
                and context.get("mode") == "chatgpt"
                and str(context.get("identity", "")).startswith("cloud_sponsor:")
            )
        )
    )


async def sponsored_auth_context(subject_hash: str | None = None) -> AuthContext:
    """Check the designated sponsor independently of the user's current choice."""
    from sigma import cloud_workspaces

    workspace = cloud_workspaces.current()
    return await _cloud_sponsored_context(
        subject_hash or (workspace.subject_hash if workspace else None)
    )


PLAN_MESSAGES = {
    "disconnected": (
        "Connect AI",
        "Research requires a ChatGPT connection. Sign in to continue.",
    ),
    "connected": (
        "ChatGPT connected",
        "Using ChatGPT plan allowance or credits. Session, permission and catalog verified; inference and remaining usage are not guaranteed.",
    ),
    "reauth_required": (
        "Reconnect ChatGPT",
        "Your ChatGPT session has expired. Please sign in again to continue.",
    ),
    "plan_not_permitted": (
        "ChatGPT · plan access not enabled",
        "Enable ChatGPT plan use for this account, or explicitly choose API-key billing. No automatic billing switch.",
    ),
    "limited": (
        "ChatGPT usage limit reached",
        "Review plan or app limits in Manage usage. API-key billing has not been selected automatically.",
    ),
    "forbidden": (
        "ChatGPT access restricted",
        "A plan/workspace/region policy prevented access. Check your account permissions; no billing fallback occurred.",
    ),
    "unauthorized": (
        "Reconnect ChatGPT",
        "ChatGPT did not accept this authorization. Reconnect the selected account; no API key is needed.",
    ),
    "unavailable": (
        "ChatGPT temporarily unavailable",
        "Retry later. Your account is retained; no API-key fallback or inference health check was attempted.",
    ),
    "invalid_response": (
        "ChatGPT access unknown",
        "The account catalog could not be validated. Retry; existing settings and credentials are retained.",
    ),
}


async def connection(
    refresh: bool = False, context: Mapping[str, Any] | None = None
) -> dict[str, Any]:
    try:
        if context is None:
            context = await auth_context()
        from sigma import cloud_workspaces

        prefs = (
            {
                "mode": context["mode"],
                "active_account": None,
                "accounts": [],
                "welcome_pending": False,
                "usage_url": None,
            }
            if cloud_workspaces.enabled() or str(context.get("identity", "")).startswith("cloud_")
            else await chatgpt_auth.preferences()
        )
    except ProjectError:
        return {
            "mode": "unknown",
            "status": "unavailable",
            "label": "AI account storage unavailable",
            "guidance": "Check private SIGMA account storage ownership/permissions. Manual research remains available; no credential or billing path was selected.",
            "accounts": [],
            "active_account": None,
            "welcome_pending": False,
            "checked_at": None,
            "ttl_seconds": TTL,
        }
    key, mode = context["token"], context["mode"]
    identity = hashlib.sha256((mode + key).encode()).hexdigest()
    credential_state = _credential_state(identity) if key else None
    if context["status"] != "connected":
        state = {"status": context["status"], "checked_at": None, "ttl_seconds": TTL}
    elif credential_state is None:
        state = _result("unavailable", None)
    else:
        age = time.monotonic() - credential_state.checked_at
        if credential_state.result is None or age >= (RETRY_COOLDOWN if refresh else TTL):
            if credential_state.pending is None or credential_state.pending.done():
                expected = credential_state.generation
                task = asyncio.create_task(_check(key, mode))
                credential_state.pending = task

                def complete(
                    done: asyncio.Task, *, target=credential_state, generation=expected
                ) -> None:
                    if target.pending is not done:
                        return
                    target.pending = None
                    if target.generation != generation:
                        return
                    if done.cancelled():
                        target.result = _result("unavailable", datetime.now(UTC).isoformat())
                        target.checked_at = time.monotonic()
                        return
                    try:
                        result = done.result()
                        if isinstance(result, _CatalogResult):
                            target.result = result.result
                            target.known, target.labels, target.order = (
                                result.known,
                                result.labels,
                                result.order,
                            )
                        else:
                            target.result = dict(result)
                            target.known, target.labels, target.order = set(), {}, []
                        target.checked_at = time.monotonic()
                    except (httpx.HTTPError, TimeoutError, ValueError, TypeError):
                        target.result = _result("unavailable", datetime.now(UTC).isoformat())
                        target.checked_at = time.monotonic()

                task.add_done_callback(complete)
            pending_task = credential_state.pending
            if pending_task is not None:
                await asyncio.shield(pending_task)
        state = dict(credential_state.result or _result("unavailable", None))
    label, guidance = (PLAN_MESSAGES if mode == "chatgpt" else MESSAGES)[state["status"]]
    if cloud_workspaces.enabled() and str(context.get("identity", "")).startswith(
        "cloud_personal_unavailable:"
    ):
        label = "Personal ChatGPT connection unavailable"
        from sigma.cloud_personal import UNAVAILABLE_GUIDANCE

        guidance = UNAVAILABLE_GUIDANCE
    elif mode == "chatgpt" and str(context.get("identity", "")).startswith("cloud_sponsor:"):
        label = "SIGMA-sponsored ChatGPT · " + str(state["status"]).replace("_", " ")
        if state["status"] != "connected":
            guidance = (
                "SIGMA-sponsored ChatGPT is temporarily unavailable. Please try again later. "
                "Saved research is unchanged."
            )
    return {
        **state,
        **prefs,
        "mode": mode,
        "sponsor_account_selected": context.get("identity") == "local_personal_unconnected",
        "label": label,
        "guidance": guidance,
        "account_label": context.get("account_label"),
        "welcome_pending": prefs["welcome_pending"]
        and mode == "chatgpt"
        and state["status"] == "connected",
    }


def inference_failure(status: str, guard: str | None = None) -> None:
    if guard is None:
        return
    state = _credential_states.get(guard)
    if state is None:
        return
    state.generation += 1
    state.result = {
        "status": status,
        "checked_at": datetime.now(UTC).isoformat(),
        "ttl_seconds": TTL,
    }
    state.checked_at = time.monotonic()
    state.known, state.labels, state.order = set(), {}, []


async def models(refresh: bool = False, context: Mapping[str, Any] | None = None) -> dict[str, Any]:
    if context is None:
        try:
            context = await auth_context()
        except ProjectError:
            context = None
    state = await connection(refresh, context)
    identity = (
        hashlib.sha256((str(context["mode"]) + str(context["token"])).encode()).hexdigest()
        if context is not None
        else ""
    )
    credential_state = _credential_states.get(identity)
    # The models API is used broadly and does not need the account identity;
    # keep the email scoped to the connection-status surface that owns its UI.
    public_state = {key: value for key, value in state.items() if key != "account_label"}
    verified = state["status"] == "connected"
    choices = [
        {
            "id": identifier,
            **capability,
            "label": (
                credential_state.labels.get(identifier, capability["label"])
                if credential_state
                else capability["label"]
            )
            if state["mode"] == "chatgpt" and verified
            else capability["label"],
            "availability": (
                "available"
                if credential_state and identifier in credential_state.known
                else "unavailable"
            )
            if verified
            else "unverified",
        }
        for identifier in (
            (
                (credential_state.order if credential_state else [])
                + [
                    key
                    for key in CATALOG
                    if key not in (credential_state.order if credential_state else [])
                ]
            )
            if state["mode"] == "chatgpt" and verified
            else list(CATALOG)
        )
        for capability in [CATALOG[identifier]]
    ]
    accessible = [c["id"] for c in choices if c["availability"] == "available"]
    default = DEFAULT_MODEL if DEFAULT_MODEL in accessible or not accessible else accessible[0]
    message = (
        "Using ChatGPT plan allowance or credits."
        if state["mode"] == "chatgpt"
        else "OpenAI API · billed separately."
    ) + " Account access checked; inference/remaining usage is not verified."
    if not accessible:
        message = "No reviewed model is verified accessible. Sol/High is an unverified offline preference; manual research remains available."
    elif default != DEFAULT_MODEL:
        message = f"Sol is unavailable to this account. Initial choice: {CATALOG[default]['label']} / High. Later requests never substitute models."
    if os.environ.get("SIGMA_AI_MODEL") and os.environ["SIGMA_AI_MODEL"] not in CATALOG:
        message += " SIGMA_AI_MODEL is not a reviewed reasoning model; legacy projects use the documented Sol/High default. Saved project choices are unaffected."
    return {
        "models": choices,
        "connection": public_state,
        "default_model": default,
        "default_effort": "high",
        "default_verified": verified and bool(accessible),
        "message": message,
    }
