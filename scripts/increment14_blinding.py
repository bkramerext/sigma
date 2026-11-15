"""Normalize the two arms to a shared, identity-neutral scoring artifact.

This is a deterministic offline transformer. It does not establish that graders
are blind; the runner must keep arm maps and provenance outside scorer access.
"""

from __future__ import annotations

import hashlib
import json
import re
import secrets
from typing import Any

FIELDS = {
    "conclusion": 2000,
    "reasoning": 3000,
    "challenge": 2500,
    "evidence": 2000,
    "uncertainty": 1500,
    "next_test": 1000,
}
ROLE_LANGUAGE = re.compile(r"\b(?:SIGMA|Investigator|Skeptic|baseline|arm\s*[AB])\b", re.IGNORECASE)


def _text(value: Any) -> str:
    if isinstance(value, list):
        value = "\n".join(str(item) for item in value)
    elif not isinstance(value, str):
        value = "" if value is None else str(value)
    return re.sub(r"\s+", " ", value).strip()


def _remove_identity_words(value: str) -> str:
    return ROLE_LANGUAGE.sub("research process", value)


def _from_sigma(raw: dict[str, Any]) -> dict[str, Any]:
    investigator = raw.get("investigator_output", {})
    skeptic = raw.get("skeptic_output", {})
    if not isinstance(investigator, dict) or not isinstance(skeptic, dict):
        raise TypeError("Malformed structured submission")
    return {
        "conclusion": skeptic.get("solution_claim") or investigator.get("claim"),
        "reasoning": " ".join(
            filter(
                None, (_text(investigator.get("method")), _text(skeptic.get("argument_summary")))
            )
        ),
        "challenge": skeptic.get("response") or skeptic.get("objections"),
        "evidence": investigator.get("evidence_status"),
        "uncertainty": skeptic.get("remaining_obligations") or investigator.get("open_obligations"),
        "next_test": skeptic.get("next_question"),
    }


def normalize_submission(
    raw: dict[str, Any] | str,
    *,
    arm: str,
    upstream_truncation_fields: list[str] | None = None,
) -> dict[str, Any]:
    """Return the fixed common form; retain clipping as an explicit outcome flag.

    Both arms must be instructed to emit this same six-field contract. For the
    structured workflow, `raw` is assembled from its final Investigator and
    Skeptic records. For the single-role workflow, `raw` is parsed JSON with
    the same six keys. Long fields are clipped identically and flagged; callers
    must score them as submitted, never drop the pair.
    """
    if arm not in {"sigma", "single_role"}:
        raise ValueError("Unknown arm")
    if isinstance(raw, str):
        try:
            parsed = json.loads(raw)
        except json.JSONDecodeError as exc:
            raise ValueError("Submission must be valid JSON in the shared contract") from exc
        if not isinstance(parsed, dict):
            raise TypeError("Submission must be a JSON object")
        raw = parsed
    values = _from_sigma(raw) if arm == "sigma" else raw
    if set(values) != set(FIELDS):
        raise ValueError("Submission must contain exactly the common six fields")

    result: dict[str, Any] = {"schema": "sigma-blind-submission-v1"}
    role_field_map = {
        "claim": "conclusion",
        "solution_claim": "conclusion",
        "method": "reasoning",
        "argument_summary": "reasoning",
        "response": "challenge",
        "objections": "challenge",
        "evidence_status": "evidence",
        "computational_citations": "evidence",
        "open_obligations": "uncertainty",
        "remaining_obligations": "uncertainty",
        "next_question": "next_test",
    }
    normalized_upstream_fields = [
        role_field_map.get(field.rsplit(".", 1)[-1], field)
        for field in (upstream_truncation_fields or [])
    ]
    clipped = (
        sorted(FIELDS)
        if any(field not in FIELDS for field in normalized_upstream_fields)
        else sorted(set(normalized_upstream_fields))
    )
    for field, limit in FIELDS.items():
        value = _remove_identity_words(_text(values[field]))
        if len(value) > limit:
            value = value[:limit].rstrip()
            clipped.append(field)
        result[field] = value
    result["clipped_fields"] = sorted(set(clipped))
    return result


def digest_submission(submission: dict[str, Any]) -> str:
    payload = json.dumps(submission, ensure_ascii=False, sort_keys=True, separators=(",", ":"))
    return hashlib.sha256(payload.encode("utf-8")).hexdigest()


def scorer_packet(anonymous_id: str, submission: dict[str, Any]) -> dict[str, Any]:
    """Strip execution metadata before a scorer sees a submission."""
    if not anonymous_id or not isinstance(submission, dict):
        raise ValueError("Invalid scorer packet")
    if submission.get("schema") != "sigma-blind-submission-v1":
        raise ValueError("Submission is not normalized")
    visible = {
        key: value for key, value in submission.items() if key not in {"schema", "clipped_fields"}
    }
    for field in submission.get("clipped_fields", []):
        visible[field] += " [shared field limit reached; remainder omitted]"
    return {"submission_id": anonymous_id, "submission": visible}


def new_scorer_packet(submission: dict[str, Any]) -> tuple[str, dict[str, Any]]:
    """Create a fresh random scorer ID; retain the returned mapping privately."""
    anonymous_id = secrets.token_urlsafe(12)
    return anonymous_id, scorer_packet(anonymous_id, submission)
