#!/usr/bin/env python3
"""Read-only single-section stream diagnosis. DRY RUN unless --execute.

Uses one saved paper checkpoint and the exact production section instructions,
schema and request payload. --execute dispatches exactly one possibly paid call.
No paper, research, project, or checkpoint writes occur.
"""
from __future__ import annotations

import argparse
import ast
import asyncio
import hashlib
import inspect
import json
import os
import sys
import textwrap
from collections import Counter
from datetime import UTC, datetime
from pathlib import Path
from time import monotonic
from typing import Any

import httpx

from sigma import papers, publication_reference_compiler
from sigma.local_config import load_local_config
from sigma.openai_connection import auth_context
from sigma.plan_stream import completed
from sigma.paper_stream_guard import JSONWhitespaceGuard, JSONWhitespaceStall

TARGET_ID = "b546bb60-845b-4afb-a9b8-ad2b8748a832"
ORIGINAL_BYTES = 74271
ORIGINAL_INSTRUCTIONS = 3917


class SampleComplete(Exception):
    pass


def project_from_checkpoint(file: Path) -> Path:
    root = file.parent.parent
    if root.name == "papers":
        return root.parent
    if root.name.startswith(".") and root.name.endswith(".papers"):
        return root.with_name(root.name[1:-7])
    raise ValueError(f"Unexpected checkpoint layout: {file}")


def find_project(given: str | None) -> Path:
    if given:
        return Path(given).expanduser().resolve()
    roots = [Path.cwd() / "projects"]
    if os.environ.get("SIGMA_PROJECTS_ROOT"):
        roots.append(Path(os.environ["SIGMA_PROJECTS_ROOT"]).expanduser())
    found: list[Path] = []
    for root in dict.fromkeys(roots):
        if not root.is_dir():
            continue
        for file in root.rglob("checkpoint.json"):
            if file.is_symlink() or file.parent.name != ".long-paper-work":
                continue
            try:
                if json.loads(file.read_text()).get("project_id") == TARGET_ID:
                    found.append(project_from_checkpoint(file))
            except (OSError, ValueError, TypeError):
                continue
    found = list(dict.fromkeys(found))
    if len(found) != 1:
        raise ValueError(f"Found {len(found)} matching projects. Specify --project PATH.")
    return found[0]


def exact_base_instructions() -> str:
    # Read the same Python string constant used in _generate_long_draft;
    # do not maintain a second, potentially divergent prompt in this script.
    source = textwrap.dedent(inspect.getsource(papers._generate_long_draft))
    node = ast.parse(source).body[0]
    for statement in node.body:
        if isinstance(statement, ast.Assign):
            if any(isinstance(t, ast.Name) and t.id == "section_instructions"
                   for t in statement.targets):
                return ast.literal_eval(statement.value)
    raise ValueError("Could not locate canonical section instructions")


def construct(work: dict[str, Any], number: int) -> tuple[str, str, bool]:
    plan = papers.LongPaperPlan.model_validate(work["plan"])
    if not 1 <= number <= len(plan.sections):
        raise ValueError("Section outside frozen outline")
    if str(number) in work.get("section_drafts", {}):
        raise ValueError("Section already authored; refusing to replay")
    if str(number) not in work.get("section_dispatches", {}):
        raise ValueError("Section was never dispatched; refusing to create new work")
    section = plan.sections[number - 1]
    package = work["frozen_package"]
    notes = [papers.EvidenceNote.model_validate(n) for n in work["evidence_notes"]]
    data = next((s["data"] for s in package["sources"] if s["kind"] == "project"), {})
    discipline = data.get("investigation_type", "default")
    guidance = publication_reference_compiler.guidance(
        work.get("publication_compilation", {}), list(work.get("writing_sources", []))
    )
    visuals = bool(work.get("include_diagrams", True))
    instructions = exact_base_instructions()
    instructions += (
        "\n\nSelected paper-writing sources describe academic presentation only. "
        "Do not infer new research facts or citations from them."
    )
    instructions += "\n\nRESEARCH TYPE AND WRITING STYLE: " + papers._paper_style(discipline)[3]
    instructions += "\n\n" + papers._subject_methodology(discipline)
    if visuals:
        instructions += "\n\n" + papers.SECTION_TABLE_INSTRUCTIONS
    selected = [n.model_dump() for n in notes if set(n.evidence_refs).intersection(section.evidence_refs)]
    value = {
        "title": plan.title,
        "project_question": str(data.get("problem", ""))[:3000],
        "investigation_type": discipline,
        "publication_references": data.get("publication_references", []),
        "publication_reference_urls": data.get("publication_reference_urls", []),
        "paper_writing_methodology": guidance,
        "shared_claim_register": [
            c.model_dump() for c in plan.claims if c.id in section.claim_ids
        ],
        "section_number": number,
        "section_plan": section.model_dump(),
        "paper_wide_thesis": plan.abstract,
        "paper_section_roles": [
            {"number": i, "heading": p.heading, "purpose": p.purpose}
            for i, p in enumerate(plan.sections, 1)
        ],
        "evidence_notes": selected,
    }
    if work.get("evidence_strategy") == "structured_v1":
        original = papers._research_integrity_records(package)
        room = max(0, min(60000, 214000 - len(papers._json(value))))
        value["original_research_excerpts"] = papers._section_original_excerpts(
            original, set(section.evidence_refs), section.heading + " " + section.purpose, room
        )
    return papers._provider_input_text(value, "sigma_long_paper_section", 220000), instructions, visuals


