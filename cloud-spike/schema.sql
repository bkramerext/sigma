-- Disposable spike schema. Never applied to local SIGMA research packages.
CREATE TABLE budgets (
  scope TEXT PRIMARY KEY,
  ceiling INTEGER NOT NULL CHECK (ceiling >= 0),
  spent INTEGER NOT NULL DEFAULT 0 CHECK (spent >= 0 AND spent <= ceiling),
  concurrency INTEGER NOT NULL CHECK (concurrency > 0)
);
CREATE TABLE jobs (
  id TEXT PRIMARY KEY,
  owner TEXT NOT NULL REFERENCES budgets(scope),
  request_key TEXT NOT NULL,
  state TEXT NOT NULL DEFAULT 'queued'
    CHECK (state IN ('queued','dispatched','succeeded','uncertain','stopped')),
  revision INTEGER NOT NULL DEFAULT 0,
  lease TEXT,
  expires INTEGER,
  artifact_key TEXT,
  digest TEXT,
  UNIQUE(owner, request_key)
);
CREATE TABLE projects (
  id TEXT PRIMARY KEY,
  owner TEXT NOT NULL REFERENCES budgets(scope),
  revision INTEGER NOT NULL DEFAULT 0,
  document TEXT NOT NULL
);
-- A single conditional UPDATE is the dispatch boundary. Trigger effects and
-- state transition share its transaction; do not check then charge in JS.
CREATE TRIGGER charge_dispatch BEFORE UPDATE OF state ON jobs
WHEN OLD.state = 'queued' AND NEW.state = 'dispatched'
BEGIN
  SELECT CASE WHEN NOT EXISTS (
    SELECT 1 FROM budgets WHERE scope = 'global' AND spent < ceiling
    AND (SELECT COUNT(*) FROM jobs WHERE state = 'dispatched') < concurrency
  ) THEN RAISE(ABORT, 'global limit') END;
  SELECT CASE WHEN NOT EXISTS (
    SELECT 1 FROM budgets WHERE scope = NEW.owner AND spent < ceiling
    AND (SELECT COUNT(*) FROM jobs WHERE state = 'dispatched' AND owner = NEW.owner)
      < concurrency
  ) THEN RAISE(ABORT, 'user limit') END;
  UPDATE budgets SET spent = spent + 1 WHERE scope IN ('global', NEW.owner);
END;
