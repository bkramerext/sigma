# A18 — Research quality and integration

Status: **ready for Blue implementation**. A18 is the integrated local research-quality and reliability milestone. The former A19–A21 roadmap is not a dependency; A20 AI-authored papers is a separate, already authorized feature, and A23 project difficulty is implemented. A22 cloud migration remains separate.

Read `docs/HUMAN-AI-INTERACTION.md`, `docs/ASSIGNMENT-A17.6.md`, and `docs/STATUS.md` before implementation. Inspect the current code and tests before proposing changes. Preserve local operation and existing user workflows.

## Why A18 exists: SIGMA's defining product promise

**Blue: this is a long-lived, product-defining assignment, not a collection of small stories.** SIGMA exists to help people make real progress on hard problems that cannot be solved in one prompt, one session, or by a single line of attack. The research may span days or weeks, involve competing ideas and dead ends, and require revisiting assumptions as evidence accumulates. If SIGMA cannot sustain and organize that work, the product does not fulfill its purpose, no matter how polished the interface or how many agents it can launch.

A productive SIGMA user should be able to state a difficult objective, develop or generate several meaningfully different strategies, set multiple agents to work on them, and understand what is happening without micromanaging every step. Agents should do substantive work: derive, test, challenge, compare, revise, and sometimes reject approaches. The system should help the user distinguish a promising mechanism from attractive speculation, recognize when a proof or experiment is incomplete, and decide what to investigate next. Failed approaches and negative findings are valuable if they prevent repeated wasted effort.

The user should be able to interrupt the investigation, inspect a trustworthy record of claims and evidence, fork an approach based on what was learned, redirect effort, and return later without reconstructing the project's intellectual history. SIGMA should preserve *why* decisions were made, what remains unresolved, which strategy contributed what, and how confidence is justified. Human supervision should be practical at the level of research goals and strategy, not an obligation to babysit every model call. Concurrent agents should expand the breadth and critical depth of inquiry while remaining visible, bounded, and accountable.

**Build the integrated experience, not a checklist of disconnected features.** A18 is intentionally ambitious and may take sustained engineering effort. Own the end-to-end product outcome, make coherent architectural improvements when needed, and keep the research loop working as a whole. Use intermediate checkpoints, tests, and PRs to control risk and communicate progress, **not to redefine A18 into a sequence of tiny independent stories or to defer essential capabilities**. If a requirement conflicts with real usability, reliability, or research integrity, investigate and propose the best integrated solution rather than implementing the words mechanically. Escalate material product tradeoffs, but otherwise exercise engineering ownership.

The bar is complete solutions on Easy and Medium problems, and substantive, defensible progress on Hard problems; do not pretend a finite test suite establishes universal coverage. The bar is that SIGMA can pursue them intelligently, make and preserve defensible progress, expose uncertainty and failure honestly, and substantially improve a human researcher's ability to organize and advance difficult work. **That is the reason for A18 and the standard by which it will be judged.**

## Objective

Make SIGMA a dependable local research system that produces useful, evidence-backed progress through bounded agentic investigation, preserves that progress, and can be meaningfully supervised by a human. Improve the actual research mechanism and end-to-end reliability, not the number of features or panes.

A17.6–A17.8 are integrated. Read and preserve their current outcome-recognition, verification-label, Strategy Assessments, and evidence contracts. In particular, `docs/STATUS.md` records that A17.8's Maximum Regions live trial **did not demonstrate independent discovery** because the sample strategy already contained the solution. Do not repeat that leakage or count that trial as A18 research acceptance. Integrate with A20 paper generation and A23 difficulty without broadening their scope.

## Scope inherited from A18–A21

### 1. Substantive research iteration (former A18)

- Audit the current Explore / Challenge / coordinator cycle, research-session execution, and persisted artifacts. Identify concrete failure modes before changing architecture.
- Each bounded iteration should have a research question or proof obligation, a specific proposed mechanism or claim, an appropriate test or critique, and an evidence-backed disposition. Avoid generic brainstorming, repetition, and conclusions based only on agent confidence.
- Make critique genuinely adversarial and specific: check assumptions, attempt counterexamples, identify missing derivations, and separate established facts, numerical evidence, provisional hypotheses, and independently verified results.
- Preserve useful negative findings and unresolved obligations. Do not fabricate proof, independent verification, experimental results, or novelty.
- Respect existing model/account selection, token/call/time budgets, cancellation, and durable evidence boundaries. No hidden provider fallback or uncontrolled autonomous loops.

