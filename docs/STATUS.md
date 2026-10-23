# SIGMA status

## A18 continuation: live research and portfolio coordination (2026-10-22)

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
  separate from the 60-second model-call timeout. A deterministic recovery test
  forces a preflight timeout, verifies zero calls were charged, then resumes and
  completes one full Investigator/Skeptic cycle.
- Corrected the ladder documentation count: it has five runnable samples.
- Added the run protocol and scoring rubric in
  [the research ladder evaluation](evaluations/rh-research-ladder.md). Exact
  finite checks in `tests/research_ladder.py` validate example arithmetic only;
  they do not prove any analytic claim or RH.

### Live ChatGPT-plan evidence

I checked the active provider mode before each session; both were `chatgpt`,
connected, and used the configured `gpt-6.1-sol` / High setting. No request was
sent unless that check passed. The two captured project/session records remain
locally available under `projects/` and are not committed as source fixtures:

| Stage | Saved project and session | Calls / elapsed | Result |
|---|---|---:|---|
| Easy: Counting Pairwise Handshakes | `projects/a18-live-easy-20261022-232853.sigma`; session `1935da6d-5ad6-4d64-9982-06fe5f802300`; artifact `5f2e756e-f7ae-4780-9424-763195af2e7f` | 2 / 39 s | Completed. The Investigator derived `n(n−1)/2`, checked `n=1,2,3`, and supplied an incidence-count argument. The Skeptic raised a specific objection: the distinct-person convention was assumed rather than tied to the wording. It asked for the alternative convention to be handled. The saved outcome is **Mixed · partial progress, unresolved**, with verification `incomplete`; it did not label the result verified. |
| Medium: Prime Factorization and the Euler Product | `projects/a18-live-medium-20261022-233002.sigma`; session `16316d1d-fdca-4042-85dd-79e03828920f` | 2 dispatched / 40 s | Both concurrent Investigator calls timed out before producing an artifact. The session records both branches as failed, with `hold_after_failure`; strategy assessments are `not_used`, and the outcome is `Pending · execution failed`. No inference about either mathematical approach was made. The configured cap was four calls; no Skeptic calls were dispatched. |

Together these account for four dispatched plan calls: two completed and two
timed out. The session records contain no token-usage metadata, so token use
and remaining plan allowance cannot be quantified here. A timed-out remote
request may still consume plan allowance. There was no reported HTTP 429,
quota-limit response, or automatic billing fallback, but I stopped live
experiments after the two timeouts because further calls would add uncertain
usage without resolving whether the provider was simply slow or limited. No
Hard or RH live session was run.

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
- **Cross-strategy reasoning:** The software validates exact peer citations and
  only suggests a combination for reciprocal complement judgments. The live
  Medium run failed before peer evidence existed; model ability to make useful
  cross-strategy decisions is therefore unverified.

At the time of the Medium run, the provider timeout was 40 seconds; both
concurrent High-reasoning requests reached that bound. I have raised the
per-request bound to 60 seconds, while retaining the separate configured
session-duration ceiling, and added a deterministic test that exercises SIGMA's
own timeout cancellation path. This change has not been re-evaluated live
because the timed-out calls may have consumed plan allowance and no usage
metadata is available. The system still has no external reference search,
computation tool, or formal proof checker; model statements cannot certify
mathematical truth.

### Verification

- Final `./sigma test` passed after adding all five samples, the timeout
  isolation regression, and the terminal-recommendation fix. It covered all
  executable scenarios, Ruff check/format, Pyright, frontend typecheck, and
  production build. The ladder check confirmed five independent sample copies,
  answer-free Easy inputs, exact finite Euler/eta arithmetic, and theta spot
  checks; its printed note explicitly limits those checks to finite examples.
- An additional adversarial lifecycle pass added preflight-failure, preflight
  timeout and recovery, queued branch stop, and duration/call-limit resume regressions. The final full-suite
  `./sigma test` passed on 2026-10-22, including Ruff check/format, Pyright
  (zero errors), frontend typecheck, and the production Vite build.
- Real Chrome `browser_checks/a17_research.py` passed against a local provider
  fixture at desktop (1440px) and mobile (390px), including multi-strategy
  selection, stop during provider work, resume, and the coordinator panel. I
  inspected both screenshots. Real Chrome `browser_checks/a20_paper.py` also
  passed after setting its dedicated UI/fixture ports explicitly.

**Recommendation:** Accept the coordinator and failure-handling engineering as
implemented once the final full suite passes, but do not accept A18 as evidence
of research effectiveness. Live evidence is limited to one elementary result
with a useful criticism and one Medium provider timeout; strategy improvement,
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
[design](asn6-design.md) and [decisions](DECISIONS.md) for limits.

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
[asn8.2-security.md](asn8.2-security.md).

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
