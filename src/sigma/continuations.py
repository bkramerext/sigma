"""Explicit human approval of frozen cross-strategy evidence; no inferred truth.

Companion records publish before their strategy under the project's write lock.
An unpublished orphan is ignored. Edits invalidate approval instead of silently
changing the approved question. Sessions copy the packet, never reread it mid-run.
"""

from __future__ import annotations

import hashlib
import json
import os
from dataclasses import asdict
from pathlib import Path
from typing import Any
from uuid import UUID

from pydantic import BaseModel, ConfigDict, Field

from sigma.projects import ProjectError, _stage, create_strategy, inspect_project

MAX_PACKET_BYTES = 64_000


class Rejection(BaseModel):
    model_config = ConfigDict(extra="forbid", strict=True)
    artifact_id: str = Field(min_length=36, max_length=36)
    rationale: str = Field(min_length=10, max_length=600)


class Approval(BaseModel):
    model_config = ConfigDict(extra="forbid", strict=True)
    parent_strategy_id: str = Field(min_length=36, max_length=36)
    title: str = Field(min_length=1, max_length=200)
    question: str = Field(min_length=10, max_length=1000)
    obligation_id: str | None = Field(default=None, max_length=64)
    source_artifact_ids: list[str] = Field(max_length=8)
    rejected_sources: list[Rejection] = Field(default_factory=list, max_length=8)
    preview_digest: str = Field(min_length=64, max_length=64)


def digest(value: Any) -> str:
    return hashlib.sha256(
        json.dumps(value, sort_keys=True, ensure_ascii=False).encode()
    ).hexdigest()


def proposal(path: str, parent_id: str, obligation_id: str | None = None) -> dict[str, Any]:
    from sigma.research_sessions import read_session_snapshot
    from sigma.research_state import build_current_understanding

    view = inspect_project(path)
    parent = next(
        (s for s in view.project.strategies if s.id == parent_id and not s.removed_at), None
    )
    if parent is None:
        raise ProjectError("Continuation parent is unavailable")
    sessions, unavailable = read_session_snapshot(path)
    if unavailable:
        raise ProjectError(
            "Some saved session records are unavailable; inspect them before approval"
        )
    state = build_current_understanding(view.project.id, sessions)
    obligation = next((o for o in state["obligations"] if o["id"] == obligation_id), None)
    if obligation_id and (
        not obligation or not obligation["actionable"] or obligation["strategy_id"] != parent_id
    ):
        raise ProjectError(
            "Choose an open obligation in the parent strategy; resolved/ambiguous duties cannot be proposed"
        )
    artifacts = {a["id"]: a for s in sessions for a in s.get("artifacts", [])}
    inherited = approved_packets(path, [parent_id], validate_dispatch=False).get(parent_id, {})
    inherited_negative = {r["artifact_id"] for r in inherited.get("sources", []) if r["mandatory"]}
    sources = []
    for finding in state["findings"]:
        source = finding["source"]
        artifact = artifacts.get(source["artifact_id"])
        if not artifact or not source["available"]:
            continue
        sources.append(
            {
                "artifact_id": source["artifact_id"],
                "source": source,
                "strategy_title": finding["strategy_title"],
                "claim": finding["text"],
                "status": finding["status"],
                "verification": finding["verification"],
                "evidence_kind": finding["evidence_kind"],
                "mandatory": source["artifact_id"] in inherited_negative
                or (
                    source["strategy_id"] == parent_id
                    and finding["status"] == "local_refutation_reported"
                )
                or bool(obligation and source in obligation["sources"]),
                "artifact_digest": digest(artifact),
                "artifact": artifact,
            }
        )
    # Refutations are selected by saved stop reason too; no language classifier.
    for row in sources:
        if (
            row["source"]["strategy_id"] == parent_id
            and row["artifact"].get("skeptic_output", {}).get("stop_reason")
            == "decisive_counterexample"
        ):
            row["mandatory"] = True
    result = {
        "project_id": view.project.id,
        "parent_strategy_id": parent_id,
        "parent_digest": digest(asdict(parent)),
        "obligation": obligation,
        "question": obligation["text"] if obligation else "",
        "sources": sources,
        "caution": "Recorded claims are unverified. Local refutations remain mandatory; no project solution is inferred. Select only relevant transfers. Original scoped duties stay open until explicitly reviewed.",
    }
    result["preview_digest"] = digest(result)
    return result


