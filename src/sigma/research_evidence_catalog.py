"""Versioned evidence inventory for one final research dispatch.

Availability describes representation, never scientific correctness. The
catalog is derived from supplied rows, not historical ID allowlists.
"""

from __future__ import annotations

from copy import deepcopy
from typing import Any, Literal, TypedDict

Availability = Literal["complete", "extract", "pointer_only", "omitted"]
Category = Literal["own", "prior", "continuation", "peer"]
POINTER = "pointer_only_original_not_supplied"


class Source(TypedDict):
    availability: Availability
    argument: Literal["structured", "narrative", "not_supplied"]
    strategy_id: str | None
    closure_argument: bool
    conflicted: bool


class Catalog(TypedDict):
    version: int
    note: str
    obligation_peer_citations: bool
    own: dict[str, Source]
    prior: dict[str, Source]
    continuation: dict[str, Source]
    peer: dict[str, Source]
    current_investigator: dict[str, Any]
    obligations: list[str]
    computations: list[dict[str, Any]]


class EvidenceContext(dict[str, Any]):
    """Dispatch dict with an out-of-band, nonserialized provenance inventory."""

    def __init__(self, context: dict[str, Any]) -> None:
        super().__init__(deepcopy(context))
        self.candidates: dict[Category, list[str]] = {}
        self.original_obligations: list[dict[str, Any]] = []
        self.omission_metadata: dict[str, Any] = {}

    def remember(self, category: Category, rows: list[Any], key: str = "id") -> None:
        self.candidates[category] = list(
            dict.fromkeys(
                row[key] for row in rows if isinstance(row, dict) and isinstance(row.get(key), str)
            )
        )


def _rows(value: Any) -> list[dict[str, Any]]:
    return [row for row in value if isinstance(row, dict)] if isinstance(value, list) else []


def _argument(row: dict[str, Any]) -> Literal["structured", "narrative", "not_supplied"]:
    candidates = [row]
    for field in ("investigator_output", "objective_review", "argument_extract"):
        value = row.get(field)
        if isinstance(value, dict):
            candidates.append(value)
    for value in candidates:
        for field in ("reasoning_steps", "argument_steps"):
            if any(
                isinstance(step.get("argument"), str)
                and step["argument"].strip()
                or isinstance(step.get("statement"), str)
                and step["statement"].strip()
                for step in _rows(value.get(field))
            ):
                return "structured"
    if any(
        isinstance(value.get(field), str) and value[field].strip()
        for value in candidates
        for field in ("method", "argument_summary")
    ):
        return "narrative"
    return "not_supplied"


def _partial(row: dict[str, Any]) -> bool:
    return bool(
        row.get("extract_truncated_fields")
        or row.get("extract_complete") is False
        or row.get("reasoning_steps_omitted")
        or row.get("evidence_availability") == POINTER
        or row.get("evidence_availability") == "incomplete_extract_original_not_supplied"
    )


def complete_argument(row: Any) -> bool:
    """A whole supplied structured argument is not proof or independent verification."""
    if not isinstance(row, dict) or _partial(row) or row.get("retracted_by_artifact_ids"):
        return False
    if row.get("coordinator_decision") == "stop_retracted_claim":
        return False
    investigation = row.get("investigator_output")
    if isinstance(investigation, dict) and _partial(investigation):
        return False
    skeptic = row.get("skeptic_output")
    if isinstance(skeptic, dict) and skeptic.get("stop_reason") == "claim_retracted":
        return False
    steps = row.get("reasoning_steps")
    if steps is None and isinstance(investigation, dict):
        steps = investigation.get("reasoning_steps")
    return bool(
        isinstance(steps, list)
        and steps
        and all(
            isinstance(step, dict)
            and isinstance(step.get("argument"), str)
            and step["argument"].strip()
            and "[truncated" not in step["argument"]
            for step in steps
        )
    )


def _whole_investigator(row: dict[str, Any]) -> bool:
    return (
        not _partial(row)
        and all(isinstance(row.get(key), str) and row[key].strip() for key in ("claim", "method"))
        and isinstance(row.get("reasoning_steps"), list)
        and all(
            isinstance(step, dict)
            and isinstance(step.get("argument"), str)
            and step["argument"].strip()
            and "[truncated" not in step["argument"]
            for step in row["reasoning_steps"]
        )
    )


