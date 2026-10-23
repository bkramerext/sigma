# A18 — Research quality and integration

Status: **ready for Blue implementation**. A18 is the integrated local research-quality and reliability milestone. The former A19–A21 roadmap is not a dependency; A20 AI-authored papers is a separate, already authorized feature, and A23 project difficulty is implemented. A22 cloud migration remains separate.

Read `docs/HUMAN-AI-INTERACTION.md`, `docs/ASSIGNMENT-A17.6.md`, and `docs/STATUS.md` before implementation. Inspect the current code and tests before proposing changes. Preserve local operation and existing user workflows.

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

Prefer a small number of coherent, independently testable increments over a broad rewrite. Avoid schema changes unless necessary for durable evidence or continuation, and preserve legacy-session compatibility.

## Research-quality evaluation and acceptance gates

**The goal is a product that does real research work, not just a working research UI.** Engineering acceptance and research acceptance are distinct; passing one never implies the other.

- **Engineering gate:** complete local workflows, persistence, cancellation/recovery, provenance, honest outcome labels, and reports pass deterministic tests and relevant real-browser checks. A failure must show a toast or equivalent clear UI error and return to a recoverable state, never silently promote failure to a research conclusion.
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

**Definition of done:** A reliable local research workflow **and separately demonstrated substantive research progress** under the research gate above. If live-provider authorization is unavailable, deliver and report engineering completion with research acceptance explicitly **not tested**, not silently passed. Do not prolong A18 for speculative UX or former roadmap features.
