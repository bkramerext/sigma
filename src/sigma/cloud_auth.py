"""Opt-in Google OIDC access control for hosted SIGMA deployments.

Cloud identity is deliberately separate from the local ChatGPT authorization store.
The SQLite database contains only access rules, OAuth flow state, and hashed sessions.
"""

from __future__ import annotations

import base64
import hashlib
import hmac
import os
import re
import secrets
import sqlite3
import time
from dataclasses import dataclass
from pathlib import Path
from threading import Lock
from typing import Any
from urllib.parse import urlencode, urlsplit

import httpx
import jwt
from fastapi import APIRouter, HTTPException, Request
from fastapi.responses import JSONResponse, RedirectResponse, Response
from pydantic import BaseModel, Field

from sigma.config_secrets import SecretConfigurationError, secret_value

router = APIRouter(prefix="/api/cloud-auth", tags=["cloud-auth"])
SESSION_COOKIE = "__Host-sigma_session"
FLOW_COOKIE = "__Host-sigma_oidc_flow"
DENIED_COOKIE = "__Host-sigma_denied"
SESSION_SECONDS = 8 * 60 * 60
FLOW_SECONDS = 5 * 60
DENIED_SECONDS = 10 * 60
GOOGLE_ISSUERS = ("https://accounts.google.com", "accounts.google.com")
DISCOVERY_URL = "https://accounts.google.com/.well-known/openid-configuration"
_EMAIL = re.compile(r"^[^\s@<>]+@[^\s@<>]+\.[^\s@<>]+$")
_DOMAIN = re.compile(r"^(?=.{1,253}$)(?:[a-z0-9](?:[a-z0-9-]{0,61}[a-z0-9])?\.)+[a-z]{2,63}$")
_SCHEMA_LOCK = Lock()
_SCHEMA_READY: set[tuple[str, int, int]] = set()


@dataclass(frozen=True)
class Config:
    enabled: bool
    client_id: str | None
    client_secret: str | None
    origin: str | None
    admin_contact_email: str | None
    database: Path | None
    error: str | None
    local: bool = False


def _local_mode() -> bool:
    return os.environ.get("SIGMA_CLOUD_AUTH_LOCAL", "").strip().casefold() in {"1", "true", "yes"}


def _cookie_name(name: str, cfg: Config) -> str:
    return name.removeprefix("__Host-") if cfg.local else name


def _cookie_options(cfg: Config, name: str, *, max_age: int | None = None) -> dict[str, Any]:
    options: dict[str, Any] = {
        "path": "/",
        "secure": not cfg.local,
        "httponly": True,
        "samesite": "lax",
    }
    if max_age is not None:
        options["max_age"] = max_age
    return options


def _clear_cookie(response: Response, cfg: Config, name: str) -> None:
    response.delete_cookie(_cookie_name(name, cfg), **_cookie_options(cfg, name))


@dataclass(frozen=True)
class Principal:
    subject: str
    email: str
    role: str

    def public(self) -> dict[str, str]:
        return {"email": self.email, "role": self.role}


def _normalize_email(value: str) -> str:
    normalized = value.strip().casefold()
    if len(normalized) > 254 or not _EMAIL.fullmatch(normalized):
        raise ValueError("Enter a valid email address.")
    return normalized


def _normalize_domain(value: str) -> str:
    normalized = value.strip().casefold().removesuffix(".")
    if not _DOMAIN.fullmatch(normalized):
        raise ValueError("Enter an exact email domain, such as example.org.")
    return normalized


