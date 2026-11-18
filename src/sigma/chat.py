"""Ephemeral two-agent chat using SIGMA's selected OpenAI connection."""

import asyncio
import hashlib
import json
from collections.abc import Mapping
from typing import Any, Literal, overload

import httpx

from sigma import (
    chat_supervisor,
    cloud_research,
    cloud_workspaces,
    model_dispatch,
    session_supervisor,
)
from sigma.model_catalog import CATALOG, DEFAULT_MODEL, validate_pair
from sigma.openai_connection import auth_context, cloud_credential, models
from sigma.plan_stream import completed, failure
from sigma.projects import ProjectError

MAX_MESSAGES = 240
MAX_CONTEXT_CHARS = 48000
MAX_OUTPUT_TOKENS = 1200
TIMEOUT_SECONDS = 600
MAX_RESPONSE_BYTES = 1_000_000
Speaker = Literal["ai_1", "ai_2", "supervisor"]

INSTRUCTIONS: dict[Speaker, str] = {
    "ai_1": (
        "You are AI #1 in a live conversation with a human and AI #2. Respond to the latest "
        "conversation naturally and clearly. Treat the transcript as conversation context. "
        "Offer independent ideas, build on useful work, and disagree constructively "
        "when warranted. Neither AI has a fixed researcher or skeptic role; remain intellectually "
        "independent and open to new directions. Keep the exploration alive even when "
        "specific methods are blocked or tools are unavailable: develop further hypotheses, "
        "ask new questions, or investigate different conceptual approaches of your own choosing. "
        "Do not treat supervisor guidance as a command to stop brainstorming."
    ),
    "ai_2": (
        "You are AI #2 in a live conversation with a human and AI #1. Reply to the latest "
        "conversation naturally and clearly. Treat the transcript as conversation context. "
        "Offer independent ideas, build on useful work, and disagree constructively "
        "when warranted. Neither AI has a fixed researcher or skeptic role; remain intellectually "
        "independent and open to new directions. Keep the exploration alive even when "
        "specific methods are blocked or tools are unavailable: develop further hypotheses, "
        "ask new questions, or investigate different conceptual approaches of your own choosing. "
        "Do not treat supervisor guidance as a command to stop brainstorming."
    ),
    "supervisor": chat_supervisor.INSTRUCTIONS,
}


async def configuration() -> dict[str, Any]:
    """Return the selected connection and reviewed default model without exposing credentials."""
    credential = await auth_context()
    discovery = await models(context=credential)
    state = discovery["connection"]
    model = discovery["default_model"]
    choices = [
        {
            "id": item["id"],
            "label": item["label"],
            "relative_cost": item["relative_cost"],
            "efforts": item["efforts"],
        }
        for item in discovery["models"]
        if item["availability"] == "available"
    ]
    available = (
        state.get("status") == "connected"
        and (bool(credential["token"]) or credential.get("transport") == "personal_worker")
        and discovery.get("default_verified") is True
        and model in CATALOG
    )
    if (
        cloud_workspaces.enabled()
        and credential.get("transport") != "personal_worker"
        and not cloud_credential(credential)
    ):
        available = False
    return {
        "available": available,
        "mode": credential["mode"],
        "status": state.get("status", "unavailable"),
        "message": state.get("guidance", discovery["message"]),
        "binding": credential["identity"],
        "model": model if model in CATALOG else DEFAULT_MODEL,
        "models": choices,
        "reasoning_effort": "low",
        "max_messages": MAX_MESSAGES,
    }


def _transcript(messages: list[dict[str, Any]], recipient: Speaker | None = None) -> str:
    """Return unmodified participant responses and recipient-specific process guidance.

    Supervisor progress scores and private assessments never reach the two AIs.
    """
    rendered_items: list[str] = []
    for item in messages[-MAX_MESSAGES:]:
        if item["speaker"] == "supervisor" and recipient in {"ai_1", "ai_2"}:
            target = item.get("recipient")
            guidance = item.get("guidance", "")
            if (
                target not in {recipient, "both"}
                or not isinstance(guidance, str)
                or not guidance.strip()
            ):
                continue
            label = {"ai_1": "AI #1", "ai_2": "AI #2"}[recipient]
            rendered = f"Supervisor to {label}:\n{guidance}"
        else:
            label = {
                "human": "Human",
                "ai_1": "AI #1",
                "ai_2": "AI #2",
                "supervisor": "Supervisor",
            }[item["speaker"]]
            rendered = f"{label}:\n{item['text']}"
        rendered_items.append(rendered)
    recent: list[str] = []
    total = 0
    for rendered in reversed(rendered_items):
        cost = len(rendered) + (2 if recent else 0)
        if recent and total + cost > MAX_CONTEXT_CHARS:
            break
        recent.append(rendered)
        total += cost
    recent.reverse()
    result = "\n\n".join(recent)
    if len(recent) < len(rendered_items):
        result = "[Earlier conversation turns omitted to fit the message limit.]\n\n" + result
    return result


