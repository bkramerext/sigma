# PR #297 Green consolidated R4R — 2026-10-28

Branch: `coordinator/signin-session-playback-stabilization`
Repository: `bkramerext/sigma`
Updated base: `origin/main` at `6ecc0df23127f4f1f920943331ff43afcc399682` (T313).
Validated implementation HEAD: `efa26c2` (merge of current main plus guest authorization corrections).
Final handoff commit SHA: recorded in the updated PR #297 description after this file is committed.

## Security audit and corrections

The prior guest policy broadly admitted `/api/projects/` and relied on selected denies. The API inventory and direct HTTP tests identified a fragile boundary: a new or overlooked registered route could otherwise inherit guest access. Guest access now uses an explicit route/method allowlist; every other registered project route is denied by default. Guest-safe sample browsing and isolated guest workspace operations remain available. Tests directly call the actual API routes and check denial of member project/session access, mutations, research execution, provider-backed operations, proposal/model lookup, and sponsorship endpoints. The guest identity is propagated into handlers so allowed reads do not accidentally schedule provider work. Built-in admin behavior is preserved.

Google authentication remains separate from membership authorization: an uninvited identity becomes a guest with no research or sponsorship entitlement. Invitation requests are durable, deduplicated, visible to admin, and approval grants membership on the next sign-in. Test fixtures isolate project/workspace state and mock OAuth/provider boundaries.

## Verification

`./sigma test` — PASS, all steps, including Ruff check/format, Pyright, frontend typecheck/build, `tests/cloud_auth.py` (70 tests), cloud research APIs, and deterministic sponsored provider responses. One unrelated graph-present sandbox scenario is skipped because the local Python sandbox image is unavailable; the withheld-graph branch passes.

Real Chromium checks — PASS:

- `browser_checks/local_auth_real_backend.py`: real Vite + local API, deterministic OAuth/provider boundary; persisted identity/session behavior.
- `browser_checks/guest_samples.py`: guest sample browsing.
- `browser_checks/issue279_invite_me.py`: invitation request, retry/reload behavior, zero-allowance Reload me, and member access.
- `browser_checks/local_admin_sponsor_pill.py`: admin/member sponsor pill behavior.
- `browser_checks/t17_8_saved_session.py`: saved session playback without provider calls.
- `browser_checks/about_dialog_acceptance.py`: responsive About dialog and focus/help behavior at desktop/mobile widths.

`git diff --check` — PASS. No paid provider calls were made. Sponsored inference and OAuth boundaries in automated checks are deterministic fixtures, not live Google/OpenAI calls.

## Acceptance state

| Criterion | State | Evidence |
|---|---|---|
| Guest Google identity is authenticated without membership | MET (automated) | Cloud auth tests and real-backend Chromium fixture |
| Guest sample browse; deny member-only reads, mutations, execution, provider/sponsor calls | MET (automated) | Direct API route inventory tests and guest browser check |
| Durable invitation request and duplicate suppression | MET (automated) | SQLite-backed cloud auth tests and invitation browser check |
| Admin request visibility/approval; admin access preserved | MET (automated) | Cloud auth tests and local admin browser checks |
| Subsequent sign-in gives member role and expected allowance | MET (automated) | Deterministic auth test confirms configured allowance; browser member-access fixture |
| Sponsored research succeeds and usage/allowance is attributed | MET (automated fixture) | Sponsored research API tests exercise successful fake provider responses, completed calls, accounting, and ownership isolation. This is not joined to the same N approval fixture. |
| One live Easy sponsored session by N after the full approval flow | UNVERIFIED | Requires the final manual acceptance run; no real provider call was made. |
| Live Google OAuth for N | UNVERIFIED | OAuth was deterministic in automated checks. |

Release acceptance therefore remains pending the live manual N workflow. Do not merge or deploy until it passes.

## Exact manual acceptance steps

1. Start the local stack with `./sigma start` and open `http://127.0.0.1:5173`.
2. Sign in with N's Google account. Verify the identity pill identifies N, Invite Me! appears, and sponsored/research execution is unavailable with no allowance.
3. Click Invite Me! and verify acknowledgement. Reload and verify the pending request remains and the button is absent; try a second request and verify it is suppressed.
4. Sign in as `zetacontinuation@gmail.com`, open **Admin Settings** → invitation requests, locate N, and approve the request.
5. Sign back in as N. Verify member role, no invitation prompt, and the expected sponsorship allowance.
6. Keep personal ChatGPT disconnected. Start one short **Easy** research session, verify sponsored inference is selected, wait for completion, and verify the usage is attributed to N and the allowance reflects the spend.

Record screenshots and the resulting session/usage evidence in the handoff before calling release acceptance complete. Do not use a paid provider call without the authorized live acceptance setup.

## Scope and disposition

This PR retains the existing sign-in, connection-mode, budgeting, and session-playback workstream and reconciles it with current main. The combined full diff was reviewed; no merge or deployment was performed. The PR description has been updated to summarize the current implementation and this verification state.
