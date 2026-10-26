"""Offline contract tests for the consolidated cloud acceptance report."""

from __future__ import annotations

from sigma import cloud_acceptance


def test_new_report_starts_unrun_and_identifies_release() -> None:
    report = cloud_acceptance.new_report(
        origin="https://sigma.example", release_sha="abc123", generated_at="2026-10-25T00:00:00Z"
    )
    assert report["deployed_release_sha"] == "abc123"
    assert all(item["status"] == "NOT RUN" for item in report["checks"])
    assert cloud_acceptance.summarize(report)["summary"]["decision"].startswith("NO-GO")


def test_endpoint_probe_records_only_observed_pass(monkeypatch) -> None:
    monkeypatch.setattr(
        cloud_acceptance,
        "validate_public_endpoint",
        lambda hostname, address: ["DNS", "TLS", "API"],
    )
    report = cloud_acceptance.new_report(origin="https://sigma.example", release_sha="abc")
    cloud_acceptance.run_endpoint_check(report, hostname="sigma.example", expected_ipv4="192.0.2.1")
    check = report["checks"][0]
    assert check["status"] == "PASS"
    assert "DNS; TLS; API" in check["evidence"]


def test_fail_and_blocked_never_become_go() -> None:
    report = cloud_acceptance.new_report(origin="https://sigma.example", release_sha="abc")
    report["checks"][0].update(status="PASS", evidence="probe")
    report["checks"][1].update(status="BLOCKED", evidence="owner window not authorized")
    assert "NO-GO" in cloud_acceptance.summarize(report)["summary"]["decision"]
    report["checks"][1].update(status="PASS", evidence="hosted browser record")
    report["checks"][2].update(status="FAIL", evidence="cross-user read succeeded")
    assert "NO-GO" in cloud_acceptance.summarize(report)["summary"]["decision"]


def test_invalid_status_rejected() -> None:
    report = cloud_acceptance.new_report(origin="https://sigma.example", release_sha="abc")
    report["checks"][0]["status"] = "MAYBE"
    try:
        cloud_acceptance.summarize(report)
    except ValueError as error:
        assert "invalid status" in str(error)
    else:
        raise AssertionError("invalid statuses must not be accepted")


def test_passes_require_evidence_and_exact_release_sha() -> None:
    report = cloud_acceptance.new_report(origin="https://sigma.example", release_sha="not-recorded")
    for check in report["checks"]:
        check.update(status="PASS", evidence="observed hosted artifact")
    assert "release SHA" in cloud_acceptance.summarize(report)["summary"]["decision"]
    report["deployed_release_sha"] = "a" * 40
    report["checks"][0]["evidence_kind"] = "local"
    try:
        cloud_acceptance.summarize(report)
    except ValueError as error:
        assert "requires hosted evidence" in str(error)
    else:
        raise AssertionError("local evidence must not pass a hosted acceptance row")
    report["checks"][0]["evidence_kind"] = "automated_hosted"
    report["checks"][0]["evidence"] = ""
    try:
        cloud_acceptance.summarize(report)
    except ValueError as error:
        assert "requires evidence" in str(error)
    else:
        raise AssertionError("PASS without an evidence reference must be rejected")