def approve(path: str, approval: Approval):
    preview = proposal(path, approval.parent_strategy_id, approval.obligation_id)
    if preview["preview_digest"] != approval.preview_digest:
        raise ProjectError("Research changed since preview; inspect and approve a fresh proposal")
    accepted = approval.source_artifact_ids
    rejected = [r.artifact_id for r in approval.rejected_sources]
    catalog = {s["artifact_id"]: s for s in preview["sources"]}
    mandatory = {s["artifact_id"] for s in preview["sources"] if s["mandatory"]}
    if (
        len(set(accepted)) != len(accepted)
        or len(set(rejected)) != len(rejected)
        or set(accepted) & set(rejected)
        or not (set(accepted) | set(rejected)) <= catalog.keys()
        or not mandatory <= set(accepted)
        or not accepted
    ):
        raise ProjectError(
            "Select available sources exactly once, including mandatory local counterexamples/target evidence"
        )
    packet = {
        "version": 1,
        "project_id": preview["project_id"],
        "parent_strategy_id": approval.parent_strategy_id,
        "parent_digest": preview["parent_digest"],
        "question": approval.question.strip(),
        "obligation": preview["obligation"],
        "sources": [catalog[s] for s in accepted],
        "rejected_sources": [r.model_dump() for r in approval.rejected_sources],
        "unselected_artifact_ids": sorted(catalog.keys() - set(accepted) - set(rejected)),
        "caution": preview["caution"],
        "authorship": "researcher-approved continuation; sources retain their own provenance",
    }
    if len(json.dumps(packet, ensure_ascii=False).encode()) > MAX_PACKET_BYTES:
        raise ProjectError(
            "Selected evidence exceeds the 64 KB continuation packet; narrow the selection. No evidence was truncated"
        )

    # Rechecked inside the same project write lock that publishes the strategy.
    def publish(project, strategy):
        fresh = proposal(path, approval.parent_strategy_id, approval.obligation_id)
        if fresh["preview_digest"] != approval.preview_digest or project.id != packet["project_id"]:
            raise ProjectError("Research changed before approval; inspect again")
        record = {
            **packet,
            "strategy_id": strategy.id,
            "strategy_digest": digest(strategy.approach),
            "approved_at": strategy.created_at,
        }
        record["packet_digest"] = digest(record)
        directory = Path(path).resolve() / "continuations"
        directory.mkdir(mode=0o700, exist_ok=True)
        if directory.is_symlink():
            raise ProjectError("Continuation storage cannot be a symbolic link")
        destination = directory / f"{strategy.id}.json"
        staged = _stage(
            directory, json.dumps(record, ensure_ascii=False, separators=(",", ":")).encode()
        )
        try:
            os.link(staged, destination)  # publish a complete private file; never overwrite
        finally:
            staged.unlink(missing_ok=True)

    return create_strategy(
        path, approval.title, approval.question.strip(), _continuation_writer=publish
    )