def _whole_original(row: dict[str, Any]) -> bool:
    investigation = row.get("investigator_output")
    if isinstance(investigation, dict):
        return (
            not _partial(row)
            and isinstance(row.get("skeptic_output"), dict)
            and bool(row["skeptic_output"])
            and _whole_investigator(investigation)
        )
    return _whole_investigator(row)


def _has_visible_evidence(row: dict[str, Any]) -> bool:
    if _argument(row) != "not_supplied":
        return True
    if any(
        isinstance(row.get(field), str) and row[field].strip()
        for field in ("claim", "claim_or_question", "response")
    ):
        return True
    if any(
        isinstance(value, str) and value.strip()
        for field in ("assumptions", "objections", "open_obligations")
        for value in (row[field] if isinstance(row.get(field), list) else [])
    ):
        return True
    for field in ("python_execution", "sage_execution"):
        execution = row.get(field)
        if (
            isinstance(execution, dict)
            and execution.get("evidence_availability") != POINTER
            and isinstance(execution.get("id"), str)
            and isinstance(execution.get("status"), str)
            and any(
                execution.get(key)
                for key in ("source", "stdout", "stderr", "artifacts", "artifact_error")
            )
        ):
            return True
    return any(
        isinstance(row.get(field), dict) and _has_visible_evidence(row[field])
        for field in ("investigator_output", "objective_review", "skeptic_output")
    )


def _source(row: dict[str, Any], *, complete: bool = False) -> Source:
    if row.get("evidence_availability") == POINTER:
        availability: Availability = "pointer_only"
    elif not _has_visible_evidence(row):
        availability = "pointer_only"
    elif (
        complete
        and _whole_original(row)
        and not str(row.get("evidence_availability", "")).endswith("original_not_supplied")
    ):
        availability = "complete"
    else:
        availability = "extract"
    strategy = row.get("strategy_id")
    return {
        "availability": availability,
        "argument": "not_supplied" if availability == "pointer_only" else _argument(row),
        "strategy_id": strategy if isinstance(strategy, str) else None,
        "closure_argument": availability != "pointer_only" and complete_argument(row),
        "conflicted": False,
    }


def _approved_rows(context: dict[str, Any]) -> list[dict[str, Any]]:
    packet = context.get("approved_continuation")
    if not isinstance(packet, dict):
        return []
    if packet.get("dispatch_encoding") == "exact-text-pool-v1":
        from sigma.continuations import expand_dispatch_packet

        packet = expand_dispatch_packet(packet)
    from sigma.continuations import digest
    from sigma.projects import ProjectError

    rows: list[dict[str, Any]] = []
    for source in _rows(packet.get("sources")):
        artifact = source.get("artifact")
        if (
            not isinstance(artifact, dict)
            or not isinstance(source.get("artifact_id"), str)
            or artifact.get("id") != source["artifact_id"]
        ):
            raise ProjectError("Approved continuation artifact identity is inconsistent")
        expected = source.get("artifact_digest")
        if isinstance(expected, str) and digest(artifact) != expected:
            raise ProjectError("Approved continuation artifact digest is inconsistent")
        rows.append(
            artifact if isinstance(expected, str) else {**artifact, "extract_complete": False}
        )
    return rows


def _sources(rows: list[dict[str, Any]], key: str, *, complete: bool = False) -> dict[str, Source]:
    result: dict[str, Source] = {}
    originals: dict[str, dict[str, Any]] = {}
    for row in rows:
        identifier = row.get(key)
        if not isinstance(identifier, str):
            continue
        source = _source(
            row, complete=complete and isinstance(row.get("investigator_output"), dict)
        )
        previous = result.get(identifier)
        if previous is None:
            result[identifier] = source
            originals[identifier] = row
        elif (
            previous["availability"] == "pointer_only" and source["availability"] != "pointer_only"
        ):
            if previous["strategy_id"] not in (None, source["strategy_id"]):
                source["conflicted"] = True
            result[identifier] = source
            originals[identifier] = row
        elif source["availability"] != "pointer_only" and row != originals[identifier]:
            previous["conflicted"] = True
        elif source["strategy_id"] not in (None, previous["strategy_id"]):
            previous["conflicted"] = True
    return result


