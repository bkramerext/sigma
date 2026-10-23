"""Regression coverage for deterministic, escaped Project Audit reports."""

from __future__ import annotations

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
                "terminal": {"status": "completed", "summary": "Candidate retained for review."},
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
    assert plain_type == "text/plain; charset=utf-8"
    for expected in (
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

    html_report, html_type = render_report(data, "html")
    assert html_type == "text/html; charset=utf-8"
    assert "<script>alert" not in html_report
    assert "&lt;script&gt;alert(&#x27;x&#x27;)&lt;/script&gt;" in html_report
    assert "&lt;pre&gt;" not in html_report

    latex, latex_type = render_report(data, "tex")
    assert latex_type == "application/x-tex; charset=utf-8"
    assert latex.startswith("% !TEX program = xelatex")
    for escaped in (r"\&", r"\_", r"\textbackslash{}", r"\textless{}", r"\textgreater{}"):
        assert escaped in latex
    assert latex.count(r"\end{document}") == 1
    assert r"\write18" not in latex
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
