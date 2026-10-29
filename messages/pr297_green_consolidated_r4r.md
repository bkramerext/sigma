# PR #297 Green final integration R4R

Repository: `bkramerext/sigma`
Branch: `coordinator/signin-session-playback-stabilization`
Final integrated HEAD: `681fe09648c223119fa5022c63bc06b0ef93c634`
Integrated `origin/main`: `2d4368adf341aca105f5b645c676909da71ed5fb`
PR #297 remains open and unmerged. No deployment or paid provider calls.

## Main integration

Merged the post-Red `main` into the published PR branch with a non-rewriting merge. Red #317 scheduler/session changes, Blue #314 Markdown rendering, and the approved About diagram remain present. Red's deterministic Maximum Regions browser lifecycle, Blue's real-Chrome math check, and responsive About acceptance all pass on the integrated tree.

## Google sign-in failure and correction

The real-Chromium reproduction showed the first-visit `Welcome to SIGMA!` modal intercepting pointer events aimed at the visible Google sign-in pill. The modal now has its own **Sign in with Google** link so first-time visitors can start OAuth without dismissing Welcome first. The browser regression clicks that dialog link, continues past Welcome, then clicks the actual header pill. Both paths reach the real local `/api/cloud-auth/login` endpoint and assert its 302 target is Google's OAuth authorization URL. The redirect is captured and fulfilled by a deterministic fixture; live Google OAuth was not run.

## Invitation, membership, and Reload me!

`browser_checks/local_auth_real_backend.py` uses two deterministic Google identities against a separate real SIGMA API process and durable local auth database. It:

- Submits an uninvited guest's request through the real API and confirms it is persisted. Email delivery is deliberately unconfigured; the test stubs the delivery boundary after verifying the persisted request, so no email is sent.
- Signs in as the built-in admin, opens the actual Administrator Settings dialog, confirms the guest request appears, adds the guest, and verifies the request leaves the queue. A fresh deterministic session then resolves as a member, matching the required subsequent-sign-in behavior.
- Exercises **Reload me!** on the member pill. It is hidden at `$0.05`, visible at `$0.04`, and sends a real API reload request at `$0.03`. The admin dialog displays the persisted request as an allowance reload request.
- Retains a guest cookie while switching Google identities and verifies project, saved-session, and artifact reads are isolated. Guest reads include `no-store`, `no-referrer`, `nosniff`, and `frame-ancestors 'none'` headers.

## Security and spending checks

Guest middleware retains server-side default denial and an explicit method/path allowlist. Direct API tests exercise actual guest-safe handlers and deny cross-owner/member data, writes, exports, research dispatch, provider operations, and admin routes. Monthly spending tests cover settled usage across rollover under monthly and cumulative policies, unresolved reserved/unknown obligations, and concurrent reservations against the global ceiling.

## Verification

- `./sigma test` — PASS on this integrated source tree, including cloud auth, monthly research windows, Red's research-session tests, Ruff, Pyright, frontend typecheck, and production build. The existing graph-present sandbox subcase was skipped because its local Python sandbox image is unavailable; the graph-withheld branch passed.
- `browser_checks/local_auth_real_backend.py` — PASS: both Google sign-in entry points, durable invitation, admin visibility/approval, subsequent member session, `$0.03` Reload me! request/admin visibility, guest response headers, and two-identity project/session/artifact isolation.
- `browser_checks/guest_samples.py` — PASS: public sample flow and welcome dialog.
- `browser_checks/issue279_invite_me.py` — PASS: invitation request/retry, reload threshold at `$0.05`/`$0.04`, and member access.
- `browser_checks/happy_path_reliability.py` — PASS: Red's deterministic Maximum Regions lifecycle, report, usage fixture, and reopen.
- `browser_checks/t301_markdown_math.py` — PASS: Blue #314 Markdown math rendering and semantic preservation.
- `browser_checks/about_dialog_acceptance.py` — PASS at 1440/390/320px and touch help at 390px.
- `git diff --check` — PASS.

The product feedback API and administrator handling have existing coverage in `tests/cloud_auth.py`, which passed in the full suite. This pass did not add a dedicated product-feedback browser acceptance.

## Acceptance state

| Criterion | State | Evidence |
|---|---|---|
| Current main integrated, preserving Red #317, Blue #314, and About changes | MET | Merge commit and three relevant Chrome checks |
| Google sign-in controls reach the real local OAuth-start endpoint | MET (automated) | Welcome CTA and actual pill clicked in real Chrome; redirect URL validated by fixture |
| Live Google OAuth with account N | UNVERIFIED | No live OAuth callback was performed |
| Durable guest invitation, real admin dialog visibility/approval, and subsequent member role | MET (deterministic real API/browser) | Shared auth DB, real admin dialog/API, fresh post-approval session |
| Reload me! threshold below `$0.05` and admin visibility | MET (deterministic real API/browser) | Hidden at `$0.05`, visible at `$0.04`, request recorded at `$0.03` and shown to admin |
| Guest identity isolation, cache protection, default-deny route audit | MET | Direct API and real-backend Chrome checks |
| Monthly rollover and global reservation limits | MET | Adversarial unit tests |
| Red scheduler/session, Blue Markdown, approved About diagram | MET (automated + Chrome) | Full suite and real-Chrome checks |
| N's live Google → invitation → approval → Easy sponsored session with usage attribution | UNVERIFIED (human release gate) | Not run; deterministic provider fixtures do not establish a live provider call or N's real spend attribution |
| Dedicated product-feedback browser acceptance | UNMET / not in this pass | Existing feedback API/admin tests pass; no feature-specific browser acceptance was added |

## Manual release acceptance steps

The local SIGMA UI is available at `http://127.0.0.1:5173` from this checkout.

1. Sign in with test account N through Google. Confirm N's identity pill and **Invite Me!** appear, with research and sponsorship unavailable before approval.
2. Click **Invite Me!** once. Confirm acknowledgement; reload and confirm the pending request suppresses the button and a duplicate is not created.
3. Sign in as `zetacontinuation@gmail.com`. Open Administrator Settings, locate N's request, approve it, and verify it is removed from the pending list.
4. Sign back in as N. Confirm member status, no invitation prompt, and the displayed sponsorship allowance.
5. Without connecting personal ChatGPT, run one short Easy session. Confirm sponsored inference, a successful provider call, session completion, usage attributed to N, and the allowance debit.
6. Record timestamps, N identity, admin approval, completed session, and before/after allowance. This live run remains pending; do not merge or deploy before it passes.