def _groups(context: dict[str, Any]) -> dict[Category, dict[str, Source]]:
    raw: dict[Category, list[dict[str, Any]]] = {
        "own": _rows(context.get("prior_artifacts")),
        "prior": _rows(context.get("prior_session_findings")),
        "continuation": _approved_rows(context),
        "peer": _rows(context.get("other_strategy_evidence")),
    }
    groups: dict[Category, dict[str, Source]] = {
        category: _sources(
            rows, "artifact_id" if category == "peer" else "id",
            complete=category == "continuation",
        )
        for category, rows in raw.items()
    }
    exact_claims: dict[str, set[str]] = {}
    for category, rows in raw.items():
        for row in rows:
            identifier = row.get("artifact_id" if category == "peer" else "id")
            claim = row.get("claim_or_question") or row.get("claim")
            if (
                isinstance(identifier, str)
                and isinstance(claim, str)
                and claim.strip()
                and "[truncated" not in claim
                and "[INCOMPLETE EXTRACT" not in claim
                and row.get("evidence_availability") != POINTER
            ):
                exact_claims.setdefault(identifier, set()).add(claim)

    by_id: dict[str, list[tuple[Category, Source]]] = {}
    for category, sources in groups.items():
        for identifier, source in sources.items():
            by_id.setdefault(identifier, []).append((category, source))
    for identifier, rows in by_id.items():
        strategies = {source["strategy_id"] for _, source in rows if source["strategy_id"]}
        categories = {category for category, _ in rows}
        if (
            len(strategies) > 1
            or len(exact_claims.get(identifier, set())) > 1
            or ("peer" in categories and len(categories) > 1)
            or ("own" in categories and len(categories) > 1)
            or any(source["conflicted"] for _, source in rows)
        ):
            for _, source in rows:
                source["conflicted"] = True
                source["closure_argument"] = False
    return groups


def computation_targets(context: dict[str, Any]) -> list[dict[str, Any]]:
    """Return only actual non-pointer execution records in the supplied packet."""
    targets: dict[tuple[str | None, str], dict[str, Any]] = {}
    blocked = {
        identifier
        for group in _groups(context).values()
        for identifier, source in group.items()
        if source["conflicted"]
    }

    def add(artifact_id: str | None, output: Any) -> None:
        if (
            artifact_id in blocked
            or not isinstance(output, dict)
            or output.get("evidence_availability") == POINTER
        ):
            return
        for field in ("python_execution", "sage_execution"):
            execution = output.get(field)
            if (
                isinstance(execution, dict)
                and isinstance(execution.get("id"), str)
                and isinstance(execution.get("status"), str)
                and execution["status"] in {
                    "completed", "failed", "error", "timeout", "timed_out",
                    "interrupted", "cancelled", "blocked", "rejected",
                    "unavailable", "running", "queued", "output_limit",
                }
                and execution.get("evidence_availability") != POINTER
            ):
                targets[(artifact_id, execution["id"])] = {
                    "research_artifact_id": artifact_id,
                    "execution": execution,
                }

    for field, key in (
        ("prior_session_findings", "id"),
        ("prior_artifacts", "id"),
        ("other_strategy_evidence", "artifact_id"),
    ):
        for row in _rows(context.get(field)):
            identifier = row.get(key)
            if not isinstance(identifier, str) or row.get("evidence_availability") == POINTER:
                continue
            add(identifier, row)
            add(identifier, row.get("investigator_output"))
    # Full explicitly approved originals supersede a duplicate bounded extract.
    for row in _approved_rows(context):
        if _source(row, complete=True)["availability"] != "pointer_only":
            add(row["id"], row)
            add(row["id"], row.get("investigator_output"))
    add(None, context.get("investigator_output"))
    return list(targets.values())


