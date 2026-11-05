"""Single mail transport for About Feedback, Email Project, and CLI diagnostics.

The MIME message is assembled by each caller. Transport selection and
recipient handling are shared; production's explicit settings retain priority.
"""

from __future__ import annotations

from email.message import EmailMessage


def send_message(
    message: EmailMessage, *, recipients: list[str], reply_to: str | None = None
) -> None:
    """Send one MIME message using the configured Gmail API or SMTP transport."""
    from sigma import cloud_auth

    if cloud_auth.email_env("GMAIL_TOKEN_FILE"):
        from sigma.gmail_delivery import send_message as gmail_send

        gmail_send(message, recipients=recipients, reply_to=reply_to)
    else:
        cloud_auth.send_smtp_message(message, recipients, reply_to=reply_to)
