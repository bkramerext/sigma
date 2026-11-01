#!/usr/bin/env python3
"""Offline structural risk audit for generated SIGMA manuscripts.

Flags are review prompts, not a scientific validity judgment. Reads existing
TXT and compact JSON metadata only; makes no provider, network or project calls.

Usage:
    python semantic_gate.py path/to/iteration_1/papers
    python semantic_gate.py path/to/iteration_1/papers --compare path/to/iteration_2/papers
"""
from __future__ import annotations

import argparse
import json
from pathlib import Path
import re

CLAIM = re.compile(r"(?m)^C(?P<id>\d+)\s*[·:]\s*(?P<status>[^:\n]+):\s*(?P<statement>[^\n]*)")
RECORD_PATH = re.compile(
    r"\b(?:investigator_output|skeptic_output|solution_review|events|outcome|"
    r"come/solution_review)(?:/[A-Za-z0-9_-]+){2,}", re.IGNORECASE
)
OPERATIONAL_CLAIM = re.compile(
    r"^(?:title|events/\d+(?:/[A-Za-z0-9_-]+)*|project_change|"
    r"(?:investigator_output|skeptic_output)/(?:reasoning_steps|open_obligations)/\d+|"
    r"outcome/caveats/\d+)\s*:",
    re.IGNORECASE,
)
OMISSION = re.compile(r"(?:omitted|omitting)\s+(\d+)\s+(?:material\s+)?saved\s+(?:research\s+)?field\s+fragment", re.IGNORECASE)


def _section(text: str, name: str, next_name: str | None) -> str:
    marker = f"\n{name}\n"
    if marker not in text:
        return ""
    tail = text.split(marker, 1)[1]
    if next_name and f"\n{next_name}\n" in tail:
        tail = tail.split(f"\n{next_name}\n", 1)[0]
    return tail.strip()


def audit_text(text: str, metadata: dict) -> dict:
    abstract = _section(text, "Abstract", "Problem framing")
    register = _section(text, "Claim register", "Limitations")
    conclusion = _section(text, "Conclusions", None)
    body = text.split("\nClaim register\n", 1)[0]
    claims = [m.groupdict() for m in CLAIM.finditer(register)]
    claim_mentions = {
        c["id"]: len(re.findall(rf"\bC{re.escape(c['id'])}\b", body))
        for c in claims
    }
    warnings = metadata.get("validation_warnings", [])
    omitted_mentions = sorted({int(m.group(1)) for warning in warnings for m in OMISSION.finditer(warning)})
    indexed_omitted = metadata.get("generation", {}).get("evidence_fields_omitted")
    issues = []
    abstract_paths = RECORD_PATH.findall(abstract)
    if abstract_paths:
        issues.append("abstract contains raw saved-record locators")
    operational_claims = [
        {"id": c["id"], "statement": c["statement"]}
        for c in claims if OPERATIONAL_CLAIM.search(c["statement"])
    ]
    if operational_claims:
        issues.append("claim register includes operational metadata or raw record locators")
    if conclusion and len(conclusion.split()) < 40:
        issues.append("conclusion is unusually short; inspect for generic fallback")
    if indexed_omitted is not None and any(n != indexed_omitted for n in omitted_mentions):
        issues.append("inconsistent omission counts in metadata warnings")
    return {
        "abstract_words": len(abstract.split()),
        "abstract_record_paths": abstract_paths,
        "claim_count": len(claims),
        "operational_claims": operational_claims,
        "claim_mentions_in_body": claim_mentions,
        "conclusion_words": len(conclusion.split()),
        "conclusion_preview": conclusion[:240],
        "omitted_index_fragments": indexed_omitted,
        "omission_counts_in_warnings": omitted_mentions,
        "review_flags": issues,
        "scope": "text/metadata structure only; not truth, evidence relevance, or PDF visual quality",
    }


def audit_directory(directory: Path) -> dict:
    result = {}
    for metadata_file in sorted(directory.glob("*.metadata.json")):
        prefix = metadata_file.name.removesuffix(".metadata.json")
        txt_file = directory / f"{prefix}.txt"
        if not txt_file.is_file():
            result[prefix] = {"review_flags": ["missing TXT manuscript"]}
            continue
        result[prefix] = audit_text(
            txt_file.read_text(encoding="utf-8"),
            json.loads(metadata_file.read_text(encoding="utf-8")),
        )
    return result


def main() -> None:
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("directory", type=Path)
    parser.add_argument("--compare", type=Path, default=None)
    args = parser.parse_args()
    result = {"baseline": audit_directory(args.directory)}
    if args.compare:
        result["candidate"] = audit_directory(args.compare)
    print(json.dumps(result, indent=2, ensure_ascii=False))


if __name__ == "__main__":
    main()