def approved_packets(
    path: str, strategy_ids: list[str] | None = None, *, validate_dispatch: bool = True
) -> dict[str, dict[str, Any]]:
    view = inspect_project(path)
    directory = Path(view.path) / "continuations"
    if directory.is_symlink():
        raise ProjectError("Continuation storage cannot be a symbolic link")
    result = {}
    for strategy in view.project.strategies:
        if strategy_ids is not None and strategy.id not in strategy_ids:
            continue
        UUID(strategy.id)
        file = directory / f"{strategy.id}.json"
        if not file.exists():
            # A missing record after deliberate file deletion is not recoverable;
            # normal project edits cannot remove this companion.
            continue
        if file.is_symlink() or file.stat().st_size > MAX_PACKET_BYTES + 2000:
            raise ProjectError("Invalid continuation packet storage")
        try:
            record = json.loads(file.read_text())
            payload = {k: v for k, v in record.items() if k != "packet_digest"}
            if (
                digest(payload) != record["packet_digest"]
                or record["project_id"] != view.project.id
                or record["strategy_id"] != strategy.id
                or (validate_dispatch and record["strategy_digest"] != digest(strategy.approach))
            ):
                raise ValueError()
        except (ValueError, KeyError, TypeError) as exc:
            raise ProjectError(
                "Continuation approval is invalid or strategy was edited; approve a new fork"
            ) from exc
        if validate_dispatch:
            from sigma.research_sessions import read_session_snapshot

            sessions, unavailable = read_session_snapshot(path)
            artifacts = {
                (row["id"], a["id"]): a for row in sessions for a in row.get("artifacts", [])
            }
            if unavailable or any(
                digest(artifacts.get((row["source"]["session_id"], row["artifact_id"])))
                != row["artifact_digest"]
                for row in record["sources"]
            ):
                raise ProjectError(
                    "Approved source evidence is missing or changed; inspect and approve a fresh fork"
                )
        result[strategy.id] = record
    return result


def compact_dispatch_packet(packet: dict[str, Any]) -> dict[str, Any]:
    """Lossless exact-text interning, never semantic selection or truncation.

    Full approved artifacts remain in the session. Only identical long strings
    repeated in the dispatched packet use aliases. Every source/status/objection
    remains reconstructable; an alias is not a verified assertion.
    """
    from collections import Counter

    counts: Counter[str] = Counter()

    def count(value):
        if isinstance(value, str) and len(value) >= 120:
            counts[value] += 1
        elif isinstance(value, dict):
            if "$sigma_text" in value or "dispatch_text_pool" in value:
                raise ProjectError("Reserved text-pool key in approved evidence; inspect source")
            for child in value.values():
                count(child)
        elif isinstance(value, list):
            for child in value:
                count(child)

    count(packet)
    names = {
        value: f"T{index + 1}" for index, (value, copies) in enumerate(counts.items()) if copies > 1
    }

    def encode(value):
        if isinstance(value, str) and value in names:
            return {"$sigma_text": names[value]}
        if isinstance(value, dict):
            return {key: encode(child) for key, child in value.items()}
        if isinstance(value, list):
            return [encode(child) for child in value]
        return value

    encoded = encode(packet)
    encoded["dispatch_text_pool"] = {name: value for value, name in names.items()}
    encoded["dispatch_encoding"] = "exact-text-pool-v1"
    # Alias path overhead can exceed the savings for small packets. Keep the
    # original unchanged rather than spending more context on an optimization.
    if len(json.dumps(encoded, ensure_ascii=False)) >= len(json.dumps(packet, ensure_ascii=False)):
        return packet
    return encoded


def expand_dispatch_packet(packet: dict[str, Any]) -> dict[str, Any]:
    """For inspection/tests: reconstruct the exact immutable approved packet."""
    if packet.get("dispatch_encoding") != "exact-text-pool-v1":
        return packet
    texts = packet.get("dispatch_text_pool", {})

    def decode(value):
        if isinstance(value, dict) and set(value) == {"$sigma_text"}:
            name = value["$sigma_text"]
            if name not in texts or not isinstance(texts[name], str):
                raise ProjectError("Continuation text reference is unavailable")
            return texts[name]
        if isinstance(value, dict):
            return {key: decode(child) for key, child in value.items()}
        if isinstance(value, list):
            return [decode(child) for child in value]
        return value

    return decode(
        {
            key: value
            for key, value in packet.items()
            if key not in {"dispatch_encoding", "dispatch_text_pool"}
        }
    )
