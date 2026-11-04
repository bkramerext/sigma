"""Temporary local feedback delivery diagnostics, with no browser or production changes.

Uses the same feedback notification and transport as the web endpoint, without
persisting a feedback record or claiming a browser-authenticated identity.
"""

from __future__ import annotations

import json
import os
import smtplib
import socket
import ssl
import stat
import sys
import time
from pathlib import Path
from unittest.mock import patch
from uuid import uuid4

from sigma.local_config import load_local_config
from sigma.projects import ROOT


def _active_setting(*names: str) -> tuple[str, str]:
    """Honor the same first-present env-variable precedence as mail delivery."""
    for name in names:
        if name in os.environ:
            return name, os.environ[name].strip()
    return names[0], ""


def _password_setting() -> tuple[str, str | None]:
    """Resolve the active SMTP secret setting without displaying its value."""
    for prefix in ("SIGMA_EMAIL_", "SIGMA_INVITATION_"):
        value = prefix + "SMTP_PASSWORD"
        filename = value + "_FILE"
        if value in os.environ or filename in os.environ:
            return value, filename if filename in os.environ else None
    return "SIGMA_EMAIL_SMTP_PASSWORD", None


def _config_help() -> None:
    example = Path.home() / ".config" / "sigma" / "smtp-password"
    print()
    print("Expected local SMTP settings (place in checkout .env or export them):")
    print(f"  Checkout .env: {ROOT / '.env'}")
    print("  SIGMA_EMAIL_SMTP_USERNAME=<Gmail account used to send mail>")
    print(f"  SIGMA_EMAIL_SMTP_PASSWORD_FILE={example}")
    print("  SIGMA_CLOUD_ADMIN_CONTACT_EMAIL=<local Google sign-in email (test recipient)>")
    print("  SIGMA_EMAIL_SMTP_HOST=smtp.gmail.com    # optional; default shown")
    print("  SIGMA_EMAIL_SMTP_PORT=587              # optional; STARTTLS")
    print("  Password file: Gmail app password, NOT the normal account password.")
    print("  Password file must use an absolute path, be private (chmod 600),")
    print("  and stay outside Git. In .env, ~ and $HOME are not expanded.")
    print("  Existing SIGMA_INVITATION_SMTP_* names also work.")
    print("  Exported shell variables override the checkout .env, even when empty.")
    if example.is_file():
        mode = stat.S_IMODE(example.stat().st_mode)
        print(f"  Existing candidate password file: {example} (permissions {mode:03o})")
    else:
        print(f"  Candidate password file not found at: {example}")


