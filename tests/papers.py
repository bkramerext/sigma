"""Bounded paper evidence validation, rendering safety and durable version scenarios."""

from __future__ import annotations

import asyncio
import json
from pathlib import Path
from tempfile import TemporaryDirectory
from typing import cast
from unittest.mock import patch

import httpx

from sigma import papers
from sigma.api import app
from sigma.plan_stream import completed
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


def test_incomplete_chatgpt_paper_stream_is_rejected() -> None:
    events = [
        {"type": "response.created", "sequence_number": 0, "response": {"id": "resp-paper"}},
        {"type": "response.output_text.delta", "sequence_number": 1, "delta": "partial JSON"},
    ]
    stream = "".join("data: " + json.dumps(event) + "\n\n" for event in events)

    async def handler(_request):
        return httpx.Response(200, headers={"content-type": "text/event-stream"}, content=stream)

    real_client = httpx.AsyncClient
    with patch(
        "sigma.papers.httpx.AsyncClient",
        side_effect=lambda **kwargs: real_client(transport=httpx.MockTransport(handler), **kwargs),
    ):
        try:
            asyncio.run(
                papers._provider(
                    {"sources": []},
                    {"mode": "chatgpt", "token": "fixture"},
                    {"model": "gpt-6.1-sol", "reasoning_effort": "high"},
                )
            )
        except ProjectError as exc:
            assert "without a valid response.completed" in str(exc)
        else:
            raise AssertionError("Partial provider streams must not produce a paper draft")


def test_api_disconnect_cancels_paper_before_publication(path: Path) -> None:
    async def check() -> None:
        started = asyncio.Event()
        cancelled = asyncio.Event()
        credential = {"identity": "chatgpt:fixture", "mode": "chatgpt", "token": "fixture"}
        config = {
            "available": True,
            "binding": credential["identity"],
            "model": "gpt-6.1-sol",
            "reasoning_effort": "high",
        }

        async def slow_provider(*_args):
            started.set()
            try:
                await asyncio.sleep(20)
            finally:
                cancelled.set()

        queue = asyncio.Queue()
        body = {
            "path": str(path),
            "expected_project_id": inspect_project(path).project.id,
            "expected_binding": credential["identity"],
        }
        await queue.put(
            {"type": "http.request", "body": json.dumps(body).encode(), "more_body": False}
        )
        sent = []

        async def send(message):
            sent.append(message)

        scope = {
            "type": "http",
            "asgi": {"version": "3.0"},
            "http_version": "1.1",
            "method": "POST",
            "scheme": "http",
            "path": "/api/projects/papers",
            "raw_path": b"/api/projects/papers",
            "query_string": b"",
            "root_path": "",
            "headers": [(b"host", b"testserver"), (b"content-type", b"application/json")],
            "server": ("testserver", 80),
            "client": ("127.0.0.1", 1234),
        }
        with (
            patch.object(papers, "auth_context", new=lambda: asyncio.sleep(0, result=credential)),
            patch.object(
                papers, "configuration", new=lambda **_kwargs: asyncio.sleep(0, result=config)
            ),
            patch.object(papers, "_provider", new=slow_provider),
        ):
            serving = asyncio.create_task(app(scope, queue.get, send))
            await asyncio.wait_for(started.wait(), timeout=2)
            await queue.put({"type": "http.disconnect"})
            await asyncio.wait_for(serving, timeout=2)
        assert papers.list_papers(str(path)) == []
        assert cancelled.is_set()
        assert not papers._gate.locked()

    asyncio.run(check())


