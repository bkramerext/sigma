"""Bind a reported computational inference to actual supplied execution output.

Hash equality establishes receipt of exact displayed output, not mathematical
validity. Failed execution can support only an inconclusive/limitation report.
"""

import hashlib
from typing import Any

from pydantic import BaseModel, ConfigDict, Field

from sigma.projects import ProjectError


class ComputationFeedback(BaseModel):
    model_config = ConfigDict(extra="forbid", strict=True)
    research_artifact_id: str | None
    execution_id: str = Field(min_length=1, max_length=100)
    observed_status: str = Field(min_length=1, max_length=40)
    observed_field: str = Field(pattern="^(stdout|stderr)$")
    observed_text_sha256: str = Field(min_length=64, max_length=64)
    reported_effect: str = Field(pattern="^(counterexample|bounded_support|inconclusive)$")
    next_test: str = Field(min_length=10, max_length=1000)


def validate_feedback(
    feedback: dict[str, Any] | None,
    citations: list[dict[str, Any]],
    targets: list[dict[str, Any]],
    *,
    next_question: str,
    assessment: str,
) -> None:
    if feedback is None:
        return  # Legacy and non-computational research make no structured assertion.
    target = next(
        (
            row["execution"]
            for row in targets
            if row["research_artifact_id"] == feedback["research_artifact_id"]
            and row["execution"]["id"] == feedback["execution_id"]
        ),
        None,
    )
    if target is None:
        raise ProjectError(
            "Computational feedback requires execution evidence supplied in this call"
        )
    text = target.get(feedback["observed_field"])
    if (
        not isinstance(text, str)
        or hashlib.sha256(text.encode()).hexdigest() != feedback["observed_text_sha256"]
        or feedback["observed_status"] != target.get("status")
    ):
        raise ProjectError(
            "Computational feedback does not match the observed execution status/output"
        )
    matching = [
        row
        for row in citations
        if row["execution_id"] == feedback["execution_id"]
        and row["research_artifact_id"] == feedback["research_artifact_id"]
    ]
    if not matching:
        raise ProjectError("Computational feedback requires a linked computation citation")
    if feedback["reported_effect"] != "inconclusive":
        if feedback["observed_field"] != "stdout":
            raise ProjectError(
                "Warnings/errors cannot establish a computational counterexample/support"
            )
        if target.get("status") != "completed" or target.get("exit_code") != 0 or not text.strip():
            raise ProjectError(
                "A failed, missing or empty computation cannot establish a counterexample/support"
            )
        expected_evidence = "output" if feedback["observed_field"] == "stdout" else "error"
        if not any(
            row["use"] == "result" and row["evidence"] == expected_evidence for row in matching
        ):
            raise ProjectError(
                "A reported computational result requires a citation to that exact output"
            )
    if assessment in {"continue", "revise"} and next_question != feedback["next_test"]:
        raise ProjectError(
            "The next dispatched question must match the evidence-linked computational follow-up"
        )
