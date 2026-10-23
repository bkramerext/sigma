"""Bounded paper evidence validation, rendering safety and durable version scenarios."""

from __future__ import annotations

import asyncio
from pathlib import Path
from tempfile import TemporaryDirectory
from unittest.mock import patch

from sigma import papers
from sigma.projects import ProjectError, initialize_project, inspect_project


def draft(ref: str = "project:pid") -> papers.PaperDraft:
    return papers.PaperDraft.model_validate(
        {
            "title": "An evidence-bound exploratory note",
            "abstract": "This paper describes an exploratory record and its limitations. No formal result is asserted beyond the saved evidence.",
            "abstract_claim_ids": ["C1"],
            "problem_framing": ["The question is bounded by the saved project objective."],
            "problem_framing_claim_ids": ["C1"],
            "methods": ["We reviewed the saved sessions and their durable artifacts."],
            "methods_claim_ids": ["C1"],
            "claims": [
                {
                    "id": "C1",
                    "statement": "The saved project contains a research objective.",
                    "status": "established",
                    "evidence_refs": [ref],
                    "reasoning": "The objective is explicitly present in the project snapshot.",
                }
            ],
            "sections": [
                {
                    "heading": "Evidence reviewed",
                    "paragraphs": ["The complete snapshot was retained."],
                    "claim_ids": ["C1"],
                },
                {
                    "heading": "Interpretation",
                    "paragraphs": [r"The formula is $R(n)=1+\frac{n(n+1)}{2}$."],
                    "claim_ids": ["C1"],
                },
            ],
            "limitations": ["This paper does not establish a formal proof."],
            "open_obligations": ["A human should review the argument."],
            "conclusions": ["Only claims tied to the recorded snapshot are presented."],
            "conclusion_claim_ids": ["C1"],
            "validation_warnings": ["No external references were supplied."],
        }
    )


