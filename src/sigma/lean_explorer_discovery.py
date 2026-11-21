"""Bounded, source-grounded discovery of relevant Lean declarations.

The local proof *root* is the only required file-system input. The selected
mathematical section provides the query; no manual file navigation is needed.

This is lexical retrieval, NOT Lean elaboration or a proof dependency graph.
Every result carries a source location, file hash and a reproducible score
explanation. Candidate connections are hypotheses until verified.
"""

from __future__ import annotations

import heapq
import re
import time
from collections.abc import Callable
from dataclasses import dataclass
from typing import Any

from sigma import lean_explorer, lean_explorer_local, lean_explorer_map
from sigma.projects import ProjectError

MAX_SCAN_FILES = 40_000
MAX_SCAN_BYTES = 320 * 1024 * 1024
MAX_SCAN_SECONDS = 120
MAX_CANDIDATES = 12
MAX_AUTO_SELECTED = 5
_PROGRESS_EVERY = 120
_WORDS = re.compile(r"[A-Za-z][a-z]*|[A-Z]+(?=[A-Z][a-z]|\b)|[A-Z]?[a-z]+|[0-9]+")
_IGNORE = frozenset(
    """which with from into that this these those then than what why where
    when which whose there here them they their were would should could does
    have has had some many most only other about across between against
    proof proves proving theorem definition lemma lemmas mathematics mathematical
    argument establishes establish understand understanding selected section
    explain explaining uses useful need needs formal formalization human reader
    result results assumptions input inputs source sources actual current
    developed support supporting foundations construction constructions
    theory estimates estimate theorem formalized lines selected identify
    independent relationship connect connects how an and the for are is
    it or of by in on to at as a be do can we its not all each with
    of zero true false nat int prop sorry namespace open import simp
    """.split()
)
_GENERICS = frozenset({"structure", "field", "value", "base", "step", "main", "aux", "test"})


@dataclass(frozen=True)
class _Hit:
    rank: int
    score: int
    path: str
    name: str
    line: int
    kind: str
    reasons: tuple[str, ...]


def _tokens(value: str) -> set[str]:
    # Split CamelCase, snake_case, acronyms and mixed Lean identifiers.
    clean = re.sub(r"([a-z0-9])([A-Z])", r"\1 \2", value.replace("_", " "))
    clean = re.sub(r"([A-Z])([A-Z][a-z])", r"\1 \2", clean)
    return {
        x.lower()
        for x in _WORDS.findall(clean)
        if len(x) >= 3 and x.lower() not in _IGNORE and x.lower() not in _GENERICS
    }


def _terms(section: dict[str, Any]) -> tuple[set[str], set[str]]:
    anchor = _tokens(section["title"])
    context = _tokens(section["purpose"] + " " + section["question"])
    for hint in section.get("declaration_hints", []):
        anchor.update(_tokens(hint))
    if not anchor and not context:
        raise ProjectError("The selected section has no usable discovery terms.")
    return anchor, context - anchor


def _rank(
    path: str,
    name: str,
    kind: str,
    declaration_line: str,
    neighboring_lines: str,
    anchors: set[str],
    context: set[str],
    hints: list[str],
) -> tuple[int, tuple[str, ...]]:
    name_tokens = _tokens(name)
    path_tokens = _tokens(path)
    line_tokens = _tokens(declaration_line)
    nearby_tokens = _tokens(neighboring_lines)
    n_anchor = name_tokens & anchors
    n_context = name_tokens & context
    p_anchor = path_tokens & anchors
    p_context = path_tokens & context
    body_anchor = (line_tokens | nearby_tokens) & anchors
    body_context = (line_tokens | nearby_tokens) & context
    exact = any(hint.lower() in name.lower() for hint in hints if len(hint) >= 4)
    score = (
        45 * bool(exact)
        + 14 * len(n_anchor)
        + 7 * len(n_context)
        + 4 * len(p_anchor)
        + 2 * len(p_context)
        + 2 * len(body_anchor)
        + len(body_context)
        + (2 if kind in {"theorem", "lemma"} else 0)
    )
    reasons: list[str] = []
    if exact:
        reasons.append("source declaration matches a section seed name")
    if n_anchor or n_context:
        reasons.append("declaration identifier: " + ", ".join(sorted(n_anchor | n_context)[:6]))
    if p_anchor or p_context:
        reasons.append("module path: " + ", ".join(sorted(p_anchor | p_context)[:5]))
    if body_anchor or body_context:
        reasons.append("declaration text: " + ", ".join(sorted(body_anchor | body_context)[:6]))
    return score, tuple(reasons)


