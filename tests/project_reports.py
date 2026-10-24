"""Regression coverage for deterministic, escaped Project Audit reports."""

from __future__ import annotations

import os
from pathlib import Path
from tempfile import TemporaryDirectory

from fastapi.testclient import TestClient

from sigma.api import app, export_project_view
from sigma.project_reports import render_report
from sigma.projects import create_strategy, initialize_project


def fixture() -> dict:
    return {
        "export_version": 2,
        "project": {
            "id": "project-id",
            "title": "Riemann <script>alert('x')</script> & proof",
            "problem": "Can we prove 50%? A & B; x_1 < x_2. \\end{document}\\write18{evil}",
            "investigation_type": "mathematical",
            "active_order": ["strategy-id"],
            "strategies": [
                {
                    "id": "strategy-id",
                    "title": "Independent counterexample search",
                    "approach": "Check boundary cases using c:\\proofs & x_1.",
                    "created_at": "2026-01-01T00:00:00Z",
                    "removed_at": None,
                }
            ],
        },
        "research_sessions": [
            {
                "session_number": 3,
                "status": "ended",
                "outcome": {
                    "assessment": "mixed",
                    "provisional": False,
                    "metrics": {
                        "operational": [
                            {"label": "Model calls", "value": "2 dispatched · 2 completed"}
                        ],
                        "research_quality": [
                            {"label": "Verification", "value": "Convincing, unverified"}
                        ],
                    },
                    "solution_review": {
                        "claim": "Candidate formula",
                        "claim_scope": "conditional",
                        "argument_summary": "Upper bound and attaining construction.",
                        "argument_steps": [
                            {
                                "number": 1,
                                "title": "Insertion recurrence",
                                "argument": "The nth line has at most n-1 crossings and therefore creates at most n regions.",
                                "epistemic_status": "deduction",
                                "basis_artifact_ids": ["artifact-1"],
                                "research_artifact_id": "artifact-1",
                                "review": {
                                    "disposition": "accepted",
                                    "rationale": "The crossing count partitions the line into at most n pieces.",
                                    "basis_artifact_ids": ["artifact-1"],
                                },
                            }
                        ],
                        "assumptions": ["Euclidean lines"],
                        "proof_obligations": ["Verify n=0"],
                        "verification_status": "convincing_unverified",
                        "basis_artifact_ids": ["artifact-1"],
                        "unresolved_objections": [],
                    },
                },
                "strategy_assessments": [
                    {
                        "strategy_id": "strategy-id",
                        "strategy_title": "Independent counterexample search",
                        "assessment": "productive",
                        "rationale": "The linked counterexample attempt clarified the boundary case.",
                        "basis_artifact_ids": ["artifact-1"],
                    }
                ],
                "strategy_title": "Independent counterexample search",
                "started_at": "2026-01-02T00:00:00Z",
                "artifacts": [
                    {
                        "note": "Unverified calculation",
                        "claim": "A < B & C",
                        "method": "Compute f(x_1)",
                        "assumptions": ["A&B", "x > 0"],
                        "evidence_status": "Provisional; not independently checked",
                        "skeptic_response": "The boundary case remains open.",
                        "objections": ["Missing proof"],
                        "coordinator_decision": "continue",
                        "open_obligations": ["Prove convergence"],
                        "next_question": "Can the bound be sharpened?",
                    }
                ],
                "terminal_reason": "budget_exhausted",
            }
        ],
        "agentic_runs": [
            {
                "run_id": "run-1",
                "started_at": "2026-01-03T00:00:00Z",
                "terminal": {
                    "status": "completed",
                    "summary": "Candidate retained for review; $R(n)=1+n(n+1)/2$ and $$R(0)=1$$.",
                },
                "steps": [
                    {
                        "index": 1,
                        "role": "strategy_explore",
                        "status": "completed",
                        "output": {
                            "approach": "Use an explicit recurrence.",
                            "mechanism": "Induction",
                            "evidence_boundary": "Finite checks do not prove the claim.",
                        },
                    }
                ],
                "history": [{"outcome": "present", "summary": "Ready for human review."}],
            }
        ],
    }