def config() -> Config:
    enabled = os.environ.get("SIGMA_CLOUD_AUTH_ENABLED", "").strip().lower() in {"1", "true", "yes"}
    local = enabled and _local_mode()
    if not enabled:
        return Config(False, None, None, None, None, None, None, False)
    client_id = os.environ.get("GOOGLE_OIDC_CLIENT_ID", "").strip() or None
    secret_error = False
    try:
        client_secret = secret_value("GOOGLE_OIDC_CLIENT_SECRET")
    except SecretConfigurationError:
        client_secret = None
        secret_error = True
    origin = os.environ.get("SIGMA_CLOUD_PUBLIC_ORIGIN", "").strip().rstrip("/") or None
    admin_contact = os.environ.get("SIGMA_CLOUD_ADMIN_CONTACT_EMAIL", "").strip()
    root = os.environ.get("SIGMA_CLOUD_AUTH_HOME", "").strip()
    error = "Cloud authentication secret configuration is invalid." if secret_error else None
    if not client_id or not client_secret or not origin or not root or not admin_contact:
        error = "Cloud authentication is enabled but required configuration is missing."
    parsed = urlsplit(origin or "")
    try:
        local_origin = (
            local
            and parsed.scheme == "http"
            and parsed.hostname in {"127.0.0.1", "localhost"}
            and parsed.port == 5173
            and parsed.path == ""
            and not parsed.query
            and not parsed.fragment
            and not parsed.username
        )
    except ValueError:
        local_origin = False
    if not error and (
        (local and not local_origin)
        or (not local and parsed.scheme != "https")
        or not parsed.hostname
        or parsed.path
        or parsed.query
        or parsed.fragment
        or parsed.username
    ):
        error = "Cloud public origin must be an exact HTTPS origin."
    database = None
    if not error:
        try:
            admin_contact = _normalize_email(admin_contact)
            path = Path(root)
            if not path.is_absolute():
                raise ValueError
            path.mkdir(mode=0o700, parents=True, exist_ok=True)
            stat = path.lstat()
            if path.is_symlink() or stat.st_uid != os.getuid() or stat.st_mode & 0o077:
                raise ValueError
            database = path / "access.sqlite3"
            if database.is_symlink():
                raise ValueError
            if database.exists():
                db_stat = database.lstat()
                if (
                    database.is_symlink()
                    or db_stat.st_uid != os.getuid()
                    or db_stat.st_mode & 0o077
                ):
                    raise ValueError
            with _SCHEMA_LOCK:
                current = database.stat() if database.exists() else None
                marker = (str(database), current.st_dev, current.st_ino) if current else None
                if not marker or marker not in _SCHEMA_READY:
                    _initialize(database)
                    current = database.stat()
                    _SCHEMA_READY.add((str(database), current.st_dev, current.st_ino))
        except (OSError, sqlite3.Error, ValueError):
            error = "Cloud authentication storage or admin configuration is invalid."
    return Config(
        True,
        client_id,
        client_secret,
        origin,
        admin_contact or None,
        database,
        error,
        local,
    )


def _connect(path: Path) -> sqlite3.Connection:
    connection = sqlite3.connect(
        path, timeout=5, isolation_level="IMMEDIATE", factory=_ClosingConnection
    )
    connection.row_factory = sqlite3.Row
    connection.execute("PRAGMA foreign_keys=ON")
    connection.execute("PRAGMA busy_timeout=5000")
    return connection


class _ClosingConnection(sqlite3.Connection):
    def __exit__(self, exc_type, exc_value, traceback):
        try:
            return super().__exit__(exc_type, exc_value, traceback)
        finally:
            self.close()


def _initialize(path: Path) -> None:
    existed = path.exists()
    with _connect(path) as db:
        db.executescript("""
            CREATE TABLE IF NOT EXISTS grants (
                kind TEXT NOT NULL CHECK(kind IN ('email','domain')),
                value TEXT NOT NULL,
                role TEXT NOT NULL CHECK(role IN ('member','admin')),
                active INTEGER NOT NULL CHECK(active IN (0,1)),
                updated_at INTEGER NOT NULL,
                allowance_usd REAL,
                PRIMARY KEY(kind,value)
            );
            CREATE TABLE IF NOT EXISTS bootstrap_subject (
                email TEXT PRIMARY KEY,
                subject TEXT NOT NULL UNIQUE
            );
            CREATE TABLE IF NOT EXISTS sessions (
                token_hash TEXT PRIMARY KEY,
                subject TEXT NOT NULL,
                email TEXT NOT NULL,
                expires_at INTEGER NOT NULL
            );
            CREATE TABLE IF NOT EXISTS identities (
                subject TEXT PRIMARY KEY,
                email TEXT NOT NULL,
                updated_at INTEGER NOT NULL
            );
            CREATE TABLE IF NOT EXISTS flows (
                state_hash TEXT PRIMARY KEY,
                nonce TEXT NOT NULL,
                verifier TEXT NOT NULL,
                expires_at INTEGER NOT NULL
            );
            CREATE TABLE IF NOT EXISTS denied_access (
                token_hash TEXT PRIMARY KEY,
                email TEXT NOT NULL,
                expires_at INTEGER NOT NULL
            );
            CREATE TABLE IF NOT EXISTS audit (
                id INTEGER PRIMARY KEY,
                actor TEXT NOT NULL,
                action TEXT NOT NULL,
                kind TEXT NOT NULL,
                value TEXT NOT NULL,
                at INTEGER NOT NULL
            );
        """)
        columns = {row["name"] for row in db.execute("PRAGMA table_info(grants)")}
        if "allowance_usd" not in columns:
            db.execute("ALTER TABLE grants ADD COLUMN allowance_usd REAL")
    if not existed:
        path.chmod(0o600)


def _hash(value: str) -> str:
    return hashlib.sha256(value.encode()).hexdigest()


