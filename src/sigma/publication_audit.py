"""Deterministic publication-requirement and repeated-prose audit.

Audits are conservative. Presence of a structure is never proof that a
scientific or editorial obligation was fulfilled. Each accepted requirement
remains visible in the saved paper, including requirements too complex to
verify mechanically.
"""

from __future__ import annotations

import re
from collections.abc import Mapping
from typing import Any


def _lines(markdown: str) -> list[str]:
    """Keep every nonblank clause, including those after the tenth kilobyte."""
    result: list[str] = []
    for line in markdown.splitlines():
        cleaned = re.sub(r"^\s*(?:[-*+]\s+|\d+[.)]\s+|#{1,6}\s+)", "", line).strip()
        if cleaned:
            result.append(cleaned)
    return result or ([markdown.strip()] if markdown.strip() else [])


def reconcile(requirements: str, paper: Mapping[str, Any]) -> list[dict[str, str]]:
    """Do not infer fulfillment from prose similarity or author assertions."""
    sections = paper.get("sections", [])
    if not isinstance(sections, list):
        sections = []
    tables = [
        table
        for section in sections
        if isinstance(section, dict)
        for table in section.get("tables", [])
        if isinstance(table, dict)
    ]
    diagrams = [item for item in paper.get("diagrams", []) if isinstance(item, dict)]
    examples = [
        item
        for section in sections
        if isinstance(section, dict)
        for item in section.get("examples", [])
        if isinstance(item, dict)
    ]
    result: list[dict[str, str]] = []
    for requirement in _lines(requirements):
        lowered = requirement.casefold()
        status = "needs_review"
        note = "Scientific and editorial fulfillment requires independent review."
        if re.search(r"\b(tables?|tabulations?)\b", lowered):
            if not tables:
                status, note = "missing", "A table was requested, but the paper has no table."
            elif re.search(r"\bcounterexamples?\b", lowered):
                has_counterexample_table = any(
                    re.search(r"\bcounterexamples?\b", str(table).casefold()) for table in tables
                )
                if not has_counterexample_table:
                    note = "Tables exist, but no counterexample table was identified; inspect their contents."
                else:
                    note = (
                        "A candidate counterexample table exists; verify it meets the requirement."
                    )
            else:
                note = "A table exists; verify its content meets the requirement."
        elif re.search(r"\b(diagrams?|figures?|charts?|plots?)\b", lowered):
            if not diagrams:
                status, note = (
                    "missing",
                    "A diagram or figure was requested, but none was included.",
                )
            else:
                note = "A diagram exists; verify its content meets the requirement."
        elif re.search(r"\b(worked examples?|illustrations?)\b", lowered):
            if not examples:
                status, note = "missing", "A worked example was requested, but none was included."
            else:
                note = "An example exists; verify that it meets the requirement."
        result.append({"text": requirement, "status": status, "note": note})
    return result


def overlap_warnings(paper: Mapping[str, Any]) -> list[str]:
    """Flag near-duplicated substantial paragraphs across distinct sections.

    This catches editorial repetition without rewriting a proof or discarding
    caveats. Short technical definitions, summaries and ordinary overlaps are
    intentionally exempt.
    """
    sections = paper.get("sections", [])
    if not isinstance(sections, list):
        return []
    prior: list[tuple[str, set[str], str]] = []
    findings: list[str] = []
    for section in sections:
        if not isinstance(section, dict):
            continue
        heading = str(section.get("heading", "Unnamed section"))
        for paragraph in section.get("paragraphs", []):
            if not isinstance(paragraph, str) or len(paragraph) < 180:
                continue
            tokens = re.findall(r"[a-z0-9]+", paragraph.casefold())
            if len(tokens) < 35:
                continue
            shingles = {" ".join(tokens[i : i + 4]) for i in range(len(tokens) - 3)}
            if not shingles:
                continue
            for older_heading, older_shingles, _ in prior:
                if older_heading == heading:
                    continue
                score = len(shingles & older_shingles) / max(1, len(shingles | older_shingles))
                if score >= 0.82:
                    findings.append(
                        f"Potential repeated argument across '{older_heading}' and '{heading}' "
                        f"(four-word overlap {score:.0%}); review without deleting distinct evidence."
                    )
                    break
            prior.append((heading, shingles, paragraph))
    if len(findings) > 12:
        return [
            *findings[:12],
            f"{len(findings) - 12} more substantial paragraph overlaps require review.",
        ]
    return findings
