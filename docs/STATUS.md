# SIGMA status

## Lean toolbar color feedback (2026-10-23)

Changed the disabled Lean logo in mathematical projects from its darker copper
filter to the same light copper used by the neighboring Project toolbar icons
(`#e0c4a0`). Updated the A20 browser assertion to require the unfiltered SVG
color. `./sigma test` passed. A focused real-Chrome check confirmed the logo is
visible, disabled, and rendered from the light-copper SVG; screenshot:
`/tmp/sigma-lean-light-copper.png`. The broader `browser_checks/a20_paper.py`
scenario did not complete because it expects an obsolete Google-sign-in
placeholder selector; it fails before reaching paper export. Its existing
Ruff check also reports two RUF007 findings in unrelated adjacent-gap loops.
No paid provider calls were made.

## T20.1: Minor UI acceptance fixes (2026-10-23)

Replaced the Project action's LaTeX wordmark with a compact typographic TeX
mark and added the official Lean Prover logo as a muted, disabled action. The
Project actions now follow TeX → Lean → Export/Download → Settings, with equal
six-pixel gaps and 34px controls. Centered the Model pill, changed the muted
Google placeholder to Google Sign-in with a gray status dot, and made connected
ChatGPT accounts read ChatGPT connected. API-key connections remain labeled
OpenAI API connected.
Removed the redundant AI paper choice from Export Project; the TeX shortcut
opens the existing saved-paper authoring workflow directly. Kept the Outcome
Markdown control inline at 28×28 px and renamed its evidence subsection to
Citations, Evidence & Obligations. Removed the redundant Session/Outcome column
heading and divider from the Sessions panel; the individual session headings,
statuses, actions, and Outcome contents remain directly visible.

Validation: `./sigma test` passed. Real Chrome `browser_checks/a20_paper.py`,
`browser_checks/header.py`, and `browser_checks/a17_research.py` passed. A20
checked Project actions, both tooltips and disabled Lean keyboard behavior, and
Export at 1440, 1280, 390, and 320 px. The header check covered pills through
320 px. A17 covered the Session heading removal, Outcome disclosure/toggle
behavior, historical/interrupted/multi-strategy records, and responsive widths
1440, 1280, 390, and 320 px. Desktop/mobile screenshots were
inspected at `/tmp/sigma-t20-project-download-desktop.png`,
`/tmp/sigma-t20-project-download-mobile.png`,
`/tmp/sigma-t25-outcome-desktop.png`, and
`/tmp/sigma-t25-outcome-mobile.png`. Paper generation used only the isolated
provider fixture; no paid provider call was made.

## T20.1 follow-up UI polish (2026-10-23)

Updated research-session limits end to end: defaults are 30 agent calls, 1 hour,
12,000 output tokens per call, and 3 Skeptic iterations (1–5). The duration
setting accepts minutes, hours, or days and is converted to backend minutes;
validation and enforcement are shared with API, CLI, and session execution.
Existing saved limits remain readable without being reset. The optional dollar
budget remains unimplemented pending reliable cost accounting.

Recent and Sample projects are grouped by type in an internally scrolling
home list. Recent shows at most four projects per type, marks the newest in
bold, and returns with only the active project type expanded. Repeated clicks
on the selected Samples or Recent tab expand/collapse all groups. Project
titles use matching Inter 13px styling in both lists, with only the newest
Recent title bold. Recent and Sample descriptions omit repeated type icons and
labels and align strategy count and difficulty under the title. Open Project
Cancel now follows its heading. Tooltip timing and click-to-hide behavior are
shared across the app.

The T20.1 follow-up branch includes the current main additions for Arrival,
Xenopus tail regeneration, and quantum chemistry samples.

The Lean proof control is shown only for mathematical projects. A focused real
Chrome check confirmed it is absent from Engineering and remains copper and
disabled (coming soon) for Mathematics.

Request-failure toasts now match the dark workspace: compact navy surfaces,
copper error accents, muted light text, and an understated underlined Dismiss
action. Real Chrome confirmed the styling and keyboard activation of Dismiss.

Real Chrome checks passed for `browser_checks/recents.py` (1280×720, 390×844,
320×700; screenshots in `/tmp/sigma-samples-*.png`), `browser_checks/header.py`,
`browser_checks/settings.py`, and `browser_checks/a20_paper.py`. The first A17
attempt stopped at 0/30 calls because clearing the cost field retained a $0.01
limit. PR #35 fixed the input behavior; the complete A17 flow passed against a
fresh fixture afterward. No paid provider call was made.

## T21 local alpha UI/browser acceptance (2026-10-23)

Initial acceptance ran against `main` at `9cb487e`; after T28 merged, the
current integration run used `main` at `317c5c4`. No live provider calls or
worker coordination were used. Real Chrome passed project creation/open/recent
navigation and persistence, settings and limit validation/save/reload, strategy
editing, three-round multi-strategy progress, pause/resume/stop during provider
work, historical/interrupted session inspection, Outcome/metrics/provenance,
and audit/text/HTML report downloads with failure recovery. The T20.1 header,
cost clearing, and responsive checks passed at desktop and phone sizes.

The first post-T28 A17 run exposed a stale shared provider fixture: strict
research schemas now require `computational_citations`, but the fixture omitted
it for non-computational responses. The fixture now supplies an empty list and
the full A17 Chrome flow passes. This was a test-fixture mismatch, not a
production session regression.

Real Chrome also ran a bounded Python computation and verified the completed
execution, exact source/stdout, execution ID, and T28's `computed.json` text
representation in the saved execution record at 1440px and 390px. A real Sage
10.8 Docker run passed in Chrome: the Skeptic saw the completed execution and
the captured `witnesses.json` metadata/hash; the Outcome/report and 320px layout
were inspected. T28 artifact inspections are available inside the expanded
execution JSON record; the UI does not render a separate preview panel. No
release-blocking UI defect was found and no product UI changes were needed.

Screenshots are under `/tmp`, including `sigma-a177-after-session-card.png`,
`sigma-a177-after-export-mobile.png`, `sigma-a23-model-controls-390.png`,
`sigma-t21-python-evidence-desktop.png`, `sigma-t21-python-evidence-mobile.png`,
`sigma-t26-sage-desktop.png`, and `sigma-t26-sage-mobile.png`.

Validation: `browser_checks/recents.py`, `browser_checks/settings.py`,
`browser_checks/a17_research.py`, `browser_checks/header.py`,
`browser_checks/sage_execution.py`, the real Chrome Python-evidence scenario,
`tests/computational_evidence.py`, `tests/python_sandbox.py`,
`tests/research_sessions.py`, `tests/sage_execution.py`,
`tests/project_reports.py`, and `./sigma test` passed on the integrated main
state. No paid provider calls were made.

## T17.8 deterministic acceptance on current main (2026-10-23)