def test_unequal_metric_groups() -> None:
    # Exercise each longer group, either empty group, and historical no-metrics.
    # Row text includes the old delimiter to ensure it remains ordinary content.
    operational = [
        {"label": "Calls", "value": "2 completed"},
        {"label": "Last operational row", "value": "<script>ops</script> || input: 20"},
    ]
    quality = [
        {"label": "Verification", "value": "Unverified"},
        {"label": "Last quality row", "value": "Open obligation: x < 2"},
    ]
    for ops, research in (
        (operational, quality[:1]),
        (operational[:1], quality),
        (operational, []),
        ([], quality),
        ([], []),
    ):
        data = fixture()
        data["research_sessions"][0]["outcome"]["metrics"] = {
            "operational": ops,
            "research_quality": research,
        }
        plain, _ = render_report(data, "txt")
        html_report, _ = render_report(data, "html")
        assert isinstance(plain, str) and isinstance(html_report, str)
        for item in ops + research:
            assert f"{item['label']}: {item['value']}" in plain
            assert f"<dt>{item['label']}</dt>" in html_report
        assert ("Operational metrics" in plain) == bool(ops)
        assert ("Research-quality metrics" in plain) == bool(research)
        assert ("Operational metrics</h5>" in html_report) == bool(ops)
        assert ("Research-quality metrics</h5>" in html_report) == bool(research)
        if ops or research:
            header_end = html_report.index(
                "</header>", html_report.index('<article class="report-session">')
            )
            assert header_end < html_report.index("Outcome metrics</h4>")
        if len(ops) == 2:
            assert "&lt;script&gt;ops&lt;/script&gt; || input: 20" in html_report
        if len(research) == 2:
            assert "Open obligation: x &lt; 2" in html_report
        assert "<script>" not in html_report
        assert html_report.count('<dl class="report-outcome-metrics">') == bool(ops) + bool(
            research
        )


def test_report_retains_reviewed_argument_steps() -> None:
    data = fixture()
    data["research_sessions"][0]["outcome"]["solution_review"]["strategy_findings"] = [
        {
            "strategy_title": "Branch A",
            "status": "partial",
            "claim": "A partial bound.",
            "research_artifact_id": "artifact-1",
            "reasoning_steps": [
                {
                    "number": 1,
                    "title": "Partial lemma",
                    "argument": "The finite bound follows under the stated condition.",
                    "epistemic_status": "deduction",
                    "review": {
                        "disposition": "unresolved",
                        "rationale": "The other direction is missing.",
                        "objection": "No attainment argument.",
                    },
                }
            ],
            "objections": ["No attainment argument."],
            "open_obligations": ["Construct an attaining case."],
        },
        {
            "strategy_title": "Branch B",
            "status": "execution_failed",
            "execution_status": "failed",
            "failure_reason": "Provider timed out before a complete cycle.",
            "claim": "No research artifact was saved for this strategy.",
            "research_artifact_id": "",
            "research_artifact_ids": [],
            "reasoning_steps": [],
            "objections": [],
            "open_obligations": ["Provider timed out before a complete cycle."],
        },
    ]
    plain, _ = render_report(data, "txt")
    html_report, _ = render_report(data, "html")
    assert isinstance(plain, str) and isinstance(html_report, str)
    assert "Insertion recurrence" in plain
    assert "at most n pieces" in plain
    assert "Skeptic rationale: The crossing count" in plain
    assert "Insertion recurrence" in html_report
    assert "at most n pieces" in html_report
    assert "Branch A · partial" in plain
    assert "Branch B · execution_failed" in plain
    assert "Strategy execution status: failed" in plain
    assert "Provider timed out before a complete cycle." in plain
    assert "No attainment argument." in plain

    single_failure = fixture()
    single_failure["research_sessions"][0]["outcome"]["solution_review"]["strategy_findings"] = [
        {
            "strategy_title": "Only selected route",
            "status": "execution_failed",
            "execution_status": "failed",
            "failure_reason": "Provider unavailable.",
            "claim": "No research artifact was saved for this strategy.",
            "research_artifact_id": "",
            "research_artifact_ids": [],
            "reasoning_steps": [],
            "objections": [],
            "open_obligations": ["Provider unavailable."],
        }
    ]
    single_report, _ = render_report(single_failure, "txt")
    assert isinstance(single_report, str)
    assert "Only selected route · execution_failed" in single_report
    assert "Provider unavailable." in single_report