### 2. Cross-strategy coordination (former A19)

- Use the project's saved, enabled strategies as distinct candidate approaches, not interchangeable prompt text. Maintain their identity and provenance through agent activity and artifacts.
- Compare strategies by concrete evidence and outstanding obligations. Choose whether to continue, test a different approach, combine evidence, or stop based on explicit reasons and available budget.
- Avoid repeatedly trying a disproven or exhausted mechanism without new information. Preserve a record of why a direction was pursued, rejected, or revisited.
- Keep the session-level outcome and strategy-specific contribution assessments consistent with A17.6; **do not independently redesign those labels or duplicate its implementation**.
- Coordination must work with one strategy as well as multiple strategies; disabled strategies must not enter new sessions.

### 3. Human supervision and research continuity (former A20)

- **Reuse the existing Project → Research Session → Strategies workspace.** Do not introduce a new cockpit, dashboard, pane, or navigation system.
- Make current research activity, findings, objections, decisions, and next obligations inspectable through existing session and artifact surfaces.
- Provide the smallest useful intervention capability if the current runtime cannot accept direction: a bounded, explicit user instruction for the **next** research step, with clear timing, persisted provenance, and no silent mutation of previous results. If implementing this safely would require substantial UX, document the observed limitation and defer the control rather than inventing speculative UI.
- Enable research to continue from prior durable findings when a new session begins, without claiming that stopped or interrupted provider calls have been resumed. Preserve prior evidence and avoid replaying incomplete calls automatically.
- Session navigation arrows, elaborate agent drill-down, strategy scheduling UI, and other speculative UX are **not required**. Add no interface solely because it appeared in the former roadmap.

### 4. End-to-end reliability and demonstration (former A21)

- Test complete local flows: create/open project; author/fork/disable strategies; generate a candidate; start and inspect a research session; receive and persist evidence; assess results; stop or end; reload; continue in a new session; export and inspect the report.
- Exercise failure and recovery: provider rejection, timeout, malformed or partial stream, budget exhaustion, interruption, cancellation, duplicate start, stale state, and reload. Preserve saved artifacts, show a clear error/toast, and keep the UI in an appropriate recoverable state.
- Confirm that no failure silently turns into a negative research conclusion or a falsely successful one. Distinguish operational state, research outcome, and contribution assessment.
- Run deterministic fixtures and relevant real-browser checks with an isolated/mock provider. Include at least one substantive mathematical example (Maximum Regions Formed by Lines) and one counterexample where the agents cannot justify a completed solution.
- After deterministic validation, conduct a **separately reported** real-provider research-quality evaluation if the user authorizes the usage and credentials are available. Do not describe mocked or prompt-only results as real-agent quality evidence.
- Keep exports, history, and provenance faithful to saved data. Record actual commands run, pass/fail results, and remaining limitations in `docs/STATUS.md`.

## Implementation order and coordination

1. **Baseline:** inspect the merged research-cycle code and A17.8 findings. Establish falsifiable quality criteria and answer-leakage controls before changing behavior. Record actual failure cases, not guesses.
2. **Improve:** implement bounded, domain-general research-cycle and continuity corrections; retain the current UI and A17 outcome/assessment contracts. Add adversarial fixtures and avoid sample-specific keyword heuristics.
3. **Integrate:** re-read main before opening the PR, preserve A20/A23 behavior, and run `./sigma test`, focused browser checks, and an end-to-end local scenario. Fix regressions before enhancements.
4. **Evaluate:** complete deterministic quality checks and prepare the live evaluation protocol. Execute real-provider trials **only after explicit user authorization**, with a bounded call/time budget. Report research acceptance separately from engineering acceptance.

Maintain coherent, testable checkpoints while delivering the integrated research product; checkpoints are risk controls, not a reason to split A18 into small feature stories or drop core scope. Avoid schema changes unless necessary for durable evidence or continuation, and preserve legacy-session compatibility.

## Difficulty-tier product expectations

**Easy and Medium problems are solution targets, not merely progress targets.** The product ambition is that SIGMA solves **every legitimately classified Easy or Medium problem** in its supported research domains, subject to a well-defined, solvable task and the resources made available. This is an ambitious product requirement, **not a claim of achieved reliability or a guarantee that any present model can solve all such tasks**. Treat failures as defects or capability gaps to diagnose, not as acceptable success under a weaker progress rubric.

