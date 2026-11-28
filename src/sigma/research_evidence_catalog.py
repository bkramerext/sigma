"""Versioned evidence inventory for one final research dispatch.

Availability describes representation, never scientific correctness. The
catalog is derived from supplied rows, not historical ID allowlists.
"""

from __future__ import annotations

from typing import Any, Literal, TypedDict

Availability = Literal["complete", "extract", "pointer_only", "omitted"]
Category = Literal["own", "prior", "continuation", "peer"]
POINTER = "pointer_only_original_not_supplied"


class Source(TypedDict):
    availability: Availability
    argument: Literal["structured", "narrative", "not_supplied"]
    strategy_id: str | None


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
        super().__init__(context)
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


def _source(row: dict[str, Any], *, complete: bool = False) -> Source:
    if row.get("evidence_availability") == POINTER:
        availability: Availability = "pointer_only"
    elif _argument(row) == "not_supplied" and not any(
        row.get(field)
        for field in (
            "claim",
            "claim_or_question",
            "method",
            "reasoning_steps",
            "argument_steps",
            "argument_summary",
            "investigator_output",
            "objective_review",
            "skeptic_output",
            "objections",
            "assumptions",
            "python_execution",
            "sage_execution",
            "open_obligations",
        )
    ):
        availability = "pointer_only"
    elif (
        complete
        and not row.get("extract_truncated_fields")
        and row.get("extract_complete") is not False
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
    }


def _approved_rows(context: dict[str, Any]) -> list[dict[str, Any]]:
    packet = context.get("approved_continuation")
    if not isinstance(packet, dict):
        return []
    if packet.get("dispatch_encoding") == "exact-text-pool-v1":
        from sigma.continuations import expand_dispatch_packet

        packet = expand_dispatch_packet(packet)
    return [
        artifact
        for source in _rows(packet.get("sources"))
        if isinstance(artifact := source.get("artifact"), dict)
        and isinstance(source.get("artifact_id"), str)
        and artifact.get("id") == source["artifact_id"]
    ]


def _sources(rows: list[dict[str, Any]], key: str, *, complete: bool = False) -> dict[str, Source]:
    result: dict[str, Source] = {}
    for row in rows:
        identifier = row.get(key)
        if not isinstance(identifier, str):
            continue
        source = _source(row, complete=complete)
        previous = result.get(identifier)
        if previous is None or previous["availability"] == "pointer_only":
            result[identifier] = source
    return result


def computation_targets(context: dict[str, Any]) -> list[dict[str, Any]]:
    """Return only actual non-pointer execution records in the supplied packet."""
    targets: dict[tuple[str | None, str], dict[str, Any]] = {}

    def add(artifact_id: str | None, output: Any) -> None:
        if not isinstance(output, dict) or output.get("evidence_availability") == POINTER:
            return
        for field in ("python_execution", "sage_execution"):
            execution = output.get(field)
            if (
                isinstance(execution, dict)
                and isinstance(execution.get("id"), str)
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
    return {
        "version": 1,
        "note": (
            "Complete means the original representation is supplied, not verified. "
            "Extracts support only their visible material; pointers are not citable."
        ),
        "obligation_peer_citations": context.get("scheduler_version") == 2,
        "own": _sources(_rows(context.get("prior_artifacts")), "id"),
        "prior": _sources(_rows(context.get("prior_session_findings")), "id"),
        "continuation": _sources(_approved_rows(context), "id", complete=True),
        "peer": _sources(_rows(context.get("other_strategy_evidence")), "artifact_id"),
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
        if source["availability"] in {"complete", "extract"}
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
        "original_obligation_references": context.original_obligations,
        "historical_omission_metadata": context.omission_metadata,
    }
