"""Durable, project-scoped publication-reference compilation.

Publication references are untrusted editorial guidance, not research evidence.
The cached checklist is keyed by the complete effective reference selection and
the hashes of the selected readable excerpts. A dispatched call is never replayed.
"""

from __future__ import annotations

import hashlib
import json
import math
import os
from collections.abc import Awaitable, Callable, Mapping
from datetime import UTC, datetime
from pathlib import Path
from typing import Any

MAX_ITEMS = 12
MAX_GUIDANCE_CHARS = 3000
SCHEMA = 2


def _hash(value: Any) -> str:
    return hashlib.sha256(
        json.dumps(value, sort_keys=True, ensure_ascii=False, separators=(",", ":")).encode()
    ).hexdigest()


def _now() -> str:
    return datetime.now(UTC).isoformat()


def fingerprint(
    project_id: str,
    kind: str,
    sources: list[dict[str, Any]],
    reference_selection_sha256: str = "",
    compilation_context: Mapping[str, Any] | None = None,
) -> str:
    return _hash(
        {
            "schema": SCHEMA,
            "project_id": project_id,
            "kind": kind,
            "reference_selection_sha256": reference_selection_sha256,
            "compilation_context": dict(compilation_context or {}),
            "sources": [
                {
                    name: source.get(name)
                    for name in ("url", "title", "tier", "sha256", "reference_set_sha256")
                }
                | {
                    "actual_excerpt_sha256": (
                        hashlib.sha256(source["excerpt"].encode()).hexdigest()
                        if isinstance(source.get("excerpt"), str)
                        else None
                    )
                }
                for source in sources[:3]
            ],
        }
    )


def validate(value: Any, key: str) -> bool:
    if not isinstance(value, dict) or value.get("schema") != SCHEMA:
        return False
    if value.get("fingerprint") != key:
        return False
    if value.get("status") not in {"running", "completed", "skipped", "fallback"}:
        return False
    lines = value.get("checklist")
    kept = value.get("retained_urls")
    dropped = value.get("omitted_urls")
    usage = value.get("provider_usage")
    if (
        value.get("record_sha256")
        != _hash({name: item for name, item in value.items() if name != "record_sha256"})
        or type(value.get("provider_calls_attempted")) is not int
        or value["provider_calls_attempted"] not in (0, 1)
        or value.get("usage_status") not in {"pending", "measured", "unknown", "not_applicable"}
        or not isinstance(value.get("rationale"), str)
        or len(value["rationale"]) > 600
        or not isinstance(value.get("started_at"), str)
        or (value.get("finished_at") is not None and not isinstance(value["finished_at"], str))
    ):
        return False
    if usage is not None and (
        not isinstance(usage, dict)
        or type(usage.get("input_tokens")) is not int
        or type(usage.get("cached_input_tokens")) is not int
        or type(usage.get("output_tokens")) is not int
        or usage["input_tokens"] < 0
        or not 0 <= usage["cached_input_tokens"] <= usage["input_tokens"]
        or usage["output_tokens"] < 0
        or (
            usage.get("estimated_cost_usd") is not None
            and (
                type(usage["estimated_cost_usd"]) not in (int, float)
                or not math.isfinite(usage["estimated_cost_usd"])
                or not 0 <= usage["estimated_cost_usd"] <= 1000
            )
        )
    ):
        return False
    return (
        isinstance(lines, list)
        and len(lines) <= MAX_ITEMS
        and all(isinstance(s, str) and 0 < len(s) <= 400 for s in lines)
        and sum(map(len, lines)) <= MAX_GUIDANCE_CHARS
        and isinstance(kept, list)
        and isinstance(dropped, list)
        and len(kept) + len(dropped) <= 3
        and all(isinstance(s, str) and len(s) <= 2048 for s in kept + dropped)
        and len(set(kept + dropped)) == len(kept) + len(dropped)
        and not (set(kept) & set(dropped))
        and value.get("checklist_sha256") == _hash(lines)
        and (value["status"] != "completed" or (bool(kept) and bool(lines)))
    )


