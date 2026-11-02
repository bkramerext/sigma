# SIGMA status

## Issue #458 — legacy Recent Projects pin migration (2026-11-01)

Reproduced the Saved Projects failure against this Mac account's existing
`~/.local/state/sigma` index without changing it. The state directory was owned
by the current user and mode `0700`; `recents.lock` and `recents.json` were
owned by the current user and mode `0600`. The 49,033-byte index was valid
schema v1 with 154 entries, each carrying the historical boolean `pinned`
field (two entries pinned). `_validate` raised `ValueError` because its exact
entry-key check allowed only the newer shape. Commit `4dc4f921` repaired modes
but did not account for this older entry schema, so `d4ab7d0` still returned
the generic unavailable response. A read-only preflight verified both saved
pins against their project IDs and found no family conflict.

Schema-v1 validation now accepts the legacy `pinned` boolean. Migration checks
each pinned entry against the project at its saved path and derives its pin
family from the verified project title before writing schema v2. A missing or
identity-mismatched project rejects migration and leaves the original index
bytes unchanged. The unavailable message no longer falsely diagnoses only
permissions. No repair was applied to the user's actual index during this
assignment; opening Saved Projects with the updated app performs the safe
one-time migration.

Verification: `uv run --locked --no-sync python tests/recents.py` passed,
including legacy pin preservation across a fresh process and rejection without
writing when project identity differs. Real Chrome on the local app rendered a
fixture Saved project and its pin indicator in Projects → Saved; authentication
and the Recent Projects response were deterministic browser fixtures, while
the migration service itself was exercised by the focused test. `./sigma test`
passed, including Ruff, formatting, Pyright (0 diagnostics), frontend typecheck,
and production build. The existing large JavaScript chunk advisory remains; the
optional graph-present Python sandbox scenario was skipped because its image is
not installed. No provider calls were made. Existing real-user Saved list
acceptance after applying the migration remains the user's confirmation gate.