def recurrence(text: str) -> dict[str, Any]:
    slices = [text[i:i + 128] for i in range(0, max(0, len(text) - 127), 32)]
    counts = Counter(slices)
    return {
        "sample_windows": len(slices),
        "repeat_fraction": round(sum(n - 1 for n in counts.values() if n > 1)
                                 / max(1, len(slices)), 3),
        "max_repeat": max(counts.values(), default=0),
    }


def section_wire_schema(visuals: bool, layout: str) -> dict[str, Any]:
    """Reorder only keys, preserving the exact production field contracts."""
    schema = papers._paper_response_schema(papers.LongSectionDraft, include_diagrams=visuals)
    if layout == "prose-last":
        original = schema["properties"]
        order = [key for key in ("tables", "examples", "paragraphs") if key in original]
        if set(order) != set(original):
            raise ValueError("Unexpected section schema fields; refusing changed-shape diagnostic")
        schema["properties"] = {key: original[key] for key in order}
        schema["required"] = order
    elif layout != "production":
        raise ValueError(f"Unknown diagnostic layout: {layout}")
    return schema


async def probe(args: argparse.Namespace, work: dict[str, Any], payload: str,
                instructions: str, visuals: bool, emit: Any) -> None:
    auth = await auth_context()
    if auth["mode"] != "chatgpt" or not auth["token"] or auth["status"] != "connected":
        raise ValueError("Connect your ChatGPT account first; no call was dispatched")
    schema = section_wire_schema(visuals, args.schema_layout)
    request = {
        "model": work["model"], "store": False,
        "reasoning": {"effort": work["reasoning_effort"]},
        "instructions": instructions,
        "input": [{"role": "user", "content": payload}],
        "text": {"format": {"type": "json_schema", "name": "sigma_long_paper_section",
                            "strict": True,
                            "schema": schema}},
        "stream": True,
    }
    fragments: list[str] = []
    whitespace_guard = JSONWhitespaceGuard()
    types: Counter[str] = Counter()
    seen = 0
    size = 0
    begin = monotonic()

    def event_seen(kind: str, byte_count: int) -> None:
        types[kind] += 1

    def text_seen(delta: str) -> None:
        nonlocal seen, size
        seen += 1
        size += len(delta.encode())
        fragments.append(delta)
        try:
            whitespace_guard.observe(delta)
        except JSONWhitespaceStall:
            emit("whitespace_stall", deltas=seen, bytes=size,
                 consecutive_whitespace=whitespace_guard.consecutive,
                 elapsed_s=round(monotonic()-begin, 1))
            raise
        if seen == 1 or seen % 500 == 0:
            joined = "".join(fragments)
            emit("progress", deltas=seen, bytes=size, elapsed_s=round(monotonic()-begin, 1),
                 repetition=recurrence(joined[-24000:]), sample_tail=joined[-1200:])
        if seen >= args.max_deltas or size >= args.max_bytes:
            raise SampleComplete

    outcome = "unknown"
    emit("dispatch", model=request["model"], effort=work["reasoning_effort"],
         schema_layout=args.schema_layout, schema_fields=list(schema["properties"]),
         max_seconds=args.max_seconds, max_deltas=args.max_deltas, max_bytes=args.max_bytes)
    try:
        async with asyncio.timeout(args.max_seconds):
            async with httpx.AsyncClient(timeout=None, trust_env=False,
                                         follow_redirects=False) as client:
                async with client.stream(
                    "POST", "https://api.openai.com/v1/responses",
                    headers={"Authorization": "Bearer " + auth["token"],
                             "Accept": "text/event-stream"}, json=request,
                ) as response:
                    emit("headers", http_status=response.status_code)
                    if response.status_code != 200:
                        raise RuntimeError(f"HTTP {response.status_code}")
                    result = await completed(
                        response, max_stream_bytes=None, max_event_chars=4000000,
                        max_events=100000, max_text_bytes=papers.MAX_RESPONSE_BYTES,
                        on_event_observed=event_seen, on_text_delta=text_seen,
                    )
                    items = [
                        part["text"]
                        for item in result.get("output", [])
                        if isinstance(item, dict) and item.get("type") == "message"
                        for part in item.get("content", [])
                        if isinstance(part, dict) and part.get("type") == "output_text"
                    ]
                    if len(items) != 1:
                        raise ValueError("Provider completed without one JSON output text")
                    decoded = json.loads(items[0])
                    if not isinstance(decoded, dict) or set(decoded) != set(schema["required"]):
                        raise ValueError("Provider output missing or adding strict schema fields")
                    parsed = papers.LongSectionDraft.model_validate_json(items[0])
                    outcome = "validated"
                    emit("provider_validated", usage=result.get("usage"),
                         paragraphs=len(parsed.paragraphs),
                         paragraph_words=sum(len(part.split()) for part in parsed.paragraphs),
                         tables=len(parsed.tables), examples=len(parsed.examples))
    except SampleComplete:
        outcome = "sample_limit"
    except JSONWhitespaceStall:
        outcome = "whitespace_stall"
    except TimeoutError:
        outcome = "time_limit"
    except Exception as exc:
        outcome = "error"
        emit("exception", error_type=type(exc).__name__, detail=str(exc)[:500])
    finally:
        text = "".join(fragments)
        emit("final", outcome=outcome, elapsed_s=round(monotonic()-begin, 1),
             deltas=seen, output_bytes=size, event_types=dict(types),
             repetition=recurrence(text), output_prefix=text[:64000],
             output_tail=text[-4000:])
        print(f"Probe ended: {outcome}. {seen} deltas, {size} output bytes.")