def read(path: Path, key: str) -> dict[str, Any] | None:
    if path.is_symlink() or not path.is_file():
        return None
    try:
        if path.stat().st_size > 24000:
            return None
        value = json.loads(path.read_text(encoding="utf-8"))
    except (OSError, ValueError):
        return None
    return value if validate(value, key) else None


def save(path: Path, value: Mapping[str, Any]) -> None:
    if path.is_symlink():
        raise OSError("Unsafe publication-reference cache")
    # Seal the entire decision and its accounting, not only the checklist:
    # changing retained/omitted URLs must invalidate the cache as well.
    sealed = dict(value)
    sealed["record_sha256"] = _hash(
        {name: item for name, item in sealed.items() if name != "record_sha256"}
    )
    if isinstance(value, dict):
        value["record_sha256"] = sealed["record_sha256"]
    encoded = json.dumps(sealed, ensure_ascii=False, sort_keys=True).encode()
    if len(encoded) > 24000:
        raise ValueError("Publication-reference cache too large")
    temp = path.with_name(path.name + "." + os.urandom(8).hex() + ".tmp")
    try:
        with temp.open("xb") as output:
            os.fchmod(output.fileno(), 0o600)
            output.write(encoded)
            output.flush()
            os.fsync(output.fileno())
        os.replace(temp, path)
        fd = os.open(path.parent, os.O_RDONLY)
        try:
            os.fsync(fd)
        finally:
            os.close(fd)
    finally:
        temp.unlink(missing_ok=True)


def guidance(value: Mapping[str, Any], sources: list[dict[str, Any]]) -> list[dict[str, str]]:
    if value.get("status") == "completed":
        return [{"writing_guidance": line} for line in value.get("checklist", [])]
    if value.get("status") == "skipped":
        return []
    from sigma import paper_writing_sources

    return paper_writing_sources.prompt_material(sources)


