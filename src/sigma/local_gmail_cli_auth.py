"""CLI-owned local Gmail OAuth flow using SIGMA's already-registered web redirect.

No SIGMA application server, database, or browser cookie is involved. The OAuth
consent identifies the sending Google account independently of SIGMA UI login.
Nothing in this module runs in SIGMA's production backend.
"""

from __future__ import annotations

import base64
import hashlib
import json
import os
import secrets
import stat
import time
import webbrowser
from email.utils import parseaddr
from http.server import BaseHTTPRequestHandler, HTTPServer
from pathlib import Path
from tempfile import NamedTemporaryFile
from urllib.parse import parse_qs, urlencode, urlsplit

import httpx
import jwt

from sigma.config_secrets import SecretConfigurationError, secret_value

GMAIL_SEND_SCOPE = "https://www.googleapis.com/auth/gmail.send"
REDIRECT_URI = "http://127.0.0.1:5173/api/cloud-auth/callback"
GOOGLE_AUTHORIZE = "https://accounts.google.com/o/oauth2/v2/auth"
GOOGLE_TOKEN = "https://oauth2.googleapis.com/token"
GOOGLE_DISCOVERY = "https://accounts.google.com/.well-known/openid-configuration"
GRANT_FILENAME = "gmail-send-token.json"


class LocalGmailAuthError(RuntimeError):
    """An actionable CLI authorization failure (never includes Google secrets)."""


def _home() -> Path:
    name = os.environ.get("SIGMA_CLOUD_AUTH_HOME", "").strip()
    return Path(name) if name else Path.home() / ".sigma" / "local-cloud-auth"


def _client_credentials() -> tuple[str, str]:
    client_id = os.environ.get("GOOGLE_OIDC_CLIENT_ID", "").strip()
    try:
        client_secret = secret_value("GOOGLE_OIDC_CLIENT_SECRET") or ""
    except SecretConfigurationError as exc:
        raise LocalGmailAuthError(
            "Invalid GOOGLE_OIDC_CLIENT_SECRET[_FILE] configuration."
        ) from exc
    if not client_id or not client_secret:
        raise LocalGmailAuthError(
            "Local Gmail authorization needs GOOGLE_OIDC_CLIENT_ID and "
            "GOOGLE_OIDC_CLIENT_SECRET (or GOOGLE_OIDC_CLIENT_SECRET_FILE) "
            "in the checkout .env. Use the Google web client already configured for local SIGMA."
        )
    return client_id, client_secret


def _private_home(*, create: bool) -> Path:
    home = _home()
    if create:
        try:
            home.mkdir(parents=True, exist_ok=True, mode=0o700)
        except OSError as exc:
            raise LocalGmailAuthError(
                "Cannot create the local Gmail credential directory."
            ) from exc
    try:
        info = home.lstat()
    except OSError as exc:
        raise LocalGmailAuthError("Local Gmail credential directory is unavailable.") from exc
    if (
        not stat.S_ISDIR(info.st_mode)
        or info.st_uid != os.getuid()
        or stat.S_IMODE(info.st_mode) & 0o077
    ):
        raise LocalGmailAuthError(
            f"Local Gmail credential directory must be a private directory owned by you: {home}"
        )
    return home


def existing_grant() -> tuple[Path, str] | None:
    """Read only a private OAuth grant bound to the configured local web client."""
    client_id = os.environ.get("GOOGLE_OIDC_CLIENT_ID", "").strip()
    if not client_id:
        return None
    path = _home() / GRANT_FILENAME
    try:
        home = path.parent.lstat()
        info = path.lstat()
        if (
            not stat.S_ISDIR(home.st_mode)
            or home.st_uid != os.getuid()
            or stat.S_IMODE(home.st_mode) & 0o077
            or not stat.S_ISREG(info.st_mode)
            or info.st_uid != os.getuid()
            or stat.S_IMODE(info.st_mode) & 0o077
        ):
            return None
        if info.st_size > 16_384:
            return None
        data = json.loads(path.read_text(encoding="utf-8"))
    except (OSError, ValueError, UnicodeError):
        return None
    if not isinstance(data, dict) or data.get("client_id") != client_id:
        return None
    if not all(
        isinstance(data.get(key), str) and data[key]
        for key in ("sender", "subject", "client_id", "client_secret", "refresh_token")
    ):
        return None
    if GMAIL_SEND_SCOPE not in str(data.get("scope", "")).split():
        return None
    sender = str(data["sender"])
    if parseaddr(sender)[1] != sender or "@" not in sender:
        return None
    return path, sender


