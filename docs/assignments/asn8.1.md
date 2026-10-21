# A8.1: One-command SIGMA UI launch, automatic local configuration and safe instance replacement

**Status:** Ready for Codex; targeted fix after A8, independent of A9. Implement rather than merely document. Read `docs/HUMAN-AI-INTERACTION.md`, current `src/sigma/ui.py`, `sigma`, `src/sigma/openai_connection.py`, `scenarios/tooling.py`, and current `docs/STATUS.md`. No new artwork or Home/Strategies redesign.

## User requirement

A normal local user should run:

```sh
cd ~/sigma
./sigma ui
```

and SIGMA should **load its own configuration** and start successfully without making the user manually `source .env`, run `lsof`, find PIDs, `kill` old SIGMA services, or troubleshoot its normal previous instance. The user encountered "Port 8000 is unavailable" while trying to restart to enable OpenAI; this is a real experience defect to fix. Make routine startup/restart boring and safe.

## 1. Load local configuration automatically

- The launcher/backend must load **the checkout's** `ROOT/.env` (not necessarily `$PWD/.env`, and never frontend Vite environment files) before backend process creation and before API configuration is read. Support typical simple dotenv syntax, including both `OPENAI_API_KEY=...` and `export OPENAI_API_KEY="..."`, blank lines, comments, and quoted values. Prefer a well-established pinned dotenv parser such as python-dotenv rather than executing arbitrary shell contents. Do **not** `source` or shell-evaluate `.env` in Python. Any other launcher entrypoints requiring the same provider setup should be consistent.
- Existing environment variables **take precedence** over file values unless the user explicitly passes a documented override option; tests must check precedence. Do not echo key values, print config dumps, leak credentials in process arguments, browser, logs, or errors. `.env` stays ignored by Git; a template `.env.example` with placeholders (no real key) is optional.
- Preserve A8's explicit `SIGMA_AI_ENABLED=1` switch and separate consent for billed generation. Show actionable, accurate "not configured" guidance when missing. A valid key in the file + enabled switch should produce a real non-generating API connectivity check after launch, **without** manual shell setup.
- Read file errors safely: absent file is normal; malformed/unreadable file yields a precise fix instruction without dumping secrets. Never override another user's or unrelated process's configuration.

## 2. Safe instance lifecycle and port conflicts

Current `src/sigma/ui.py` statically binds 127.0.0.1:8000 and :5173; a second invocation immediately raises a "Port ... unavailable" error, leaving the user to inspect/kill the prior instance. Replace that workflow with a **reliable SIGMA-owned instance lifecycle**:

- Recognize an **already running SIGMA UI started from this checkout** using a robust ownership/identity mechanism (e.g. local private control socket plus ownership/instance handshake under a user-writable 0700 state directory, coordinated with an exclusive lock). A file containing a PID alone or a port-number heuristic **is not sufficient evidence** to send signals; protect against stale files, PID reuse, races, simultaneous launches, other users, other SIGMA checkouts and changing symlinks.
- If a confirmed same-checkout SIGMA UI is running, automatically **request a graceful shutdown**, wait for the old supervisor to clean up *both of its actual child process groups*, and start a fresh instance with the newly loaded `.env`. Give one concise message such as "Restarting existing SIGMA instance…" rather than demanding manual cleanup. A browser pointing at the default address should connect to the new instance when ready.
- Preserve foreground semantics and Ctrl+C graceful teardown; avoid processes orphaned by rapid successive launches, SIGTERM, errors during partial startup, and races with simultaneous SIGMA invocations. Consider how replacing the supervisor affects the older terminal: it should exit cleanly and not be left repeatedly trying to reclaim the ports.
- **Never terminate an arbitrary process** merely because it listens on port 8000 or 5173. If an unrelated service, an unverifiable old SIGMA version, or a different checkout occupies a required port, either choose alternate coordinated free backend/frontend ports and print the actual browser URL, or clearly report which port blocks startup and why safe takeover is impossible. Prefer a graceful automatic fallback to available ports if it preserves correct Vite proxy/API wiring, app origin checks, frontend URLs and launcher readiness. Otherwise a clear rare-case conflict is acceptable; unsafe killing is not.
- Dynamic-port fallback, if chosen, must dynamically generate Vite proxy target, FastAPI allowed localhost origin and browser URL coherently; be explicit about security boundaries. Do not globally loosen TrustedHost/origin restrictions, bind to 0.0.0.0, or allow unrelated hosts. Browser tab and API connection status should always point to this launcher, not an old process.
- A stale ownership/lock/socket record from a crashed process must be recoverable without manual `rm`; remove only SIGMA-owned stale state following safe verification.
- Don't introduce a daemon or background agent runner: only the local two-process dev UI lifecycle is within scope.

## 3. Verification

- Regression tests for dotenv parsing (quoted `export` format shown by the user), missing file, explicit environment precedence, no shell execution, and no output of API key. Verify `SIGMA_AI_ENABLED=1` reaches the backend and real provider status is checked using controlled fixtures; no paid calls.
- Real-process integration test: start SIGMA UI, invoke `./sigma ui` again from a fresh shell, assert new instance is ready and inherits updated `.env`, both old owned backend/frontend are gone, correct port routing, old supervisor exits, and Ctrl+C of current owner cleans up. Exercise a rapid double invocation and crash recovery.
- Simulate an unrelated listener on port 8000 and/or 5173 and another checkout's instance: assert no unrelated process receives any termination signal. Test any alternate-port fallback with correct CORS and proxy, or verify safe actionable error without process corruption.
- Check no change to project files from starting, restarting or closing the UI; never make Close Project a save or shutdown operation. Preserve current A7/A8 project UI and art.
- Run `./sigma test`, frontend tests/typecheck/build, and (where possible) actual browser startup/restart; record test results and known limitations in `docs/STATUS.md` and revise `docs/GETTING-STARTED.md` and README. Only claim checks really performed.

**Acceptance:** With `~/sigma/.env` containing `export OPENAI_API_KEY="sk-proj-..."` and `export SIGMA_AI_ENABLED=1`, `./sigma ui` automatically reads both values and cleanly starts/restarts a prior SIGMA instance from the same checkout without requiring the user to `source`, find PIDs, or kill processes. It refuses unsafe takeover of unrelated listeners.
