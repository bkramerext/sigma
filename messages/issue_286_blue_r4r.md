# Blue handoff — Issue #286 Maximum Concurrent Sessions

- Issue: [#286](https://github.com/bkramerext/sigma/issues/286)
- Branch: `blue/issue-286-concurrent-sessions`
- Base: `main` at `e2f4f6e89ea4a83f9e01b74aa63ae3f1b267a910`
- Implementation commit: `f3fea3a7a6222ea2a03f23c8cd18c0d59d0bc39a`
- PR: [#287](https://github.com/bkramerext/sigma/pull/287), open against `main`
- PR head at creation: `f3fea3a7a6222ea2a03f23c8cd18c0d59d0bc39a`

## Implementation

Added `max_concurrent_sessions` to the shared research limits contract with a
hard-coded default of 1 and positive-integer validation without an application
maximum. The Limits tab accepts decimal text and sends it losslessly, including
values beyond JavaScript's safe integer range. Existing projects that predate
the field inherit 1; limits remain in project bundle members and per-session
records retain the admission-time snapshot.

Local admission and resume count queued/running sessions while holding the
existing per-project interprocess lock. The count is per project; it no longer
rejects an unrelated project's session due to another local worker. Hosted
admission also reserves the project slot in the SQLite `BEGIN IMMEDIATE`
transaction. Paused/stopped/terminal and interrupted records free capacity.
Stale local work is recovered before admission. A queued hosted record missing
its durable reservation is safely paused because no call was dispatched;
running calls retain the existing uncertain-completion safeguards. Capacity
errors explain how to proceed.

## Verification

- `uv run python tests/research_sessions.py` — passed, including concurrent
  callers racing for two slots, rejection of the third, and reuse after stop.
- `uv run python tests/project_settings.py` — passed; default, project
  isolation, invalid values, numeric and arbitrary-length decimal values.
- `uv run python tests/project_bundle.py` — passed; exact JSON bundle round-trip
  with an 80 digit setting.
- `uv run python tests/cloud_research.py` — passed; hosted atomic reservation,
  pause/terminal/interrupted release states, restart recovery, workspace
  isolation.
- `uv run python tests/sage_execution.py` and `tests/cloud_auth.py` — passed
  after updating former global-exclusion assumptions for per-project scope.
- Full `./sigma test` — passed every step, including Ruff check/format,
  Pyright (0 diagnostics), frontend typecheck, and production build.
- Standalone `npm --prefix frontend run build` — passed. Vite retained the
  existing advisory about the 519 kB main JavaScript chunk.
- Real Chrome `browser_checks/issue286_concurrent_sessions.py` — passed at
  desktop and narrow mobile viewport. It checked default 1, zero rejection,
  saving/reopening an 80 digit value, and responsive dialog placement.

No real or paid provider calls, live OAuth, cloud deployment, or production
changes occurred. Browser acceptance used an isolated local fake provider and a
temporary copy of a shipped sample; the actual project export is preserved at
`docs/evaluations/issue_286/exports/concurrent-session-limits.sigma.json`.

## Review notes

Cloud provider worker concurrency and queue limits remain independently
administrator controlled. The project setting controls admitted research
sessions for the project and does not change provider request or billing limits.