This pass starts from current `main` at `ef3aadc` (T21 PR #38), which includes
A17.6/A17.7, T27's research-intelligence changes, and T28's computational
evidence integration. No provider/model endpoint was invoked. The two
`docs/ASSIGNMENT-A17.6.md` and `docs/ASSIGNMENT-A17.7.md` files named in the
ticket are absent in this checkout; the historical implementation and
verification records remain in this file. T29's human-intervention branch is
not part of this main snapshot and is outside this acceptance scope.

At initial PR publication, `main` had advanced to `e58eccd` with
documentation-only software-factory commits. That base was merged into the
branch; the application and test tree used for that initial validation did not
change. GitHub metadata at that earlier PR head reported `mergeable: false`
despite a clean local merge/compare. The subsequent T29 integration and fresh
PR state are recorded below.

### Workflow trace and falsifiable rubric

The current pipeline takes the persisted project question and session strategy
snapshot into `_agent_context` / `_role_request`, saves the validated
Investigator output and its execution/citations, gives the Skeptic the
ordered saved artifact history, validates its structured review, and runs the
coordinator in `src/sigma/research_sessions.py`. The coordinator requires an
achieved, `convincing_unverified` review with a claim, argument summary,
obligations, no unresolved objections or remaining obligations, and valid
supporting artifact references. It persists the objective review, Skeptic
objections, coordinator decision and strategy review together with the
artifact. `_outcome_without_metrics` keeps objective state separate from
session execution state and labels an achieved result as a solution candidate
(unverified). `_strategy_assessments` derives contribution only from saved,
strategy-linked review evidence and the eligibility snapshot. Session APIs
project the same records for the workspace; `src/sigma/project_reports.py`
exports saved outcomes and evidence. This is a structured evidence contract,
not a proof checker: the product cannot independently establish that a
provider's mathematical analysis is sound.

For Maximum Regions, the external acceptance rubric is: an upper bound must
justify why the k-th inserted line contributes at most k regions; an attaining
construction must justify that each earlier intersection is distinct; and
the empty arrangement must be handled. Numerical examples alone do not prove
the general result. This rubric was not added to either prompt. The
answer-free regression creates the exact question and a bounded insertion
strategy, then verifies both captured Investigator and Skeptic request
contexts contain neither the expected formula nor the known construction.
No prompt receives the evaluator reference answer.

### Deterministic adversarial evidence

Added `test_maximum_regions_false_candidate_is_rejected` to
`tests/research_sessions.py`. It sends the Investigator's plausible but false
candidate `R(n)=n^2+1`, then a specific Skeptic objection: at n=2, two distinct
lines form at most four regions, contradicting the candidate's predicted
five. The end-to-end session stops as `stop_decisive_counterexample`, persists
the objection and `not_achieved` review, projects a negative outcome, and
marks its strategy unproductive. The test also confirms the reference formula
and counterexample were absent from the initial Investigator context and
checks the saved response after reopening the session.

Existing deterministic cases cover the other boundaries: a complete
Maximum Regions argument can end positively with no next question while
remaining `convincing_unverified`; an unsupported component-identification
step with an explicit Skeptic objection remains incomplete; and a three-cycle
proof can close obligations only after the Skeptic reviews ordered evidence.
`test_answer_free_maximum_regions_prompt` checks prompt leakage. The
binary-string Fibonacci scenario applies the same achieved/partial contract to
a different proof mechanism. Outcome and strategy attribution tests cover
unknown legacy attribution, project-order snapshots, noncontributors,
disabled strategies, and strategy edits after the session. T28 scenarios
cover saved computational execution, citation validation, captured artifacts
and cross-session evidence. The Chrome A17 scenario exercises the workspace
and report projection of historical, interrupted and completed sessions.

### Acceptance matrix

| Criterion | Status | Evidence and limit |
|---|---|---|
| 1. Solution quality | **UNVERIFIED** | No real provider calls were made under the no-paid-call restriction. The historical 2026-10-22 Maximum Regions run in the earlier A17.8 section is preserved, but it used a shipped solution-bearing strategy and therefore does not qualify as independent discovery. Deterministic fixtures cannot establish agent discovery. |
| 2. Meaningful criticism | **MET** | Deterministic Maximum Regions complete/incomplete/counterexample cases exercise an explicit material objection, a contradicted false claim, a retracted false alarm, and an adequately supported conclusion. The live-model tendency to critique remains empirically unverified. |
| 3. Sound coordination | **MET** | `test_maximum_regions_solution_and_frozen_attribution` and the generic binary-string scenario prove that an achieved review with an empty next question ends productively; the new false-candidate case ends on a decisive counterexample. |
| 4. Calibrated conclusions | **MET** | Unsupported and incomplete reviews remain unresolved; a refuted candidate is negative; successful model-style agreement stays `convincing_unverified`. Historical and current code paths do not call agreement independent proof verification. |
| 5. Evidence-based attribution | **MET** | Deterministic session tests tie solution contribution to referenced saved artifacts and preserve project order, eligibility snapshots, disabled/not-used/unproductive states, and historical labels after strategy edits. |
| 6. Generalization | **MET** | The same structured review path is exercised by the different Fibonacci recurrence proof and an incomplete variant. This establishes deterministic contract reuse only; no second live problem was run. |
| 7. Operational reliability | **MET** | Current-main `./sigma test` passed; real Chrome `browser_checks/a17_research.py` passed against the isolated provider fixture. Research-session, computational-evidence, report, persistence, recovery, lifecycle, export and browser scenarios passed. Live provider reliability and quality remain unverified. |
| 8. Reproducible evidence | **MET** | Exact commands/results, the new adversarial fixture, screenshot locations and historical session/artifact IDs are recorded here and in `messages/t17.8_gray_acceptance.txt`. Test-generated sessions assert persisted artifact/session linkage. No live usage or cost is claimed. |

### Verification and decision

Passed after adding the false-candidate regression:

- `uv run --locked --no-sync python tests/research_sessions.py`
- `uv run --locked --no-sync python tests/project_reports.py`
- `uv run --locked --no-sync python tests/computational_evidence.py`
- `uv run --locked --no-sync python tests/agentic_evidence.py`
- `SIGMA_BROWSER_FIXTURE_URL=http://127.0.0.1:8022 uv run --with playwright python browser_checks/a17_research.py` (real Chrome; isolated local fixture)
- `./sigma test` (all steps passed after the final regression addition)

Chrome captures from the A17 journey include `/tmp/sigma-a177-after-maximum-regions.png`,
`/tmp/sigma-a1771-after-maximum-regions-html.png`,
`/tmp/sigma-a1771-after-maximum-regions-export-mobile.png`, and
`/tmp/sigma-a177-after-export-mobile.png`. The browser journey emitted
`PASS real Chrome A18: existing workspace and export flows, multi-strategy
selection, concurrent live activity, and stop during provider work` (the
script is `browser_checks/a17_research.py`; “live activity” here is fixture
traffic, not a live model).

No product workflow defect requiring implementation changes was found. The
new test closes a deterministic acceptance gap; existing product behavior
passed. Recommendation: accept the deterministic/evidence-contract portion
for human review, keep T17.8 open, and leave genuine real-agent solution
quality **UNVERIFIED** until a separately authorized bounded real-provider
trial can be run. This restriction does not authorize such a trial.

### T29 integration recheck (2026-10-23)

After T29 PR #39 merged as `aaf0995`, I merged current `main` into the T17.8
branch at `29d5d53`. Git merged the overlapping ticket tracker, STATUS, and
research-session test files automatically; there were no content conflicts or
manual resolutions. The T17.8 false-candidate regression remains at
`tests/research_sessions.py::test_maximum_regions_false_candidate_is_rejected`.

On this integrated source tree, focused `tests/research_sessions.py`,
`tests/project_reports.py`, `tests/computational_evidence.py`, and
`tests/agentic_evidence.py` passed. Real Chrome also passed
`browser_checks/a17_research.py` against a fresh isolated fixture and
`browser_checks/t29_intervention.py` against another fresh fixture. The latter
confirmed an objection can be submitted during fixture-backed research without
spending a provider call, and that acknowledgement/provenance and mobile layout
remain intact. Full `./sigma test` passed after the merge, including T29's
service, export-sample, lint, Pyright, frontend typecheck, and production-build
checks. No live or paid provider calls were made. Screenshots include
`/tmp/sigma-t29-intervention-mobile.png` and the A17 outcome/report captures
listed above.

No T17.8/T29 conflict or acceptance blocker was found. T17.8 remains open for
human sign-off; real-model solution quality remains **UNVERIFIED**.
After pushing this integration, GitHub's pull-request REST state reports PR #41
as `mergeable: true`, `mergeable_state: clean`, with base `aaf0995` and head
`c1fe8ea`. A prior connector snapshot still returned `mergeable: false`; the
current REST state confirms that is stale connector metadata, not a conflict.

## PR #35 review follow-up (2026-10-23)

The A17 0/30 stop came from the cost-limit input, not a provider or
session-engine regression. With a native number field, entering invalid `0`
and clearing it in the same draft left `$0.01` in the submitted settings and
correctly blocked the first provider call. The field now uses decimal text
input with the existing explicit validation, so clearing an invalid value
persists as unlimited. A17 confirms the saved value is null. The expected
session usage is 6/30 calls across three rounds.

The response guard now trusts reported output-token usage when it is within the
configured limit, regardless of UTF-8 byte length. A separate 1 MB transport
ceiling still rejects malformed or unexpectedly large responses before
parsing. A regression scenario confirms a response larger than four times the
token allowance is accepted when reported usage is in bounds, while the
existing transport-ceiling scenario still rejects oversized bodies.

Validation: `uv run --locked --no-sync python tests/research_sessions.py`,
real Chrome `browser_checks/a17_research.py` against a fresh isolated fixture,
and `./sigma test` all passed. No paid provider calls were made.

## T20 project-header LaTeX shortcut reconciliation

Reconciled the existing direct paper action with the project header. The initial
T20 action row placed its TeX wordmark after Project Download and before Project
Settings, using the existing compact copper icon-control style. The four Model,
Google, Thinking, and ChatGPT pills retain their existing
2×2 grid and compact header geometry. Closing direct paper authoring restores
focus to the shortcut. T20.1 removes the redundant paper option from Export
Project and keeps the direct authoring shortcut as the sole paper entry point.

Validation: `./sigma test` passed (lifecycle/API/workflow checks, Ruff, Pyright,
frontend typecheck and production build). Real Chrome A20 paper workflow passed
using the isolated provider fixture, including Project Download/TeX/Settings
order at 1440 and 390 pixels, keyboard activation and focus return, and the
existing Export Project path. The project-header check passed at 1280, 1100,
700, 390, and 320 pixels with no horizontal overflow. Screenshots were inspected
at desktop and mobile widths. No paid provider call was made. PR #10 is merged.

## T25: Outcome visual hierarchy

Replaced the two-column session presentation with one vertical reading flow.
Outcome summary, evidence references, and caveats stay immediately visible;
Status, Strategy Assessments, Metrics, and Provenance are independently
collapsible. Citations, Evidence & Obligations appears when a solution review
or saved artifacts exist. Details use stacked label/value pairs rather than tables or
side-by-side columns, with the existing copper/dark disclosures and Markdown
controls retained.

The Metrics subsection renders the existing T24 operational and research-quality
groups and provenance source inventory without recomputing measures. Provenance
also surfaces recorded step attempts and outcomes, artifact/session/strategy
links, model and billing configuration distinctions, prior-session evidence,
and saved Python execution details where available. Missing historic fields
remain marked unavailable; session completion and recorded verification are
not presented as independent proof.

Validation: `./sigma test` passed (workflow scenarios, Ruff, Pyright, frontend
typecheck, and production build). The focused real-Chrome check
`browser_checks/a17_research.py` passed against the current UI and provider
fixture, including keyboard disclosure interaction, no-table and single-column
assertions, T24 metrics/provenance, historical and interrupted records,
multi-strategy live activity, and desktop/mobile widths (1440, 1280, 390, and
320 px). No paid/live provider call was made.

### Outcome Markdown control follow-up

Moved the Render as Markdown control into the Outcome heading flow, directly
after the title and before the outcome label. Scoped its compact icon, hover,
active, and focus styling to the current heading markup; removed obsolete
selectors left over from the prior layout. Real Chrome verifies the control's
order and 28 px size at 1440, 1280, 390, and 320 px, keyboard activation and
focus visibility, unchanged provider-call count, and responsive overflow.
`./sigma test` and `browser_checks/a17_research.py` passed.

## A18 continuation: live research and portfolio coordination (2026-10-22–23)

This continues the A18 work on PR #8; it does not replace the earlier baseline
and implementation record below. I added an Easy-to-Hard research ladder, a
saved-evidence coordinator review, adversarial portfolio tests, and real-plan
evaluation. I did not run any API-key-billed call.

### Engineering changes

- Added the answer-free Easy sample **Counting Pairwise Handshakes**, followed
  by the existing Medium Euler-product and Hard alternating-series,
  theta-functional-equation, and RH portfolio samples. The first three
  mathematical samples have explicit methodological hints; those runs cannot
  establish independent method discovery. The RH entry remains a research
  program for an open problem, not a candidate proof.
- The portfolio coordinator now validates Skeptic references against exact
  supplied peer artifact IDs, records cited cross-strategy relations, and
  presents evidence-linked continue/revise/hold/challenge/abandon suggestions.
  It can flag cited contradictions and overlaps, and proposes combining two
  strategies only when the complementary judgments are reciprocal. All such
  judgments are unverified and do not mutate the saved strategy pool.
- Added deterministic tests for failed approaches, fabricated references,
  one-sided versus reciprocal complement claims, contradictions, strategy
  evolution/recovery, stop/resume, and timeout isolation. A transport timeout
  is stored as a failed provider step; the affected branch is marked
  `hold_after_failure`, its peer branch continues, and the timeout is not
  reinterpreted as mathematical evidence.
- The new timeout test exposed a stale portfolio recommendation at terminal
  budget exhaustion: a branch could retain a pre-finalization `continue`
  recommendation after its status had changed to ended. Terminal cleanup now
  recomputes the coordinator summary after final branch statuses and budget
  reasons are applied; the regression requires a terminal branch never to
  advertise `continue` or `revise`.
- A separate adversarial review found three lifecycle gaps beyond provider
  timeouts: a wave-level preflight exception could be returned as a branch
  result and leave the portfolio spinning; stop/pause could leave queued
  branches and a stale coordinator snapshot; and resume after duration/call
  exhaustion could end only the parent session. Wave failures now terminate
  through the session failure path. Stop/pause reconcile every queued/running
  branch and return the persisted post-cancellation state. Resume-limit exits
  terminalize eligible branches and refresh outcome, attribution, and
  coordinator summaries. Deterministic regressions exercise all three cases,
  including three in-flight workers plus a fourth queued strategy.
- Model/account preflight exceptions and hangs now pause the session before
  dispatching a provider call. A bounded 30-second preflight timeout is
  separate from the model-call timeout. A deterministic recovery test
  forces a preflight timeout, verifies zero calls were charged, then resumes and
  completes one full Investigator/Skeptic cycle.
- The reviewer was right that cross-strategy coordinator actions were
  advisory: the scheduler fair-rotated active branches and the Investigator
  received peer artifacts only as generic context. Material cited relations
  (`supports`, `contradicts`, `complements`, `overlaps`) now create a persisted
  handoff on the cited target branch. The target's next question explicitly
  asks it to test that relation against both cited artifacts, and pending
  handoff targets take selection priority when the shared call budget cannot
  fund every branch. The Investigator instructions require an explicit
  adopt/reject/unresolved judgment. Each handoff has a stable ID; call steps
  record the handoff ID and both artifact IDs, and the resulting research
  artifact records the handoff it was prompted with.
- A deterministic end-to-end regression produces a source finding in strategy
  A that cites strategy B's saved artifact, stops the session while B's next
  handoff preflight is blocked, then resumes. With only one complete cycle
  remaining, the scheduler selects B rather than A; the exact provider request
  contains the handoff question, both IDs, and the directed instruction. B's
  resulting artifact retains the evidence link. This proves the orchestration
  changes B's prompt and survives stop/recovery; it does not prove a real model
  will make a sound or useful change in response.
- Added a no-op control: an `unrelated` report creates no handoff and leaves the
  target question unchanged. A reported contradiction with a stated integer vs
  real-domain mismatch creates only a scoped challenge; it does not set the
  target branch to refuted. The Investigator prompt explicitly requires a
  domain/assumption check. This is a prompt-level guard, not a deterministic
  semantic validator; real model rejection of a false transfer remains
  unverified.
- Added explicit Skeptic retractions for a strategy's own earlier
  cross-strategy source artifacts. References are validated against that
  branch's saved evidence. A retraction removes an unconsumed handoff and
  restores the target's prior question; consumed handoffs remain in history
  with the retraction source. The coordinator no longer reports a retracted
  relation as an active conflict/combination. Deterministic controls cover both
  withdrawal before use and withdrawal after use: the former restores the
  target question, while the latter preserves the target's prompted-artifact
  lineage and marks that handoff retracted. Neither deletes the original
  evidence or marks the target disproven.
- Corrected the ladder documentation count: it has five runnable samples.
- Added the run protocol and scoring rubric in
  [the research ladder evaluation](evaluations/rh-research-ladder.md). Exact
  finite checks in `tests/research_ladder.py` validate example arithmetic only;
  they do not prove any analytic claim or RH.

### Live ChatGPT-plan evidence

I checked the active provider mode before each session; all were `chatgpt`,
connected, and used `gpt-6.1-sol` (High for the first two, Medium for the transfer
trial). No request was sent unless that check passed. The three captured project/session records remain
locally available under `projects/` and are not committed as source fixtures:

| Stage | Saved project and session | Calls / elapsed | Result |
|---|---|---:|---|
| Easy: Counting Pairwise Handshakes | `projects/a18-live-easy-20261022-232853.sigma`; session `1935da6d-5ad6-4d64-9982-06fe5f802300`; artifact `5f2e756e-f7ae-4780-9424-763195af2e7f` | 2 / 39 s | Completed. The Investigator derived `n(n−1)/2`, checked `n=1,2,3`, and supplied an incidence-count argument. The Skeptic raised a specific objection: the distinct-person convention was assumed rather than tied to the wording. It asked for the alternative convention to be handled. The saved outcome is **Mixed · partial progress, unresolved**, with verification `incomplete`; it did not label the result verified. |
| Medium: Prime Factorization and the Euler Product | `projects/a18-live-medium-20261022-233002.sigma`; session `16316d1d-fdca-4042-85dd-79e03828920f` | 2 dispatched / 40 s | Both concurrent Investigator calls timed out before producing an artifact. The session records both branches as failed, with `hold_after_failure`; strategy assessments are `not_used`, and the outcome is `Pending · execution failed`. No inference about either mathematical approach was made. The configured cap was four calls; no Skeptic calls were dispatched. |
| Medium: A18 Cross-Strategy Transfer Trial | `projects/a18-live-cross-transfer-20261023.sigma`; session `31cc2a95-5981-4b31-b4e7-1d11625c1180` | 2 dispatched / 60 s | Both concurrent Investigator calls timed out exactly at SIGMA's 60-second client ceiling. No artifacts or Skeptic calls; both branches were `hold_after_failure`; outcome `Pending · execution failed`. No handoff or research-quality observation was possible. The session call cap was 10; live work stopped after these two calls. |

Together these account for six dispatched plan calls: two completed and four
timed out. The session records contain no token-usage metadata, so token use
and remaining plan allowance cannot be quantified here. A timed-out remote
request may still consume plan allowance. There was no reported HTTP 429,
quota-limit response, or automatic billing fallback, but I stopped live
experiments after a second Medium trial also timed out at the raised 60-second
ceiling. Repeating the request would add uncertain usage without new
diagnostic information. No Hard or RH live session was run.

The cross-strategy trial protocol and oracle criteria were recorded before the
second Medium trial in
[the A18 transfer evaluation](evaluations/a18-cross-strategy-transfer.md).
The active connection was checked as `chatgpt / connected`; the trial used
`gpt-6.1-sol` at Medium reasoning. It did not reach the Skeptic or coordinator
stages.

### Research-quality assessment

- **Independent discovery:** Partially demonstrated only for the Easy count.
  The answer was absent from the saved problem and generic strategy. The
  derivation is short and familiar, and one task cannot establish general
  discovery ability. The Medium and harder runs supply method hints and are
  unsuitable for measuring independent method selection.
- **Skeptic criticism:** Demonstrated once with a concrete assumption tied to
  the Investigator's formula and an explicit way to resolve it. The objection
  may be stricter than ordinary mathematical usage, where “pair” conventionally
  means two distinct people; this is still a useful calibration test, not proof
  of consistently strong criticism.
- **Coordinator recognition:** On the Easy artifact, the outcome remained
  mixed/partial with an unresolved objection and incomplete verification. This
  is appropriately cautious. It did not claim the count was externally or
  formally verified. The Medium failure was correctly treated as an execution
  failure, not disproof of a strategy. Real multi-strategy synthesis remains
  unverified because that run timed out before any artifact or Skeptic review.
- **Strategy improvement:** Deterministic tests show that saved objections,
  peer findings, and revised questions flow into later cycles and that failed
  strategies remain distinct from mathematically unproductive ones. There is
  no live evidence yet that agents improved a strategy over a previous attempt.
- **Cross-strategy reasoning:** Deterministic integration now shows a cited
  finding from A alters B's scheduled next Investigator question and survives
  stop/resume with source/target artifact attribution. The live transfer trial
  timed out before artifacts existed; real-model transfer precision, Skeptic
  quality, and whether the prompted change improves the result remain
  unverified.

The earlier Medium run used a 40-second request timeout and both concurrent
High-reasoning calls reached it. The new trial used the raised 60-second
request timeout at Medium reasoning; both initial calls again reached the
client ceiling. The per-call timeout was initially raised to 120 seconds, then
increased to **15 minutes** after the human correctly challenged the short
ceiling for sustained research. Each call is capped by the session's remaining
time; Stop still cancels local provider work immediately. A deterministic
transport regression verifies an in-flight call is cancelled at the session
deadline despite the generous call ceiling. The new ceiling is not live-validated because
allowance consumption from the four timed-out requests is unknown. Timeout
steps now persist `failure_kind=timeout`, the effective call/session seconds, and a clear
note that remote processing may continue and consume plan usage. A separate
30-second preflight timeout protects model/account checks without charging a
provider call. Deterministic tests exercise fail-fast preflight recovery and
both timeout classification paths. No live request was retried. SIGMA still lacks external reference search,
computation tools, or a formal proof checker; model statements cannot certify
mathematical truth.

### Verification

- Final `./sigma test` passed after adding all five samples, the timeout
  isolation regression, and the terminal-recommendation fix. It covered all
  executable scenarios, Ruff check/format, Pyright, frontend typecheck, and
  production build. The ladder check confirmed five independent sample copies,
  answer-free Easy inputs, exact finite Euler/eta arithmetic, and theta spot
  checks; its printed note explicitly limits those checks to finite examples.
- Adversarial lifecycle and peer-handoff regressions passed in `./sigma test`
  on 2026-10-23, including preflight failure/timeout recovery, queued-branch
  stop, duration/call-limit resume, the A-to-B finding that changes B's
  scheduled next question and survives stop/resume, and source-evidence
  retraction both before and after the target consumes the handoff. The suite
  passed again after raising the call ceiling to 15 minutes and adding the
  in-flight session-deadline cancellation regression. Ruff check
  and format, Pyright (zero errors), frontend typecheck, and production Vite
  build also passed.
- Real Chrome `browser_checks/a17_research.py` passed against a local provider
  fixture at desktop (1440px) and mobile (390px), including multi-strategy
  selection, stop during provider work, resume, and the coordinator panel. I
  inspected both screenshots. Real Chrome `browser_checks/a20_paper.py` also
  passed after setting its dedicated UI/fixture ports explicitly.

**Recommendation:** Accept the coordinator and failure-handling engineering as
implemented once the final full suite passes, but do not accept A18 as evidence
of research effectiveness. Live evidence is limited to one elementary result
with a useful criticism and two Medium provider timeout trials; strategy improvement,
cross-strategy synthesis, and all Hard/RH capability remain unverified.

## A18 implementation and evaluation (started 2026-10-22)

### Baseline and research-quality boundary

The branch is `a18-blue`, originally based on `origin/main` at `6adbeed`;
checkpoint `0377231` contains the bounded-continuity and answer-leakage work. Baseline
inspection found one strategy per session, sequential Investigator/Skeptic
calls, provider gates held per call, and no persisted branch-level execution
state. The A17.8 Maximum Regions trial is not independent-discovery evidence:
its saved strategy already contained the answer. At this original checkpoint,
no live-provider A18 research had been run; the subsequent bounded plan-backed
trials and their limitations are recorded in the continuation section above.
Mocked outputs establish software behavior only, not model ability or research
quality.

### Completed engineering work

- **Bounded continuity:** a new session freezes up to 12 prior findings and
  16 KB serialized, with source session, strategy, artifact, objections,
  obligations, disposition, and next question. Long fields are visibly clipped;
  the full source remains inspectable. Both roles receive the unverified
  findings, and steps record cited source artifact IDs. Legacy session records
  remain readable. A large-history fixture checks the prompt stays below its
  48 KB bound and that project data is not rewritten.
- **Answer-leakage guard:** a fresh Easy Maximum Regions fixture starts with the
  objective and a generic line-insertion strategy. A deterministic assertion
  checks the exact provider inputs do not contain the known formula or attaining
  construction. The mocked output is not counted as a solution attempt.
- **Concurrent distinct strategies:** the start API accepts up to 12 distinct,
  saved, enabled strategy IDs and rejects disabled, removed, missing, or
  over-budget selections. Duplicate IDs are normalized. Every selected strategy
  must have budget for an Investigator/Skeptic pair. A fair rotating allocator
  spends from one shared call budget. Provider work runs with a semaphore capped
  at three calls; shared proposal, agentic, text-conversion, and session gates
  are held across each concurrent call wave and released in `finally`. Each
  branch has its own question, current action, cycle, call count, pending
  output, status, reason, and artifact attribution. Peer evidence is explicitly
  marked and source IDs are persisted on steps.
- **Coordination and outcomes:** the coordinator commits A17.6-compatible
  artifacts and strategy assessments per branch, then records continuing and
  stopped branches and the artifact IDs used for comparison. Provider and
  malformed-review failures are isolated to their branch; remaining work can
  continue. A budget unable to fund a complete pair finalizes outcome,
  assessments, event, and timestamp. The overall outcome remains based on
  saved artifacts, not operational success or failure.
- **Stop and recovery:** stop cancels all in-flight portfolio calls, preserves
  completed role outputs, marks unfinished steps interrupted, clears active
  step IDs, and does not silently replay them. Explicit resume uses remaining
  budget and completed pending output only. Recovery validates selected
  strategies. Existing duplicate-start and idempotency protections remain.
- **Existing workspace UI:** the start confirmation defaults to one strategy
  for compatibility and shows an explicit selector when more are available;
  users may select multiple within the shared-call limit. The existing session
  pane polls and displays each strategy's status, current action/question,
  cycle, calls, artifacts, and coordinator reason. No additional dashboard was
  introduced. “Fork strategy from findings” prefills the existing authoring
  form with source strategy ID, session, findings, criticism, open obligations,
  decisions, and questions; parent text truncation is disclosed. The source
  artifact and fork draft remain available through existing project/session
  surfaces.

### Deterministic and browser evidence

`tests/research_sessions.py` exercises single-strategy compatibility, bounded
continuity, answer-free inputs, three-strategy concurrent execution,
ten-strategy stress, out-of-order completions, branch-local provider rejection,
shared-budget exhaustion, parent/fork follow-up, and stop/resume during three
simultaneous requests.
The ten-strategy fixture observed a maximum of **3 simultaneous provider calls**
for 20 total calls and 10 attributed artifacts, with out-of-order responses in
**0.225 seconds** in the latest full-suite run on this machine. All four shared
provider gates were held during calls and released afterward. The stop/resume
fixture confirms no new call is dispatched after stop, interrupted calls are
not fabricated as artifacts, and the project file remains byte-for-byte
unchanged.

The real-Chrome fixture scenario exercises actual multi-strategy selection,
observes two branch states while one provider fixture is delayed, and stops the
session during provider work. The provider is an isolated local mock. The same
scenario retains continuation, fork-draft, Maximum Regions artifact/outcome,
reload, Markdown, and report-export checks. This is engineering evidence, not a
live research evaluation.

### Evaluation and remaining gaps

- **Engineering gate: pass.** The final deterministic suite and isolated real-
  Chrome workflow pass. Core continuity, bounded concurrency, live activity,
  recovery, provenance, and branch isolation are covered. New single-strategy
  sessions now share the same A17.6-compatible coordinator path; the legacy
  worker remains for pre-portfolio records.
- **Research gate: limited and still incomplete.** At this original checkpoint,
  no live model run was authorized; the later Easy and timed-out Medium sessions
  are recorded above. Their evidence does not establish multi-strategy quality.
  No claim is made that agents independently solved Maximum Regions. The
  earlier A17.8 result is disqualified by answer leakage.
- **Not implemented:** a user-authored next-step instruction during a running
  session. In a multi-branch wave, deciding which strategy receives that
  instruction and recording exactly when it entered the prompt needs a durable,
  attributed intervention contract; silently applying one session-level text
  to several concurrent branches would be ambiguous. Existing stop, strategy
  selection, and evidence-based fork controls remain usable. This is a known
  supervision limitation, not a passed criterion.
- **Research coordination limitation:** the local coordinator compares
  branch-level saved artifact IDs, Skeptic dispositions, and remaining
  questions; it does not call a separate model to synthesize or merge the
  strategies. No evidence supports claiming that a real coordinator chose the
  best mechanism. A deterministic parent/fork scenario confirms that a follow-
  up session can carry both strategy identities, preserve the parent's text,
  include prior findings, and attribute separate artifacts and assessments.
  No live-provider parent-versus-fork comparison has been run.
- **Live evaluation protocol:** use an answer-free Maximum Regions project with
  a sealed external solution/rubric; an Incremental Dependency Scheduler
  (Computer Science, Medium) scored for algorithm, proof, complexity, and
  adversarial cases; and Unexpected Oscillation (Physics, Medium) scored for
  evidence handling and non-fabrication. Record initial inputs, strategy text,
  model/effort, fixed call/time limits, session IDs, every role output, external
  scoring, failures, and usage. Count a Medium partial result as progress, not
  a solve. Audit every prompt source for leakage before each trial. Do not run
  these trials without explicit usage authorization.

The universal Easy/Medium solve aspiration is not established by finite mocks or
one future live trial. These changes improve control and observability; they do
not show SIGMA is yet a trustworthy research agent. A bounded user-direction
mechanism and actual cross-domain live evidence are the clearest remaining
limitations.

Final verification:

- `uv run --locked --no-sync python tests/research_sessions.py`: passed,
  including the 10-strategy load (20 calls, 10 artifacts, maximum concurrency
  3, out-of-order responses, 0.225 seconds in the latest full-suite run),
  parent/fork follow-up, partial provider failure, low budget, stop/recovery,
  guard changes, and A17.6 outcome regressions.
- `./sigma test`: passed all scenarios, Ruff check/format, Pyright (0 errors),
  frontend typecheck, and production Vite build. This is deterministic or
  mocked software evidence; it contains no live model research evaluation.
- `SIGMA_BROWSER_BASE_URL=http://127.0.0.1:5175
  SIGMA_BROWSER_FIXTURE_URL=http://127.0.0.1:8014 uv run --locked --no-sync
  --with playwright python browser_checks/a17_research.py`: passed in real
  Chrome against the isolated A18 mock, including two selected strategy
  branches, visible activity after reload during a delayed request, a stop with
  a completed role output retained and the in-flight call marked interrupted,
  and existing continuation/fork-draft, Maximum Regions, outcome, and export
  checks. This does not execute a real research model.

### Post-merge verification (2026-10-22)

Merged the then-current `origin/main` (`6a64976`, including A20 paper authoring)
into `a18-blue` with merge commit `4addffa`. The full `./sigma test` passed
after that merge: all source-controlled scenarios, Ruff check/format, Pyright
(0 errors), frontend typecheck, and production build. The ten-strategy stress
fixture completed 20 calls and saved 10 artifacts at a maximum concurrency of
3, with out-of-order completions in 0.226 seconds. These remain deterministic
and mocked engineering checks, not model-quality evidence.

The merge changed the LaTeX export choice from direct PDF download to the A20
paper-authoring handoff. Updated the older A17 browser scenario to check the
authoring handoff and return path without making a provider request, and to
check preserved/nonempty mobile filenames rather than relying on stale
defaults. Real Chrome then passed both the A18/A17 workspace scenario against
the isolated fixture (`SIGMA_BROWSER_BASE_URL=http://127.0.0.1:5175`, fixture
8014) and `browser_checks/a20_paper.py` against the isolated paper fixture
(UI 5175, fixture 8012). A20 browser coverage generated and retrieved its
fixture-authored compiled PDF. No live provider call was made. The A18 research
gate remains untested, with the limitations and no-independent-solve claims
above unchanged.

Before opening the review, fetched and merged the subsequently advanced
`origin/main` tip `b04a319` (journal-only changes) in merge commit `bfd8587`.
The PR head includes this latest base; GitHub reports the PR mergeable.

## A23: project difficulty setting (2026-10-22)

Added descriptive project difficulty with stable values `easy`, `medium`, and
`hard`, displayed as Easy, Medium, and Hard. New projects default to Medium;
legacy schema v1–v7 projects retain unknown difficulty (`null`) without a
write. Unknown difficulty is not shown in the project header or details and is
omitted from reports. The Settings selector shows “Not set” and preserves that
state until a difficulty is chosen. Settings edits that leave a legacy
difficulty unknown preserve the old schema. The first edit that chooses a
difficulty upgrades to schema v8 and creates the existing exact
`project.vN.json` backup. Difficulty participates in the settings audit chain, is validated
when read, and appears in JSON audit exports and human reports only when set.
The Maximum Regions sample is explicitly Easy, and sample copies retain that
value. Difficulty does not affect generation, agents, budgets, or research
outcomes.

The New Project form has a labeled selector defaulting to Medium. In Settings,
the research category and difficulty controls sit side by side; Difficulty can
remain unset for legacy projects. The project header shows a compact “Difficulty
· …” badge only when a value exists, with an accessible “Project difficulty:
…” name. No other product UI was changed. The existing settings browser
scenario verifies the field and follows the current combined project-title/
description and project-settings controls.

Verification passed:

- `./sigma test`: all executable scenarios, Ruff check/format, Pyright (0 errors),
  frontend TypeScript check, and production Vite build.
- `uv run --locked --no-sync --with playwright python browser_checks/settings.py`:
  real Chrome with the isolated HTTP fixture passed default Medium, saving Hard,
  failed-save draft retention, reload persistence, project-header metadata, and
  responsive overflow checks. It also verifies the Settings controls are
  side-by-side and that a schema-v7 project renders no difficulty badge and
  retains an unset selector. Viewports: 1672×941, 768×844, 390×844 and 320×844.
  The fixture makes no provider inference calls. Captures inspected:
  `/tmp/sigma-project-header-type-320.png`, `/tmp/sigma-a8-create-390.png`, and
  `/tmp/sigma-settings-classification-side-by-side.png`.
- `git diff --check` and Ruff checks for the updated browser scenario passed.

The captured Settings dialog places Research type and Difficulty in balanced
side-by-side controls. The captured new-project dialog shows Difficulty beside
Research category. At 320px wide, the project name wraps cleanly while a set
difficulty badge remains visible and the page has no horizontal overflow.

## A23.1 Evaluation (2026-10-23)

The first implementation put controls beside Difficulty and replaced the
functional ChatGPT connection control with a passive sign-in status. PR review
rejected both choices and pointed to the updated `tickets/t23.1.md`. The revised
header preserves Difficulty and places four distinct pills in the requested
upper-right 2×2 arrangement: Model over Thinking on the left, Google sign-in
over ChatGPT sign-in on the right. Google is a clearly unavailable, noninteractive
placeholder. The ChatGPT pill is the existing `ConnectionStatus` disclosure,
with its live state, connection/reconnection, account switching, billing mode,
and disconnect actions preserved.

The account-verified model catalog supplies relative cost tiers derived from
published API token prices. Dollar signs have an accessible explanation that
they are not session charges. Model and Thinking selections persist through
the existing project settings update service and affect subsequent provider
requests without changing billing mode. Model rotation includes every
available catalog model; if the next model disallows the current effort, the
header visibly announces the resulting effort before activation and persists
both values together. Thinking cycles only through the current model's
supported efforts.

Verification passed:

- `./sigma test`: all scenarios passed, including Ruff check/format, Pyright,
  frontend TypeScript check, and production Vite build. Model-catalog scenarios
  verify all three documented relative price tiers and reject a model/thinking
  pair after the fixture narrows the model's supported efforts.
- `uv run --with playwright python browser_checks/header.py`: real Chrome with
  an isolated local fixture passed precise two-by-two placement, keyboard
  cycling, incompatible-effort reconciliation, persisted project settings,
  accessible cost disclosure, unavailable Google sign-in, and the existing
  functional ChatGPT connection dialog at 1280, 1100, 700, 390, and 320px.
  No provider inference or paid API call was made. Inspected captures:
  `/tmp/sigma-a23-model-controls-1280.png` and
  `/tmp/sigma-a23-model-controls-390.png`.

The model catalog and settings contract are tested with deterministic fixtures;
live provider inference was not used for this UI/configuration assignment. The
ChatGPT control was exercised against the local fixture and its existing
connection dialog/actions, not a live sign-in or account.

### T23.1 local/cloud Google-pill acceptance follow-up (2026-10-23)

The local project header had no Google pill after cloud identity integration,
and the cloud project header omitted the ChatGPT connection control. The header
now always retains ChatGPT status, shows the noninteractive “Google Sign-in ·
Coming soon” placeholder in local workspaces, and shows the existing cloud
identity control in cloud workspaces. The narrow layout keeps Model | Google
above Thinking | ChatGPT, with Difficulty on its separate first row. No auth
flow or provider behavior was changed.

Verification passed on the current main base `1134361`:

- `./sigma test` passed all scenario, lint, type, and production-build steps.
- `browser_checks/header.py` passed in real Chrome at 1280, 1100, 700, 390,
  and 320px. It checks local placeholder availability/accessibility,
  non-interactivity, no login request, and existing control behavior.
- `browser_checks/t23_1_google_signin.py` passed in real Chrome at 1280, 390,
  and 320px for cloud signed-out login-route availability, authenticated
  project identity/sign-out state, ChatGPT visibility, row ordering, and no
  horizontal overflow. Authentication endpoints were deterministic local
  fixtures; external Google OAuth was not invoked.

## A17.8 Evaluation (2026-10-22)

**Recommendation: A17.8 needs further work before acceptance; do not mark A17
complete yet.** The implementation now preserves skeptical objections,
recognizes evidence-backed conclusions with no next step, and labels model
agreement as unverified. The live trial did not establish that the agents can
independently discover a solution, because the shipped Maximum Regions sample
starts with a human-authored strategy that already contains the formula, upper
bound, attaining construction, and essentially the full insertion proof. A
further answer-free live trial would be needed to establish that claim. No more
provider runs are recommended without explicit authorization; this work used
four bounded sessions (12 ChatGPT-plan calls total) because live failures
revealed successive implementation defects. Plan usage and dollar cost were
not exposed by the session records.

### Investigation and changes

I traced the saved project and strategy through Investigator/Skeptic prompts,
ordered artifact context, coordinator decision, objective review, strategy
assessment, and report projection. The baseline session (project
`projects/maximum-regions-by-lines-24.sigma`, session
`05fd0942-25d6-422b-8d43-1686699207e5`, artifact
`3a52e4b0-9d71-409b-88af-9f8f4e264d34`) consumed two calls at one round. The
Skeptic correctly identified that the Investigator asserted, rather than
justified, the link between half-plane sign sets and connected components.
SIGMA kept that result mixed and incomplete. This was sound calibration, but
not an independent solution: the sample's original human-authored strategy
already gives the same formula, the `y = kx + k²` construction, and the
insertion argument almost in full. Thus an answer in the agent output cannot
be credited as independent discovery.

The baseline also exposed two software defects. First,
`_maximum_regions_proof_obligations` was a Maximum Regions keyword recognizer
that could replace the Skeptic's explicit incomplete decision with an achieved
assessment. Running the previous implementation directly with complete-looking
keywords and a Skeptic objection phrased as “region/sign-set identification
remains asserted” returned all four proof obligations anyway. A stale server
then reproduced the end-to-end failure: session
`994131fc-fc7c-4daa-8f9f-4d642c5e6e9f` ended positive although its Skeptic marked
the objective `not_achieved`, verification `incomplete`, and retained an
unresolved component-identification obligation. This run was captured as
evidence of the old implementation, not counted as a post-fix result.

Second, the reserved/cost-estimation prompt told the Skeptic to review the full
ordered evidence set, while the actual provider prompt showed only the current
Investigator claim. The context builder also silently supplied only the two
latest artifacts. I removed the problem-specific recognizer, made the actual
request and reservation share the same role guidance, and pass the full
ordered history subject to the existing 48,000-character safety bound. If the
complete history exceeds that limit, the call now fails safely instead of
silently omitting evidence. The coordinator accepts a candidate only when the
Skeptic explicitly marks it achieved and unverified, supplies a claim,
argument, proof obligations, and valid supporting cycles, and leaves no
unresolved objections or remaining obligations. It can close Investigator
notes against that complete review; an achieved review with no concrete next
step is normalized to a productive conclusion. A follow-up live run caught
the old false negative in that path: session
`ea3df69e-0b6b-4a71-86dd-fa9161f42e62` ended `stop_no_progress` despite the final
Skeptic explicitly reviewing both artifacts as achieved. The coordinator
correction now covers that case. Finally, resolved historical obligations no
longer produce a stale top-level “Open obligations remain” caveat.

### Before and after evidence

| Run | Configuration and evidence | Result |
|---|---|---|
| Baseline | `gpt-6.1-sol`, High, ChatGPT plan; 1 round, 2 calls, 10 minutes, 4,000 output tokens/call. Project `maximum-regions-by-lines-24.sigma`; session `05fd0942-25d6-422b-8d43-1686699207e5`; artifact `3a52e4b0-9d71-409b-88af-9f8f4e264d34`. | Mixed / incomplete. Skeptic asked for a two-direction component/sign-set justification. Coordinator correctly did not claim success. The supplied strategy already contains the proof idea. |
| Stale-process reproduction | Same model/effort; 1 round, 2 calls. Project `maximum-regions-by-lines-25.sigma`; session `994131fc-fc7c-4daa-8f9f-4d642c5e6e9f`. Backend had been started before the source change. | Incorrect positive under the old code, despite the Skeptic's explicit `not_achieved`, `incomplete`, and unresolved objection. This is a failure reproduction, not post-fix evidence. |
| Intermediate corrected source | Same model/effort; 3 rounds, 6 calls. Project `maximum-regions-by-lines-26.sigma`; session `ea3df69e-0b6b-4a71-86dd-fa9161f42e62`; artifacts `2df24548-e127-4180-9247-06b4d6c95bfb` and `13461143-fc85-4ec0-803b-c2ba09daaac4`. | Skeptic's final review explicitly said achieved, cited both cycles, and had no next question, but provider used `stop_reason=unresolved` and the Investigator retained an open note. Coordinator ended `stop_no_progress`. This exposed and motivated the generic no-next-step correction. |
| Final corrected live run | `gpt-6.1-sol`, High, ChatGPT plan; 3 rounds, 6 calls, 30 minutes, 4,000 output tokens/call; no API-key cost cap (`null`) in plan mode. Fresh sample copy `projects/maximum-regions-by-lines-27.sigma`, displayed as “Maximum Regions Formed by Lines v7”; session `124d2b7f-9f9b-4060-86dd-fa9161f42e62`; four calls, two cycles. Artifacts `0261791f-ebc1-4eb6-8d0e-58a709a745aa` and `5c105ed4-8bf1-4f0d-92ad-5a4f129452e3`. | Positive, `stop_productive_conclusion`, achieved but `convincing_unverified`. Cycle 1's Skeptic found that small-value checks merely substituted into the formula; cycle 2 directly counted 1, 2, 4, and 7 regions and closed the objection. The final review cites both artifacts and has no unresolved objections or next question. The sample strategy still disclosed the main proof, so this does not establish independent discovery. |

The final Investigator argument covers the sign-pattern components, exact
insertion increment, upper bound, explicit construction, and `n = 0`. The final
Skeptic checks the ordered record, distinguishes the real small-value evidence
gap from a counterexample, and accepts the combined argument as unverified.
The strategy assessment is **Contributed to solution**, based on both saved
artifact IDs. No external source, symbolic checker, or independent human proof
checker was used. The live outcome is a model-generated candidate, not a
mathematical certification. The final browser capture, including the corrected
caveat projection, is `/tmp/sigma-a178-live-postfix-final-render.png`; the
browser report capture is
`/tmp/sigma-a1771-after-maximum-regions-html.png`.

### Current product strength assessment

SIGMA is looking strong as a research-workflow product and promising, but not
yet proven, as an autonomous research system. Its engineering supports a
substantial end-to-end loop: parallel Investigator and Skeptic work, saved and
ordered evidence, criticism that can change the coordinator's decision,
strategy attribution, resumable sessions, and an outcome that exposes its
uncertainty. A17.8's deterministic regressions show that important failure
modes in this loop are testable and that the coordinator no longer treats
proof-shaped language as proof.

The live Maximum Regions run is encouraging evidence of useful review: the
Skeptic caught a concrete gap in the initial small-case evidence, the
Investigator supplied direct counts, and the coordinator recognized the
resolved objection while preserving the “unverified” qualification. This is
credible evidence of review and coordination working together. It does not
show that SIGMA can originate a result: the sample strategy already contained
the central formula and proof outline, and no independent checker validated
the mathematics. SIGMA is a capable, evidence-centered research assistant and
review workspace; its autonomous discovery quality remains unestablished.

### What would improve research-trustworthiness evaluation

**Preparation request for ChatGPT:** assemble a reviewable evaluation packet for
one answer-free live research run. Do not place the reference answer or proof
in SIGMA's project, sample, repository, or prompt context. Keep it in a separate
sealed evaluator file for comparison after the run. The packet should contain:

- The research question SIGMA will receive, precise success criteria, domain
  constraints, and permitted sources or tools.
- A leakage review confirming that the answer and proof outline are absent from
  the project, samples, repository history, and supplied context; include any
  likely leakage paths that should be checked before the run.
- The sealed expected result and independent validation material: for
  mathematics, a proof sketch or mechanically checkable result where feasible;
  for empirical work, authoritative sources and a qualified domain reviewer.
  SIGMA's agents must not be the sole judges of correctness.
- A scoring rubric with explicit pass/fail anchors for correctness, independent
  discovery, evidence quality, counterevidence handling, calibration, and
  reproducibility. Mark which items require human judgment.
- A proposed bounded configuration: model/effort, call and time limits, and
  usage constraints. Running it requires explicit authorization; plan-mode
  records may not expose monetary cost.

ChatGPT should return the participant-facing task separately from the sealed
answer/reference, plus the leakage checklist, rubric, and proposed run bounds.
This lets the task be reviewed before execution without accidentally giving
SIGMA the answer. Once approved and run, preserve the prompts and ordered
artifacts, compare the result against the sealed reference, and have the
reviewer assess the reasoning.

With those conditions, we can preserve the prompts, ordered artifacts, and
decision trail, compare SIGMA's answer with the held-back reference, and have a
qualified reviewer assess the reasoning. Without them, deterministic tests
can improve system behavior but cannot establish research discovery; SIGMA
should be described as a research assistant rather than a trustworthy
autonomous researcher.

### Exit criteria

| Criterion | Status | Evidence and limits |
|---|---|---|
| 1. Solution quality | **Unmet** | Final live artifacts `0261791f-…` and `5c105ed4-…` contain the formula, upper bound, and attaining construction; the Skeptic closes the remaining checks. However, `samples/maximum-regions-by-lines/project.json` is a human-authored solution-bearing strategy. The agents elaborated and checked it, but this run cannot demonstrate independent discovery. |
| 2. Meaningful criticism | **Met** | Baseline artifact `3a52e4b0-…` identifies the missing component/sign-set justification. Final artifact `0261791f-…` points out that numeric substitution is not an independent small-value check; cycle 2 answers with direct geometric counts. Deterministic tests retain incomplete objections rather than promoting keyword-complete text. Criticism was useful and recoverable, not evidence that the mathematical claim was false. |
| 3. Sound coordination | **Met** | Final session `124d2b7f-…` ended `stop_productive_conclusion` after the Skeptic marked the multi-artifact objective achieved and returned an empty next question. The actual coordinator bug seen in `ea3df69e-…` is covered by the no-next-step regression. |
| 4. Calibrated conclusions | **Met** | Final outcome is “Positive · solution candidate (unverified)” with no independent-verification claim. The old false positive in `994131fc-…` is reproduced in a regression and rejected by the new structured evidence rule. A deterministic projection test verifies resolved historical obligations do not leave a stale open-obligations caveat. |
| 5. Evidence-based attribution | **Met** | Final strategy assessment is `contributed_to_solution` and cites artifacts `0261791f-…` and `5c105ed4-…`. Research-session scenarios retain project order, eligibility snapshots, and unknown attribution for legacy records. |
| 6. Generalization | **Met, deterministic only** | `test_generic_objective_review_on_binary_strings` exercises a distinct final-symbol partition/Fibonacci recurrence proof and an incomplete version. No second live problem was run; this is not empirical evidence of live generalization. No problem-specific completion heuristic remains. |
| 7. Operational reliability | **Met** | `./sigma test` passed all executable scenarios, Ruff, Pyright, frontend typecheck, and production build. Real Chrome `browser_checks/a17_research.py` passed the isolated-provider A17.7.1 / A17.6 persistence, outcome Markdown, dialogs, exports, and responsive checks. The live result persisted with separate execution status, objective outcome, and strategy contribution. Existing Starlette/httpx TestClient deprecation warnings remain non-failing. |
| 8. Reproducible evidence | **Met** | Baseline, stale-runtime reproduction, intermediate failure, and final run are identified above with exact session/artifact IDs, model, effort, limits, calls, outcomes, test commands, and screenshot paths. Connected-plan usage/cost is not returned by session records; no API-key billing path was used. |

The red/green coordinator regression specifically models a complete-looking
Maximum Regions argument paired with a material unresolved Skeptic objection.
The previous recognizer returned success for that case; the revised scenario
ends mixed. Separate tests cover a complete unverified conclusion with an empty
next step, a retracted spurious counterexample, a distributed proof across
cycles, an oversized full-history failure, and the binary-string generalization.
`tests/research_sessions.py` passes with these checks. The old-context behavior
was also directly exercised from the pre-change revision, where the Skeptic
prompt/history contract omitted earlier saved artifacts. This provides
deterministic regression evidence; it does not make the model roles
independent.

**Decision:** do not accept A17.8 or declare A17 complete yet. The engineering
corrections are supported by deterministic regressions and a successful
bounded live review, but exit criterion 1 remains unmet because the shipped
strategy contains the answer. A future answer-free Maximum Regions trial or a
human-approved comparable problem is needed to establish independent solving.
Any additional provider experiment should be separately authorized and
bounded; the four sessions above already exceeded the assignment's default
one-baseline/one-post-fix trial count while fixing defects discovered in the
earlier runs.

## Session controls, elapsed time, reports, and editing follow-up (2026-10-22)

Session elapsed time now freezes at Stop and excludes stopped intervals if the
session is resumed. Interrupted calls can be resumed immediately; the extra
resume warning dialog is removed. The Strategies toolbar's Play action always
starts a new session and says so explicitly; resuming is a per-session action.
Paused sessions may coexist with a new session, while queued and running
sessions still enforce single-session execution. The adjacent toolbar control
is Stop, with matching accessible and hover text and a stop-square icon.

Research Report HTML now has a structured, responsive layout with each research
session presented as a distinct unit: status and outcome are summarized first,
then the outcome evidence, session-specific strategy assessments, and artifacts
follow beneath. The LaTeX report uses nested paper-style sections, compact
session metadata, a typeset assessment table, and explicitly distinguishes the
current record from a future AI-produced academic paper. Export now offers four
direct choices—Project Audit, Text file, HTML report, and Academic paper using
LaTeX—with extensions displayed next to the filename and no format dropdown.
Project export and settings icons, Back to home, and the New/Generate links use
the same color and semibold 13px type as Disable/Fork/Remove. Strategy Remove
and visible Session/Recent Remove links use the same neutral action color;
confirmation remains destructive. The
settings control uses a standard gear outline, and the Project and Strategy
Markdown controls are optically lowered 2px for vertical centering. Existing
high-contrast hover treatment is retained.
Project and strategy title/description editing remains active until Save or
Cancel, and the title pencils have no hover text. Opening a Sample appends `v1`,
`v2`, and so on without a comma.

Verification: `./sigma test` passed all executable scenarios, Ruff, Pyright
(zero errors), frontend typecheck, and Vite production build. The focused
report scenario passed for the nested HTML and LaTeX structure, escaping, report
API, and unchanged Project Audit export. Tectonic compiled the fixture report to
PDF without layout warnings. A focused real-Chrome check verified all four
export choices, their filename extensions, the absence of a format dropdown,
and the copper export/settings icons. The research-session scenario passed, including
stopped elapsed-time stability and resuming an interrupted provider call. The
real-Chrome A17 browser check was attempted but currently stops at outdated
project-editor assertions; its UI checks need updating to the combined
title/description editor before it can serve as a passing browser regression.

## Home, sample, and research-type refinements (2026-10-22)

Opening a Sample creates projects named `Foobar v1`, then `Foobar v2`, and so
on, skipping titles already in use. New Project calls its field **Research
category**; Settings retains **Research type**. The alphabetized choices are
Biology, Chemistry, Computer Science, Economics, Engineering, Law, Mathematics,
Military, Philosophy, Physics, Religion, and Other. Each category has a copper
icon in the picker, project lists, and beside the project-page title. Existing
`default` values remain compatible and display as Other. New Project's
underlined Create and Cancel actions now follow the title. Project Audit and
workspace details display the friendly category label.

Recent-project removal now asks for underlined Confirm or Cancel in a floating
confirmation card without changing the row layout. Its message says the project
and research will be kept in storage. The Home credit's blue shooting-star
streak stays invisible at rest and crosses the viewport from left to right on
hover; it stays one shot while the pointer remains over the credit and sits
through the first credit line. Reduced-motion preferences show it without
animation.

Verification: `./sigma test` passed all scenarios, Ruff check/format, Pyright
(zero errors), frontend typecheck and production build. Real Chrome interaction
checks are being rerun against the updated local UI; the previous run stopped
because a connection overlay remained open.

## A17.7.1 and follow-up UI refinements (2026-10-22)

Completed the A17.7.1 dialog, report, and outcome corrections. Settings Save and
Cancel sit beside the title; report Cancel is next to Export Project and
Download stays left-aligned. Project Audit displays `JSON`, and Research Report
offers `Text`, `HTML`, and `LaTeX` without extensions in the format picker. The
selected suffix (`.json`, `.txt`, `.html`, or `.pdf`) appears beside the
editable filename. LaTeX uses the bounded external Tectonic compiler to produce
a real article-style PDF, with a browser preview and recoverable failures when
the compiler is unavailable. The report opens with the requested note about
the future academic-style report. Tectonic is not bundled or installed by the
app; production PDF export requires the binary on `PATH` or `SIGMA_TECTONIC`.

The Outcome Markdown switch now renders the complete outcome together:
assessment label, summary, evidence references, solution claim, argument,
assumptions, proof obligations, resolved and unresolved review notes,
verification, and caveats. Switching views preserves the saved result and does
not call a provider. Legacy outcomes without a summary retain their fallback.

The project-page Back to home caption is now an underlined button with the same
action as the arrow. Floating tooltips are dismissed when their trigger leaves
the document during navigation. Session-removal confirmation floats over the
row instead of changing its layout and has underlined Confirm and Cancel
actions. The Home page now has a compact, title-case blue credit at lower right:
“By Brian Kramer, ChatGPT & Codex” and “October 2026”, with a fine blue streak.

Recent Projects contained three stale entries named `edits.sigma`. Their saved
paths pointed into macOS temporary directories that no longer exist; these are
orphaned recent-index rows, not project data in the repository. The test runner
now isolates its Recent index and no longer adds scenario projects to the
user's list. Each old row can be cleared with its Remove action.

Verification:

- `./sigma test` passed all scenarios, Ruff, Pyright (zero errors), frontend
  typecheck, and Vite production build. Starlette emitted its existing,
  non-failing TestClient/httpx deprecation warning.
- Focused report tests passed, including structured HTML, LaTeX escaping,
  recoverable missing-compiler behavior, and PDF generation through the
  verified local Tectonic binary.
- `uv run --with playwright python browser_checks/a17_research.py` passed in
  real Chrome against the isolated mock provider. It verified desktop and
  narrow layouts, the complete Outcome Markdown toggle and math, export format
  labels/suffixes, structured HTML, compiled PDF preview/download, the
  unchanged session-row geometry beneath its confirmation overlay, and
  Back-to-home tooltip dismissal. No live provider calls were made.
- Reviewed real-browser captures: `/tmp/sigma-a1771-home-credit.png`,
  `/tmp/sigma-a1771-remove-session-confirm.png`,
  `/tmp/sigma-a1771-after-report-html-mobile.png`,
  `/tmp/sigma-a1771-after-pdf-preview.png`,
  `/tmp/sigma-a1771-after-maximum-regions-html.png`, and
  `/tmp/sigma-a1771-after-maximum-regions-pdf.png`.

## A17.7 UI corrections and regression hardening (2026-10-22)

Corrected the project header so its full title occupies its own row and the
Back arrow and caption sit together below it. Actionable icon controls now share
a body-portal tooltip that follows pointer and keyboard focus and stays inside
the viewport. Project export/settings icons share the edit-pencil hover and
focus treatment. The Markdown control is a larger standalone mark without the
old enclosing rectangle.

Settings now keeps its heading, tabs and Save/Cancel footer reachable while the
Limits panel scrolls inside a viewport-sized dialog. Opening Settings or Export
locks the page behind it and restores prior scroll styles on close. Session
summary uses one grid anchor for `Session #N`, lifecycle status, outcome and
cycle/call progress; status no longer repeats in Details. Resume/Stop/Remove
actions occupy a right-aligned vertical column, with Resume above Remove. The
research-assessment table keeps a usable minimum width on narrow screens and
scrolls horizontally instead of squeezing its rationale column.

Export Project now shows JSON (.json) while Audit is selected and exposes only
Text, HTML and LaTeX for Research Report. Cancel shares the title baseline;
Download is the copper footer action. The edited filename stem is preserved
across type/format switches, with its selected extension shown separately. The
compact responsive dialog was exercised for successful downloads, blocked-tab
recovery, request failure recovery, Escape, filename sanitization and all four
output types.

Recent-project isolation now applies to the test runner and standalone
scenarios that open projects, to browser fixtures, and to their subprocesses.
The runner supplies private temporary app-state, managed-project and auth
directories. The affected `edits.sigma` workflow has a regression that opens a
project while a sentinel external Recent index is present, checks that the
project appears only in isolated state, and verifies the sentinel bytes remain
unchanged. No existing Recent entries were deleted or rewritten.

The final A17.6 integrated check ran against the A17.7 build. Maximum Regions
ended with `stop_productive_conclusion`, an empty next question, a positive
`achieved` objective and a convincing-but-unverified caveat. The session's
artifact-linked **Contributed to solution** assessment persisted after reload
and strategy disable/enable, and matched both Project Audit and Research Report
exports. Session lifecycle stayed separate from outcome. The source-controlled
research-session scenarios also cover budget exhaustion, recoverable assessment
errors with saved artifacts, and stop/resume behavior; the browser fixture
exercised pause/stop, an ambiguous interrupted-call state, and visible error
recovery. The existing 2026-10-22 real-agent Maximum Regions evaluation remains
the live quality result; this UI verification made no live or paid calls.

Verification:

- `./sigma test` passed all scenarios, Ruff check/format, Pyright (zero errors),
  frontend typecheck and Vite production build. Starlette emitted its existing
  non-failing TestClient/httpx deprecation warning.
- `uv run --locked --no-sync ruff check browser_checks/a17_research.py` and
  `uv run --locked --no-sync ruff format --check browser_checks/a17_research.py`
  passed.
- `uv run --with playwright python browser_checks/a17_research.py` passed in
  real Chrome with the isolated mock provider. It covered 1440×900 desktop,
  520×430 short desktop, 390×420 mobile and 390×844 narrow workspace layouts;
  hover/focus tooltips and shared icon states; header geometry; Settings scroll
  containment and background lock; narrow session action placement and exact
  summary alignment; Audit/Report downloads, format/filename switching, popup
  and request failures; and the integrated A17.6 Maximum Regions reload/export
  checks. No live provider calls were made.
- Before/after screenshots were captured and reviewed. Baseline screenshots
  from clean commit `788fb00` are `/tmp/sigma-a177-before-workspace.png`,
  `/tmp/sigma-a177-before-export.png`,
  `/tmp/sigma-a177-before-settings-limits.png`, and
  `/tmp/sigma-a177-before-session-card.png`; the pre-change header is also at
  `/tmp/sigma-a177-before-header.png`. Final captures are
  `/tmp/sigma-a177-after-icon-tooltip.png`,
  `/tmp/sigma-a177-after-export-desktop.png`,
  `/tmp/sigma-a177-after-export-mobile.png`,
  `/tmp/sigma-a177-after-settings-short-desktop.png`,
  `/tmp/sigma-a177-after-settings-mobile.png`,
  `/tmp/sigma-a177-after-settings-main-mobile.png`,
  `/tmp/sigma-a177-after-session-card.png`,
  `/tmp/sigma-a177-after-session-stopped-actions-mobile.png`, and
  `/tmp/sigma-a177-after-maximum-regions.png`.

## A17.6 Research outcomes and strategy attribution (2026-10-22)

Separated research-objective assessment from execution status and strategy
contribution. Completed, evidence-supported work can now end positively when no
next question remains, while provider failure, budget exhaustion, stop state,
and verification caveats remain distinct. Solution reviews retain the claim,
argument, assumptions, proof obligations, unresolved/resolved objections, and
artifact references. Model-reported confidence is labeled as an unverified
candidate unless independent verification actually occurred.

Strategy assessments are persisted in project display order from the session's
eligibility snapshot. They distinguish **Contributed to solution**,
**Productive**, **Unproductive**, **Not used**, and **Disabled**; attribution
requires strategy-linked artifact evidence and survives later strategy edits.
Legacy sessions without attribution remain unknown. The project report and
session UI display the same saved review and contribution evidence. Failed
assessment calls retain earlier committed artifacts and expose a recoverable
error; empty timeout exceptions now produce a clear timeout message.

Completed the persisted strategy-enable prerequisite needed for A17.6's
historical eligibility semantics: legacy strategies default to enabled, and a
first toggle migrates the project to schema 7 with an auditable event and exact
pre-migration backup. Disabled strategies stay visible but cannot start or
resume research. Existing session snapshots and assessments remain unchanged
after later toggles.

The deterministic Maximum Regions regression covers a complete one-cycle proof,
evidence assembled across multiple cycles, presentation-only follow-up requests,
an unsupported counterexample signal, material objections, and reload-safe
strategy attribution. The assigned line-arrangement checklist reconciles saved
evidence across the ordered session artifacts and never upgrades the result to
formally verified.

Verification on 2026-10-22:

- `./sigma test` passed all source-controlled scenarios, including research
  outcomes, Maximum Regions attribution and aggregation, recoverable assessment
  timeout with retained artifacts, Ruff check/format, Pyright (zero errors),
  frontend typecheck, and production build. Starlette emitted its existing
  non-failing TestClient/httpx deprecation warning.
- `uv run --with playwright python browser_checks/a17_research.py` passed in
  real Chrome against the isolated mock provider. It verified the Maximum
  Regions outcome, cited **Contributed to solution** row, rendered proof review,
  persistence after reload, disabling/re-enabling across reloads, Start blocking
  while disabled, and preservation of historical attribution alongside the
  A17.5 workspace/export checks.
- A separate fresh Maximum Regions project was run with actual
  Investigator/Skeptic calls through the connected ChatGPT-plan mode using
  `gpt-6.1-sol` at High effort. The final run ended with **Positive · solution
  candidate (unverified)**, objective status `achieved`, the incremental-counting
  strategy attributed **Contributed to solution**, and a link to its saved
  artifact. The UI/report retained the caveat that no independent verification
  or formal proof checker was used. This live evaluation was not a deterministic
  test; earlier live attempts exposed a false mixed outcome and one provider
  timeout, which informed the regression and recovery-message fixes. No
  API-key billing path was used.

## A17.5 Project export and stabilization (2026-10-22)

Replaced the Project-page download icon with a single **Export project** control.
Its dialog creates either the existing v2 Project Audit JSON or a deterministic
Research Report in UTF-8 text, standalone escaped HTML, or XeLaTeX-compatible
LaTeX. The report includes project/problem details, all strategies and approaches,
chronological sessions and artifacts, lifecycle state distinct from outcome,
agentic run evidence, decisions, objections, caveats, and open obligations. It
labels agent-generated findings as provisional unless independently verified.
No model requests are used. The report API reads the same export snapshot as the
existing audit endpoint; Project Audit content and version semantics are intact.

The filename is an editable, sanitized stem with a separate extension derived
from export type/format. Changing type or format preserves the stem, and manual
extensions cannot override the selected type. The checkbox opens a safe view in a
new tab during the initiating gesture while still downloading the file; blocked
tabs leave the download available and report the condition. The dialog supports
Escape, focus restoration, narrow viewports and recoverable empty-name errors.

Reviewed and stabilized the post-A17.4 direct UI changes: natural sessions end
as `ended`, stopped sessions remain resumable, numbering comes from the durable
sequence counter after deletions, interrupted calls are not automatically
replayed, and bounded context continues from durable evidence. Removed stale
stage/kebab expectations in browser checks, verified inline Fork/Remove and
session controls, and added a synchronous duplicate-start guard. Restored
meaningful native hover titles across actionable Project, Strategy and Session
controls.

Verification on 2026-10-22:

- `./sigma test` passed all scenarios, including the new report/escaping/API
  checks, Ruff check/format, Pyright (zero errors), frontend typecheck and Vite
  production build. Starlette emitted its existing non-failing TestClient/httpx
  deprecation warning.
- `uv run --with playwright python browser_checks/a17_research.py` passed in
  real Chrome against the isolated mock provider. It verified all four export
  types, derived filenames and stem retention, unsafe/empty filename handling,
  checkbox defaults, HTML new-tab plus download, blocked-popup recovery,
  Escape/focus restoration,
  desktop/mobile dialog bounds, button hover titles, strategy actions, inline
  session controls, ended/outcome distinction, removal and monotonic numbering.
- Visually inspected `/tmp/sigma-a175-export-desktop.png` and
  `/tmp/sigma-a175-export-mobile.png`; both dialogs fit and remain legible.
  No live provider calls were made. No TeX engine (XeLaTeX, LuaLaTeX or pdfLaTeX)
  is installed here, so the escaped XeLaTeX-targeted output was checked by tests
  but not compiled to PDF.

## A16 agentic Generate Strategy notebook (2026-10-22)

Connected the project-page Generate Strategy composer to the existing bounded
Explore → fresh Challenge → coordinator workflow and A16.1 evidence records.
The UI validates ordered, run-bound SSE events and requires a complete terminal
result before presenting a draft. It shows one current action, an ordered
completed ledger, and the Critic's public summary, objections, comparison and
unresolved obligations. Candidates remain editable and unsaved until explicit
Save strategy; stopping, provider errors, malformed or incomplete streams and
cancellation leave strategy data untouched. Browser abort disconnects the
active stream and allows immediate retry. Error paths use the existing request
toast. Reduced-motion preference disables the notebook filament animation.

Fixed evidence export to list an active record with `running` status when its
terminal field is still null during cancellation. Added a regression assertion.
The browser fixture now includes a mechanism-aware Planar Regions case: its
Euler face-count strategy is materially distinct from the Sample's saved
incremental-counting baseline.

Verification on 2026-10-22: `./sigma test` passed all scenarios, Ruff,
formatting, Pyright (zero errors), frontend typecheck and production build.
Real Chrome `browser_checks/a16_agentic.py` passed with the isolated mock
provider. It verified the Maximum Regions baseline and a distinct Euler
mechanism; Counting Constrained Binary Strings' Explore/Challenge result,
cancelled-run evidence and immediate retry, editable draft, explicit save and
reopen, a distinct follow-up candidate, before/after project exports, provider
error toast recovery, missing-terminal recovery, reduced motion, and unchanged
Sample source bytes. No real-model calls or paid/account-billed quality trial
were run; qualitative model effectiveness remains unassessed. The test runner
continues to emit its existing non-failing Starlette/httpx deprecation notice.

## Candidate-solution generation and Sample return behavior (2026-10-21)

Generate Strategy now asks the selected model for **one concrete proposed
solution**, rather than a plan to investigate or evaluate possible solutions.
The proposed approach must describe the substantive mechanism or course of
action. The unsaved draft editor and saved strategy contain **only the
`approach` field**; existing auxiliary `first_tests`, `assumptions`, and
`failure_modes` response fields remain in the transport schema for compatibility,
but are no longer appended to the accepted strategy. Their eventual placement
in evaluation/rubric artifacts is a separate data-model decision. No generated
claim is represented as independently tested.

The deferred agentic Explore/Revise prompt contracts were aligned with the
solution-first requirement; the evaluator's challenge and decision logic was
not redesigned. The existing receipt, selected-account/model binding,
human-edited explicit save, and failure/cancellation guards are unchanged.

Opening a Sample creates a working project copy. On a successful open, Home's
persisted catalog preference now switches to **Recent** before navigating into
the copy; returning from the project displays Recent. Failed Sample opens
do not change that preference. Ordinary manually selected tabs remain sticky.

Updated `tests/proposals.py`, `tests/agentic.py`,
`browser_checks/a15_generate.py`, and `browser_checks/recents.py` with
regression assertions covering generation instructions, solution-only draft
persistence, and Sample-to-Recent navigation. Source and test contents were
reviewed in the repository, but **these tests and the full suite have not been
executed in this session**.

## Strategy preview and Home tab persistence (2026-10-21)

The collapsed strategy summary remains a one-line teaser. Expanding a strategy
now hides that teaser and displays the full approach without truncation.
Home remembers the Samples/Recent selection across project navigation and page
reload using the existing browser-local preference mechanism, while retaining
Samples as the default when no preference exists.

Added real-Chrome assertions to `browser_checks/recents.py` for expanding and
collapsing full strategy text, retaining Samples after a sample-project visit,
and retaining Recent after a recent-project visit and reload. Reviewed the
committed CSS, React state, and test assertions for consistency. **The browser
regression and full `./sigma test` suite have not been executed in this session**
because the local SIGMA web/API servers and repository test environment are
not accessible here. No runtime-verification claim is made.

Updated: 2026-10-21

## A14.2 ChatGPT-plan Markdown conversion recovery

Reproduced the reported case against the connected ChatGPT-plan transport using
a disposable copy of the empty-pool Mathematical sample example. The provider
returned HTTP 200 without a `Content-Type`; the previous conversion code tried
to parse the untyped body only as JSON, replaced the parse failure with `{}`,
then described that placeholder as a ChatGPT `other-object` rejection. The
local conversion endpoint returned HTTP 400, and the source and companion store
were unchanged. With the repair, an untyped but correctly framed SSE response
is passed to the shared strict Responses stream validator. Bounded JSON remains
supported, recognized provider errors keep their actionable diagnosis, and
malformed/unknown envelopes are reported as malformed output rather than as a
provider rejection. No API-key fallback or model change occurs.

The Σ control switches to rendered Markdown only after the conversion has been
validated and stored; on failure it remains on the plain source, with one
dismissible request toast and an explicit retry by selecting Σ again. Its hover
title is “Convert to markdown.”

Actual verification: one post-fix live ChatGPT-plan request to the disposable
copy returned provider HTTP 200 with no content type and local API HTTP 200;
the Markdown representation was current and nonempty, while the copied
`project.json` stayed byte-for-byte unchanged. Two earlier diagnostic requests
in the same investigation reproduced the failure and may count against plan/app
usage; all temporary project copies were removed. No live requests are used by
automated tests. `tests/text_views.py`
passed untyped SSE, completed JSON, provider rejection, malformed/partial SSE,
missing `output_text`, structured-output validation, timeout, cancellation,
source/account binding and API error preservation. Real Chrome
`browser_checks/a142.py` passed the one-toast failure, retained source/no saved
artifact, exact tooltip and explicit successful retry using a mock provider.
`./sigma test`, Ruff, Pyright, frontend typecheck/build also passed. The
existing Starlette TestClient/httpx deprecation notice remains non-failing.

## Sample project test stabilization

Updated the sample catalog scenario to cover the current behavior: each open
creates an independent copy with a distinct identity, copied projects enter
Recents, existing research is preserved, and shipped examples remain unchanged.
Added the dedicated sample-copy unit tests to `./sigma test` and updated the
agentic sample scenario to check the same copy semantics. Corrected Ruff import
ordering and formatting issues exposed by the complete run.

Verification on 2026-10-21: `./sigma test` passed all scenarios and unit tests,
Ruff, Pyright, frontend typecheck, and production build. Starlette emitted its
existing non-failing TestClient/httpx deprecation notice.

## Test suite directory migration

Renamed the source-controlled executable checks from `scenarios/` to `tests/`.
Updated `./sigma test`, Ruff and Pyright scopes, the browser-check fixture import,
test run instructions, and documented file paths. Test behavior is unchanged;
the checks remain workflow-oriented and use temporary projects and controlled
providers.

Verification on 2026-10-21: `./sigma test` passed all scenarios, Ruff, Pyright,
frontend typecheck and production build after the rename.

## Text conversion response stabilization

The ChatGPT plan conversion path now accepts either a bounded completed JSON
response or the existing validated event stream. When a plan route returns a
JSON error with HTTP 200, SIGMA reports its sanitized provider diagnostic
instead of surfacing an internal `plan_stream:content_type` parsing failure;
the source remains unchanged. The conversion scenario covers JSON success,
sanitized JSON error, and the explicit SSE content type.

Verification on 2026-10-21: `./sigma test` passed all scenarios, Ruff, Pyright
(zero errors), frontend typecheck, and production build. Several scenarios were
updated to match the current `investigation_type` serialization and six-entry
Recent Projects limit; these were stale test expectations, not runtime changes.

## Large strategy Markdown conversions

The conversion service had incorrectly reused Generate Strategy's 128 KB
provider-response limit. A complete conversion can have a larger response
envelope, especially when a ChatGPT-plan bridge omits `Content-Type` and the
client must buffer a valid SSE stream before classifying it. Text conversions
now have a separate explicit 1 MB response cap, matching the shared SSE parser;
payloads above it are still rejected without truncation or a saved conversion.
The selected model, billing path, source bounds, and validated converted-body
limits are unchanged.

Verification: `tests/text_views.py` converts an approximately 8 KB generated
strategy description from both a >128 KB API JSON envelope and >128 KB untyped
ChatGPT-plan SSE, verifies the full derived result and unchanged authored
approach, and confirms the 1 MB cap rejects oversized responses without writing
a representation. `browser_checks/a142.py` passed the failure-toast/source
retention and explicit-retry UI flow in real Chrome. `./sigma test` passed all
scenarios, Ruff, Pyright, frontend typecheck and production build; no paid API
calls were made.

## Implemented

- **ASN-1 / SPEC-001:** Local project lifecycle with persistent identity/history; shared Python services for UI, API, CLI, and scenarios. RH seed initializes once.
- **Tooling:** `./sigma setup`, `./sigma test`, and `./sigma ui`. UI launches local FastAPI and Vite servers and cleans up on exit.
- **ASN-2:** Refined branding and landing-page copy.
- **ASN-3:** Separate Home and Project screens; persistent manual strategies; keyboard-accessible contextual command hierarchy. Future commands are disabled with explanations.

## Verification

All checks below passed on 2026-10-20:

- `./sigma test`: lifecycle/strategy/API/CLI and launcher scenarios, Ruff, Pyright, frontend typecheck/build.
- Real Chrome/Playwright: open/close, browser navigation, strategy save/reload/reopen, errors, focus, action disclosures, 320px/390px layouts.
- Migration tests: v1 compatibility, exact backup, concurrent writes, corrupt data, failed saves, and external-edit detection.

Tests used temporary projects; RH data was preserved. Existing non-failing Starlette TestClient deprecation notice remains.

## ASN-3.1 verification

Verified on 2026-10-20 after pulling `38f48c4`. ASN-3 already puts the single Fork
control inside Actions, alongside Schedule and Report artifact; no UI code change
was needed.

- `uv run --with playwright python /tmp/sigma-asn31-browser.py`: real Chrome check
  passed. Fork is hidden while Actions is closed, disabled when opened, and linked
  to “Forking is not available yet.” No duplicate exists. Keyboard Enter/Escape
  and focus restoration work; 320px/390px layouts have no horizontal overflow.
- `./sigma test`: all scenarios, Ruff, Pyright, frontend typecheck/build passed.
- Temporary-project bytes and RH data were unchanged by menu interactions.
  Desktop/mobile screenshots: `/tmp/sigma-asn31-desktop.png` and
  `/tmp/sigma-asn31-mobile-320.png`; mobile screenshot visually inspected.

## Command group and button refinement

Schedule and Report artifact now form an exclusive native accordion. Only one
strategy Actions menu can also remain open, including when opened by keyboard.
Command buttons and disclosure triggers share New strategy's outlined styling,
spacing, typography, hover/pressed states and focus treatment; unavailable
commands retain their disabled state and explanation.

Verified on 2026-10-20:

- `./sigma test`: all scenarios, lint/types, frontend typecheck/build passed.
- `uv run --with playwright python /tmp/sigma-accordion-browser.py`: real Chrome
  verified mouse/keyboard exclusivity, matching computed button styles and hover,
  disabled commands, Escape focus restoration, and 320px/390px layouts. Temporary
  project data stayed unchanged; no JavaScript errors. Visually inspected
  `/tmp/sigma-accordion-320.png`.

## Corrected strategy command hierarchy

The strategy-name chevron now reveals three sibling groups: Scheduling, Artifact,
and Actions. There is no visible top-level label. Fork appears only under Actions,
with its disabled state and explanation preserved. Group/menu exclusivity and the
shared outlined control styling remain in place.

Verified on 2026-10-20: `./sigma test` passed. Real Chrome check
`uv run --with playwright python /tmp/sigma-command-hierarchy.py` passed for the
three-group hierarchy, Fork containment, one-at-a-time expansion, keyboard and
Escape focus, and desktop/390px/320px layouts. No JavaScript errors or data
changes; `/tmp/sigma-command-hierarchy-320.png` visually inspected.

## Strategy Edit and Remove

Actions now contains working Edit and Remove commands alongside unavailable Fork;
Remove is no longer in Scheduling. Edit opens a prefilled name/description dialog.
Remove confirms the named strategy and removes it from the active pool, retaining
its full research record and history. Cancel/Escape restores chevron focus; errors
retain dialog text. Edit history exposes before-and-after values under View changes.

The shared services, API and CLI support both operations. First edit/removal of a
v2 project atomically publishes v3 after preserving an exact `project.v2.json`
backup. Identity/authorship/creation time remain unchanged. Removed records remain
in inspection; active-list queries exclude them. Unchanged edits append no event.

Verified on 2026-10-20:

- `./sigma test`: all lifecycle/strategy/edit-removal/API/CLI/launcher scenarios,
  Ruff (twelve Python files), Pyright, frontend types/build passed. Scenarios cover
  backup migration, audit chains, no-op edits, rejection of invalid/removed IDs,
  failed writes, retry, concurrency and corrupt edit/removal histories.
- `uv run --with playwright python /tmp/sigma-edit-remove-browser.py`: real Chrome
  passed prefilled edit, cancellation/Escape/focus, injected failures with retained
  text and retry, persistence after reload/reopen, history before/after values,
  and confirmed removal returning the empty pool. 320px/390px dialogs fit without
  horizontal overflow; no JavaScript errors. Test projects were temporary; RH was
  byte-identical afterward.
- Visually inspected `/tmp/sigma-edit-dialog-320.png` and
  `/tmp/sigma-remove-dialog-320.png`. UI server restarted for the new API.

## ASN-5: approved Strategy Pool workspace

Implemented the supplied workspace identity with a compact transparent metallic
header logo, dark navigation rail, quiet navy canvas, copper/gold New strategy
control, bordered strategy list, and matching forms/dialogs/history. All workspace
rules are isolated in `frontend/src/workspace.css` under `.workspace-page`; older
conflicting workspace header rules were removed. Home JSX and Home-specific CSS
were unchanged. Backend routes, data models and persistence were unchanged.

Asset gate passed: supplied reference is a valid 1705×922 RGB PNG; logo is a
385×96 RGBA PNG with real alpha (range 0–255, transparent corners). Originals are
retained under `assets/`; the public logo copy is byte-identical. No artwork was
regenerated, and the reference screenshot is never served as a UI background.

Actual verification on 2026-10-20:

- Merged `origin/main` through `dc98916` while preserving the local artwork commit
  and pre-existing Home asset modifications. Those Home changes remain unstaged.
- `./sigma test`: all lifecycle/strategy/change/API/CLI/launcher scenarios, Ruff,
  Pyright, and frontend typecheck/build passed. Corrected a pre-existing Ruff
  formatting failure in the CLI smoke test's final print statement; no behavior
  changed. Existing non-failing TestClient warning remains.
- `npm --prefix frontend run build`: final workspace build/typecheck passed.
- `uv run --with playwright python /tmp/sigma-asn5-browser.py`: real Chrome passed
  Home/project/close/back/forward, actual RH opening, temporary strategy creation,
  full descriptions, edit/retry/reload, removal/cancel/reopen, retained history,
  keyboard accordion/focus, skip navigation, loading and error states, disabled
  future controls, and reduced motion. No JavaScript errors; RH file unchanged.
- `uv run --with playwright python /tmp/sigma-asn5-home.py before` and `after`:
  Home screenshots were byte-identical at 1705×922, 1440×1200, 768×1024, 390×844,
  and 320×844. Home source and the pre-existing Home asset hashes also matched.
- Workspace screenshots at those five sizes have no page-level horizontal
  overflow. Inspected `/tmp/sigma-asn5-workspace-1705.png`, `-768.png`, `-320.png`,
  `/tmp/sigma-asn5-edit-mobile.png`, and `/tmp/sigma-asn5-commands-mobile.png`;
  compared the desktop composition with `assets/sigma-workspace-reference.png`.
  Mobile rail scrolls within its own row; the command panel stays within the
  viewport and scrolls when necessary.

Intentional differences from the concept: no title-area Sigma/waves, search or
status filters, invented statuses/IDs/dates, View actions, settings/theme tools,
or nonfunctional project selector. The real title/problem, full approaches,
author/creation metadata, commands and history are preserved. Future destinations
are disabled and marked Later. These are the assignment's prescribed deviations;
no required interactions or visual checks remain blocked.

## ASN-6: Home project commands and research modes

Implemented matched Open Project / New Project dialogs and a resting Home command
pair, stacked on mobile with no path input. Open retains truthful local-path
entry; New previews its server-derived destination and asks only for name,
multiline problem and mode. Both dialogs support keyboard focus, Cancel/Escape,
retained inputs on failure and duplicate/busy protection. Created projects open
the real workspace. Research mode appears in collapsed Project details.

Shared services, API and CLI support managed creation under the checkout's
`projects/` root or an explicit existing owned `SIGMA_PROJECTS_ROOT`. Exclusive
name reservation and staged publication reject existing directories/files,
including symlinks, and preserve concurrent research during rollback. New schema
v4 persists Default/Mathematical; legacy v1–v3 reads default without rewriting,
retaining existing migration/backup and history semantics. See
[design](../tickets/t6-design.md) and [decisions](DECISIONS.md) for limits.

Actual verification on 2026-10-20:

- `./sigma test`: lifecycle, managed project creation, strategies, edit/removal,
  API, CLI and launcher scenarios all passed; Ruff check/format (13 Python files),
  Pyright (0 errors), frontend typecheck and production build passed. Existing
  non-failing Starlette TestClient deprecation warning remains.
- New `tests/project_creation.py` verifies both modes on disk and reopen,
  legacy v1/v2/v3 no-write reads, preserved strategy/history semantics, invalid
  modes/fields/names, Unicode naming, collisions, missing/foreign/symlink roots,
  injected publication failures, concurrent files and eight competing creators.
- `uv run --with playwright python /tmp/sigma-asn6-browser.py /private/tmp/sigma-asn6.15KfaQ`:
  real Chrome passed both Home commands, keyboard opening/cancel/focus restoration,
  bad-path and injected-create error recovery with retained text, both persisted
  modes, reload/reopen/back/forward, readonly destination/collision validation,
  two synchronous submissions yielding one request, disabled busy controls/Escape,
  arbitrary existing paths, strategy create/edit/remove and audit history. No JS
  errors; RH state unchanged. Browser-navigation assertions wait for Home to settle
  before traversing history.
- Resting Home and creation dialogs checked at 1705, 768, 390 and 320px; no page or
  dialog horizontal overflow. Visually inspected desktop/320px Home and New
  screenshots, plus 320px Open. Screenshots are `/tmp/sigma-asn6-home-*.png`,
  `/tmp/sigma-asn6-new-*.png` and `/tmp/sigma-asn6-open-320.png`.
- `/tmp/sigma-asn6-workspace.py before` / `after`: full-page workspace screenshots
  byte-identical at 1705×922, 768×1024, 390×844 and 320×844. ASN-5 styles unchanged.
- Accepted pre-existing canonical Home art was preserved and committed as-is;
  SHA-256 `eeb16d623f1723d98e8c9a157603d923c2ca8cfc728483804e20b96da5cd9529`
  matches canonical, generated runtime and browser-served bytes. Deleted the
  generated runtime copy and rebuilt successfully to verify automatic restoration
  from `assets/`. No artwork regeneration or ASN-4.1 animation.
- Browser creation tests used a temporary root; launcher restored to the default
  `/Users/admin/sigma/projects` and destination endpoint verified. A project named
  “My basic project” created during that session was copied without overwriting to
  the default root with identical document bytes; original retained.

Limitations remain local POSIX storage and path-based Open (no native picker).
Crash leftovers and ambiguous lost responses are documented; artifact engines,
recent-project indexing and agent functionality remain deferred.

## A7: Strategies workspace and human-reviewed AI proposals

Implemented the approved compact Strategies workspace with two-level rows,
full-approach disclosure, vertical three-dot commands and upper-right grips.
New Strategy is a single warm split action: primary Write manually, dropdown
Write manually / Generate with AI. Stage rings include text and are explicitly
manually tracked: Draft, Ready to explore, Exploring, On hold. No automatic
research activity or evaluation is claimed. Existing edit/remove/history and
Open/Close remain functional; removed research stays in the project.

Order is durable and active-only, with pointer, Chrome touch, and keyboard
pick-up/move/drop/cancel. Previews do not save; errors revert; stale concurrent
order/active-list changes are rejected. Schema v5 validates order/stage audit
replay and adds optional summary/provenance. V1–v4 reads remain unchanged with
creation-order/Draft defaults and exact backups on actual v5 updates. Existing
manual-only lazy migrations remain compatible.

OpenAI Responses integration is opt-in and server-configured (`SIGMA_AI_ENABLED`,
`OPENAI_API_KEY`, optional `SIGMA_AI_MODEL`, default `gpt-4.1`). Generate returns
one strictly validated, unsaved draft. Context disclosure/consent, optional seed,
editable review, explicit regeneration, human acceptance and provider/model
provenance are implemented. Server timeout/concurrency/context/output bounds,
lexical duplicate rejection and request cancellation are enforced. No keys or
prompt dumps are stored in projects or browser bundles. No paid calls were made.

Actual verification on 2026-10-20:

- Asset gate: exact supplied `assets/sigma-strategies-reference.png` inspected,
  1672×941 PNG, SHA-256
  `9cf973b6552f755061b8f45aecbfdd17275a1e6b50bd84a4ce0536da13e49858`.
  Retained as reference only. Original Home PNG and workspace logo hashes match
  the A6 baseline. Obsolete unused SVG logos removed after checking references;
  Home/atmosphere assets retained.
- `./sigma test`: all lifecycle/project-create/strategy/change/tracking/proposal/
  API/CLI/launcher scenarios passed, plus Ruff check/format (16 files), Pyright
  (0 errors), frontend typecheck and production build. The existing non-failing
  Starlette TestClient deprecation warning remains.
- `tests/strategy_tracking.py`: v1–v4 no-write reads/defaults, exact backups,
  active-only order, removed history, stable IDs/timestamps, no-ops, failed saves,
  stale order, competing reorder/stage/edit writes, corruption and API/CLI checks.
- `tests/proposals.py`: exact official Responses endpoint/payload, strict
  schema/full context, empty/seeded generation, no mutation until human-edited
  acceptance, signed provenance, unavailable/invalid config, bad/refused/
  incomplete output, rate errors, lexical duplicate, timeout, concurrent requests,
  oversized context and cancellation. ASGI middleware/endpoint disconnect replay
  confirms cancellation joins the adapter and releases its request slot.
- `uv run --with playwright python browser_checks/strategies.py`: real installed
  Chrome passed desktop/manual/stage/menu/detail flows, keyboard reorder/cancel,
  save rollback, reload, desktop pointer drag, actual CDP touch drag/drop/cancel,
  narrow layouts, AI fixture error/retry/review/edited acceptance and cancellation,
  and reduced motion. No JavaScript errors. These are browser touch-emulation
  checks, not physical-device testing. Provider is an explicitly identified
  HTTP fixture on a separate API port, forwarded only in the test browser.
- `uv run python browser_checks/http_cancel.py`: real HTTP disconnect against the
  fixture cancels an in-flight request, permits an immediate next request, and
  leaves project bytes identical. This caught/fixed receive-channel polling that
  missed disconnect events behind middleware. No claim of live provider billing
  cancellation: OpenAI may already have processed a sent request.
- `uv run ruff check src tests browser_checks` and format checks passed.
  Browser fixture/checks are source-controlled and documented separately from
  `sigma test`; they require installed Chrome and Playwright.
- Compared actual workspace at 1672×941 with the approved reference; inspected
  screenshots for split menu, clamped Actions menu, expanded approach, lifted
  touch row, 768/390/320px layouts and desktop/mobile draft review. Artifacts are
  `/tmp/sigma-a7-workspace-*.png`, `-split-1672.png`, `-actions-1672.png`,
  `-detail-1672.png`, `-touch-lift-390.png`, and `-ai-review-*.png`.
- Home before/after screenshots byte-identical at 1672×941, 768×1024, 390×844 and
  320×844 against the A6 implementation. Actual default server checked for
  unavailable-provider messaging, disabled Generate, Escape/focus restoration,
  RH Open/Close and browser back/forward. RH document, Home art and logo bytes
  remain unchanged. Tests used temporary projects only.

Intentional differences from the mock: omit invented S-IDs/sample data; full UUID
and real creation metadata live in expanded details. Stages reflect human work
rather than fictitious automated evaluation. Unimplemented rail destinations
remain disabled/Later; retain actual project title and Close instead of fake
selector/theme/settings controls. Small +/− detail affordances expose full text;
manual writing retains its working inline composer. On mobile the rail scrolls,
rows stack stage labels, and menus/dialogs fit the viewport. Draft review collapses
context after generation. No Home changes or A4.1 animation.

Live OpenAI account access, billing and mathematical proposal quality were not
verified: controlled HTTP fixtures exercised the real adapter and no paid calls
were authorized. Set the documented server environment and make an explicit user
request to use live generation. Semantic novelty/proof validity still require
human judgment; no runner, evaluator, branch lineage or artifact engine is added.
The UI is running normally with default project location; the test fixture server
is stopped after verification. See Getting Started for setup/limits and Decisions
for schema/concurrency/receipt tradeoffs.

## A8: shared project settings, curated models and real API status

Implemented one Create/Edit project dialog (exact headers/actions), the small
44px pencil beside the project heading, and transactional name/problem/mode/model/
Thinking level updates. Creation retains its readonly managed destination; Edit
never moves it. No-op, Cancel/Escape and Close do not save. Successful edits update
the workspace in place and return focus; failed/stale saves retain entered values.
All new init/create operations persist schema v6. Legacy v1–v5 reads stay unchanged;
first settings updates make an exact version backup and retain UUID, strategies,
stages, active order, archived records and prior events. Strict `project.updated`
before/after chains and expected-settings conflict checks protect concurrent edits.

Reviewed Sol/Luna/Astra choices use four compatible efforts (High default), with
relative $/$$/$$$ cost tiers and official pricing link. Official model pages were
opened/verified on 2026-10-20 for text, Responses, strict JSON and reasoning support;
references are in Getting Started and `model_catalog.py`. No token prices are
inferred from `/v1/models`. Fresh account discovery intersects known IDs only;
unavailable/unverified choices are qualified and stored selections are retained.
Sol/High is preferred when verified accessible; alternate initial defaults and
provisional offline Sol/High are explicit. Unreviewed bootstrap overrides are
called out; saved project settings win. Requests never substitute another model
or drop/lower effort. Proposal receipts and new provenance bind requested effort
and actual returned model to the immutable request snapshot.

The upper-right dot/text now verifies actual API authentication with bounded
GET /v1/models. Checking/missing/auth/permission/rate/network/invalid/stale states
are distinct; green means only fresh valid HTTP 200 authentication/reachability,
not selected-model generation, credits, quota or billing. Requests coalesce/cache
for 60 seconds (3-second Retry cooldown), with 8-second deadline and response bounds.
The browser checks once on app load, reuses state across routes, and expires green
without polling. No credential/raw provider error/catalog is exposed to React.
Workspace status space is reserved; Home uses existing header/sky space.

Actual verification on 2026-10-20:

- Final `./sigma test`: all lifecycle/create/settings/model-connection/tracking/
  proposal/strategy/edit/remove/API/CLI/launcher scenarios passed. Ruff check/format
  (20 files), Pyright (0 errors), frontend typecheck and production build passed.
  Existing non-failing Starlette TestClient deprecation notice remains.
- `tests/project_settings.py`: explicit model/High creation, v1–v5 no-write
  defaults, no-op, exact backups, both mode directions, stable identity/location/
  archived research/order, failed writes, stale editor races, independent strategy
  changes, strict corrupt audit rejection, and API/CLI update/conflict checks.
  Empty/unknown models and unsupported efforts are rejected without creating files.
- `tests/model_connection.py`: valid curated discovery (unreviewed models do
  not escape), coalescing eight calls into one, cache/TTL/Retry, zero accessible
  choices, missing setup, 401, 403, 429, 500, redirect, malformed/oversized responses,
  network failure and timeout. Controlled Responses fixture verifies saved model
  plus real `reasoning.effort` (including High and Extra high across scenarios),
  strict schema, 25,000-token bound, no pre-acceptance mutation, concurrent settings
  snapshot/provenance, unavailable model/no fallback and offline metadata edits.
- `uv run --with playwright python browser_checks/settings.py`: real Chrome passed
  shared field order/Create/Edit headers, Sol/High, pencil keyboard opening and
  return focus, no-op/cancel, failed create/update retry, duplicate synchronous
  submits/busy/Escape guard, both mode/model/effort changes, reload, UUID/path/audit
  retention, stale edits preserving unsaved text, explicit unsupported-effort
  correction, unavailable-model retention and actual offline metadata save.
  Status checks cover initial Checking/no green, authenticated fixture green,
  key/permission/rate/offline/unconfigured alternatives, stale success, safe details
  and Retry access. No JavaScript errors. Screenshots at 1672/768/390/320px are
  `/tmp/sigma-a8-create-*.png`, `-edit-*.png`, and `-status-*-320.png`.
- Real 320px Chrome stress check: unbroken 200-character title, long visible problem
  and 20,000-character form problem fit without horizontal overflow; Escape keeps
  document bytes and returns focus. Screenshot: `/tmp/sigma-a8-long-edit-320.png`.
- `uv run --with playwright python browser_checks/strategies.py` and
  `uv run python browser_checks/http_cancel.py`: A7 manual/edit/remove, stage,
  keyboard/mouse/CDP touch reorder/drop/cancel, rollback/reload, AI draft review/
  human acceptance/cancellation and actual HTTP disconnect/slot release all pass.
  Tests use explicitly identified no-network provider fixtures and temporary
  projects, not physical-device or live API-account claims.
- `uv run ruff check src tests browser_checks` and corresponding format check
  passed (24 files). Browser fixture and A8 checks are source-controlled and
  documented separately from the standard suite.
- Compared current UI with a temporary checkout of actual A7 `2a8f90b`, serving the
  same approved PNG. `/tmp/sigma-a8-compare.py` with Playwright/Pillow confirmed Home
  pixels outside the requested header/sky status area identical at 1672×941,
  768×1024, 390×844 and 320×844. The initial baseline captured before Vite served its
  generated public image was rejected; comparisons awaited decoded art and visible
  UI. Strategy list at desktop is pixel-identical; tablet/mobile lists have the
  same dimensions/composition (up to one screenshot crop pixel), visually reviewed.
  Header height changes alter gradient/capture phase, not row styling. Artifacts:
  `/tmp/sigma-a8-home-reference-*.png`, `-home-current-*.png`, and
  `-strategies-reference/current-*.png`. Temporary reference server/worktree removed.
- Fresh dev startup test removed only the generated public Home copy and restarted
  `./sigma ui`: new config-evaluation copy served HTTP 200 `image/png` on first
  launch with exact canonical bytes. Fixes the older late buildStart copy, which
  could miss Vite's initial public-file scan. Human copying is not required.
- RH document, canonical Home PNG and workspace logo hashes match the pre-A8
  baseline; existing untracked `models.json` also stayed byte-identical and is not
  committed or used as authentication proof. No image generation or A4.1 animation.
  Test API fixture server is stopped; normal UI runs with default project root.

Limits: no live OpenAI generation/billing/quality check was performed; all provider
integration uses controlled HTTP fixtures. Normal server currently reports Not
configured, never fake green. Configure server API enablement/key and restart to
check real authentication; an explicit user request is needed for billable
proposals. Higher thinking may hit the unchanged 60-second deadline or 25,000-token
budget; failures never downgrade or retry automatically. API/catalog changes need
deliberate review. Past missing effort remains unknown. No cost accounting,
per-strategy settings, agent work or Close-time save/confirmation is introduced.

## Current boundaries

No live agents, scheduler, evaluator, generated reports, forks, paid calls, or hosting. Local POSIX storage limitations and migration behavior are in [DECISIONS](DECISIONS.md). Run instructions are in [Getting Started](GETTING-STARTED.md).

## Project dialog terminology correction

Per user request, the creation dialog heading and submit button now say “New Project” to match Home. Edit Project / Save Changes are unchanged. Updated browser-check expectations. Validation: `./sigma test` passed (scenarios, API/CLI, Ruff, Pyright, frontend typecheck/build); real Chrome confirmed both dialog labels.


## A8.1 — automatic local configuration and safe UI replacement

Implemented the one-command startup/restart fix independently of A9. `./sigma ui`
loads checkout-root `.env` with pinned python-dotenv 1.2.1 before spawning the API;
quoted `export` assignments work without sourcing. Environment values win. The
whole file is validated before mutation; absent is normal, malformed/unreadable
files get safe actionable diagnostics without raw contents. CLI project commands
and the standalone backend factory share the loader. Setup/test avoid loading it.
AI enablement and explicit billed-generation consent are preserved.

A private owned 0700 state directory, no-follow launch lock and canonical
path/device/inode identity handshake coordinate same-checkout replacement.
Shutdown is requested through a private Unix socket; the old supervisor confirms
both server guardians have exited before the replacement starts. Pipe guardians
own the actual child groups and clean up after supervisor crashes as well as
normal stops. No recorded PID or occupied port authorizes a signal. Stale refused
owned sockets recover automatically. Unverified state, other checkouts and unrelated
listeners cause a named safe conflict. Ports remain fixed at 8000/5173; no dynamic
fallback or relaxed host/origin checks. Readiness verifies the per-launch public
instance ID at the API and through Vite before announcing the URL. No project/UI
artwork or Close behavior changed. README, Getting Started, decisions and a
placeholder-only `.env.example` document the behavior.

Actual verification:

- `./sigma test` passed: all existing research lifecycle/settings/strategy/provider
  scenarios, API/CLI checks, launcher failure/interrupt checks, new dotenv and
  ownership scenarios, Ruff check/format (27 files), Pyright (zero errors),
  frontend TypeScript check and production build. Existing non-failing Starlette
  TestClient deprecation notice remains.
- `tests/local_config.py`: missing file, quoted export/single/plain/empty
  values, comments, explicit environment precedence (including disabled AI),
  literal shell/variable syntax without execution/expansion, no key output,
  atomic malformed-file rejection, UTF-8 and unreadable-file safe diagnostics.
- `tests/instance_ownership.py`: canonical alias and changing symlink target,
  different checkout IDs, directory permissions/symlink refusal, non-socket state
  preservation, refused stale-socket recovery, live wrong-identity refusal without
  sending shutdown or removing its endpoint, and no-follow lock protection.
- `uv run --with playwright python tests/ui_lifecycle.py` passed against
  disposable real checkouts and explicit no-network provider fixtures. Started
  actual `./sigma ui` from another working directory; a fresh second invocation
  loaded updated `.env`, verified the new model availability, and let the old
  supervisor exit zero with both old child trees gone. API and frontend proxy,
  allowed/forbidden origins, Chrome's authenticated-fixture connection status
  and New Project dialog passed. Ctrl+C and SIGTERM cleaned up; actual supervisor
  SIGKILL left a stale socket and pipe guardians recovered automatically. Rapid
  concurrent launches serialized to one working owner. A different checkout and
  unrelated listeners on each default port survived safe refusal. Fixture logs
  contained no key; provider transport allowed only GET /v1/models. Source project
  file hashes and temporary research sentinel stayed unchanged.
- Also exercised actual normal-checkout `./sigma ui` followed by `./sigma ui`:
  the second invocation printed the restart message and became ready while the
  old command exited cleanly. Normal launcher is left running after verification.

Limits: real-process/Chrome checks were run on macOS, not Linux or a physical
browser device. The opt-in lifecycle check requires free default ports and Chrome
at its documented macOS location. An older launcher without the ownership protocol
cannot be safely replaced automatically; its own controls must stop it once.
Same-user malicious processes are outside the private-directory trust boundary.
No paid generation or live provider billing/quality verification was performed.
Existing untracked `models.json`, local `.env`, project research and artwork are
not committed or rewritten by this change.

## A8.2 — ChatGPT connection and explicit billing modes

Implemented documented local OSS Sign in with ChatGPT. The repository's public
visibility and Apache license were checked, and current official SIWC discovery,
registration, session, token, model/inference, preview and UI documentation was
read before implementation. Exact sources and security decisions are in
[../tickets/t8.2-security.md](../tickets/t8.2-security.md).

Home/workspace reuse the small top-right account control: Connect AI, official
Continue with ChatGPT button, connected/account/usage/reconnect states, account
switch/add, disconnect, and explicit advanced API-key billing. Manual work needs
no connection, key, .env or enable flag. A present key never selects billing;
SIGMA_AI_ENABLED no longer gates runtime behavior. Plan failures never use a key.

Backend-owned PKCE/state/nonce and real loopback callback validate signed RS256
OIDC identity, issued client/account binding, scopes and expiration. Stable host
and separate registrations persist in private owner-only application storage,
never projects, Git, Vite or React. Refresh rotation serializes across processes;
terminal errors retain registration for reconnect. Invalid-grant code retries
retain the issued client transiently. Disconnect reports unconfirmed revocation
honestly. Account storage failures keep manual model defaults available.

On-demand sign-in retains seed/draft and resumes one initiating generation,
checking project/account bindings and cancellation. Header sign-in does not
generate. Plan requests use the required bounded SSE Responses contract and
preview-compatible body; API-key requests keep their existing contract. Both
retain strict proposal validation, returned-model/effort receipts, explicit human
Save Strategy and schema v6. No recurring consent checkbox or automatic saving.
One-time welcome is informational. Existing SIGMA artwork is unchanged; the
sign-in mark is the unmodified official asset. A9 remains separate.

Actual verification:

- `./sigma test` passed all scenarios, API/CLI checks, Ruff, Pyright (zero errors),
  frontend typecheck and production build. Existing non-failing TestClient
  deprecation notice remains. Final frontend build and Ruff check/format over
  `src`, `tests`, and `browser_checks` passed (39 Python files); final Pyright passed.
- `tests/chatgpt.py`: real loopback callback and generated RSA-signed OIDC
  fixtures verify PKCE/exact code exchange, stable host/issued client, nonce,
  state, issuer/audience/signature/expiry/subject/client rejection, missing tokens,
  duplicate callback race, cancellation/decline, discovery endpoint validation,
  scope denial/enablement, distinct same-email registrations, both catalog shapes,
  strict completed SSE and malformed/out-of-order/incomplete/failed/oversized
  errors, explicit API mode without flag, no billing fallback or sign-in writes,
  project/account binding, terminal refresh and confirmed/unconfirmed revoke.
  Added invalid-grant retry and unreadable-store/manual-default checks passed.
- `tests/chatgpt_restart.py`: two fresh real processes contending for an
  expired rotating session performed exactly one refresh, retained host/account/
  client identity, and atomically stored the replacement with 0600 permissions.
- Real Chrome `browser_checks/chatgpt.py` passed manual project/strategy creation
  while disconnected, cancelled/declined login preserving a nonempty seed, signed
  simulated authorization resuming exactly one SSE generation, no pre-acceptance
  project write, one explicit human save, actual returned-model provenance,
  welcome once/reload without generation, account menu/switch, explicit API billing,
  expiry/offline/permission/usage-limit states, keyboard focus and no JS errors.
  Responsive screenshots at 1280x720, 1440x900, 390x844 and 320x844 are under
  `/tmp/sigma-a82-*.png`; desktop and mobile menu captures were visually inspected.
- Existing `browser_checks/settings.py`, `browser_checks/strategies.py`, and
  `browser_checks/http_cancel.py` passed with explicit no-network API-key fixtures.
  Settings CRUD/conflicts/offline preservation, manual strategy CRUD/stages,
  mouse/keyboard/touch ordering, draft review/acceptance and actual HTTP
  disconnection/cancellation all remain working. Fixture startup now explicitly
  selects dummy key billing; production never does so automatically.
- `tests/ui_lifecycle.py` passed real fresh-shell restart with updated .env,
  explicit persisted key-mode selection, proxy/origin routing, old owner/children
  gone, Ctrl+C/SIGTERM, hard-crash pipe cleanup/stale recovery, rapid launches,
  different checkout and unrelated listener refusal, and unchanged research.
- Normal launcher was restarted; real Chrome confirmed Home/account control and
  official sign-in asset without starting live OAuth or generation.

Limits: all OAuth and inference verification uses controlled fixtures. Live
sign-in, account/workspace eligibility, structured-output admission, plan capacity
and billing/quality have not been verified or consumed. Live testing requires an
explicit user request. Private files protect against other OS accounts, not code
already running as this account; a crash between remote token rotation and local
publication can require reconnect. Tested on macOS/Chrome, not physical devices
or Linux. A9's Recent Projects and dialog-header correction are not implemented
here. Local .env, existing research, canonical artwork and untracked models.json
are not committed or rewritten.

## A9 — four recents, included exercise and visible dialog controls

Implemented a private application-level four-item LRU keyed by existing project
UUID. Successful create/open services and explicit API/CLI init record canonical
path and actual access time; inspect, edits and Close do not reorder or write the
index. Home reads fresh titles/minimal metadata, opens actual projects, disables
unavailable entries and can forget a pointer without deleting research. Creation/
recent navigation passes its already-loaded view into the workspace, avoiding an
incidental second Open write. Index state uses an owned 0700 XDG/per-user directory,
0600 no-follow index/lock, multiprocess serialization and atomic fsynced writes.
Index failure warns separately from an already successful research operation.

The supplied Mathematical template is installed byte-for-byte with validated v5
schema/UUID/history and exclusive no-replace publication. Existing same-UUID
research is preserved; other occupants/symlinks report a conflict. Per-root
bootstrap facts prevent reinstatement after deletion/forgetting/eviction and do
not displace four real accesses. Initial inclusion says Included example and has
no invented last-opened time. Opening shows the three real Draft strategies;
normal edits evolve the copy independently of the unchanged Git template.

New/Edit Project now use a title/action header (Create or Save Changes, Cancel)
and one scrolling body in one native form. The header remains visible at laptop
and mobile sizes; busy buttons/Escape, native validation, duplicate guards,
errors/retry and focus restoration remain operational. No artwork redesign or
provider behavior change. Future Markdown/LaTeX transcript rendering is documented
in agent-output-design.md, without implementing execution or hidden reasoning.
Independent mathematical verification is outside the active project template.

Actual verification:

- `./sigma test` passed all existing and new scenarios, API/CLI checks, Ruff,
  Pyright (zero errors), frontend typecheck and production build. Existing
  non-failing TestClient deprecation notice remains. Final targeted recents
  scenarios, Ruff check/format over `src`, `tests`, and `browser_checks` (43 files) and
  Pyright passed after the state-path guard and extra failure cases.
- `tests/recents.py`: exact first/second bootstrap, strict seed/event/strategy
  identity, five creates/four-entry eviction, actual API/CLI accesses, repeated
  opens, Close/inspect/title-refresh byte immutability, renamed/moved/corrupt
  projects, forget/no reseed, concurrent real processes/threads and parallel
  bootstrap. Full genuine lists survive inclusion; bad templates, publication
  failure, edited existing seed, other-project collisions, symlinks, root switches,
  corrupt index and failed index replacement preserve research. State permissions
  and refusal of checkout/project-package state locations are checked. The two
  expected index-failure warnings demonstrate secondary-error handling.
- `tests/example_math.py`: independent residue/adjacency DP cross-checked by
  exhaustive enumeration through n=12 gives a_12=128; recurrence checked through
  n=120. Exact arithmetic in Z[omega] verifies three-step traces, determinant and
  Cayley–Hamilton identities in all phases. The analytic root-of-unity recurrence
  and density proof is in docs/example-math-verification.md; no proof/answer was
  inserted into the unproved seed and no agent/Lean activity is claimed.
- Real Chrome `browser_checks/recents.py` passed actual example opening with three
  Draft strategies, first inclusion versus actual access, five UI creations,
  eviction, Open/recent click UUID deduplication, corrupt/unavailable/forget flow,
  unchanged template and zero JavaScript errors. Measured header button bounds
  at 1280x720, 1440x900, 390x844 and 320x700 for Create and Edit before/after body
  scroll, long problem/help/localized labels, save spinner, Escape/duplicate guard,
  failure with retained text and successful retry. Confirmed no second post-create
  Open request. Home also checked at 768x1024. Captures: /tmp/sigma-a9-*.png;
  desktop Home and 320px Edit were visually inspected.
- Existing real Chrome `browser_checks/settings.py` passed shared form defaults,
  field/pair validation, offline retention, create/edit/no-op/conflict/error/retry,
  UUID/history preservation, keyboard/focus, responsive and connection-state
  checks. Fixtures use isolated app/credential/project roots and no live provider.
- Normal `./sigma ui` safely replaced its prior instance and became ready, with
  the included example installed in the configured root. Canonical artwork and
  source example bytes remain unchanged; no tracked live research was added.

Limits: local cooperative POSIX locking and same-OS-account trust boundary remain.
Research publication and secondary-index updates are not one cross-file atomic
transaction; a failed index update can be retried by a later explicit Open without
resubmitting creation. A hard crash can leave an empty reserved example directory;
existing directories are inspected, never silently reset. Up to four full project
files are validated server-side to refresh metadata, while the browser receives
only the small index view. Chrome checks used macOS emulation, not physical
phones or Linux. No paid calls, autonomous agents or transcript renderer. Existing
untracked models.json and local .env remain unmodified and uncommitted.

## A8.2.1 — quiet, current connection status

AI connection health now refreshes centrally in `AIProvider`, once per app rather
than once per header. For the current 60-second check TTL, a visible connected
ChatGPT or API-key account is checked at 48 seconds. Hidden tabs pause scheduled
requests and resume with one due check. Background checks leave the header label
steady; manual Retry shows progress only in the account popover. Repeated network
or provider-unavailable failures show a neutral actionable warning after a
transport failure, retain a known provider-specific unavailable label, and retry
with visible-only 30/60/120-second backoff capped at five minutes. A successful
check or deliberate account/mode change resets backoff. No-account states are not
polled. Old in-flight results are discarded after sign-in, account/mode changes
or Disconnect. The A8.2 one-time welcome acknowledgment remains unchanged.

Actual verification:

- `./sigma test` passed all scenarios, API/CLI checks, Ruff, Pyright (zero errors),
  frontend typecheck and production build. The existing non-failing Starlette
  TestClient deprecation notice remains.
- Real Chrome `browser_checks/connection_refresh.py` passed with a controlled
  clock and mocked browser fetches: repeated 48-second refresh cycles, no header
  flash while background/manual checks are held open, hidden-tab pause and one refresh on
  return after expiry, transient failure warning and 30-second retry, manual
  recovery, stale successful response rejected after Disconnect, and welcome
  acknowledgment only once across multiple checks and reload. No provider calls.
- Real Chrome `browser_checks/chatgpt.py` passed against the signed local OAuth
  fixture: disconnected manual work, cancelled/declined and successful sign-in,
  one explicit strategy save, account controls, separately billed API mode,
  outage/limit/permission/reconnect states, and responsive 1280/1440/390/320px
  layouts. No live sign-in or billable inference. Final frontend build/typecheck,
  Ruff check/format (45 Python files), and Pyright all passed after changes.

Limits: the verified status remains a bounded non-generating model-catalog
authentication/reachability check; it does not establish inference entitlement,
credits, quota or billing. Browser refresh behavior was controlled-clock tested;
no live provider state or physical mobile device was used.

## Home copper artwork update

Home now uses the approved copper background and static slogan artwork. Vite
copies both source PNGs byte-for-byte from `assets/` into `frontend/public/`;
the originals remain unchanged. The slogan is blended with `screen` and feathered
at its edges so its dark canvas does not form a hard rectangle. Home actions stay
below the raised Σ/SIGMA mark, and the connection control remains in the upper
right. The responsive crop keeps the background image's aspect ratio.

Actual verification:

- Real Chrome screenshots at 1440x900, 390x844 and 320x700 were visually
  inspected (`/tmp/sigma-verified-*.png`). The connection control clears the
  slogan and Σ at each size, the actions remain below the artwork, and no
  horizontal overflow was measured. This was browser emulation, not physical
  mobile hardware.
- `npm run build` passed TypeScript checking and the Vite production build.
- `./sigma test` passed lifecycle and project creation scenarios, then stopped
  in `tests/recents.py:204`. Its bad-template check patches
  `sigma.recents.TEMPLATE`, but `bootstrap_example()` calls `_install(root)` whose
  default `template=TEMPLATE` was bound when the function was defined, so the
  fixture patch is not observed and its assertion fails. This failure occurs in
  existing scenario/application code, unrelated to the Home artwork change; the
  later checks in that command did not run.

## A11 — copper Home controls and sample catalog

Home now offers Samples and Recent Projects tabs, with Samples selected on
entry per the later UI request. The catalog discovers every valid shipped
investigation and places the Jesus example last. Selecting a Sample row opens the
project directly with no dialog, creating an independent working copy with its
own identity and a distinct path. The original source remains byte-for-byte
unchanged, and opened copies appear in Recents. Existing automatic sample recent
entries are removed from the index on read; project directories and research
files are left untouched. The Home buttons use matching navy/copper
resting styles, and both hover with the selected tab's copper gradient. Dialogs,
lists, connection status and Close Project use coordinated copper styling.

Actual verification:

- `./sigma test` passed all scenarios and API/CLI checks, Ruff check/format,
  Pyright (zero errors), frontend typecheck, and production build. The existing
  non-failing Starlette TestClient deprecation notice remains.
- Real Chrome `browser_checks/recents.py` passed tab keyboard navigation, exact
  button rest/hover style comparisons, stable direct sample opens, Recent/Forget and
  unavailable path behavior, source immutability, no page errors, and 1280px,
  390px and 320px responsive layout checks. The 1280px Home screenshot was
  visually inspected; the controls do not cover the approved artwork. The New
  Project dialog had no internal vertical scroll at 1280x800. Screenshots are
  under `/tmp/sigma-a11-*.png`.

Limits: browser sizes were Chrome emulation, not physical devices. The first
selection creates one managed installation because the checked-in catalog paths
are not `.sigma` packages; this is a stable project, not a new copy on each open.

Follow-up: the "Open a Project" heading retained a gold color from the older Home
stylesheet. It now uses the exact resting copper text color of Open/New Project.
Real Chrome checked the heading against both buttons' computed colors and the
desktop screenshot was visually inspected. `./sigma test` and the full A11 Chrome
check passed again after the change.

The direct-open correction removed the working-copy dialog and endpoint. Real
Chrome verified immediate opens, the same project path on repeat selections,
retained edits, exclusion from Recents, source-file immutability, and desktop and
mobile layouts. `./sigma test` passed the updated scenarios, API/CLI, Ruff,
Pyright, frontend typecheck and production build after the correction.

## Project header artwork

The project-page header now uses the approved `assets/sigma-project-header.png`
through an identical copy in `frontend/public/`. It is displayed as a full image
with proportional sizing at desktop and narrow widths. The Home page and its
artwork are unchanged.

Actual verification: `npm --prefix frontend run build` passed TypeScript and the
Vite production build. Byte comparisons confirmed the source, public and built
PNG files are identical. Real Chrome `browser_checks/recents.py` passed, and its
1280px and 390px project-page screenshots were visually inspected; the logo and
copper/blue wire effects are visible without cropping or horizontal overflow.

## A13 — project header and shared copper controls

The workspace header now places the complete project name immediately to the
right of the approved SIGMA artwork, replacing only the redundant workspace
tagline. It wraps instead of clipping or hiding below 1100px. The unchanged
`ConnectionStatus` component now uses one shared pill style on Home and in the
workspace; Open/New Project and Close project use one shared copper button style
with matching resting, hover, disabled and focus states. Home artwork, workspace
navigation and project content remain unchanged.

Actual verification:

- `./sigma test` passed all scenarios and API/CLI checks, Ruff check/format,
  Pyright (zero errors), frontend typecheck and production build. The existing
  non-failing Starlette TestClient deprecation notice remains.
- Real Chrome `browser_checks/header.py` passed full long-name display and no
  overflow at 1280, 1100, 700, 390 and 320px; checked artwork dimensions,
  workspace-only tagline removal, identical Home/Close button and connection
  pill styles, live status/dot, disclosure, keyboard focus and Close. Its five
  screenshots under `/tmp/sigma-a13-header-*.png` were inspected at desktop,
  1100px, 700px and mobile widths.
- Real Chrome `browser_checks/recents.py` passed Home and sample/recent regressions
  after the shared CSS change. The 390px Home and project screenshots were
  inspected, with the approved Home artwork and project navigation intact.

## Project header placement follow-up

The approved project artwork now begins at the viewport's top-left corner. Its
unused dark lower area no longer reserves extra vertical space above the project
workspace. The project title, header controls and workspace navigation are
layered above the artwork so they remain legible and clickable. The image file
and its aspect ratio are unchanged.

Actual verification: `./sigma test` passed all scenarios, API/CLI checks, Ruff,
Pyright, frontend typecheck and production build. Real Chrome
`browser_checks/header.py` passed at 1280, 1100, 700, 390 and 320px, including
artwork top-left placement, aspect ratio, control interactions and no horizontal
overflow. Desktop, tablet and mobile screenshots were visually inspected.

The header display now clips only the blank bottom quarter of the artwork. The
top 75%, including the complete SIGMA lettering and copper/blue wires, remains
visible. The source/public image files are untouched, and the clipped display
ends above workspace navigation. `./sigma test` and real Chrome header checks
passed again at all five viewport widths; desktop and mobile screenshots were
visually inspected.

## Project introduction and Strategies controls follow-up

The upper project pane gives the title and description the full available width.
It scrolls vertically when the description grows beyond the pane's bounded
height. New Strategy now sits to the right of the Strategies heading below the
divider and matches the Home action's 50px button height and padding. Strategy
expand/collapse and the split action use standard chevrons instead of text
symbols. The New Strategy action no longer has a leading plus.

Actual verification: `./sigma test` passed scenarios, API/CLI checks, Ruff,
Pyright, frontend typecheck and production build. Real Chrome
`browser_checks/strategies.py` passed creation, edit/remove, reordering and AI
flows after checking button placement, long-description scrolling and no
horizontal overflow at desktop and 390px. Desktop/mobile screenshots were
visually inspected. `browser_checks/header.py` passed at five widths.

## UI browser launch follow-up

`./sigma ui` now opens `http://127.0.0.1:5173` in the default browser after
both the API and Vite frontend report ready. If the browser cannot open, the
servers continue running and the terminal repeats the URL for manual use.
The browser is not opened during failed startup. The tooling scenario checks
the one-time launch and failure paths. Actual verification: `./sigma test`
passed scenarios, API/CLI checks, Ruff, Pyright, frontend typecheck and build.
The ready message also names the FastAPI API server at `127.0.0.1:8000` and
the Vite UI server at `127.0.0.1:5173`; the tooling scenario asserts both lines.

Home's content wrapper now has no left padding, so approved artwork starts at
the viewport edge. The Open Project heading, action buttons and sample/recent
catalog share a deliberate left inset. Real Chrome checks at 1280px and 390px
confirmed their positions and no horizontal overflow; screenshots were inspected.

## A14 — bounded agentic Generate Strategy (2026-10-21)

Generate with AI now uses a streamed, role-isolated Explore → Challenge → Decide
coordinator. A skeptical review can trigger targeted revision, a second
mechanism, or a no-viable-strategy stop. Each run is limited to six model calls,
two candidate attempts and 120 seconds; each provider call has a 35-second
deadline. The selected project model, thinking level and connected billing mode
remain bound throughout. Full active and removed strategy approaches are sent;
oversized context stops the run rather than truncating it. Progress events are
typed, sequential public summaries, and the browser rejects malformed or
unterminated streams. The draft stays editable and unsaved until Save strategy
records human acceptance and signed model provenance. No research tools or
literature searches run in this slice.

The project sidebar now collapses to an accessible icon rail on desktop. The
description/Strategies divider can be dragged or adjusted by keyboard, and its
default position sits close below the description. The project description
retains bounded vertical scrolling for long text; narrow layouts retain the
horizontal navigation row. Home and approved raster artwork were unchanged.

Actual verification on 2026-10-21:

- `./sigma test` passed all scenarios, API/CLI checks, Ruff, Pyright (zero
  errors), frontend typecheck and production build. `tests/agentic.py`
  covers sample zero-pool generation, explicit acceptance/reopen, later-strategy
  context, duplicate retry, skeptical revision, no-proposal and six-call stops,
  malformed/refused output, binding changes, timeouts, duplicate-run guard,
  cancellation, ChatGPT-plan streaming and ASGI disconnect, all with mocked
  transport and no paid calls.
- Real Chrome `browser_checks/agentic.py` passed against a fresh isolated
  provider fixture: zero strategy rows, chronological progress and critique,
  unsaved cancellation, explicit save/reopen, a second distinct mechanism,
  in-flight cancellation and source immutability. Desktop and 390px review
  screenshots were visually inspected; the dialog fits and scrolls.
- Real Chrome `browser_checks/strategies.py` passed sidebar collapse/expand,
  divider placement and drag/keyboard resizing, long-description scrolling,
  320px/390px layouts and strategy create/edit/remove/reorder/AI regressions.
  The collapsed desktop screenshot was visually inspected; no JavaScript errors
  or page-level horizontal overflow occurred.

The browser fixture's provider output is deterministic and does not demonstrate
live-model research quality, entitlement or account usage. Playwright's API
proxy can outlive a locally aborted request briefly; the direct ASGI disconnect
scenario verifies server-side cancellation and run-gate release.

## A15 — basic Generate Strategy path (2026-10-21)

The active A15 scope is the single-request Generate Strategy assignment. The
first broken integration was in the visible UI: it called the A14 streamed
agentic endpoint, while the already-supported bounded proposal service was
exposed separately and had its own request, validation, receipt and save tests.
The UI now calls that existing service directly. It presents one editable,
unsaved proposal; Save remains the only persistence action. Pending and cancel
states are visible, and the copy no longer promises independent review. A14's
agentic service and tests remain intact for the deferred A16 extension; the
original A15 text-representations work remains separately implemented.

Generation rejects an in-flight result if the connected account or billing
mode, project identity, selected model/thinking effort, or full research and
strategy context changed while the provider request was running. The existing
API-key and ChatGPT-plan response adapters, strict structured validation,
response/context limits, concurrency guard, and signed project/model provenance
remain in use. Failed requests and local cancellation leave research untouched
and keep the draft composer recoverable.

Actual verification on 2026-10-21:

- `./sigma test`: all executable scenarios and API/CLI checks passed; Ruff check
  and format passed; Pyright reported zero errors; frontend typecheck and Vite
  production build passed. Provider and agent tests use deterministic mocked
  transports; no paid provider call was made.
- `uv run --with playwright python browser_checks/a15_generate.py`: real Chrome
  passed the empty counting-project/empty-seed flow, exactly one bounded request
  per generation, substantive editable unsaved draft, cancel without mutation,
  simulated HTTP 500 with one dismissible request toast and inline recovery,
  in-flight cancellation without mutation, explicit edited save/reopen, and a
  different proposal with existing strategy context. The source fixture stayed
  byte-identical. Screenshots at 1440×900 and 390×844 were inspected; neither
  has horizontal overflow. These checks use the isolated mock provider on port
  8002, not live OpenAI.
- `tests/proposals.py` now also exercises the proposals API endpoint and verifies
  that an account change during a provider request discards the result without
  changing project state. `tests/model_connection.py` verifies changed-model
  rejection during the request.

## Project header spacing follow-up (2026-10-21)

The project header now displays the upper 64% of its unchanged artwork, retaining
the complete raised SIGMA lettering and visible copper/blue wires while removing
the remaining dark area beneath them. Its bottom padding is zero, so the project
workspace begins at about 125px on desktop instead of about 166px. Header
controls and the project title stay above the content without overlap.

Actual verification: `./sigma test` passed all scenarios, API/CLI checks,
Ruff, Pyright and frontend typecheck/build. Real Chrome `browser_checks/header.py`
passed at 1280, 1100, 700, 390 and 320px, and `browser_checks/strategies.py`
passed the project layout and strategy regressions. Desktop and 390px project
screenshots were visually inspected; no horizontal overflow or JavaScript errors
were observed. The public PNG and source artwork were not changed.

## A15 — Plain, Markdown and Rendered project text (2026-10-21)

The research problem and expanded strategy approaches now have a three-view
control. Plain and Markdown are separate durable bodies; Rendered is a local
read-only Markdown/KaTeX preview. Selecting a missing or stale view now starts
its conversion automatically per the later user request; failures retain the
source and offer Retry. The UI reports AI attribution, working/cancellation,
conversion errors and stale copies. A direct in-place description or title
edit requires Save; Escape cancels without writing. The project View selector
sits at the lower-right of the description pane above its draggable divider.
The project title appears once in the header, beside a back arrow; clicking it
edits the title in place. Other options remain in Project Settings. Home shows
a Current Project shortcut above “Switch to a new project,” validated through
the read-only inspect endpoint. The sidebar's collapse preference survives
leaving and reopening a project. Sample source fixtures and approved artwork
remain unchanged.

A versioned portable `text-representations.json` companion stores format history
and source-digest keyed conversions without rewriting legacy project documents
on read or conversion. Both conversion directions use the selected account,
model and Thinking settings through one bounded, cancellable service. The
current source is checked again under the project lock before publishing a
result. Strategy generation receives the current authoritative text and its
format. No live paid conversion was made for verification.

Actual verification: `./sigma test` passed all scenarios, API/CLI checks, Ruff,
Pyright (zero errors), frontend typecheck and production build. The A15 offline
scenario passed mock-provider conversion in both directions, v1–v6 read-only
migration, sample immutability, cache reuse, stale edits/conflicts, cancellation,
ASGI disconnect, malformed/truncated output, account/model availability and
ChatGPT-plan streaming. Real Chrome `browser_checks/text_views.py` passed
literal and rendered inline/display math, working/error/stale states,
in-place title/description editing and safe rendering, zero provider requests on cached switches,
Current Project reopen and desktop/390px layouts. Real Chrome
`browser_checks/header.py` passed the back-arrow header at five widths;
`browser_checks/strategies.py` passed layout, divider, strategy CRUD and AI
regressions and sidebar persistence. Real Chrome `browser_checks/settings.py`
passed in-place title/description editing, separate project settings, retained
model selection and conflict/error handling; `browser_checks/recents.py`
passed sample/recent Home navigation. Desktop/mobile screenshots were visually inspected and no
horizontal viewport overflow or page errors occurred. The renderer can display
an AI conversion faithfully but cannot verify mathematical equivalence; users
must review derived text before relying on it.


## UI recovery and explicit shutdown (2026-10-21, awaiting local verification)

The `./sigma ui` launcher now records the exact owner PID, process birth time,
user, command and checkout identity in a private owner file. Restart recognizes a
verified suspended launcher, sends SIGCONT so it can serve its control endpoint,
and requests a clean shutdown. If a verified owner remains suspended while
holding the startup lock, the launcher escalates after a bounded wait. An
unresponsive authenticated owner can receive SIGTERM then SIGKILL after a
bounded grace period. Unrelated port listeners, changed PIDs and unverifiable
control records are never signalled. Startup reports its stages rather than
waiting silently.

The new `./sigma shutdown` command uses the same checkout-specific control
mechanism without starting servers. Offline ownership and CLI-shutdown scenarios
and opt-in real-process suspended-launcher/shutdown lifecycle checks were added.
These changes were committed via GitHub and **have not been locally executed or
verified yet**; run `./sigma test` and the opt-in `tests/ui_lifecycle.py`
before treating the behavior as verified.

## Legacy suspended UI startup recovery (2026-10-21, pending local verification)

A launch or `shutdown` previously could block behind an older suspended SIGMA
launcher that predated owner registration. When a startup lock is held without
an owner record, the replacement path now queries the OS for the actual lock
holder and checks the exact checkout CLI path, user identity and process birth
before resuming it. If the same verified process retains the lock after a grace
period, termination escalates with identity rechecks. It never kills a process
merely for using ports 8000/5173. An offline regression covers legacy lock
inspection, suspension recovery and rejection of unrelated processes. The
change is committed but awaits macOS startup/restart/shutdown testing.

## Multiple suspended launchers (2026-10-21, pending macOS verification)

An initial legacy recovery attempt rejected multiple processes with open file
descriptors for the checkout's startup lock as "ambiguous", blocking both `ui`
and `shutdown`. Recovery now enumerates and verifies all reported holders
for the same checkout and OS user, resumes all verified suspended SIGMA UI
launchers, and escalates only against verified process identities still holding
the lock after the grace period. If any holder is unverified, no signals are sent.
The offline test now includes multiple holders and an unrelated-process negative
control. This is committed, but it has not been exercised on the user's Mac.

## Verified orphan-server cleanup (2026-10-21, awaiting macOS confirmation)

After suspended-launcher recovery, the UI can still be blocked by an orphaned
FastAPI or Vite listener on ports 8000/5173. The new `sigma.ui_orphans`
service examines a listening PID's OS user, process birth/command, working
directory, expected SIGMA server arguments, and (for FastAPI) its nonempty
`/api/ui-instance` identity. Only a matching same-checkout listener can be
stopped, first with SIGTERM and then (after a bounded grace period and
identity re-verification) SIGKILL. Unknown or unrelated listeners are untouched.

Both `./sigma shutdown` and `./sigma ui` now invoke that cleanup after
serializing through the private instance lock. The mock-provider-free offline
`tests/ui_orphans.py` regression covers owned servers, unrelated
listeners, changed process identity and SIGKILL escalation, and runs in
`./sigma test`. The isolated tests passed in the assistant's Python
environment, but end-to-end behavior on the user's macOS machine is not yet
verified.

## Samples terminology and source directory rename (2026-10-21)

The Home catalog now calls the shipped examples **Samples**. Samples is the
first tab and remains selected by default; Recent follows it. The Python
catalog module and public handlers were renamed to `sigma.samples` and
`/api/projects/samples`, including the open route and request field. The Home
component, CSS classes, browser checks, scenario filenames and documentation
use the same terminology. The checked-in project JSON and identities remain
unchanged; their containing directory moved from `examples/` to `samples/`.
Runtime discovery now reads `samples/` through the `SAMPLES` path constant.

Actual verification: `./sigma test` passed all scenarios, API/CLI checks, Ruff,
Pyright, frontend typecheck and production build. Real Chrome
`browser_checks/recents.py`, `browser_checks/a15_generate.py` and
`browser_checks/a142.py` passed, including real Chrome checks after the
directory move. `browser_checks/text_views.py` reached the
opened sample project, then stopped at a stale `.project-eyebrow` selector;
the current project page uses the “Project description” heading. It needs a
separate refresh of its project-page assertions.

## Markdown conversion tooltip (2026-10-21)

The gray Σ control now shows a visible hover and keyboard-focus tooltip reading
“Convert to markdown”; while the hourglass is active, it reads “Converting to
markdown”; after a successful conversion, it reads “Show plain text”. The
A14.2 real-Chrome regression checks all three states.

Actual verification: `uv run --with playwright python
browser_checks/a142.py` passed in real Chrome, including the initial gray state,
in-progress state, conversion failure and retry, and the rendered-state
tooltip. `./sigma test` passed all scenarios, API/CLI checks, Ruff, Pyright,
frontend typecheck and production build.

## Generate Strategy controls and manual fallback removal (2026-10-21)

Removed “Continue manually” from the Generate Strategy flow. Its starting point
and generated draft remain in that dialog through cancellation, sign-in decline,
and generation errors; users can still separately choose New to create a manual
strategy or fork an existing strategy. Moved Generate/Regenerate into the
dialog heading as an underlined action immediately before Cancel, and updated
authentication and provider guidance to point to retry or explicit billing
settings instead of a manual-continuation path.

Actual verification: `./sigma test` passed all scenarios, API/CLI checks, Ruff
check and format, Pyright, frontend typecheck and production build.

## Immediate retry after cancelling generation (2026-10-21)

The Generate dialog now sends a request ID and explicitly asks the API to cancel
the server-side generation task when the user cancels. This releases SIGMA's
single-request slot without waiting for the provider's normal completion; the
provider may still process or bill a request already received. The dialog keeps
Generate disabled until cancellation is confirmed, then allows an immediate
new intentional request. A short-lived cancellation tombstone handles a cancel
that reaches the API just before its proposal POST.

Actual verification: `./sigma test` passed all scenarios, Ruff, Pyright,
frontend typecheck and production build. Real Chrome
`uv run --with playwright python browser_checks/a15_generate.py` passed with an
immediate Generate retry after cancelling a deliberately delayed mock request;
no live provider call was made.

## Project and Strategies heading controls (2026-10-21)

The project heading is simply **Project**. Its text and Settings controls share
the heading row, with controls immediately after the heading. New and Generate
are beside Strategies on its heading row. Project description editing shows
Save and Cancel without Settings. Project action buttons use the same 16px
spacing as the Strategies action buttons. During strategy generation, the
button itself carries the visible loading label; the duplicate visible status
line is removed while a screen-reader-only live status remains.

Actual verification: `./sigma test` passed all scenarios, API/CLI checks, Ruff
check and format, Pyright, frontend typecheck and production build.
`uv run --with playwright python browser_checks/a15_generate.py` passed in real
Chrome against the isolated mock provider, including generation, failure,
cancellation, save/reopen, and mobile overflow checks. No live provider call was
made.

## Project description edit actions (2026-10-21)

While the project description is being edited, its text action row now shows
Save and Cancel without Settings. Settings returns after the edit is saved or
cancelled.

Actual verification: `./sigma test` passed all scenarios, API/CLI checks, Ruff
check and format, Pyright, frontend typecheck and production build.

## Pulled test stabilization verification (2026-10-21)

Pulled `b2153f5` from `origin/main` as a clean fast-forward. Re-ran
`./sigma test`: all source-controlled scenarios passed, including proposal and
agentic cancellation/retry coverage; Ruff check and format, Pyright, frontend
typecheck, and the production build also passed. No stabilization fixes were
needed. FastAPI's TestClient emitted the existing Starlette deprecation warning
about `httpx`; it did not affect the results.

## A16.1: durable agentic generation evidence (2026-10-22)

The `/api/projects/proposals/agentic` run now stores a private JSON record at
`<project>.sigma/agentic-runs/<run-id>.json`. It captures the exact validated
Explorer/Critic/revision outputs, ordered activity references and coordinator
decisions, including local overlap overrides and reasons. Each record binds the
public provider input (problem, strategy corpus and starting point), project ID,
nonsecret digests, selected model/thinking/provider mode, prompt/schema digests,
final unsaved draft when present, and an explicit terminal disposition. A step
interrupted after its start is retained with no fabricated output. Authentication
identity, tokens, headers, provider envelopes and receipts are excluded.

Records are atomically published with owner-only permissions, isolated to the
project copy, and retained within 32 runs, 8 MB per project and 512 KB per file.
Sample source directories reject writes. `./sigma agentic-runs PATH` lists runs;
adding a run ID prints the full JSON artifact. The API provides matching list and
export GETs. No strategy document schema or human-save behavior changed.

Actual verification: `./sigma test` passed all scenarios, including new
`tests/agentic_evidence.py` retention/security checks and expanded
`tests/agentic.py` output/lifecycle/storage checks; Ruff check/format, Pyright,
frontend typecheck and production build passed. Real Chrome
`uv run --with playwright python browser_checks/a15_generate.py` passed against
the isolated mock provider, confirming the existing A15 generation flow remains
intact. No live model calls were made. Scenario artifacts are created in
temporary projects and removed with the test directory; a real run is saved at
`<project>.sigma/agentic-runs/<run-id>.json`.

## A17: persistent research sessions (2026-10-22)

The project workspace now has three panes: independently collapsible Project and
Strategies panes around an always-visible Research session pane. Research sessions
are numbered and selectable from history, with live role activity, current action,
call/cycle budget, and inspectable artifacts. Each session selects a saved strategy.
An explicit **Investigate** flow shows the selected model, account billing mode,
six-call/three-cycle cap, and usage disclosure before starting. A background worker runs one structured
Investigator and one independent Skeptic call per cycle. Python uses each
Skeptic decision to continue, revise the next question, or stop. Each completed
cycle is a durable, ordered artifact labeled as unverified model research; no
claim is called tested or proved, and the saved project or strategy is never
mutated.

Sessions and public role outputs are stored separately under
`<project>.sigma/research-sessions/` with owner-only permissions, atomic writes,
per-record and per-project storage bounds, and no artifact pruning. Start,
status, pause, resume, and stop are available through local project API routes.
Sessions survive browser navigation and recover on backend restart as paused;
in-flight calls count against the limit and are not automatically retried.
Calls coordinate with strategy generation, proposal generation, and text
conversion gates. Credentials, provider envelopes and hidden reasoning are not
stored. No strategy stage promotion, external research, or computational
verification is performed.

Actual verification: `./sigma test` passed all scenarios, including new
`tests/research_sessions.py` coverage for three dependent cycles, the revise
branch, six-call cap, strategy nonmutation, pause/stop and gate release,
explicit resume with remaining budget, malformed output, streamed ChatGPT
Responses, idempotency and restart recovery. Ruff check/format, Pyright,
frontend typecheck and production build passed. Real Chrome
`uv run --with playwright python browser_checks/a17_research.py` passed in real
Chrome at desktop and mobile sizes, including pane order and independent collapse,
unsaved drafts retained across collapse, consent, session numbering/history, live
activity and artifact inspection, navigation/reopen, pause/resume/stop, and
failure-toast recovery. No
live or paid provider call was made. The worker runs only while the local API
process is alive; research notes remain unverified.

## A17.1: consistent section, table and inline-edit patterns (2026-10-22)

Project now has a standalone `PROJECT` section heading followed by an inline
title-and-pencil row, then the full editable description. It is not collapsible;
the title has no `Project:` prefix. Strategy rows follow the existing table
pattern with plain titles, in-place pencil editing and visible descriptions.
Neither title nor description is hidden behind row disclosure. Existing IDs,
revision history, provenance and research snapshots remain unchanged. Legacy
untitled strategies retain their deterministic display-only fallback. Generated
titles still request a concise 2–12 word name and reject multiline or overlong
values.

Sessions now follow Strategies in a matching section/table, with a static
singular/plural count, ascending `Session #N` rows, status indicators and native
keyboard-accessible row disclosure for activity, findings, critiques, cycles and
artifacts. Research still starts through Strategies Play; there is no competing
start action in Sessions. New/Generate sit immediately before the count in the
right-aligned Strategies heading controls. Play selects the first eligible saved
strategy in existing order, resumes the currently bound paused session and never
changes strategy within an active session. A17 confirmation, identity/binding
checks, idempotency, six-call/three-cycle limits and stop/error reconciliation
remain in force; no chaining or paid calls were added.

The existing ChatGPT connection pill now pulses only its green status dot while
tracked provider work is active. Request tracking is reference-counted by unique
request identity, so overlapping generation and text conversion remain active
until both complete. Research calls are detected from durable session step state
and monitored through terminal status, including across client navigation. Errors,
cancellation and timeouts release their request; disconnect or unavailable
connection status disables the green pulse. Reduced-motion users see a steady
green dot.

Actual verification: `./sigma test` passed all scenarios; Ruff, Pyright, frontend
typecheck and Vite production build passed. Real Chrome
`uv run --with playwright python browser_checks/a17_research.py` passed at
1440px desktop and 390px mobile. It covers inline editing and persistence,
generated-title acceptance, legacy fallback, absence of Project/Strategy
disclosure, visible descriptions, session order/count/status/disclosure,
three-cycle history and artifact inspection, Play/Pause/Stop, error recovery,
concurrent request pulse, reduced-motion behavior and mobile overflow. I inspected
the desktop and mobile captures at `/tmp/sigma-a171-desktop.png` and
`/tmp/sigma-a171-mobile.png`. No paid provider calls were made.

## A17.2: workspace interaction consistency and layering (2026-10-22)

Session rows no longer disclose or hide their contents. Their status, action,
budget, activity and controls remain visible; artifact entries retain their own
detail disclosures so full validated role outputs remain inspectable. Strategies
header controls now follow the heading inline in New/Generate, count, divider,
Play/Pause order. Project title editing keeps its pencil beside the title, and
the header labels its existing navigation control **Back to Home**.

New and Generate expand Strategies before opening and focus their creation
surface. A synchronous workspace mode lock allows only one Project/Strategy edit,
New or Generate mode at a time. Competing entry buttons expose disabled state;
keyboard and rapid pointer attempts are blocked. Save errors retain the active
draft and its recovery controls; cancel and successful saves release the lock.
Play/Pause and the connection pill are disabled during these UI modes, without
changing or claiming cancellation of an already-running research session.

The connection popover now uses a body portal with a modal backdrop and focus
trap, sits above project/workspace stacking contexts, and blocks underlying
pointer actions. Escape and backdrop close it and restore trigger focus. Small
screens keep the panel within the viewport. The remote launcher rename was also
reconciled: `./sigma start` is the current command, `--navigate` is opt-in, and
owner verification still accepts an already-running legacy `./sigma ui` process.
Owner verification also recognizes the new `./sigma start --navigate` invocation.
Launcher tests now match these behaviors.

Actual verification: `./sigma test` passed all scenarios, Ruff check/format,
Pyright (zero errors), frontend typecheck, and production build. The existing
Starlette TestClient/httpx deprecation warning remains non-failing. The updated
`tests/tooling.py` passed separately after adding an explicit legacy-owner
compatibility assertion. Real Chrome `uv run --with playwright python
browser_checks/a17_research.py` passed with the isolated provider fixture at
1440px desktop and 390px mobile. It exercises noncollapsible Sessions with
artifact access, header order, auto-expand/focus, cross-workspace mode exclusion
by keyboard and rapid clicks, cancel/save-error recovery, modal portal/backdrop/
Escape and blocked underlay, Play/Pause, session history/artifacts and provider
activity. Desktop and mobile captures were inspected at
`/tmp/sigma-a171-desktop.png` and `/tmp/sigma-a171-mobile.png`. No live provider
calls were made.

## A17.3: research settings, reliability and workspace interaction (2026-10-22)

Project, Strategies and Sessions now collapse independently; the Sessions count
continues to poll while its content is hidden. Project and strategy inline edits
cancel on click-away, while Generate runs independently of editing and rejects
duplicate or stale proposal acceptance. Session headers retain `Session #N`,
show their strategy separately and align the status column; the strategy action
is an underlined `Go to <title>` link that expands, scrolls to and focuses by
stable strategy ID. Starting a session has a separate confirmation showing the
chosen strategy, billing mode and effective limits.

Settings has keyboard-operable Main and Limits tabs. The per-project limits
sidecar is validated, privately written by atomic replacement and defaults for
older projects without migration. A session snapshots its limits at start;
changing settings does not alter existing sessions. Backend admission is
serialized across processes, and a worker lock distinguishes a live worker from
a stale session after restart. A provider request interrupted at an ambiguous
completion point cannot be resumed and replayed; completed artifacts remain
available, and the UI explains that a provider may already have charged for the
attempt. Timeouts remain separate from elapsed session limits, which count pause
time.

API-key sessions record provider token usage and display estimated cumulative
spend. Estimates apply model-specific Standard short-context published input,
cached-input and output rates (checked 2026-10-22 at
https://developers.openai.com/api/docs/pricing); estimates are not invoices.
Unknown model prices or missing/unreliable usage are shown as unavailable, and a
cost-limited session pauses before a call it cannot conservatively bound.
ChatGPT subscription sessions have no dollar estimate or cost cap. SIGMA sends
the configured output-token ceiling to the API-key provider; provider-side token
enforcement is not guaranteed for the ChatGPT transport, so the final parsed
response is independently bounded. Raw streaming transport is capped at 1 MB to
allow for framing while retaining a finite ceiling.

Actual verification: `./sigma test` passed all scenarios, including new
`tests/research_sessions.py`, `tests/project_settings.py` and stale-proposal
receipt coverage. Ruff check and format check passed across `src`, `tests`, and
`browser_checks`; Pyright reported zero errors; frontend typecheck and Vite
production build passed. Real Chrome
`uv run --with playwright python browser_checks/a17_research.py` passed with the
isolated provider fixture at 1440px desktop and 390px mobile; I inspected both
captures at `/tmp/sigma-a171-desktop.png` and `/tmp/sigma-a171-mobile.png`.
Coverage includes click-away cancellation, independent collapse and live
session counts, confirmation limits, token/cost presentation, interruption
safety, strategy navigation/focus, failure recovery and mobile overflow. No
live or paid provider call was made. The existing Starlette TestClient/httpx
deprecation warning remains non-failing.

## A17.4: workspace disclosures, session outcomes and export (2026-10-22)

Project, Strategies, Sessions, each strategy and each session now use focusable
chevron disclosures. Their content stays mounted while collapsed, so drafts,
activity updates and session polling continue. Project Download and Settings
remain in the Project bar while its description is collapsed. Section headings
share Home Projects typography and divider spacing. Home recents put the open
project first, bold its title and place Remove on its metadata row. Strategy
More actions is a flat menu beside the title pencil; Schedule and Report artifact
remain disabled with explanations, while Fork, Change stage and separated
Remove retain their behavior. Play expands and reveals the launched/resumed
session. Session removal is terminal-only, confirmation-based, revision-checked
and leaves the project and other sessions untouched; a durable sequence counter
prevents reusing deleted numbers.

Settings uses a wider fixed outer frame with an internally scrolling body and
validates future-session limits without changing existing snapshots. Backend
and UI enforce 1–10 rounds, 2–20 calls, 1–120 minutes, 256–16,384 output
tokens, and $0.01–$100 or blank for the API-only cost cap; call allowance must
cover two calls per round. Numeric spinners are hidden. Session Outcome is
derived from saved artifacts and Coordinator decisions, carries caveats, and
remains independent of execution status. Export v2 includes ordered session
records with snapshots, steps, token use, artifacts, decisions, errors and the
same derived outcome while filtering credentials and identity metadata.

Coordination audit: the observed local two-call session had an Investigator
result followed by a Skeptic review that accepted the result and found no next
test. The previous Coordinator stopped on the generic `stop` assessment, so the
stop itself was appropriate but its reason was ambiguous. The structured
`productive_conclusion` branch now records a useful reported conclusion and
explicitly labels it unverified. Mocked decisions cover recoverable objections
(revise when a concrete question remains), decisive counterexamples, no
progress, budget exhaustion and productive conclusions; criticism alone does
not stop a session.

Previously saved limit sidecars that fit the older contract but exceed the new
bounds remain readable without rewriting. The Settings form shows their
validation errors and requires explicit correction before save; backend session
admission rejects them until then. Existing session snapshots remain untouched.

Final A17.4 verification: `./sigma test` passed all scenarios, Ruff, Pyright,
frontend typecheck and production build. Real Chrome used the local mock
provider, not paid/live calls, at 1440×900 desktop and 390×844 narrow mobile.
The A17 research browser scenario covers stable Settings dimensions, collapsed
Project actions, menu order/keyboard state, strategy/session disclosures,
launch scrolling, completed activity collapse, artifact/outcome visibility,
confirmed deletion and preservation of session numbers 1 and 3 after removing
2. Screenshots: `/tmp/sigma-a174-desktop.png` and
`/tmp/sigma-a174-mobile.png`. Legacy project/session records are not migrated;
out-of-bound saved limits remain unchanged until explicitly corrected.


## Session lifecycle and context continuation (2026-10-22, direct edits)

User-requested lifecycle distinction: Stop now preserves a resumable `stopped` session, while normal terminal research transitions to `ended` (older `completed` records remain readable/removable). Stopped sessions expose Resume and Remove in the title row; running/queued/paused sessions expose Stop, and ended sessions expose Remove. Stop acts without a confirmation prompt. Resume uses the saved session identity, model, strategy, artifacts and remaining call allowance, and excludes time spent stopped from the deadline. Interrupted provider attempts remain recorded and charged against the call budget; explicit resumption may make a new attempt, not recover an uncommitted provider response.

A deterministic context assembler supplies the current strategy, question, two most recent full artifacts, the accumulated obligation ledger and prior artifact IDs to each role. Skeptic also receives the pending Investigator output. It refuses oversized context instead of silently dropping objections; each step records source artifact IDs and obligation count. This is an initial bounded implementation, not semantic retrieval.

The direct lifecycle/context-continuation edits were included in the A17.7 local
verification above. They were exercised by the full source-controlled scenario
suite and the real-Chrome pause/stop/error workflow using the mock provider; no
paid calls were made.

Latest UI follow-up (2026-10-22): Project and strategy title editing now shares
one Save/Cancel pair with the description editor. The Markdown control keeps a
title-row slot in normal view and is hidden during Save/Cancel; title fields
stay content-sized with a reduced gap before Save/Cancel.
The Research Artifacts Markdown view now renders every artifact at once, with
one control for the full collection. A session-remove confirmation opens
rightward from its action to stay on screen, a single strategy no longer leaves
an empty reorder-handle gutter, and disabled strategies show Enable instead of
a separate status pill. Reorder previews use neighboring row centers and skip
unchanged positions to prevent pointer jitter. Strategy removal has one anchored
confirmation popup; Confirm calls removal directly without opening the retired
dialog. Strategies and Sessions show their divider only while collapsed.
Confirmation actions in Sessions, Strategies and Recent Projects share the
regular underlined-link size. Full `./sigma test` passed, including Ruff,
Pyright, frontend typecheck and production build; Ruff check/format also passed
for the updated research browser scenario. A fresh browser run stopped at its
existing stale “Open Counting Constrained Binary Strings” selector before
reaching workspace assertions.

The Project details & history section is controlled by
`SHOW_PROJECT_DETAILS_AND_HISTORY` in the frontend runtime and is currently
hidden (`false`). Frontend typecheck and production build passed after this
flag was added.

## A20 — AI-authored research paper (2026-10-22)

Implemented on `feature/a20-ai-authored-paper` for review; no merge performed.
The existing Project export action and **Academic paper using LaTeX** option open
the versioned AI-authored paper workflow; no additional project action or icon
was added. Project Audit and deterministic Research Report renderers and routes
retain their existing output semantics. The pipeline is in
`src/sigma/papers.py`; API routes list, generate, read, and download paper
versions. The visible workflow states the selected project model and provider
mode, one-call limit, API-key billing disclosure, progress, cancellation, saved
version history, complete structured preview, evidence references, and PDF
download. Returning to Export Project preserves its selected report type,
filename, and tab preference; the filename and tab preference also control the
compiled paper PDF.

Each request takes the full current project/strategy/session/artifact/agentic-run
snapshot and stable source IDs, computes a SHA-256 fingerprint, and sends the
complete package or refuses it above 100,000 bytes; repeated nested strategy,
artifact, and step arrays are represented by their own source records rather
than duplicated in parent records. Evidence is never silently truncated. The
provider returns a strict structured draft with claims, evidence
references, claim status, claim-to-narrative links for the abstract/framing/
methods/sections/conclusions, unresolved obligations, and author self-review
warnings. The validator rejects unknown source/claim IDs and flags missing
references, missing narrative links, explicit counterexample/contradiction
language, cited unverified/incomplete evidence labeled established, omitted
saved obligations, and citation-like external references. Nuanced contradiction
review remains model self-review, is labeled as such, and is not independent
mathematical verification. No external bibliography is generated.

API-key mode uses one Responses call with `store:false`, a 12,000-token output
ceiling, a 120-second request timeout, and a 1 MB response cap. ChatGPT-plan
mode uses the completed-stream validator with a separate 4 MB cap; no output
token ceiling is claimed for that transport. Disconnect cancels the request;
PDF compilation runs off the event loop through the existing bounded Tectonic
path, and a cancelled or failed compile publishes no version. The controlled
renderer escapes prose and permits only a small math-command allowlist; it never
executes model-supplied document LaTeX. Per-project sidecars under private
`papers/` storage retain up to 50 immutable versions with the exact source
snapshot, structured draft, provider/model/effort, timestamp, validation notes,
PDF hash/size, and compiled PDF. Regeneration adds a new record; project edits
do not rewrite old snapshots. The project audit/history and research-session
records are not mutated. Removing a project directory also removes its nested
paper versions.

Verification performed:

- `./sigma test` passed the full suite, including the new `tests/papers.py`,
  Ruff check/format, Pyright, frontend typecheck, and production build. The
  existing non-failing Starlette/httpx deprecation warning remains.
- `uv run --with playwright python browser_checks/a20_paper.py` passed in real
  Chrome against the isolated provider fixture. It opened the Maximum Regions
  Sample copy, generated and inspected a saved research session, authored from
  that snapshot, checked claim/source linkage and immutability metadata, and
  retrieved the compiled PDF through the browser. No live provider call was
  made.
- The actual fixture PDF was rendered with macOS Quick Look and visually
  inspected. Its title, abstract, section hierarchy, formula and evidence-link
  markers were legible; the result was labeled unverified. Captures:
  `/tmp/sigma-a20-paper-preview.png`, `/tmp/sigma-a20-paper-mobile.png`, and
  `/tmp/sigma-a20-paper.pdf.png`.
- The isolated unresolved-project fixture produced an exploratory note with no
  theorem-proof claim. Adversarial unit fixtures cover invented source IDs,
  unverified/incomplete cited evidence labeled established, contradiction
  language, citation-like external text, and missing saved obligations.
- The normal SIGMA ports were occupied by an unrelated/unverifiable service;
  `./sigma start` correctly refused to replace it. Browser checks used the
  current Vite app on port 5174 and fixture API on 8012, leaving the existing
  service untouched. The known stale A17 browser assertions were not rerun; the
  source-controlled A17/API/export regressions passed in `./sigma test`.

### ChatGPT-plan stream-limit follow-up

After the user reported a Maximum Regions generation failure, traced the exact
message to the shared ChatGPT SSE parser, which had applied its 1 MB research
proposal cap and emitted “no strategy was saved” for paper generation. The
paper route now supplies its own bounded 4 MB streamed-response allowance and
a paper-specific overflow message; API-key JSON remains capped at 1 MB. The
paper dialog shows both mode-specific response limits. A synthetic 1.1 MB SSE
regression confirms the paper stream completes under its configured cap and
that overflow at the smaller cap reports a paper error without strategy
wording.

After this follow-up, `./sigma test` passed the full suite, Ruff, Pyright,
frontend typecheck, and production build. Real Chrome A20 browser check passed
on Vite 5174 with isolated provider fixture 8012, including the visible limits,
Maximum Regions Sample workflow, remembered export options, and PDF download.
The configured local `projects/` contains no Maximum Regions user project, so
the user's exact saved project and a live ChatGPT-plan provider run were not
available to verify. The fixture proves the UI and bounded parser behavior,
not real-provider compatibility; that remains unverified.

No bounded real-provider trial was run. The user's saved Maximum Regions
project is absent from the configured local project root, and no paid API call
was made without explicit billing approval. Author prose quality,
provider-specific output compatibility, and real-provider timeout/rate-limit
behavior therefore remain unverified. The A17.8 core-system acceptance gate
remains open. Recommendation: review A20 as a
separate capability, then verify compatibility against the accepted integrated
A17 work on the latest `main` before any merge. Do not mark A20 complete until
human review and an authorized quality trial or an explicit decision to leave
that criterion open.

### PR #5 review follow-up

Integrated the current `main` into `feature/a20-ai-authored-paper`, retaining
the A20 legacy-report verification-status behavior and the A23 optional
difficulty display. No merge into `main` was performed. Corrected PDF prose math
handling for Unicode superscripts and common mathematical commands, including
claim statements and reasoning. Frozen open obligations are now deduplicated
with their source/field references and reconciled against the author's list;
unlisted items are explicitly not presumed resolved. The complete reconciliation
is persisted in each new paper record and shown in both the PDF and saved-paper
preview. Older records remain readable without this field.

Added recovery coverage for provider rejection and malformed JSON in the real
Chrome workflow; a partial ChatGPT stream is rejected by the paper adapter, and
an ASGI disconnect cancels in-flight authoring without publishing a version or
holding the generation gate. The Maximum Regions browser fixture deliberately
contains twelve frozen proof obligations while the paper lists none, and checks
that all twelve remain visible and source-linked in the reconciliation.

After integrating latest `main` and the review fixes, `./sigma test` passed the
full suite, including Ruff, Pyright, frontend typecheck, and production build.
Real Chrome A20 workflow passed against the isolated provider fixture, including
rejection, malformed-response recovery, all twelve obligation records, and PDF
retrieval. No live provider request was made. A17.8 remains an acceptance gate;
A20 is not merged pending compatibility review against accepted A17 work.

### Mathematics paper structure and exposition follow-up

The paper prompt now detects `investigation_type=mathematical` and requires a
mathematics-paper organization: notation and definitions, a precise result
statement, separate upper-bound and attainment arguments for extremal results,
all nontrivial proof steps, edge cases, and explicit verification status. The
PDF renderer uses math-appropriate Introduction, Evidence and scope,
Verification status and limitations, and Conclusion headings, with the
claim/evidence register after the conclusion. The safe math allowlist now
renders `\mathcal` notation. The Maximum Regions browser fixture demonstrates
a detailed convex-cell lemma, incremental bound, explicit attaining family,
recurrence, and base case; browser assertions check these explanations, and
the isolated fixture checks that the math-specific instructions reach the
provider.

`./sigma test` and the real Chrome A20 workflow passed after these changes.
The fixture PDF was opened and visually inspected; its notation and section
layout render cleanly. `/tmp/sigma-a20-mathematics-paper.pdf` is the improved
fixture artifact. This is not a live-model paper, so actual provider prose
quality remains unverified.

## A19 — isolated Python execution service (2026-10-22)

The former A19 coordination item was consolidated into A18. Per the current
assignment, A19 is layered on the reviewed A18 branch state (`1114aba`) and
connects its portfolio role-call boundary without changing Blue's checkout or
branch. A20 was merged by PR #5; historical notes above that said it was not
merged describe the state at the time they were written. A17.8's independent-
research acceptance gate remains open, but does not block bounded local
computation.

The standalone proof of concept is in `sandbox-poc/`. A pinned Python 3.12.8
base image and fully pinned scientific-Python requirements provide NumPy,
SciPy, pandas, SymPy, and Matplotlib. The SIGMA service exposes a typed Python
entry point and POST/list/get/artifact project API. It executes one source submission in
a fresh local image, resolved to its immutable image ID, with Docker
`--pull=never`, `--network=none`, UID 65532, read-only root, a 64 MiB
non-executable temporary filesystem, no capabilities, no-new-privileges,
512 MiB memory/swap, one CPU, 64 processes, a 15-second wall deadline, 16,000
source bytes, and 32,000 combined captured output bytes. One execution is
admitted per backend process. Each completed or rejected attempt is stored with
source, bounded stdout/stderr, status/exit code, timing, image ID, resource
policy, optional session/strategy/cycle references, and captured file metadata
in a private project sidecar. Captured content is restricted to eight flat
regular files, 4 MB each and combined, with SHA-256 checked on retrieval. The
project document is not changed.

In A18's portfolio role loop, Investigator may return bounded nullable
`python_code`. Nonempty code runs once before the Skeptic call. The Skeptic
receives the exact code, execution status/ID, bounded output, and artifact
metadata; the same record is retained in the Investigator step and saved
research artifact. Timeout, nonzero exit, output-limit, unavailable, and busy
statuses remain explicit. Pause/stop waits for the hard-bounded execution to
finish and persists its result before propagating cancellation. Code is treated
as finite-computation evidence, not proof.

Actual container verification used Colima/Docker and the built ARM64 image:

- `docker build --pull=false -t sigma-research-python:0.1 sandbox-poc` passed.
- `uv run --locked --no-sync python sandbox-poc/runtime-check.py` passed against
  the actual image: UID 65532, zero effective capabilities, no-new-privileges,
  read-only `/work`, 512 MiB memory, one-CPU cgroup, and 64-process cgroup were
  checked from inside the container. All five scientific libraries imported; SciPy integration,
  SymPy integration and a pandas reduction produced expected values; Matplotlib
  wrote its runtime state and plotted using bounded `/tmp`; a direct socket
  attempt was denied; a 768 MiB allocation failed under the 512 MiB ceiling;
  1 MB output was stopped and capped at 32,000 bytes; an infinite loop was
  killed by the 15-second timeout; and a real execution record was persisted
  and retrieved from a temporary project.
- `uv run --locked --no-sync python sandbox-poc/agent-workflow-check.py` passed
  the actual fixture-backed Investigator→Docker sandbox→Skeptic workflow. The
  Skeptic inspected the source, completed status, output, and execution ID; the
  test then retrieved and validated the saved 17,141-byte PNG artifact.
- The research workload answered its own question: enumerating line
  arrangements through `n=12` gave 79 regions and matched
  `1 + n(n+1)/2` at every finite case. It exercised NumPy linear algebra, SciPy
  integration and root finding, SymPy summation, pandas comparisons, and a
  captured Matplotlib PNG.
- `printf ... | python sandbox-poc/run.py` passed as a standalone proof-of-
  concept import smoke for the five libraries.
- The first actual attempt exposed Docker's requirement that a `--cidfile` path
  not already exist. The adapter now reserves a random private path, removes the
  placeholder before `docker run`, and uses the resulting container ID to stop
  timed-out or output-flooding containers. The second run exposed diagnostic
  text exceeding the output cap by its own length; capture now reserves space
  for the diagnostic. The final runtime check passed after both fixes and
  `docker ps` showed no remaining research container.

`uv run --locked --no-sync python tests/python_sandbox.py` passed deterministic
command-policy, size/metadata validation, busy admission, private storage,
project binding, cancellation, and HTTP record/artifact API tests.
`uv run --locked --no-sync python tests/research_sessions.py` passed A18's full
research scenarios plus deterministic Investigator→Python→Skeptic and
stop-during-execution provenance tests. Final `./sigma test` passed every
scenario, Ruff check/format, Pyright (0 errors), frontend typecheck, and
production build. Existing Starlette/httpx deprecation warnings were
non-failing. The A18 research browser fixture now supplies the strict
`python_code: null` field for no-code proposals; the real Chrome A18 workflow
passed against the existing isolated fixture after this contract update. A19
has no separate UI to verify. The actual image run used Docker/Colima rather
than a live provider; the provider/agent integration used deterministic
fixtures. No live provider calls were made. A17.8 remains an independent
acceptance gate. Python results do not constitute formal verification or Lean
evidence.

Audit follow-up: `python.started` and `python.completed` session events record
execution ID and terminal status. Tests now verify the exact Python source and
full execution record survive the project JSON audit export and A20 paper
evidence snapshot; captured binary files remain separately retrievable by
execution ID. Corrected Getting Started documentation that still described the
sandbox as awaiting A18 integration. Re-ran `tests/research_sessions.py`,
`tests/papers.py`, lint/format for changed code, `./sigma test`, and the real
Chrome A18 workflow; all passed.

### Adversarial review follow-up

Review found that a backend crash after execution-sidecar persistence but
before session update could cause a resumed session to execute the identical
proposal again. Recovery now looks up the exact project/session/strategy/cycle
and source tuple and reattaches the existing terminal record. The public
execution API now requires provenance references as a complete tuple and
checks them against the selected project's saved session. Execution reads
validate that the project exists before creating sidecar storage; sample
projects reject execution evidence, preserving their source files.

Validation passed `tests/python_sandbox.py` (including forged/partial
provenance, nonexistent project side effects, and sample write protection),
`tests/research_sessions.py` (including crash-window recovery without a second
execution), Ruff and format checks, `./sigma test`, the actual Docker runtime
check, and the fixture-backed real Docker Investigator→Skeptic workflow. The
first full-suite rerun caught a Pyright mismatch in the new path-typed recovery
call and the runtime smoke caught invalid synthetic provenance; both were
fixed before the final passing run. No live provider calls were made.

The A19 branch was first synced with Blue's `a18-blue` head
(`2927897`) without changing that branch. The merged interface adds required
Skeptic cross-strategy relations and a 60-second provider-call deadline; the
A19 guidance, agent fixture, and 256 KB context bound coexist with those
changes. After resolving only the shared guidance/timeout hunks, `./sigma
test` passed with the A18 research ladder, all A19 tests, lint/format, Pyright,
frontend typecheck, and production build. The actual Docker runtime check and
fixture-backed Investigator→sandbox→Skeptic check passed, including the
required relation field and PNG retrieval. Real Chrome A18 workflow passed on
the merged tree against a fresh local provider fixture. No live provider call
was made.

After Blue advanced A18 with portfolio lifecycle and preflight-recovery fixes,
A19 was merged with the new tip `b7e4111` (merge commit `8f03694` on this
branch; Blue's branch was not changed). Adversarial review confirmed that
Investigator execution remains shielded through stop/pause, writes its terminal
sidecar before cancellation propagates, and leaves the control state intact;
restart recovery reattaches an exact project/session/strategy/cycle/source
match instead of rerunning it, and the resulting full record is attached to
the Investigator evidence before the Skeptic call. The Skeptic propagation,
crash-window recovery, and stop-during-execution regressions all passed as part
of a fresh `./sigma test` on this merged tree (including A18's new lifecycle
and preflight tests, Ruff check/format, Pyright, frontend typecheck, and
production build). Fresh actual-Docker runs of both
`sandbox-poc/runtime-check.py` and `sandbox-poc/agent-workflow-check.py` passed;
the latter completed the fixture-backed Investigator→sandbox→Skeptic cycle
and retrieved its 17,141-byte PNG. No live provider call was made.

### A19 computation usefulness and adversarial continuation (2026-10-23)

The next review found concrete evidence-loss bugs. A 30,000-byte control-character
stream and a 30,000-byte invalid UTF-8 stream each ran successfully but failed
the old 64 KB JSON storage bound after escaping/decoding. The execution record
cap now accommodates the worst bounded JSON expansion; exact non-UTF-8 bytes
are additionally retained in base64. Rejecting a symlink artifact previously
replaced the program's stderr; `artifact_error` now records capture failures
separately while preserving both program streams. The host transport now uses
nonblocking input and bounded process reaping, including a stalled runtime and
an early EOF without a completion marker.

Recovery now reserves code and provenance durably **before** dispatch. A held
file lock identifies a live execution across processes; an orphan reservation
is exposed as interrupted with no invented output. This closes the earlier
crash window before terminal persistence. Reservation deduplication is atomic
under the sidecar lock. Later identical failed source in the same session and
strategy reuses the original failure and its actual cycle provenance; changed
source runs normally. Deterministic regressions exercise failure→unchanged
reuse→revised program, exact Skeptic propagation, interrupted recovery, expanded
output storage, early EOF, stalled runtime, and hostile archives.

Agent instructions now state `/artifacts`, file/output/memory/time limits,
fresh-filesystem behavior, experiment design, numerical controls and the need
to inspect actual code rather than trust a printed answer. Removed a generic
"no tools" instruction that conflicted with the sandbox capability. The basic
workflow check now computes the line recurrence rather than printing a
hardcoded answer. No UI was added.

Six actual-Docker scientific workflows passed through scripted
Investigator→Python→Skeptic cycles. The scripted provider examines captured
results and carries its revised question into the next cycle. These establish
software behavior, not model research ability:

| Investigation | Actual observation |
| --- | --- |
| Catastrophic cancellation | At x=1e-16, direct evaluation returned 0.0 while the stable form returned 0.5; the revised experiment agreed with the SymPy limit 1/2. |
| Ill-conditioned Hilbert solve | Condition number about 1.60e13; relative residual 1.22e-16 but relative solution error 6.19 under a 1e-12 alternating perturbation. An initial test used only the first component and incorrectly expected error >0.1; its assertion failed. The recorded failure was retained, the perturbation was diagnosed, and a discriminating direction was used. |
| Singular system | NumPy's direct solve failed; the next experiment used least squares, found rank 1 and an explicit null vector, and did not mistake nonuniqueness for inconsistency. |
| Prime polynomial | No counterexample in n=0..39; an expanded exact search found n=40, giving 1681=41². The finite search was never treated as a universal proof. |
| Monte Carlo integration | 24 fixed-seed trials over 888,000 total samples; SciPy reference 0.7468241328124271; mean standard error fell from about 0.00636 to 0.000636. pandas CSV and Matplotlib PNG passed retrieval and SHA-256 checks. |
| Unbounded computation | A real 15-second timeout was followed by a changed finite geometric-sum experiment with an explicit 1.82e-12 remainder bound. |

Full sources, sessions, outputs and binary artifacts for these experiments are
retained locally under `projects/a19-computation-evaluation-20261023.sigma/`;
they are private local evaluation data, not committed fixtures. The actual
Docker adversarial script passed symlink/FIFO/nested/oversized/excess/invalid-name
artifact rejection, 32,000-byte control/invalid-UTF-8 outputs, host-file and
credential exclusion, exhaustion at 62 child processes, tmpfs exhaustion,
concurrent busy admission, repeated cancellation, and backend SIGKILL while a
detached descendant retained pipes. The runner watchdog and automatic removal
left no new running or stopped container. The container image was rebuilt for
the runner change.

Two real plan-backed trials used the already selected connected ChatGPT plan,
without paid API calls or any billing switch. Both timed out on their first
Investigator request at the then-current 60-second A18 deadline: High with a
4096-token output cap (session `e1cea997-a554-4a2a-a23e-e6157f7e2201`, 60.3 s),
then a changed Medium/2048-token experiment (session
`fd68c069-e608-4ec6-aea4-286f30f6142a`, 60.4 s). Each charged one dispatched
call to its local budget, produced no research artifact and ran no Python.
The records remain in `projects/a19-plan-stability-20261023.sigma` and
`projects/a19-plan-stability-medium-20261023.sigma`. Timed-out remote work may
consume plan allowance; usage could not be quantified. Live ability to choose
and critique computation is therefore still unverified by these trials.

Before the next A18 sync, `./sigma test` passed all checks and real Chrome
`browser_checks/a17_research.py` passed against a fresh local fixture and UI
from this checkout. Further validation against Blue's newly advanced branch
is recorded below when complete.

### Latest A18 integration, actual model evidence, and final checks

A19 now includes Blue's `a18-blue` tip `b5c8ff1`, through merge commit
`3195927` on Green's branch. Blue's branch was not changed. The merge preserves
peer handoffs, relation retractions, provider timeout classification and the
new 120-second provider deadline alongside A19's 256,000-character context cap.
The strict Skeptic fixtures were updated for the required
`retracted_cross_strategy_source_artifact_ids` field. The A19 diff against
that base remains confined to computation and its documentation/tests.

The integration review found another practical gap: peer and prior-session
summaries retained the Investigator's pre-run claim but omitted computation
status. They now carry attributed code/result previews with truncation flags;
the original exact evidence is unchanged. Simultaneous research proposals now
take turns through a cancellable gate before dispatch. This avoids spending
an entire model round on busy admission. A three-strategy actual-Docker
portfolio completed all three computations with distinct provenance. The
stop regression confirms that the already dispatched run is saved while the
two queued proposals never launch. Queued proposals are visible as
`python.queued`, and no new program starts after the session deadline. The
direct execution API retains its explicit busy status.

The expanded scientific harness passed **eight workflows and fourteen Python
proposals**, covering the original six scenarios, rejection of a hardcoded
printed "PROVED" claim with zero tested inputs, and the three-strategy
portfolio. Its scripted Skeptic now makes case-specific judgments from the
actual results: an exact prime counterexample refutes the universal claim,
small residual is insufficient accuracy evidence, singularity is not
inconsistency, and timeout is not mathematical refutation. The Monte Carlo
case also captured a 100,000-row, 1,896,400-byte CSV. Independent host parsing
checked row count, value range and the reported mean; retrieval hashes matched.
Latest scientific records are retained under
`projects/a19-final-large-data-20261023.sigma/`. These fixtures still cannot
establish live model judgment or general scientific competence.

After the A18 deadline changed, a bounded **real ChatGPT-plan** session
successfully exercised Investigator→Python→Skeptic. It used the already
selected plan, `gpt-6.1-sol`, Medium reasoning and a two-call cap; no paid API
call, account change or billing switch was made. Session
`3da31b2e-a751-4c17-8605-07cd01feff89` is saved in
`projects/a19-plan-stability-integrated-20261023.sigma`:

- Investigator returned after about 70.9 seconds, explaining the cancellation
  mechanism and proposing its own deterministic NumPy/Decimal experiment.
  Neither the stable formula nor expected answer was supplied in the project
  or strategy. The task is nevertheless a familiar elementary numerical
  stability problem; it is not evidence of hard independent discovery.
- Execution `70f38541-3ddf-4447-8f8d-d7137d47452f` completed in 281 ms.
  The program compared direct and rationalized formulas against 100-digit
  references, checked alternative 140-digit references and tried three grid
  sizes, boundary points and named inputs. At x=1e-15 the direct relative error
  was about 0.11182, versus 2.80e-17 for the stable form. The largest sampled
  stable relative error on the 1,028-input largest grid was 2.351010e-16.
- Skeptic finished at 110.7 seconds total. It inspected the code and successful
  execution, quoted the observed errors correctly, retained the arithmetic
  assumptions, distinguished samples from a uniform bound, and correctly
  recognized that the proposed zero range was sufficient rather than an
  exact cutoff. Source, exact stdout/stderr, image ID and provenance remain
  attached to the saved research artifact.
- A replay (`8e76a3fb-e928-4005-82d2-4344a3cb0c26`) produced identical output.
  A separate SymPy experiment (`df0a6d2d-142f-4a11-9ce2-6e74cc1aa234`) used
  exact rational representations of four binary64 inputs to independently
  confirm the error estimates and symbolically check the condition-number
  identity. These are reproducibility and arithmetic checks, not Lean proof.

The real Skeptic also exposed a workflow flaw: it asked for a new cycle just
to update the proposal's "not yet executed" prose, although that prose was
necessarily written before execution. The instructions now explicitly explain
that timing and ask the Skeptic to synthesize the attached result, retire
resolved execution obligations and avoid a rewrite-only cycle. The original
artifact remains **mixed/partial and unverified**, preserving the actual
review; it was not relabeled after changing instructions.

A separate bounded continuation to evaluate that correction and saved-result
reuse was rejected before output with HTTP 400 (`responses-error`, no specific
provider code). Session `f0f09b6b-d933-4a74-8a20-74f8e2ea643d` is retained in
the same project; its failure did not mutate the successful prior artifact or
trigger a billing fallback. The provider's precise cause is unknown, and no
more live calls were made. Across the four trials, five requests were
dispatched: two completed, two timed out and one was rejected. Usage metadata
was absent, so plan consumption cannot be quantified. The latest phase
guidance and cross-session synthesis remain unverified with a live model.

Final verification against the merged A18 code passed the full `./sigma test`
suite, all sandbox/scientific/adversarial scripts, separate Ruff checks for
`sandbox-poc/`, and real Chrome `browser_checks/a17_research.py` against a fresh
fixture from this checkout. The latter covered the latest Skeptic schema,
multi-strategy activity, control actions, existing workspace and exports.
Artifact tampering and parent-directory symlinks are rejected by deterministic
regressions. Artifact collection now shares the remaining execution deadline
instead of extending a near-limit run by another five seconds. The final
runtime and Investigator→Docker→Skeptic smoke checks passed after that change.

The final queue review also added a snapshot check immediately before Python
dispatch: disabling or editing a strategy while its proposal waits now pauses
the session, matching A18's provider preflight guard. A three-branch regression
changes the project while the first computation is active and verifies that
its result is saved while the two waiting programs never start. Existing
historical executions remain inspectable under their original provenance.

## T24: research outcome metrics (2026-10-23)

Outcome metrics are derived when persisted research sessions are read, with
independent operational and research-quality groups. Operational evidence
includes provider steps, token usage, durations, Python execution IDs, saved
file sizes, failures, retries and cost; research-quality evidence covers
investigated strategies, per-strategy cycles, outcome, verification, current
obligations, cited conclusions, attribution and unresolved objections. JSON
audit exports and text/HTML reports carry the same read-time projection.
Following PR #13 review, T24 supplies data only; T25 owns the Outcome UI.
The proposed Outcome metrics table and its CSS have been removed.

Call status accounting uses distinct persisted step IDs; interrupted requests,
timeouts, HTTP rejections and other failures stay separate. Repeated
strategy/role/cycle steps are shown as later attempts, with no automatic retry
assumed. A mismatch between the saved call counter and unique step records is
visible and leaves unrecorded statuses unavailable. Python totals use unique
execution IDs, so restart recovery and cross-cycle reuse do not add a second
run or duplicate captured file bytes. Concurrent strategy cycles are keyed by
strategy and cycle; session wall time is kept separate from summed call
durations, which can overlap.

Token aggregates are computed only from persisted validated provider usage.
Missing input/output metadata yields unavailable totals; a missing cached-token
field is unavailable rather than zero. Cached input remains a subset of input
when total tokens are calculated. ChatGPT-plan spend is reported as unknown,
including the historical T18/T19 plan trials whose allowance consumption could
not be quantified. Timeouts, interruptions, and provider rejections with no
usage evidence also keep API dollar cost unavailable. API-key estimates require
complete input/output/cached usage and a known model rate. The existing
standard, short-context model rates were checked against the [official API
pricing page](https://developers.openai.com/api/docs/pricing) on 2026-10-23;
values are labeled estimates and are not invoices. No provider calls were made
for T24.

Deterministic regressions now cover incomplete/mismatched records, absent token
and cache metadata, an actual mocked HTTP 400 response recorded as rejected,
timeout classification, cancellation and resumed retries, two concurrently
investigated strategies, duplicate step IDs, reused Python execution IDs,
artifact deduplication, cost availability, evidence-linked conclusions and
historical unknowns. Project report tests assert the metrics survive text and
HTML output. The pre-review Chrome run checked the proposed table, which has
since been removed per the T25 presentation contract. The revised Chrome
scenario checks the metrics/source inventory through the API and preserves
existing desktop/mobile Outcome interactions instead of prescribing T25 UI.

Early suite runs caught two Ruff formatting issues and one stale assertion after
the unavailable-token wording was clarified; the formatting and assertion were
corrected. After the last call-accounting and cost-date changes, final
`./sigma test` passed: all executable scenarios, 57 formatted Python files,
Pyright with 0 errors/warnings/information, frontend typecheck, and production
Vite build. The 10-strategy load completed 20/20 calls and 10 artifacts at max
concurrency 3. The original Chrome run passed with the table assertions before review;
post-review checks are recorded below. No live provider calls were made. Metrics improve attribution and
make gaps visible; they do not measure agent competence, establish research
effectiveness, or convert numerical/model evidence into mathematical
verification.


### T24 review revisions

The review identified a real export defect: `zip` truncated unequal metric
groups. Text and HTML exports now render each nonempty group independently;
HTML uses semantic label/value lists. Regressions cover either longer group,
either empty group, both empty, and escaped/delimiter-containing row content.
The last row of both groups survives in every applicable case.

`outcome.metrics.sources` adds a structured, deduplicated inventory of session,
step, artifact, execution and investigated-strategy IDs. The source records
remain unchanged and inspectable through session JSON and saved execution APIs.
This inventory is not per-row claim provenance or verification authority.
The [T24 data contract](T24-DATA-CONTRACT.md) documents existing claim citations,
role/cycle context, model/effort scope, exact Python evidence and file hashes,
and missing fields (notably explicit artifact-to-role-step foreign keys and
provider receipt IDs). T25 must preserve these unknowns rather than infer exact
attempt attribution from a strategy/cycle match.

The new `docs/ASSIGNMENT-A24.md` has been removed and the legacy assignment
tracker restored to avoid conflicting with PR #11's pending ticket migration.
The canonical T24 ticket will come from that PR; the supporting data-contract
document is not a replacement. PR #11 was still open when revisions began;
its unfinished migration has not been merged into this feature branch.

Post-review verification on 2026-10-23 passed: `./sigma test` (all scenarios,
Ruff, 57 formatted source files, zero Pyright errors, frontend typecheck and
Vite build), plus the real Chrome workspace scenario using fresh isolated
fixture servers on ports 8016/5187. The browser asserts that metrics and source
IDs remain available via the session API while the proposed Outcome table is
absent; existing plain/Markdown and mobile flows pass.

An additional real Chrome report experiment retained unequal metric groups at
desktop and 320px widths, with no page overflow. Visual inspection caught a
header-ordering issue when no outcome summary existed: metrics appeared inside
the session header before its status facts. HTML headings now flush that header;
a regression checks their order. The full suite and report experiment passed
again after the fix. I inspected the corrected mobile report and workspace
captures (`/tmp/sigma-t24-review-report-mobile.png` and
`/tmp/sigma-a18-coordinator-review-mobile.png`). Owned fixture/dev servers were
stopped. No paid or live-provider calls were made. PR #13 remains open for
review; T25 presentation and the pending PR #11 migration are separate work.


### T24 post-migration validation (2026-10-23)

PR #11 merged as `ccb6157`. Its current main was merged into the T24 branch
without conflicts; no old assignment files or legacy tracker were restored.
All 44 migrated historical documents were checked byte-for-byte against main.
Canonical `tickets/t24.md` and `TICKET_TRACKING.md` now point to PR #13's
reviewed implementation and pending final merge approval. The supporting
[T24 data contract](T24-DATA-CONTRACT.md) links to the canonical tickets;
T25 continues to own the Outcome UI.

Post-merge `./sigma test` passed: all executable/backend scenarios, Ruff checks,
57 formatted files, Pyright with zero errors/warnings, frontend typecheck and
production build. The 10-strategy regression completed 20/20 calls and ten
artifacts at concurrency three. The suite includes unequal/empty report groups
and escaped row content. No live or paid provider calls were made.

The real Chrome `browser_checks/a17_research.py` scenario passed again using
fresh isolated fixtures on 8016/5187. Strengthened assertions compare all metrics
and source IDs from the downloaded JSON audit to the session API, verify all
16 metric rows in the actual downloaded HTML and text reports, and retain the
existing desktop/mobile, Markdown, concurrent strategy, stop/resume and export
failure checks. A backend regression independently compares the persisted
session's metrics/source inventory to its JSON audit and every text/HTML row.
Thus operational/research-quality metrics and the documented provenance remain
available for T25 without adding Outcome markup.

A separate Chrome report experiment passed with either group longer, correct
session-header ordering, every metric row retained, and desktop/320px layouts
without page overflow. I inspected the new mobile report and desktop workspace
captures (`/tmp/sigma-t24-migration-report-research_quality-mobile.png` and
`/tmp/sigma-a18-coordinator-review-desktop.png`). Owned test servers were stopped.
PR #13 is ready for final merge approval; it has not been self-merged. Existing
provenance limitations in the data contract remain explicit, including absent
artifact-to-step foreign keys and unknown provider receipt/plan consumption.


## T26: first-class SageMath execution (2026-10-23)

Implemented from merged main `b917e24` and ticket/specification PR #20. Every
actual Investigator and Skeptic request now explicitly advertises both scientific
Python and SageMath, their observed local availability, proposal/result fields,
capabilities, bounds and evidence interpretation. The same prompt/schema builder
is used for dispatch and conservative cost reservation. Role steps save the
capability snapshot. Investigators alone dispatch; Skeptics inspect returned
source/results and request revisions through the next Investigator cycle. No
new provider calls, retries or billing fallback were added.

Sage uses a separate nullable `sage_code` proposal and `sage_execution` result;
both code fields cannot contain programs. The pinned official Sage 10.8 amd64
image runs native Sage preparsing under the shared fixed container runner. It
retains no-network/no-host-mount/non-root/read-only/no-capabilities controls,
source/output/artifact bounds and one shared admission/queue limit with Python.
Sage has explicit 60-second/1-GiB/128-MiB-temporary limits; Python retains
15-second/512-MiB/64-MiB limits. No runtime pull/build occurs. Optional
`./sigma sandbox-build --runtime sagemath`, `sandbox-capabilities`, and
`sandbox-execute` commands support setup and use; ordinary setup/tests do not
download Sage. See [Sage execution](SAGE-EXECUTION.md).

New records preserve runtime/version/native syntax, exact source and hash,
immutable image ID, status/output/files and project/session/strategy/cycle.
Sage agent records validate and retain the exact completed Investigator step,
role and model/effort configuration. Runtime-aware lookup/reservations prevent
Python/Sage source collisions and preserve interrupted/uncertain reservations
without rerunning them. Peer/prior-session previews, JSON audit and paper-source
exports retain Sage evidence with the original IDs. Metrics keep both engines'
statuses separate and count file storage/source IDs once. Independent metric
lists now have nine operational and eight research-quality entries, and text/
HTML exports retain all entries. Historical records remain Python by default.

The existing Outcome hierarchy exposes Sage status, execution ID and file
hashes through its evidence card. A source/output disclosure provides the full
escaped execution record for either engine. Visual review found that an
inherited global `dl` grid squeezed metric labels into alternating narrow
columns; the metric group now explicitly uses block layout. This is a scoped
layout correction, without replacing T25's hierarchy.

Failures found and corrected:
- The upstream Sage home directory was not searchable by UID 65532; the derived
  image fixes that at build time. Its outer HOME must be the existing /tmp;
  the runner then creates a private temporary Sage configuration directory.
- A new stop/resume regression found that the coordinator ended queued branches
  at their final round even with a pending Investigator result. The round limit
  now allows that existing cycle's Skeptic review to finish, preserving call
  budgets and avoiding duplicate computations.
- The first mixed-session test hit the existing one-active-session restriction;
  this policy is preserved. The test covers mixed concurrent strategies and
  verifies a second session is rejected before provider calls.

Verification completed on the final implementation:
- `./sigma test` passed: all scenarios including new deterministic Sage tests,
  Ruff, 59 formatted Python files, Pyright zero errors/warnings, frontend
  typecheck and production build. The ten-strategy regression completed 20/20
  calls and ten artifacts, max concurrency three.
- Deterministic Sage tests cover both roles' available/unavailable guidance,
  strict typed selection, every execution failure status, exact evidence and
  hash retrieval, role-step attribution, API/export/paper/peer/prior context,
  engine-separated recovery, uncertain interrupted reservations, failed-source
  reuse then productive revision, mixed Python/Sage queue stop/resume, and
  missing execution IDs shown unavailable. A stopped final-cycle computation
  is saved and reviewed after resume without a duplicate run.
- Explicit builds via SIGMA tooling passed for both runtimes. Final Sage image:
  `sha256:893cc1fd570d267cb57235f561ba3c7ac64c08ca2c86e48faba31ac1244bb41e`.
  The official amd64 base is pinned in `sandbox-poc/Dockerfile.sage`.
- `sandbox-poc/sage-check.py` passed on the final image: native polynomial
  algebra and exact rational/exponent semantics, factorization/modular inverse,
  elliptic-curve cardinality checked against independent finite enumeration,
  PNG/JSON generation and hash-checked retrieval, non-root/cgroup/capability/
  read-only controls, network denial, exception, unsafe symlink capture,
  output limit, memory exhaustion, 60-second timeout and caller cancellation
  that drains bounded execution and saves its actual result. The combined
  finite experiment took 29.751s; timeout returned in 60.082s.
- `sandbox-poc/sage-cli-check.py` passed through the public CLI: native
  factorization and `2^3 = 8`, saved source and runtime provenance (22.336s).
- Additional real helper-interface probe passed:
  `gap.eval('Size(SymmetricGroup(4))')` returned `24` and
  `singular.eval('ring r=0,(x),dp; poly f=(x-1)*(x+1); f;')` returned `x2-1`.
  This took 47.924s under amd64 emulation and left no running container.
- The rebuilt Python image passed `sandbox-poc/runtime-check.py`: scientific
  imports, actual finite computation/plot capture, network denial and memory/
  output/time limits. Its original deterministic regressions also passed.
- Real Chrome `browser_checks/sage_execution.py` passed against mock provider
  roles with the real final Sage image. The Investigator requested an exact
  experiment; Sage found 341=11*31 passing the base-2 Fermat test; the Skeptic
  received that contradicting evidence, its source, originating step and hash.
  Session/API/artifact/metrics/report access and desktop/320px views passed;
  the final source/output disclosure and metric block layout were checked.
  Last run: 24.965s; screenshots `/tmp/sigma-t26-sage-desktop.png` and
  `/tmp/sigma-t26-sage-mobile.png` were visually inspected.
- The existing `browser_checks/a17_research.py` Chrome workspace/export/stop/
  resume/multi-strategy scenario passed as a regression.

Limitations: this pins an amd64 image; arm64 was validated with emulation, not a
native arm64 Sage build. Cold startup is typically 20–30s here; helper interfaces
can use nearly the entire 60-second limit. Stop of dispatched work preserves
bounded-completion semantics and can wait for that hard limit/cleanup; it is not
an immediate kill. Admission is per backend process, not a host-wide scheduler.
Availability reports local image inspection, not a guarantee that a later
container launch cannot fail. Legacy pre-portfolio sessions truthfully report
computational dispatch unavailable and require a new session. Plot/binary
contents remain metadata to agents (T28 follow-up). No live-provider calls were
made; mock-agent tests do not establish real-model tool-selection quality or
mathematical proof. Docker's host kernel/daemon/image remain trusted boundaries.

Final reconciliation also tightened cross-cycle Sage failure reuse to matching
version/syntax/image profiles while preserving the original cycle's uncertain
reservation. Its deterministic regression passed; Pyright caught loop-scoped
fixture variables in that new test, which were initialized explicitly before
the final full-suite rerun. The public capability CLI reported both locally
built runtimes with their distinct 15s/60s limits.

T26 implementation is submitted in [PR #24](https://github.com/bkramerext/sigma/pull/24), open for review and not
self-merged. The [coordinator handoff](../messages/t26_coordinator_handoff.txt)
is created and ready to read. Final `./sigma test` passed after the profile
recovery and command-default checks; the worktree contains no test project
data. Owned browser fixture/dev servers were stopped, and no research
containers remained running.

## T27: Research intelligence and agent guidance (2026-10-23)

T27 addresses gaps found in the existing handoff and history paths. Before this
change, a peer relation could enter a target Investigator's question, but the
Skeptic did not receive that active handoff as a structured review obligation;
the coordinator then used the source relation directly. Prior sessions exposed
saved artifacts, but a provider attempt that failed before producing an artifact
was absent from subsequent investigations. The Investigator prompt also
advertised the Python environment without checking whether its sandbox image
was actually available, and the handoff queue silently discarded items beyond
four.

The implementation makes these paths evidence-linked and bounded. A new
session snapshots up to 12 prior failed or interrupted attempts using only
safe classification metadata, with an explicit omitted count and an 8 KB bound.
Prior saved findings now also retain bounded assumptions, assumptions reviewed,
limitations/proof obligations, and Python execution observations, with their
artifact IDs and unverified evidence status.
The Investigator must cite only supplied attempt IDs; the exact consumed IDs
are persisted on provider steps and resulting artifacts. Operational failures
are explicitly distinguished from mathematical counterexamples. The Skeptic
receives pending handoffs after the target Investigator uses them and must
return exactly one structured review per handoff. It compares assumptions and
domains, records accept-for-local-testing, reject, narrow, or unresolved, and
marks withdrawn evidence. Rejected transfers remain in the audit record but no
longer generate coordinator conflict/overlap/combination actions. Handoffs past
the four-item prompt limit are retained in a deferred queue and promoted as
capacity becomes available. The runtime prompt now receives the sandbox's
actual Python availability snapshot; unavailable Python must not be proposed.

Deterministic evidence:

- The multi-strategy regression `test_peer_finding_changes_target_investigator_after_stop_and_resume`
  sends a contradictory finding into the target branch, checks the changed
  Investigator method and exact source/target IDs after stop/resume, then checks
  that the target Skeptic reviews the same handoff. Its fixture identifies an
  integer-only source assumption versus a target over all real arrangements;
  the Skeptic rejects the transfer, the coordinator retains the rejection with
  both evidence IDs, and the target is not marked refuted. Baseline inspection
  and the earlier regression showed that the old flow checked only Investigator
  prompt uptake and had no Skeptic handoff decision.
- `test_failed_attempt_guides_next_session_with_provenance` starts with a
  provider failure and no artifact, verifies the next Investigator receives the
  failed attempt ID and changes to a bounded symbolic action, then verifies the
  exact reference is saved on the step and artifact. The earlier failed session
  file remains byte-for-byte unchanged.
- `test_peer_handoff_queue_defers_without_silent_loss` checks that six findings
  are retained as four prompted and two deferred, then promoted without loss.
  The domain-mismatch control also checks a withdrawal surfaced to a Skeptic
  after dispatch.
- Python guidance regressions exercise both runtime-present and unavailable
  snapshots. The Skeptic prompt calls finite computation evidence rather than
  theorem verification; existing sandbox scenarios continue checking execution
  capture, timeout, errors, restart recovery, and exact source provenance.

These are deterministic mocked orchestration scenarios. They demonstrate that
SIGMA now carries, validates, and acts on the intended evidence paths; they do
not establish that a live Investigator will reason correctly, that a live
Skeptic will notice a subtle mismatch, or that research quality improved on a
mathematical problem. No provider calls or paid/live evaluations were made for
T27. No browser checks were run because T27 changes no UI. The full test suite
passed on 2026-10-23: `./sigma test` completed all backend scenarios, the
10-strategy 20/20-call concurrency fixture, Ruff check/format, Pyright with
zero errors/warnings/informations, frontend typecheck, and the Vite production
build. The focused `tests/research_sessions.py` run also passed after the final
stale-handoff and prior-assumption changes. Live model behavior remains
unverified as required by the no-live-call constraint.

The response to the question about work continuing after browser closure is in
`messages/t27_browser_closed_research.txt`: session work is server-side and
continues while the backend remains running; backend restart interrupts an
in-flight call for explicit recovery rather than retrying it automatically.

### T27 PR #18 review follow-up (2026-10-23)

Prior-session failed/interrupted attempts are now globally sorted by attempt
recency, using finished/started/session timestamps, before the 12-attempt and
8 KB context limits are applied. `test_prior_session_failure_history_prioritizes_newest_attempts`
intentionally makes session creation order differ from attempt recency and
confirms the newest attempt is presented first.

Deferred peer handoffs now have an explicit per-strategy limit of 24. At
capacity, SIGMA keeps an overflow count and at most eight compact recent
omission records; older omission records increment a separate counter. The
coordinator decision exposes this bounded overflow summary. The regression
`test_peer_handoff_deferred_storage_is_bounded_and_reports_overflow` drives ten
handoffs past capacity and checks the deferred cap, recent-record cap, omitted
count, visible coordinator summary, and serialized branch size.

Verification after these review changes passed on 2026-10-23: focused
`tests/research_sessions.py` and `./sigma test`, including all backend scenarios,
the 10-strategy 20/20-call load case, Ruff, Pyright (zero errors/warnings),
frontend typecheck, and production build. No live provider calls were made.

## T22.2: Google authentication and invited access (2026-10-23)

Implemented cloud authentication as an explicit deployment opt-in. When enabled,
the FastAPI boundary requires a live server-side session for every API route
except readiness/status and the OIDC begin/callback endpoints; mutating requests
require the configured exact Origin. Local mode stays on the existing behavior.
The Google flow uses authorization code plus PKCE S256, one-time state and
nonce, fixed Google discovery/token endpoints, published JWKS signature
verification, exact issuer/audience, expiry, nonce, subject and `email_verified`
checks. Access is limited to normalized exact email entries, exact email domains,
and the configured bootstrap administrator. Explicit revoked email rules win
over domain rules. Session cookies are Secure, HttpOnly, SameSite=Lax host-only
cookies; only SHA-256 session digests are stored in a private SQLite file.

Administrators can list, add and revoke email/domain entries and grant an email
administrator role through the copper/dark Access Management UI. No invitation
emails are sent. Cloud mode denies the process-wide `/api/ai/*` endpoints so a
Google account cannot inherit local ChatGPT authorization or AI billing. The
bootstrap email is bound to its first Google subject. Configuration and setup
are documented in [CLOUD-AUTH](CLOUD-AUTH.md).

`tests/cloud_auth.py` uses generated local RSA signing keys and mocked Google
responses; it verifies successful bootstrap and individual invitation, exact
domain matching, lookalike denial, signature/issuer/audience/expiry/nonce/email
claim rejection, OAuth state replay, session expiry, revocation against existing
sessions, API route protection, spoofed identity-header rejection, missing
configuration fail-closed behavior, and local-mode compatibility. No live Google
or model-provider calls are involved.

Following the T22.2 acceptance update, an unauthorized valid identity now lands
on a distinct “Access not yet granted” page. Its three actions link to the
parent-T22 `/demo` route without creating a workspace, open a prefilled
`mailto:` invitation request using `SIGMA_CLOUD_ADMIN_CONTACT_EMAIL`, or restart
Google sign-in with `prompt=select_account`. The public status response exposes
only the configured contact and the current caller's own identity state; it
does not expose grants or other users. `/demo` is a no-workspace handoff page;
the curated read-only Demo and guest APIs remain T22 work.

Explicit limits: no per-user project/workspace isolation or migration, guest
Demo, durable job scheduling, cloud deployment, or hosted AI-provider auth was
implemented. The existing file-backed project API remains shared across
authorized cloud users, so this auth increment alone must not be treated as a
private multi-tenant research deployment. No deployment credentials or Google
OAuth client were created.

Final verification on 2026-10-23 passed: `./sigma test` (including six focused
cloud-auth tests, all backend scenarios, the 10-strategy 20/20-call load case,
Ruff, Pyright with zero errors/warnings, frontend typecheck, and production
build), plus `browser_checks/t22_access_denied.py` in real Chrome at desktop and
mobile viewport sizes. The browser check verified the denied screen, configured
prefilled `mailto:` request, account-switch link, and `/demo` handoff without
project or AI API calls. No live Google or model-provider calls were made.

## T22.2 PR #37 corrections (2026-10-23)

Moved cloud sign-in into the existing copper/dark Home header above Projects;
authenticated account actions now stay in the Home/project headers. Removed the
legacy Google placeholder. Unauthenticated cloud visitors render Home without
mounting the private App/catalog, so the screen makes no private project or AI
requests and creates no workspace. The local-disabled branch continues to mount
the original local App and APIs without cloud identity.

An unauthorized callback now issues no session and stores the verified email
only in a short-lived private denial record accessible through an opaque,
Secure/HttpOnly cookie. The denial endpoint is separate from status and exposes
only that attempt's email. The Home denial experience shows it and places it in
the prefilled invitation draft. Starting account selection removes the record
and cookie and retains Google's `prompt=select_account`. Curated Demo and private
workspace storage remain in parent T22 scope.

Correction verification passed on 2026-10-23: `./sigma test` (including eight
focused cloud-auth tests, all backend scenarios, the 10-strategy 20/20-call load
case, Ruff, Pyright with zero errors/warnings, frontend typecheck and production
build); `uv run --with playwright python browser_checks/t22_access_denied.py`
passed in real Chrome with cloud-denied and local-mode coverage at desktop and
mobile widths. No live Google or model-provider calls were made.

## T28: Computational evidence and artifact comprehension (2026-10-23)

T28 extends the existing Python and SageMath execution evidence. Agents now
receive bounded content inspections beside the persisted execution record:
PNG/JPEG artifacts receive a low-resolution grayscale rendering and recognized
text/CSV artifacts receive an escaped, bounded text preview. Each representation
states what it cannot show; oversized, corrupt, unsupported, missing or
integrity-mismatched files produce explicit notices. Inspection uses the
existing hash-checked artifact store and never changes the saved execution
status. At most two artifacts and 4 MB per file are inspected; image decoding
is limited to 2 million pixels, text to 1,400 characters, and raster previews
to 64 by 20 cells. Pillow is pinned at 13.0.0. This does not transcribe plot
labels or exact pixels, inspect arbitrary binary formats, or constitute visual
or mathematical verification.

Investigator and Skeptic contexts receive source, captured output/error,
runtime, status, originating step/session, limitations and bounded artifact
inspections from earlier Python and SageMath executions. Structured citations
must refer to supplied execution evidence. Failed computations cannot be cited
as results; artifact claims require an available inspection. Reuse keeps the
original execution ID and provenance, and the prior session's bytes remain
unchanged. Inspected previews are separately stored in the role step for audit.
Python and SageMath status metrics are separately aggregated from persisted
execution records (deduplicated by runtime and execution ID), including all
recorded statuses; artifact storage totals remain independently deduplicated.
A proposal without a recorded run is not counted as an execution.

Deterministic regressions cover a plotted image, CSV/text, corrupt and
oversized images/files, unsupported PDF, sidecar integrity failure, separate
Python/SageMath completed/failed/timeout/cancelled/other status counts, duplicate
references, artifact storage, proposal-only evidence, and cross-session
successful and failed Python/SageMath citations. The multi-session tests verify
that the later Investigator and Skeptic receive the earlier source, result,
inspection, status and provenance, and that no new execution is claimed.

Actual Docker workflow checks on 2026-10-23 used the locally available pinned
Python 3.12.8 and SageMath 10.8 images. Each wrote a Matplotlib/Sage PNG to the
existing `/artifacts` mount; execution completed and the persisted, integrity-
checked file was inspected successfully. A first Python container attempt
wrote to the read-only working directory and failed as expected; using the
supported `/artifacts` path succeeded. A first Sage plot omitted `var('x')` and
failed with `NameError`; explicitly declaring the variable succeeded. These
failures confirmed ordinary execution errors remain visible and do not produce
fabricated preview evidence.

`./sigma test` passed on 2026-10-23: backend regressions, the 10-strategy
20/20-call concurrency fixture, Python and Sage service tests, T28 regressions,
Ruff, Pyright (0 errors/warnings/informations), frontend typecheck, and Vite
production build. Direct `ruff check src tests sigma`, format check, and
Pyright also passed. An exploratory whole-repository Ruff command found three
pre-existing findings under `browser_checks/` and `sandbox-poc/`; the supported
suite scopes lint to `src`, `tests`, and `sigma` and passed. No browser run was
needed because no UI files changed. No live model calls were made, so live agent
interpretation quality remains unverified. Blue's T27 PR #18 was reviewed for
its evidence contract; commit 102ca15 is an ancestor of current `main`, and the
full suite was rerun with the merged T27 changes present.

### T28 rebase against Gray PR #35 (2026-10-23)

Rebased T28 onto current `main` at 9cb487e. The only conflict was the final
return in `_call`: Gray's commit requires usage to be read through `_usage(raw)`
for its provider response/token guard, while T28 needs citation validation
before returning. The resolved path performs `_validate_computation_citations`
and then returns `validated, _usage(raw)`. Gray's `MAX_SESSION_DURATION_MINUTES`,
1 MB response bound, per-call output-token check, current session defaults, and
T28's 32 KB prior-session evidence context are all retained. No Gray UI or
recents changes were edited.

After resolution, `tests/computational_evidence.py` passed, including separate
Python/SageMath run-status counts, and `tests/research_sessions.py` passed,
including its 10-strategy concurrent workload and Gray's provider/limit paths.
The full `./sigma test` then passed on the rebased tree, including backend
regressions, Ruff, Pyright (0 errors/warnings/informations), frontend typecheck
and the Vite production build. No live provider calls were made.

## T29 Human intervention during active research (2026-10-23)

Added a bounded `POST /api/projects/research-sessions/{id}/interventions` service
and a compact panel in each session. Users can submit an objection, evidence note,
or priority, targeting selected strategies and Investigator/Skeptic roles. The
session accepts at most 24 guidance entries and retains at most eight rejected
attempts in its bounded audit. Empty and malformed targets are rejected; guidance
does not change the model, billing mode, tool access, token/call budget, deadline,
or saved findings.

Delivery is serialized with worker step creation and pause/stop transitions using
the per-session state lock. Each targeted role receives guidance only when a
subsequent call is prepared. A call already in flight retains its original prompt.
The step stores intervention IDs; the intervention stores strategy, role, actual
cycle, step, dispatch/acknowledgment times, uptake, rationale, and repeated
attempts. Agent output must acknowledge each delivered ID exactly once or that
branch fails without committing that response. Interrupted calls are recorded and
re-queued only for a later explicit resume; provider failures remain
unacknowledged and are not automatically retried. Supersession is allowed only
before any delivery attempt and only with identical targets.

Deterministic regression evidence in `tests/research_sessions.py`:

- `test_concurrent_human_guidance_is_delivered_and_attributed` holds two
  Investigator calls concurrently, submits strategy-specific Skeptic guidance,
  and verifies only the targeted later Skeptic prompt receives it. The guided
  Skeptic changes its next question, the artifact cites the review ID, and the
  saved step/event/strategy/cycle attribution matches. Concurrent peer steps stay
  unguided and both branches complete.
- `test_intervention_delivery_pause_resume_keeps_attempt_provenance` pauses an
  in-flight guided provider request, confirms the interrupted call is not
  committed, resumes explicitly, and verifies the prior interrupted attempt and
  new acknowledged attempt remain distinct while earlier findings are retained.
- `test_intervention_recovery_supersession_and_rejection` simulates a persisted
  running call and backend recovery, checks interruption-to-queued recovery,
  pre-delivery supersession, the 24-entry bound, and terminal-session rejection.

`browser_checks/t29_intervention.py` uses real Chrome with the isolated fixture:
it submits during an active delayed call, verifies the call count does not change
on submission, checks per-role acknowledgment and audit persistence, and checks
desktop and 390px layouts. It passed; screenshots are
`/tmp/sigma-t29-intervention-desktop.png` and
`/tmp/sigma-t29-intervention-mobile.png`.
The deterministic provider fixture acknowledges only IDs in its supplied prompt.
No live provider calls were made. `./sigma test` passed, including the CLI smoke
check, Ruff, format check, Pyright (zero errors/warnings), frontend typecheck and
production build (T29 adds no CLI command).

Limitations: acknowledgment and uptake are structured agent self-reports, not
independent evidence that a user-supplied claim is true. Guidance is not injected
retroactively into an already-dispatched call. Paused/stopped sessions retain
queued guidance for a later explicit resume. Old legacy sessions without
strategy-bound execution records reject guidance. Invalid requests rejected by
HTTP schema validation do not create session audit entries; accepted and
service-level rejected requests are audited within the configured cap.

### T29 integration with T28 and T21 on current main (2026-10-23)

Integrated current main at `317c5c46` after T28 merged, then incorporated the
newer `ef3aadcc` T21 alpha acceptance update and the documentation-only
`e033173` and `e58eccd` software-factory protocol commits. Latest base
`e58eccd525e475a53319364b1eb8175d711f66f2` was merged at tested head
`301ca1762983cdcb3aad4ed1c1548c4e9b0dd03f`. Conflict resolution preserves
T28's SageMath execution records, bounded artifact inspections, and required
computation citations alongside T29's intervention reviews and per-step
provenance. The provider fixture now returns both required citation and
intervention-review fields. On the latest merged tree, `./sigma test` passed,
including research-session concurrency/recovery, T28 citation and artifact
regressions, CLI smoke, Ruff, format check, Pyright (0
errors/warnings/informations), frontend typecheck, and production build.

The first Chrome run correctly exposed that the deterministic provider fixture
did not yet emit T28's required empty computation-citation list when no tool was
used. The fixture now emits it, and project names are unique across reruns. The
real Chrome T29 check then passed at desktop and 390px mobile: guidance submitted
during an in-flight call made no extra call, subsequent target-role acknowledgments
and audit provenance persisted, and the mobile layout had no horizontal overflow.
The real Chrome check passed again after the latest main merge, at desktop and
390px mobile. No live provider calls were made.

## T30: Create Samples from exported projects (2026-10-23)

Added the curator command `sigma make_sample exported_project.json --name
sample_name`. It accepts the current SIGMA project export v2 JSON, validates the
project through the existing strict project decoder, and writes the validated
project definition plus a sanitized evidence sidecar into `samples/<name>/`.
Names are lowercase alphanumeric/hyphen slugs, the 32 MB export/storage bound is
explicit, and existing catalog entries are never overwritten.

The existing Samples browser continues to discover generated entries through
`project.json`. Opening a generated sample still goes through
`open_sample_project`, creates a new project UUID/location/title, preserves
strategy IDs/history, and installs public research-session and agentic-run
records into the existing project evidence stores. Copied session/run records
are rebound to the new project identity and canonical path; computation/finding,
step, strategy and session IDs remain stable. Sensitive fields (credentials,
identity hashes and private config), recognized bearer/provider key patterns,
user home paths and path-valued metadata are removed or replaced. Opening and
editing the copy does not mutate the source project or sample template.

The mandatory acceptance regression creates a two-strategy project, runs a
successful Investigator/Skeptic cycle with captured Python code and output, and
saves a failed provider session plus an agentic run. It exports through the
existing `export_project_view`, invokes the actual CLI parser with the requested
`make_sample` command, loads the resulting entry through `sample_projects` and
`open_sample_project`, then checks research outcomes, failure status, strategy
and execution provenance, computational code/output, agentic-run history,
independent strategy edits, and byte-for-byte source immutability. It also
checks that injected credentials and home paths are absent from both generated
JSON files. A discovered export-shape issue was fixed: API dataclass exports
contain null optional event fields, while `_decode` accepts canonical persisted
events only. Import removes only those known null optional event keys before
strict validation. Session exports omit `project_path`; the copy loader binds
that field to the new project path so the standard session store can read it.

Known export limitation: export v2 contains computational execution metadata,
code/output/errors and T28 previews within research-session evidence, but does
not contain raw execution-store binary artifacts. The converter retains the
available records and previews and does not invent binary files; links needing
the original raw bytes remain unavailable in a generated sample. The sanitizer
handles the current export's known private fields and common credential/path
forms; arbitrary unlabelled secret-like text cannot be classified reliably.
No UI or active research execution code was changed. No live or paid provider
calls were used. Final verification on the T30 branch passed:

- `uv run --locked --no-sync python tests/make_sample.py` — exported project to
  CLI sample creation to existing sample loader passed, including successful
  Python evidence, failed session, provenance, independent edit, redaction and
  source immutability.
- `./sigma test` — all backend scenarios, sample acceptance test, Ruff,
  formatting, Pyright (0 errors/warnings/informations), frontend typecheck, and
  production build passed.

The suite emitted existing Starlette/httpx deprecation warnings; they did not
fail tests. No live or paid provider calls were made.

### T29 refresh against PR #40 / current main (2026-10-23)

Merged latest main `7f84d40d7e2cee8ed14423384362319ba6485580` at tested
integration head `46e5ce5928481a2ea4dac766ecb7f960592ce728`. This brings in PR #40's
sample-from-export work plus the intervening software-factory and T22 acceptance
documents. Conflicts were limited to `TICKET_TRACKING.md` and `docs/STATUS.md`;
both T29's open-review entry and its full evidence section were kept alongside
T30's tracking and evaluation. The automatically merged code retains the T29
intervention endpoint, agent prompt delivery/acknowledgment validation, UI, and
regression tests. `./sigma test` passed on the integrated tree, including T29
concurrency/recovery, T30 exported-sample import, computational evidence, CLI
smoke, Ruff, format check, Pyright (0 errors), frontend typecheck, and production
build.

The real Chrome `browser_checks/t29_intervention.py` check also passed on that
tree at desktop and 390px mobile. It verified guidance submitted during an
in-flight request causes no extra call, the targeted agent-step acknowledgment
and provenance persist, and the mobile UI has no horizontal overflow. No live
provider calls were made.

## T22.2 PR #37 review corrections on current main (2026-10-23)

Starting `/api/cloud-auth/login` now deletes the presented prior session digest
from the private auth database and expires the host-only session cookie before
beginning account selection. The denied callback also defensively deletes any
presented session and expires its cookie, so a valid but unauthorized Google
identity cannot leave an earlier account active. Authorized account switching
uses the same fresh-login boundary. Local mode continues to bypass cloud auth.

The administrator Access Management dialog now shows the configured bootstrap
administrator and currently authorized sessions with role and expiry. Its
backend summary removes expired or revoked sessions before returning them.
Current-main project difficulty/catalog/header changes are retained, while the
legacy Google placeholder is removed from project headers in favor of the cloud
identity control when cloud auth is enabled.

Deterministic `tests/cloud_auth.py` coverage now exercises authorized A to
unauthorized B, authorized A to authorized B, and unauthorized B to Use Another
Account against the real FastAPI middleware, SQLite session database, cookie
responses, and protected API routes. It checks prior-session deletion and the
appropriate private API access at each transition. The domain/revocation test
uses separate browser clients for administrator and member identities.

Validation on this integrated head passed: `./sigma test` (backend scenarios,
all 10 cloud-auth tests, concurrency workloads, Ruff, format, Pyright with zero
errors/warnings, frontend typecheck, and production build) and
`uv run --with playwright python browser_checks/t22_access_denied.py` in real
Chrome. The browser check covers the denied screen and request, account switch,
Demo handoff, unrestricted local Home, and administrator session summary. No
live Google or model-provider calls were made.

### PR #37 refresh against main (2026-10-23)

Fetched main at `6b6d1e458495d93dec0f78b2b983cf3b3acf39cc` and merged it into
T22.2 at `e8ccb8e21b5bc87d738b67cc190a3bf5f2d54bd2`. The only textual conflict
was `docs/STATUS.md`: retained T29's new intervention evidence and the existing
T22.2 auth correction evidence together. `TICKET_TRACKING.md` and the T29 API,
research-session service/tests, and frontend UI merged automatically; no
functional hunk was discarded. T22.2 account-switch invalidation, admin
session summary, cloud API protection, and local unrestricted mode remain in
the integrated tree.

On the integrated tree, `./sigma test` passed all backend scenarios, including
10 cloud-auth tests, Ruff, format check, Pyright (zero diagnostics), frontend
typecheck, and production build. Real Chrome checks also passed:
`browser_checks/t22_access_denied.py` covered denied-account actions, request
prefill, Demo handoff, local unrestricted Home, and Access Management session
summary; `browser_checks/t29_intervention.py` covered intervention submission,
no extra provider call, acknowledgment provenance, and mobile layout. T29's
isolated fixture ran on port 8003 because port 8002 was already occupied by a
different checkout; that listener was left untouched. No live provider calls
were made.

## T22 Gate A private workspaces against merged PR #37 (2026-10-23)

Integrated current `main` at `24ca812f8502c594a673e7233bd7962e9b8c907b`
(`24ca812`) into the private-workspace branch. Resolved the `src/sigma/api.py`
conflict by retaining PR #37's cloud-auth middleware, trusted-host setup and
router while adding a FastAPI request dependency that consumes the middleware's
actual `cloud_auth.Principal`. Protected requests fail closed without that
principal. Workspace selection uses only its verified Google `subject`; email,
role, request headers, browser-supplied workspace IDs and paths do not select
storage. Authorized OIDC callbacks provision an empty workspace before issuing
the session. An unauthorized callback creates no workspace, and storage failure
prevents session issuance.

While validating, `origin/main` advanced to `a486833368156c8a2c0e941bcc43868f808185f0`
(`a486833`). Merged that current head as `a21074d`; its delta from PR #37 was
T38/T39 evaluation tickets and software-factory documentation only, with no
application-code conflicts. The final checks below ran after that merge.

The mapping database stores a domain-separated subject hash and a random
server-generated workspace ID. Project creation and all project-path services
run under that request's workspace root; symlink, traversal and cross-root paths
map to a generic 404. Recent-project state and proposal-cancellation IDs are
workspace-scoped. Existing local project roots, recents, ChatGPT authorization,
and CLI behavior remain active when cloud auth is disabled. The shared Samples
catalog is read-only; opening a sample copies it into the current user's root.
No legacy local projects are migrated or copied automatically.

Added deterministic two-user integration coverage using a separate Uvicorn
process around the production FastAPI app and real persistent project services.
It checks isolation for projects, strategies, sessions, exports/reports,
executions (including failed records), artifacts, paper URLs, proposals,
text, and Recent IDs; forged headers; copied IDs and paths; traversal and
symlinks; revocation data retention; server restart; and an offline workspace
backup/restore preserving owner mappings and artifact bytes. A focused
cancellation regression checks that another workspace cannot cancel a proposal
by guessing its request ID. `tests/cloud_auth.py` now also verifies the actual
mock-Google -> session -> merged middleware -> workspace path and proves
forged subject/email/workspace headers cannot override the principal or cause a
second mapping. An unauthorized identity does not provision a workspace.

Real Chrome `browser_checks/t22_private_workspaces.py` passed with separate A/B
browser contexts routed through the actual API/storage fixture: each created
project appeared only in its own Recent list and a copied cross-user project
path returned the generic 404. The existing OIDC/auth regressions passed all 10
cases. Final `./sigma test` passed, including all backend tests, the new
workspace and auth regressions, Ruff, format check, Pyright (zero diagnostics),
frontend typecheck and production build. No Google or provider service calls
were made. Ruff initially found import ordering/formatting issues and the test
suite caught a bad test expectation on the stateless `/api/projects/close`
endpoint; those were corrected before the final passing run. Starlette's
existing `httpx` deprecation warnings remain informational.

API ownership review found no uncovered private project/session/artifact path
in the current route set: path-bearing operations reach the common
`projects.project_path` boundary, root-based create/destination operations use
the bound workspace, and recents/cancellation use workspace state. `/api/ui-instance`,
the read-only shared Samples catalog, general execution-capability metadata,
and authenticated `/api/cloud-auth/*` administration are separate surfaces.
Gate B remains a required dependency before cloud research execution is
deployment-ready: current cloud auth blocks `/api/ai/*`, but model-backed
project routes such as proposal generation, research-session start, paper
generation and text conversion still use the process-level provider context if
configured. They are project-path scoped but not yet authorized against
per-user provider credentials/budgets. This increment did not add Gate B's
provider authorization, durable-job controls or compute budgets, and no paid
calls were made. Public Demo behavior and cloud deployment remain later T22
gates.

## T22 Gate C public Demo implementation (2026-10-23)

The hosted `/demo` route now shows one curated, read-only SIGMA research
experience adapted from `samples/handshake-count-easy/project.json`. It includes
project details, two strategies, a saved session and outcome, saved analysis,
research evidence, a finite computation, and its captured CSV artifact. The
snapshot uses stable IDs and timestamps and explicitly identifies its finite
check as illustrative evidence, not a proof.

Guests, denied Google identities and signed-in visitors read only the
server-configured `SIGMA_CLOUD_DEMO_AUDIT` audit snapshot through dedicated
GET-only endpoints with no client-supplied project ID or path. Reports use the
existing A17.5 export dialog and project report renderer for JSON audit, Text,
HTML and LaTeX. Private project routes remain behind cloud authentication;
missing Demo configuration fails closed. The cloud Home exposes an Explore Demo
link, the invitation request remains reachable from the denied flow, and local
SIGMA continues to bypass cloud authorization and show its full project UI.
Implementation does not alter Green's workspace branch or storage design.

After current main advanced to `113436118514ff7cca2c806c8924f958ff16392f`
through Gate A private-workspace PR #43, the public-Demo branch integrated that
head. Conflicts in `src/sigma/api.py` and `docs/STATUS.md` were reconciled: the
Demo now runs in a mounted read-only sub-application outside the app-wide
private-workspace dependency while remaining subject to the parent cloud-auth
middleware, and both Gate A and Gate C status evidence are retained. No
workspace implementation was rewritten. On this integrated
tree, `./sigma test` passed all backend scenarios, including Demo and cloud-auth
security tests, Ruff, formatting, Pyright (zero diagnostics), frontend typecheck
and production build. Real Chrome checks passed for
`browser_checks/t22_demo.py` and `browser_checks/t22_access_denied.py` at 1440px
desktop and 390px mobile. They verified saved-data inspection, read-only controls,
four exports, the denied invitation flow, anonymous Home Demo navigation, and
unrestricted local Home. API tests use the real FastAPI middleware and ensure
guests cannot read or export arbitrary projects, cannot mutate, and do not
trigger model or execution functions; they also compare the snapshot bytes
before and after browsing/exports. Browser API payloads and exports use the
deterministic snapshot fixture. No live Google sign-in or paid provider calls
were made.

Known integration limit: deployment must install the curated snapshot at its
configured `SIGMA_CLOUD_DEMO_AUDIT` location. Gate A private-workspace isolation
is integrated from PR #43; Gate B provider authorization/budget controls and
cloud deployment remain open in parent T22. This PR does not claim those gates
are complete.

## T39 adversarial RH evaluation tooling (closed 2026-10-23)

**Status: DONE for the scoped tooling deliverable; merged PR #47**
(`2c533a11dfbc27e0078c99127a41c6f24c8e5197`). The coordinator delivered
an exact degree-six mathematical countermodel, an exact finite-eta identity
positive control, four answer-redacted adversarial challenges, an offline human
scoring/review contract, and capture of acknowledged Skeptic interventions from
persisted research-session steps and same-cycle artifacts. Deterministic tests
were added to `./sigma test`. No paid provider calls were made.

**Not validated by closing T39:** the new tests have not been executed in the
coordinator's environment against the full checkout; real challenge delivery,
live Investigator/Skeptic mathematical judgment, multi-session adaptation,
reports and UI quality remain **UNVERIFIED**. T39's closure records delivery of
the evaluation infrastructure, not acceptance of SIGMA's research capability.
Real-agent validation and any failures found belong in a separate follow-up
research-quality evaluation ticket rather than being silently counted as MET.

## A17.8 follow-up acceptance preparation (2026-10-23)

The coordinator reviewed the 2026-10-22 A17.8 live/evidence record and
published an [answer-free independent-discovery acceptance packet](evaluations/a17-8-independent-acceptance-packet.md).
It defines a fresh-project Maximum Regions trial without copying the
answer-bearing sample strategy, a pre-run leakage checklist, bounded session
limits, human proof-assessment anchors, a deterministic distinct-problem
control, and precise provenance requirements. The packet was **not run** and
does not contain an evaluator answer key.

**A17.8 remains NOT ACCEPTED.** Previously reported criteria 2–5 and 7–8
retain their documented scope and evidence. Criterion 1 is **UNMET** in the
earlier contaminated-strategy live run; independence and quality in a fresh
answer-free run remain **UNVERIFIED**. Criterion 6 is deterministic-only.
No new provider calls or model fees were incurred. The coordinator has GitHub
repository access but not access to the running local SIGMA session/provider.
Do not treat protocol creation or T39 tooling closure as live-agent acceptance.


## T22 Gate B durable bounded research (2026-10-23)

Started `feature/t22-gate-b-durable-execution` from merged Gate A main at
`1134361`. Gate B keeps the existing Research Session/project JSON as the
source of truth for session transitions, events, model outputs, computational
evidence and outcomes. Added a private SQLite admission/accounting ledger beside
cloud workspace storage for owner-bound jobs and provider-call reservations.
SQLite immediate transactions serialize queue admission, concurrent worker
claims, global inference-spend reservations and per-user token reservations.
The cloud path requires an explicitly configured server API key, a reviewed
model price, a per-session cost ceiling and a global spend ceiling; it never
uses the local checkout's provider key or ChatGPT account. Standalone cloud
proposal, agentic-proposal, paper-generation and text-conversion routes are
blocked until they have bounded accounting of their own. Local mode retains
the existing provider and worker behavior.

Every model call writes a project-record `preparing` step, then a durable
ledger reservation and a project-record `reserved` state before provider I/O.
Known usage reconciles the held estimate. Timeout, cancellation, or restart
records an unknown attempt and retains the spend/token hold; start idempotency
and call IDs prevent replaying the same reservation. A queued job with no
provider attempt can be scheduled after an owner reconnects. A running job is
reconciled as interrupted and is not automatically replayed. Per-user/global
worker and queue ceilings are environment-configurable and fail closed.

Deterministic regressions exercise duplicate start/attempt IDs, concurrent
two-workspace claims and spend races, token/spend exhaustion, owner denial,
known/unknown/not-dispatched accounting, cancellation and timeout, queued
reconnection, interrupted session recovery, and the authenticated HTTP
start/status/idempotency/cross-owner workflow with a fake provider. Cloud
workspace regressions also confirm standalone inference routes return 403.
`tests/cloud_research_api.py` uses the production FastAPI route/services and a
deterministic principal fixture; it does not contact a provider. The real
Chrome `browser_checks/t22_private_workspaces.py` continues to pass A/B
workspace isolation through the production API fixture.

Final verification on this branch: `./sigma test` passed all backend scenarios,
including cloud-auth/workspace/research regressions, Ruff, format check, Pyright
(zero diagnostics), frontend typecheck and Vite production build. The command
`uv run --with playwright python browser_checks/t22_private_workspaces.py`
passed in real Chrome. No provider or Google calls were made. The first local
Playwright invocation without `--with playwright` could not import the optional
browser dependency; rerunning with the documented ephemeral dependency
provisioning passed. Existing Starlette/httpx deprecation warnings remain
informational.

Added `browser_checks/t22_durable_research.py` and ran
`uv run --with playwright python browser_checks/t22_durable_research.py` in
real Chrome. Two authenticated browser contexts start/reconnect around a
blocked fake provider call; both contexts disconnect, the backend process is
hard-killed, and a fresh backend reads the same persistent workspace. The
owner sees a paused session with an unknown attempt, a second owner receives
404, and repeating the same start key returns the original job without a
second fake dispatch. This exercises actual process restart and browser
disconnect without live Google or provider calls.

No cloud deployment/restart or paid provider smoke test was run. The global
spend ceiling accounts conservatively for ambiguous calls; operator-visible
cost is an estimate, not a provider invoice. The SQLite queue and project-file
writes are separate durable stores: a process crash between queue reservation
and initial project-session publication can leave an orphan queue row that
consumes a queue slot until manual ledger repair. These remain deployment and
availability limitations; Gate C, public Demo, Cloudflare deployment, and
public release remain out of scope.
