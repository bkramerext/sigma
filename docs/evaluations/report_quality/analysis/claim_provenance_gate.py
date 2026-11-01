#!/usr/bin/env python3
"""Offline claim-to-source locator specificity audit for generated SIGMA TeX.

Detects absent or coarse source labels; does not prove the source supports the
claim or that a fine-grained label resolves to an existing saved artifact.
"""
from __future__ import annotations

import argparse
import json
from pathlib import Path
import re

CLAIM = re.compile(r"\\subsection\{(C\d+)\s+--\s+([^}]+)\}([\s\S]*?)(?=\\subsection\{C\d+\s+--|\\section\{Limitations\}|\\section\{Open obligations\}|\Z)")
EVIDENCE = re.compile(r"\\textit\{Evidence: \}\s*([^\n]*)")


def audit(tex: str) -> dict:
    rows = []
    for match in CLAIM.finditer(tex):
        cid, kind, body = match.groups()
        evidence = EVIDENCE.search(body)
        labels = re.findall(r"\[([^\]]+)\]", evidence.group(1)) if evidence else []
        has_fine = any("artifact" in x.casefold() or "step" in x.casefold() for x in labels)
        rows.append({"id": cid, "kind": kind, "labels": labels,
                     "specificity": "artifact_or_step" if has_fine else "coarse_only" if labels else "missing"})
    return {"claim_count": len(rows),
            "coarse_only_claim_ids": [x["id"] for x in rows if x["specificity"] == "coarse_only"],
            "missing_claim_ids": [x["id"] for x in rows if x["specificity"] == "missing"],
            "claims": rows,
            "scope": "locator specificity only, not support validity or external scholarly citation"}


def main() -> None:
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("directory", type=Path)
    args = parser.parse_args()
    result = {p.stem: audit(p.read_text(encoding="utf-8"))
              for p in sorted(args.directory.glob("*.tex"))}
    print(json.dumps(result, indent=2, ensure_ascii=False))


if __name__ == "__main__":
    main()
