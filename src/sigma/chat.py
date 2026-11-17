"""Ephemeral two-agent chat using SIGMA's selected OpenAI connection."""

import asyncio
import hashlib
import json
from collections.abc import Mapping
from typing import Any, Literal

import httpx

from sigma import cloud_research, cloud_workspaces, model_dispatch
from sigma.model_catalog import CATALOG, DEFAULT_MODEL, validate_pair
from sigma.openai_connection import auth_context, cloud_credential, models
from sigma.plan_stream import completed, failure
from sigma.projects import ProjectError

MAX_MESSAGES = 80
MAX_CONTEXT_CHARS = 48000
MAX_OUTPUT_TOKENS = 1200
TIMEOUT_SECONDS = 60
MAX_RESPONSE_BYTES = 1_000_000
Speaker = Literal["ai_1", "ai_2", "supervisor"]

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
        "Build on ideas, introduce independent perspectives, and disagree constructively "
        "when warranted. Keep your reply concise enough to support an ongoing exchange."
    ),
    "supervisor": (
        "You are SIGMA's metacognitive research supervisor, not a third research participant. "
        "Your sole job is to monitor the health, independence, clarity and productivity of "
        "a dialogue between two equally autonomous AIs in pursuit of the human's Research Objective. "
        "You MUST NOT provide research ideas, subject-matter feedback, factual corrections, "
        "methods, proofs, examples from the discipline, or suggested substantive conclusions. "
        "Help them articulate THEIR OWN ideas: occasionally prompt clearer claims, assumptions, "
        "evidence, uncertainty, or precise disagreement, like an art teacher supporting a "
        "student's creativity without telling them what to create. Recognize self-correction, "
        "useful patient exploration, valuable detours, and genuinely new progress. Do not "
        "confuse slow progress with stagnation, or mathematical sophistication with discovery. "
        "Notice anchoring, fixation, unjustified confidence, circularity, lost promising threads, "
        "unbalanced initiative, and preparation substituting for execution. "
        "Review the broader trajectory. Prefer silence; small clarity nudges can be more frequent "
        "than substantive redirections, but only intervene when likely beneficial. "
        "Address ai_1, ai_2 or both explicitly, never take ownership of the research. "
        "Score current research progress toward the objective using a domain-neutral rubric: "
        "objective_alignment 0-1.5, originality 0-2, substantive_advancement 0-3, "
        "evidence_validation 0-2.5, research_momentum 0-1. "
        "Scores may rise, fall or remain steady; neither agreement nor passage of time earns points. "
        "A credible, consequential and supported breakthrough candidate may trigger a special "
        "10.0 milestone, but this is NOT independent proof or validation. "
        "If a prior candidate is decisively invalidated, indicate that. "
        "Return ONLY a JSON object with fields: "
        "rubric (object containing the five numeric dimensions named above), "
        "assessment (brief process/progress assessment, no research ideas), "
        "action (continue, nudge, or redirect), recipients (array of ai_1 and/or ai_2), "
        "guidance (exact short process-only instruction to deliver, empty when continuing), "
        "breakthrough_candidate (boolean), breakthrough_invalidated (boolean). "
        "A breakthrough must be more than an interesting proposal, reformulation, or plausible claim. "
        "Do not manufacture interventions or a breakthrough to please the human."
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


def _transcript(messages: list[dict[str, Any]], audience: Speaker = "supervisor") -> str:
    """Use authentic participant text; deliver supervisor guidance only to its recipients.

    Scores and private assessments never enter the two participants' prompts.
    """
    recent: list[str] = []
    current_chars = 0
    for item in reversed(messages[-MAX_MESSAGES:]):
        speaker = item["speaker"]
        if speaker == "supervisor":
            if audience != "supervisor":
                if audience not in item.get("recipients", []):
                    continue
                guidance = item.get("guidance", "")
                if not guidance:
                    continue
                rendered = f"Supervisor to {audience.upper()}:\n{guidance}"
            else:
                rendered = f"Supervisor assessment:\n{item['text']}"
        else:
            label = {"human": "Human", "ai_1": "AI #1", "ai_2": "AI #2"}.get(speaker)
            if label is None:
                continue
            rendered = f"{label}:\n{item['text']}"
        extra_chars = len(rendered) + (2 if recent else 0)
        if recent and current_chars + extra_chars > MAX_CONTEXT_CHARS:
            break
        recent.append(rendered)
        current_chars += extra_chars
    recent.reverse()
    result = "\n\n".join(recent)
    if len(messages) > len(recent):
        result = "[Earlier conversation turns may be omitted to fit the message limit.]\n\n" + result
    return result


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
    messages: list[dict[str, Any]],
    conversation_id: str,
    expected_binding: str,
    model: str,
    reasoning_effort: str,
    research_objective: str = "",
    supervisor_latched: bool = False,
) -> str:
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
    if not isinstance(research_objective, str):
        raise ProjectError("Research Objective must be a string.")

    credential = await auth_context()
    is_personal = model_dispatch.uses_personal_worker(credential)
    if (not credential["token"] and not is_personal) or credential["status"] != "connected":
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
    if cloud_workspaces.enabled() and not is_personal and not cloud_credential(credential):
        raise ProjectError("Sponsored chat is not configured for this account.")

    transcript = _transcript(messages, audience=speaker)
    objective = research_objective.strip()
    prefix = f"Research Objective:\n{objective}\n\n" if objective else ""
    if speaker == "supervisor":
        prefix += f"Breakthrough milestone currently active: {supervisor_latched}.\n\n"
    payload: dict[str, Any] = {
        "model": model,
        "store": False,
        "max_output_tokens": MAX_OUTPUT_TOKENS,
        "reasoning": {"effort": reasoning_effort},
        "instructions": INSTRUCTIONS[speaker],
        "input": [
            {
                "role": "user",
                "content": prefix + transcript,
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
        if cloud_research.billing_enabled() and not is_personal:
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

RUBRIC_MAXIMA = {
    "objective_alignment": 1.5,
    "originality": 2.0,
    "substantive_advancement": 3.0,
    "evidence_validation": 2.5,
    "research_momentum": 1.0,
}


async def assess(
    *,
    messages: list[dict[str, Any]],
    research_objective: str,
    supervisor_latched: bool,
    conversation_id: str,
    expected_binding: str,
    model: str,
    reasoning_effort: str,
) -> dict[str, Any]:
    """Return a domain-neutral review; do not let the supervisor steer subject matter."""
    raw = await respond(
        speaker="supervisor",
        messages=messages,
        research_objective=research_objective,
        supervisor_latched=supervisor_latched,
        conversation_id=conversation_id,
        expected_binding=expected_binding,
        model=model,
        reasoning_effort=reasoning_effort,
    )
    try:
        parsed = json.loads(raw.removeprefix("```json").removeprefix("```").removesuffix("```").strip())
        rubric = parsed["rubric"]
        if not isinstance(rubric, dict):
            raise ValueError("rubric")
        scores: dict[str, float] = {}
        for key, maximum in RUBRIC_MAXIMA.items():
            val = rubric[key]
            if isinstance(val, bool) or not isinstance(val, (int, float)):
                raise ValueError(key)
            value = float(val)
            if not 0 <= value <= maximum:
                raise ValueError(key)
            scores[key] = round(value, 2)
        action = parsed["action"]
        if action not in {"continue", "nudge", "redirect"}:
            raise ValueError("action")
        recipients = parsed["recipients"]
        if not isinstance(recipients, list) or any(r not in {"ai_1", "ai_2"} for r in recipients):
            raise ValueError("recipients")
        recipients = list(dict.fromkeys(recipients))
        guidance = parsed["guidance"]
        assessment = parsed["assessment"]
        if not isinstance(guidance, str) or not isinstance(assessment, str) or not assessment.strip():
            raise ValueError("guidance/assessment")
        if len(guidance) > 1800 or len(assessment) > 1800:
            raise ValueError("length")
        candidate = parsed["breakthrough_candidate"]
        invalidated = parsed["breakthrough_invalidated"]
        if not isinstance(candidate, bool) or not isinstance(invalidated, bool):
            raise ValueError("milestone")
        if action == "continue":
            guidance, recipients = "", []
        elif not recipients or not guidance.strip():
            raise ValueError("targeted guidance")
        if candidate and invalidated:
            raise ValueError("contradictory milestone")
    except (KeyError, TypeError, ValueError, AttributeError) as exc:
        raise ProjectError("The supervisor returned an invalid assessment; the conversation can continue.") from exc
    latched = (supervisor_latched and not invalidated) or candidate
    score = 10.0 if latched else min(9.9, round(sum(scores.values()), 1))
    recipient_labels = [("AI #1" if r == "ai_1" else "AI #2") for r in recipients]
    result: dict[str, Any] = {
        "speaker": "supervisor",
        "score": score,
        "rubric": scores,
        "action": action,
        "recipients": recipients,
        "guidance": guidance.strip(),
        "assessment": assessment.strip(),
        "breakthrough_candidate": candidate,
        "breakthrough_invalidated": invalidated,
        "milestone_latched": latched,
    }
    lines = [
        f"**Research progress:** {score:.1f} / 10.0",
        f"**Assessment:** {result['assessment']}",
        f"**Action:** {action.title()}",
    ]
    if recipients:
        lines += [
            f"**To:** {', '.join(recipient_labels)}",
            f"**Direction:** {result['guidance']}",
        ]
    if latched:
        lines.append("**Potential breakthrough detected — 10.0 milestone (validation required).**")
    elif invalidated:
        lines.append("**Previous breakthrough candidate invalidated; normal scoring resumed.**")
    lines.append(
        "**Rubric:** " + "; ".join(f"{key}: {value:g}/{RUBRIC_MAXIMA[key]:g}" for key, value in scores.items())
    )
    result["text"] = "\n\n".join(lines)
    return result