def main() -> None:
    test_incomplete_chatgpt_paper_stream_is_rejected()
    with TemporaryDirectory() as temporary:
        cancelled_path = Path(temporary) / "cancelled.sigma"
        initialize_project(cancelled_path, "Cancelled paper", "A bounded saved question")
        test_api_disconnect_cancels_paper_before_publication(cancelled_path)

    class StreamResponse:
        def __init__(self, content: bytes):
            self.headers = {"content-type": "text/event-stream"}
            self.content = content

        async def aiter_bytes(self):
            yield self.content

    large_event = (
        b'data: {"type":"response.created","sequence_number":0,"response":{"id":"r"},"padding":"'
        + b"x" * 1_100_000
        + b'"}\n\n'
        + b'data: {"type":"response.completed","sequence_number":1,"response":{"id":"r","status":"completed","output":[]}}\n\n'
    )
    parsed_stream = asyncio.run(
        completed(
            cast(httpx.Response, StreamResponse(large_event)),
            max_stream_bytes=papers.MAX_CHATGPT_STREAM_BYTES,
        )
    )
    assert parsed_stream["status"] == "completed"
    try:
        asyncio.run(
            completed(
                cast(httpx.Response, StreamResponse(large_event)),
                max_stream_bytes=papers.MAX_RESPONSE_BYTES,
                overflow_message="ChatGPT paper response exceeded the 1 MB stream limit. No paper was saved.",
            )
        )
    except ProjectError as exc:
        assert "ChatGPT paper response" in str(exc) and "No paper was saved" in str(exc)
        assert "strategy" not in str(exc)
    else:
        raise AssertionError("Paper stream byte limit must be enforced with paper-specific error")

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
    frozen_obligations = {
        "sources": [
            {
                "id": "artifact:max-regions:proof",
                "data": {"open_obligations": [f"Frozen obligation {index}" for index in range(12)]},
            }
        ]
    }
    reconciliation = papers._reconcile_obligations(
        parsed.model_copy(update={"open_obligations": []}), frozen_obligations
    )
    assert len(reconciliation) == 12
    assert all(
        item["source_refs"] == ["artifact:max-regions:proof:open_obligations"]
        for item in reconciliation
    )
    assert all(
        item["status"] == "Not listed by author; not presumed resolved" for item in reconciliation
    )
    reconciled_tex = papers._tex(
        parsed,
        [],
        "a" * 64,
        obligation_reconciliation=reconciliation,
    )
    assert r"\section{Frozen obligation reconciliation}" in reconciled_tex
    assert "Frozen obligation 11" in reconciled_tex
    listed = papers._reconcile_obligations(
        parsed.model_copy(update={"open_obligations": ["  Frozen   obligation 0 "]}),
        frozen_obligations,
    )
    assert listed[0]["status"] == "Listed as open in paper"
    assert listed[1]["status"] == "Not listed by author; not presumed resolved"
    try:
        papers._validate(draft("artifact:unknown"), package)
    except ProjectError as exc:
        assert "unknown evidence IDs" in str(exc)
    else:
        raise AssertionError("Unknown evidence references must be rejected")
    tex = papers._tex(parsed, warnings, "a" * 64)
    assert r"\frac{n(n+1)}{2}" in tex
    assert r"\textbackslash{}input" not in tex
    notation = papers._latex_prose(r"Let $R(\mathcal{A})$ denote the region count.")
    assert r"$R(\mathcal{A})$" in notation
    assert r"\textbackslash{}mathcal" not in notation
    formula_draft = parsed.model_copy(
        update={
            "claims": [
                parsed.claims[0].model_copy(
                    update={
                        "statement": r"The count is $R(n)=1+\sum_{j=1}^n j²$.",
                        "reasoning": r"The line family lies in $\mathbb{R}^2$.",
                    }
                )
            ]
        }
    )
    formula_tex = papers._tex(formula_draft, warnings, "a" * 64, math_style=True)
    assert r"$R(n)=1+\sum_{j=1}^n j^{2}$" in formula_tex
    assert r"$\mathbb{R}^2$" in formula_tex
    assert r"\textbackslash{}sum" not in formula_tex
    assert r"\textbackslash{}mathbb" not in formula_tex
    unicode_superscript = papers._latex_prose("The saved construction uses j².")
    assert "$j^{2}$" in unicode_superscript
    math_tex = papers._tex(parsed, warnings, "a" * 64, math_style=True)
    assert r"\section{Introduction}" in math_tex
    assert r"\section{Evidence and scope}" in math_tex
    assert r"\section{Verification status and limitations}" in math_tex
    assert r"\section{Conclusion}" in math_tex
    assert math_tex.index(r"\section{Conclusion}") < math_tex.index(
        r"\section*{Claim status and evidence}"
    )
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
