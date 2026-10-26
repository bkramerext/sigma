# SIGMA Exploratory QA — 2026-10-26

## Executive summary

The audit exercised the public hosted landing page and read-only demo, plus isolated local workflows against the current `main` snapshot. Two reproducible defects were assigned finding IDs. BUG-001 was already fixed by #163 on `main`; the same behavior was reproduced only on an older local checkout. BUG-002 was reproduced on current `main`, fixed in implementation PR [#203](https://github.com/bkramerext/sigma/pull/203), and covered by a new real-Chrome check. No production data was changed and no paid inference was requested.

The hosted product is behind an approved-account gate. Consequently, the public demo and unauthenticated pages were tested, but authenticated research lifecycle, settings, inference, saved-paper, and account workflows could not be accepted on hosted SIGMA. Local no-cost testing verified project and strategy persistence and settings, while AI-backed actions were deliberately left uncalled. This report does not claim complete hosted workflow coverage.

## Environment and limitations

- Audit date: 2026-10-26 (America/Los_Angeles).
- Hosted target: `https://sigma-research.duckdns.org/`, accessed in isolated real Chrome 156.0.8078.47. The root requires an approved Google account. No sign-in, account bypass, or credentials were attempted.
- Hosted `/demo`: read-only curated sample; inspected a completed session, strategy assessments, outcome/evidence/computation disclosures and project export UI. Downloaded the Audit JSON export. Desktop and 390px mobile layouts inspected.
- Local: current `origin/main` snapshot `134b30d` in an isolated worktree, real Chrome 156.0.8078.47, temporary project/state roots, local Vite/API and no-network provider fixture as relevant. A separate reproduction of BUG-001 used the pre-existing stale branch `green/t99-t137-consolidated-acceptance`, whose code predates the `main` fix.
- No paid inference, production writes, deletion of owner data, deployment, configuration changes, or destructive security tests were performed.
- The report was prepared from manual interaction, browser observations, network request outcomes, source inspection, and focused regression checks. Screenshots are linked below; personal account data and secrets are excluded.

## Coverage matrix

| Area | Status | Evidence / boundary |
|---|---|---|
| Hosted home, About dialog, account gate | Tested | Landing page rendered at desktop/mobile; native About modal opens/closes and focus returns. The gate prevents workspace access. |
| Hosted Recent Projects, project creation/settings | Blocked | Requires approved account; not attempted without authorized test account. |
| Hosted sample/demo project and completed session | Tested (read-only) | Inspected the curated “Counting Pairwise Handshakes” demo, outcome, strategies, evidence/computations and export options. |
| Hosted live strategy editing/generation/fork/removal/enablement | Blocked | Not available in read-only demo; workspace authentication required. No inference invoked. |
| Hosted research start/pause/resume/stop/restart/navigation/refresh recovery | Blocked | No authorized hosted account; no paid provider call. |
| Hosted reports, exports, saved academic papers | Partial | Read-only project Audit JSON export downloaded and export options inspected. Generated reports, LaTeX/paper generation, and saved-paper library are unverified. |
| Hosted settings/account/model/inference limits | Blocked | Auth gate prevents access; the unauthenticated connection endpoint returns 401 as expected for protected state. No account settings were changed. |
| Local project creation and persistence | Tested | Created disposable project, edited title/description with newline, Unicode, emoji and literal markup, reloaded and verified persisted text without executing markup. |
| Local project settings | Tested (limited) | Research/limits/preferences tabs inspected; keyboard ArrowRight changed tabs; model selection and an advanced Outcome preference persisted after reload. Model authorization/connectivity was not established. |
| Local strategy lifecycle | Tested (limited) | Created manual strategy, toggled disable/enable, opened Fork form and cancelled, removed disposable strategy after inspecting history-preservation confirmation; remaining set survived reload. Generation was not invoked. |
| Local research lifecycle and recovery | Blocked by provider availability | Start attempt without connected AI showed a provider/account error and created no session; no provider request was dispatched. Pause/resume/stop/restart/refresh-during-run therefore not tested. |
| Local About from project workspace | Tested and fixed | BUG-002 regression check runs at 1440px and 390px, checks modal, Escape, focus return, route preservation, and no API call. |
| Local browser refresh/back/forward/direct URLs | Partial | Project settings and strategy state survived reload; full active-session navigation matrix blocked by no inference. |
| Accessibility / keyboard | Partial | Keyboard tab switching and modal Escape/focus return tested. Comprehensive screen-reader, contrast, and keyboard audit not performed. |
| Error handling | Partial | Missing provider path left project usable and created no session; unauth hosted protected request returned 401 behind the gate. Failure/retry paths for inference and exports were not tested. |

## Findings

### BUG-001 — Project creation triggers React maximum update depth loop

