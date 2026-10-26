BLUE R4R — Guest Play sign-in dialog

Branch: `fix/guest-samples-about-privacy` (continued for overlap with the active
Guest implementation).
PR: https://github.com/bkramerext/sigma/pull/246 (open against `main`; not merged)
Integrated `origin/main`: `48fe9a1fee87a23c1af1665f1f30723ef39d9e97`
Integration merge commit (main-integrated code head):
`9743cd704b8a97a50b8187877c1464f988818e42`.

Guest Play now opens the “Ready to investigate?” dialog:

- “Sign in to run a research session. You can explore sample projects as a
  guest.”
- “Sign in now” opens the existing Google sign-in pill; its Google link starts
  the established SIGMA login workflow.
- “Cancel” and Escape dismiss the dialog and restore focus to Play.

The action buttons use the Session remove confirmation action style, are
left-aligned, and share the same copper text color. The Guest Play control opens
only the dialog. It does not invoke the normal
session start handler, read provider configuration or limits, reserve budget,
make a provider request, or mutate the project. Authenticated users still call
the original Play handler. The dialog uses the shared project-settings modal and
action styles.

Verification:

- `uv run --with playwright python browser_checks/guest_samples.py` — PASS in
  real Chrome. It checks exact dialog copy, the Google pill handoff and login
  route, left alignment and matching action colors, Cancel/Escape, restored
  focus, and no research/configuration/limits requests or writes when Guest
  Play is clicked or dismissed.
- `uv run python tests/cloud_auth.py` — PASS (30 tests).
- `uv run python tests/chatgpt.py` — PASS, including recovery behavior.
- `npm --prefix frontend run typecheck` — PASS.
- `npm --prefix frontend run build` — PASS; existing >500 kB chunk-size advisory.
- `uv run ruff check browser_checks/guest_samples.py` — PASS.
- `uv run ruff format --check browser_checks/guest_samples.py` — PASS.
- `./sigma test` — PASS, including repository Ruff, formatting, Pyright (0
  diagnostics), frontend typecheck, and build. The four failures recorded on
  the pre-integration branch (tooling admin-contact assertion, Gmail Ruff and
  formatting, and Gmail `.decode` Pyright) were resolved by current main; no
  test failures remain on the integrated tree.

Integration: `origin/main` advanced from `6a607a4` to `48fe9a1` and included
T200 sponsored ChatGPT/model availability changes. The merge had one conflict,
in `docs/STATUS.md`; both the Guest entries and main's T200 reconciliation
entry were retained. No code conflicts occurred. Guest Play and its Google pill
handoff passed real-Chrome acceptance after integration. The branch is pushed;
PR #246 is open against `main` and returned for review, not merged.

## Final CI correction (2026-10-26)

Correction commit: `56cdbdf65a56d025d15b1192dd19b0a4aa65be3d`. Updated
`browser_checks/t92_recent_running.py` and
`browser_checks/model_availability.py` to expand the Mathematics sample group
before locating the sample's Open button. T92 also expands the Mathematics
Recent group after returning Home and after reload, before locating the recent
project entry. No UI defaults changed; sample groups remain collapsed initially.

Verification on the correction tree:

- `uv run --with playwright python browser_checks/t92_recent_running.py` — PASS
  real Chrome: idle/running status, polling, reload, clear, and responsive widths.
- `uv run --with playwright python browser_checks/model_availability.py` — PASS
  real Chrome: 401/403/503 handling, saved-setting integrity, desktop/mobile,
  and no inference calls.
- `uv run --with playwright python browser_checks/guest_samples.py` — PASS
  real Chrome: guest samples, Guest Play no-dispatch behavior, and Google pill
  handoff.
- Ruff check and format for both changed browser checks — PASS.
- `./sigma test` — PASS, including repository Ruff, formatting, Pyright,
  frontend typecheck, and production build.

The local browser runs used temporary UI and fixture ports because the default
ports were occupied; the tests forwarded the browser origin expected by the
local fixture. GitHub Actions use their existing default ports. PR #246 is
updated and open for review at the correction commit plus this handoff update;
not merged.

This change is on the active Guest branch as requested for the overlapping
implementation. No provider calls or budget reservations were made. No research
data or authentication logic changed.
