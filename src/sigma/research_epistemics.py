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


def execution_provenance(record: Mapping[str, Any]) -> dict[str, Any]:
    """Inventory persisted tool execution, never infer it from authored prose.

    Deduplicate the same execution seen in a step and its resulting artifact.
    Missing IDs and conflicting statuses remain explicit rather than becoming
    successful observations. This is an inventory, not a claim-evidence checker.
    """
    rows: dict[tuple[str, str], dict[str, Any]] = {}
    unidentified = 0

    def collect(value: Any, runtime: str, artifact_id: str = "", step_id: str = "") -> None:
        nonlocal unidentified
        if not isinstance(value, dict):
            return
        execution_id = value.get("id")
        if not isinstance(execution_id, str) or not execution_id:
            unidentified += 1
            return
        stored_runtime = value.get("runtime")
        if isinstance(stored_runtime, str) and stored_runtime in {"python", "sagemath"}:
            runtime = stored_runtime
        key = (runtime, execution_id)
        row = rows.setdefault(
            key,
            {
                "id": execution_id,
                "runtime": runtime,
                "statuses": [],
                "artifact_ids": [],
                "step_ids": [],
                "source_recorded": False,
                "output_recorded": False,
            },
        )
        status = value.get("status")
        status = status if isinstance(status, str) and status else "unavailable"
        if status not in row["statuses"]:
            row["statuses"].append(status)
        if artifact_id and artifact_id not in row["artifact_ids"]:
            row["artifact_ids"].append(artifact_id)
        if step_id and step_id not in row["step_ids"]:
            row["step_ids"].append(step_id)
        row["source_recorded"] |= isinstance(value.get("source"), str)
        row["output_recorded"] |= any(key in value for key in ("stdout", "stderr", "artifacts"))

    def collect_fields(value: Any, artifact_id: str = "", step_id: str = "") -> None:
        if not isinstance(value, dict):
            return
        for field, runtime in (("python_execution", "python"), ("sage_execution", "sagemath")):
            collect(value.get(field), runtime, artifact_id, step_id)

    for artifact in record.get("artifacts") or []:
        if isinstance(artifact, dict):
            identifier = artifact.get("id")
            collect_fields(
                artifact.get("investigator_output"),
                artifact_id=identifier if isinstance(identifier, str) else "",
            )
    for step in record.get("steps") or []:
        if isinstance(step, dict):
            identifier = step.get("id")
            collect_fields(
                step.get("output"),
                step_id=identifier if isinstance(identifier, str) else "",
            )
    for branch in record.get("strategy_runs") or []:
        if isinstance(branch, dict):
            collect_fields(branch.get("pending_investigation"))

    records = list(rows.values())
    completed = sum(row["statuses"] == ["completed"] for row in records)
    inconclusive = len(records) - completed
    return {
        "records": records,
        "unidentified_count": unidentified,
        "completed_count": completed,
        "other_count": inconclusive,
        "note": (
            "No persisted Python/SageMath execution records; authored measurement "
            "claims are not established by a saved computation."
            if not records and not unidentified
            else "Saved execution status and IDs are provenance, not independent "
            "verification of a model-authored claim. Failed or interrupted "
            "executions establish no measured result."
        ),
    }
