"""Gmail API invitation notifications using a locally authorized OAuth refresh token.

The token file is created by the operator using the gmail.send scope. Never
commit it, include it in images, or expose it to the browser.
"""

from __future__ import annotations

import base64
import json
import os
from email.message import EmailMessage
from pathlib import Path
from urllib.error import HTTPError, URLError
from urllib.parse import urlencode
from urllib.request import Request, urlopen

def _email_env(suffix: str) -> str:
    direct = os.environ.get(f"SIGMA_{suffix}")
    if direct is not None:
        return direct.strip()
    modern = os.environ.get(f"SIGMA_EMAIL_{suffix}")
    if modern is not None:
        return modern.strip()
    return os.environ.get(f"SIGMA_INVITATION_{suffix}", "").strip()


TOKEN_ENDPOINT = "https://oauth2.googleapis.com/token"
SEND_ENDPOINT = "https://gmail.googleapis.com/gmail/v1/users/me/messages/send"


def send_invitation(
    email: str, requested_at: int, *, recipient: str, request_type: str = "invitation"
) -> None:
    """Preserve the existing single-recipient invitation API."""
    subject = (
        "SIGMA sponsorship reload request"
        if request_type == "reload"
        else "SIGMA invitation request"
    )
    introduction = (
        "A signed-in SIGMA member requested a sponsored allowance reload.\n\n"
        if request_type == "reload"
        else "A verified Google account requested SIGMA access.\n\n"
    )
    send_admin_notification(
        subject,
        introduction + f"Account: {email}\nRequested at (UTC epoch): {requested_at}\n",
        recipients=[recipient],
    )


def send_admin_notification(subject: str, body: str, *, recipients: list[str]) -> None:
    """Send one privacy-preserving email to verified active administrators."""
    sender = _email_env("GMAIL_SENDER").lower()
    if not sender or not recipients:
        raise RuntimeError("Invitation delivery is not configured.")
    message = EmailMessage()
    if len(recipients) == 1:
        message["To"] = recipients[0]
    else:
        message["To"] = sender
        message["Bcc"] = ", ".join(recipients)
    message["Subject"] = subject
    message.set_content(body)
    send_message(message, recipients=recipients)


def send_message(message: EmailMessage, *, recipients: list[str], reply_to: str | None = None) -> None:
    """Deliver a complete MIME message through SIGMA's configured Gmail OAuth account.

    Gmail API accepts the MIME recipient headers rather than an SMTP envelope.
    A failed API request can have an uncertain outcome; callers must not auto-retry.
    """
    token_file = _email_env("GMAIL_TOKEN_FILE")
    sender = _email_env("GMAIL_SENDER").lower()
    if not token_file or not sender or not recipients:
        raise RuntimeError("Gmail delivery is not configured.")
    if any(header in message for header in ("From", "To", "Cc", "Bcc")):
        raise ValueError("Recipient and sender headers must be assigned by the transport.")
    message["From"] = sender
    if len(recipients) == 1:
        message["To"] = recipients[0]
    else:
        message["To"] = sender
        message["Bcc"] = ", ".join(recipients)
    if reply_to:
        message["Reply-To"] = reply_to
    try:
        path = Path(token_file)
        credentials = json.loads(path.read_text(encoding="utf-8"))
        if not isinstance(credentials, dict):
            raise TypeError("Invalid OAuth credentials")
        if not {"client_id", "client_secret", "refresh_token"} <= credentials.keys():
            raise ValueError("Missing OAuth refresh credentials")
        if not all(credentials[k] for k in ("client_id", "client_secret", "refresh_token")):
            raise ValueError("Empty OAuth refresh credentials")
        # Do not accept an arbitrary token endpoint from the credentials file.
        data = urlencode(
            {
                "client_id": credentials["client_id"],
                "client_secret": credentials["client_secret"],
                "refresh_token": credentials["refresh_token"],
                "grant_type": "refresh_token",
            }
        ).encode("utf-8")
        request = Request(
            TOKEN_ENDPOINT,
            data=data,
            headers={"Content-Type": "application/x-www-form-urlencoded"},
            method="POST",
        )
        with urlopen(request, timeout=15) as response:
            token = json.load(response)["access_token"]

        raw = base64.urlsafe_b64encode(message.as_bytes()).decode("ascii")
        request = Request(
            SEND_ENDPOINT,
            data=json.dumps({"raw": raw}).encode("utf-8"),
            headers={
                "Authorization": f"Bearer {token}",
                "Content-Type": "application/json",
            },
            method="POST",
        )
        with urlopen(request, timeout=15) as response:
            if response.status != 200:
                raise ValueError("Gmail API send was unsuccessful")
    except (OSError, ValueError, KeyError, TypeError, HTTPError, URLError):
        # Avoid leaking OAuth tokens, response bodies, or provider error details.
        raise RuntimeError("Invitation notification could not be delivered.") from None
