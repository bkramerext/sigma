"""Versioned evidence inventory for one final research dispatch.

Availability describes representation, never scientific correctness. The
catalog is derived from supplied rows, not historical ID allowlists.
"""

from __future__ import annotations

import json
import re
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
            source["conflicted"] = previous["conflicted"]
            result[identifier] = source
            originals[identifier] = row
        elif source["availability"] != "pointer_only" and row != originals[identifier]:
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
            rows,
            "artifact_id" if category == "peer" else "id",
            complete=category == "continuation",
        )
        for category, rows in raw.items()
    }
    exact_claims: dict[str, set[str]] = {}
    explicit_strategies: dict[str, set[str]] = {}
    for category, rows in raw.items():
        for row in rows:
            identifier = row.get("artifact_id" if category == "peer" else "id")
            strategy = row.get("strategy_id")
            # Record every explicit identity, including replaced pointers.
            # Missing metadata is unknown, not a contradictory identity.
            if isinstance(identifier, str) and isinstance(strategy, str) and strategy:
                explicit_strategies.setdefault(identifier, set()).add(strategy)
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
        strategies = explicit_strategies.get(identifier, set())
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
    targets: dict[tuple[str | None, str], list[dict[str, Any]]] = {}
    execution_examples: dict[str, list[dict[str, Any]]] = {}
    conflicting_executions: set[str] = set()
    blocked = {
        identifier
        for group in _groups(context).values()
        for identifier, source in group.items()
        if source["conflicted"]
    }

    def add(artifact_id: str | None, output: Any) -> None:
        if not isinstance(output, dict) or output.get("evidence_availability") == POINTER:
            return
        for field in ("python_execution", "sage_execution"):
            execution = output.get(field)
            if (
                isinstance(execution, dict)
                and isinstance(execution.get("id"), str)
                and isinstance(execution.get("status"), str)
                and execution["status"]
                in {
                    "completed",
                    "failed",
                    "error",
                    "timeout",
                    "timed_out",
                    "interrupted",
                    "cancelled",
                    "blocked",
                    "rejected",
                    "unavailable",
                    "running",
                    "queued",
                    "output_limit",
                }
                and execution.get("evidence_availability") != POINTER
            ):
                identifier = execution["id"]
                examples = execution_examples.setdefault(identifier, [])
                # A sparse first record does not establish agreement between
                # later records. Compare all distinct supplied pairs.
                if execution not in examples:
                    if identifier not in conflicting_executions and (
                        not _compatible_executions(execution, execution)
                        or any(not _compatible_executions(other, execution) for other in examples)
                    ):
                        conflicting_executions.add(identifier)
                    examples.append(execution)
                if artifact_id not in blocked:
                    targets.setdefault((artifact_id, identifier), []).append(execution)

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
    return [
        {
            "research_artifact_id": key[0],
            "execution": (
                examples[0] if len(examples) == 1 else max(examples, key=_execution_preference)
            ),
        }
        for key, examples in targets.items()
        if key[1] not in conflicting_executions
    ]


def _execution_preference(execution: dict[str, Any]) -> tuple[Any, ...]:
    """Prefer a usable actual record, not arbitrary serialized length or a union."""
    permission = execution_permissions(execution)
    return (
        int(permission["closure_output"]) + len(permission["closure_filenames"]),
        int(permission["closure_output"]),
        len(permission["result_filenames"]),
        len(permission["evidence"]) + len(permission["filenames"]),
        sum(
            len(execution[field])
            for field in ("stdout", "stderr")
            if isinstance(execution.get(field), str)
        ),
        json.dumps(execution, sort_keys=True, ensure_ascii=False),
    )


def _compatible_text(
    first: dict[str, Any], second: dict[str, Any], field: str, truncation_field: str
) -> bool:
    a, b = first.get(field), second.get(field)
    if not isinstance(a, str) or not isinstance(b, str):
        return True
    if a == b:
        return bool(first.get(truncation_field)) == bool(second.get(truncation_field))
    if field == "representation":
        marker = "\n[truncated; inspect the original saved artifact]"
        if first.get(truncation_field):
            a = a.removesuffix(marker)
        if second.get(truncation_field):
            b = b.removesuffix(marker)
    return bool(
        (first.get(truncation_field) and len(a) < len(b) and b.startswith(a))
        or (second.get(truncation_field) and len(b) < len(a) and a.startswith(b))
    )


def _compatible_inspections(first: dict[str, Any], second: dict[str, Any]) -> bool:
    for field in ("sha256", "size_bytes", "media_type", "execution_id"):
        if field in first and field in second and first[field] != second[field]:
            return False
    a, b = first.get("inspection"), second.get("inspection")
    if not isinstance(a, dict) or not isinstance(b, dict):
        return True
    for field in ("status", "format"):
        if field in a and field in b and a[field] != b[field]:
            return False
    return _compatible_text(a, b, "representation", "truncated")


