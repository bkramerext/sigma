"""Offline, deterministic structural audit of SIGMA paper artifacts.

This is NOT a scientific peer reviewer or PDF visual validator. It audits the
files already produced; it never calls a model, provider, network or SIGMA.
Usage:
    python docs/evaluations/report_quality/analysis/manuscript_audit.py \
      docs/evaluations/report_quality/iteration_1/papers
"""

from __future__ import annotations

import argparse
import collections
import hashlib
import json
import re
from pathlib import Path

CLAIM = re.compile(
    r"(?m)^C(\d+)\s*[·:]\s*(established|conjecture|limitation|unresolved|"
    r"hypothesis|proposed|definition|conditional deduction|counterexample)\s*:",
    re.IGNORECASE,
)
POINTER = re.compile(r"\[C0*(\d+)\]")
URL = re.compile(r"https?://[^\s)\]}]+")
PROVENANCE_WARNING = re.compile(
    r"\b(?:C0*\d+)\b.*(?:unverified|incomplete|conjectur|counterexample|contradict)",
    re.IGNORECASE,
)


def digest(path: Path) -> str:
    h = hashlib.sha256()
    with path.open("rb") as f:
        for chunk in iter(lambda: f.read(1024 * 1024), b""):
            h.update(chunk)
    return h.hexdigest()


def audit(meta_path: Path) -> dict:
    metadata = json.loads(meta_path.read_text(encoding="utf-8"))
    prefix = meta_path.name.removesuffix(".metadata.json")
    root = meta_path.parent
    artifact_checks = {}
    problems = []
    for kind in ("txt", "tex", "pdf"):
        path = root / (prefix + "." + kind)
        present = path.is_file()
        item = {"present": present}
        expected = metadata.get("hashes", {}).get(kind, {})
        if present:
            item["bytes"] = path.stat().st_size
            item["sha256"] = digest(path)
            if expected.get("sha256"):
                item["hash_matches_metadata"] = item["sha256"] == expected["sha256"]
                if not item["hash_matches_metadata"]:
                    problems.append(kind + ": SHA-256 mismatch")
            if expected.get("bytes") is not None and item["bytes"] != expected["bytes"]:
                problems.append(kind + ": byte count mismatch")
        else:
            problems.append(kind + ": missing")
        artifact_checks[kind] = item

    text_metrics = None
    if artifact_checks["txt"]["present"]:
        text = (root / (prefix + ".txt")).read_text(encoding="utf-8")
        claims = [
            {"id": int(m.group(1)), "label": m.group(2).lower()} for m in CLAIM.finditer(text)
        ]
        claim_ids = [c["id"] for c in claims]
        refs = [int(m.group(1)) for m in POINTER.finditer(text)]
        referenced_unknown = sorted(set(refs) - set(claim_ids))
        if referenced_unknown:
            problems.append(
                "references to unregistered C-IDs: " + ",".join(map(str, referenced_unknown))
            )
        if len(claim_ids) != len(set(claim_ids)):
            problems.append("duplicate claim IDs")
        paragraphs = [p for p in re.split(r"\n\s*\n", text.strip()) if p.strip()]
        text_metrics = {
            "words_whitespace_split": len(text.split()),
            "blank_line_blocks": len(paragraphs),
            "largest_block_words": max((len(p.split()) for p in paragraphs), default=0),
            "claim_count": len(claims),
            "claim_kinds": dict(collections.Counter(c["label"] for c in claims)),
            "claims": claims,
            "internal_claim_pointers": len(refs),
            "unregistered_claim_pointers": referenced_unknown,
            "external_url_occurrences": len(URL.findall(text)),
            "unique_external_urls": sorted(set(URL.findall(text))),
        }

    generation = metadata.get("generation", {})
    proof = generation.get("proofreading", {})
    source_warnings = metadata.get("validation_warnings", [])
    report = {
        "name": prefix,
        "project_id": metadata.get("project_id"),
        "paper_id": metadata.get("paper_id"),
        "source_count": metadata.get("source_count"),
        "preflight_snapshot_sha256": metadata.get("preflight_snapshot_sha256"),
        "artifacts": artifact_checks,
        "text_structure": text_metrics,
        "evidence_fields_omitted": generation.get("evidence_fields_omitted"),
        "publication_status": generation.get("publication_status"),
        "proofreading_status": proof.get("status"),
        "proofreading_unresolved_diagnostics": proof.get("unresolved_diagnostic_count"),
        "layout_status": generation.get("layout_status"),
        "layout_warnings": generation.get("layout_warnings", []),
        "metadata_claim_provenance_warnings": [
            w for w in source_warnings if PROVENANCE_WARNING.search(w)
        ],
        "objective_integrity_problems": problems,
        "audit_scope": (
            "file presence/hash, text structure, claim IDs, and generator metadata; "
            "not scientific verification, source coverage, PDF appearance or truth"
        ),
    }
    return report


def main() -> int:
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("paper_dir", type=Path)
    parser.add_argument(
        "--strict", action="store_true", help="return nonzero on missing/corrupt paper artifacts"
    )
    args = parser.parse_args()
    paths = sorted(args.paper_dir.glob("*.metadata.json"))
    if not paths:
        parser.error("no *.metadata.json files in paper_dir")
    reports = [audit(path) for path in paths]
    print(json.dumps(reports, indent=2, ensure_ascii=False))
    return int(args.strict and any(r["objective_integrity_problems"] for r in reports))


if __name__ == "__main__":
    raise SystemExit(main())