async def ensure(
    path: Path,
    project_id: str,
    kind: str,
    sources: list[dict[str, Any]],
    compile_call: Callable[[list[dict[str, Any]], str], Awaitable[Mapping[str, Any]]],
    reference_selection_sha256: str = "",
    *,
    compilation_context: Mapping[str, Any] | None = None,
    allow_paid_call: bool = True,
    fallback_reason: str = "insufficient_writing_headroom",
) -> dict[str, Any]:
    key = fingerprint(project_id, kind, sources, reference_selection_sha256, compilation_context)
    urls = [item["url"] for item in sources[:3]]
    previous = read(path, key)
    if previous is None and path.exists():
        # A valid cache from another reference selection may be replaced.
        # An unreadable or partially corrupted cache may represent a
        # dispatched-but-uncertain paid call for *this* selection. Do not
        # silently replay it, even if the validation failure is only in the
        # provider-usage fields.
        try:
            raw_previous = json.loads(path.read_text(encoding="utf-8"))
            valid_prior_selection = (
                isinstance(raw_previous, dict)
                and isinstance(raw_previous.get("fingerprint"), str)
                and validate(raw_previous, raw_previous["fingerprint"])
            )
        except (OSError, ValueError):
            valid_prior_selection = False
        if not valid_prior_selection:
            fallback = {
                "schema": SCHEMA,
                "fingerprint": key,
                "status": "fallback",
                "retained_urls": urls,
                "omitted_urls": [],
                "checklist": [],
                "checklist_sha256": _hash([]),
                "rationale": "Saved compiler state was invalid; uncertain paid call was not replayed.",
                "started_at": _now(),
                "finished_at": _now(),
                "provider_calls_attempted": 1,
                "usage_status": "unknown",
                "provider_usage": None,
                "failure_reason": "invalid_saved_cache_no_replay",
            }
            save(path, fallback)
            return fallback
    if previous is not None:
        # Never trust a cached decision listing a reference outside this exact
        # frozen selection, even when the checklist hash itself is valid.
        if sorted(previous["retained_urls"] + previous["omitted_urls"]) != sorted(urls):
            previous = {
                **previous,
                "status": "fallback",
                "retained_urls": urls,
                "omitted_urls": [],
                "checklist": [],
                "checklist_sha256": _hash([]),
                "failure_reason": "invalid_reference_membership",
                "finished_at": _now(),
            }
            save(path, previous)
        if previous["status"] == "running":
            previous = {
                **previous,
                "status": "fallback",
                "usage_status": "unknown",
                "failure_reason": "uncertain_dispatched_call",
                "finished_at": _now(),
            }
            save(path, previous)
        return previous
    record: dict[str, Any] = {
        "schema": SCHEMA,
        "fingerprint": key,
        "status": ("skipped" if not urls else "running" if allow_paid_call else "fallback"),
        "retained_urls": urls,
        "omitted_urls": [],
        "checklist": [],
        "checklist_sha256": _hash([]),
        "rationale": (
            "No readable publication references"
            if not urls
            else (
                "A previously recorded publication compiler call is uncertain; "
                "the missing cache was not treated as proof of non-dispatch."
            )
            if not allow_paid_call and fallback_reason == "uncertain_previous_attempt_cache_missing"
            else "Compilation skipped to preserve first paper-writing call capacity."
            if not allow_paid_call
            else ""
        ),
        "started_at": _now(),
        "finished_at": _now() if not urls or not allow_paid_call else None,
        "provider_calls_attempted": int(bool(urls and allow_paid_call)),
        "usage_status": "pending" if urls and allow_paid_call else "not_applicable",
        "provider_usage": None,
    }
    if urls and not allow_paid_call:
        record["failure_reason"] = fallback_reason
    # Do not change any part of a sealed decision after writing it: a funding
    # fallback also must remain valid across paper checkpoint recovery.
    save(path, record)  # Persist the dispatched marker *before* the provider call.
    if not urls or not allow_paid_call:
        return record
    try:
        response = await compile_call(sources, kind)
        retained = response.get("retained_urls", [])
        omitted = response.get("omitted_urls", [])
        lines = response.get("checklist", [])
        if (
            not isinstance(retained, list)
            or not isinstance(omitted, list)
            or len(retained) + len(omitted) != len(urls)
            or set(retained + omitted) != set(urls)
            or len(set(retained + omitted)) != len(urls)
            or not isinstance(lines, list)
            or not 1 <= len(lines) <= MAX_ITEMS
            or any(not isinstance(s, str) or not s.strip() or len(s) > 400 for s in lines)
            or sum(map(len, lines)) > MAX_GUIDANCE_CHARS
        ):
            raise ValueError("Invalid publication-reference compiler result")
        raw_usage = response.get("provider_usage")
        metered_usage = None
        if isinstance(raw_usage, dict):
            input_tokens = raw_usage.get("input_tokens")
            cached_tokens = raw_usage.get("cached_input_tokens")
            output_tokens = raw_usage.get("output_tokens")
            cost = raw_usage.get("estimated_cost_usd")
            if (
                type(input_tokens) is int
                and input_tokens >= 0
                and type(cached_tokens) is int
                and 0 <= cached_tokens <= input_tokens
                and type(output_tokens) is int
                and output_tokens >= 0
                and (
                    cost is None
                    or (type(cost) in (int, float) and math.isfinite(cost) and 0 <= cost <= 1000)
                )
            ):
                metered_usage = {
                    "input_tokens": input_tokens,
                    "cached_input_tokens": cached_tokens,
                    "output_tokens": output_tokens,
                    "estimated_cost_usd": cost,
                }
        record.update(
            {
                "status": "completed" if retained else "skipped",
                "usage_status": "measured" if metered_usage is not None else "unknown",
                "provider_usage": metered_usage,
                "retained_urls": retained,
                "omitted_urls": omitted,
                "checklist": lines if retained else [],
                "checklist_sha256": _hash(lines if retained else []),
                "rationale": str(response.get("rationale", ""))[:600],
                "finished_at": _now(),
            }
        )
    except Exception as exc:  # noqa: BLE001 - optional compiler falls back on provider/validation failures
        # No malformed guidance enters authoring; saved excerpts remain the fallback.
        # Cancellation (BaseException) leaves status=running, becoming fallback on resume.
        record.update(
            {
                "status": "fallback",
                "usage_status": "unknown",
                "failure_reason": type(exc).__name__,
                "finished_at": _now(),
            }
        )
    save(path, record)
    return record
