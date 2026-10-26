"""Consolidated SIGMA Cloud acceptance evidence report generator.

The automated portion is deliberately read-only. Interactive, owner-authorized,
and operational checks stay NOT RUN until a reviewer records observed evidence.
"""

from __future__ import annotations

import argparse
import json
import re
import urllib.error
from datetime import UTC, datetime
from pathlib import Path

from sigma.public_endpoint import validate_public_endpoint

CHECKS: tuple[tuple[str, str, str], ...] = (
    (
        "https_redirect_tls_api",
        "Public HTTPS, certificate, redirects, API routing",
        "automated_hosted",
    ),
    (
        "oauth_signin_authorization",
        "Google OAuth sign-in and authorization",
        "hosted_browser_owner",
    ),
    ("workspace_isolation", "Two-account workspace isolation", "hosted_browser_owner"),
    ("project_persistence", "Project creation and persistence", "hosted_browser"),
    (
        "provider_research",
        "Research session using real provider inference",
        "hosted_paid_authorized",
    ),
    ("python_sage_isolation", "Python/Sage sandbox execution and isolation", "hosted_owner"),
    ("outcomes_reports_exports", "Outcomes, reports, TeX and PDF exports", "hosted_browser"),
    ("restart_persistence", "Application restart and state persistence", "hosted_operator"),
    ("backup_restore_rollback", "Backup, restore and rollback evidence", "hosted_operator"),
    ("monitoring_recovery", "Monitoring and recovery behavior", "hosted_operator"),
)
VALID = {"PASS", "FAIL", "BLOCKED", "NOT RUN"}
SHA_RE = re.compile(r"^[0-9a-fA-F]{40}$")


def new_report(*, origin: str, release_sha: str, generated_at: str | None = None) -> dict:
    """Create a report that does not imply unobserved evidence passed."""
    return {
        "schema_version": 1,
        "generated_at": generated_at or datetime.now(UTC).isoformat(),
        "origin": origin,
        "deployed_release_sha": release_sha or None,
        "evidence_boundary": "Hosted rows require evidence from the deployed release. Local and mocked evidence do not satisfy hosted acceptance.",
        "checks": [
            {
                "id": identifier,
                "area": label,
                "status": "NOT RUN",
                "evidence_kind": kind,
                "evidence": "",
            }
            for identifier, label, kind in CHECKS
        ],
        "summary": {
            "PASS": 0,
            "FAIL": 0,
            "BLOCKED": 0,
            "NOT RUN": len(CHECKS),
            "decision": "NO-GO / INCOMPLETE",
        },
    }


def summarize(report: dict) -> dict:
    """Validate statuses and recompute conservative overall decision."""
    counts = {status: 0 for status in VALID}
    for check in report["checks"]:
        if check.get("status") not in VALID:
            raise ValueError(f"invalid status for {check.get('id', 'unknown')}")
        if (
            check["status"] in {"PASS", "FAIL", "BLOCKED"}
            and not str(check.get("evidence", "")).strip()
        ):
            raise ValueError(
                f"{check['status']} requires evidence for {check.get('id', 'unknown')}"
            )
        if check["status"] == "PASS" and not (
            str(check.get("evidence_kind", "")).startswith("hosted")
            or str(check.get("evidence_kind", "")).endswith("_hosted")
        ):
            raise ValueError(f"PASS requires hosted evidence for {check.get('id', 'unknown')}")
        counts[check["status"]] += 1
    decision = "GO CANDIDATE — coordinator and owner review required"
    if counts["FAIL"]:
        decision = "NO-GO — failed acceptance evidence"
    elif counts["BLOCKED"] or counts["NOT RUN"]:
        decision = "NO-GO / INCOMPLETE — blocked or unrun acceptance evidence"
    elif not SHA_RE.fullmatch(str(report.get("deployed_release_sha") or "")):
        decision = "NO-GO / INCOMPLETE — exact deployed release SHA is missing or invalid"
    report["summary"] = {**counts, "decision": decision}
    return report


def run_endpoint_check(report: dict, *, hostname: str, expected_ipv4: str) -> None:
    """Run existing read-only DNS/TLS/routing probe and record its outcome."""
    check = next(item for item in report["checks"] if item["id"] == "https_redirect_tls_api")
    try:
        components = validate_public_endpoint(hostname, expected_ipv4)
    except (OSError, TimeoutError, ValueError, urllib.error.URLError) as error:
        check.update(
            status="FAIL",
            evidence=f"Read-only public endpoint probe failed: {type(error).__name__}: {error}",
        )
    else:
        check.update(
            status="PASS", evidence="Read-only hosted probe passed: " + "; ".join(components)
        )


def main(argv: list[str] | None = None) -> int:
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("--origin", help="canonical public HTTPS origin")
    parser.add_argument("--release-sha", help="deployed release SHA from owner/release record")
    parser.add_argument(
        "--expected-ip", help="owner-verified reserved IPv4; enables live read-only endpoint probe"
    )
    parser.add_argument(
        "--finalize", type=Path, help="recompute summary for a completed/edited evidence JSON"
    )
    parser.add_argument("--output", type=Path, required=True, help="JSON evidence report path")
    args = parser.parse_args(argv)
    if args.finalize:
        if args.expected_ip:
            parser.error("--expected-ip is only valid while creating a report, not finalizing it")
        try:
            report = json.loads(args.finalize.read_text(encoding="utf-8"))
            known = {identifier for identifier, _, _ in CHECKS}
            actual = {item.get("id") for item in report.get("checks", [])}
            if actual != known or len(report.get("checks", [])) != len(CHECKS):
                raise ValueError("check IDs do not match this acceptance schema")
            summarize(report)
        except (OSError, json.JSONDecodeError, ValueError, AttributeError) as error:
            parser.error(f"cannot finalize evidence report: {error}")
    else:
        if not args.origin or not args.release_sha:
            parser.error("--origin and --release-sha are required unless --finalize is used")
        if not args.origin.startswith("https://") or args.origin.endswith("/"):
            parser.error("--origin must be canonical HTTPS origin without trailing slash")
        report = new_report(origin=args.origin, release_sha=args.release_sha)
    if args.expected_ip:
        hostname = args.origin.removeprefix("https://")
        if "/" in hostname or ":" in hostname:
            parser.error("--origin must contain only a hostname")
        run_endpoint_check(report, hostname=hostname, expected_ipv4=args.expected_ip)
    summarize(report)
    args.output.parent.mkdir(parents=True, exist_ok=True)
    args.output.write_text(json.dumps(report, indent=2) + "\n", encoding="utf-8")
    print(json.dumps(report["summary"], indent=2))
    return 0 if report["summary"]["decision"].startswith("GO CANDIDATE") else 1


if __name__ == "__main__":
    raise SystemExit(main())