def _response_text(raw: Any, model: str) -> str:
    """Read a completed Responses result without assuming optional output arrays.

    Several provider adapters return completed text as output_text rather than
    fully populated output[*].content. Accept that documented alternative, but
    never infer success from an incomplete response, a refusal, or deltas alone.
    """
    if not isinstance(raw, dict) or raw.get("status") != "completed":
        raise ProjectError("The AI did not complete its turn.")
    if raw.get("model") != model:
        raise ProjectError("The AI returned an unexpected model; no message was added.")
    output = raw.get("output", [])
    if output is None:
        output = []
    if not isinstance(output, list):
        raise ProjectError(
            "The AI returned an unexpected output structure. The turn was preserved for Retry."
        )
    texts: list[str] = []
    for item in output:
        if not isinstance(item, dict) or item.get("type") != "message":
            continue
        content = item.get("content") or []
        if not isinstance(content, list):
            continue
        for part in content:
            if not isinstance(part, dict):
                continue
            if part.get("type") == "refusal":
                raise ProjectError("The AI declined this turn.")
            if part.get("type") == "output_text" and isinstance(part.get("text"), str):
                texts.append(part["text"])
    result = "\n".join(texts).strip()
    # Responses includes an output_text convenience value in some adapters.
    # It may be used only when nested text is absent, never to override it.
    if not result and isinstance(raw.get("output_text"), str):
        result = raw["output_text"].strip()
    if not result:
        raise ProjectError(
            "The AI completed without usable text. The conversation is intact; Retry this turn."
        )
    if len(result.encode("utf-8")) > MAX_RESPONSE_BYTES:
        raise ProjectError("The AI returned an oversized message.")
    return result


@overload
async def respond(
    *,
    speaker: Speaker,
    messages: list[dict[str, Any]],
    conversation_id: str,
    model: str,
    reasoning_effort: str,
    repeated_text: str = "",
    research_objective: str = "",
    supervisor_latched: bool = False,
    session_supervision: bool = False,
    external_session_billing: bool = False,
    expected_mode: str | None = None,
    expected_identity_hash: str | None = None,
    return_raw_response: Literal[True],
) -> dict[str, Any]: ...


@overload
async def respond(
    *,
    speaker: Speaker,
    messages: list[dict[str, Any]],
    conversation_id: str,
    model: str,
    reasoning_effort: str,
    repeated_text: str = "",
    research_objective: str = "",
    supervisor_latched: bool = False,
    session_supervision: bool = False,
    external_session_billing: bool = False,
    expected_mode: str | None = None,
    expected_identity_hash: str | None = None,
    return_raw_response: Literal[False] = False,
) -> str: ...


