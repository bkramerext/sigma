"""Bounded, source-backed *candidate* discovery from an indexed local Lean root.

This is a first navigation stage, not a formal dependency extractor. Rankings
are lexical evidence for review; they do not establish theorem dependencies.
"""

from __future__ import annotations

import re
from collections.abc import Callable
from typing import Any

from sigma import lean_explorer, lean_explorer_local, lean_explorer_map
from sigma.projects import ProjectError

MAX_SCAN_FILES = 20_000
MAX_CANDIDATES = 12
MAX_SCAN_SOURCE_BYTES = 3 * 1024 * 1024
MIN_TRIAL_FILE_BYTES = 48 * 1024
# A large, representative source file in the pinned Alpöge mirror.
AUTOMORPHIC_TRIAL_FILE = (
    "src/Development/AbelianVarietyTheory/Definitions/AutomorphicMembership/ExistsSameData.lean"
)

_WORD = re.compile(r"[A-Za-z][A-Za-z0-9]*")
_CAMEL = re.compile(r"(?<=[a-z0-9])(?=[A-Z])")
_STOP = frozenset(
    [
        "a",
        "an",
        "and",
        "are",
        "as",
        "at",
        "be",
        "by",
        "can",
        "does",
        "do",
        "for",
        "from",
        "how",
        "in",
        "into",
        "is",
        "it",
        "its",
        "of",
        "on",
        "or",
        "our",
        "over",
        "should",
        "that",
        "the",
        "their",
        "them",
        "there",
        "these",
        "this",
        "to",
        "use",
        "using",
        "was",
        "were",
        "what",
        "when",
        "where",
        "which",
        "who",
        "why",
        "will",
        "with",
        "without",
        "mathematical",
        "mathematics",
        "proof",
        "proofs",
        "lean",
        "theorem",
        "theorems",
        "lemma",
        "lemmas",
        "result",
        "results",
        "theory",
        "formal",
        "source",
        "explain",
        "connect",
        "connection",
        "connections",
        "arguments",
        "argument",
        "possible",
        "input",
        "inputs",
        "make",
        "needed",
        "need",
        "later",
        "many",
        "entire",
    ]
)


def _words(value: str) -> set[str]:
    # Segment Lean-style CamelCase identifiers as well as prose.
    value = _CAMEL.sub(" ", value.replace("_", " ").replace("-", " "))
    return {
        item.lower()
        for item in _WORD.findall(value)
        if len(item) >= 4 and item.lower() not in _STOP
    }


def _score(
    path: str, kind: str, name: str, excerpt: str, terms: set[str], hints: list[str]
) -> tuple[int, list[str]]:
    identifier = _words(name)
    location = _words(path.rsplit(".lean", 1)[0])
    source = _words(excerpt)
    direct_hints = [
        value for value in hints if value.lower() in (name.lower(), name.split(".")[-1].lower())
    ]
    name_hits = sorted(identifier & terms)
    path_hits = sorted(location & terms)
    body_hits = sorted((source & terms) - identifier - location)
    score = 15 * len(direct_hints) + 7 * len(name_hits) + 3 * len(path_hits)
    score += min(4, len(body_hits))
    if kind in {"theorem", "lemma"} and score > 0:
        score += 2
    reasons = [
        *(f"named hint: {hint}" for hint in direct_hints),
        *(f"declaration name: {term}" for term in name_hits),
        *(f"source path: {term}" for term in path_hits),
        *(f"source text: {term}" for term in body_hits[:4]),
    ]
    return score, reasons


def _trial_file(paths: list[str], terms: set[str], section_id: str) -> tuple[str, int]:
    """Select one sizeable section-related indexed file; never leave the local root."""
    indexed = set(paths)
    if section_id == "automorphic-foundation" and AUTOMORPHIC_TRIAL_FILE in indexed:
        payload, _, _, _ = lean_explorer_local.read_module(AUTOMORPHIC_TRIAL_FILE)
        if MIN_TRIAL_FILE_BYTES <= len(payload) <= MAX_SCAN_SOURCE_BYTES:
            return AUTOMORPHIC_TRIAL_FILE, len(payload)

    likely = [path for path in paths if _words(path.rsplit(".lean", 1)[0]) & terms]
    likely.sort(key=lambda path: (-len(_words(path.rsplit(".lean", 1)[0]) & terms), path))
    best_path = ""
    best_size = 0
    for path in likely[:250]:
        try:
            payload, _, _, _ = lean_explorer_local.read_module(path)
        except (ProjectError, OSError):
            continue
        if (
            MIN_TRIAL_FILE_BYTES <= len(payload) <= MAX_SCAN_SOURCE_BYTES
            and len(payload) > best_size
        ):
            best_path, best_size = path, len(payload)
    if not best_path:
        raise ProjectError(
            "No large section-related Lean file (at least 48 KiB) was found "
            "in the indexed root. Choose a different section or source root."
        )
    return best_path, best_size