- **Severity:** High
- **Status:** FIXED on current `main` in existing issue [#163](https://github.com/bkramerext/sigma/issues/163) (commit `3bfe7db`). Not a new implementation PR from this audit.
- **Feature:** Local Home → Recent Projects → project creation → workspace render.
- **Reproduced:** Local only, on stale checkout `green/t99-t137-consolidated-acceptance`; not reproduced on current `main`. Hosted reproduction blocked by account gate.
- **Steps:** Open local Home; create a project with a valid title and problem; allow the app to navigate into the new project workspace.
- **Expected:** Project opens and remains interactive without uncaught render errors.
- **Actual:** The create API returned 201 and saved/opened the project, then Chrome repeatedly logged `Maximum update depth exceeded`, making workspace rendering unstable.
- **Evidence:** During reproduction Chrome logged `Maximum update depth exceeded`; [local-workspace-render-loop.png](evaluations/exploratory_qa_20261026/evidence/local-workspace-render-loop.png) records the affected workspace view (the console text is recorded here, not overlaid on the screenshot). In the current `main` snapshot, project creation completed without the render-loop console error; the existing strategy-selection browser check also passed.
- **Root-cause hypothesis (confirmed by source change):** Strategy rows were rebuilt on each parent render and consumed by an effect that publishes process controls, feeding state updates back into render. #163 memoized the strategy list and added a browser regression guard.
- **Regression evidence:** On current `main`, `browser_checks/t43_1_strategy_selection.py` passed, including its maximum-depth console-error guard. Local current-main project creation and persistence also completed without this error.

### BUG-002 — About action is inert in project workspace

- **Severity:** Medium
- **Status:** FIXED in [implementation PR #203](https://github.com/bkramerext/sigma/pull/203) (commit `b1716e8`). Hosted acceptance remains blocked by sign-in gate.
- **Feature:** Project workspace global header → About SIGMA.
- **Reproduced:** Local current `main`; hosted workspace unverified.
- **Steps:** Open any project workspace and click the global header button named “About SIGMA.”
- **Expected:** About dialog opens and can be dismissed; Escape returns keyboard focus to the invoking button without leaving the project.
- **Actual:** No dialog appeared. The header emitted `sigma-open-about`, but its listener was mounted only by the Home screen, which is absent in a project workspace.
- **Evidence:** Reproduced in local Chrome by workspace interaction and source inspection (`Header` dispatches the event; listener lived only under Home). The fix adds the listener and dialog in `ProjectScreen`. The regression check is [project_about.py](../browser_checks/project_about.py); run against local Vite and fixture as documented in [browser_checks/README.md](../browser_checks/README.md). It passed at 1440px and 390px, checked native-modal semantics, Escape dismissal, focus restoration, unchanged route, no API request, and no page errors.
- **Root cause:** Event listener ownership followed the Home component lifecycle rather than the global header lifecycle.
- **Verification:** `./sigma test` passed all steps on the implementation branch, including lint/format, Python type checks, frontend typecheck, and production build. Build emitted the existing large-chunk advisory only.

## Existing Blue-owned issues: observations only

No duplicate findings are filed for #200, #201, or #202. Account access was unavailable, so their authenticated hosted steps could not be independently reproduced in this audit. The public landing gate behaved as expected; the unauthenticated AI-connection request received 401 while the page remained usable. This should not be treated as validation of the settings states in #200. Research start was not made against the hosted account, so #201's paused-session/result symptom was not tested. Paper generation and the preflight issue in #202 were not exercised. These observations are for Blue to consider alongside their owned investigations; this report does not repeat or close those issues. The sponsored-inference cost-setting investigation was not exercised.

## UX improvement suggestions (not defects)

- **UX-001 — Preview/demo boundary:** The public demo allows useful inspection of an existing investigation but does not make the authentication boundary and unavailable actions discoverable beyond the sign-in gate. Consider a concise, non-promotional explanation of which capabilities require an approved account. No implementation proposed in this audit.
- **UX-002 — Provider unavailable recovery:** When local research start is blocked because no AI provider is connected, the project remains usable and no session is created. A direct link to the relevant connection setup could reduce recovery effort. This is a usability suggestion; the observed protection and no-session outcome are correct.

## Recommended fix priorities

1. **BUG-002:** Review and merge implementation PR #203 after CI/review; then verify About from an authenticated hosted project on desktop and mobile.
2. **BUG-001:** No new work needed unless the existing #163 regression reappears; retain its render-loop guard.
3. **Hosted acceptance:** Use an explicitly authorized non-owner test account with a safe, disposable project to validate project settings, full strategy/session lifecycle, refresh/reopen recovery, report exports, saved paper library, settings persistence, and account/model limits without paid inference unless separately authorized.
4. **Blue follow-up:** Have Blue compare the unauthenticated 401 observation and gate behavior with #200–#202 and the sponsored-inference cost-setting work; do not infer resolution from this audit.

## Areas requiring further hosted acceptance

An authorized hosted test account is required to complete the inaccessible workflows. Before any acceptance that could dispatch a model call, confirm a zero-cost/no-dispatch test route or obtain explicit authorization for the cost. Hosted checks should use a new disposable project, avoid deleting existing projects, and verify persistence after navigation/reload. Specifically outstanding: create/edit project; strategy create/edit/generate/fork/remove/enable; session start/pause/resume/stop/restart and interrupted-session recovery; investigator/skeptic findings, outcomes and evidence; computations; generated reports and exports; saved academic papers; settings/account/model and inference limits; keyboard/screen-reader/accessibility; and network/error retry behavior.