def _now() -> int:
    return int(time.time())


def _db(cfg: Config) -> sqlite3.Connection:
    if not cfg.database:
        raise RuntimeError("Cloud authentication is not configured.")
    return _connect(cfg.database)


def _authorization(cfg: Config, subject: str, email: str) -> str | None:
    with _db(cfg) as db:
        return _authorization_in_db(db, cfg, subject, email)


def _authorization_in_db(
    db: sqlite3.Connection, cfg: Config, subject: str, email: str
) -> str | None:
    bound = db.execute(
        "SELECT subject FROM bootstrap_subject WHERE email=?", (cfg.admin_contact_email,)
    ).fetchone()
    if bound:
        if bound["subject"] == subject and email == cfg.admin_contact_email:
            return "admin"
        if email == cfg.admin_contact_email:
            return None
    elif email == cfg.admin_contact_email:
        db.execute("INSERT INTO bootstrap_subject(email,subject) VALUES(?,?)", (email, subject))
        return "admin"
    explicit = db.execute(
        "SELECT role,active FROM grants WHERE kind='email' AND value=?", (email,)
    ).fetchone()
    if explicit:
        return explicit["role"] if explicit["active"] else None
    domain = email.rsplit("@", 1)[1]
    allowed = db.execute(
        "SELECT role,active FROM grants WHERE kind='domain' AND value=?", (domain,)
    ).fetchone()
    return allowed["role"] if allowed and allowed["active"] else None


def resolve_session(raw: str | None) -> Principal | None:
    cfg = config()
    if not cfg.enabled or cfg.error or not raw or len(raw) > 128:
        return None
    with _db(cfg) as db:
        row = db.execute(
            "SELECT subject,email,expires_at FROM sessions WHERE token_hash=?", (_hash(raw),)
        ).fetchone()
        if not row or row["expires_at"] <= _now():
            return None
        role = _authorization(cfg, row["subject"], row["email"])
        if not role:
            db.execute("DELETE FROM sessions WHERE token_hash=?", (_hash(raw),))
            return None
        return Principal(row["subject"], row["email"], role)


async def middleware(request: Request, call_next):
    cfg = config()
    if not cfg.enabled:
        return await call_next(request)
    path = request.url.path
    public = path == "/api/ui-instance" or path in {
        "/api/cloud-auth/status",
        "/api/cloud-auth/login",
        "/api/cloud-auth/callback",
        "/api/cloud-auth/denied",
    }
    demo_public = path in {"/api/cloud-demo/", "/api/cloud-demo/report"} and request.method in {
        "GET",
        "HEAD",
    }
    if cfg.error:
        if public:
            return await call_next(request)
        return JSONResponse({"error": "Cloud authentication is not ready."}, status_code=503)
    origin = request.headers.get("origin")
    if request.method not in {"GET", "HEAD", "OPTIONS"} and origin != cfg.origin:
        return JSONResponse({"error": "Request origin is not authorized."}, status_code=403)
    if public or demo_public:
        return await call_next(request)
    try:
        principal = resolve_session(request.cookies.get(_cookie_name(SESSION_COOKIE, cfg)))
    except (sqlite3.Error, OSError, RuntimeError):
        return JSONResponse(
            {"error": "Cloud authentication is temporarily unavailable."}, status_code=503
        )
    if principal is None:
        response = JSONResponse({"error": "Authentication required."}, status_code=401)
        _clear_cookie(response, cfg, SESSION_COOKIE)
        return response
    if path.startswith("/api/cloud-auth/admin/") and principal.role != "admin":
        return JSONResponse({"error": "Administrator access required."}, status_code=403)
    # Local Google identity gates project access but does not replace the
    # separate local ChatGPT account flow. Hosted SIGMA must never proxy a
    # user's personal ChatGPT authorization through the service.
    if path.startswith("/api/ai/") and not cfg.local:
        return JSONResponse(
            {"error": "AI provider authorization is unavailable in cloud mode."}, status_code=403
        )
    request.state.cloud_principal = principal
    response = await call_next(request)
    response.headers["Cache-Control"] = "no-store"
    response.headers["Referrer-Policy"] = "no-referrer"
    response.headers["X-Content-Type-Options"] = "nosniff"
    response.headers["Content-Security-Policy"] = "frame-ancestors 'none'"
    return response


