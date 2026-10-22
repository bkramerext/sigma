# A18 — Research quality and integration

Status: **ready for implementation**. Consolidates the remaining intended scope of A18–A21; A19, A20, and A21 are retired as separate planned assignments. A22 remains a separate cloud-migration assignment.

Read `docs/HUMAN-AI-INTERACTION.md`, `docs/ASSIGNMENT-A17.6.md`, and `docs/STATUS.md` before implementation. Inspect the current code and tests before proposing changes. Preserve local operation and existing user workflows.

## Objective

Make SIGMA a dependable local research system that produces useful, evidence-backed progress through bounded agentic investigation, preserves that progress, and can be meaningfully supervised by a human. Improve the actual research mechanism and end-to-end reliability, not the number of features or panes.

A18 may proceed **in parallel with A17.6**, but avoid modifying A17.6's outcome-recognition, verification-label, and Strategy Assessments contracts until that implementation is integrated. Resolve conflicts against the latest code, not assumptions about the earlier roadmap.

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

1. **Begin now, without waiting for A17.6:** inspect research-cycle code, document specific quality gaps, add isolated deterministic tests, and implement improvements that do not overlap A17.6's files/contracts.
2. **Integrate after A17.6 lands:** rebase/re-read current interfaces; exercise outcome/assessment semantics, continuity, and cross-strategy coordination against the merged implementation. Do not overwrite Codex's concurrent changes.
3. **Close with integrated verification:** run `./sigma test`, focused browser checks, and the end-to-end local scenario. Fix regressions before adding enhancements.

Prefer a small number of coherent, independently testable increments over a broad rewrite. Avoid schema changes unless necessary for durable evidence or continuation, and preserve legacy-session compatibility.

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

**Definition of done:** A reliable, evidence-based **local** research workflow demonstrated end to end. Do not keep A18 open merely to implement every former A19–A21 idea.
