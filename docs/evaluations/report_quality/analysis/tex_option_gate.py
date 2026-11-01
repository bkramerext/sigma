#!/usr/bin/env python3
"""Offline TeX/options and overflow-context audit; no TeX compilation or provider calls.

Usage: python tex_option_gate.py path/to/papers
Flags identify mismatches and review candidates, not verified visual defects.
"""
from __future__ import annotations

import argparse
import json
from pathlib import Path
import re

EXCERPT = re.compile(r"\\subsection\{Research excerpt \d+\}")
WARNING_LINE = re.compile(r"report\.tex:(\d+):\s*Overfull")


def audit_tex(tex: str, metadata: dict) -> dict:
    lines = tex.splitlines()
    excerpt_count = len(EXCERPT.findall(tex))
    excerpt_appendix = "\\section{Selected source-linked research excerpts}" in tex
    requested = metadata.get("generation", {}).get("include_research_excerpts")
    schema_lines = [i for i, line in enumerate(lines, 1)
                    if "provider\\_input\\_audit" in line or
                    "request\\_body/text/format/schema" in line or
                    "request\\_body/text/format/schema" in line]
    overflow = []
    for warning in metadata.get("generation", {}).get("layout_warnings", []):
        match = WARNING_LINE.search(warning)
        if not match:
            continue
        line_no = int(match.group(1))
        context = lines[line_no - 1] if 1 <= line_no <= len(lines) else ""
        # TeX overfull diagnostics often name the end of a paragraph, not
        # the exact token. Inspect a narrow neighborhood, without asserting
        # that a nearby URL, schema or identifier caused the overflow.
        nearby = "\n".join(lines[max(0, line_no - 3):min(len(lines), line_no + 2)])
        signals = []
        if "https://" in nearby or "http://" in nearby:
            signals.append("nearby_raw_url")
        if "provider\\_input\\_audit" in nearby or ("schema" in nearby and "\\{" in nearby):
            signals.append("nearby_provider_schema_or_serialized_json")
        if re.search(r"[0-9a-f]{35,}", nearby):
            signals.append("nearby_long_hex_identifier")
        overflow.append({"line": line_no, "warning": warning,
                         "line_preview": context[:200], "candidate_signals": signals})
    flags = []
    if requested is False and excerpt_appendix:
        flags.append("research excerpts rendered despite false generation option")
    if schema_lines:
        flags.append("provider plumbing or request schema appears in manuscript")
    return {"requested_excerpts": requested,
            "excerpt_appendix_present": excerpt_appendix,
            "excerpt_subsections": excerpt_count,
            "provider_schema_lines": schema_lines,
            "overfull_line_contexts": overflow,
            "review_flags": flags,
            "scope": "TeX text and metadata only; no visual PDF or scientific validity assertion"}


def main() -> None:
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("directory", type=Path)
    args = parser.parse_args()
    out = {}
    for metadata_path in sorted(args.directory.glob("*.metadata.json")):
        stem = metadata_path.name.removesuffix(".metadata.json")
        tex_path = metadata_path.with_name(stem + ".tex")
        if not tex_path.is_file():
            out[stem] = {"review_flags": ["missing TeX source"]}
            continue
        out[stem] = audit_tex(tex_path.read_text(encoding="utf-8"),
                              json.loads(metadata_path.read_text(encoding="utf-8")))
    print(json.dumps(out, indent=2, ensure_ascii=False))


if __name__ == "__main__":
    main()
