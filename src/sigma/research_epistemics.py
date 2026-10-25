"""Conservative presentation of saved research evidence, not a verification engine."""

from __future__ import annotations

from collections.abc import Mapping, Sequence
from typing import Any, Literal, TypedDict


class ArgumentAvailability(TypedDict):
    status: Literal["structured", "narrative", "not_recorded"]
    label: str


def verification_label(review: Mapping[str, Any] | None) -> str:
    """A saved declaration cannot supply independent checker provenance.

    SIGMA currently has no independent proof-verification service. In particular,
    accepting a legacy `verified` code must not imply that such a service ran.
    Keep the code intact; qualify its meaning in every human-readable projection.
    """
    value = review.get("verification_status") if review else None
    return {
        "incomplete": "Incomplete",
        "convincing_unverified": "Convincing but unverified",
        "verified": "Reported verified; not independently checked by SIGMA",
        "unknown": "Unknown",
        None: "Not recorded",
        "": "Not recorded",
    }.get(str(value) if value is not None else None, "Unknown")


def argument_availability(
    review: Mapping[str, Any] | None, artifacts: Sequence[Mapping[str, Any]] = ()
) -> ArgumentAvailability:
    """Describe the representation present, without judging its correctness.

    Nonempty prose is evidence of a saved narrative, not of a valid proof. No
    length heuristic, synthetic steps or inferred verification is appropriate.
    """
    review = review or {}
    if review.get("argument_steps"):
        return {
            "status": "structured",
            "label": "Structured argument steps are recorded; review their evidence and objections.",
        }
    narrative = any(
        isinstance(value, str) and bool(value.strip())
        for item in (review, *artifacts)
        for key in ("argument_summary", "method", "skeptic_response")
        for value in (item.get(key),)
    )
    if narrative:
        return {
            "status": "narrative",
            "label": (
                "Structured argument steps were not recorded; saved narrative is available "
                "for inspection in Reasoning / proof and the research artifacts. "
                "Its completeness and correctness remain unassessed."
            ),
        }
    return {
        "status": "not_recorded",
        "label": (
            "Structured argument steps and argument narrative were not recorded. "
            "Inspect any retained artifacts before assessing this claim."
        ),
    }
