# SIGMA brainstorm and roadmap

This is a source-controlled record of design ideas, not an implementation specification or a commitment to build every item. Preserve ideas here without allowing them to expand the immediate implementation scope. Promote an idea into a focused specification when a working slice requires it.

**Dating convention:** Date each idea individually (YYYY-MM-DD), since categories are long-lived. Dates on existing ideas mark when they were recorded in this brainstorm, not necessarily when they were first conceived. Earlier proposal dates are not reliably known. Append new dated bullets under the relevant category rather than redating or rewriting old entries; use an explicit later dated bullet for revisions or reversals.

## Core research model

- **2026-10-20** — A **strategy** is an evolving search for a solution, beginning with a seed idea. It is not itself a solution or a single research output. It accumulates investigations, evidence, experiments, failures, and revisions.
- **2026-10-20** — A project has a **strategy pool**. **Generation 0** contains independent roots (including new roots introduced later). A fork is a new strategy with a parent, one generation deeper. Children retain distinct histories and evaluations; parents remain intact.
- **2026-10-20** — Begin with one parent per fork (a forest). Cross-strategy synthesis or multiple parents can be considered later if needed.
- **2026-10-20** — Generation denotes ancestry, not merit or scheduling priority.
- **2026-10-20** — Govern growth: fork admission should require a material difference and reason to investigate; check overlap/duplicates; bound active branches, children per parent, depth, and total cost. Humans can pause or prioritize branches and subtrees.

## Rubrics, adversarial evaluation, and scheduling

- **2026-10-20** — A **rubric** is a configurable, human-editable set of natural-language standards used by evaluator agents to assess whether a strategy has a **promising path toward the project objective**. It is not simply a direct score of the latest output, nor a calibrated probability of solving a problem like RH.
- **2026-10-20** — Example judgment criterion: “This is a known result that is fundamental and well understood in academic papers.” Assess significance and provenance separately from novelty or future promise.
- **2026-10-20** — Example investigative criterion: “Survives adversarial tests for falsity or triviality.” Such a criterion may direct the evaluator to conduct bounded experiments, seek counterexamples, test degeneracies, compare with generic functions, search literature, and identify unsupported steps. Report the tests performed and remaining uncertainty; surviving finite tests is not proof.
- **2026-10-20** — Separate **research/generation**, **independent evaluation**, and **deterministic scheduling**. Agents produce proposals and evidence; the scheduler decides allocations under constraints. Keep evidence classification distinct from strategic assessment.
- **2026-10-20** — Evaluation may itself require bounded agent work. Preserve rubric versions, evidence, explanations, failed tests, and unknown/insufficient-evidence assessments.
- **2026-10-20** — A scheduler can weigh promise, uncertainty, information value, costs, dependencies, and exploration versus exploitation, but should never treat agent confidence as authority or bypass hard limits. Record explainable allocation decisions.

## Human control and interfaces

- **2026-10-20** — Humans can edit rubrics and constraints; promote/demote strategy priority; pause/resume individual strategies, branches, or the project; and request investigation of specific strategies subject to hard constraints.
- **2026-10-20** — Preserve human priority directives separately from evaluator assessments rather than altering scores. Audit who changed what, why, and under which rubric/constraint version.
- **2026-10-20** — Web UI, CLI, and scenario runner are **equal clients of one typed application command/query interface**. Do not make tests depend on the CLI or make the web UI invoke CLI subprocesses.
- **2026-10-20** — The UI should make strategy genealogy, evidence, scheduling decisions, human overrides, and history understandable without hiding uncertainty.

## Projects and persistence

- **2026-10-20** — A project is a directory with a `.sigma` extension, e.g. `rh.sigma/`, convenient to ignore with `*.sigma/` in Git.
- **2026-10-20** — Inside: `config.json` (declarative objective, rubric, agent and scheduling configuration; no secrets), `state.db` (SQLite state and events), `artifacts/` (generated outputs), and optionally `scenarios/` (project-specific executable scenarios).
- **2026-10-20** — Keep credentials outside source-controlled config, referenced through environment or local secret storage.

## Verification and implementation approach

- **2026-10-20** — Prefer source-controlled, human-readable **executable scenarios** over a large brittle unit-test suite. Scenarios invoke the common application interface and assert meaningful behavior and invariants.
- **2026-10-20** — Use deterministic scripted agents, clocks, and budgets in scenarios. Live model integration tests are opt-in. Preserve failure evidence and clear diagnostics.
- **2026-10-20** — Test adversarial behaviors: inflated confidence, contradictory claims, false success, trivial mathematical identities, invalid dependencies, exhausted budgets, and prohibited forks.
- **2026-10-20** — Maintain lightweight specs with purpose, contracts, invariants, failures, and acceptance scenarios. Codex implements bounded slices; architectural brainstorming alone does not trigger implementation.
- **2026-10-20** — Start with a minimal scenario runner, not a general-purpose test language. Defer elaborate scheduling policies, rubric-directed test orchestration, and sophisticated genealogy UI until real working slices need them.

## Agent runtime and public presentation

- **2026-10-20** — Agent/provider configuration should include roles, model selection, timeouts, retries, concurrency, and cost/token budgets. A ChatGPT subscription does not automatically pay for OpenAI API use; settle runtime authentication/billing before implementing live agent execution.
- **2026-10-20** — Public repository structure should demonstrate separation of intent, agent judgment, governance, execution, and verification through actual code and scenarios. Keep README and docs technically grounded, without recruitment-oriented claims or private background.
- **2026-10-20** — SIGMA is a research orchestration system, not a claim to be a general software factory.

## Configuration, spending, and progress notifications

These are candidate features for later agent-execution increments, **not additions to the active UI assignment**.

- **2026-10-20** — **Project-level configuration** establishes defaults and guardrails for the research environment: model/provider selection, overall spending ceiling, agent execution limits (steps, tool calls, recursion/depth, concurrent runs), timeouts, retry policies, report-back intervals, evaluation rubric, and notification preferences. Draw on established industry practices for bounded, observable agent workflows; evaluate specific defaults when implementing.
- **2026-10-20** — **Strategy-level configuration** should remain minimal initially: scheduling state, priority, and a per-strategy spending ceiling. Strategies inherit project defaults unless a justified override is necessary. Do not build a complex settings form before real use reveals what is needed.
- **2026-10-20** — **Cost visibility:** Show actual accrued spending and the strategy's limit as restrained secondary text on an in-progress strategy, e.g. `Spent $2.34 / $10.00 limit`. Distinguish actual measured costs from estimates, and enforce limits through application services rather than merely displaying them.
- **2026-10-20** — **Progress reports:** A configurable report-back timeout/interval should ensure a long-running investigation provides periodic progress even without a breakthrough. Clarify how elapsed-time limits differ from reporting cadence and execution deadlines.
- **2026-10-20** — **Notifications:** Allow opt-in alerts for significant research events, especially a **candidate solution**. A message such as `I think I found a solution to the RH project!` should clearly indicate an unverified claim. Track separate states for candidate discovery, independent verification, and any later externally validated result; do not equate agent confidence or finite tests with mathematical proof.
- **2026-10-20** — Keep notification delivery channels, provider integrations, and detailed strategy overrides undecided until a concrete implementation slice calls for them.

## Documentation reconciliation

SPEC-001 uses a `.sigma/` directory with a versioned JSON document and shared typed services. SQLite remains a potential later storage choice; executable scenarios are the current acceptance checks. See DECISIONS.md for the implemented format and tradeoffs.