def test_context_manifest_is_reported() -> None:
    data = fixture()
    data["research_sessions"][0]["artifacts"][0]["skeptic_output"] = {
        "obligation_reviews": [
            {
                "obligation_id": "obligation-1",
                "status": "addressed",
                "basis_artifact_ids": ["artifact-1"],
                "basis_step_ids": [],
                "rationale": "The linked construction covers this case.",
            }
        ]
    }
    data["research_sessions"][0]["steps"] = [
        {
            "id": "step-1",
            "role": "skeptic",
            "context_manifest": {
                "selected_count": 2,
                "omitted_count": 8,
                "assembled_context_bytes": 12000,
                "sources": [
                    {
                        "source_ids": ["artifact-critical"],
                        "category": "counterexample_or_latest",
                        "reason": "explicitly unresolved obligation or marked counterexample",
                        "status": "selected",
                    },
                    {
                        "source_ids": ["artifact-old"],
                        "category": "history",
                        "reason": "lower priority; original retained in session",
                        "status": "omitted",
                    },
                ],
                "omitted_prior_session_findings": {
                    "count": 3,
                    "source_ids": ["prior-old"],
                    "reason": "bounded index",
                },
            },
        }
    ]
    report, _ = render_report(data, "txt")
    assert isinstance(report, str)
    for expected in (
        "Agent context selection",
        "2 selected, 8 current-session artifacts omitted",
        "artifact-critical",
        "artifact-old",
        "original retained in session",
        "Omitted prior-session findings: 3",
        "Obligation disposition: addressed · obligation-1",
        "model-reported, unverified",
    ):
        assert expected in report