- **Easy:** expect a complete correct solution, independently checked against a hidden reference answer or other objective oracle where possible. No partial-credit substitution for completion.
- **Medium:** expect a complete correct solution, potentially after sustained multi-strategy research, critique, forking, and additional bounded sessions. Do not call defensible partial progress a solved Medium problem.
- **Hard:** expect meaningful, defensible progress, honest unresolved obligations, and a well-organized continuing investigation; a complete solution is a bonus, not a universal requirement.
- **Evaluation integrity:** difficulty labels are fixed before each test, with externally held answers/rubrics and explicit task assumptions. Do not relabel failures, leak solutions into strategy prompts, cherry-pick runs, or silently extend budgets. Use diverse samples and report per-tier solve rate, verification method, failures, and resource consumption. Report the gap to the universal Easy/Medium aspiration honestly; do not claim that a finite benchmark proves 'every problem.'
- **Acceptance reporting:** the engineering gate may pass while the Easy/Medium universal solution target remains unmet. Report this distinction explicitly. For A18's live research evaluation, a defensible partial result on an Easy/Medium sample counts as *research progress*, **not** as meeting its tier's solve requirement. Additional live calls require user authorization.

## Complete strategy lifecycle and concurrent research (required A18 scope)

A18 encompasses **all remaining research-quality work**, including strategy generation, evolution, multi-strategy agent execution, human supervision, and evaluation. Do not defer these core behaviors to another research-quality milestone. Reuse existing capabilities when sound; implement missing behavior when demonstrated by the end-to-end workflow.

- **Generate and author strategies:** exercise the actual product's AI candidate-generation and manual authoring workflows. Create genuinely distinct candidate approaches, not paraphrases of one answer; validate persistence, provenance, enable/disable state, and error handling. Generation must not quietly supply an evaluator's reference answer.
- **Fork and improve:** after an investigation, fork at least one strategy using specific saved findings, objections, or failed tests. Preserve parent identity and rationale. Compare the revised strategy against its original in a later bounded session, and ensure assessments distinguish their evidence and outcomes. Do not silently rewrite historical strategy text or results.
- **Concurrent multi-strategy research:** demonstrate multiple enabled strategies being investigated concurrently, with distinct agent work and provenance, not merely multiple strategies listed in a prompt or a single Investigator/Skeptic pair sequentially rotating through them. Keep execution bounded by existing concurrency, model, time, token and call limits; isolate failures and avoid duplicate or orphaned calls. Blue may choose the smallest suitable orchestration architecture, but actual concurrent execution is an acceptance requirement.
- **Live supervision:** within the existing Research Session pane, show which strategies/agents are active concurrently, their meaningful current states, completed artifacts, objections, and overall progress. Preserve usable stop/cancel and error handling; no new dashboard or speculative agent cockpit. Do not claim live visibility from a post-run summary alone.
- **Stop, recover, continue:** start research, stop during concurrent activity, verify completed evidence remains durable and incomplete calls are not represented as results, reload, and start a new session that explicitly incorporates prior findings. Exercise duplicate-start, one-agent failure, provider rejection, timeout, budget exhaustion, and user cancellation.
- **End-to-end acceptance scenario:** create/open a fresh project; generate multiple distinct strategies; enable/disable and fork strategies; start a bounded concurrent research session; observe live per-agent/per-strategy state; stop while active; inspect and compare durable evidence; fork an improved strategy based on outcomes; run a follow-up session comparing original and fork; assess contributions and export a faithful report. Verify through real browser plus deterministic/mock provider, and separately through bounded live-provider evaluation only with explicit user authorization.

## Research-quality evaluation and acceptance gates

**The goal is a product that does real research work, not just a working research UI.** Engineering acceptance and research acceptance are distinct; passing one never implies the other.

