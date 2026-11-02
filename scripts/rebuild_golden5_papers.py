"""Rebuild review papers from their archived structured drafts.

This is a local render and TeX compile. It does not resume research, call an AI
provider, or replace the archived source records.
"""

from __future__ import annotations

import argparse
import gzip
import json
import shutil
import subprocess
import tempfile
from pathlib import Path

from sigma import papers

ROOT = Path(__file__).resolve().parents[1]
ARCHIVE = ROOT / "docs/evaluations/report_quality/golden5"
ADDITIONAL_ARCHIVE = ROOT / "docs/evaluations/report_quality/additional"
VISUAL_OVERRIDES = ARCHIVE / "visual_overrides.json"
READER_GUIDES = ARCHIVE / "reader_guides.json"
WORKED_EXAMPLES = ARCHIVE / "worked_examples.json"
SLUGS = (
    "agent-reliability-v1",
    "sovereign-ai-federation-v2",
    "xenopus-tadpoles-v9",
    "nonconsecutive-subset-sums-modulo-3",
    "warp-drive-design",
    "qubit-non-markovian-v1",
    "operation-narrow-passage-round10",
)
OUTPUT_NAMES = {
    "qubit-non-markovian-v1": "when-does-qubit-decoherence-require-a-non-markovian-model-v1-v1",
    "operation-narrow-passage-round10": "operation-narrow-passage",
}


def rebuild(slug: str, output_dir: Path, tectonic: str) -> None:
    record_path = (
        (ADDITIONAL_ARCHIVE if slug == "operation-narrow-passage-round10" else ARCHIVE)
        / slug
        / "metadata.full.json.gz"
    )
    with gzip.open(record_path, "rt", encoding="utf-8") as stream:
        record = json.load(stream)
    draft = papers.PaperDraft.model_validate(record["draft"])
    # Curated explanatory visuals are stored as structured paper data, not as
    # edits to generated TeX. Their evidence links come from the saved claims.
    visual_data = json.loads(VISUAL_OVERRIDES.read_text(encoding="utf-8"))
    claim_map = {claim.id: claim for claim in draft.claims}
    diagrams = list(draft.diagrams) if slug == "agent-reliability-v1" else []
    for item in visual_data.get(slug, []):
        refs = list(
            dict.fromkeys(
                ref for claim_id in item["claim_ids"] for ref in claim_map[claim_id].evidence_refs
            )
        )
        diagrams.append(papers.PaperDiagram.model_validate({**item, "evidence_refs": refs[:20]}))
    section_data = [section.model_dump() for section in draft.sections]
    example = json.loads(WORKED_EXAMPLES.read_text(encoding="utf-8"))[slug]
    target_section = example["section"]
    for section in section_data:
        if section["heading"] == target_section:
            section["examples"].append(
                {key: value for key, value in example.items() if key != "section"}
            )
            break
    else:
        raise ValueError(f"Worked-example section not found: {target_section}")
    editorial_path = record_path.parent / "editorial_override.json"
    if editorial_path.exists():
        editorial = json.loads(editorial_path.read_text(encoding="utf-8"))
        for edit in [editorial, *editorial.get("additional_sections", [])]:
            for section in section_data:
                if section["heading"] != edit["section"]:
                    continue
                if "paragraphs" in edit:
                    section["paragraphs"] = edit["paragraphs"]
                if "table" in edit:
                    table = edit["table"]
                    refs = list(
                        dict.fromkeys(
                            ref
                            for claim_id in table["claim_ids"]
                            for ref in claim_map[claim_id].evidence_refs
                        )
                    )
                    section["tables"].append({**table, "evidence_refs": refs[:20]})
                    section["claim_ids"] = list(
                        dict.fromkeys([*section["claim_ids"], *table["claim_ids"]])
                    )
                break
            else:
                raise ValueError(f"Editorial section not found: {edit['section']}")
    draft = papers.PaperDraft.model_validate(
        {
            **draft.model_dump(),
            "sections": section_data,
            "diagrams": [diagram.model_dump() for diagram in diagrams],
            "reader_guide": json.loads(READER_GUIDES.read_text(encoding="utf-8"))[slug],
        }
    )
    generation = record["generation"]
    project = next(
        (source["data"] for source in record["snapshot"]["sources"] if source["kind"] == "project"),
        {},
    )
    investigation_type = project.get("investigation_type", "default")
    tex = papers._tex(
        draft,
        list(record["validation_warnings"]),
        record["snapshot_sha256"],
        math_style=investigation_type == "mathematical",
        investigation_type=investigation_type,
        obligation_reconciliation=record.get("obligation_reconciliation", []),
        material_omissions=generation.get("material_evidence_omissions", []),
        include_research_details=True,
        include_claim_details=True,
        include_validation_notes=False,
        include_research_excerpts=False,
        source_reference_map={
            item["source_ref"]: item["label"]
            for item in (
                generation.get("source_reference_map")
                or papers._source_reference_records(record["snapshot"])
            )
        },
        writing_sources=generation.get("writing_sources", []),
    )
    with tempfile.TemporaryDirectory(prefix=f"sigma-{slug}-") as temp:
        work = Path(temp)
        source = work / "paper.tex"
        source.write_text(tex, encoding="utf-8")
        result = subprocess.run(
            [tectonic, "--keep-logs", "--print", "--outdir", str(work), str(source)],
            capture_output=True,
            text=True,
            check=False,
        )
        if result.returncode or not (work / "paper.pdf").is_file():
            raise RuntimeError(
                f"TeX compilation failed for {slug}:\n{result.stdout}\n{result.stderr}"
            )
        output_dir.mkdir(parents=True, exist_ok=True)
        output_name = OUTPUT_NAMES.get(slug, f"{slug}-golden5")
        for suffix in ("tex", "pdf"):
            shutil.copyfile(work / f"paper.{suffix}", output_dir / f"{output_name}.{suffix}")
    print(f"{slug}: {output_dir / (output_name + '.pdf')}")


def main() -> None:
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("slugs", nargs="*", choices=SLUGS, default=SLUGS)
    parser.add_argument("--output-dir", type=Path, default=ROOT / "papers")
    parser.add_argument("--tectonic", default="tectonic")
    args = parser.parse_args()
    for slug in args.slugs:
        rebuild(slug, args.output_dir, args.tectonic)


if __name__ == "__main__":
    main()