def discover(
    section_id: str,
    progress: Callable[[int, int, int, str], None] | None = None,
    *,
    limit: int = MAX_CANDIDATES,
) -> dict[str, Any]:
    """Rank actual declarations throughout an indexed local Lean tree.

    Data is scanned in bounded batches; progress is real (files, bytes,
    candidate count). A stopped or oversized scan does not return partial
    evidence as though it were complete.
    """
    lean_explorer_local.require_local()
    section = lean_explorer_map.section(section_id)
    if not 1 <= limit <= MAX_CANDIDATES:
        raise ProjectError("Invalid number of evidence candidates.")
    source = lean_explorer_local.source()
    if source is None:
        raise ProjectError("Index the local Lean root before discovering evidence.")
    paths, _ = lean_explorer_local._modules()
    if len(paths) > MAX_SCAN_FILES:
        raise ProjectError(
            "The indexed Lean source has more than 40,000 modules. "
            "A larger-scale incremental index is needed; discovery has not begun."
        )
    anchors, context = _terms(section)
    hints = section.get("declaration_hints", [])
    started = time.monotonic()
    bytes_scanned = 0
    read_files = 0
    matched = 0
    skipped_large = 0
    # Keep a small heap, not all declarations, regardless of proof size.
    best: list[tuple[int, int, _Hit]] = []
    serial = 0
    for path in paths:
        if time.monotonic() - started > MAX_SCAN_SECONDS:
            raise ProjectError(
                "Discovery exceeded its 120-second scan budget; no incomplete scope was saved."
            )
        try:
            payload, _, _, _ = lean_explorer_local.read_module(path)
        except ProjectError as exc:
            if "exceeds the per-file source limit" in str(exc):
                skipped_large += 1
                continue
            raise
        bytes_scanned += len(payload)
        if bytes_scanned > MAX_SCAN_BYTES:
            raise ProjectError(
                "Discovery reached its 320 MiB scan budget; no incomplete scope was saved."
            )
        read_files += 1
        try:
            text = payload.decode("utf-8")
        except UnicodeDecodeError:
            continue
        lines = text.splitlines()
        # Take only the declaration preface and a small, local proof neighborhood.
        # Match quality is evidence of *lexical relevance*, not proof dependency.
        for dec in lean_explorer._declarations(text):
            start = dec["line"] - 1
            name = dec["name"]
            score, reasons = _rank(
                path,
                name,
                dec["kind"],
                lines[start],
                "\n".join(lines[start + 1 : min(start + 10, len(lines))]),
                anchors,
                context,
                hints,
            )
            if score < 7 or not reasons:
                continue
            matched += 1
            serial += 1
            hit = _Hit(serial, score, path, name, dec["line"], dec["kind"], reasons)
            value = (score, serial, hit)
            if len(best) < max(limit * 7, 28):
                heapq.heappush(best, value)
            elif score > best[0][0]:
                heapq.heapreplace(best, value)
        if progress is not None and read_files % _PROGRESS_EVERY == 0:
            progress(read_files, len(paths), bytes_scanned, path)
    if progress is not None:
        progress(read_files, len(paths), bytes_scanned, "complete")
    ordered = sorted((hit for _, _, hit in best), key=lambda x: (-x.score, x.path, x.line))
    # Avoid a single large module monopolizing a multi-module investigation.
    per_file: dict[str, int] = {}
    result: list[dict[str, Any]] = []
    for hit in ordered:
        if per_file.get(hit.path, 0) >= 2:
            continue
        if len(result) >= limit:
            break
        # Re-read the exact match (with actual file checksum and excerpt) so
        # a candidate can be inspected or added without trusting search text.
        item = lean_explorer.declaration(hit.path, hit.name, source_mode="local")
        result.append(
            {
                **item,
                "relevance_score": hit.score,
                "why_candidate": list(hit.reasons),
                "status": "lexical_candidate_not_dependency",
            }
        )
        per_file[hit.path] = per_file.get(hit.path, 0) + 1
    return {
        "section_id": section_id,
        "section_title": section["title"],
        "source_root_id": source["root_id"],
        "source_directory": source["directory"],
        "files_scanned": read_files,
        "bytes_scanned": bytes_scanned,
        "matching_declarations": matched,
        "skipped_large_files": skipped_large,
        "index_type": "lexical cross-module candidate retrieval; NOT elaborated Lean dependencies",
        "complete": True,
        "candidates": result,
    }
