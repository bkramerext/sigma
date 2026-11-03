"""Conservative presentation of saved research evidence, not a verification engine."""

from __future__ import annotations

import re

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
    completed_rows = [row for row in records if row["statuses"] == ["completed"]]
    completed = len(completed_rows)
    # A saved 'completed' status without the corresponding source/output fields
    # must never be presented as an observed experiment by implication.
    unsubstantiated = sum(
        not (row["source_recorded"] and row["output_recorded"]) for row in completed_rows
    )
    inconclusive = len(records) - completed
    return {
        "records": records,
        "unidentified_count": unidentified,
        "completed_count": completed,
        "completed_without_recorded_io_count": unsubstantiated,
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


# Outcome policy v2: scientific dependency assessment, not a truth oracle.
# These helpers operate only on frozen evidence; they do not modify sessions.

OUTCOME_POLICY_VERSION = "scientific-v2"


def _normalized_obligation(value: str) -> str:
    return " ".join(value.casefold().split())


def objective_obligation_impact(
    note: str,
    *,
    skeptic: Mapping[str, Any],
    reviewed_steps: Sequence[Mapping[str, Any]],
    mathematical: bool,
) -> dict[str, Any]:
    """Classify *dependency*, separately from whether an obligation is open.

    A typed review must cite the reviewed argument steps that justify the lack
    of dependency. Historical mathematics has a narrow explicit-disavowal
    compatibility path, never a rule that sources/peer work are optional.
    Ambiguity blocks objective completion.
    """
    text = str(note).strip()
    normalized = _normalized_obligation(text)
    for row in skeptic.get("obligation_impacts", []) or []:
        if not isinstance(row, Mapping) or _normalized_obligation(
            str(row.get("obligation_text") or "")
        ) != normalized:
            continue
        impact = row.get("impact")
        rationale = str(row.get("dependency_rationale") or "").strip()
        numbers = row.get("basis_step_numbers")
        numbers = numbers if isinstance(numbers, list) else []
        accepted = {
            item.get("number")
            for item in reviewed_steps
            if isinstance(item, Mapping)
            and isinstance(item.get("review"), Mapping)
            and item["review"].get("disposition") == "accepted"
            and not str(item["review"].get("objection") or "").strip()
        }
        valid = (
            len(rationale) >= 24
            and bool(numbers)
            and all(type(n) is int and n in accepted for n in numbers)
        )
        if impact == "objective_blocking":
            return {
                "text": text, "impact": impact, "rationale": rationale,
                "basis_step_numbers": numbers,
            }
        if impact == "nonblocking_followup" and valid:
            return {
                "text": text, "impact": impact, "rationale": rationale,
                "basis_step_numbers": numbers,
            }
        # Explicit nonblocking without reviewed dependency evidence is unsafe.
        return {
            "text": text, "impact": "undetermined",
            "rationale": "Dependency review lacks accepted supporting steps.",
            "basis_step_numbers": numbers,
        }

    # Historical E1 compatibility: only a mathematical argument with every
    # critical step accepted, and a note explicitly disavowing a dependency
    # on that argument, can retain optional peer-source inspection.
    complete_steps = bool(reviewed_steps) and all(
        isinstance(step, Mapping)
        and isinstance(step.get("review"), Mapping)
        and step["review"].get("disposition") == "accepted"
        and not str(step["review"].get("objection") or "").strip()
        for step in reviewed_steps
    )
    is_inspection = re.search(
        r"\b(?:peer|source|reference|citation|literature|bibliograph)\w*\b", text,
        flags=re.IGNORECASE,
    )
    cites_argument = re.search(
        r"\b(?:proof|derivation|argument|construction|theorem)\b", text,
        flags=re.IGNORECASE,
    )
    explicit_independence = re.search(
        r"\b(?:non[- ]?blocking|independent of|unrelated to|not (?:needed|required|"
        r"necessary|a premise)|does not (?:affect|alter|undermine|bear on)|"
        r"no (?:mathematical|logical|proof) (?:dependency|obligation|gap))\b",
        text, flags=re.IGNORECASE,
    )
    if mathematical and complete_steps and is_inspection and cites_argument and explicit_independence:
        return {
            "text": text, "impact": "nonblocking_followup",
            "rationale": (
                "The saved note explicitly disavows dependence of the reviewed "
                "mathematical argument on this external inspection. "
                "This is agent-reported, not independent verification."
            ),
            "basis_step_numbers": [
                step["number"] for step in reviewed_steps
                if type(step.get("number")) is int
            ],
            "historical_explicit_disavowal": True,
        }
    return {
        "text": text, "impact": "undetermined",
        "rationale": "No evidence-backed determination that this open item is independent of the objective.",
        "basis_step_numbers": [],
    }


def objective_obligation_impacts(
    notes: Sequence[str],
    *,
    skeptic: Mapping[str, Any],
    reviewed_steps: Sequence[Mapping[str, Any]],
    mathematical: bool,
) -> list[dict[str, Any]]:
    """Preserve every distinct open note; never silently clear it."""
    seen: set[str] = set()
    results: list[dict[str, Any]] = []
    for value in notes:
        if not isinstance(value, str) or not value.strip():
            continue
        normalized = _normalized_obligation(value)
        if normalized in seen:
            continue
        seen.add(normalized)
        results.append(
            objective_obligation_impact(
                value, skeptic=skeptic, reviewed_steps=reviewed_steps,
                mathematical=mathematical,
            )
        )
    return results
