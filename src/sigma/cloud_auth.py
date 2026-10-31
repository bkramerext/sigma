"""Opt-in Google OIDC access control for hosted SIGMA deployments.

Cloud identity is deliberately separate from the local ChatGPT authorization store.
The SQLite database contains only access rules, OAuth flow state, and hashed sessions.
"""

from __future__ import annotations

import asyncio
import base64
import hashlib
import hmac
import os
import re
import secrets
import smtplib
import sqlite3
import ssl
import time
from contextvars import ContextVar
from dataclasses import dataclass
from email.message import EmailMessage
from pathlib import Path
from threading import Lock
from typing import Any, Literal
from urllib.parse import urlencode, urlsplit
from uuid import uuid4

import httpx
import jwt
from fastapi import APIRouter, HTTPException, Request
from fastapi.responses import JSONResponse, RedirectResponse, Response
from pydantic import BaseModel, ConfigDict, Field

from sigma.config_secrets import SecretConfigurationError, secret_value

router = APIRouter(prefix="/api/cloud-auth", tags=["cloud-auth"])
SESSION_COOKIE = "__Host-sigma_session"
GUEST_COOKIE = "__Host-sigma_guest"
FLOW_COOKIE = "__Host-sigma_oidc_flow"
INVITE_INTENT_COOKIE = "__Host-sigma_invite_intent"
DENIED_COOKIE = "__Host-sigma_denied"
FEEDBACK_RATE_COOKIE = "__Host-sigma_feedback_rate"
SESSION_SECONDS = 8 * 60 * 60
FLOW_SECONDS = 5 * 60
DENIED_SECONDS = 10 * 60
FEEDBACK_RATE_SECONDS = 24 * 60 * 60
GOOGLE_ISSUERS = ("https://accounts.google.com", "accounts.google.com")
DISCOVERY_URL = "https://accounts.google.com/.well-known/openid-configuration"
_EMAIL = re.compile(r"^[^\s@<>]+@[^\s@<>]+\.[^\s@<>]+$")
_DOMAIN = re.compile(r"^(?=.{1,253}$)(?:[a-z0-9](?:[a-z0-9-]{0,61}[a-z0-9])?\.)+[a-z]{2,63}$")
_SCHEMA_LOCK = Lock()
_SCHEMA_READY: set[tuple[str, int, int]] = set()
# Legacy local sponsorship identity; never used to address notification emails.
INVITATION_RECIPIENT = "zetacontinuation@gmail.com"


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


_CURRENT_PRINCIPAL: ContextVar[Principal | None] = ContextVar(
    "sigma_cloud_auth_principal", default=None
)


def current_principal() -> Principal | None:
    """Return the verified account bound to this request or its async worker."""
    return _CURRENT_PRINCIPAL.get()