@router.get("/status")
def status(request: Request):
    cfg = config()
    local_setup_missing = []
    if not cfg.enabled or cfg.local:
        local_setup_missing = [
            key
            for key in (
                "GOOGLE_OIDC_CLIENT_ID",
                "GOOGLE_OIDC_CLIENT_SECRET",
                "SIGMA_CLOUD_ADMIN_CONTACT_EMAIL",
            )
            if not os.environ.get(key, "").strip()
        ]
    try:
        principal = (
            resolve_session(request.cookies.get(_cookie_name(SESSION_COOKIE, cfg)))
            if cfg.enabled and not cfg.error
            else None
        )
    except (sqlite3.Error, OSError, RuntimeError):
        return {
            "enabled": cfg.enabled,
            "ready": False,
            "local_setup_missing": local_setup_missing,
            "authenticated": False,
            "user": None,
        }
    return {
        "enabled": cfg.enabled,
        "ready": not cfg.error if cfg.enabled else True,
        # Names only: the setup panel can explain missing local prerequisites
        # without ever returning OAuth secrets or the configured admin email.
        "local_setup_missing": local_setup_missing,
        "authenticated": principal is not None,
        "user": principal.public() if principal else None,
        "admin_contact_email": cfg.admin_contact_email if cfg.enabled and not cfg.error else None,
        "target": "local" if cfg.local else "hosted" if cfg.enabled else "local",
    }


@router.get("/login")
def login(
    request: Request,
):
    cfg = config()
    if not cfg.enabled:
        return RedirectResponse("/")
    if cfg.error or not cfg.origin or not cfg.client_id:
        raise HTTPException(503, "Cloud authentication is not ready.")
    state, nonce, verifier = (
        secrets.token_urlsafe(32),
        secrets.token_urlsafe(32),
        secrets.token_urlsafe(48),
    )
    challenge = (
        base64.urlsafe_b64encode(hashlib.sha256(verifier.encode()).digest()).rstrip(b"=").decode()
    )
    denied_cookie = request.cookies.get(_cookie_name(DENIED_COOKIE, cfg))
    session_cookie = request.cookies.get(_cookie_name(SESSION_COOKIE, cfg))
    with _db(cfg) as db:
        if denied_cookie:
            db.execute("DELETE FROM denied_access WHERE token_hash=?", (_hash(denied_cookie),))
        if session_cookie:
            db.execute("DELETE FROM sessions WHERE token_hash=?", (_hash(session_cookie),))
        db.execute("DELETE FROM flows WHERE expires_at<=?", (_now(),))
        db.execute(
            "INSERT INTO flows(state_hash,nonce,verifier,expires_at) VALUES(?,?,?,?)",
            (_hash(state), nonce, verifier, _now() + FLOW_SECONDS),
        )
    params = {
        "client_id": cfg.client_id,
        "redirect_uri": cfg.origin + "/api/cloud-auth/callback",
        "response_type": "code",
        "scope": "openid email profile",
        "state": state,
        "nonce": nonce,
        "code_challenge": challenge,
        "code_challenge_method": "S256",
        "access_type": "online",
        "prompt": "select_account",
    }
    response = RedirectResponse(
        "https://accounts.google.com/o/oauth2/v2/auth?" + urlencode(params), status_code=302
    )
    response.set_cookie(
        _cookie_name(FLOW_COOKIE, cfg),
        state,
        **_cookie_options(cfg, FLOW_COOKIE, max_age=FLOW_SECONDS),
    )
    _clear_cookie(response, cfg, DENIED_COOKIE)
    _clear_cookie(response, cfg, SESSION_COOKIE)
    response.headers["Cache-Control"] = "no-store"
    response.headers["Referrer-Policy"] = "no-referrer"
    return response