def discover(
    section_id: str,
    progress: Callable[[int, int, int, str], None] | None = None,
    *,
    start_offset: int = 0,
    single_file_trial: bool = False,
) -> dict[str, Any]:
    """Search safely indexed local modules for candidate section evidence.

    A candidate gets a full source recheck when attached to a dossier. The
    lexical score is deliberately transparent and must not be interpreted as
    a proof dependency or evidence that the section map is correct.
    """
    section = lean_explorer_map.section(section_id)
    cfg = lean_explorer_local.source()
    if cfg is None:
        raise ProjectError("Index the local Lean directory before exploring.")
    indexed = lean_explorer_local.list_files(offset=0, limit=1)
    total = indexed["total_files"]
    # Reuse the validated index, not a second filesystem tree walker.
    paths: list[str] = []
    for offset in range(0, total, lean_explorer_local.MAX_QUERY_RESULTS):
        page = lean_explorer_local.list_files(
            offset=offset, limit=lean_explorer_local.MAX_QUERY_RESULTS
        )
        paths.extend(page["files"])
    paths.sort(key=lambda name: (not name.startswith("src/"), name))
    terms = _words(
        " ".join(
            [
                section["title"],
                section["question"],
                section["purpose"],
                *section.get("declaration_hints", []),
            ]
        )
    )
    chosen_file = ""
    chosen_bytes = 0
    if single_file_trial:
        if start_offset:
            raise ProjectError("A single-file trial starts from the beginning of its file.")
        chosen_file, chosen_bytes = _trial_file(paths, terms, section_id)
        scan = [chosen_file]
        total = 1
    else:
        if not 0 <= start_offset <= total:
            raise ProjectError("Invalid Lean discovery continuation offset.")
        scan = paths[start_offset : start_offset + MAX_SCAN_FILES]
    hints = section.get("declaration_hints", [])
    ranked: list[dict[str, Any]] = []
    declarations = 0
    matching = 0
    unreadable = 0
    for number, path in enumerate(scan, 1):
        try:
            payload, _, _, _ = lean_explorer_local.read_module(path)
            if len(payload) > MAX_SCAN_SOURCE_BYTES:
                unreadable += 1
                continue
            text = payload.decode("utf-8")
        except (ProjectError, UnicodeError, OSError):
            unreadable += 1
            continue
        lines = text.splitlines()
        found = lean_explorer._declarations(text)
        declarations += len(found)
        file_ranked: list[dict[str, Any]] = []
        seen_names: set[str] = set()
        for index, item in enumerate(found):
            # The current lexical reader resolves the first occurrence of a
            # name in a file. Do not suggest an ambiguous later occurrence.
            if item["name"] in seen_names:
                continue
            seen_names.add(item["name"])
            start = item["line"]
            end = found[index + 1]["line"] - 1 if index + 1 < len(found) else len(lines)
            excerpt = "\n".join(lines[start - 1 : min(start + 15, end)])
            score, reasons = _score(path, item["kind"], item["name"], excerpt, terms, hints)
            if score < 7 and not single_file_trial:
                continue
            if single_file_trial and score < 7:
                reasons = [
                    "one-file trial source sample; section relevance unverified",
                    *reasons,
                ]
            matching += 1
            file_ranked.append(
                {
                    "path": path,
                    "name": item["name"],
                    "kind": item["kind"],
                    "start_line": start,
                    "relevance_score": score,
                    "reasons": reasons,
                }
            )
        file_ranked.sort(key=lambda item: (-item["relevance_score"], item["start_line"]))
        ranked.extend(file_ranked[:3])
        # Bound memory even for roots with hundreds of thousands of declarations.
        if len(ranked) > 1200:
            ranked.sort(
                key=lambda item: (
                    -item["relevance_score"],
                    item["path"],
                    item["start_line"],
                )
            )
            ranked = ranked[:300]
        if progress is not None and (number % 100 == 0 or number == len(scan)):
            progress(start_offset + number, total, matching, path)

    ranked.sort(
        key=lambda item: (
            -item["relevance_score"],
            item["path"],
            item["start_line"],
            item["name"],
        )
    )
    # Avoid one large module crowding out all other source regions.
    per_file: dict[str, int] = {}
    shortlist: list[dict[str, Any]] = []
    for item in ranked:
        if per_file.get(item["path"], 0) >= 3:
            continue
        shortlist.append(item)
        per_file[item["path"]] = per_file.get(item["path"], 0) + 1
        if len(shortlist) >= MAX_CANDIDATES:
            break
    return {
        "section_id": section_id,
        "source_root_id": cfg["root_id"],
        "single_file_trial": single_file_trial,
        "selected_file": chosen_file,
        "selected_file_bytes": chosen_bytes,
        "index_type": "lexical heuristic discovery, not elaborated Lean dependencies",
        "start_offset": start_offset,
        "next_offset": start_offset + len(scan),
        "scanned_files": len(scan),
        "total_files": total,
        "complete": start_offset + len(scan) == total,
        "unreadable_files": unreadable,
        "candidate_declarations": declarations,
        "matching_declarations": matching,
        "candidates": shortlist,
        "warning": (
            "Candidates are scored using declaration names, source paths and "
            "nearby text. Section assignments and dependencies are unverified."
        ),
    }
