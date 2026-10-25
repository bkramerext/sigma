"""Offline adversarial checks: saved tool status is not measured evidence."""

from copy import deepcopy

from sigma.project_reports import render_report
from sigma.research_epistemics import execution_provenance


def main() -> None:
    data = {
        "project": {"title": "Offline integrity", "problem": "Evidence?", "strategies": []},
        "research_sessions": [
            {
                "session_number": 1,
                "status": "ended",
                "strategy_title": "Bounded",
                "outcome": {"conclusion": "MODEL CLAIM NOT INDEPENDENTLY VALIDATED"},
                "artifacts": [
                    {
                        "id": "finding",
                        "investigator_output": {
                            "python_execution": {
                                "id": "reported-only",
                                "runtime": "python",
                                "status": "completed",
                            }
                        },
                    }
                ],
                "steps": [],
            }
        ],
        "agentic_runs": [],
    }
    session = data["research_sessions"][0]
    original = deepcopy(data)
    source = execution_provenance(session)
    assert source["completed_count"] == 1
    assert source["completed_without_recorded_io_count"] == 1
    for fmt in ("txt", "html", "tex"):
        report, _ = render_report(data, fmt)
        assert isinstance(report, str)
        warning = "completed-status execution record(s) lack saved source or output"
        assert warning in report
        assert report.index(warning) < report.index("MODEL CLAIM NOT INDEPENDENTLY VALIDATED")
    assert data == original
    session["steps"] = [
        {
            "id": "dispute",
            "output": {"python_execution": {"id": "reported-only", "status": "failed"}},
        }
    ]
    conflicted = execution_provenance(session)
    assert conflicted["completed_count"] == 0
    assert conflicted["completed_without_recorded_io_count"] == 0
    assert set(conflicted["records"][0]["statuses"]) == {"completed", "failed"}
    for fmt in ("txt", "html", "tex"):
        report, _ = render_report(data, fmt)
        assert isinstance(report, str)
        assert "status completed / failed" in report
    execution = session["artifacts"][0]["investigator_output"]["python_execution"]
    session["steps"] = []
    execution["source"] = "print(42)"
    execution["stdout"] = "42"
    assert execution_provenance(session)["completed_without_recorded_io_count"] == 0
    print("PASS adversarial report status/provenance across TXT HTML TeX")


if __name__ == "__main__":
    main()