@router.get("/callback")
async def callback(
    request: Request,
    state: str = "",
    code: str = "",
    error: str = "",
):
    cfg = config()
    if not cfg.enabled or cfg.error or not cfg.origin or not cfg.client_id or not cfg.client_secret:
        raise HTTPException(503, "Cloud authentication is not ready.")
    flow_cookie = request.cookies.get(_cookie_name(FLOW_COOKIE, cfg))
    denied_cookie = request.cookies.get(_cookie_name(DENIED_COOKIE, cfg))
    session_cookie = request.cookies.get(_cookie_name(SESSION_COOKIE, cfg))
    if (
        error
        or not state
        or not code
        or not flow_cookie
        or not hmac.compare_digest(state, flow_cookie)
    ):
        raise HTTPException(400, "Sign-in could not be verified.")
    with _db(cfg) as db:
        flow = db.execute(
            "SELECT nonce,verifier,expires_at FROM flows WHERE state_hash=?", (_hash(state),)
        ).fetchone()
        db.execute("DELETE FROM flows WHERE state_hash=?", (_hash(state),))
    if not flow or flow["expires_at"] <= _now():
        raise HTTPException(400, "Sign-in has expired. Please try again.")
    try:
        async with httpx.AsyncClient(timeout=8, trust_env=False, follow_redirects=False) as client:
            token_response = await client.post(
                "https://oauth2.googleapis.com/token",
                data={
                    "code": code,
                    "client_id": cfg.client_id,
                    "client_secret": cfg.client_secret,
                    "redirect_uri": cfg.origin + "/api/cloud-auth/callback",
                    "grant_type": "authorization_code",
                    "code_verifier": flow["verifier"],
                },
            )
            token_response.raise_for_status()
            token_data = token_response.json()
            if not isinstance(token_data, dict):
                raise TypeError("Invalid token response")
            id_token = token_data.get("id_token")
            if not isinstance(id_token, str) or len(id_token) > 16384:
                raise ValueError("Missing ID token")
            discovery_response = await client.get(DISCOVERY_URL)
            discovery_response.raise_for_status()
            discovery = discovery_response.json()
            if (
                discovery.get("issuer") != "https://accounts.google.com"
                or not isinstance(discovery.get("jwks_uri"), str)
                or not discovery["jwks_uri"].startswith("https://www.googleapis.com/")
            ):
                raise ValueError("Invalid OIDC discovery")
            jwks_response = await client.get(discovery["jwks_uri"])
            jwks_response.raise_for_status()
            if len(jwks_response.content) > 256_000:
                raise ValueError("Oversized JWKS")
            jwks = jwt.PyJWKSet.from_dict(jwks_response.json())
            header = jwt.get_unverified_header(id_token)
            key_id = header.get("kid")
            signing_keys = [
                key
                for key in jwks.keys
                if key.key_id == key_id
                and key.algorithm_name == "RS256"
                and key.public_key_use == "sig"
            ]
            if len(signing_keys) != 1:
                raise ValueError("Unknown signing key")
            key = signing_keys[0].key
        claims = jwt.decode(
            id_token,
            key,
            algorithms=["RS256"],
            audience=cfg.client_id,
            issuer=list(GOOGLE_ISSUERS),
            options={"require": ["iss", "aud", "exp", "iat", "sub", "nonce"]},
        )
        if claims.get("aud") != cfg.client_id or (
            claims.get("azp") is not None and claims.get("azp") != cfg.client_id
        ):
            raise ValueError("Invalid audience")
        if not hmac.compare_digest(str(claims.get("nonce", "")), flow["nonce"]):
            raise ValueError("Invalid nonce")
        if claims.get("email_verified") is not True:
            raise ValueError("Unverified email")
        email = _normalize_email(claims.get("email", ""))
        subject = claims.get("sub")
        if not isinstance(subject, str) or not subject or len(subject) > 255:
            raise ValueError("Invalid subject")
    except (httpx.HTTPError, jwt.PyJWTError, ValueError, KeyError, TypeError, AttributeError):
        raise HTTPException(401, "Google sign-in could not be verified.") from None
    role = _authorization(cfg, subject, email)
    if not role:
        denied_token = secrets.token_urlsafe(32)
        with _db(cfg) as db:
            if session_cookie:
                db.execute("DELETE FROM sessions WHERE token_hash=?", (_hash(session_cookie),))
            db.execute("DELETE FROM denied_access WHERE expires_at<=?", (_now(),))
            if denied_cookie:
                db.execute("DELETE FROM denied_access WHERE token_hash=?", (_hash(denied_cookie),))
            db.execute(
                "INSERT INTO denied_access(token_hash,email,expires_at) VALUES(?,?,?)",
                (_hash(denied_token), email, _now() + DENIED_SECONDS),
            )
        response = RedirectResponse("/?access=denied", status_code=303)
        _clear_cookie(response, cfg, FLOW_COOKIE)
        _clear_cookie(response, cfg, SESSION_COOKIE)
        response.set_cookie(
            _cookie_name(DENIED_COOKIE, cfg),
            denied_token,
            **_cookie_options(cfg, DENIED_COOKIE, max_age=DENIED_SECONDS),
        )
        response.headers["Cache-Control"] = "no-store"
        response.headers["Referrer-Policy"] = "no-referrer"
        return response
    # Provision only after the Google subject has passed authorization, before
    # an authenticated session is issued. This creates an empty root and keeps
    # identity/provider concerns out of project path handling.
    if not cfg.local:
        from sigma.cloud_workspaces import WorkspaceUnavailable, workspace_for_subject

        try:
            workspace_for_subject(subject)
        except WorkspaceUnavailable as exc:
            raise HTTPException(503, "Private workspace is unavailable.") from exc
    raw = secrets.token_urlsafe(32)
    with _db(cfg) as db:
        db.execute(
            "INSERT INTO identities(subject,email,updated_at) VALUES(?,?,?) ON CONFLICT(subject) DO UPDATE SET email=excluded.email,updated_at=excluded.updated_at",
            (subject, email, _now()),
        )
        db.execute(
            "INSERT INTO sessions(token_hash,subject,email,expires_at) VALUES(?,?,?,?)",
            (_hash(raw), subject, email, _now() + SESSION_SECONDS),
        )
    response = RedirectResponse("/", status_code=303)
    response.set_cookie(
        _cookie_name(SESSION_COOKIE, cfg),
        raw,
        **_cookie_options(cfg, SESSION_COOKIE, max_age=SESSION_SECONDS),
    )
    _clear_cookie(response, cfg, FLOW_COOKIE)
    _clear_cookie(response, cfg, DENIED_COOKIE)
    response.headers["Cache-Control"] = "no-store"
    response.headers["Referrer-Policy"] = "no-referrer"
    return response