def _save_grant(
    *, sender: str, subject: str, client_id: str, client_secret: str, refresh_token: str, scope: str
) -> Path:
    home = _private_home(create=True)
    if not subject or not refresh_token or GMAIL_SEND_SCOPE not in scope.split():
        raise LocalGmailAuthError("Google did not grant offline Gmail Send permission.")
    existing = home / GRANT_FILENAME
    if existing.is_symlink():
        raise LocalGmailAuthError("Refusing a symlinked Gmail credential file.")
    temporary: Path | None = None
    try:
        with NamedTemporaryFile(
            "w", encoding="utf-8", dir=home, prefix=".gmail-send-", delete=False
        ) as stream:
            temporary = Path(stream.name)
            os.fchmod(stream.fileno(), 0o600)
            json.dump(
                {
                    "sender": sender,
                    "subject": subject,
                    "scope": scope,
                    "client_id": client_id,
                    "client_secret": client_secret,
                    "refresh_token": refresh_token,
                },
                stream,
            )
            stream.flush()
            os.fsync(stream.fileno())
        os.replace(temporary, existing)
        temporary = None
        return existing
    except OSError as exc:
        raise LocalGmailAuthError("Could not save the private Gmail authorization.") from exc
    finally:
        if temporary is not None:
            temporary.unlink(missing_ok=True)


def _verified_google_identity(
    client: httpx.Client, id_token: str, *, client_id: str, nonce: str
) -> tuple[str, str]:
    """Reuse the OIDC issuer, audience, nonce and JWKS checks used by SIGMA."""
    try:
        discovery_response = client.get(GOOGLE_DISCOVERY)
        discovery_response.raise_for_status()
        discovery = discovery_response.json()
        jwks_uri = discovery.get("jwks_uri")
        if (
            discovery.get("issuer") != "https://accounts.google.com"
            or not isinstance(jwks_uri, str)
            or not jwks_uri.startswith("https://www.googleapis.com/")
        ):
            raise ValueError("Unrecognized Google discovery document.")
        jwks_response = client.get(jwks_uri)
        jwks_response.raise_for_status()
        if len(jwks_response.content) > 256_000:
            raise ValueError("Oversized Google signing keys.")
        jwks = jwt.PyJWKSet.from_dict(jwks_response.json())
        header = jwt.get_unverified_header(id_token)
        matched = [
            key
            for key in jwks.keys
            if key.key_id == header.get("kid")
            and key.algorithm_name == "RS256"
            and key.public_key_use == "sig"
        ]
        if len(matched) != 1:
            raise ValueError("Unknown Google signing key.")
        claims = jwt.decode(
            id_token,
            matched[0].key,
            algorithms=["RS256"],
            audience=client_id,
            issuer=["https://accounts.google.com", "accounts.google.com"],
            options={"require": ["iss", "aud", "exp", "iat", "sub", "nonce"]},
        )
        if (
            claims.get("aud") != client_id
            or (claims.get("azp") is not None and claims["azp"] != client_id)
            or not secrets.compare_digest(str(claims.get("nonce", "")), nonce)
            or claims.get("email_verified") is not True
        ):
            raise ValueError("Google account verification failed.")
        sender = str(claims.get("email", "")).strip().casefold()
        if parseaddr(sender)[1] != sender or "@" not in sender or len(sender) > 254:
            raise ValueError("Invalid verified Google email.")
        subject = claims.get("sub")
        if not isinstance(subject, str) or not subject or len(subject) > 255:
            raise ValueError("Invalid Google subject.")
        return sender, subject
    except (
        httpx.HTTPError,
        jwt.PyJWTError,
        ValueError,
        KeyError,
        TypeError,
        AttributeError,
    ) as exc:
        raise LocalGmailAuthError(
            "Google identity validation failed; no Gmail authorization was saved."
        ) from exc