def _computation_permissions(context: dict[str, Any]) -> list[dict[str, Any]]:
    result = []
    for target in computation_targets(context):
        execution = target["execution"]
        evidence = [
            field
            for field, available in (
                ("source", isinstance(execution.get("source"), str)),
                ("output", bool(execution.get("stdout"))),
                (
                    "error",
                    bool(execution.get("stderr") or execution.get("artifact_error"))
                    or execution.get("status") != "completed",
                ),
            )
            if available
        ]
        result.append(
            {
                "artifact_id": target["research_artifact_id"],
                "execution_id": execution["id"],
                "evidence": evidence,
                "filenames": [
                    item["filename"]
                    for item in _rows(execution.get("artifacts"))
                    if isinstance(item.get("filename"), str)
                ],
            }
        )
    return result


def build_catalog(context: dict[str, Any]) -> Catalog:
    current = context.get("investigator_output")
    step_id = context.get("investigator_step_id")
    current_source = _source(current, complete=True) if isinstance(current, dict) else None
    if current_source and context.get("investigator_output_extract_complete") is False:
        if current_source["availability"] == "complete":
            current_source["availability"] = "extract"
        current_source["closure_argument"] = False
    groups = _groups(context)
    return {
        "version": 1,
        "note": (
            "Complete means the original representation is supplied, not verified. "
            "Extracts support only their visible material; pointers and conflicts are not citable. "
            "closure_argument means a whole unretracted structured argument is supplied, not a proof."
        ),
        "obligation_peer_citations": context.get("scheduler_version") == 2,
        "own": groups["own"],
        "prior": groups["prior"],
        "continuation": groups["continuation"],
        "peer": groups["peer"],
        "current_investigator": {
            "step_id": (
                step_id
                if current_source
                and current_source["availability"] in {"complete", "extract"}
                and isinstance(step_id, str)
                else None
            ),
            "availability": current_source["availability"] if current_source else "omitted",
            "argument": current_source["argument"] if current_source else "not_supplied",
            "closure_argument": bool(
                current_source
                and current_source["availability"] == "complete"
                and current_source["closure_argument"]
            ),
        },
        "obligations": [
            row["obligation_id"]
            for row in _rows(context.get("obligation_ledger"))
            if isinstance(row.get("obligation_id"), str)
        ],
        "computations": _computation_permissions(context),
    }


def citable(sources: dict[str, Source]) -> set[str]:
    return {
        identifier
        for identifier, source in sources.items()
        if source["availability"] in {"complete", "extract"} and not source["conflicted"]
    }


def artifact_permissions(catalog: Catalog, *, include_peer: bool) -> set[str]:
    allowed = citable(catalog["own"]) | citable(catalog["prior"]) | citable(catalog["continuation"])
    return allowed | citable(catalog["peer"]) if include_peer else allowed


def step_permissions(catalog: Catalog) -> set[str]:
    current = catalog["current_investigator"]
    identifier = current["step_id"]
    return (
        {identifier}
        if isinstance(identifier, str) and current["availability"] in {"complete", "extract"}
        else set()
    )


def audit_inventory(context: dict[str, Any]) -> dict[str, Any]:
    """Record known omitted identities separately from the bounded provider input."""
    if not isinstance(context, EvidenceContext):
        return {}
    catalog = context["evidence_catalog"]
    omitted: dict[str, Any] = {}
    for category, identifiers in context.candidates.items():
        supplied = catalog[category]
        available = set(supplied)
        missing = [identifier for identifier in identifiers if identifier not in available]
        if missing:
            omitted[category] = {
                "availability": "omitted",
                "ids": missing,
                "count": len(missing),
                "reason": "not selected under bounded research context policy",
            }
    supplied_obligations = set(catalog["obligations"])
    omitted_obligations = [
        row["obligation_id"]
        for row in context.original_obligations
        if row["obligation_id"] not in supplied_obligations
    ]
    return {
        "version": 1,
        "omitted": omitted,
        "omitted_obligation_ids": omitted_obligations,
        "original_obligation_references": deepcopy(context.original_obligations),
        "historical_omission_metadata": deepcopy(context.omission_metadata),
    }