@router.get("/denied")
def denied_identity(request: Request):
    cfg = config()
    denied_cookie = request.cookies.get(_cookie_name(DENIED_COOKIE, cfg))
    if not cfg.enabled or cfg.error or not denied_cookie or len(denied_cookie) > 128:
        raise HTTPException(404, "No denied sign-in is available.")
    with _db(cfg) as db:
        row = db.execute(
            "SELECT email,expires_at FROM denied_access WHERE token_hash=?", (_hash(denied_cookie),)
        ).fetchone()
        if not row or row["expires_at"] <= _now():
            if row:
                db.execute("DELETE FROM denied_access WHERE token_hash=?", (_hash(denied_cookie),))
            raise HTTPException(404, "No denied sign-in is available.")
        email = row["email"]
    response = JSONResponse({"email": email})
    response.headers["Cache-Control"] = "no-store"
    response.headers["Referrer-Policy"] = "no-referrer"
    return response


@router.post("/logout")
def logout(request: Request):
    cfg = config()
    raw = request.cookies.get(_cookie_name(SESSION_COOKIE, cfg))
    if raw and cfg.database:
        with _db(cfg) as db:
            db.execute("DELETE FROM sessions WHERE token_hash=?", (_hash(raw),))
    response = Response(status_code=204)
    _clear_cookie(response, cfg, SESSION_COOKIE)
    return response


class GrantRequest(BaseModel):
    kind: str = Field(pattern="^(email|domain)$")
    value: str = Field(min_length=3, max_length=254)
    role: str = Field(default="member", pattern="^(member|admin)$")
    allowance_usd: float | None = Field(default=None, ge=0.01, le=15.0)


class AllowanceRequest(BaseModel):
    allowance_usd: float | None = Field(default=None, ge=0.01, le=15.0)


class GrantUpdate(BaseModel):
    kind: str = Field(pattern="^(email|domain)$")
    value: str = Field(min_length=3, max_length=254)
    role: str = Field(pattern="^(member|admin)$")
    allowance_usd: float | None = Field(default=None, ge=0.01, le=15.0)


class GrantUpdatesRequest(BaseModel):
    updates: list[GrantUpdate] = Field(min_length=1, max_length=250)


def effective_spending_allowance(email: str, default_usd: float) -> float:
    """Resolve the verified identity's current allowance, never a browser claim."""
    cfg = config()
    normalized = _normalize_email(email)
    if not cfg.enabled or cfg.error:
        raise RuntimeError("Cloud access policy is unavailable.")
    with _db(cfg) as db:
        row = db.execute(
            "SELECT allowance_usd FROM grants WHERE kind='email' AND value=? AND active=1",
            (normalized,),
        ).fetchone()
        if row is not None:
            return float(row["allowance_usd"] if row["allowance_usd"] is not None else default_usd)
        row = db.execute(
            "SELECT allowance_usd FROM grants WHERE kind='domain' AND value=? AND active=1",
            (normalized.rsplit("@", 1)[1],),
        ).fetchone()
        return float(
            row["allowance_usd"] if row and row["allowance_usd"] is not None else default_usd
        )


def _configured_default_allowance() -> float | None:
    from decimal import Decimal, InvalidOperation

    try:
        value = Decimal(os.environ["SIGMA_CLOUD_USER_SPEND_CEILING_USD"])
    except (KeyError, InvalidOperation):
        return None
    if not value.is_finite() or value < Decimal("0.01") or value > Decimal("15.00"):
        return None
    return float(value)


def _admin_spending_snapshot(
    subject: str, allowance: float | None
) -> dict[str, float | int | None]:
    from sigma import cloud_research, cloud_workspaces

    workspace = cloud_workspaces.workspace_for_subject(subject)
    return cloud_research.admin_workspace_spending(workspace.workspace_id, allowance)