def _smtp_ready() -> bool:
    """Check settings without exposing SMTP credentials or contacting Gmail."""
    from sigma import cloud_auth
    from sigma.config_secrets import SecretConfigurationError

    ready = True
    host_key, host = _active_setting("SIGMA_EMAIL_SMTP_HOST", "SIGMA_INVITATION_SMTP_HOST")
    port_key, port_value = _active_setting("SIGMA_EMAIL_SMTP_PORT", "SIGMA_INVITATION_SMTP_PORT")
    host = host if host_key in os.environ else "smtp.gmail.com"
    port_value = port_value if port_key in os.environ else "587"
    print(f"[{'OK' if host else 'MISSING'}] {host_key}: {host or '(empty)'} (SMTP server)")
    if not host:
        ready = False
    try:
        port = int(port_value)
        if not 1 <= port <= 65535:
            raise ValueError
        print(f"[OK] {port_key}: {port} (STARTTLS expected on port 587 for Gmail)")
    except ValueError:
        print(f"[INVALID] {port_key}: expected port 587 (integer between 1 and 65535)")
        ready = False

    username_key, username = _active_setting(
        "SIGMA_EMAIL_SMTP_USERNAME", "SIGMA_INVITATION_SMTP_USERNAME"
    )
    if not username:
        print(f"[MISSING] {username_key}: Gmail address used for authenticated sending")
        ready = False
    else:
        try:
            cloud_auth._normalize_email(username)
        except ValueError:
            print(f"[INVALID] {username_key}: expected a valid email address")
            ready = False
        else:
            print(f"[OK] {username_key}: {username} (authenticated sender, not recipient)")

    secret_key, file_key = _password_setting()
    if file_key:
        raw_path = os.environ[file_key].strip()
        if not raw_path:
            print(f"[MISSING] {file_key}: absolute path to a Gmail app-password file")
            ready = False
        elif not Path(raw_path).is_absolute():
            print(f"[INVALID] {file_key}: use an absolute path; ~ and $HOME do not expand")
            ready = False
        else:
            path = Path(raw_path)
            if not path.is_file():
                print(f"[MISSING] {file_key}: file not found at {path}")
                ready = False
            else:
                print(f"[OK] {file_key}: {path} (password contents hidden)")
                mode = stat.S_IMODE(path.stat().st_mode)
                if mode & 0o077:
                    print(f"[WARNING] Password file permissions {mode:03o}; use chmod 600 {path}")
    elif not os.environ.get(secret_key, "").strip():
        print(
            "[MISSING] SIGMA_EMAIL_SMTP_PASSWORD_FILE: absolute path to a Gmail app-password file"
        )
        print("          (legacy SIGMA_INVITATION_SMTP_PASSWORD[_FILE] is also supported)")
        ready = False
    else:
        print(f"[OK] {secret_key}: set (contents hidden; a private _FILE is preferred)")

    try:
        if not cloud_auth.email_secret("SMTP_PASSWORD"):
            print("[MISSING] SMTP password: empty or not configured")
            ready = False
    except SecretConfigurationError:
        print("[INVALID] SMTP password: conflicting, unreadable, or unsafe file configuration")
        ready = False

    if not ready:
        _config_help()
    return ready


def _gmail_ready() -> bool:
    from sigma import cloud_auth

    ready = True
    token_key, token_path = _active_setting(
        "SIGMA_GMAIL_TOKEN_FILE",
        "SIGMA_EMAIL_GMAIL_TOKEN_FILE",
        "SIGMA_INVITATION_GMAIL_TOKEN_FILE",
    )
    if not token_path or not Path(token_path).is_file():
        print(f"[MISSING] {token_key}: existing absolute path to a Gmail OAuth token JSON file")
        ready = False
    else:
        print(f"[OK] {token_key}: file exists (token contents hidden)")
        try:
            values = json.loads(Path(token_path).read_text(encoding="utf-8"))
            if not isinstance(values, dict) or not all(
                values.get(k) for k in ("client_id", "client_secret", "refresh_token")
            ):
                raise ValueError
            print("[OK] Gmail OAuth token JSON: client_id, client_secret, refresh_token present")
        except (OSError, ValueError, UnicodeError):
            print("[INVALID] Gmail OAuth token JSON: missing required credentials or unreadable")
            ready = False
    sender_key, sender = _active_setting(
        "SIGMA_GMAIL_SENDER",
        "SIGMA_EMAIL_GMAIL_SENDER",
        "SIGMA_INVITATION_GMAIL_SENDER",
    )
    if sender:
        try:
            cloud_auth._normalize_email(sender)
        except ValueError:
            print(f"[INVALID] {sender_key}: expected a valid Gmail sender address")
            ready = False
        else:
            print(f"[OK] {sender_key}: {sender}")
    else:
        print(f"[MISSING] {sender_key}: Gmail address authorized for the OAuth token")
        ready = False
    if not ready:
        print("Expected Gmail API settings: SIGMA_GMAIL_TOKEN_FILE=<absolute JSON path>")
        print("and SIGMA_GMAIL_SENDER=<authorized Gmail mailbox>.")
        print("For SMTP instead, rerun with --transport smtp.")
    return ready