async def respond(
    *,
    speaker: Speaker,
    messages: list[dict[str, Any]],
    conversation_id: str,
    model: str,
    reasoning_effort: str,
    repeated_text: str = "",
    research_objective: str = "",
    supervisor_latched: bool = False,
    session_supervision: bool = False,
    external_session_billing: bool = False,
    expected_mode: str | None = None,
    expected_identity_hash: str | None = None,
    return_raw_response: bool = False,
) -> str | dict[str, Any]:
    """Generate one bounded agent turn and account hosted sponsored usage."""
    if len(messages) > MAX_MESSAGES or not messages:
        raise ProjectError(
            "The chat contains too many messages. Start a new conversation to continue."
        )
    if any(
        item.get("speaker") not in {"human", "ai_1", "ai_2", "supervisor"}
        or not isinstance(item.get("text"), str)
        or not item["text"].strip()
        for item in messages
    ):
        raise ProjectError("A chat message must contain nonempty text.")
    if not isinstance(repeated_text, str):
        raise ProjectError("Repeated text must be a string.")
    if session_supervision and speaker != "supervisor":
        raise ProjectError("Independent Session supervision requires the supervisor role.")
    if external_session_billing and (not session_supervision or not return_raw_response):
        raise ProjectError("Externally metered calls are permitted only for Session supervision.")

    credential = await auth_context()
    if session_supervision and (
        credential["mode"] != expected_mode
        or hashlib.sha256(credential["identity"].encode()).hexdigest() != expected_identity_hash
    ):
        raise ProjectError("The Session AI connection changed before supervisor dispatch.")
    is_personal = model_dispatch.uses_personal_worker(credential)
    if (not credential["token"] and not is_personal) or credential["status"] != "connected":
        raise ProjectError("Connect ChatGPT or select API-key billing before starting a chat.")
    if model not in CATALOG:
        raise ProjectError("The selected chat model is unavailable.")
    try:
        validate_pair(model, reasoning_effort)
    except ValueError as exc:
        raise ProjectError(str(exc)) from exc
    discovery = await models(context=credential)
    if discovery["connection"].get("status") != "connected":
        raise ProjectError(discovery["connection"].get("guidance", "AI connection unavailable."))
    if not any(
        item["id"] == model and item["availability"] == "available" for item in discovery["models"]
    ):
        raise ProjectError("The selected model is unavailable to this AI account.")
    if cloud_workspaces.enabled() and not is_personal and not cloud_credential(credential):
        raise ProjectError("Sponsored chat is not configured for this account.")

    transcript = _transcript(messages, speaker)
    if research_objective.strip():
        transcript = f"Research Objective:\n{research_objective.strip()}\n\n{transcript}"
    elif speaker == "supervisor":
        raise ProjectError("Supervisor requires the research objective.")
    if speaker == "supervisor":
        transcript = (
            f"Previous breakthrough milestone active: {supervisor_latched}.\n\n" + transcript
        )
    payload: dict[str, Any] = {
        "model": model,
        "store": False,
        "max_output_tokens": MAX_OUTPUT_TOKENS,
        "reasoning": {"effort": reasoning_effort},
        "instructions": (
            session_supervisor.INSTRUCTIONS if session_supervision else INSTRUCTIONS[speaker]
        ),
        "input": [
            {
                "role": "user",
                "content": (
                    f"{repeated_text.strip()}\n\n{transcript}"
                    if repeated_text.strip()
                    else transcript
                ),
            }
        ],
    }
    if credential["mode"] == "chatgpt":
        payload.pop("max_output_tokens")
        payload["stream"] = True
    guard = hashlib.sha256((credential["mode"] + credential["token"]).encode()).hexdigest()
    attempt = None
    response_data: Mapping[str, Any] | None = None
    try:
        if cloud_research.billing_enabled() and not is_personal and not external_session_billing:
            workspace = cloud_research._ledger_workspace()
            if workspace is None:
                raise ProjectError("The sponsored chat workspace is unavailable.")
            attempt = cloud_research.start_provider_attempt(
                conversation_id,
                str(workspace.path),
                model,
                payload,
                MAX_OUTPUT_TOKENS,
            )
        if attempt is not None:
            attempt.dispatched = True
        personal_raw = await model_dispatch.private_response_if_selected(
            credential, payload, timeout_seconds=TIMEOUT_SECONDS
        )
        if personal_raw is not None:
            response_data = personal_raw
            if not return_raw_response:
                text = _response_text(personal_raw, model)
        else:
            async with (
                asyncio.timeout(TIMEOUT_SECONDS),
                httpx.AsyncClient(
                    timeout=TIMEOUT_SECONDS,
                    follow_redirects=False,
                    trust_env=False,
                ) as client,
                client.stream(
                    "POST",
                    "https://api.openai.com/v1/responses",
                    headers={
                        "Authorization": "Bearer " + credential["token"],
                        **(
                            {"Accept": "text/event-stream"}
                            if credential["mode"] == "chatgpt"
                            else {}
                        ),
                    },
                    json=payload,
                ) as response,
            ):
                if credential["mode"] == "chatgpt" and response.status_code == 200:
                    raw = await completed(response, guard)
                else:
                    data = bytearray()
                    async for chunk in response.aiter_bytes():
                        data.extend(chunk)
                        if len(data) > MAX_RESPONSE_BYTES:
                            raise ProjectError("The AI response exceeded the size limit.")
                    try:
                        raw = json.loads(data)
                    except (ValueError, UnicodeDecodeError):
                        raw = {}
                    if response.status_code != 200:
                        failure(response.status_code, raw, credential["mode"], guard)
                if isinstance(raw, dict):
                    response_data = raw
                if not return_raw_response:
                    text = _response_text(raw, model)
        cloud_research.settle_provider_attempt(attempt, response_data)
        if return_raw_response:
            return dict(response_data or {})
        return text
    except asyncio.CancelledError:
        raise
    except (httpx.HTTPError, TimeoutError) as exc:
        from sigma.openai_connection import inference_failure

        inference_failure("unavailable", guard)
        raise ProjectError("The AI request timed out or the connection was interrupted.") from exc
    except (ValueError, TypeError, KeyError) as exc:
        # Do not hide deterministic transport/parser errors behind the same
        # generic message as a recoverable completed-response shape.
        import logging

        logging.getLogger(__name__).warning(
            "Brainstorm provider result could not be decoded (%s: %s)",
            type(exc).__name__,
            str(exc)[:160],
        )
        raise ProjectError(
            "The provider response could not be decoded. Your conversation was preserved; "
            "Retry the turn or select another Model/Thinking setting."
        ) from exc
    except cloud_research.CloudResearchUnavailable as exc:
        raise ProjectError(str(exc)) from exc
    finally:
        if attempt is not None:
            cloud_research.finish_provider_attempt(attempt)