def main() -> None:
    test_unequal_metric_groups()
    test_context_manifest_is_reported()
    data = fixture()
    plain, plain_type = render_report(data, "txt")
    assert isinstance(plain, str)
    assert plain_type == "text/plain; charset=utf-8"
    for expected in (
        "Research type: Mathematics",
        "Research problem: Can we prove 50%? A & B; x_1 < x_2.",
        "Session #3",
        "Execution status: ended",
        "Outcome:",
        "Outcome metrics",
        "Operational metrics",
        "Model calls: 2 dispatched · 2 completed",
        "Research-quality metrics",
        "Verification: Convincing, unverified",
        "Solution claim: Candidate formula",
        "Claim scope: conditional",
        "Verification status: convincing_unverified",
        "Strategy Assessments",
        "Productive: The linked counterexample attempt clarified the boundary case.",
        "Claim: A < B & C",
        "Method: Compute f(x_1)",
        "Assumptions: A&B; x > 0",
        "Evidence status: Provisional; not independently checked",
        "Open obligations: Prove convergence",
        "Run run-1",
        "Finite checks do not prove the claim.",
    ):
        assert expected in plain
    legacy_data = fixture()
    del legacy_data["research_sessions"][0]["outcome"]["solution_review"]["verification_status"]
    legacy_report, _ = render_report(legacy_data, "txt")
    assert isinstance(legacy_report, str)
    assert "Verification status:" not in legacy_report
    assert "Difficulty:" not in plain
    data["project"]["difficulty"] = "easy"
    plain_with_difficulty, _ = render_report(data, "txt")
    assert isinstance(plain_with_difficulty, str)
    assert "Difficulty: Easy" in plain_with_difficulty

    html_report, html_type = render_report(data, "html")
    assert isinstance(html_report, str)
    assert html_type == "text/html; charset=utf-8"
    assert "<script>alert" not in html_report
    assert "&lt;script&gt;alert(&#x27;x&#x27;)&lt;/script&gt;" in html_report
    assert "&lt;pre&gt;" not in html_report
    assert '<dl class="report-outcome-metrics">' in html_report
    assert "report-outcome-metrics-table" not in html_report
    assert "2 dispatched · 2 completed" in html_report
    assert (
        "<h1>Riemann &lt;script&gt;alert(&#x27;x&#x27;)&lt;/script&gt; &amp; proof</h1>"
        in html_report
    )
    assert '<header class="report-header">' in html_report
    assert '<section class="report-section">' in html_report
    assert '<h2 class="report-heading">Research sessions</h2>' in html_report
    assert '<article class="report-session">' in html_report
    assert '<h3 class="report-record-heading">Session #3</h3>' in html_report
    assert '<h4 class="report-subheading">Strategy Assessments</h4>' in html_report
    assert html_report.index("Session #3</h3>") < html_report.index("Strategy Assessments</h4>")
    assert html_report.index("Strategy Assessments</h4>") < html_report.index(
        '<table class="report-assessment-table">'
    )
    assert '<dl class="report-session-meta">' in html_report
    assert (
        '<div class="report-session-fact"><dt>Execution status</dt><dd class="report-session-value report-status-ended">ended</dd></div>'
        in html_report
    )
    assert (
        '<div class="report-session-fact"><dt>Outcome</dt><dd class="report-session-value report-outcome-mixed">mixed</dd></div>'
        in html_report
    )
    assert html_report.index("</dl>") < html_report.index("Solution claim:")
    assert html_report.index('<article class="report-session">') < html_report.index(
        "Strategy Assessments</h4>"
    )
    assert '<table class="report-assessment-table">' in html_report
    assert ".report-assessment-table col:nth-child(3){width:44%}" in html_report
    assert "@media(max-width:640px)" in html_report and "@media print" in html_report
    assert '<math class="report-math"' in html_report and "R(n)=1+n(n+1)/2" in html_report
    assert 'display="block"' in html_report and "R(0)=1" in html_report
    assert "<script>" not in html_report and "<pre>" not in html_report

    latex, latex_type = render_report(data, "tex")
    assert isinstance(latex, str)
    assert latex_type == "application/x-tex; charset=utf-8"
    assert latex.startswith("% Generated by SIGMA")
    assert r"\documentclass[11pt]{article}" in latex
    assert r"\author{SIGMA Research Record}" in latex
    assert (
        r"\begin{quote}\small In the future we plan on using AI to produce a typical academic paper based on the results of the research.\end{quote}"
        in latex
    )
    assert r"\section{Research sessions}" in latex
    assert r"\subsection{Session \#3}" in latex
    assert (
        r"\begin{description}[style=nextline,font=\normalfont\bfseries,leftmargin=0pt,labelsep=0pt]"
        in latex
    )
    assert r"\item[Execution status] ended" in latex
    assert r"\subsubsection*{Strategy assessments}" in latex
    assert r"\begin{longtable}{>{\raggedright\arraybackslash}p{.16\linewidth}" in latex
    assert r"\paragraph{Artifact 1 · Unverified calculation}" in latex
    assert latex.index(r"\subsection{Session \#3}") < latex.index(
        r"\subsubsection*{Strategy assessments}"
    )
    assert r"$R(n)=1+n(n+1)/2$" in latex
    assert r"\[R(0)=1\]" in latex
    for escaped in (r"\&", r"\_", r"\textbackslash{}", r"\textless{}", r"\textgreater{}"):
        assert escaped in latex
    assert latex.count(r"\end{document}") == 1
    assert r"\write18" not in latex
    assert "<script>" not in latex
    try:
        render_report(data, "md")
    except ValueError:
        pass
    else:
        raise AssertionError("unsupported format was accepted")

    empty = fixture()
    empty["research_sessions"] = []
    empty["agentic_runs"] = []
    empty["project"]["strategies"] = []
    empty_report, _ = render_report(empty, "txt")
    assert isinstance(empty_report, str)
    assert "No strategies are recorded." in empty_report
    assert "No research sessions are recorded." in empty_report
    assert "No agentic runs are recorded." in empty_report

    with TemporaryDirectory(prefix="sigma-report-") as temporary:
        path = Path(temporary) / "empty.sigma"
        initialize_project(path, "Empty report", "No saved research yet.")
        create_strategy(path, "Saved sample strategy", "Record a concrete mathematical approach.")
        audit_before = export_project_view(str(path))
        with TestClient(app) as client:
            for output_format, mime in (
                ("txt", "text/plain"),
                ("html", "text/html"),
                ("tex", "application/x-tex"),
            ):
                response = client.get(
                    "/api/projects/export/report",
                    params={"path": str(path), "format": output_format},
                )
                assert response.status_code == 200 and mime in response.headers["content-type"]
                assert response.text
            old_tectonic = os.environ.get("SIGMA_TECTONIC")
            os.environ["SIGMA_TECTONIC"] = "sigma-missing-tectonic-a1771"
            try:
                pdf_response = client.get(
                    "/api/projects/export/report", params={"path": str(path), "format": "pdf"}
                )
                assert pdf_response.status_code == 400
                assert "Install Tectonic" in pdf_response.json()["error"]
            finally:
                if old_tectonic is None:
                    os.environ.pop("SIGMA_TECTONIC", None)
                else:
                    os.environ["SIGMA_TECTONIC"] = old_tectonic
                if output_format == "txt":
                    assert "Saved sample strategy" in response.text
                    assert "Record a concrete mathematical approach." in response.text
            invalid = client.get(
                "/api/projects/export/report", params={"path": str(path), "format": "md"}
            )
            assert invalid.status_code == 400
        assert export_project_view(str(path)) == audit_before
    print("PASS empty and populated reports, lifecycle/outcome distinction, UTF-8 and escaping")
    print("PASS report API formats and unchanged Project Audit export")


if __name__ == "__main__":
    main()
