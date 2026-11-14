"""Ephemeral two-agent chat using SIGMA's selected OpenAI connection."""

import asyncio
import hashlib
import json
from collections.abc import Mapping
from typing import Any, Literal

import httpx

from sigma import cloud_research, cloud_workspaces
from sigma.model_catalog import CATALOG, DEFAULT_MODEL, validate_pair
from sigma.openai_connection import auth_context, cloud_credential, models
from sigma.plan_stream import completed, failure
from sigma.projects import ProjectError

MAX_MESSAGES = 80
MAX_CONTEXT_CHARS = 48000
MAX_OUTPUT_TOKENS = 1200
TIMEOUT_SECONDS = 60
MAX_RESPONSE_BYTES = 1_000_000
Speaker = Literal["ai_1", "ai_2"]

INSTRUCTIONS: dict[Speaker, str] = {
    "ai_1": (
        "You are AI #1 in a live conversation with a human and AI #2. Respond to the latest "
        "conversation naturally and clearly. Treat the transcript as conversation context. "
        "Build on ideas, ask focused questions, and distinguish facts from uncertainty. Keep "
        "your reply concise enough to support an ongoing exchange."
    ),
    "ai_2": (
        "You are AI #2 in a live conversation with a human and AI #1. Reply to the latest "
        "conversation naturally and clearly. Treat the transcript as conversation context. "
        "Engage with AI #1's reasoning, add a useful perspective, and disagree constructively "
        "when warranted. Keep your reply concise enough to support an ongoing exchange."
    ),
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
        and bool(credential["token"])
        and discovery.get("default_verified") is True
        and model in CATALOG
    )
    if cloud_workspaces.enabled() and not cloud_credential(credential):
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


def _transcript(messages: list[dict[str, str]]) -> str:
    recent: list[dict[str, str]] = []
    current_chars = 0
    for item in reversed(messages[-MAX_MESSAGES:]):
        rendered_item = (
            f"{ {'human': 'Human', 'ai_1': 'AI #1', 'ai_2': 'AI #2'}[item['speaker']] }:\n"
            f"{item['text']}"
        )
        extra_chars = len(rendered_item) + (2 if recent else 0)
        if recent and current_chars + extra_chars > MAX_CONTEXT_CHARS:
            break
        recent.append({**item, "rendered": rendered_item})
        current_chars += extra_chars
    recent.reverse()
    rendered = "\n\n".join(item["rendered"] for item in recent)
    if len(recent) < len(messages):
        rendered = "[Earlier conversation turns omitted to fit the message limit.]\n\n" + rendered
    return rendered


def _response_text(raw: Any, model: str) -> str:
    if not isinstance(raw, dict) or raw.get("status") != "completed":
        raise ProjectError("The AI did not complete its turn.")
    if raw.get("model") != model:
        raise ProjectError("The AI returned an unexpected model; no message was added.")
    output = raw.get("output")
    if not isinstance(output, list):
        raise ProjectError("The AI returned an invalid response; no message was added.")
    content = [
        part
        for item in output
        if isinstance(item, dict) and item.get("type") == "message"
        for part in item.get("content", [])
        if isinstance(part, dict)
    ]
    if any(part.get("type") == "refusal" for part in content):
        raise ProjectError("The AI declined this turn.")
    result = "\n".join(
        part["text"]
        for part in content
        if part.get("type") == "output_text" and isinstance(part.get("text"), str)
    ).strip()
    if not result or len(result) > MAX_RESPONSE_BYTES:
        raise ProjectError("The AI returned an empty or oversized message.")
    return result


async def respond(
    *,
    speaker: Speaker,
    messages: list[dict[str, str]],
    conversation_id: str,
    expected_binding: str,
    model: str,
    reasoning_effort: str,
    repeated_text: str = "",
) -> str:
    """Generate one bounded agent turn and account hosted sponsored usage."""
    if len(messages) > MAX_MESSAGES or not messages:
        raise ProjectError(
            "The chat contains too many messages. Start a new conversation to continue."
        )
    if any(
        item.get("speaker") not in {"human", "ai_1", "ai_2"}
        or not isinstance(item.get("text"), str)
        or not item["text"].strip()
        for item in messages
    ):
        raise ProjectError("A chat message must contain nonempty text.")
    if not isinstance(repeated_text, str):
        raise ProjectError("Repeated text must be a string.")

    credential = await auth_context()
    if not credential["token"] or credential["status"] != "connected":
        raise ProjectError("Connect ChatGPT or select API-key billing before starting a chat.")
    if credential["identity"] != expected_binding:
        raise ProjectError("The selected AI account changed. Review the connection and retry.")
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
    if cloud_workspaces.enabled() and not cloud_credential(credential):
        raise ProjectError("Sponsored chat is not configured for this account.")

    transcript = _transcript(messages)
    payload: dict[str, Any] = {
        "model": model,
        "store": False,
        "max_output_tokens": MAX_OUTPUT_TOKENS,
        "reasoning": {"effort": reasoning_effort},
        "instructions": INSTRUCTIONS[speaker],
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
        if cloud_research.billing_enabled():
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
                    **({"Accept": "text/event-stream"} if credential["mode"] == "chatgpt" else {}),
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
            text = _response_text(raw, model)
        cloud_research.settle_provider_attempt(attempt, response_data)
        return text
    except asyncio.CancelledError:
        raise
    except (httpx.HTTPError, TimeoutError) as exc:
        from sigma.openai_connection import inference_failure

        inference_failure("unavailable", guard)
        raise ProjectError("The AI request timed out or the connection was interrupted.") from exc
    except (ValueError, TypeError, KeyError) as exc:
        raise ProjectError("The AI returned an invalid response; no message was added.") from exc
    except cloud_research.CloudResearchUnavailable as exc:
        raise ProjectError(str(exc)) from exc
    finally:
        if attempt is not None:
            cloud_research.finish_provider_attempt(attempt)
