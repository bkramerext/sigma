# T279 / Issue #279 — Blue R4R

**Status:** R4R — implementation and local verification complete; independent review requested.  
**Branch:** `blue/issue-279-invite-me`  
**Base:** `main` at `918aee4ecf9d4a54d89e5c2d7dd97009ebc401ad`  
**Verified implementation commits:** `e118694` (`T279: add invitation request to sign-in pills`) and `024f606` (zero-allowance **Reload me!**).
**PR:** [#281](https://github.com/bkramerext/sigma/pull/281), open against `main`, not merged. It was opened at branch head `be0722bc0fcd1ac1a7a6fb09b30af77a1b7c6b2e`; subsequent commits include the allowance correction and documentation-only updates.
**Merge:** not performed.

## Implemented

- Guest **Invite me** pill opens an accessible SIGMA-styled dialog explaining that Google verification is required. Its sign-in action uses T81/T88's existing `/api/cloud-auth/login?invite=1` path.
- After a verified, uninvited Google sign-in, the existing invitation dialog shows the server-verified identity and proposed privacy notice link. It submits only `{}` to T81's existing request endpoint; identity continues to come from the protected denied-access cookie.
- Submission is disabled while pending. Failures remain retryable. Success uses the established T81 confirmation and removes the pill.
- The denied-identity endpoint now reports the invitation status belonging to that verified subject. A recorded request remains confirmed, without a second submission or pill, after refresh. This reuses the existing invitation table and admin workflow.
- Authorized members/admins do not see **Invite me**. Existing sign-in, membership enforcement, guest Samples, and model controls are unchanged.
- The guest pill is labeled **Invite me!**. When a hosted signed-in user's remaining allowance reaches zero, **Reload me!** appears in the Admin header slot and reloads SIGMA.

## Verification evidence

- **MET:** `uv run python tests/cloud_auth.py` — 47 tests passed. Includes denied identity, durable invitation request status, membership controls, duplicate/idempotency and authorization paths.
- **MET:** `uv run --with playwright python browser_checks/issue279_invite_me.py` — passed in installed Chrome. Deterministic API routes exercised desktop/mobile layout, guest sign-in explanation and intent URL, verified invitation dialog and privacy link, keyboard submission, recoverable mocked failure/retry, success, pill removal after submission and reload, and member visibility.
- **MET:** The same real-Chrome check verifies the **Reload me!** control stays hidden with positive allowance, appears in the Admin slot at zero, reloads, and fits at mobile width.
- **MET:** `npm run typecheck` in `frontend/` passed.
- **MET:** `npm --prefix frontend run build` passed; the existing advisory for a JavaScript chunk above 500 kB remains.
- **MET:** `./sigma test` passed all scenarios, Ruff check/format, Pyright (0 diagnostics), frontend typecheck, and production build.
- **MET:** `git diff --check` passed.
- **UNVERIFIED:** Live Google OAuth, live authenticated SMTP/email delivery, and hosted deployment were not exercised. Browser acceptance used deterministic local routes; no live provider calls, paid work, or production changes occurred.
- Existing Starlette/httpx deprecation and occasional SQLite resource warnings appeared during tests; there were no failed checks.

## Scope notes

No dependencies or conflicts found. Pre-existing untracked `gmail_test.py` and `smtp_test.py` were left untouched. The handoff and tracker updates are committed and pushed after the verified implementation commit.