def local_sponsored_principal(*, require_selected: bool = True) -> Principal | None:
    """Return the eligible local account, optionally requiring its sponsored choice."""
    cfg = config()
    principal = current_principal()
    if not cfg.local or principal is None:
        return None
    try:
        account = _persist_user_state(cfg, principal)
        if not account["sponsorship"]["eligible"]:
            return None
        if require_selected and model_access_for_subject(principal.subject) != "sponsored":
            return None
    except (OSError, RuntimeError, sqlite3.Error):
        return None
    return principal


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
    if (
        not origin
        or not root
        or (not local and (not client_id or not client_secret or not admin_contact))
    ):
        error = "Cloud authentication is enabled but required configuration is missing."
    parsed = urlsplit(origin or "")
    try:
        local_origin = (
            local
            and parsed.scheme == "http"
            and parsed.hostname in {"127.0.0.1", "localhost"}
            and parsed.port is not None
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
            admin_contact = _normalize_email(admin_contact) if admin_contact else None
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
            CREATE TABLE IF NOT EXISTS contact_admin_subject (
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
            CREATE TABLE IF NOT EXISTS user_state (
                subject TEXT PRIMARY KEY,
                email TEXT NOT NULL,
                role TEXT NOT NULL CHECK(role IN ('member','admin')),
                access_active INTEGER NOT NULL CHECK(access_active IN (0,1)),
                workspace_id TEXT,
                sponsorship_eligible INTEGER NOT NULL CHECK(sponsorship_eligible IN (0,1)),
                model_access TEXT NOT NULL CHECK(model_access IN ('personal','sponsored')),
                model_access_selected INTEGER NOT NULL DEFAULT 0
                    CHECK(model_access_selected IN (0,1)),
                model_connection_status TEXT NOT NULL DEFAULT 'checking'
                    CHECK(model_connection_status IN ('checking','connected','unconfigured','disconnected','unauthorized','forbidden','limited','unavailable','invalid_response','reauth_required')),
                model_access_explicit INTEGER NOT NULL DEFAULT 0
                    CHECK(model_access_explicit IN (0,1)),
                invitation_welcome_pending INTEGER NOT NULL DEFAULT 0
                    CHECK(invitation_welcome_pending IN (0,1)),
                updated_at INTEGER NOT NULL
            );
            CREATE TABLE IF NOT EXISTS personal_authorizations (
                subject TEXT PRIMARY KEY,
                authorized_at INTEGER NOT NULL
            );
            CREATE TABLE IF NOT EXISTS flows (
                state_hash TEXT PRIMARY KEY,
                nonce TEXT NOT NULL,
                verifier TEXT NOT NULL,
                expires_at INTEGER NOT NULL,
                return_to TEXT
            );
            CREATE TABLE IF NOT EXISTS denied_access (
                token_hash TEXT PRIMARY KEY,
                email TEXT NOT NULL,
                subject TEXT,
                expires_at INTEGER NOT NULL
            );
            CREATE TABLE IF NOT EXISTS invitation_requests (
                subject TEXT PRIMARY KEY,
                email TEXT NOT NULL,
                requested_at INTEGER NOT NULL,
                status TEXT NOT NULL CHECK(status IN ('pending','sending','notified','reviewed','declined')),
                notification_error TEXT,
                notification_started_at INTEGER,
                request_type TEXT NOT NULL DEFAULT 'invitation' CHECK(request_type IN ('invitation','reload'))
            );
            CREATE TABLE IF NOT EXISTS feedback_requests (
                id TEXT PRIMARY KEY,
                subject TEXT,
                account_email TEXT,
                contact_email TEXT,
                message TEXT NOT NULL,
                submitted_at INTEGER NOT NULL,
                status TEXT NOT NULL CHECK(status IN ('new','reviewed','closed'))
            );
            CREATE TABLE IF NOT EXISTS feedback_rate_limits (
                key_hash TEXT PRIMARY KEY,
                window_started_at INTEGER NOT NULL,
                request_count INTEGER NOT NULL
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
        user_state_columns = {row["name"] for row in db.execute("PRAGMA table_info(user_state)")}
        if "model_access_explicit" not in user_state_columns:
            db.execute(
                "ALTER TABLE user_state ADD COLUMN model_access_explicit INTEGER NOT NULL DEFAULT 0 CHECK(model_access_explicit IN (0,1))"
            )
        if "invitation_welcome_pending" not in user_state_columns:
            db.execute(
                "ALTER TABLE user_state ADD COLUMN invitation_welcome_pending INTEGER NOT NULL DEFAULT 0 CHECK(invitation_welcome_pending IN (0,1))"
            )
        if "model_access_selected" not in user_state_columns:
            db.execute(
                "ALTER TABLE user_state ADD COLUMN model_access_selected INTEGER NOT NULL DEFAULT 0 CHECK(model_access_selected IN (0,1))"
            )
            if "model_access_explicit" in user_state_columns:
                db.execute("UPDATE user_state SET model_access_selected=model_access_explicit")
        denied_columns = {row["name"] for row in db.execute("PRAGMA table_info(denied_access)")}
        if "subject" not in denied_columns:
            db.execute("ALTER TABLE denied_access ADD COLUMN subject TEXT")
        request_columns = {
            row["name"] for row in db.execute("PRAGMA table_info(invitation_requests)")
        }
        if "notification_started_at" not in request_columns:
            db.execute("ALTER TABLE invitation_requests ADD COLUMN notification_started_at INTEGER")
        if "request_type" not in request_columns:
            db.execute(
                "ALTER TABLE invitation_requests ADD COLUMN request_type TEXT NOT NULL DEFAULT 'invitation' CHECK(request_type IN ('invitation','reload'))"
            )
        feedback_columns = {
            row["name"] for row in db.execute("PRAGMA table_info(feedback_requests)")
        }
        if "notification_error" not in feedback_columns:
            db.execute("ALTER TABLE feedback_requests ADD COLUMN notification_error TEXT")
        flow_columns = {row["name"] for row in db.execute("PRAGMA table_info(flows)")}
        if "return_to" not in flow_columns:
            db.execute("ALTER TABLE flows ADD COLUMN return_to TEXT")
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
    # Evaluate the original, subject-bound bootstrap identity first. Changing
    # the administrator contact must not revoke an established administrator.
    bootstrap_email = _bootstrap_admin_email(db, cfg)
    bound = db.execute(
        "SELECT subject FROM bootstrap_subject WHERE email=?", (bootstrap_email,)
    ).fetchone()
    if bound:
        if bound["subject"] == subject and email == bootstrap_email:
            return "admin"
        if email == bootstrap_email:
            return None
    elif bootstrap_email and email == bootstrap_email:
        db.execute("INSERT INTO bootstrap_subject(email,subject) VALUES(?,?)", (email, subject))
        return "admin"
    # A subsequently configured contact is also an administrator. Pin the
    # verified subject so a different Google identity cannot claim that email.
    if cfg.admin_contact_email and email == cfg.admin_contact_email:
        contact = db.execute(
            "SELECT subject FROM contact_admin_subject WHERE email=?", (email,)
        ).fetchone()
        if contact is not None:
            return "admin" if contact["subject"] == subject else None
        try:
            db.execute(
                "INSERT INTO contact_admin_subject(email,subject) VALUES(?,?)",
                (email, subject),
            )
        except sqlite3.IntegrityError:
            return None
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


def _materialize_domain_member(db: sqlite3.Connection, subject: str, email: str) -> bool:
    """Convert an active member-domain policy into an individual member grant.

    An explicit email grant (including a revoked grant) always wins. The caller
    must have verified the Google subject and email; neither comes from a form.
    """
    if not subject or subject.startswith("legacy-denied:"):
        return False
    now = _now()
    # One conditional INSERT is the admission/approval decision. It checks
    # the live domain policy and absence of any explicit (including revoked)
    # email grant under SQLite's writer transaction, so two tabs cannot both
    # approve or race an administrator's revocation between SELECT and INSERT.
    inserted = db.execute(
        "INSERT INTO grants(kind,value,role,active,updated_at,allowance_usd) "
        "SELECT 'email',?,'member',1,?,d.allowance_usd FROM grants AS d "
        "WHERE d.kind='domain' AND d.value=? AND d.role='member' AND d.active=1 "
        "AND NOT EXISTS(SELECT 1 FROM grants AS e WHERE e.kind='email' AND e.value=?) "
        "ON CONFLICT(kind,value) DO NOTHING",
        (email, now, email.rsplit("@", 1)[1], email),
    )
    if inserted.rowcount != 1:
        return False
    db.execute(
        "INSERT INTO identities(subject,email,updated_at) VALUES(?,?,?) "
        "ON CONFLICT(subject) DO UPDATE SET email=excluded.email,updated_at=excluded.updated_at",
        (subject, email, now),
    )
    db.execute(
        "INSERT INTO invitation_requests(subject,email,requested_at,status,request_type) "
        "VALUES(?,?,?,'reviewed','invitation') "
        "ON CONFLICT(subject) DO UPDATE SET email=excluded.email,status='reviewed',"
        "request_type='invitation',notification_started_at=NULL,notification_error=NULL "
        "WHERE invitation_requests.request_type='invitation'",
        (subject, email, now),
    )
    db.execute(
        "INSERT INTO audit(actor,action,kind,value,at) VALUES(?,?,?,?,?)",
        (email, "domain_auto_member", "email", email, now),
    )
    return True


def _sponsorship_eligibility_in_db(
    db: sqlite3.Connection, cfg: Config, subject: str, email: str, role: str | None
) -> int:
    if not sponsored_access_enabled() or role is None:
        return 0
    if not cfg.local:
        return 1
    # Administrator sponsorship follows the verified administrator role,
    # regardless of which grant or bootstrap identity conferred that role.
    if role == "admin":
        return 1
    if _mock_enabled(cfg) and subject.startswith("mock:"):
        return 1
    domain = email.rsplit("@", 1)[-1]
    grant = db.execute(
        "SELECT 1 FROM grants WHERE active=1 AND ((kind='email' AND value=?) OR (kind='domain' AND value=?)) LIMIT 1",
        (email, domain),
    ).fetchone()
    return int(grant is not None)


def _bootstrap_admin_email(db: sqlite3.Connection, cfg: Config) -> str | None:
    """Keep an established bootstrap identity independent from contact metadata."""
    bound = db.execute("SELECT email FROM bootstrap_subject").fetchall()
    if len(bound) == 1:
        return str(bound[0]["email"])
    if bound:
        return None
    return cfg.admin_contact_email


def _configured_bootstrap_admin_email(cfg: Config) -> str | None:
    with _db(cfg) as db:
        return _bootstrap_admin_email(db, cfg)


def sponsored_access_enabled() -> bool:
    """Allow the operator to disable hosted sponsorship without affecting local auth."""
    return os.environ.get("SIGMA_CLOUD_SPONSORED_ENABLED", "true").strip().lower() in {
        "1",
        "true",
        "yes",
    }


def force_sponsored_mode_enabled() -> bool:
    """Opt in to server-enforced sponsorship for every otherwise eligible hosted user."""
    return os.environ.get("SIGMA_CLOUD_FORCE_SPONSORED_MODE", "false").strip().lower() in {
        "1",
        "true",
        "yes",
    }


def _persist_user_state(cfg: Config, principal: Principal) -> dict[str, Any]:
    """Return the persistent account model, refreshing revocable access fields."""
    workspace_id: str | None = None
    # Mock users need distinct workspace identities even though the local
    # development server otherwise follows the local-storage path.
    if not cfg.local or (_mock_enabled(cfg) and principal.subject.startswith("mock:")):
        from sigma.cloud_workspaces import WorkspaceUnavailable, workspace_for_subject

        try:
            workspace_id = workspace_for_subject(principal.subject).workspace_id
        except WorkspaceUnavailable as exc:
            raise RuntimeError("Private workspace is unavailable.") from exc
    with _db(cfg) as db:
        first_member_session = (
            principal.role == "member"
            and db.execute(
                "SELECT 1 FROM user_state WHERE subject=?", (principal.subject,)
            ).fetchone()
            is None
        )
        sponsorship_eligible = _sponsorship_eligibility_in_db(
            db, cfg, principal.subject, principal.email, principal.role
        )
        # Eligible accounts start on sponsorship until they explicitly select
        # personal inference. The choice persists across status refreshes.
        model_access = "sponsored" if sponsorship_eligible else "personal"
        _upsert_user_state(
            db,
            principal.subject,
            principal.email,
            principal.role,
            workspace_id,
            sponsorship_eligible,
            model_access,
        )
        if first_member_session:
            # A local guest session can become a member when an administrator
            # adds the grant. That path has no new OAuth callback to set the
            # one-time welcome flag, so initialize it on first member access.
            db.execute(
                "UPDATE user_state SET invitation_welcome_pending=1 WHERE subject=? AND role='member'",
                (principal.subject,),
            )
        if not sponsored_access_enabled():
            db.execute(
                "UPDATE user_state SET model_access='personal',sponsorship_eligible=0 WHERE subject=?",
                (principal.subject,),
            )
        row = db.execute(
            "SELECT email,role,access_active,workspace_id,sponsorship_eligible,model_access,model_access_selected,model_connection_status,invitation_welcome_pending FROM user_state WHERE subject=?",
            (principal.subject,),
        ).fetchone()
    assert row is not None
    return {
        "identity": {"email": row["email"], "verified": True},
        "access": {"status": "invited" if row["access_active"] else "revoked", "role": row["role"]},
        "workspace": {"available": bool(row["workspace_id"]), "id": row["workspace_id"]},
        "model_access": {"mode": row["model_access"], "connection": row["model_connection_status"]},
        "sponsorship": {
            "eligible": bool(row["sponsorship_eligible"]),
            "forced": bool(
                (
                    (not cfg.local and force_sponsored_mode_enabled())
                    or (cfg.local and _local_sponsored_test_mode(cfg))
                )
                and row["sponsorship_eligible"]
            ),
        },
        "invitation_welcome_pending": (
            bool(row["invitation_welcome_pending"]) and row["role"] != "admin"
        ),
    }


def _upsert_user_state(
    db: sqlite3.Connection,
    subject: str,
    email: str,
    role: str,
    workspace_id: str | None,
    sponsorship_eligible: int,
    model_access: str,
) -> None:
    db.execute(
        """INSERT INTO user_state(subject,email,role,access_active,workspace_id,
               sponsorship_eligible,model_access,model_access_selected,model_connection_status,updated_at)
           VALUES(?,?,?,1,?,?,?,0,'checking',?)
           ON CONFLICT(subject) DO UPDATE SET email=excluded.email,
               role=excluded.role,access_active=1,workspace_id=excluded.workspace_id,
               sponsorship_eligible=excluded.sponsorship_eligible,
               model_access=CASE WHEN excluded.sponsorship_eligible=0 THEN 'personal'
                   WHEN user_state.model_access_selected=0 THEN excluded.model_access
                   ELSE user_state.model_access END,
               model_access_selected=CASE WHEN excluded.sponsorship_eligible=0 THEN 0
                   ELSE user_state.model_access_selected END,
               updated_at=excluded.updated_at""",
        (subject, email, role, workspace_id, sponsorship_eligible, model_access, _now()),
    )


def model_access_for_subject(subject: str) -> str:
    cfg = config()
    if not cfg.enabled or cfg.error:
        raise RuntimeError("Account connection choice is unavailable.")
    with _db(cfg) as db:
        row = db.execute(
            "SELECT model_access,sponsorship_eligible FROM user_state WHERE subject=? AND access_active=1",
            (subject,),
        ).fetchone()
    if row is None:
        raise RuntimeError("Authorized account state is unavailable.")
    if not sponsored_access_enabled():
        return "personal"
    if (
        (not cfg.local and force_sponsored_mode_enabled())
        or (cfg.local and _local_sponsored_test_mode(cfg))
    ) and row["sponsorship_eligible"]:
        return "sponsored"
    return str(row["model_access"])


def set_model_access(subject: str, mode: str) -> None:
    if mode not in {"personal", "sponsored"}:
        raise ValueError("Unsupported model connection choice.")
    if mode == "sponsored" and not sponsored_access_enabled():
        raise PermissionError("Sponsored access is disabled.")
    cfg = config()
    if not cfg.enabled or cfg.error:
        raise RuntimeError("Hosted connection choice is unavailable.")
    with _db(cfg) as db:
        eligibility = db.execute(
            "SELECT sponsorship_eligible,"
            "EXISTS(SELECT 1 FROM personal_authorizations WHERE subject=user_state.subject) "
            "AS personal_authorized FROM user_state WHERE subject=? AND access_active=1",
            (subject,),
        ).fetchone()
        if (
            mode == "personal"
            and (
                (not cfg.local and force_sponsored_mode_enabled())
                or _local_sponsored_test_mode(cfg)
            )
            and sponsored_access_enabled()
            and eligibility is not None
            and eligibility["sponsorship_eligible"]
        ):
            raise PermissionError("Sponsored mode is required for this account.")
        if (
            mode == "personal"
            and eligibility is not None
            and eligibility["sponsorship_eligible"]
            and not eligibility["personal_authorized"]
        ):
            # A mode flag is not evidence of OAuth. This subject-bound record
            # is written only after a successful local OAuth callback with plan
            # scopes, and survives later token/provider failures.
            raise PermissionError(
                "Connect your personal ChatGPT account before selecting personal access."
            )
        changed = db.execute(
            "UPDATE user_state SET model_access=?,model_access_selected=1,model_access_explicit=1,updated_at=? WHERE subject=? AND access_active=1"
            + (" AND sponsorship_eligible=1" if mode == "sponsored" else ""),
            (mode, _now(), subject),
        ).rowcount
        if changed != 1:
            raise PermissionError("This account is not eligible for the selected connection.")


def record_personal_authorization(subject: str) -> None:
    """Record successful plan-permitted OAuth for an eligible local subject."""
    cfg = config()
    if not cfg.enabled or cfg.error or not cfg.local:
        return
    with _db(cfg) as db:
        row = db.execute(
            "SELECT access_active,sponsorship_eligible FROM user_state WHERE subject=?",
            (subject,),
        ).fetchone()
        if row is None or not row["access_active"]:
            raise RuntimeError("Authorized account state is unavailable.")
        if row["sponsorship_eligible"]:
            db.execute(
                "INSERT INTO personal_authorizations(subject,authorized_at) VALUES(?,?) "
                "ON CONFLICT(subject) DO UPDATE SET authorized_at=excluded.authorized_at",
                (subject, _now()),
            )


def persist_model_connection_status(subject: str, status: str) -> None:
    """Persist provider connectivity from a server-side check for this identity."""
    allowed = {
        "checking",
        "connected",
        "unconfigured",
        "disconnected",
        "unauthorized",
        "forbidden",
        "limited",
        "unavailable",
        "invalid_response",
        "reauth_required",
    }
    cfg = config()
    if not cfg.enabled or cfg.error or status not in allowed:
        raise RuntimeError("Model connection state is unavailable.")
    with _db(cfg) as db:
        changed = db.execute(
            "UPDATE user_state SET model_connection_status=?,updated_at=? WHERE subject=? AND access_active=1",
            (status, _now(), subject),
        ).rowcount
        if changed != 1:
            raise RuntimeError("Authorized account state is unavailable.")


def _sync_user_state_in_db(db: sqlite3.Connection, cfg: Config) -> None:
    """Persist current revocable roles/eligibility without touching usage history."""
    for row in db.execute("SELECT subject,email,role FROM user_state").fetchall():
        role = _authorization_in_db(db, cfg, row["subject"], row["email"])
        db.execute(
            "UPDATE user_state SET role=?,access_active=?,sponsorship_eligible=?,model_access=CASE WHEN ? THEN model_access ELSE 'personal' END,updated_at=? WHERE subject=?",
            (
                role or row["role"],
                int(role is not None),
                _sponsorship_eligibility_in_db(db, cfg, row["subject"], row["email"], role),
                int(sponsored_access_enabled()),
                _now(),
                row["subject"],
            ),
        )


def resolve_session(raw: str | None) -> Principal | None:
    cfg = config()
    if (
        cfg.enabled
        and cfg.local
        and not cfg.error
        and not _mock_enabled(cfg)
        and os.environ.get("SIGMA_LOCAL_AUTO_ADMIN") == "true"
        and cfg.admin_contact_email
    ):
        return Principal("local-admin:" + cfg.admin_contact_email, cfg.admin_contact_email, "admin")
    if not cfg.enabled or cfg.error or not raw or len(raw) > 128:
        return None
    with _db(cfg) as db:
        row = db.execute(
            "SELECT subject,email,expires_at FROM sessions WHERE token_hash=?", (_hash(raw),)
        ).fetchone()
        if not row or row["expires_at"] <= _now():
            return None
        role = _authorization_in_db(db, cfg, row["subject"], row["email"])
        if role == "member":
            # A verified guest may still have a live session when the admin
            # adds its domain. Persist the same individual approval as a new
            # Google callback, including allowance and pending-request cleanup.
            _materialize_domain_member(db, row["subject"], row["email"])
        # A verified Google identity remains signed in locally while awaiting
        # an invitation. This is identity only: middleware keeps guest access
        # on the public sample and invitation paths below.
        if not role and cfg.local:
            return Principal(row["subject"], row["email"], "guest")
        if not role:
            db.execute("DELETE FROM sessions WHERE token_hash=?", (_hash(raw),))
            db.execute(
                "UPDATE user_state SET access_active=0,sponsorship_eligible=0,updated_at=? WHERE subject=?",
                (_now(), row["subject"]),
            )
            return None
        db.execute(
            "UPDATE user_state SET role=?,access_active=1,sponsorship_eligible=?,model_access=CASE WHEN ? THEN model_access ELSE 'personal' END,updated_at=? WHERE subject=?",
            (
                role,
                _sponsorship_eligibility_in_db(db, cfg, row["subject"], row["email"], role),
                int(sponsored_access_enabled()),
                _now(),
                row["subject"],
            ),
        )
        return Principal(row["subject"], row["email"], role)


_GUEST_PROJECT_READ_PATHS = {
    "/api/projects/inspect",
    "/api/projects/strategies",
    "/api/projects/events",
    "/api/projects/research-limits",
    "/api/projects/current-understanding",
    "/api/projects/research-sessions",
    "/api/projects/research-executions",
    "/api/projects/papers",
    "/api/projects/papers/preflight",
    "/api/projects/papers/progress",
    "/api/projects/proposals/config",
    "/api/projects/text",
    "/api/projects/recent",
}


def _guest_project_route_allowed(method: str, path: str) -> bool:
    """Explicitly allow sample browsing and project reads inside a guest workspace."""
    if method == "GET" and (path == "/api/projects/samples" or path in _GUEST_PROJECT_READ_PATHS):
        return True
    if method == "POST" and path in {
        "/api/projects/samples/open",
        "/api/projects/open",
        "/api/projects/close",
    }:
        return True
    if method != "GET":
        return False
    parts = path.split("/")
    if len(parts) == 5 and parts[:3] == ["", "api", "projects"]:
        resource, identifier = parts[3:]
        if resource == "research-sessions" and identifier:
            return True
        if resource == "papers" and identifier and identifier != "preflight":
            return True
        if resource == "research-executions" and identifier:
            return True
    if (
        len(parts) == 7
        and parts[:3] == ["", "api", "projects"]
        and parts[3] == "research-executions"
        and parts[4]
        and parts[5] == "artifacts"
        and parts[6]
    ):
        return True
    if (
        len(parts) == 5
        and parts[:3] == ["", "api", "projects"]
        and parts[3] == "papers"
        and parts[4]
    ):
        return True
    return bool(
        len(parts) == 6
        and parts[:3] == ["", "api", "projects"]
        and parts[3] == "papers"
        and parts[4]
        and parts[5] in {"pdf", "txt", "tex"}
    )


async def _guest_project_response(request: Request, call_next, principal: Principal | None = None):
    """Run one allowlisted operation within a temporary guest-only workspace."""
    from sigma import cloud_workspaces

    cfg = config()
    subject = principal.subject if principal is not None else None
    token = request.cookies.get(_cookie_name(GUEST_COOKIE, cfg))
    workspace = cloud_workspaces.guest_workspace(token, subject=subject) if token else None
    if workspace is None:
        token = secrets.token_hex(32)
        workspace = cloud_workspaces.guest_workspace(token, create=True, subject=subject)
    if workspace is None:
        return _guest_secure_response(
            JSONResponse({"error": "Guest workspace is unavailable."}, status_code=503)
        )
    request.state.cloud_guest_workspace = workspace
    # Mark authenticated and anonymous guests so project reads can suppress
    # provider discovery and queued session dispatch.
    guest_principal = principal or Principal("guest-workspace", "guest@localhost.invalid", "guest")
    request.state.cloud_principal = guest_principal
    principal_token = _CURRENT_PRINCIPAL.set(guest_principal)
    try:
        response = await call_next(request)
    finally:
        _CURRENT_PRINCIPAL.reset(principal_token)
    response.set_cookie(
        _cookie_name(GUEST_COOKIE, cfg),
        token,
        **_cookie_options(cfg, GUEST_COOKIE, max_age=SESSION_SECONDS),
    )
    return _guest_secure_response(response)


def _guest_secure_response(response: Response) -> Response:
    """Keep guest-scoped project content out of shared caches and embedders."""
    response.headers["Cache-Control"] = "no-store"
    response.headers["Referrer-Policy"] = "no-referrer"
    response.headers["X-Content-Type-Options"] = "nosniff"
    response.headers["Content-Security-Policy"] = "frame-ancestors 'none'"
    return response


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
    public = public or (request.method == "GET" and path.startswith("/api/ai/auth/callback/"))
    public = public or (path == "/api/cloud-auth/mock/select" and _mock_enabled(cfg))
    public = public or (path == "/api/cloud-auth/invitation-request" and request.method == "POST")
    public = public or (path == "/api/cloud-auth/feedback" and request.method == "POST")
    demo_public = path in {"/api/cloud-demo/", "/api/cloud-demo/report"} and request.method in {
        "GET",
        "HEAD",
    }
    if cfg.error:
        guest_catalog = path == "/api/projects/samples" and request.method == "GET"
        guest_open = path == "/api/projects/samples/open" and request.method == "POST"
        if guest_catalog or guest_open:
            origin = request.headers.get("origin")
            allowed = {cfg.origin, "http://127.0.0.1:5173", "http://localhost:5173"}
            if guest_open and origin not in allowed:
                return JSONResponse({"error": "Request origin is not authorized."}, status_code=403)
            from sigma import cloud_workspaces

            guest_cookie = _cookie_name(GUEST_COOKIE, cfg)
            guest_token = request.cookies.get(guest_cookie)
            workspace = cloud_workspaces.guest_workspace(guest_token) if guest_token else None
            if workspace is None:
                guest_token = secrets.token_hex(32)
                workspace = cloud_workspaces.guest_workspace(guest_token, create=True)
            assert workspace is not None and guest_token is not None
            request.state.cloud_guest_workspace = workspace
            response = await call_next(request)
            response.set_cookie(
                guest_cookie,
                guest_token,
                **_cookie_options(cfg, guest_cookie, max_age=SESSION_SECONDS),
            )
            response.headers["Cache-Control"] = "no-store"
            response.headers["Referrer-Policy"] = "no-referrer"
            response.headers["X-Content-Type-Options"] = "nosniff"
            response.headers["Content-Security-Policy"] = "frame-ancestors 'none'"
            return response
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
        guest_cookie = _cookie_name(GUEST_COOKIE, cfg)
        guest_token = request.cookies.get(guest_cookie)
        guest_workspace = None
        if guest_token:
            from sigma import cloud_workspaces

            guest_workspace = cloud_workspaces.guest_workspace(guest_token)
        create_guest = (path == "/api/projects/samples" and request.method == "GET") or (
            path == "/api/projects/samples/open" and request.method == "POST"
        )
        if path.startswith("/api/projects/") and (guest_workspace is not None or create_guest):
            if not _guest_project_route_allowed(request.method, path):
                return _guest_secure_response(
                    JSONResponse(
                        {"error": "This project operation requires member access."},
                        status_code=403,
                    )
                )
            return await _guest_project_response(request, call_next)
        response = JSONResponse({"error": "Authentication required."}, status_code=401)
        _clear_cookie(response, cfg, SESSION_COOKIE)
        return response
    if principal.role == "guest":
        guest_auth_paths = {
            ("POST", "/api/cloud-auth/logout"),
            ("POST", "/api/cloud-auth/invitation-request"),
            ("POST", "/api/cloud-auth/feedback"),
        }
        if path.startswith("/api/projects/"):
            if not _guest_project_route_allowed(request.method, path):
                return _guest_secure_response(
                    JSONResponse(
                        {"error": "This project operation requires member access."},
                        status_code=403,
                    )
                )
            return await _guest_project_response(request, call_next, principal)
        if path != "/api/cloud-auth/status" and (request.method, path) not in guest_auth_paths:
            return JSONResponse({"error": "Member access requires an invitation."}, status_code=403)
    if path.startswith("/api/cloud-auth/admin/") and principal.role != "admin":
        return JSONResponse({"error": "Administrator access required."}, status_code=403)
    # Local Google identity gates project access but does not replace the
    # separate local ChatGPT account flow. Hosted SIGMA must never proxy a
    # user's personal ChatGPT authorization through the service.
    if (
        path.startswith("/api/ai/")
        and not cfg.local
        and not (
            (request.method == "GET" and path in {"/api/ai/models", "/api/ai/connection"})
            or (request.method == "POST" and path == "/api/ai/mode")
            or (
                principal.role == "admin"
                and request.method == "POST"
                and path == "/api/ai/sponsor-auth/begin"
            )
            or (
                principal.role == "admin"
                and request.method == "GET"
                and path.startswith(("/api/ai/auth/open/", "/api/ai/auth/attempt/"))
            )
            or (
                principal.role == "admin"
                and request.method == "POST"
                and path.startswith("/api/ai/auth/cancel/")
            )
        )
    ):
        return JSONResponse(
            {"error": "AI provider authorization is unavailable in cloud mode."}, status_code=403
        )
    if _mock_enabled(cfg) and principal.subject.startswith("mock:"):
        # Keep normal project CRUD available for UI acceptance testing.
        # The allowlisted mock research route is deterministic and provider-free.
        # Keep live AI/provider and other research execution routes server-denied.
        # Explicitly allow known provider-free project mutations. New routes
        # fail closed until reviewed, instead of relying on name heuristics.
        safe_project_writes = {
            "/api/projects/open",
            "/api/projects/init",
            "/api/projects/close",
            "/api/projects/create",
            "/api/projects/update",
            "/api/projects/research-limits",
            "/api/projects/strategies",
            "/api/projects/strategies/remove",
            "/api/projects/strategies/edit",
            "/api/projects/strategies/enabled",
            "/api/projects/strategies/stage",
            "/api/projects/strategies/reorder",
            "/api/projects/text/source",
            "/api/projects/recent/forget",
            "/api/projects/samples/open",
            "/api/projects/research-sessions/mock",
            "/api/projects/guest-copy",
        }
        project_write = path.startswith("/api/projects/") and request.method not in {
            "GET",
            "HEAD",
            "OPTIONS",
        }
        mock_session_control = (
            request.method == "POST"
            and re.fullmatch(r"/api/projects/research-sessions/[^/]+/control", path) is not None
        )
        if path.startswith(("/api/ai/", "/api/cloud-research/")) or (
            project_write and path not in safe_project_writes and not mock_session_control
        ):
            scenario = _mock_allowance(cfg, principal.subject)
            mode = model_access_for_subject(principal.subject)
            message = (
                "Simulated sponsorship allowance exhausted."
                if mode == "sponsored" and scenario["scenario"] == "exhausted"
                else "Mock walkthrough: research execution is disabled to prevent real provider charges."
            )
            return JSONResponse({"error": message, "simulated": True}, status_code=403)
    request.state.cloud_principal = principal
    principal_token = _CURRENT_PRINCIPAL.set(principal)
    try:
        response = await call_next(request)
    finally:
        _CURRENT_PRINCIPAL.reset(principal_token)
    response.headers["Cache-Control"] = "no-store"
    response.headers["Referrer-Policy"] = "no-referrer"
    response.headers["X-Content-Type-Options"] = "nosniff"
    response.headers["Content-Security-Policy"] = "frame-ancestors 'none'"
    return response


# Mock identities are available only on the loopback-only local auth server.
_MOCK_IDENTITIES = {
    "member-a": ("mock-member-a@localhost.invalid", "member"),
    "member-b": ("mock-member-b@localhost.invalid", "member"),
    "admin": ("mock-admin@localhost.invalid", "admin"),
    "uninvited": ("mock-uninvited@localhost.invalid", None),
}


def _mock_enabled(cfg: Config) -> bool:
    try:
        origin = urlsplit(cfg.origin or "")
        local_origin = (
            origin.scheme == "http"
            and origin.hostname in {"127.0.0.1", "localhost", "::1"}
            and origin.port is not None
            and not origin.username
            and not origin.password
            and not origin.path
            and not origin.query
            and not origin.fragment
        )
    except ValueError:
        local_origin = False
    return (
        cfg.enabled
        and cfg.local
        and not cfg.error
        and os.environ.get("SIGMA_MOCK_AUTH", "").strip() == "1"
        and local_origin
        and os.environ.get("SIGMA_CLOUD_AUTH_LOCAL", "").strip().lower() in {"1", "true", "yes"}
    )


def _local_sponsored_test_mode(cfg: Config) -> bool:
    """Force sponsored UI state only in an explicitly enabled loopback launch."""
    try:
        origin = urlsplit(cfg.origin or "")
        loopback = (
            origin.scheme == "http"
            and origin.hostname in {"127.0.0.1", "localhost", "::1"}
            and origin.port is not None
            and not origin.username
            and not origin.password
            and not origin.path
            and not origin.query
            and not origin.fragment
        )
    except ValueError:
        loopback = False
    return (
        cfg.enabled
        and cfg.local
        and not cfg.error
        and loopback
        and os.environ.get("SIGMA_LOCAL_SPONSORED_TEST_MODE", "").strip().lower()
        in {"1", "true", "yes"}
    )


_MOCK_ALLOWANCES = {"available": 25.0, "low": 1.0, "exhausted": 0.0}


def _mock_allowance(cfg: Config, subject: str) -> dict[str, Any]:
    with _db(cfg) as db:
        db.execute(
            """CREATE TABLE IF NOT EXISTS mock_allowances (
                subject TEXT PRIMARY KEY, scenario TEXT NOT NULL,
                updated_at INTEGER NOT NULL
            )"""
        )
        row = db.execute(
            "SELECT scenario FROM mock_allowances WHERE subject=?", (subject,)
        ).fetchone()
    scenario = row["scenario"] if row else "available"
    return {"scenario": scenario, "remaining_usd": _MOCK_ALLOWANCES[scenario], "simulated": True}


@router.get("/mock/funding")
def mock_funding(request: Request):
    cfg = config()
    if not _mock_enabled(cfg):
        raise HTTPException(404, "Not found")
    principal = resolve_session(request.cookies.get(_cookie_name(SESSION_COOKIE, cfg)))
    if principal is None or not principal.subject.startswith("mock:"):
        raise HTTPException(401, "Choose a mock member first.")
    _persist_user_state(cfg, principal)
    return {
        "mode": model_access_for_subject(principal.subject),
        "allowance": _mock_allowance(cfg, principal.subject),
        "provider": _mock_provider(cfg, principal.subject),
    }


@router.post("/mock/allowance")
def mock_allowance(request: Request, scenario: str):
    cfg = config()
    if not _mock_enabled(cfg):
        raise HTTPException(404, "Not found")
    if request.headers.get("origin") != cfg.origin:
        raise HTTPException(403, "Request origin is not authorized.")
    if request.client is None or request.client.host not in {"127.0.0.1", "::1", "localhost"}:
        raise HTTPException(403, "Mock authentication requires a loopback client.")
    principal = resolve_session(request.cookies.get(_cookie_name(SESSION_COOKIE, cfg)))
    if principal is None or not principal.subject.startswith("mock:"):
        raise HTTPException(401, "Choose a mock member first.")
    if scenario not in _MOCK_ALLOWANCES:
        raise HTTPException(400, "Unknown mock allowance scenario.")
    with _db(cfg) as db:
        db.execute(
            """CREATE TABLE IF NOT EXISTS mock_allowances (
                subject TEXT PRIMARY KEY, scenario TEXT NOT NULL,
                updated_at INTEGER NOT NULL
            )"""
        )
        db.execute(
            """INSERT INTO mock_allowances(subject,scenario,updated_at) VALUES(?,?,?)
            ON CONFLICT(subject) DO UPDATE SET scenario=excluded.scenario,
            updated_at=excluded.updated_at""",
            (principal.subject, scenario, _now()),
        )
    return _mock_allowance(cfg, principal.subject)


_MOCK_PROVIDERS = {"connected", "unavailable", "error"}


def _mock_provider(cfg: Config, subject: str) -> str:
    with _db(cfg) as db:
        db.execute("""CREATE TABLE IF NOT EXISTS mock_providers (
            subject TEXT PRIMARY KEY, scenario TEXT NOT NULL, updated_at INTEGER NOT NULL
        )""")
        row = db.execute(
            "SELECT scenario FROM mock_providers WHERE subject=?", (subject,)
        ).fetchone()
    return str(row["scenario"]) if row else "connected"


@router.post("/mock/provider")
def mock_provider(request: Request, scenario: str):
    cfg = config()
    if not _mock_enabled(cfg):
        raise HTTPException(404, "Not found")
    if (
        request.headers.get("origin") != cfg.origin
        or request.client is None
        or request.client.host not in {"127.0.0.1", "::1", "localhost"}
    ):
        raise HTTPException(403, "Mock scenario changes require a same-origin loopback client.")
    principal = resolve_session(request.cookies.get(_cookie_name(SESSION_COOKIE, cfg)))
    if principal is None or not principal.subject.startswith("mock:"):
        raise HTTPException(401, "Choose a mock member first.")
    if scenario not in _MOCK_PROVIDERS:
        raise HTTPException(400, "Unknown mock provider scenario.")
    with _db(cfg) as db:
        db.execute("""CREATE TABLE IF NOT EXISTS mock_providers (
            subject TEXT PRIMARY KEY, scenario TEXT NOT NULL, updated_at INTEGER NOT NULL
        )""")
        db.execute(
            """INSERT INTO mock_providers(subject,scenario,updated_at) VALUES(?,?,?)
            ON CONFLICT(subject) DO UPDATE SET scenario=excluded.scenario,updated_at=excluded.updated_at""",
            (principal.subject, scenario, _now()),
        )
    return {"provider": scenario, "simulated": True}


@router.post("/mock/model-access")
def mock_model_access(request: Request, mode: str):
    """Change simulated funding without touching a real provider."""
    cfg = config()
    if not _mock_enabled(cfg):
        raise HTTPException(404, "Not found")
    if request.headers.get("origin") != cfg.origin:
        raise HTTPException(403, "Request origin is not authorized.")
    if request.client is None or request.client.host not in {"127.0.0.1", "::1", "localhost"}:
        raise HTTPException(403, "Mock authentication requires a loopback client.")
    principal = resolve_session(request.cookies.get(_cookie_name(SESSION_COOKIE, cfg)))
    if principal is None or not principal.subject.startswith("mock:"):
        raise HTTPException(401, "Choose a mock member first.")
    if mode not in {"personal", "sponsored"}:
        raise HTTPException(400, "Unknown mock funding mode.")
    _persist_user_state(cfg, principal)
    try:
        set_model_access(principal.subject, mode)
    except PermissionError as exc:
        raise HTTPException(403, str(exc)) from exc
    return {"mode": mode, "simulated": True}


@router.post("/mock/select")
def mock_select(request: Request, identity: str):
    cfg = config()
    if not _mock_enabled(cfg):
        raise HTTPException(404, "Not found")
    if identity not in (*_MOCK_IDENTITIES, "guest"):
        raise HTTPException(400, "Unknown mock identity")
    # Do not allow a cross-origin page to switch the active local identity.
    if request.headers.get("origin") != cfg.origin:
        raise HTTPException(403, "Request origin is not authorized.")
    # Never accept mock identity changes through a remote-facing listener.
    if request.client is None or request.client.host not in {"127.0.0.1", "::1", "localhost"}:
        raise HTTPException(403, "Mock authentication requires a loopback client.")
    old = request.cookies.get(_cookie_name(SESSION_COOKIE, cfg))
    previous_denied = request.cookies.get(_cookie_name(DENIED_COOKIE, cfg))
    with _db(cfg) as db:
        if old:
            db.execute("DELETE FROM sessions WHERE token_hash=?", (_hash(old),))
        if previous_denied:
            db.execute("DELETE FROM denied_access WHERE token_hash=?", (_hash(previous_denied),))
        response = Response(status_code=204)
        _clear_cookie(response, cfg, SESSION_COOKIE)
        _clear_cookie(response, cfg, DENIED_COOKIE)
        if identity != "guest":
            email, role = _MOCK_IDENTITIES[identity]
            if role is None:
                denied_token = secrets.token_urlsafe(32)
                db.execute(
                    "INSERT INTO denied_access(token_hash,email,subject,expires_at) VALUES(?,?,?,?)",
                    (_hash(denied_token), email, "mock:" + identity, _now() + DENIED_SECONDS),
                )
                response.set_cookie(
                    _cookie_name(DENIED_COOKIE, cfg),
                    denied_token,
                    **_cookie_options(cfg, DENIED_COOKIE, max_age=DENIED_SECONDS),
                )
            else:
                subject = "mock:" + identity
                raw = secrets.token_urlsafe(32)
                db.execute(
                    "INSERT INTO identities(subject,email,updated_at) VALUES(?,?,?) "
                    "ON CONFLICT(subject) DO UPDATE SET email=excluded.email,updated_at=excluded.updated_at",
                    (subject, email, _now()),
                )
                db.execute(
                    "INSERT INTO grants(kind,value,role,active,updated_at) VALUES('email',?,?,1,?) "
                    "ON CONFLICT(kind,value) DO UPDATE SET role=excluded.role,active=1,updated_at=excluded.updated_at",
                    (email, role, _now()),
                )
                _upsert_user_state(db, subject, email, role, None, 0, "personal")
                if _local_sponsored_test_mode(cfg):
                    eligible = _sponsorship_eligibility_in_db(db, cfg, subject, email, role)
                    if eligible:
                        db.execute(
                            "UPDATE user_state SET sponsorship_eligible=1,model_access='sponsored' WHERE subject=? AND access_active=1",
                            (subject,),
                        )
                    db.execute(
                        """CREATE TABLE IF NOT EXISTS mock_providers (
                            subject TEXT PRIMARY KEY, scenario TEXT NOT NULL,
                            updated_at INTEGER NOT NULL
                        )"""
                    )
                    db.execute(
                        """INSERT INTO mock_providers(subject,scenario,updated_at)
                        VALUES(?, 'connected', ?) ON CONFLICT(subject) DO UPDATE SET
                        scenario='connected',updated_at=excluded.updated_at""",
                        (subject, _now()),
                    )
                db.execute(
                    "INSERT INTO sessions(token_hash,subject,email,expires_at) VALUES(?,?,?,?)",
                    (_hash(raw), subject, email, _now() + SESSION_SECONDS),
                )
                response.set_cookie(
                    _cookie_name(SESSION_COOKIE, cfg),
                    raw,
                    **_cookie_options(cfg, SESSION_COOKIE, max_age=SESSION_SECONDS),
                )
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
    account = None
    if principal is not None:
        try:
            if principal.role == "guest":
                with _db(cfg) as db:
                    invitation = db.execute(
                        "SELECT status FROM invitation_requests WHERE subject=?",
                        (principal.subject,),
                    ).fetchone()
                account = {
                    "identity": {"email": principal.email, "verified": True},
                    "access": {"status": "uninvited", "role": "guest"},
                    "workspace": {"available": False, "id": None},
                    "model_access": {"mode": "personal", "connection": "disconnected"},
                    "sponsorship": {"eligible": False, "forced": False},
                    "invitation_welcome_pending": False,
                    "invitation_status": invitation["status"] if invitation else None,
                }
            else:
                account = _persist_user_state(cfg, principal)
        except (sqlite3.Error, OSError, RuntimeError):
            return {
                "enabled": cfg.enabled,
                "ready": False,
                "local_setup_missing": local_setup_missing,
                "authenticated": False,
                "user": None,
                "account": None,
                "admin_contact_email": None,
                "target": "local" if cfg.local else "hosted" if cfg.enabled else "local",
            }
    return {
        "enabled": cfg.enabled,
        "mock_auth": _mock_enabled(cfg),
        "mock_identity": bool(
            principal and _mock_enabled(cfg) and principal.subject.startswith("mock:")
        ),
        "sponsored_test_mode": _local_sponsored_test_mode(cfg),
        "ready": not cfg.error if cfg.enabled else True,
        # Names only: the setup panel can explain missing local prerequisites
        # without ever returning OAuth secrets or the configured admin email.
        "local_setup_missing": local_setup_missing,
        "authenticated": principal is not None,
        "user": principal.public() if principal else None,
        "account": account,
        "admin_contact_email": cfg.admin_contact_email if cfg.enabled and not cfg.error else None,
        "target": "local" if cfg.local else "hosted" if cfg.enabled else "local",
    }


@router.get("/local-sponsored-allowance")
def local_sponsored_allowance(request: Request):
    """Return the signed-in sponsored account's real local ledger balance."""
    cfg = config()
    if not cfg.local or cfg.error:
        raise HTTPException(404, "Not found")
    if request.client is None or request.client.host not in {"127.0.0.1", "::1", "localhost"}:
        raise HTTPException(403, "Local sponsored preview requires a loopback client.")
    principal = resolve_session(request.cookies.get(_cookie_name(SESSION_COOKIE, cfg)))
    if principal is None:
        raise HTTPException(401, "Sign in with an eligible account to view its allowance.")
    account = _persist_user_state(cfg, principal)
    if not account["sponsorship"]["eligible"]:
        raise HTTPException(403, "This account has no sponsored allowance configured.")
    from sigma import cloud_research

    try:
        budget = cloud_research.snapshot()
    except cloud_research.CloudResearchUnavailable as exc:
        raise HTTPException(503, "Sponsored allowance ledger is unavailable.") from exc
    return {**budget, "local_preview": True, "simulated": False}


def _safe_login_return_to(value: str) -> str | None:
    """Allow only a project-page continuation; reject external/open redirects."""
    from urllib.parse import parse_qs, urlencode, urlsplit

    if not value or len(value) > 4096:
        return None
    parsed = urlsplit(value)
    if parsed.scheme or parsed.netloc or parsed.path != "/project" or parsed.fragment:
        return None
    try:
        query = parse_qs(parsed.query, keep_blank_values=True, max_num_fields=8)
    except ValueError:
        return None
    paths = query.get("path", [])
    if len(paths) != 1 or not paths[0] or len(paths[0]) > 2048:
        return None
    resume_play = query.get("resume_play", [])
    return "/project?" + urlencode(
        {"path": paths[0], **({"resume_play": "1"} if resume_play == ["1"] else {})}
    )


@router.get("/login")
def login(
    request: Request,
    invite: bool = False,
    return_to: str = "",
):
    cfg = config()
    if not cfg.enabled:
        return RedirectResponse("/")
    if cfg.error or not cfg.origin:
        raise HTTPException(503, "Cloud authentication is not ready.")
    oauth_missing = [
        key
        for key, value in (
            ("GOOGLE_OIDC_CLIENT_ID", cfg.client_id),
            ("GOOGLE_OIDC_CLIENT_SECRET", cfg.client_secret),
        )
        if not value
    ]
    if oauth_missing:
        raise HTTPException(
            503,
            "Google sign-in is not configured. Set "
            + " and ".join(oauth_missing)
            + " and restart SIGMA.",
        )
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
            "INSERT INTO flows(state_hash,nonce,verifier,expires_at,return_to) VALUES(?,?,?,?,?)",
            (
                _hash(state),
                nonce,
                verifier,
                _now() + FLOW_SECONDS,
                _safe_login_return_to(return_to),
            ),
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
    if invite:
        response.set_cookie(
            _cookie_name(INVITE_INTENT_COOKIE, cfg),
            state,
            **_cookie_options(cfg, INVITE_INTENT_COOKIE, max_age=FLOW_SECONDS),
        )
    else:
        _clear_cookie(response, cfg, INVITE_INTENT_COOKIE)
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
            "SELECT nonce,verifier,expires_at,return_to FROM flows WHERE state_hash=?",
            (_hash(state),),
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
    invite_intent = request.cookies.get(_cookie_name(INVITE_INTENT_COOKIE, cfg)) == state
    role = _authorization(cfg, subject, email)
    if not role:
        if cfg.local:
            # Local Google identity is independent of invitation membership.
            # role=guest keeps all member and research routes denied below.
            raw = secrets.token_urlsafe(32)
            with _db(cfg) as db:
                if session_cookie:
                    db.execute("DELETE FROM sessions WHERE token_hash=?", (_hash(session_cookie),))
                db.execute(
                    "INSERT INTO identities(subject,email,updated_at) VALUES(?,?,?) "
                    "ON CONFLICT(subject) DO UPDATE SET email=excluded.email,updated_at=excluded.updated_at",
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
            _clear_cookie(response, cfg, INVITE_INTENT_COOKIE)
            _clear_cookie(response, cfg, DENIED_COOKIE)
            response.headers["Cache-Control"] = "no-store"
            response.headers["Referrer-Policy"] = "no-referrer"
            return response
        denied_token = secrets.token_urlsafe(32)
        with _db(cfg) as db:
            if session_cookie:
                db.execute("DELETE FROM sessions WHERE token_hash=?", (_hash(session_cookie),))
            db.execute("DELETE FROM denied_access WHERE expires_at<=?", (_now(),))
            if denied_cookie:
                db.execute("DELETE FROM denied_access WHERE token_hash=?", (_hash(denied_cookie),))
            db.execute(
                "INSERT INTO denied_access(token_hash,email,subject,expires_at) VALUES(?,?,?,?)",
                (_hash(denied_token), email, subject, _now() + DENIED_SECONDS),
            )
        response = RedirectResponse(
            "/?access=denied&invite=1" if invite_intent else "/?access=denied", status_code=303
        )
        _clear_cookie(response, cfg, FLOW_COOKIE)
        _clear_cookie(response, cfg, INVITE_INTENT_COOKIE)
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
    workspace_id = None
    authenticated_workspace = None
    if not cfg.local:
        from sigma.cloud_workspaces import WorkspaceUnavailable, workspace_for_subject

        try:
            authenticated_workspace = workspace_for_subject(subject)
            workspace_id = authenticated_workspace.workspace_id
        except WorkspaceUnavailable as exc:
            raise HTTPException(503, "Private workspace is unavailable.") from exc
    return_to = flow["return_to"] or "/"
    guest_token = request.cookies.get(_cookie_name(GUEST_COOKIE, cfg))
    if return_to.startswith("/project?") and guest_token:
        from urllib.parse import parse_qs, urlencode, urlsplit

        from sigma import cloud_workspaces, projects

        guest_workspace = cloud_workspaces.guest_workspace(guest_token, subject=subject)
        if guest_workspace is not None:
            return_query = parse_qs(
                urlsplit(return_to).query, keep_blank_values=True, max_num_fields=8
            )
            requested_paths = return_query.get("path", [])
            try:
                if len(requested_paths) == 1:
                    requested = Path(requested_paths[0]).expanduser().resolve()
                    if requested.is_relative_to(guest_workspace.path):
                        copied_path = projects.copy_project_between_workspaces(
                            requested_paths[0], guest_workspace, authenticated_workspace
                        )
                        return_to = "/project?" + urlencode(
                            {
                                "path": copied_path,
                                **(
                                    {"resume_play": "1"}
                                    if return_query.get("resume_play") == ["1"]
                                    else {}
                                ),
                            }
                        )
            except (projects.ProjectError, cloud_workspaces.WorkspaceUnavailable):
                # Complete sign-in without exposing a guest path to the member
                # workspace. The original guest copy remains intact until expiry.
                return_to = "/?project_resume=unavailable"
    raw = secrets.token_urlsafe(32)
    auto_domain_member = False
    with _db(cfg) as db:
        auto_domain_member = role == "member" and _materialize_domain_member(db, subject, email)
        existing_account = db.execute(
            "SELECT 1 FROM user_state WHERE subject=?", (subject,)
        ).fetchone()
        bootstrap_email = _bootstrap_admin_email(db, cfg)
        bootstrap_identity = email == bootstrap_email or email == cfg.admin_contact_email
        domain = email.rsplit("@", 1)[1]
        explicit_invite = db.execute(
            "SELECT 1 FROM grants WHERE active=1 AND ((kind='email' AND value=?) OR (kind='domain' AND value=?)) LIMIT 1",
            (email, domain),
        ).fetchone()
        newly_invited = (
            existing_account is None
            and role != "admin"
            and not bootstrap_identity
            and explicit_invite is not None
        )
        db.execute(
            "INSERT INTO identities(subject,email,updated_at) VALUES(?,?,?) ON CONFLICT(subject) DO UPDATE SET email=excluded.email,updated_at=excluded.updated_at",
            (subject, email, _now()),
        )
        # Keep verified identity, current authorization, private workspace,
        # and funding eligibility as separate server-owned account attributes.
        # Usage itself remains in the durable cloud-research ledger.
        _upsert_user_state(
            db,
            subject,
            email,
            role,
            workspace_id,
            _sponsorship_eligibility_in_db(db, cfg, subject, email, role),
            "sponsored"
            if not cfg.local and sponsored_access_enabled() and force_sponsored_mode_enabled()
            else "personal",
        )
        if role == "admin":
            db.execute(
                "UPDATE user_state SET invitation_welcome_pending=0 WHERE subject=?",
                (subject,),
            )
        elif newly_invited:
            db.execute(
                "UPDATE user_state SET invitation_welcome_pending=1 WHERE subject=?",
                (subject,),
            )
        db.execute(
            "INSERT INTO sessions(token_hash,subject,email,expires_at) VALUES(?,?,?,?)",
            (_hash(raw), subject, email, _now() + SESSION_SECONDS),
        )
    if auto_domain_member:
        try:
            await asyncio.to_thread(
                _deliver_invitation, email, _now(), request_type="auto_approved"
            )
        except RuntimeError:
            # Membership is durable and never rolled back by mail delivery.
            with _db(cfg) as db:
                db.execute(
                    "UPDATE invitation_requests SET notification_error=? WHERE subject=?",
                    ("delivery failed", subject),
                )
    response = RedirectResponse(return_to, status_code=303)
    response.set_cookie(
        _cookie_name(SESSION_COOKIE, cfg),
        raw,
        **_cookie_options(cfg, SESSION_COOKIE, max_age=SESSION_SECONDS),
    )
    _clear_cookie(response, cfg, FLOW_COOKIE)
    _clear_cookie(response, cfg, INVITE_INTENT_COOKIE)
    _clear_cookie(response, cfg, DENIED_COOKIE)
    response.headers["Cache-Control"] = "no-store"
    response.headers["Referrer-Policy"] = "no-referrer"
    return response


@router.post("/welcome")
def dismiss_invitation_welcome(request: Request):
    """Persist the authenticated user's one-time invitation welcome dismissal."""
    cfg = config()
    principal = getattr(request.state, "cloud_principal", None)
    if not isinstance(principal, Principal):
        raise HTTPException(401, "Authentication required.")
    if request.headers.get("origin") != cfg.origin:
        raise HTTPException(403, "Request origin is not authorized.")
    if not cfg.enabled or cfg.error:
        raise HTTPException(503, "Invitation welcome state is unavailable.")
    with _db(cfg) as db:
        changed = db.execute(
            "UPDATE user_state SET invitation_welcome_pending=0,updated_at=? WHERE subject=? AND access_active=1",
            (_now(), principal.subject),
        ).rowcount
    if changed != 1:
        raise HTTPException(403, "Invitation welcome state is unavailable.")
    return {"dismissed": True}


@router.get("/denied")
def denied_identity(request: Request):
    cfg = config()
    denied_cookie = request.cookies.get(_cookie_name(DENIED_COOKIE, cfg))
    if not cfg.enabled or cfg.error or not denied_cookie or len(denied_cookie) > 128:
        raise HTTPException(404, "No denied sign-in is available.")
    with _db(cfg) as db:
        row = db.execute(
            "SELECT subject,email,expires_at FROM denied_access WHERE token_hash=?",
            (_hash(denied_cookie),),
        ).fetchone()
        if not row or row["expires_at"] <= _now():
            if row:
                db.execute("DELETE FROM denied_access WHERE token_hash=?", (_hash(denied_cookie),))
            raise HTTPException(404, "No denied sign-in is available.")
        # A previously denied Google subject may become authorized after the
        # administrator email or grants change. Do not keep offering an
        # invitation when this verified identity is now eligible to sign in.
        authorized = (
            _authorization_in_db(db, cfg, row["subject"], row["email"]) if row["subject"] else None
        )
        invitation = db.execute(
            "SELECT status FROM invitation_requests WHERE subject=?", (row["subject"],)
        ).fetchone()
    if authorized is not None:
        response = JSONResponse({"identity_available": False, "retry_signin": True})
        response.headers["Cache-Control"] = "no-store"
        response.headers["Referrer-Policy"] = "no-referrer"
        return response
    response = JSONResponse(
        {
            "identity_available": True,
            "invitation_status": invitation["status"] if invitation else None,
        }
    )
    response.headers["Cache-Control"] = "no-store"
    response.headers["Referrer-Policy"] = "no-referrer"
    return response


def _notification_admin_recipients(cfg: Config) -> list[str]:
    """Derive active administrators from verified identities and admin grants.

    Explicit active administrator email grants are themselves operator
    authorization; they can receive mail before their first Google sign-in.
    Never trust an applicant-supplied address.
    """
    with _db(cfg) as db:
        verified = db.execute("SELECT subject,email FROM identities").fetchall()
        recipients = {
            str(row["email"])
            for row in verified
            if _authorization_in_db(db, cfg, row["subject"], row["email"]) == "admin"
        }
        # An admin grant is an explicit administrator-approved mailbox even
        # before its first Google sign-in; excluding it would silently miss
        # a newly added administrator's notifications.
        recipients.update(
            str(row["value"])
            for row in db.execute(
                "SELECT value FROM grants WHERE kind='email' AND role='admin' AND active=1"
            )
        )
        return sorted(recipients)


def _deliver_admin_notice(subject: str, body: str) -> None:
    """One privacy-preserving multi-recipient notice through existing Gmail/SMTP."""
    cfg = config()
    recipients = _notification_admin_recipients(cfg)
    if not recipients:
        raise RuntimeError("No verified SIGMA administrator notification recipient is available.")
    if os.environ.get("SIGMA_INVITATION_GMAIL_TOKEN_FILE", "").strip():
        from sigma.gmail_delivery import send_admin_notification

        send_admin_notification(subject, body, recipients=recipients)
        return

    raw_username = os.environ.get("SIGMA_INVITATION_SMTP_USERNAME", "").strip()
    try:
        username = _normalize_email(raw_username)
    except ValueError as exc:
        raise RuntimeError("Invitation delivery is not configured.") from exc
    try:
        password = secret_value("SIGMA_INVITATION_SMTP_PASSWORD")
    except SecretConfigurationError as exc:
        raise RuntimeError("Invitation delivery is not configured.") from exc
    if not password:
        raise RuntimeError("Invitation delivery is not configured.")
    host = os.environ.get("SIGMA_INVITATION_SMTP_HOST", "smtp.gmail.com").strip()
    try:
        port = int(os.environ.get("SIGMA_INVITATION_SMTP_PORT", "587"))
        if not host or not 1 <= port <= 65535:
            raise ValueError
        message = EmailMessage()
        message["Subject"] = subject
        message["From"] = username
        message["To"] = username
        message["Bcc"] = ", ".join(recipients)
        message.set_content(body)
        with smtplib.SMTP(host, port, timeout=10) as client:
            client.ehlo()
            client.starttls(context=ssl.create_default_context())
            client.ehlo()
            client.login(username, password)
            refused = client.send_message(message, from_addr=username, to_addrs=recipients)
            if isinstance(refused, dict) and refused:
                raise RuntimeError("Some administrator notifications could not be delivered.")
    except (OSError, ValueError, smtplib.SMTPException) as exc:
        raise RuntimeError("Administrator notification could not be delivered.") from exc


def _deliver_invitation(email: str, requested_at: int, *, request_type: str = "invitation") -> None:
    """Notify all verified administrators, preserving existing request semantics."""
    title = (
        "SIGMA sponsorship reload request"
        if request_type == "reload"
        else "SIGMA member automatically approved"
        if request_type == "auto_approved"
        else "SIGMA invitation request"
    )
    introduction = (
        "A signed-in SIGMA member requested a sponsored allowance reload.\n\n"
        if request_type == "reload"
        else "Automatically approved via member domain. No administrator action is required.\n\n"
        if request_type == "auto_approved"
        else "A verified Google account requested SIGMA access.\n\n"
    )
    _deliver_admin_notice(
        title,
        introduction + f"Account: {email}\nRequested at (UTC epoch): {requested_at}\n",
    )


def _deliver_feedback(
    feedback_id: str,
    message: str,
    submitted_at: int,
    *,
    account_email: str | None,
    contact_email: str | None,
) -> None:
    """Notification content is plain text; contact is explicitly unverified."""
    _deliver_admin_notice(
        "New SIGMA feedback",
        (
            f"Feedback ID: {feedback_id}\n"
            f"Submitted at (UTC epoch): {submitted_at}\n"
            f"Verified account: {account_email or 'None (guest)'}\n"
            f"Provided contact (unverified): {contact_email or 'None'}\n\n"
            f"Message:\n{message}\n"
        ),
    )


class InvitationRequestBody(BaseModel):
    request_type: Literal["invitation", "reload"] = "invitation"


@router.post("/invitation-request")
def request_invitation(
    request: Request, response: Response, body: InvitationRequestBody | None = None
):
    """Record an invitation or an eligible signed-in member's reload request."""
    body = body or InvitationRequestBody()
    cfg = config()
    if not cfg.enabled or cfg.error or not cfg.database:
        raise HTTPException(503, "Invitation requests are temporarily unavailable.")
    denied_cookie: str | None = None
    authenticated: Principal | None = None
    if body.request_type == "reload":
        raw_session = request.cookies.get(_cookie_name(SESSION_COOKIE, cfg))
        principal = resolve_session(raw_session)
        if principal is None:
            raise HTTPException(401, "Sign in with Google before requesting a reload.")
        if principal.role == "admin":
            raise HTTPException(
                403, "Administrators have no individual sponsorship allowance to reload."
            )
        with _db(cfg) as db:
            eligible = db.execute(
                "SELECT 1 FROM user_state WHERE subject=? AND access_active=1 AND sponsorship_eligible=1",
                (principal.subject,),
            ).fetchone()
        if not sponsored_access_enabled() or eligible is None:
            raise HTTPException(403, "This account is not eligible for sponsored reload requests.")
        identity = {"email": principal.email, "subject": principal.subject}
    elif (
        authenticated := resolve_session(request.cookies.get(_cookie_name(SESSION_COOKIE, cfg)))
    ) is not None and authenticated.role in {"guest", "member"}:
        identity = {"email": authenticated.email, "subject": authenticated.subject}
    else:
        denied_cookie = request.cookies.get(_cookie_name(DENIED_COOKIE, cfg))
        if not denied_cookie or len(denied_cookie) > 128:
            raise HTTPException(401, "Sign in with Google before requesting an invitation.")
        with _db(cfg) as db:
            identity = db.execute(
                "SELECT email,subject,expires_at FROM denied_access WHERE token_hash=?",
                (_hash(denied_cookie),),
            ).fetchone()
        if not identity or identity["expires_at"] <= _now():
            raise HTTPException(401, "Your verified sign-in expired. Sign in again to continue.")
    now = _now()
    if body.request_type == "invitation" and identity["subject"]:
        with _db(cfg) as db:
            auto_approved = _materialize_domain_member(db, identity["subject"], identity["email"])
            # A second tab may race after the first has committed the
            # individual grant. Do not reopen a reviewed request as pending.
            prior = db.execute(
                "SELECT 1 FROM grants AS g "
                "JOIN invitation_requests AS i ON i.email=g.value AND i.subject=? "
                "WHERE g.kind='email' AND g.value=? AND g.role='member' AND g.active=1 "
                "AND i.status='reviewed' AND EXISTS("
                "SELECT 1 FROM audit WHERE action='domain_auto_member' AND kind='email' "
                "AND value=g.value) LIMIT 1",
                (identity["subject"], identity["email"]),
            ).fetchone()
            duplicate_approval = not auto_approved and prior is not None
            if auto_approved:
                _sync_user_state_in_db(db, cfg)
            token = (
                secrets.token_urlsafe(32)
                if denied_cookie and (auto_approved or duplicate_approval)
                else None
            )
            if token:
                db.execute(
                    "INSERT INTO sessions(token_hash,subject,email,expires_at) VALUES(?,?,?,?)",
                    (_hash(token), identity["subject"], identity["email"], now + SESSION_SECONDS),
                )
        if auto_approved or duplicate_approval:
            if token:
                response.set_cookie(
                    _cookie_name(SESSION_COOKIE, cfg),
                    token,
                    **_cookie_options(cfg, SESSION_COOKIE, max_age=SESSION_SECONDS),
                )
                _clear_cookie(response, cfg, DENIED_COOKIE)
            if auto_approved:
                try:
                    if not (_mock_enabled(cfg) and str(identity["subject"]).startswith("mock:")):
                        _deliver_invitation(identity["email"], now, request_type="auto_approved")
                except RuntimeError:
                    with _db(cfg) as db:
                        db.execute(
                            "UPDATE invitation_requests SET notification_error=? WHERE subject=?",
                            ("delivery failed", identity["subject"]),
                        )
            return {"status": "approved", "duplicate": duplicate_approval}
        if _authorization(cfg, identity["subject"], identity["email"]):
            raise HTTPException(409, "This Google account is already authorized. Sign in again.")
    if (
        body.request_type == "invitation"
        and authenticated is not None
        and authenticated.role == "member"
    ):
        raise HTTPException(409, "This Google account is already authorized.")
    with _db(cfg) as db:
        # Bind to the verified Google subject without relying on browser-supplied identity.
        subject = identity["subject"]
        if subject is None and body.request_type == "invitation":
            assert denied_cookie is not None
            subject = f"legacy-denied:{_hash(denied_cookie)}"
        existing = db.execute(
            "SELECT status,requested_at,notification_started_at,request_type FROM invitation_requests WHERE subject=?",
            (subject,),
        ).fetchone()
        if (
            body.request_type == "reload"
            and existing
            and existing["request_type"] == "reload"
            and existing["status"] in {"pending", "sending", "notified"}
        ):
            return {"status": existing["status"], "duplicate": True}
        if existing and existing["status"] != "pending":
            if existing["status"] == "sending":
                if (
                    existing["notification_started_at"]
                    and existing["notification_started_at"] > now - 60
                ):
                    raise HTTPException(
                        409, "Your request is already being sent. Please wait and retry."
                    )
                db.execute(
                    "UPDATE invitation_requests SET status='pending',notification_started_at=NULL WHERE subject=?",
                    (subject,),
                )
                existing = {"status": "pending", "requested_at": existing["requested_at"]}
            elif body.request_type == "reload":
                db.execute(
                    "UPDATE invitation_requests SET email=?,requested_at=?,status='pending',request_type='reload',notification_started_at=NULL,notification_error=NULL WHERE subject=?",
                    (identity["email"], now, subject),
                )
                existing = None
            elif existing["status"] in {"reviewed", "declined"}:
                # A closed request must not permanently block a user who has
                # since lost access. Active members are rejected above; a
                # guest may submit a fresh request for administrator review.
                existing = None
            else:
                return {"status": existing["status"], "duplicate": True}
        if existing and body.request_type == "reload":
            db.execute(
                "UPDATE invitation_requests SET request_type='reload',email=? WHERE subject=?",
                (identity["email"], subject),
            )
        recent = db.execute(
            "SELECT COUNT(*) AS n FROM invitation_requests WHERE email=? AND requested_at>?",
            (identity["email"], now - 86400),
        ).fetchone()["n"]
        if not existing and recent >= 3:
            raise HTTPException(429, "Too many requests. Please try again later.")
        requested_at = int(existing["requested_at"]) if existing else now
        if not existing:
            db.execute(
                "INSERT INTO invitation_requests(subject,email,requested_at,status,request_type) VALUES(?,?,?,'pending',?) "
                "ON CONFLICT(subject) DO UPDATE SET email=excluded.email,requested_at=excluded.requested_at,status='pending',request_type=excluded.request_type,notification_started_at=NULL,notification_error=NULL",
                (subject, identity["email"], requested_at, body.request_type),
            )
        db.execute(
            "UPDATE invitation_requests SET status='sending',notification_started_at=?,notification_error=NULL WHERE subject=?",
            (now, subject),
        )
    try:
        if not (_mock_enabled(cfg) and str(identity["subject"]).startswith("mock:")):
            _deliver_invitation(identity["email"], requested_at, request_type=body.request_type)
    except RuntimeError:
        with _db(cfg) as db:
            db.execute(
                "UPDATE invitation_requests SET status='pending',notification_started_at=NULL,notification_error=? "
                "WHERE subject=? AND status='sending' AND request_type=?",
                ("delivery failed", subject, body.request_type),
            )
        # The durable request is already recorded and visible to administrators.
        # Notification delivery is best-effort; returning an error here would
        # tell the user to retry an action that has already succeeded.
        return {"status": "pending", "duplicate": bool(existing)}
    with _db(cfg) as db:
        db.execute(
            "UPDATE invitation_requests SET status='notified',notification_started_at=NULL,notification_error=NULL "
            "WHERE subject=? AND status='sending' AND request_type=?",
            (subject, body.request_type),
        )
    return {"status": "notified", "duplicate": bool(existing)}


class InvitationStatusUpdate(BaseModel):
    status: str = Field(pattern="^(reviewed|declined)$")


@router.get("/admin/invitation-requests")
def list_invitation_requests():
    cfg = config()
    with _db(cfg) as db:
        rows = db.execute(
            "SELECT subject,email,requested_at,status,request_type FROM invitation_requests "
            "WHERE status NOT IN ('reviewed','declined') ORDER BY requested_at DESC LIMIT 500"
        ).fetchall()
        grants = db.execute(
            "SELECT kind,value FROM grants WHERE active=1 AND kind IN ('email','domain')"
        ).fetchall()
    active_emails = set()
    active_domains = set()
    for grant in grants:
        try:
            normalized = (
                _normalize_email(grant["value"])
                if grant["kind"] == "email"
                else _normalize_domain(grant["value"])
            )
        except ValueError:
            continue
        (active_emails if grant["kind"] == "email" else active_domains).add(normalized)
    requests = []
    for row in rows:
        email = str(row["email"]).strip().casefold()
        domain = email.rsplit("@", 1)[-1].removesuffix(".")
        if row["request_type"] != "reload" and (email in active_emails or domain in active_domains):
            continue
        requests.append(dict(row))
    return {"requests": requests}


@router.put("/admin/invitation-requests/{subject:path}")
def update_invitation_request(subject: str, body: InvitationStatusUpdate, request: Request):
    cfg = config()
    actor: Principal = request.state.cloud_principal
    if not subject or len(subject) > 255:
        raise HTTPException(404, "Invitation request not found.")
    with _db(cfg) as db:
        result = db.execute(
            "UPDATE invitation_requests SET status=?,notification_error=NULL WHERE subject=?",
            (body.status, subject),
        )
        if not result.rowcount:
            raise HTTPException(404, "Invitation request not found.")
        db.execute(
            "INSERT INTO audit(actor,action,kind,value,at) VALUES(?,?,?,?,?)",
            (actor.email, "invitation_" + body.status, "invitation", subject, _now()),
        )
    return {"status": body.status}


class FeedbackSubmission(BaseModel):
    model_config = ConfigDict(extra="forbid")

    message: str = Field(min_length=1, max_length=4000)
    contact_email: str | None = Field(default=None, max_length=254)


class FeedbackStatusUpdate(BaseModel):
    status: str = Field(pattern="^(reviewed|closed)$")


@router.post("/feedback")
def submit_feedback(body: FeedbackSubmission, request: Request, response: Response):
    """Persist visitor feedback first, then notify administrators best-effort."""
    cfg = config()
    if not cfg.enabled or cfg.error or not cfg.database:
        raise HTTPException(503, "Feedback is temporarily unavailable.")
    message = body.message.strip()
    if not 10 <= len(message) <= 4000 or any(
        ord(character) < 32 and character not in "\n\r\t" for character in message
    ):
        raise HTTPException(422, "Feedback must be 10 to 4,000 characters.")
    contact_email = None
    if body.contact_email is not None:
        try:
            contact_email = _normalize_email(body.contact_email)
        except ValueError as exc:
            raise HTTPException(422, str(exc)) from None

    raw_session = request.cookies.get(_cookie_name(SESSION_COOKIE, cfg))
    try:
        principal = resolve_session(raw_session)
    except (sqlite3.Error, OSError, RuntimeError) as exc:
        raise HTTPException(503, "Feedback is temporarily unavailable.") from exc

    rate_cookie = request.cookies.get(_cookie_name(FEEDBACK_RATE_COOKIE, cfg))
    set_rate_cookie = not rate_cookie or not re.fullmatch(r"[A-Za-z0-9_-]{40,64}", rate_cookie)
    if set_rate_cookie:
        rate_cookie = secrets.token_urlsafe(32)
    assert rate_cookie is not None
    rate_identity = f"subject:{principal.subject}" if principal else f"visitor:{rate_cookie}"
    rate_key = _hash("feedback-rate:" + rate_identity)
    now = _now()
    with _db(cfg) as db:
        db.execute(
            "DELETE FROM feedback_rate_limits WHERE window_started_at<=?",
            (now - FEEDBACK_RATE_SECONDS,),
        )
        limit = db.execute(
            "SELECT window_started_at,request_count FROM feedback_rate_limits WHERE key_hash=?",
            (rate_key,),
        ).fetchone()
        if (
            limit
            and limit["request_count"] >= 5
            and limit["window_started_at"] > now - FEEDBACK_RATE_SECONDS
        ):
            raise HTTPException(429, "Too many feedback submissions. Please try again later.")
        if limit and limit["window_started_at"] > now - FEEDBACK_RATE_SECONDS:
            db.execute(
                "UPDATE feedback_rate_limits SET request_count=request_count+1 WHERE key_hash=?",
                (rate_key,),
            )
        else:
            db.execute(
                "INSERT INTO feedback_rate_limits(key_hash,window_started_at,request_count) VALUES(?,?,1) ON CONFLICT(key_hash) DO UPDATE SET window_started_at=excluded.window_started_at,request_count=1",
                (rate_key, now),
            )
        feedback_id = uuid4().hex
        db.execute(
            "INSERT INTO feedback_requests(id,subject,account_email,contact_email,message,submitted_at,status) VALUES(?,?,?,?,?,?,'new')",
            (
                feedback_id,
                principal.subject if principal else None,
                principal.email if principal else None,
                contact_email,
                message,
                now,
            ),
        )
    if set_rate_cookie:
        response.set_cookie(
            _cookie_name(FEEDBACK_RATE_COOKIE, cfg),
            rate_cookie,
            **_cookie_options(cfg, FEEDBACK_RATE_COOKIE, max_age=FEEDBACK_RATE_SECONDS),
        )
    response.headers["Cache-Control"] = "no-store"
    try:
        _deliver_feedback(
            feedback_id,
            message,
            now,
            account_email=principal.email if principal else None,
            contact_email=contact_email,
        )
    except RuntimeError:
        # Feedback is durable even if Gmail/SMTP is missing or temporarily
        # unavailable. The admin inbox still contains the message.
        with _db(cfg) as db:
            db.execute(
                "UPDATE feedback_requests SET notification_error=? WHERE id=?",
                ("delivery failed", feedback_id),
            )
    return {"status": "received", "id": feedback_id}


@router.get("/admin/feedback")
def list_feedback():
    cfg = config()
    with _db(cfg) as db:
        rows = db.execute(
            "SELECT id,account_email,contact_email,message,submitted_at,status FROM feedback_requests ORDER BY submitted_at DESC LIMIT 500"
        ).fetchall()
    return {"feedback": [dict(row) for row in rows]}


@router.put("/admin/feedback/{feedback_id}")
def update_feedback(feedback_id: str, body: FeedbackStatusUpdate, request: Request):
    cfg = config()
    if not re.fullmatch(r"[0-9a-f]{32}", feedback_id):
        raise HTTPException(404, "Feedback not found.")
    actor: Principal = request.state.cloud_principal
    with _db(cfg) as db:
        result = db.execute(
            "UPDATE feedback_requests SET status=? WHERE id=?",
            (body.status, feedback_id),
        )
        if not result.rowcount:
            raise HTTPException(404, "Feedback not found.")
        db.execute(
            "INSERT INTO audit(actor,action,kind,value,at) VALUES(?,?,?,?,?)",
            (actor.email, "feedback_" + body.status, "feedback", feedback_id, _now()),
        )
    return {"status": body.status}


@router.delete("/admin/feedback/{feedback_id}")
def remove_feedback(feedback_id: str, request: Request):
    cfg = config()
    if not re.fullmatch(r"[0-9a-f]{32}", feedback_id):
        raise HTTPException(404, "Feedback not found.")
    actor: Principal = request.state.cloud_principal
    with _db(cfg) as db:
        result = db.execute("DELETE FROM feedback_requests WHERE id=?", (feedback_id,))
        if not result.rowcount:
            raise HTTPException(404, "Feedback not found.")
        db.execute(
            "INSERT INTO audit(actor,action,kind,value,at) VALUES(?,?,?,?,?)",
            (actor.email, "feedback_removed", "feedback", feedback_id, _now()),
        )
    return {"removed": True}


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
        bootstrap_admin = _bootstrap_admin_email(db, cfg)
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
            allowance = _allowance_in_db(db, email, default) if role and role != "admin" else None
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
            None
            if grant["role"] == "admin"
            else grant["allowance_usd"]
            if grant["allowance_usd"] is not None
            else _configured_default_allowance()
        )
    return {"grants": grants, "sessions": users, "bootstrap_admin": bootstrap_admin}


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
        _sync_user_state_in_db(db, cfg)
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


@router.post("/admin/grants/reload/{value:path}")
def reload_member_allowance(value: str, request: Request):
    """Restore one authorized member's allowance without erasing spend history."""
    cfg = config()
    try:
        normalized = _normalize_email(value)
    except ValueError as exc:
        raise HTTPException(422, str(exc)) from None
    actor: Principal = request.state.cloud_principal
    with _db(cfg) as db:
        grant = db.execute(
            "SELECT role,active FROM grants WHERE kind='email' AND value=?", (normalized,)
        ).fetchone()
        if not grant or not grant["active"] or grant["role"] != "member":
            raise HTTPException(409, "Reload requires an active member email authorization.")
        identities = db.execute(
            "SELECT subject FROM identities WHERE email=? ORDER BY subject", (normalized,)
        ).fetchall()
        if len(identities) != 1:
            raise HTTPException(
                409,
                "Reload requires exactly one signed-in account for this email authorization.",
            )
        subject = str(identities[0]["subject"])
        role = _authorization_in_db(db, cfg, subject, normalized)
        if role != "member":
            raise HTTPException(409, "This account is not an active member.")
        allowance = _allowance_in_db(db, normalized, _configured_default_allowance())
        if allowance is None:
            raise HTTPException(409, "No sponsored allowance is configured for this account.")
    from sigma import cloud_research, cloud_workspaces

    try:
        workspace = cloud_workspaces.workspace_for_subject(subject)
        reset_at = cloud_research.admin_reload_workspace_allowance(
            workspace.workspace_id, actor.email
        )
    except cloud_research.CloudResearchUnavailable:
        raise HTTPException(503, "The sponsored allowance could not be reloaded safely.") from None
    except cloud_workspaces.WorkspaceUnavailable:
        raise HTTPException(503, "The sponsored allowance could not be reloaded safely.") from None
    with _db(cfg) as db:
        db.execute(
            "INSERT INTO audit(actor,action,kind,value,at) VALUES(?,?,?,?,?)",
            (actor.email, "reload", "email", normalized, _now()),
        )
    return {"email": normalized, "allowance_usd": allowance, "reset_at": reset_at}


@router.put("/admin/grants/updates")
def update_grants(body: GrantUpdatesRequest, request: Request):
    """Validate then atomically persist the administrator's changed grant rows."""
    cfg = config()
    bootstrap_admin = _configured_bootstrap_admin_email(cfg)
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
        if update.kind == "email" and value == bootstrap_admin and update.role != "admin":
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
        _sync_user_state_in_db(db, cfg)
    return {"updated": [{"kind": kind, "value": value} for kind, value, _, _ in normalized_updates]}


@router.delete("/admin/grants/{kind}/{value:path}")
def revoke_grant(kind: str, value: str, request: Request):
    cfg = config()
    bootstrap_admin = _configured_bootstrap_admin_email(cfg)
    if kind not in {"email", "domain"}:
        raise HTTPException(422, "Invalid access rule.")
    try:
        normalized = _normalize_email(value) if kind == "email" else _normalize_domain(value)
    except ValueError as exc:
        raise HTTPException(422, str(exc)) from None
    if kind == "email" and normalized == bootstrap_admin:
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
        _sync_user_state_in_db(db, cfg)
    return {"kind": kind, "value": normalized, "active": False}