def _allowance_in_db(db: sqlite3.Connection, email: str, default: float | None) -> float | None:
    explicit = db.execute(
        "SELECT active,allowance_usd FROM grants WHERE kind='email' AND value=?",
        (email,),
    ).fetchone()
    if explicit is not None:
        if not explicit["active"]:
            return None
        if explicit["allowance_usd"] is not None:
            return float(explicit["allowance_usd"])
        return default
    domain = db.execute(
        "SELECT active,allowance_usd FROM grants WHERE kind='domain' AND value=?",
        (email.rsplit("@", 1)[1],),
    ).fetchone()
    if domain is not None:
        if not domain["active"]:
            return None
        if domain["allowance_usd"] is not None:
            return float(domain["allowance_usd"])
    return default


@router.get("/admin/grants")
def list_grants():
    cfg = config()
    with _db(cfg) as db:
        grants = [
            dict(row)
            for row in db.execute(
                "SELECT kind,value,role,active,updated_at,allowance_usd FROM grants ORDER BY kind,value"
            )
        ]
        sessions = db.execute(
            "SELECT token_hash,subject,email,expires_at FROM sessions ORDER BY email,expires_at DESC"
        ).fetchall()
        active: dict[str, dict[str, object]] = {}
        for session in sessions:
            role = _authorization_in_db(db, cfg, session["subject"], session["email"])
            if session["expires_at"] <= _now() or not role:
                db.execute("DELETE FROM sessions WHERE token_hash=?", (session["token_hash"],))
                continue
            current = active.get(session["subject"])
            if current is None:
                active[session["subject"]] = {
                    "email": session["email"],
                    "role": role,
                    "expires_at": session["expires_at"],
                }
        identities = {
            row["subject"]: row["email"]
            for row in db.execute("SELECT subject,email FROM identities")
        }
        # Include authenticated accounts from before the durable identity index
        # migration when their session is still present.
        for session in sessions:
            identities.setdefault(session["subject"], session["email"])
        default = _configured_default_allowance()
        users: list[dict[str, object]] = []
        for subject, email in identities.items():
            role = _authorization_in_db(db, cfg, subject, email)
            current = active.get(subject)
            allowance = _allowance_in_db(db, email, default) if role else None
            users.append(
                {
                    "email": email,
                    "role": role or "member",
                    "authorized": role is not None,
                    "status": "active" if current else "authorized" if role else "revoked",
                    "expires_at": current["expires_at"] if current else None,
                    "allowance_usd": allowance,
                    "subject": subject,
                }
            )
    # Identity is server-derived and admin-only; balances come from the same
    # subject-keyed ledger even when the user's session has been revoked.
    for account in users:
        raw_allowance = account["allowance_usd"]
        allowance = (
            float(raw_allowance)
            if isinstance(raw_allowance, int | float) and not isinstance(raw_allowance, bool)
            else None
        )
        account["spending"] = _admin_spending_snapshot(str(account["subject"]), allowance)
        account.pop("subject", None)
    users.sort(key=lambda account: str(account["email"]))
    for grant in grants:
        grant["effective_allowance_usd"] = (
            grant["allowance_usd"]
            if grant["allowance_usd"] is not None
            else _configured_default_allowance()
        )
    return {"grants": grants, "sessions": users, "bootstrap_admin": cfg.admin_contact_email}


@router.post("/admin/grants")
def add_grant(body: GrantRequest, request: Request):
    cfg = config()
    try:
        value = (
            _normalize_email(body.value) if body.kind == "email" else _normalize_domain(body.value)
        )
        if body.kind == "domain" and body.role == "admin":
            raise ValueError("Domains cannot grant administrator access.")
        if body.allowance_usd is not None and not (0.01 <= body.allowance_usd <= 15.0):
            raise ValueError("Allowance must be between $0.01 and the $15 global ceiling.")
    except ValueError as exc:
        raise HTTPException(422, str(exc)) from None
    actor: Principal = request.state.cloud_principal
    with _db(cfg) as db:
        db.execute(
            "INSERT INTO grants(kind,value,role,active,updated_at,allowance_usd) VALUES(?,?,?,?,?,?) ON CONFLICT(kind,value) DO UPDATE SET role=excluded.role,active=1,updated_at=excluded.updated_at,allowance_usd=COALESCE(excluded.allowance_usd,grants.allowance_usd)",
            (body.kind, value, body.role, 1, _now(), body.allowance_usd),
        )
        db.execute(
            "INSERT INTO audit(actor,action,kind,value,at) VALUES(?,?,?,?,?)",
            (actor.email, "grant", body.kind, value, _now()),
        )
    return {
        "kind": body.kind,
        "value": value,
        "role": body.role,
        "active": True,
        "allowance_usd": body.allowance_usd,
    }


