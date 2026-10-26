BLUE R4R — Guest Play sign-in dialog

Branch: `fix/guest-samples-about-privacy` (continued for overlap with the active
Guest implementation).
PR: https://github.com/bkramerext/sigma/pull/246 (open against `main`; not merged)
Base: `main` at `6a607a488106f9c9233336eb940f0458024e527b`
Guest Play implementation commit: `ab1c381`.

Guest Play now opens the “Ready to investigate?” dialog:

- “Sign in to run a research session. You can explore sample projects as a
  guest.”
- “Sign in now” opens the existing Google sign-in pill; its Google link starts
  the established SIGMA login workflow.
- “Cancel” and Escape dismiss the dialog and restore focus to Play.

The action buttons use the Session remove confirmation action style. The Guest
Play control opens only the dialog. It does not invoke the normal
session start handler, read provider configuration or limits, reserve budget,
make a provider request, or mutate the project. Authenticated users still call
the original Play handler. The dialog uses the shared project-settings modal and
action styles.

Verification:

- `uv run --with playwright python browser_checks/guest_samples.py` — PASS in
real Chrome. The focused test checks exact dialog copy, the existing Google
pill and login route, Cancel/Escape, restored focus, no research/configuration/
limits requests, and no write requests when Guest Play is clicked or dismissed.
- `npm --prefix frontend run typecheck` — PASS.
- `npm --prefix frontend run build` — PASS; existing >500 kB chunk-size advisory.
- `uv run ruff check browser_checks/guest_samples.py` — PASS.
- `uv run ruff format --check browser_checks/guest_samples.py` — PASS.
- `./sigma test` — completed with four existing failing checks: the admin
  contact warning assertion; Gmail delivery Ruff findings; formatting in
  `src/sigma/cli.py`, `src/sigma/gmail_delivery.py`, `src/sigma/ui_instance.py`,
  and `tests/gmail_delivery.py`; and Pyright's `Message[str, str].decode` error
  in `tests/gmail_delivery.py:56`. All reached tests including ChatGPT/cloud auth
  passed. The test runner skipped its build after earlier failures; standalone
  build passed.

This change is on the active Guest branch as requested for the overlapping
implementation. PR #246 is open, mergeable, and not merged. No provider calls or
budget reservations were made. No research data or authentication logic changed.
