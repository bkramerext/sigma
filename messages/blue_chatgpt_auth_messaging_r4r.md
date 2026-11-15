BLUE R4R — Context-sensitive ChatGPT authentication messages

Branch: `fix/guest-samples-about-privacy` (continued because this task overlaps
the active Guest connection UI work).
PR: https://github.com/bkramerext/sigma/pull/246 (open against `main`, not merged)
Base: `main` at `6a607a488106f9c9233336eb940f0458024e527b`
Final PR head SHA: reported in the R4R notice.

Updated the existing connection guidance based on the authenticated state already
reported by `chatgpt_auth.session()`:

- No ChatGPT account (`disconnected`): “Research requires a ChatGPT connection.
  Sign in to continue.”
- Retained ChatGPT account needing interactive recovery (`reauth_required`):
  “Your ChatGPT session has expired. Please sign in again to continue.”

The backend already distinguishes a missing active account from an existing
account record whose credentials require reauthorization. The messages now
reflect that distinction. No authentication, credential management, account
recovery, or research persistence logic changed; saved projects and account
records remain handled by existing code. Removed the generic “Research and saved
account identity are retained” copy.

Verification:

- `uv run python tests/chatgpt.py` — PASS, including no-account guidance,
  expired-session guidance, retained account identity, and successful
  reauthentication recovery.
- `uv run ruff check src/sigma/openai_connection.py tests/chatgpt.py` — PASS.
- `uv run ruff format --check src/sigma/openai_connection.py tests/chatgpt.py` —
  PASS.
- `uv run pyright src/sigma/openai_connection.py tests/chatgpt.py` — PASS, zero
  diagnostics.
- `./sigma test` — ChatGPT tests and frontend typecheck passed. Four existing
  checks failed: `tests/tooling.py`'s admin-contact warning assertion; four Ruff
  findings in Gmail delivery; formatting findings in Gmail delivery, CLI, UI
  instance, and the already-committed guest browser check; and Pyright's
  `tests/gmail_delivery.py:56` `.decode` error. The full runner skipped the
  frontend build after failures. None of these failures involve the two changed
  Python files or the auth-message assertions.

The implementation is in [PR #246](https://github.com/bkramerext/sigma/pull/246),
which remains open and unmerged for review. No credentials, provider calls, or
saved research data were changed.
