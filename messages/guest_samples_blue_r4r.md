BLUE R4R handoff — Guest sample projects and About privacy actions

Branch: `fix/guest-samples-about-privacy`
PR: https://github.com/bkramerext/sigma/pull/246 (open against `main`; not merged)
Base: `main` at `6a607a488106f9c9233336eb940f0458024e527b`
Implementation commit: `eabb1bcf0b3393f47c9dc879ce1d9d4e50290a2e`
The PR branch will include this handoff-only follow-up commit after the code
commit above. The final PR head SHA is in the R4R notice.

Implemented temporary Guest workspaces with opaque, process-local tokens and
eight-hour inactivity expiry. Guest sample copies and Guest-created projects
live in private temporary directories; project path checks stay rooted there,
and guest Recents always return empty. This binding works even when local Google
authentication is disabled or unready. Provider-backed research, paper and
proposal generation, and AI text conversion are blocked for guests. The Guest
UI no longer requests personal AI connection/model data that produced
authentication-error toasts.

Guest Home uses the same standard Projects layout and New/Open controls as a
signed-in session, without the separate Welcome to SIGMA panel. The normal
Recent/Samples toggle is present, Samples is selected by default, and Recent is
disabled. Recent and sample groups start collapsed. Browse Published Research
is absent. Guest attempts to use AI from the connection pill or Generate action
receive a clear signed-in-account message without starting a provider request.
About retains Privacy Policy as a lower-left action button. The privacy notice
provides a top Return to SIGMA action. Google pill labels are shorter. Artwork
credit is “Brian Kramer” / “& GPT Models”.

Verification:
- `uv run python tests/cloud_auth.py` — PASS, 29 tests, including unready local
  Google Auth, temporary guest path containment, empty Recents, and blocked
  provider-backed routes.
- `uv run ruff check` and `uv run ruff format --check` on all changed Python
  files — PASS.
- `uv run pyright` on changed Python modules/tests — PASS, 0 diagnostics.
- `uv run --with playwright python browser_checks/guest_samples.py` — PASS in
  real Chrome: standard Projects Home, toggle selection/disabled state and
  collapsed groups, AI-unavailable feedback from both entry points, full sample
  project open, no authentication error, empty Recents, About Privacy Policy,
  and privacy-page Return to SIGMA.
- `npm --prefix frontend run typecheck` and `npm --prefix frontend run build` —
  PASS; existing >500 kB chunk advisory remains.
- `./sigma test` — completed with four unrelated repository failures:
  `tests/tooling.py`'s admin-contact warning assertion; four Ruff findings in
  `src/sigma/gmail_delivery.py` and `tests/gmail_delivery.py`; formatting in
  `src/sigma/cli.py`, `src/sigma/gmail_delivery.py`, `src/sigma/ui_instance.py`,
  and `tests/gmail_delivery.py`; and Pyright's `.decode` typing error at
  `tests/gmail_delivery.py:56`. Frontend typecheck and guest-focused checks
  passed; the suite skipped its build after earlier failures, so the build was
  run separately and passed.
- `git diff --check` — PASS.

All checks used local deterministic fixtures. No Google OAuth, provider calls,
paid requests, SMTP, or production deployment occurred. Guest research is
read-only: guests can inspect and edit temporary projects, but cannot start
provider-backed or computational research.