def _wait_for_existing_sigma(expected_state: str, authorize_url: str) -> str:
    """Use SIGMA's running local callback with a private, one-time handoff."""
    from sigma.local_gmail_cli_bridge import pending_flow, result

    home = _private_home(create=True)
    try:
        with pending_flow(home, expected_state):
            try:
                with httpx.Client(timeout=3, trust_env=False, follow_redirects=False) as client:
                    response = client.get(
                        "http://127.0.0.1:5173/api/cloud-auth/mail/cli-bridge-ready",
                        params={"state": expected_state},
                    )
                    response.raise_for_status()
                    probe = response.json()
            except (httpx.HTTPError, ValueError) as exc:
                raise LocalGmailAuthError(
                    "Port 5173 is in use, but no compatible local SIGMA Gmail callback "
                    "was detected. Update/restart the local SIGMA server once, or "
                    "run ./sigma shutdown to free the port, then retry. "
                    "Production is unaffected."
                ) from exc
            if (
                not isinstance(probe, dict)
                or probe.get("protocol") != 1
                or probe.get("ready") is not True
            ):
                raise LocalGmailAuthError(
                    "A listener owns port 5173, but it cannot receive this CLI's "
                    "Google callback. Restart the local SIGMA UI with the updated "
                    "checkout, or run ./sigma shutdown to free the port."
                )
            print("Using the running local SIGMA server for the Google callback.")
            print("Opening Google authorization in your browser.")
            if not webbrowser.open(authorize_url, new=2):
                raise LocalGmailAuthError(
                    "Could not open your browser automatically. Check your default browser setup."
                )
            deadline = time.monotonic() + 300
            while time.monotonic() < deadline:
                response = result(home, expected_state)
                if response is not None:
                    code, declined = response
                    if declined:
                        raise LocalGmailAuthError("Google permission was cancelled or declined.")
                    if code:
                        return code
                time.sleep(0.25)
            raise LocalGmailAuthError(
                "Google permission was not completed before the local callback expired."
            )
    except (OSError, ValueError) as exc:
        raise LocalGmailAuthError(
            "Could not create or read the private local Gmail callback handoff."
        ) from exc


def _wait_for_google_callback(expected_state: str, authorize_url: str) -> str:
    """Serve only the registered localhost OAuth callback, without starting SIGMA."""
    result: dict[str, str] = {}

    class Callback(BaseHTTPRequestHandler):
        def log_message(self, format: str, *args: object) -> None:
            pass  # Never log authorization codes or states.

        def do_GET(self) -> None:
            if len(self.path) > 12_000:
                self.send_error(400)
                return
            parsed = urlsplit(self.path)
            if parsed.path != "/api/cloud-auth/callback":
                self.send_error(404)
                return
            try:
                args = parse_qs(parsed.query, max_num_fields=8)
            except ValueError:
                self.send_error(400)
                return
            state, code, error = (
                args.get("state", []),
                args.get("code", []),
                args.get("error", []),
            )
            if state != [expected_state] or len(code) > 1 or len(error) > 1:
                self.send_error(400)
                return
            if not code and not error:
                self.send_error(400)
                return
            if error:
                result["error"] = "Google permission was cancelled or declined."
            else:
                result["code"] = code[0]
            body = (
                b"<!doctype html><meta charset='utf-8'><title>SIGMA Gmail</title>"
                b"<p>SIGMA received the Google response. Return to your terminal.</p>"
            )
            self.send_response(200)
            self.send_header("Content-Type", "text/html; charset=utf-8")
            self.send_header("Cache-Control", "no-store")
            self.send_header("Content-Security-Policy", "default-src 'none'")
            self.send_header("X-Content-Type-Options", "nosniff")
            self.send_header("Content-Length", str(len(body)))
            self.end_headers()
            self.wfile.write(body)

    class Loopback(HTTPServer):
        allow_reuse_address = False

    try:
        server = Loopback(("127.0.0.1", 5173), Callback)
    except OSError:
        return _wait_for_existing_sigma(expected_state, authorize_url)
    with server:
        print("Opening Google authorization in your browser (no SIGMA UI server needed).")
        if not webbrowser.open(authorize_url, new=2):
            raise LocalGmailAuthError(
                "Could not open your browser automatically. Check your default browser setup."
            )
        deadline = time.monotonic() + 300
        server.timeout = 0.5
        while not result and time.monotonic() < deadline:
            server.handle_request()
    if "error" in result:
        raise LocalGmailAuthError(result["error"])
    if "code" not in result:
        raise LocalGmailAuthError(
            "Google permission was not completed before the local callback expired."
        )
    return result["code"]


