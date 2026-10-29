# GREEN R4R — PR #297 Gate 3 corrections

Repository: `bkramerext/sigma`

Branch: `coordinator/signin-session-playback-stabilization`

Implementation SHA: `19821f010ac6620a3b259b25860a2721c76c509d`

Previous implementation: `01d429e` (`Require personal OAuth before mode selection`).

## Corrections

### Personal authorization and mode selection

Before this correction, `/api/ai/mode` called `set_model_access()` and the
service persisted `personal` for any eligible user. Eligibility and the saved
mode flag did not prove that the user had successfully completed ChatGPT OAuth.
The earlier tests reached `set_model_access()` directly and used prepopulated
credentials, so they missed both a direct API bypass and the distinction
between a funding preference and authorization history.

The OAuth callback now records successful plan-permitted authorization under
the originating verified Google subject, after saving that subject's personal
credentials. A missing plan scope records no authorization. First personal
selection requires this durable record. The record is independent of current
token health and the funding-mode flag, so later credential failures retain an
established personal preference. A legacy personal flag without proof remains
represented as personal and does not trigger sponsor billing.

The regression exercises the actual local API sequence with an existing Google
cookie: canceled OAuth leaves sponsorship selected; direct personal selection
and a legacy preselected personal flag without proof are rejected; a
registration without the required plan scope is rejected; successful simulated
OAuth writes the user's credential and authorization records; personal mode
then persists; provider failure does not erase it. It also verifies Z and B
cannot borrow each other's personal authorization and that using
`zetacontinuation@gmail.com` as both personal and sponsor ChatGPT email keeps
two credential stores separate.

### Exhausted sponsorship and mode selection

Previously, `/api/ai/mode` inspected the budget snapshot before allowing a
switch to sponsored mode. A zero allowance or unavailable ledger could strand
a user in personal mode even though mode choice is not research admission.
The old assertion encoded the 409 behavior instead of testing a zero-balance
disconnect and return sequence.

Local and hosted mode selection now preserves sponsorship eligibility and
forced-mode checks but does not inspect the spending ledger. Budget admission
remains in research dispatch. Tests select sponsored mode with an empty or
unavailable snapshot and separately verify exhausted sponsored research fails
before provider dispatch. Personal and sponsor credential stores remain
independent.

### Google and invitation pills

The Google pill previously hid “Sign in with Google” whenever Invite Me was
available. The browser fixture also returned a verified-denied invitation
state for an ordinary signed-out guest, which made the expected pill state
wrong.

The Google sign-in link is now independent of Invite Me. The full Chromium
scenario distinguishes a signed-out guest, a verified denied identity, a
pending invitation, and an authorized administrator. It asserts Google sign-in
with no Invite Me for guests, both actions for a verified denied identity,
no duplicate Invite Me for a pending request, and Google sign-out only for an
authorized administrator.

## Modified files

- `src/sigma/cloud_auth.py`
- `src/sigma/chatgpt_auth.py`
- `src/sigma/api.py`
- `src/sigma/ai_store.py`
- `src/sigma/cloud_personal.py`
- `frontend/src/main.tsx`
- `tests/cloud_auth.py`
- `tests/chatgpt.py`
- `tests/cloud_personal.py`
- `browser_checks/hosted_sponsored_connection.py`
- `docs/STATUS.md`

## Verification

- `uv run --locked --no-sync python tests/chatgpt.py` — passed. Covers
  successful callback proof and callback without plan permission.
- `uv run --locked --no-sync python tests/cloud_auth.py` — 68 tests passed in
  the full local run. Focused final rerun of
  `test_local_admin_sponsored_mode_transition_uses_bounded_global_pilot` and
  `test_local_existing_cookie_keeps_same_email_personal_and_sponsor_credentials_separate`
  — 2 passed.
- `uv run --locked --no-sync python tests/cloud_personal.py` — 3 passed in the
  full local run.
- `uv run --with playwright python browser_checks/local_auth_real_backend.py`
  — passed against the real local SIGMA API. Simulated only external OAuth and
  provider boundaries; covered same-email personal/sponsor OAuth, persistence,
  server restart, member privacy, and zero-budget Play denial.
- `uv run --with playwright python browser_checks/hosted_sponsored_connection.py`
  — passed, complete hosted Chromium regression (not focused-only). The
  hosted browser script mocks SIGMA API responses for UI-state coverage; the
  actual mode authorization and budget behaviors are separately covered by
  API tests.
- `./sigma test` — all configured steps passed, including Ruff check, Ruff
  format check, Pyright, frontend typecheck, and frontend production build.
  `tests/epistemic_continuity.py` skipped only its graph-present local sandbox
  case because the existing Python sandbox image is unavailable; its
  graph-withheld checks passed. Build emitted the existing advisory for a
  JavaScript chunk larger than 500 kB.
- `git diff --check` — passed before commits.

## Checklist

- **MET — first personal authorization gate:** canceled OAuth, absent proof,
  legacy mode flag without proof, and missing plan scope cannot establish
  personal mode; simulated successful OAuth stores proof by Google subject.
- **MET — preference and provider state separation:** token/provider failure
  after established personal OAuth leaves personal preference selected and
  does not fall through to sponsor billing.
- **MET — exhausted allowance selection:** sponsored mode can be selected at
  zero or when snapshot lookup is unavailable; existing research admission
  checks still fail closed before provider dispatch.
- **MET — Google and invitation controls:** full hosted Chromium covers guest,
  verified-denied, pending invitation, and authorized administrator states.
- **SIMULATED — OAuth/provider boundaries:** OAuth token validation and
  provider catalog checks use deterministic fixtures; no paid provider calls
  were made.
- **UNVERIFIED — live provider behavior:** real account OAuth, token validation,
  and real provider connectivity were not performed.
- **DEFERRED — hosted personal OAuth:** remains unsupported. Newly selecting
  hosted personal mode is rejected; legacy saved personal state remains
  visibly unavailable rather than silently spending sponsorship.
- **DEFERRED — live play acceptance:** the seven live session-playback cases
  remain for the subsequent acceptance round.
- **UNVERIFIED — remaining UX/provider acceptance:** no human live Play test
  was requested or performed.

No CI was run or awaited. No merge, deployment, or paid provider call occurred.