def _smtp_failure_hint(exc: Exception) -> str:
    """Classify only safe exception types/codes; never print provider error text."""
    cause = exc.__cause__
    if isinstance(cause, smtplib.SMTPAuthenticationError):
        code = cause.smtp_code if isinstance(cause.smtp_code, int) else None
        detail = f" (SMTP code {code})" if code is not None else ""
        return (
            f"SMTP authentication rejected{detail}. Check that the Gmail app password "
            "belongs to the SMTP sender, has not been revoked, and is not the account password."
        )
    if isinstance(cause, smtplib.SMTPNotSupportedError):
        return "SMTP server does not support a requested feature (STARTTLS or authentication)."
    if isinstance(cause, (smtplib.SMTPConnectError, socket.gaierror)):
        return "SMTP connection or DNS failed. Check network access to smtp.gmail.com:587."
    if isinstance(cause, (ssl.SSLError, ssl.SSLCertVerificationError)):
        return "SMTP TLS handshake/certificate failed. Check system certificates and TLS access."
    if isinstance(cause, (ConnectionError, TimeoutError, smtplib.SMTPServerDisconnected)):
        return "SMTP connection closed, was refused, or timed out. Check network/firewall access."
    if isinstance(cause, smtplib.SMTPRecipientsRefused) or getattr(exc, "refused_recipients", ()):
        return "SMTP rejected a recipient address. Verify the destination mailbox."
    if isinstance(cause, smtplib.SMTPResponseException):
        code = cause.smtp_code if isinstance(cause.smtp_code, int) else None
        detail = f" (SMTP code {code})" if code is not None else ""
        return f"SMTP server rejected a command{detail}. Review sending account permissions."
    if isinstance(cause, OSError):
        return "SMTP transport encountered an operating-system/network error."
    return "SMTP failed at an unclassified stage. The provider's raw error is suppressed."


def _execute(message: str) -> int:
    from sigma import cloud_auth

    print("SIGMA feedback mail diagnostic (local CLI)")
    print("Submission: notification test only; no feedback database record.")
    print("Browser identity: unavailable to CLI; configured local --signin identity is used.")
    contact_raw = os.environ.get("SIGMA_CLOUD_ADMIN_CONTACT_EMAIL", "").strip()
    contact_email: str | None = None
    if not contact_raw:
        print(
            "[MISSING] SIGMA_CLOUD_ADMIN_CONTACT_EMAIL: local Google sign-in email and test recipient"
        )
    else:
        try:
            contact_email = cloud_auth._normalize_email(contact_raw)
        except ValueError:
            print("[INVALID] SIGMA_CLOUD_ADMIN_CONTACT_EMAIL: expected an email address")
        else:
            print(f"[OK] SIGMA_CLOUD_ADMIN_CONTACT_EMAIL: {contact_email} (test recipient)")

    gmail = bool(cloud_auth.email_env("GMAIL_TOKEN_FILE"))
    print(f"Transport: {'Gmail API' if gmail else 'SMTP'}")
    ready = _gmail_ready() if gmail else _smtp_ready()
    if not ready or contact_email is None:
        if ready:
            print("Set SIGMA_CLOUD_ADMIN_CONTACT_EMAIL in the checkout's ignored .env.")
        print("RESULT: NOT SENT (configuration incomplete).")
        return 2

    print("Configuration: ready. Attempting one send; no automatic retry.")
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
        print(_smtp_failure_hint(exc), file=sys.stderr)
        if exc.state != "failed":
            print("Delivery may have occurred; inspect the inbox before retrying.", file=sys.stderr)
        return 1
    except (OSError, ValueError, RuntimeError) as exc:
        print("RESULT: FAILED (mail transport did not confirm delivery).", file=sys.stderr)
        print(f"Diagnostic category: {type(exc).__name__}", file=sys.stderr)
        if gmail:
            print("Check whether the Gmail OAuth refresh token is still valid.", file=sys.stderr)
        else:
            print("Check SMTP settings and network access; no automatic retry.", file=sys.stderr)
        return 1
    print("RESULT: ACCEPTED by mail provider. Check the recipient inbox.")
    return 0


def run(message: str, *, transport: str = "configured") -> int:
    """Exercise the feedback notification mail path without browser or persistence."""
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
