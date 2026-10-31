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
    token_file = os.environ.get("SIGMA_INVITATION_GMAIL_TOKEN_FILE", "").strip()
    sender = os.environ.get("SIGMA_INVITATION_GMAIL_SENDER", "").strip().lower()
    if not token_file or not sender or not recipients:
        raise RuntimeError("Invitation delivery is not configured.")
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

        message = EmailMessage()
        message["From"] = sender
        if len(recipients) == 1:
            message["To"] = recipients[0]
        else:
            message["To"] = sender
            message["Bcc"] = ", ".join(recipients)
        message["Subject"] = subject
        message.set_content(body)
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
