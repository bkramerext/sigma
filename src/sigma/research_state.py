"""Read-only, evidence-linked current understanding; no semantic proof reconciliation.

The view chooses latest *recorded reviews* per strategy, not the truest claim.
Only explicit, unambiguous IDs with available evidence can retire a finding or
record a resolved obligation. Legacy prose stays inspectable and unreconciled.
"""

from __future__ import annotations

from collections import Counter, defaultdict
from datetime import datetime
from typing import Any, Literal, TypedDict

from sigma.projects import inspect_project
from sigma.research_epistemics import verification_label
from sigma.research_sessions import _obligation_identity, read_session_snapshot


class EvidencePointer(TypedDict):
    project_id: str
    session_id: str
    session_number: int
    strategy_id: str
    artifact_id: str
    artifact_sequence: int
    record_path: str
    available: bool


class LocalFinding(TypedDict):
    id: str
    text: str
    investigated_claim: str
    source: EvidencePointer
    review_ref: str
    review_status: str
    status: str
    verification: str
    local_scope: str
    strategy_title: str
    strategy_text: str
    assumptions: list[str]
    objections: list[str]
    evidence_kind: str
    related_by: list[EvidencePointer]


class RecordedObligation(TypedDict):
    id: str
    text: str
    kind: str
    strategy_id: str
    status: str
    actionable: bool
    sources: list[EvidencePointer]
    dispositions: list[dict[str, Any]]
    narrative_resolution_sources: list[EvidencePointer]
    note: str


class ResearchChange(TypedDict):
    kind: str
    text: str
    source: EvidencePointer
    earlier: EvidencePointer | None
    caution: str


class CurrentUnderstanding(TypedDict):
    version: Literal[1]
    project_id: str
    session_count: int
    project_status: Literal["not_determined"]
    scope_note: str
    findings: list[LocalFinding]
    current_finding_ids: list[str]
    obligations: list[RecordedObligation]
    next_investigations: list[dict[str, Any]]
    changes: list[ResearchChange]
    failures: list[dict[str, Any]]
    limitations: list[str]


def _rows(value: Any) -> list[dict[str, Any]]:
    return [item for item in value if isinstance(item, dict)] if isinstance(value, list) else []


def _texts(value: Any) -> list[str]:
    return (
        [item for item in value if isinstance(item, str) and item.strip()]
        if isinstance(value, list)
        else []
    )


def _dict(value: Any) -> dict[str, Any]:
    return value if isinstance(value, dict) else {}


def _number(value: Any) -> int:
    return value if type(value) is int else 0


def _text(value: Any) -> str:
    return value if isinstance(value, str) else ""


def _scope(artifact: dict[str, Any]) -> list[str]:
    review, skeptic = _dict(artifact.get("objective_review")), _dict(artifact.get("skeptic_output"))
    return list(
        dict.fromkeys(
            _texts(artifact.get("assumptions"))
            + _texts(review.get("assumptions"))
            + _texts(skeptic.get("assumptions_reviewed"))
        )
    )