def authorize() -> tuple[Path, str]:
    """Authorize Gmail sending once, then return a private grant and verified sender."""
    client_id, client_secret = _client_credentials()
    state = secrets.token_urlsafe(32)
    nonce = secrets.token_urlsafe(32)
    verifier = secrets.token_urlsafe(48)
    challenge = (
        base64.urlsafe_b64encode(hashlib.sha256(verifier.encode()).digest()).rstrip(b"=").decode()
    )
    params = {
        "client_id": client_id,
        "redirect_uri": REDIRECT_URI,
        "response_type": "code",
        "scope": "openid email profile " + GMAIL_SEND_SCOPE,
        "state": state,
        "nonce": nonce,
        "code_challenge": challenge,
        "code_challenge_method": "S256",
        "access_type": "offline",
        "prompt": "consent select_account",
    }
    code = _wait_for_google_callback(state, GOOGLE_AUTHORIZE + "?" + urlencode(params))
    try:
        with httpx.Client(timeout=15, trust_env=False, follow_redirects=False) as client:
            response = client.post(
                GOOGLE_TOKEN,
                data={
                    "code": code,
                    "client_id": client_id,
                    "client_secret": client_secret,
                    "redirect_uri": REDIRECT_URI,
                    "grant_type": "authorization_code",
                    "code_verifier": verifier,
                },
            )
            response.raise_for_status()
            token_data = response.json()
            if not isinstance(token_data, dict):
                raise TypeError("Invalid Google response.")
            scope = str(token_data.get("scope", ""))
            refresh_token = token_data.get("refresh_token")
            id_token = token_data.get("id_token")
            if (
                GMAIL_SEND_SCOPE not in scope.split()
                or not isinstance(refresh_token, str)
                or not refresh_token
                or not isinstance(id_token, str)
                or not id_token
            ):
                raise LocalGmailAuthError(
                    "Google did not return offline Gmail Send permission. "
                    "The Google client may require tester access or verification."
                )
            sender, subject = _verified_google_identity(
                client, id_token, client_id=client_id, nonce=nonce
            )
    except (httpx.HTTPError, ValueError, KeyError, TypeError) as exc:
        raise LocalGmailAuthError(
            "Google authorization exchange failed. Check that this local web client "
            "allows the redirect http://127.0.0.1:5173/api/cloud-auth/callback "
            "and that Gmail Send consent is permitted."
        ) from exc
    path = _save_grant(
        sender=sender,
        subject=subject,
        client_id=client_id,
        client_secret=client_secret,
        refresh_token=refresh_token,
        scope=scope,
    )
    print(f"Google Gmail Send authorized for: {sender}")
    print(f"Private grant saved at: {path} (contents hidden)")
    return path, sender
