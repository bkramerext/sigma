"""Provider-free regression for explicit persistent bootstrap admin transfer."""

import sqlite3
from pathlib import Path
from tempfile import TemporaryDirectory

import test_environment as _test_environment  # noqa: F401

from sigma.bootstrap_admin_transfer import TransferRefused, transfer

OLD = "old@example.test"
NEW = "new@example.test"


def rows(path: Path, statement: str):
    with sqlite3.connect(path) as db:
        return db.execute(statement).fetchall()


def create(path: Path) -> None:
    with sqlite3.connect(path) as db:
        db.executescript(
            """
            CREATE TABLE bootstrap_subject (email TEXT PRIMARY KEY,subject TEXT UNIQUE);
            CREATE TABLE contact_admin_subject (email TEXT PRIMARY KEY,subject TEXT UNIQUE);
            CREATE TABLE identities (subject TEXT PRIMARY KEY,email TEXT,updated_at INTEGER);
            CREATE TABLE user_state (subject TEXT PRIMARY KEY,email TEXT,role TEXT,access_active INTEGER,
                sponsorship_eligible INTEGER,updated_at INTEGER,workspace_id TEXT);
            CREATE TABLE grants (kind TEXT,value TEXT,role TEXT,active INTEGER);
            CREATE TABLE sessions (token_hash TEXT PRIMARY KEY,subject TEXT,email TEXT,expires_at INTEGER);
            CREATE TABLE audit (id INTEGER PRIMARY KEY,actor TEXT,action TEXT,kind TEXT,value TEXT,at INTEGER);
            CREATE TABLE saved_projects (subject TEXT,data TEXT);
            INSERT INTO bootstrap_subject VALUES ('old@example.test','google-old');
            INSERT INTO identities VALUES ('google-old','old@example.test',1),
                ('google-new','new@example.test',2);
            INSERT INTO user_state VALUES ('google-old','old@example.test','admin',1,1,1,'workspace-old'),
                ('google-new','new@example.test','admin',1,1,2,'workspace-new');
            INSERT INTO sessions VALUES ('old-session','google-old','old@example.test',9999999999),
                ('new-session','google-new','new@example.test',9999999999);
            INSERT INTO saved_projects VALUES ('google-old','saved old work'),
                ('google-new','saved new work');
            """
        )


def main() -> None:
    with TemporaryDirectory() as folder:
        path = Path(folder) / "access.sqlite3"
        create(path)
        before = rows(path, "SELECT * FROM bootstrap_subject")
        plan = transfer(path, from_email=OLD, to_email=NEW)
        assert plan["status"] == "dry_run_ok" and not plan["changed"]
        assert rows(path, "SELECT * FROM bootstrap_subject") == before
        for source, target in ((OLD, "unknown@example.test"), ("wrong@example.test", NEW)):
            try:
                transfer(path, from_email=source, to_email=target, apply=True)
            except TransferRefused:
                pass
            else:
                raise AssertionError("Unverified or wrong identity was accepted")
        with sqlite3.connect(path) as db:
            db.execute("INSERT INTO contact_admin_subject VALUES (?,?)", (NEW, "imposter"))
        try:
            transfer(path, from_email=OLD, to_email=NEW, apply=True)
        except TransferRefused:
            pass
        else:
            raise AssertionError("Conflicting subject was accepted")
        with sqlite3.connect(path) as db:
            db.execute("DELETE FROM contact_admin_subject")
            db.execute("INSERT INTO grants VALUES ('email',?,?,1)", (OLD, "member"))
        result = transfer(path, from_email=OLD, to_email=NEW, apply=True)
        assert result == {"status": "transferred", "changed": True, "old_role": "member"}
        assert rows(path, "SELECT email,subject FROM bootstrap_subject") == [(NEW, "google-new")]
        assert rows(path, "SELECT email,subject FROM contact_admin_subject") == [(NEW, "google-new")]
        assert rows(path, "SELECT token_hash FROM sessions") == [("new-session",)]
        assert rows(path, "SELECT role,access_active FROM user_state WHERE subject='google-old'") == [("member", 1)]
        assert rows(path, "SELECT subject,data FROM saved_projects ORDER BY subject") == [
            ("google-new", "saved new work"), ("google-old", "saved old work")
        ]
        assert rows(path, "SELECT action,value FROM audit") == [
            ("bootstrap_admin_transferred", NEW)
        ]
        again = transfer(path, from_email=OLD, to_email=NEW, apply=True)
        assert again["status"] == "already_transferred" and not again["changed"]
        assert rows(path, "SELECT COUNT(*) FROM audit") == [(1,)]
    print("PASS guarded bootstrap admin transfer dry-run, mismatch, isolation and idempotency")


if __name__ == "__main__":
    main()
