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


class ChatGPTProviderRejection(ProjectError):
    """A classified provider error with real HTTP/stream provenance.

    The outer transport may be HTTP 200 even if a Responses SSE event
    reports a failed inference. Never synthesize an HTTP 400 for that case.
    """

    def __init__(
        self,
        message: str,
        *,
        state: str,
        code: str | None,
        http_status: int,
        streamed: bool,
        stream_event: str | None = None,
    ) -> None:
        super().__init__(message)
        self.state = state
        self.code = code if code in KNOWN_ERRORS else None
        self.http_status = http_status
        self.streamed = streamed
        # Only local parser event types are stored, never untrusted provider text.
        self.stream_event = (
            stream_event if streamed and stream_event in {"error", "response.failed"} else None
        )


def failure(
    status: int,
    raw: Any,
    mode: str,
    guard: str | None = None,
    *,
    streamed: bool = False,
    stream_event: str | None = None,
) -> None:
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
        # Strict-schema rejection is an actionable request defect, not an
        # account/plan failure. Expose only a locally allowlisted provider
        # error code, never the raw provider message or arbitrary parameters.
        if status == 400 and code == "invalid_json_schema":
            inference_failure("unavailable", guard)
            raise ChatGPTProviderRejection(
                "ChatGPT rejected SIGMA's structured-output schema "
                "(HTTP 400; provider code: invalid_json_schema). "
                "The account remains connected; no automatic retry or "
                "billing fallback occurred.",
                state="unavailable",
                code=None,
                http_status=status,
                streamed=streamed,
                stream_event=stream_event,
            )
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
            description = (
                f"ChatGPT returned an unclassified streamed error (HTTP transport {status}, "
                f"response shape: {shape}). "
                if streamed
                else f"ChatGPT rejected the request (HTTP {status}, response shape: {shape}). "
            )
            raise ChatGPTProviderRejection(
                description + "Account retained; no automatic billing fallback occurred.",
                state=state,
                code=code if isinstance(code, str) else None,
                http_status=status,
                streamed=streamed,
                stream_event=stream_event,
            )
        # A Responses stream is admitted at the outer HTTP status and can then
        # fail in-band; the provider error code is not a second HTTP response.
        safe_code = code if isinstance(code, str) and code in KNOWN_ERRORS else None
        if streamed:
            provenance = (
                f" Provider error code: {safe_code} ({stream_event or 'streamed response'}; "
                f"HTTP transport {status})."
                if safe_code
                else f" Provider error within streamed response (HTTP transport {status})."
            )
        else:
            provenance = f" (HTTP {status}"
            if safe_code:
                provenance += f"; provider code: {safe_code}"
            provenance += ")."
        if safe_code == "subscription_sharing_usage_limit_exceeded":
            provenance += (
                " This is separate from SIGMA's sponsored-dollar allowance. "
                "The provider did not identify whether its limit is plan-wide or app-specific."
            )
        raise ChatGPTProviderRejection(
            f"{message}{provenance} No strategy was saved.",
            state=state,
            code=safe_code,
            http_status=status,
            streamed=streamed,
            stream_event=stream_event,
        )
    # Provider error bodies can contain request context or other sensitive
    # values. Surface only a small allowlist of machine fields; never echo the
    # provider message or an arbitrary code/parameter into the UI.
    safe_codes = {
        "invalid_json_schema",
        "invalid_request_error",
        "invalid_parameter",
        "unsupported_parameter",
        "unsupported_value",
        "model_not_found",
        "model_access_denied",
        "insufficient_quota",
        "billing_hard_limit_reached",
    }
    safe_params = {
        "text.format",
        "text.format.schema",
        "reasoning.effort",
        "max_output_tokens",
        "model",
    }
    safe_code = code if isinstance(code, str) and code in safe_codes else None
    param = error.get("param") if isinstance(error, dict) else None
    safe_param = param if isinstance(param, str) and param in safe_params else None
    if safe_code in {
        "invalid_json_schema",
        "invalid_request_error",
        "invalid_parameter",
        "unsupported_parameter",
        "unsupported_value",
    }:
        diagnosis = "The provider rejected a request parameter or structured-output schema."
    elif safe_code in {"model_not_found", "model_access_denied"}:
        diagnosis = "The provider rejected access to the selected model."
    elif safe_code in {"insufficient_quota", "billing_hard_limit_reached"}:
        diagnosis = "The provider reported an API billing or quota limit."
    else:
        diagnosis = "The provider rejected the request; the cause is not classified."
    details = []
    if safe_code:
        details.append(f"code={safe_code}")
    if safe_param:
        details.append(f"param={safe_param}")
    detail_text = f" ({', '.join(details)})" if details else ""
    raise ProjectError(
        f"OpenAI API request failed (HTTP {status}): {diagnosis}{detail_text} "
        "No automatic retry or billing fallback occurred; no paper was saved."
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
            if kind == "error":
                # Responses SSE errors wrap the provider error in an `error`
                # event envelope. Normalize it to the JSON error shape used
                # by the non-streaming path so safe codes (including ChatGPT
                # plan routing codes) are classified consistently.
                raw_error = event.get("error")
                failure(
                    response.status_code,
                    {"error": raw_error} if isinstance(raw_error, dict) else {"error": event},
                    "chatgpt",
                    guard,
                    streamed=True,
                    stream_event="error",
                )
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
                    failure(
                        response.status_code,
                        raw,
                        "chatgpt",
                        guard,
                        streamed=True,
                        stream_event="response.failed",
                    )
                if kind == "response.incomplete":
                    raise ProjectError(
                        "ChatGPT returned an incomplete response. Retry explicitly; no strategy was saved."
                    )
                if raw.get("status") != "completed" or refused:
                    raise ProjectError(
                        "ChatGPT declined or did not complete this proposal; no strategy was saved."
                    )
                terminal = raw
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