async def main() -> None:
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("--project", help="Path to original project; auto-detects Graph Atlas")
    parser.add_argument("--section", type=int, default=2)
    parser.add_argument("--execute", action="store_true", help="One potentially paid AI call")
    parser.add_argument("--self-test", action="store_true", help="Test guard and schema without AI")
    parser.add_argument("--schema-layout", choices=("production", "prose-last"), default="production",
                        help="Diagnostic wire-field order; production behavior unchanged")
    parser.add_argument("--max-seconds", type=int, default=90)
    parser.add_argument("--max-deltas", type=int, default=4000)
    parser.add_argument("--max-bytes", type=int, default=80000)
    parser.add_argument("--report", default=None, help="Unique diagnostic JSONL output path")
    args = parser.parse_args()
    if not 10 <= args.max_seconds <= 240 or not 200 <= args.max_deltas <= 10000:
        parser.error("Invalid diagnostic bounds")
    if not 4000 <= args.max_bytes <= 200000:
        parser.error("--max-bytes must be 4000..200000")
    if args.self_test:
        baseline = section_wire_schema(True, "production")
        changed = section_wire_schema(True, "prose-last")
        assert list(baseline["properties"]) == ["paragraphs", "tables", "examples"]
        assert list(changed["properties"]) == ["tables", "examples", "paragraphs"]
        assert changed["required"] == list(changed["properties"])
        assert all(baseline["properties"][key] == changed["properties"][key]
                   for key in changed["properties"])
        guard = JSONWhitespaceGuard()
        guard.observe('{"paragraphs":["Valid paragraph"],"tables":[]')
        try:
            for _ in range(1500):
                guard.observe(" " * 3)
        except JSONWhitespaceStall:
            print(f"SELF TEST PASSED: aborted after {guard.consecutive} JSON whitespace characters.")
            return
        raise AssertionError("Whitespace guard did not fire on the synthetic stall")
    load_local_config()
    path = find_project(args.project)
    work = papers._load_work(str(path))
    if not work or work.get("project_id") != TARGET_ID:
        raise ValueError("Wrong project or missing checkpoint")
    payload, instructions, visuals = construct(work, args.section)
    input_bytes = len(payload.encode())
    print(f"Project: {path}")
    print(f"Section {args.section}: input={input_bytes} bytes; instructions={len(instructions)} chars")
    print(f"Saved model: {work['model']}, effort: {work['reasoning_effort']}")
    if args.section == 2:
        section = papers.LongPaperPlan.model_validate(work["plan"]).sections[1]
        relevant_note_count = sum(
            bool(set(n.get("evidence_refs", ())).intersection(section.evidence_refs))
            for n in work["evidence_notes"]
        )
        # The checkpoint contains exactly 53 source-linked notes and two claims.
        # The archived log supplies length, but no original request content hash:
        # allow ONLY the original size or the observed +34-byte local reconstruction.
        # The report records this uncertainty. Never describe it as bitwise replay.
        if (
            input_bytes not in {ORIGINAL_BYTES, ORIGINAL_BYTES + 34}
            or len(instructions) != ORIGINAL_INSTRUCTIONS
            or work["model"] != "gpt-6.1-sol"
            or work["reasoning_effort"] != "medium"
            or len(section.evidence_refs) != 2
            or len(section.claim_ids) != 2
            or relevant_note_count != 53
        ):
            raise ValueError(
                "Input/model/plan/evidence diverges from original Paper 3. "
                "No provider request sent; report the preflight counts."
            )
        print(f"Section 2: {relevant_note_count} notes; 2 claims; 2 evidence refs")
        if input_bytes != ORIGINAL_BYTES:
            print(
                "NOTE: reconstructed payload differs from original by "
                f"+{input_bytes - ORIGINAL_BYTES} bytes; not a bitwise-identical replay."
            )
    schema = section_wire_schema(visuals, args.schema_layout)
    schema_sha256 = hashlib.sha256(json.dumps(schema, separators=(",", ":")).encode()).hexdigest()
    print(f"Diagnostic schema layout: {args.schema_layout}; fields={list(schema['properties'])}")
    if not args.execute:
        print("DRY RUN PASSED: no provider request, no files or checkpoint changed.")
        print("Repeat with --execute to run one bounded paid diagnostic.")
        return
    report = Path(
        args.report or str(Path.home() / "Desktop" /
                           f"sigma-section-probe-{args.schema_layout}.jsonl")
    ).expanduser()
    report.parent.mkdir(parents=True, exist_ok=True)
    fd = os.open(report, os.O_WRONLY | os.O_CREAT | os.O_EXCL, 0o600)
    with os.fdopen(fd, "w", encoding="utf-8") as stream:
        def emit(event: str, **items: Any) -> None:
            stream.write(json.dumps(
                {"event": event, "utc": datetime.now(UTC).isoformat(), **items},
                ensure_ascii=False, default=str,
            ) + "\n")
            stream.flush()
        emit("preflight", project_id=TARGET_ID, section=args.section,
             model=work["model"], effort=work["reasoning_effort"],
             schema_layout=args.schema_layout, schema_fields=list(schema["properties"]),
             schema_sha256=schema_sha256, input_bytes=input_bytes, original_logged_bytes=ORIGINAL_BYTES,
             input_byte_drift=input_bytes - ORIGINAL_BYTES,
             instructions_chars=len(instructions),
             input_sha256=hashlib.sha256(payload.encode()).hexdigest(),
             instructions_sha256=hashlib.sha256(instructions.encode()).hexdigest())
        await probe(args, work, payload, instructions, visuals, emit)
    print(f"Upload this file: {report}")
    print("Original checkpoint was not modified.")


if __name__ == "__main__":
    try:
        asyncio.run(main())
    except (ValueError, RuntimeError, OSError) as exc:
        print(f"PRECHECK: {exc}", file=sys.stderr)
        sys.exit(2)