@router.put("/admin/grants/{kind}/{value:path}/allowance")
def update_grant_allowance(kind: str, value: str, body: AllowanceRequest, request: Request):
    cfg = config()
    if kind not in {"email", "domain"}:
        raise HTTPException(422, "Invalid access rule.")
    try:
        normalized = _normalize_email(value) if kind == "email" else _normalize_domain(value)
    except ValueError as exc:
        raise HTTPException(422, str(exc)) from None
    actor: Principal = request.state.cloud_principal
    with _db(cfg) as db:
        row = db.execute(
            "SELECT active FROM grants WHERE kind=? AND value=?", (kind, normalized)
        ).fetchone()
        if row is None:
            raise HTTPException(404, "Authorization entry not found.")
        db.execute(
            "UPDATE grants SET allowance_usd=?,updated_at=? WHERE kind=? AND value=?",
            (body.allowance_usd, _now(), kind, normalized),
        )
        db.execute(
            "INSERT INTO audit(actor,action,kind,value,at) VALUES(?,?,?,?,?)",
            (actor.email, "allowance", kind, normalized, _now()),
        )
    return {"kind": kind, "value": normalized, "allowance_usd": body.allowance_usd}


@router.put("/admin/grants/updates")
def update_grants(body: GrantUpdatesRequest, request: Request):
    """Validate then atomically persist the administrator's changed grant rows."""
    cfg = config()
    normalized_updates: list[tuple[str, str, str, float | None]] = []
    keys: set[tuple[str, str]] = set()
    for update in body.updates:
        try:
            value = (
                _normalize_email(update.value)
                if update.kind == "email"
                else _normalize_domain(update.value)
            )
        except ValueError as exc:
            raise HTTPException(422, str(exc)) from None
        if update.kind == "domain" and update.role == "admin":
            raise HTTPException(422, "Domains cannot grant administrator access.")
        if update.kind == "email" and value == cfg.admin_contact_email and update.role != "admin":
            raise HTTPException(409, "The configured administrator role cannot be changed here.")
        key = (update.kind, value)
        if key in keys:
            raise HTTPException(422, "An authorization entry may be updated only once per save.")
        keys.add(key)
        normalized_updates.append((update.kind, value, update.role, update.allowance_usd))
    actor: Principal = request.state.cloud_principal
    with _db(cfg) as db:
        for kind, value, _role, _allowance in normalized_updates:
            row = db.execute(
                "SELECT active FROM grants WHERE kind=? AND value=?", (kind, value)
            ).fetchone()
            if row is None or not row["active"]:
                raise HTTPException(409, "A changed authorization entry is no longer active.")
        for kind, value, role, allowance in normalized_updates:
            db.execute(
                "UPDATE grants SET role=?,allowance_usd=?,updated_at=? WHERE kind=? AND value=?",
                (role, allowance, _now(), kind, value),
            )
            db.execute(
                "INSERT INTO audit(actor,action,kind,value,at) VALUES(?,?,?,?,?)",
                (actor.email, "update", kind, value, _now()),
            )
    return {"updated": [{"kind": kind, "value": value} for kind, value, _, _ in normalized_updates]}


@router.delete("/admin/grants/{kind}/{value:path}")
def revoke_grant(kind: str, value: str, request: Request):
    cfg = config()
    if kind not in {"email", "domain"}:
        raise HTTPException(422, "Invalid access rule.")
    try:
        normalized = _normalize_email(value) if kind == "email" else _normalize_domain(value)
    except ValueError as exc:
        raise HTTPException(422, str(exc)) from None
    if kind == "email" and normalized == cfg.admin_contact_email:
        raise HTTPException(409, "The configured administrator cannot be revoked here.")
    actor: Principal = request.state.cloud_principal
    with _db(cfg) as db:
        row = db.execute(
            "SELECT role FROM grants WHERE kind=? AND value=?", (kind, normalized)
        ).fetchone()
        role = row["role"] if row else "member"
        db.execute(
            "INSERT INTO grants(kind,value,role,active,updated_at) VALUES(?,?,?,?,?) ON CONFLICT(kind,value) DO UPDATE SET active=0,updated_at=excluded.updated_at",
            (kind, normalized, role, 0, _now()),
        )
        if kind == "email":
            db.execute("DELETE FROM sessions WHERE email=?", (normalized,))
        db.execute(
            "INSERT INTO audit(actor,action,kind,value,at) VALUES(?,?,?,?,?)",
            (actor.email, "revoke", kind, normalized, _now()),
        )
    return {"kind": kind, "value": normalized, "active": False}