def _consistent_execution_files(first: dict[str, Any], second: dict[str, Any]) -> bool:
    """Check explicit inspection provenance against every supplied file manifest.

    Absent metadata remains unknown; contradictions or duplicate manifest
    filenames make the execution unsafe to cite, including under another alias.
    """
    manifests: list[dict[str, dict[str, Any]] | None] = []
    for execution in (first, second):
        manifest: dict[str, dict[str, Any]] = {}
        for item in _rows(execution.get("artifacts")):
            filename = item.get("filename")
            if not isinstance(filename, str) or not filename.strip():
                continue
            if filename in manifest:
                return False
            manifest[filename] = item
        manifests.append(manifest if isinstance(execution.get("artifacts"), list) else None)
    for execution in (first, second):
        for flag in ("stdout_truncated", "stderr_truncated"):
            if flag in execution and type(execution[flag]) is not bool:
                return False
        for item in _rows(execution.get("artifact_inspections")):
            identity = item.get("execution_id")
            if identity is not None and identity != execution.get("id"):
                return False
            inspection = item.get("inspection")
            if not isinstance(inspection, dict):
                continue
            if "truncated" in inspection and type(inspection["truncated"]) is not bool:
                return False
            filename = item.get("filename")
            if not isinstance(filename, str):
                continue
            for manifest in manifests:
                if manifest is None:
                    continue
                saved = manifest.get(filename)
                if saved is None:
                    # An available result must not claim a file absent from
                    # a supplied manifest. An omitted preview is not a result.
                    if inspection.get("status") == "available":
                        return False
                    continue
                for field in ("sha256", "size_bytes", "media_type"):
                    actual, expected = item.get(field), saved.get(field)
                    if actual is not None and expected is not None and (
                        type(actual) is not type(expected) or actual != expected
                    ):
                        return False
    return True


def _compatible_executions(first: dict[str, Any], second: dict[str, Any]) -> bool:
    for field in (
        "status",
        "exit_code",
        "source_sha256",
        "source",
        "runtime",
        "runtime_version",
        "strategy_id",
        "session_id",
        "cycle",
        "agent",
        "artifact_error",
        "stdout_base64",
        "stderr_base64",
    ):
        if field in first and field in second and first[field] != second[field]:
            return False
    for field in ("stdout", "stderr"):
        if not _compatible_text(first, second, field, f"{field}_truncated"):
            return False
    if "artifacts" in first and "artifacts" in second and first["artifacts"] != second["artifacts"]:
        return False
    if not _consistent_execution_files(first, second):
        return False
    # Missing inspections are unknown. Explicit contradictory states or
    # content of the same file cannot authorize a result.
    inspections = [
        item
        for execution in (first, second)
        for item in _rows(execution.get("artifact_inspections"))
        if isinstance(item.get("filename"), str) and item["filename"]
    ]
    return all(
        _compatible_inspections(item, other)
        for index, item in enumerate(inspections)
        for other in inspections[index + 1 :]
        if item["filename"] == other["filename"]
    )


def execution_permissions(execution: dict[str, Any]) -> dict[str, Any]:
    """The same visible-field contract drives catalog and response validation."""

    def visible(key: str) -> bool:
        value = execution.get(key)
        return isinstance(value, str) and bool(value.strip())

    if not _compatible_executions(execution, execution):
        return {
            "evidence": [],
            "filenames": [],
            "result_filenames": [],
            "closure_output": False,
            "closure_filenames": [],
        }
    evidence = [
        field
        for field, available in (
            ("source", visible("source")),
            ("output", visible("stdout")),
            ("error", visible("stderr") or visible("artifact_error")),
        )
        if available
    ]
    filenames = list(
        dict.fromkeys(
            item["filename"]
            for item in _rows(execution.get("artifacts"))
            if isinstance(item.get("filename"), str) and item["filename"].strip()
        )
    )
    result_filenames = [
        name
        for name in filenames
        if execution.get("status") == "completed"
        and any(
            item.get("filename") == name
            and isinstance(item.get("inspection"), dict)
            and item["inspection"].get("status") == "available"
            and isinstance(item["inspection"].get("representation"), str)
            and bool(item["inspection"]["representation"].strip())
            for item in _rows(execution.get("artifact_inspections"))
        )
    ]
    successful = (
        execution.get("status") == "completed"
        and type(execution.get("exit_code")) is int
        and execution["exit_code"] == 0
        and isinstance(execution.get("source_sha256"), str)
        and bool(re.fullmatch(r"[0-9a-f]{64}", execution["source_sha256"]))
    )
    return {
        "evidence": evidence,
        "filenames": filenames,
        "result_filenames": result_filenames,
        "closure_output": (
            successful and visible("stdout") and not execution.get("stdout_truncated")
        ),
        "closure_filenames": [
            name
            for name in result_filenames
            if successful
            and any(
                item.get("filename") == name
                and isinstance(item.get("inspection"), dict)
                and item["inspection"].get("status") == "available"
                and isinstance(item["inspection"].get("representation"), str)
                and bool(item["inspection"]["representation"].strip())
                and not item["inspection"].get("truncated")
                for item in _rows(execution.get("artifact_inspections"))
            )
        ],
    }


def _computation_permissions(context: dict[str, Any]) -> list[dict[str, Any]]:
    result = []
    for target in computation_targets(context):
        execution = target["execution"]
        permission = execution_permissions(execution)
        if permission["evidence"] or permission["filenames"]:
            result.append(
                {
                    "artifact_id": target["research_artifact_id"],
                    "execution_id": execution["id"],
                    **permission,
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
