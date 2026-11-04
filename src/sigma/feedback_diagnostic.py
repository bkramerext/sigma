"""Temporary local-only feedback delivery diagnostics (no browser or production changes).

Uses the same feedback notification and mail transport as the web endpoint.
It does not persist a feedback submission or assume access to a browser session.
"""

from __future__ import annotations

import os
import sys
import time
from pathlib import Path
from unittest.mock import patch
from uuid import uuid4

from sigma.local_config import load_local_config


def _execute(message: str) -> int:
    from sigma import cloud_auth

    configured_email = os.environ.get("SIGMA_CLOUD_ADMIN_CONTACT_EMAIL", "").strip()
    if not configured_email:
        print("ERROR: SIGMA_CLOUD_ADMIN_CONTACT_EMAIL is missing.", file=sys.stderr)
        print("The CLI needs the address configured for local --signin.", file=sys.stderr)
        return 2
    try:
        contact_email = cloud_auth._normalize_email(configured_email)
    except ValueError:
        print("ERROR: The local Google sign-in contact email is invalid.", file=sys.stderr)
        return 2

    gmail_file = cloud_auth.email_env("GMAIL_TOKEN_FILE")
    print("SIGMA feedback mail diagnostic (local CLI)")
    print("Contact source: SIGMA_CLOUD_ADMIN_CONTACT_EMAIL (local --signin configuration)")
    print(f"Contact: {contact_email}")
    print("Browser identity: not available to CLI; no browser session is asserted.")
    print("Submission: mail-path diagnostic only (no feedback database record).")
    if gmail_file:
        print("Transport: Gmail API")
        print("Gmail OAuth token file configured: yes")
        print(f"Gmail OAuth token file present: {'yes' if Path(gmail_file).is_file() else 'no'}")
        print(
            f"Gmail sender configured: {'yes' if bool(cloud_auth.email_env('GMAIL_SENDER')) else 'no'}"
        )
    else:
        host = cloud_auth.email_env("SMTP_HOST", "smtp.gmail.com")
        port = cloud_auth.email_env("SMTP_PORT", "587")
        print("Transport: SMTP")
        print(f"SMTP host: {host}")
        print(f"SMTP port: {port}")
        print(
            f"SMTP username configured: {'yes' if bool(cloud_auth.email_env('SMTP_USERNAME')) else 'no'}"
        )
        try:
            print(
                f"SMTP password configured: {'yes' if bool(cloud_auth.email_secret('SMTP_PASSWORD')) else 'no'}"
            )
        except (OSError, RuntimeError, ValueError):
            print("SMTP password configuration: invalid or unreadable")

    try:
        cloud_auth._deliver_feedback(
            uuid4().hex,
            message,
            int(time.time()),
            account_email=contact_email,
            contact_email=contact_email,
            diagnostic_recipients=[contact_email],
        )
    except cloud_auth.SMTPDeliveryError as exc:
        print(
            f"RESULT: FAILED (SMTP state: {exc.state}; accepted recipients: {exc.accepted_count}).",
            file=sys.stderr,
        )
        if exc.state != "failed":
            print("Delivery may have occurred; inspect the inbox before retrying.", file=sys.stderr)
        return 1
    except (OSError, ValueError, RuntimeError) as exc:
        # Do not disclose raw provider errors, tokens, or SMTP credentials.
        print("RESULT: FAILED (mail transport did not confirm delivery).", file=sys.stderr)
        print(f"Diagnostic category: {type(exc).__name__}", file=sys.stderr)
        print("Check the selected transport configuration; no automatic retry.", file=sys.stderr)
        return 1
    print("RESULT: ACCEPTED by mail provider. Check the recipient inbox.")
    return 0


def run(message: str, *, transport: str = "configured") -> int:
    """Exercise the same feedback mail path without a browser or persistence."""
    try:
        load_local_config()
    except RuntimeError as exc:
        print(f"ERROR: {exc}", file=sys.stderr)
        return 2
    message = message.strip()
    if not 10 <= len(message) <= 4000 or any(
        ord(char) < 32 and char not in "\n\r\t" for char in message
    ):
        print("ERROR: Feedback must be 10 to 4,000 valid characters.", file=sys.stderr)
        return 2
    if transport == "configured":
        return _execute(message)
    if transport == "smtp":
        # Only this process is altered; no persisted settings or secrets change.
        with patch.dict(
            os.environ,
            {
                "SIGMA_GMAIL_TOKEN_FILE": "",
                "SIGMA_EMAIL_GMAIL_TOKEN_FILE": "",
                "SIGMA_INVITATION_GMAIL_TOKEN_FILE": "",
            },
        ):
            print("Override: using SMTP for this invocation only.")
            return _execute(message)
    print("ERROR: Unsupported transport.", file=sys.stderr)
    return 2
