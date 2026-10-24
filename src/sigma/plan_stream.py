"""Bounded Responses SSE completion; no partial draft counts as a result."""

import codecs
import json
from typing import Any

import httpx

from sigma.openai_connection import inference_failure
from sigma.projects import ProjectError

MAX_STREAM_BYTES = 1000000
MAX_EVENTS = 4096
KNOWN_ERRORS = {
    "subscription_sharing_usage_limit_exceeded": (
        "limited",
        "ChatGPT plan or app usage limit reached. Manage usage at https://chatgpt.com/settings/usage; no API-key fallback occurred.",
    ),
    "subscription_sharing_user_not_eligible": (
        "forbidden",
        "ChatGPT plan use is unavailable for this account/workspace/policy. Choose another billing mode or reconnect an eligible account.",
    ),
    "subscription_sharing_unsupported_capability": (
        "forbidden",
        "This ChatGPT-plan route does not support the requested model/structured-output/reasoning capability. Change settings explicitly; no retry or fallback occurred.",
    ),
    "subscription_sharing_route_not_supported": (
        "forbidden",
        "This ChatGPT-plan route is not enabled for the selected integration. No fallback occurred.",
    ),
    "subscription_sharing_invalid_user": (
        "unauthorized",
        "ChatGPT authorization was not accepted. Reconnect the selected account.",
    ),
    "chatpass_v2_scope_not_authorized": (
        "plan_not_permitted",
        "ChatGPT plan permission does not authorize this operation. Enable plan use for this account.",
    ),
    "chatpass_v2_invalid_authorization_context": (
        "plan_not_permitted",
        "ChatGPT authorization context was not accepted. Reconnect the selected account.",
    ),
    "subscription_sharing_usage_unavailable": (
        "unavailable",
        "ChatGPT usage availability could not be checked. Account retained; retry later.",
    ),
    "subscription_sharing_user_unavailable": (
        "unavailable",
        "ChatGPT account/workspace is temporarily unavailable. Account retained; retry later.",
    ),
}


def failure(status: int, raw: Any, mode: str, guard: str | None = None) -> None:
    error = raw.get("error") if isinstance(raw, dict) else None
    code = error.get("code") if isinstance(error, dict) else None
    # Direct-route admission errors can have {"detail": "..."} rather
    # than the conventional nested {"error": {"code": ...}} envelope.
    shape = "unknown"
    if isinstance(raw, dict):
        if isinstance(error, dict):
            shape = "responses-error"
        elif isinstance(raw.get("detail"), str):
            shape = "admission-detail"
        elif isinstance(error, str):
            shape = "error-string"
        elif raw.get("type") == "error":
            shape = "top-level-error"
        else:
            shape = "other-object"
    if mode == "chatgpt":
        state, message = KNOWN_ERRORS.get(
            code if isinstance(code, str) else "",
            {
                401: (
                    "unauthorized",
                    "ChatGPT authorization or plan permission was not accepted. Reconnect the selected account.",
                ),
                403: (
                    "forbidden",
                    "ChatGPT plan/workspace/region policy denied this request. Check account permissions.",
                ),
                429: (
                    "limited",
                    "ChatGPT plan or app usage is limited. Manage usage at https://chatgpt.com/settings/usage.",
                ),
            }.get(
                status,
                (
                    "unavailable",
                    "ChatGPT request could not complete. Account retained; retry explicitly later.",
                ),
            ),
        )
        inference_failure(state, guard)
        # Provider fields can echo credentials or user data, including fields
        # that look like machine metadata. Report only locally derived status
        # and response shape.
        if state == "unavailable" and message.startswith("ChatGPT request could not complete"):
            raise ProjectError(
                f"ChatGPT rejected the request (HTTP {status}, response shape: {shape}). "
                "Account retained; no automatic billing fallback occurred."
            )
        raise ProjectError(f"{message} No strategy was saved.")
    raise ProjectError(
        f"OpenAI API request failed (HTTP {status}). Check API model permissions or separate API billing; no fallback or strategy save occurred."
    )