- **Engineering gate:** the complete strategy lifecycle, genuine concurrent multi-strategy execution, live visibility, stop/recovery, persistence, provenance, honest outcome labels, and reports pass deterministic tests and relevant real-browser checks. A failure must show a toast or equivalent clear UI error and return to a recoverable state, never silently promote failure to a research conclusion.
- **Research gate:** in an authorized real-provider trial, SIGMA starts with no answer in the research input, independently produces a correct result, defensible partial result, or evidence-backed elimination of a candidate mechanism, and records the Investigator/Skeptic/coordinator exchanges that justify that outcome. Assess the substance against an external rubric; an agent's confidence or agreement is not verification.
- **Breadth:** evaluate at least two distinct research domains, with separate evidence and rubrics. A single successful mathematical fixture does not establish generality. Record negative results, repeats, and unsupported claims, even if the software ran correctly.
- **No answer leakage:** inspect project problem, seeded strategies, prompts, continuation context, prior artifacts, and evaluator materials. Keep reference answers/rubrics outside the agents' inputs. The shipped Maximum Regions sample currently includes the proof in a strategy; use a fresh answer-free project for independent discovery tests, not that seeded strategy.
- **Suggested samples:** (1) Maximum Regions (Easy) for regression and an independently prepared *answer-free* mathematical trial; (2) Incremental Dependency Scheduler (Computer Science, Medium) for algorithm, proof, complexity, and adversarial-case reasoning; (3) Unexpected Oscillation (Physics, Medium) for scientific method under missing data and non-fabrication; (4) Warp Drive Design (Physics, Hard) for disciplined speculative reasoning and explicit proof obligations, **not** claims of a breakthrough. Military Planning can exercise coordination separately. A sealed-answer math task should supplement Maximum Regions. These are evaluation targets, not permission for unbounded live runs.
- **Precommit before live testing:** write per-sample scoring rubrics and failure criteria, baseline expectations, allowed inputs, selected model/effort, call/time budget, and what constitutes independent progress. Save exact prompts, session IDs, artifacts, and evaluator judgments. Separate deterministic/mock evidence from real-provider observations. Do not run provider calls without explicit authorization.

## Blue progress reporting and escalation

Blue owns implementation and technical judgment. **Communicate at milestones and decision points, not after each tool call or minor edit.** Keep human-facing messages short, factual, and nonrepetitive.

- **Kickoff (once):** confirm branch, scope, initial risk, and the first concrete verification target. No lengthy architecture pitch.
- **Milestones:** report after (a) baseline/failure-mode audit, (b) substantive implementation with deterministic checks, (c) integrated browser/end-to-end verification, and (d) research evaluation if authorized. Each update should usually be **4–6 lines**: *completed; evidence or test result; blocker/risk; next step*. Link durable artifacts, commits, or test records rather than pasting logs. Skip an update if it contains no meaningful change.
- **Escalate promptly, before acting:** additional live-model usage or billing; destructive migrations; security/privacy implications; changes to established UI layout/navigation beyond the narrow scope; changes to outcome/verification semantics; substantial architectural redesign; or an unresolved blocker requiring a user decision. State the decision needed, recommendation, alternatives, and consequences concisely. Routine implementation choices and test failures belong to Blue; diagnose and fix them without asking the user to manage the work.
- **Failure honesty:** report meaningful failed experiments, false positives, negative findings, and scope cuts as clearly as successes. Do not label passing mocks as proof of research quality or quietly redefine the acceptance bar after seeing results.
- **Final handoff:** open a dedicated PR; summarize the behavior delivered, exact commands run and pass/fail outcomes, real-provider sessions only if authorized (including limits, IDs, artifacts and evaluator results), remaining defects/risks, UI changes, and an explicit **Engineering gate: pass/fail/not tested** and **Research gate: pass/fail/not tested**. Place detailed evidence and reproducible steps in `docs/STATUS.md` and tests, not chat. **Do not self-merge**; ChatGPT reviews and merges the PR.

## Acceptance criteria

- Research iterations yield inspectable claims, targeted critiques/tests, and honest dispositions tied to durable artifacts; no generic 'progress' without evidence.
- Distinct strategies can be coordinated, with a documented reason for continuing, switching, combining, or stopping. Single-strategy sessions remain sound.
- A new session can use prior durable research as context without rewriting history or automatically replaying interrupted calls.
- The existing UI supports meaningful inspection and any minimal intervention actually justified by testing; no duplicate cockpit or speculative control surface.
- Session outcomes and strategy assessments remain compatible with A17.6, including historical eligibility and attribution.
- Failure paths preserve data, report errors, and remain recoverable; exports and reloads agree with persisted evidence.
- Deterministic suite, relevant real-browser checks, and end-to-end workflow pass. Live-provider quality is reported separately, never implied by mocked tests.
- `docs/STATUS.md` records changes, verification, known gaps, and any intentionally deferred intervention UX.

## Out of scope

Cloud hosting, authentication, multi-user access, public demo and security migration (A22); speculative interface redesign; new agent roles for their own sake; unbounded autonomous research; model training; formal-proof claims without independent proof checking; and unrelated product polish.

**Definition of done:** A reliable, observable, concurrent and evolving multi-strategy research product **and separately demonstrated substantive research progress** under the research gate above. If live-provider authorization is unavailable, deliver and report engineering completion with research acceptance explicitly **not tested**, not silently passed. Do not prolong A18 for speculative UX or former roadmap features.
