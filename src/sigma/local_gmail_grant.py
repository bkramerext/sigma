"""Local-only Google Gmail Send grant; never available to hosted deployments.

The existing UI sign-in verifies identity only. Gmail sending requires a separate
explicit, scope-limited Google consent on the same local web OAuth client.
"""

from __future__ import annotations

import json
import os
import stat
from pathlib import Path
from tempfile import NamedTemporaryFile
from typing import Any

GMAIL_SEND_SCOPE = "https://www.googleapis.com/auth/gmail.send"
GRANT_NAME = "gmail-send-token.json"


def grant_path(home: Path) -> Path:
    return home / GRANT_NAME


def grant_for_account(
    home: Path, *, email: str, client_id: str
) -> tuple[Path, dict[str, str]] | None:
    """Return a private, matching grant only; never substitute another Google user."""
    if not email or not client_id:
        return None
    path = grant_path(home)
    try:
        info = path.lstat()
        if not stat.S_ISREG(info.st_mode) or info.st_mode & 0o077:
            return None
        with path.open(encoding="utf-8") as stream:
            data = json.load(stream)
    except (OSError, ValueError, UnicodeError):
        return None
    if not isinstance(data, dict):
        return None
    if data.get("sender") != email.strip().casefold() or data.get("client_id") != client_id:
        return None
    if not all(
        isinstance(data.get(key), str) and data[key]
        for key in ("subject", "client_id", "client_secret", "refresh_token", "sender")
    ):
        return None
    if data["subject"].startswith(("mock:", "local-admin:")):
        return None
    if GMAIL_SEND_SCOPE not in str(data.get("scope", "")).split():
        return None
    return path, data


def save_grant(
    home: Path,
    *,
    subject: str,
    sender: str,
    client_id: str,
    client_secret: str,
    refresh_token: str,
    scope: str,
) -> Path:
    """Write an authorized local Gmail grant atomically, mode 0600."""
    if not subject or not sender or not client_id or not client_secret or not refresh_token:
        raise ValueError("Missing Google mail authorization.")
    if subject.startswith(("mock:", "local-admin:")) or GMAIL_SEND_SCOPE not in scope.split():
        raise ValueError("Missing verified Gmail Send permission.")
    if not home.is_dir() or home.is_symlink():
        raise ValueError("Local authentication storage is not initialized.")
    info = home.stat()
    if info.st_mode & 0o077 or info.st_uid != os.getuid():
        raise ValueError("Local authentication storage is not private.")
    payload: dict[str, Any] = {
        "subject": subject,
        "sender": sender.strip().casefold(),
        "client_id": client_id,
        "client_secret": client_secret,
        "refresh_token": refresh_token,
        "scope": scope,
    }
    temporary: Path | None = None
    try:
        with NamedTemporaryFile(
            "w", encoding="utf-8", dir=home, prefix=".gmail-send-", delete=False
        ) as stream:
            temporary = Path(stream.name)
            os.fchmod(stream.fileno(), 0o600)
            json.dump(payload, stream)
            stream.flush()
            os.fsync(stream.fileno())
        destination = grant_path(home)
        if destination.is_symlink():
            raise ValueError("Refusing a symlinked Gmail grant.")
        os.replace(temporary, destination)
        temporary = None
        return destination
    finally:
        if temporary is not None:
            temporary.unlink(missing_ok=True)