async def completed(
    response: httpx.Response,
    guard: str | None = None,
    *,
    max_stream_bytes: int = MAX_STREAM_BYTES,
    overflow_message: str = "Provider stream exceeded the byte limit; no strategy was saved.",
) -> dict:
    content_type = response.headers.get("content-type", "")
    ct_main = content_type.split(";")[0].strip().lower()
    if ct_main not in {"", "text/event-stream"}:
        raise ValueError(f"plan_stream:content_type({content_type!r})")
    decoder = codecs.getincrementaldecoder("utf-8")("strict")
    buffer = ""
    byte_count = event_count = 0
    sequence = -1
    response_id = None
    terminal = None
    deltas = ""
    refused = False
    async for chunk in response.aiter_bytes():
        byte_count += len(chunk)
        if byte_count > max_stream_bytes:
            raise ProjectError(overflow_message)
        buffer += decoder.decode(chunk)
        buffer = buffer.replace("\r\n", "\n")
        while "\n\n" in buffer:
            block, buffer = buffer.split("\n\n", 1)
            data = "\n".join(
                line[5:].lstrip(" ") for line in block.split("\n") if line.startswith("data:")
            )
            if not data:
                continue
            if data == "[DONE]":
                if terminal is None:
                    raise ValueError("plan_stream:done_before_terminal")
                continue
            event_count += 1
            if event_count > MAX_EVENTS or terminal is not None:
                raise ValueError("plan_stream:event_after_terminal")
            event = json.loads(data)
            kind = event.get("type")
            seq = event.get("sequence_number")
            if (
                not isinstance(kind, str)
                or not isinstance(seq, int)
                or isinstance(seq, bool)
                or seq <= sequence
            ):
                raise ValueError(f"plan_stream:seq(kind={kind},seq={seq},expected>{sequence})")
            sequence = seq
            declared = [line[6:].strip() for line in block.split("\n") if line.startswith("event:")]
            if declared and declared != [kind]:
                raise ValueError(f"plan_stream:declared_event({declared}!=[{kind}])")
            if kind == "response.created":
                if response_id is not None or not isinstance(
                    event.get("response", {}).get("id"), str
                ):
                    raise ValueError("plan_stream:created_id")
                response_id = event["response"]["id"]
            elif response_id is None:
                raise ValueError(f"plan_stream:no_id_before_{kind}")
            if kind in {"response.completed", "response.failed", "response.incomplete"}:
                raw = event.get("response")
                if not isinstance(raw, dict) or raw.get("id") != response_id:
                    raise ValueError("plan_stream:response_id_mismatch")
                if kind == "response.failed":
                    failure(400, raw, "chatgpt", guard)
                if kind == "response.incomplete":
                    raise ProjectError(
                        "ChatGPT returned an incomplete response. Retry explicitly; no strategy was saved."
                    )
                if raw.get("status") != "completed" or refused:
                    raise ProjectError(
                        "ChatGPT declined or did not complete this proposal; no strategy was saved."
                    )
                terminal = raw
            elif kind == "error":
                failure(400, {"error": event}, "chatgpt", guard)
            elif kind == "response.output_text.delta":
                if not isinstance(event.get("delta"), str):
                    raise ValueError("plan_stream:delta_not_str")
                deltas += event["delta"]
            elif kind.startswith("response.refusal."):
                refused = True
    buffer += decoder.decode(b"", final=True)
    if buffer.strip() or terminal is None:
        raise ProjectError(
            "ChatGPT stream ended without a valid response.completed. No strategy was saved."
        )
    if deltas:
        # Some streaming adapters provide the complete text only through
        # response.output_text.delta events and omit it from the terminal
        # response's output array. Reconstruct that missing field rather than
        # declaring a successfully completed stream malformed. Never replace
        # or override conflicting final text.
        items = terminal.get("output", [])
        if not isinstance(items, list):
            raise ValueError("plan_stream:invalid_terminal_output")
        texts = [
            content.get("text", "")
            for item in items
            if isinstance(item, dict) and isinstance(item.get("content", []), list)
            for content in item.get("content", [])
            if isinstance(content, dict) and content.get("type") == "output_text"
        ]
        if texts and texts != [deltas]:
            raise ValueError(
                f"plan_stream:delta_text_mismatch(len_texts={len(texts)},len_delta={len(deltas)})"
            )
        if not texts:
            terminal = {
                **terminal,
                "output": [
                    *items,
                    {"type": "message", "content": [{"type": "output_text", "text": deltas}]},
                ],
            }
    return terminal
