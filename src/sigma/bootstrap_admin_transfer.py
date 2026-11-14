"""One-time, subject-bound transfer of SIGMA's built-in administrator.

Run as the production backend UID with writers stopped and a verified backup.
Projects, workspaces, research, credentials and accounting are never moved.
"""

from __future__ import annotations

import argparse
import sqlite3
import sys
import time
from pathlib import Path


class TransferRefused(RuntimeError):
    """A transfer prerequisite was not met."""


def _email(raw: str) -> str:
    value = raw.strip().casefold()
    if not value or value.count("@") != 1 or " " in value or len(value) > 254:
        raise TransferRefused("Provide exact source and target email addresses.")
    return value


def _grant_role(db: sqlite3.Connection, email: str) -> str | None:
    """Effective role without the retiring bootstrap privilege."""
    grant = db.execute(
        "SELECT role FROM grants WHERE kind='email' AND value=? AND active=1", (email,)
    ).fetchone()
    if grant:
        return str(grant["role"])
    grant = db.execute(
        "SELECT role FROM grants WHERE kind='domain' AND value=? AND active=1",
        (email.rsplit("@", 1)[-1],),
    ).fetchone()
    return str(grant["role"]) if grant else None


def transfer(
    database: Path, *, from_email: str, to_email: str, apply: bool = False
) -> dict[str, str | bool]:
    source, target = _email(from_email), _email(to_email)
    if source == target:
        raise TransferRefused("Source and target must be distinct Google accounts.")
    if database.is_symlink() or not database.is_file():
        raise TransferRefused("Persistent authentication database does not exist.")
    db = sqlite3.connect(database.as_uri() + "?mode=rw", uri=True, isolation_level=None, timeout=5)
    db.row_factory = sqlite3.Row
    try:
        db.execute("BEGIN IMMEDIATE" if apply else "BEGIN")
        if db.execute("PRAGMA quick_check").fetchone()[0] != "ok":
            raise TransferRefused("Authentication database integrity check failed.")
        original = db.execute("SELECT email,subject FROM bootstrap_subject").fetchall()
        if len(original) != 1:
            raise TransferRefused("Exactly one persisted bootstrap administrator is required.")
        destination = db.execute(
            "SELECT subject FROM identities WHERE email=?", (target,)
        ).fetchall()
        if len(destination) != 1:
            raise TransferRefused("Target has no unique, previously verified Google identity.")
        dest_subject = destination[0]["subject"]
        active = db.execute(
            "SELECT role,access_active FROM user_state WHERE subject=? AND email=?",
            (dest_subject, target),
        ).fetchone()
        if active is None or active["role"] != "admin" or active["access_active"] != 1:
            raise TransferRefused("Target must already have active administrator authorization.")
        contact = db.execute(
            "SELECT subject FROM contact_admin_subject WHERE email=?", (target,)
        ).fetchone()
        if contact is not None and contact["subject"] != dest_subject:
            raise TransferRefused("Contact administrator is bound to another Google subject.")
        existing = original[0]
        if existing["email"] == target and existing["subject"] == dest_subject:
            db.rollback()
            return {"status": "already_transferred", "changed": False, "old_role": "unknown"}
        if existing["email"] != source or existing["subject"] == dest_subject:
            raise TransferRefused("Persisted bootstrap binding differs from expected source.")
        source_subject = existing["subject"]
        old_identity = db.execute(
            "SELECT email FROM identities WHERE subject=?", (source_subject,)
        ).fetchone()
        if old_identity is None or old_identity["email"] != source:
            raise TransferRefused("Bootstrap subject does not match verified Google identity.")
        prior_role = _grant_role(db, source)
        if apply:
            changed = db.execute(
                "UPDATE bootstrap_subject SET email=?,subject=? WHERE email=? AND subject=?",
                (target, dest_subject, source, source_subject),
            )
            if changed.rowcount != 1:
                raise TransferRefused("Bootstrap binding changed during transfer.")
            if contact is None:
                db.execute(
                    "INSERT INTO contact_admin_subject(email,subject) VALUES(?,?)",
                    (target, dest_subject),
                )
            # Existing browser sessions must not preserve the old bootstrap authority.
            db.execute("DELETE FROM sessions WHERE subject=?", (source_subject,))
            db.execute(
                "UPDATE user_state SET role=?,access_active=?,sponsorship_eligible=?,"
                "updated_at=? WHERE subject=?",
                (
                    prior_role or "member",
                    int(prior_role is not None),
                    int(prior_role is not None),
                    int(time.time()),
                    source_subject,
                ),
            )
            db.execute(
                "INSERT INTO audit(actor,action,kind,value,at) VALUES(?,?,?,?,?)",
                (
                    "bootstrap-admin-transfer",
                    "bootstrap_admin_transferred",
                    "email",
                    target,
                    int(time.time()),
                ),
            )
            db.commit()
        else:
            db.rollback()
        return {
            "status": "transferred" if apply else "dry_run_ok",
            "changed": apply,
            "old_role": prior_role or "unauthorized",
        }
    except Exception:
        db.rollback()
        raise
    finally:
        db.close()


def main() -> int:
    parser = argparse.ArgumentParser(description="Guarded bootstrap administrator transfer")
    parser.add_argument("--from-email", required=True)
    parser.add_argument("--to-email", required=True)
    parser.add_argument("--apply", action="store_true")
    parser.add_argument("--backup-verified", action="store_true")
    args = parser.parse_args()
    try:
        from sigma import cloud_auth

        cfg = cloud_auth.config()
        target = _email(args.to_email)
        if (
            not cfg.enabled
            or cfg.local
            or cfg.error
            or cfg.database is None
            or (cfg.admin_contact_email or "").strip().casefold() != target
        ):
            raise TransferRefused("Hosted configuration must name the target as its admin contact.")
        if args.apply and not args.backup_verified:
            raise TransferRefused("A verified production backup is required for --apply.")
        result = transfer(
            cfg.database,
            from_email=args.from_email,
            to_email=args.to_email,
            apply=args.apply,
        )
        print(
            f"Bootstrap transfer: {result['status']}; "
            f"prior identity independent role: {result['old_role']}."
        )
        return 0
    except (TransferRefused, sqlite3.Error, OSError) as exc:
        print(f"Transfer refused: {exc}", file=sys.stderr)
        return 2


if __name__ == "__main__":
    raise SystemExit(main())
