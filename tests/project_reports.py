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
                    "solution_review": {
                        "claim": "Candidate formula",
                        "argument_summary": "Upper bound and attaining construction.",
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


def main() -> None:
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
        "Solution claim: Candidate formula",
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
    assert "Verification status:" not in legacy_report

    html_report, html_type = render_report(data, "html")
    assert isinstance(html_report, str)
    assert html_type == "text/html; charset=utf-8"
    assert "<script>alert" not in html_report
    assert "&lt;script&gt;alert(&#x27;x&#x27;)&lt;/script&gt;" in html_report
    assert "&lt;pre&gt;" not in html_report
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