def main() -> None:
    evidence_export = {
        "project": {
            "id": "pid",
            "title": "A project",
            "strategies": [{"id": "strat-1", "approach": "A saved strategy."}],
        },
        "research_sessions": [
            {
                "id": "session-1",
                "artifacts": [{"id": "artifact-1", "claim": "A saved finding."}],
            }
        ],
        "agentic_runs": [
            {
                "run_id": "run-1",
                "steps": [{"step_id": "step-1", "output": "A saved step."}],
            }
        ],
    }
    with patch("sigma.api.export_project_view", return_value=evidence_export):
        normalized, fingerprint = papers._snapshot("unused")
    source_map = {source["id"]: source for source in normalized["sources"]}
    assert source_map["project:pid"]["data"] == {"id": "pid", "title": "A project"}
    assert source_map["strategy:strat-1"]["data"] == evidence_export["project"]["strategies"][0]
    assert source_map["session:session-1"]["data"] == {"id": "session-1"}
    assert (
        source_map["artifact:session-1:artifact-1"]["data"]
        == evidence_export["research_sessions"][0]["artifacts"][0]
    )
    assert source_map["run:run-1"]["data"] == {"run_id": "run-1"}
    assert source_map["step:run-1:step-1"]["data"] == evidence_export["agentic_runs"][0]["steps"][0]
    assert normalized["schema"] == "sigma-paper-evidence-v2" and len(fingerprint) == 64
    large_export = {
        "project": {"id": "pid", "problem": "x" * 81_900},
        "research_sessions": [],
        "agentic_runs": [],
    }
    with patch("sigma.api.export_project_view", return_value=large_export):
        large_snapshot, _ = papers._snapshot("unused")
    assert len(papers._json(large_snapshot)) > 65_000
    assert len(papers._json(large_snapshot)) <= papers.MAX_CONTEXT_BYTES
    with (
        patch("sigma.api.export_project_view", return_value=evidence_export),
        patch.object(papers, "MAX_CONTEXT_BYTES", 10),
    ):
        try:
            papers._snapshot("unused")
        except ProjectError as exc:
            assert "bytes" in str(exc) and "No evidence was omitted" in str(exc)
        else:
            raise AssertionError("Oversized complete evidence snapshots must be rejected")

    package = {"sources": [{"id": "project:pid", "data": {"problem": "A question"}}]}
    parsed = draft()
    warnings = papers._validate(parsed, package)
    assert any("not independent formal verification" in item for item in warnings)
    adversarial = parsed.model_copy(
        update={
            "claims": [
                parsed.claims[0].model_copy(
                    update={"status": "established", "evidence_refs": ["artifact:s1:a1"]}
                )
            ],
            "sections": [
                parsed.sections[0].model_copy(
                    update={"paragraphs": ["Prior work (Smith et al., 2024) confirms the result."]}
                ),
                parsed.sections[1],
            ],
            "open_obligations": [],
        }
    )
    adversarial_warnings = papers._validate(
        adversarial,
        {
            "sources": [
                {
                    "id": "artifact:s1:a1",
                    "data": {
                        "evidence_status": "incomplete, unverified",
                        "claim": "A counterexample contradicts the proposed result.",
                        "open_obligations": ["Resolve the counterexample and prove the bound."],
                    },
                }
            ]
        },
    )
    assert any("labeled established" in item for item in adversarial_warnings)
    assert any("counterexample or contradiction" in item for item in adversarial_warnings)
    assert any("Citation-like external references" in item for item in adversarial_warnings)
    assert any("open proof/research obligation" in item for item in adversarial_warnings)
    try:
        papers._validate(draft("artifact:unknown"), package)
    except ProjectError as exc:
        assert "unknown evidence IDs" in str(exc)
    else:
        raise AssertionError("Unknown evidence references must be rejected")
    tex = papers._tex(parsed, warnings, "a" * 64)
    assert r"\frac{n(n+1)}{2}" in tex
    assert r"\textbackslash{}input" not in tex
    injected_section = parsed.sections[0].model_copy(
        update={"paragraphs": [r"Run \input{host-file} now."]}
    )
    injected = parsed.model_copy(update={"sections": [injected_section, *parsed.sections[1:]]})
    injected_tex = papers._tex(injected, warnings, "a" * 64)
    assert r"\textbackslash{}input" in injected_tex
    assert "host-file" in injected_tex
    assert r"\section{Open obligations}" in tex

    with TemporaryDirectory() as temporary:
        path = Path(temporary) / "fixture.sigma"
        initialize_project(path, "Fixture", "Investigate the saved question")
        credential = {"identity": "chatgpt:fixture", "mode": "chatgpt", "token": "fixture"}
        config = {
            "available": True,
            "binding": credential["identity"],
            "model": "gpt-6.1-sol",
            "reasoning_effort": "high",
        }

        async def fake_provider(context, *_args):
            project_source = next(
                item["id"] for item in context["sources"] if item["kind"] == "project"
            )
            return draft(project_source), config["model"]

        with (
            patch.object(papers, "auth_context", new=lambda: asyncio.sleep(0, result=credential)),
            patch.object(
                papers, "configuration", new=lambda **kwargs: asyncio.sleep(0, result=config)
            ),
            patch.object(papers, "_provider", new=fake_provider),
            patch.object(papers, "_compile_pdf", new=lambda _: b"%PDF-fixture"),
        ):
            first = asyncio.run(papers.generate(str(path), credential["identity"]))
            second = asyncio.run(papers.generate(str(path), credential["identity"]))
        assert first["paper_id"] != second["paper_id"]
        assert len(papers.list_papers(str(path))) == 2
        record = papers.get_paper(str(path), first["paper_id"])
        assert record["snapshot_sha256"] == first["snapshot_sha256"]
        assert record["generation"]["call_limit"] == 1
        assert papers.get_pdf(str(path), first["paper_id"]).startswith(b"%PDF-")
        assert record["snapshot"]["sources"][0]["id"] == "project:" + record["project_id"]
        assert len(inspect_project(path).project.events) == 1

        exploratory_path = Path(temporary) / "unresolved.sigma"
        initialize_project(
            exploratory_path,
            "Unresolved question",
            "Determine whether this open question is tractable",
        )

        async def exploratory_provider(context, *_args):
            project_source = next(
                item["id"] for item in context["sources"] if item["kind"] == "project"
            )
            return papers.PaperDraft.model_validate(
                {
                    "title": "An Exploratory Record with Open Questions",
                    "abstract": "The saved project defines an open question but contains no research session or findings. This paper therefore records an exploratory state and identifies the evidence needed for future work, without forcing the material into a theorem-proof narrative.",
                    "abstract_claim_ids": ["C1"],
                    "problem_framing": [
                        "The project objective is recorded without a saved result."
                    ],
                    "problem_framing_claim_ids": ["C1"],
                    "methods": [
                        "We inspected the complete project snapshot; no research session or experiment was recorded."
                    ],
                    "methods_claim_ids": ["C1"],
                    "claims": [
                        {
                            "id": "C1",
                            "statement": "The saved project contains the stated research objective.",
                            "status": "established",
                            "evidence_refs": [project_source],
                            "reasoning": "This is directly present in the snapshot.",
                        }
                    ],
                    "sections": [
                        {
                            "heading": "Available evidence",
                            "paragraphs": [
                                "There are no saved research findings in this snapshot."
                            ],
                            "claim_ids": ["C1"],
                        },
                        {
                            "heading": "Research remains open",
                            "paragraphs": ["No substantive conclusion is supported yet."],
                            "claim_ids": [],
                        },
                    ],
                    "limitations": ["No research session or experimental result is available."],
                    "open_obligations": [
                        "Conduct and persist an investigation before drawing a substantive conclusion."
                    ],
                    "conclusions": ["This is an exploratory note, not a theorem-proof paper."],
                    "conclusion_claim_ids": ["C1"],
                    "validation_warnings": [],
                }
            ), config["model"]

        with (
            patch.object(papers, "auth_context", new=lambda: asyncio.sleep(0, result=credential)),
            patch.object(
                papers, "configuration", new=lambda **kwargs: asyncio.sleep(0, result=config)
            ),
            patch.object(papers, "_provider", new=exploratory_provider),
            patch.object(papers, "_compile_pdf", new=lambda _: b"%PDF-fixture"),
        ):
            exploratory = asyncio.run(papers.generate(str(exploratory_path)))
        exploratory_record = papers.get_paper(str(exploratory_path), exploratory["paper_id"])
        assert exploratory_record["draft"]["title"] == "An Exploratory Record with Open Questions"
        assert not any(
            item["kind"] == "session" for item in exploratory_record["snapshot"]["sources"]
        )
    print("Paper snapshots, citation validation, version retention and bounded rendering passed.")


if __name__ == "__main__":
    main()