def build_current_understanding(
    project_id: str, sessions: list[dict[str, Any]], *, unavailable_records: int = 0
) -> CurrentUnderstanding:
    """Pure deterministic projection. Every displayed relationship has a source.

    IDs reuse T37's exact scoped obligation identity. Text equality only identifies
    repeated declarations in that scope; it never establishes logical equivalence.
    Narrative resolved-objection lists are notices, not machine resolutions.
    Optional finding_relations are explicit saved assessments, never inferred from
    text. Their statuses remain model-reported and unverified.
    """
    valid = [
        s for s in sessions if s.get("project_id") == project_id and isinstance(s.get("id"), str)
    ]
    skipped = unavailable_records + len(sessions) - len(valid)
    ordered = sorted(
        valid, key=lambda s: (_number(s.get("session_number")), _text(s.get("created_at")), s["id"])
    )
    findings: list[LocalFinding] = []
    obligations: dict[str, RecordedObligation] = {}
    changes: list[ResearchChange] = []
    failures: list[dict[str, Any]] = []
    limitations = [
        "Local saved findings do not establish that the project is solved. Agent reviews and computations are not independent verification.",
        "Latest reviewed findings are shown by strategy; different wording does not establish contradiction, equivalence or supersession.",
    ]
    # Index composite identities first. Bare artifact/step IDs are usable only if
    # unique inside this project; a duplicate or foreign ID is not resolution proof.
    entries: list[tuple[dict[str, Any], dict[str, Any], EvidencePointer]] = []
    by_artifact: dict[str, list[EvidencePointer]] = defaultdict(list)
    by_step: dict[str, list[EvidencePointer]] = defaultdict(list)
    step_metadata: dict[str, dict[str, Any]] = {}
    for session in ordered:
        for artifact in sorted(
            _rows(session.get("artifacts")),
            key=lambda a: (_number(a.get("sequence")), _text(a.get("id"))),
        ):
            identifier = _text(artifact.get("id"))
            if (
                not identifier
                or artifact.get("project_id", project_id) != project_id
                or artifact.get("session_id", session["id"]) != session["id"]
            ):
                skipped += 1
                continue
            source: EvidencePointer = {
                "project_id": project_id,
                "session_id": session["id"],
                "session_number": _number(session.get("session_number")),
                "strategy_id": _text(artifact.get("strategy_id") or session.get("strategy_id")),
                "artifact_id": identifier,
                "artifact_sequence": _number(artifact.get("sequence")),
                "record_path": f"artifacts/{identifier}",
                "available": True,
            }
            entries.append((session, artifact, source))
            by_artifact[identifier].append(source)
        for step in _rows(session.get("steps")):
            if isinstance(step.get("id"), str):
                # Step provenance opens its owning session; the pointer does not
                # pretend that a call log is itself a saved research artifact.
                pointer: EvidencePointer = {
                    "project_id": project_id,
                    "session_id": session["id"],
                    "session_number": _number(session.get("session_number")),
                    "strategy_id": _text(step.get("strategy_id") or session.get("strategy_id")),
                    "artifact_id": "",
                    "artifact_sequence": 0,
                    "record_path": f"steps/{step['id']}",
                    "available": True,
                }
                by_step[step["id"]].append(pointer)
                step_metadata[step["id"]] = step
        if session.get("status") in {"failed", "stopped", "paused", "running", "queued"}:
            failures.append(
                {
                    "session_id": session["id"],
                    "session_number": _number(session.get("session_number")),
                    "status": session.get("status"),
                    "note": _text(session.get("message"))
                    or "No completed local answer is inferred from this execution state.",
                }
            )
        for branch in _rows(session.get("strategy_runs")):
            if branch.get("status") == "failed":
                failures.append(
                    {
                        "session_id": session["id"],
                        "session_number": _number(session.get("session_number")),
                        "strategy_id": branch.get("strategy_id"),
                        "status": "failed",
                        "note": _text(branch.get("reason"))
                        or "This branch failed; other branch findings are preserved.",
                    }
                )
    identities = Counter((p["session_id"], p["artifact_id"]) for _, _, p in entries)
    duplicates = {key for key, count in identities.items() if count > 1}
    skipped += sum(identities[key] for key in duplicates)
    entries = [
        entry
        for entry in entries
        if (entry[2]["session_id"], entry[2]["artifact_id"]) not in duplicates
    ]
    by_artifact.clear()
    for _, _, pointer in entries:
        by_artifact[pointer["artifact_id"]].append(pointer)
    order_index = {(p["session_id"], p["artifact_id"]): i for i, (_, _, p) in enumerate(entries)}
    latest_by_strategy: dict[str, LocalFinding] = {}
    finding_by_key: dict[tuple[str, str], LocalFinding] = {}
    for session, artifact, source in entries:
        review = _dict(artifact.get("objective_review"))
        skeptic = _dict(artifact.get("skeptic_output"))
        assumptions = _scope(artifact)
        status = _text(review.get("status")) or "not_recorded"
        local_refutation = (
            skeptic.get("stop_reason") == "decisive_counterexample"
            or artifact.get("coordinator_decision") == "stop_decisive_counterexample"
        )
        finding: LocalFinding = {
            "id": f"finding:{project_id}:{source['session_id']}:{source['artifact_id']}",
            "text": _text(review.get("claim")) or _text(artifact.get("claim_or_question")),
            "investigated_claim": _text(artifact.get("claim_or_question")),
            "source": source,
            "review_ref": f"{source['record_path']}/objective_review" if review else "",
            "review_status": status,
            "status": "local_refutation_reported"
            if local_refutation
            else "candidate_reported"
            if status == "achieved"
            else "partial_reported"
            if status == "partial"
            else "unassessed",
            "verification": verification_label(review),
            "local_scope": _text(review.get("claim_scope"))
            or "Scope not recorded; this is a local strategy finding, not a project-level theorem.",
            "strategy_title": _text(
                artifact.get("strategy_title") or session.get("strategy_title")
            ),
            "strategy_text": next(
                (
                    _text(b.get("strategy_text"))
                    for b in _rows(session.get("strategy_runs"))
                    if b.get("strategy_id") == source["strategy_id"]
                ),
                _text(session.get("strategy_text")),
            ),
            "assumptions": assumptions,
            "objections": list(
                dict.fromkeys(
                    _texts(review.get("unresolved_objections")) + _texts(artifact.get("objections"))
                )
            ),
            "evidence_kind": _text(artifact.get("evidence_status"))
            or "Evidence provenance not recorded; no live research inferred.",
            "related_by": [],
        }
        findings.append(finding)
        finding_by_key[(source["session_id"], source["artifact_id"])] = finding
        previous = latest_by_strategy.get(source["strategy_id"])
        if review:
            if previous:
                changes.append(
                    {
                        "kind": "later_finding_available",
                        "text": finding["text"],
                        "source": source,
                        "earlier": previous["source"],
                        "caution": "Later saved review; no supersession or correction is inferred. Inspect both records.",
                    }
                )
            latest_by_strategy[source["strategy_id"]] = finding
        if local_refutation:
            changes.append(
                {
                    "kind": "local_refutation_reported",
                    "text": finding["text"],
                    "source": source,
                    "earlier": None,
                    "caution": "Reported counterexample to the investigated local claim only, not a disproof of the project.",
                }
            )
        # Preserve exact scoped declarations, not a similarity-based merged list.
        note_fields = [
            ("obligation", artifact.get("open_obligations")),
            ("objection", artifact.get("objections")),
            ("objection", review.get("unresolved_objections")),
            ("obligation", skeptic.get("remaining_obligations")),
        ]
        for kind, values in note_fields:
            for text in _texts(values):
                identifier = _obligation_identity(
                    text,
                    project_id=project_id,
                    strategy_id=source["strategy_id"],
                    assumptions=assumptions,
                )
                item = obligations.setdefault(
                    identifier,
                    {
                        "id": identifier,
                        "text": text,
                        "kind": kind,
                        "strategy_id": source["strategy_id"],
                        "status": "historical_unreconciled",
                        "actionable": False,
                        "sources": [],
                        "dispositions": [],
                        "narrative_resolution_sources": [],
                        "note": "Legacy declaration without an obligation-ID disposition; not determined to be a current mandatory step.",
                    },
                )
                if source not in item["sources"]:
                    item["sources"].append(source)
                # A fresh declaration may reopen work; an older explicit closure
                # cannot silently govern a later restatement.
                item["status"], item["actionable"] = "historical_unreconciled", False

    def evidence_for(
        disposition: dict[str, Any], source: EvidencePointer
    ) -> list[EvidencePointer] | None:
        refs: list[EvidencePointer] = []
        for key, index in (("basis_artifact_ids", by_artifact), ("basis_step_ids", by_step)):
            for identifier in _texts(disposition.get(key)):
                matches = index.get(identifier, [])
                if len(matches) != 1:
                    return None
                ref = matches[0]
                if key == "basis_step_ids":
                    metadata = step_metadata[identifier]
                    owner = next((a for _, a, p in entries if p == source), {})
                    try:
                        valid_time = datetime.fromisoformat(
                            _text(metadata.get("finished_at"))
                        ) <= datetime.fromisoformat(_text(owner.get("created_at")))
                    except (TypeError, ValueError):
                        valid_time = False
                    if (
                        metadata.get("status") != "completed"
                        or ref["session_id"] != source["session_id"]
                        or not valid_time
                    ):
                        return None
                if (
                    ref["artifact_id"]
                    and order_index[(ref["session_id"], ref["artifact_id"])]
                    > order_index[(source["session_id"], source["artifact_id"])]
                ):
                    return None
                refs.append(ref)
        return refs

    # Apply explicit ID dispositions in source order, retaining their full audit.
    for _, artifact, source in entries:
        skeptic = _dict(artifact.get("skeptic_output"))
        for disposition in (
            _rows(artifact.get("obligation_dispositions"))
            + _rows(skeptic.get("obligation_reviews"))
            + _rows(skeptic.get("coordinator_closed_obligations"))
        ):
            item = obligations.get(_text(disposition.get("obligation_id")))
            if item is None:
                continue
            refs = evidence_for(disposition, source)
            state = disposition.get(
                "status",
                "addressed"
                if disposition in _rows(skeptic.get("coordinator_closed_obligations"))
                else "unknown",
            )
            source_order = order_index[(source["session_id"], source["artifact_id"])]
            if not any(
                order_index[(p["session_id"], p["artifact_id"])] <= source_order
                for p in item["sources"]
            ):
                continue
            valid_disposition = (
                state in {"unresolved", "addressed", "superseded", "retracted", "unknown"}
                and bool(_text(disposition.get("rationale")).strip())
                and refs is not None
                and (bool(refs) or state in {"unresolved", "unknown"})
            )
            item["dispositions"].append(
                {
                    "status": state,
                    "source": source,
                    "basis": refs or [],
                    "rationale": _text(disposition.get("rationale")),
                    "valid": valid_disposition,
                    "applied": valid_disposition
                    and not any(
                        order_index[(p["session_id"], p["artifact_id"])] > source_order
                        for p in item["sources"]
                    ),
                    "verification": "Recorded disposition; not independently verified",
                }
            )
            # A disposition before a later declaration cannot retire the latter.
            if any(
                order_index[(p["session_id"], p["artifact_id"])] > source_order
                for p in item["sources"]
            ):
                continue
            if valid_disposition:
                item["status"] = {
                    "addressed": "resolved_reported",
                    "superseded": "superseded_reported",
                    "retracted": "retracted_reported",
                    "unresolved": "open_reported",
                    "unknown": "historical_unreconciled",
                }[state]
                item["actionable"] = state == "unresolved"
                item["note"] = "Explicit source-linked disposition, reported and unverified."
                if state in {"addressed", "superseded", "retracted"}:
                    changes.append(
                        {
                            "kind": f"obligation_{state}",
                            "text": item["text"],
                            "source": source,
                            "earlier": item["sources"][0],
                            "caution": "Explicit evidence-linked disposition, reported and unverified; not an independently proved result.",
                        }
                    )
            else:
                item["note"] = (
                    "Saved disposition lacks unambiguous available evidence or a rationale; no resolution inferred."
                )
        # Optional explicit claim-level assessments, distinct from peer-handoff
        # retractions (which must not be mistaken for retraction of a whole claim).
        for relation in _rows(artifact.get("finding_relations")):
            target = finding_by_key.get(
                (
                    _text(relation.get("source_session_id")),
                    _text(relation.get("source_artifact_id")),
                )
            )
            kind = relation.get("relation")
            refs = evidence_for(relation, source)
            if (
                target
                and kind in {"supersedes", "refutes"}
                and refs
                and _text(relation.get("rationale")).strip()
                and order_index[(target["source"]["session_id"], target["source"]["artifact_id"])]
                < order_index[(source["session_id"], source["artifact_id"])]
            ):
                target["status"] = (
                    "superseded_reported" if kind == "supersedes" else "refuted_reported"
                )
                target["related_by"].append(source)
                changes.append(
                    {
                        "kind": kind,
                        "text": _text(relation.get("rationale")),
                        "source": source,
                        "earlier": target["source"],
                        "caution": "Explicit saved assessment with available evidence; not independent verification.",
                    }
                )
    # Current legacy open notes are proposals only. Older unlinked notes remain
    # visible but are not automatically recycled into mandatory next steps.
    for item in obligations.values():
        latest = latest_by_strategy.get(item["strategy_id"])
        if item["status"] != "historical_unreconciled" or not latest:
            continue
        narrative_notices = [
            p_source
            for _, a, p_source in entries
            if (
                item["text"] in _texts(_dict(a.get("objective_review")).get("resolved_objections"))
                and any(
                    p["artifact_id"]
                    in _texts(_dict(a.get("objective_review")).get("basis_artifact_ids"))
                    for p in item["sources"]
                )
                and p_source["strategy_id"] == item["strategy_id"]
                and order_index[(p_source["session_id"], p_source["artifact_id"])]
                >= order_index[
                    (item["sources"][-1]["session_id"], item["sources"][-1]["artifact_id"])
                ]
            )
        ]
        item["narrative_resolution_sources"] = narrative_notices
        if narrative_notices:
            item["note"] = (
                "A later review lists this exact text as resolved, but no obligation-ID resolution was recorded. Inspect the narrative; not a mandatory next step."
            )
        elif (
            item["sources"][-1] == latest["source"]
            and latest["review_status"] == "partial"
            and not any(d["valid"] and d["applied"] for d in item["dispositions"])
        ):
            item["status"] = (
                "challenged_reported" if item["kind"] == "objection" else "open_reported"
            )
            item["actionable"] = item["kind"] == "obligation"
            item["note"] = (
                "Open in the latest local partial review; suggested work, not an independently assessed requirement."
            )
    current = [
        row["id"]
        for row in latest_by_strategy.values()
        if row["status"] not in {"superseded_reported", "refuted_reported"}
    ]
    next_questions = [
        {
            "obligation_id": item["id"],
            "question": item["text"],
            "source": item["sources"][-1],
            "qualification": "Proposed from a saved open obligation; review its scope before starting.",
        }
        for item in obligations.values()
        if item["actionable"]
    ]
    if skipped:
        limitations.append(
            f"{skipped} unavailable, malformed or foreign records were excluded. Missing evidence is not treated as resolved."
        )
    if any(item["status"] == "historical_unreconciled" for item in obligations.values()):
        limitations.append(
            "Historical obligations without reliable ID-linked dispositions remain unreconciled; they are not automatically proposed as mandatory work."
        )
    return {
        "version": 1,
        "project_id": project_id,
        "session_count": len(ordered),
        "project_status": "not_determined",
        "scope_note": "Latest saved local reviews by strategy. Project completion and independent correctness are not inferred.",
        "findings": findings,
        "current_finding_ids": current,
        "obligations": list(obligations.values()),
        "next_investigations": next_questions,
        "changes": list(reversed(changes)),
        "failures": failures,
        "limitations": limitations,
    }


def current_understanding(path: str) -> CurrentUnderstanding:
    view = inspect_project(path)
    records, unavailable = read_session_snapshot(path)
    return build_current_understanding(view.project.id, records, unavailable_records=unavailable)
