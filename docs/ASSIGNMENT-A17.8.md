# A17.8 — Agentic solution quality and final A17 verification

Status: **ready for implementation/verification after A17.7**. This assignment consolidates the two deferred quality items; it is not a new research-framework redesign.

Read `docs/HUMAN-AI-INTERACTION.md`, `docs/ASSIGNMENT-A17.6.md`, `docs/ASSIGNMENT-A17.7.md`, and `docs/STATUS.md`. The A17.6 implementation and its 2026-10-22 deterministic/browser/live results are already recorded. **Do not erase or discount those results, and do not claim this final verification has run until it actually has.**

## Quality item 1: Actual agentic solution quality on a solvable problem

Use **Maximum Regions Formed by Lines** as the primary real-provider sample, not only a canned fixture. Its mathematical answer is `R(n) = 1 + n(n+1)/2`, but the quality test concerns **whether SIGMA's agents independently produce, critique, and recognize a complete supported solution**.

- Start with a fresh working copy and the normal research flow. Record the exact project question, strategies, selected provider/model/effort, configured limits, session IDs, costs/calls where available, and actual artifacts.
- Assess substance, not merely a positive status: the argument must show why line `k` creates at most `k` new regions and why a general-position construction attains the bound at each step.
- Confirm Investigator/Skeptic objections and coordinator conclusions address the argument; unsupported assertions, circular proofs, or incomplete constructions must not be promoted to independently verified proof.
- A complete supported solution may end with **no next path** and still be recognized as **objective achieved**. An unverified solution candidate must remain explicitly marked unverified.
- Strategy Assessments must credit the strategy or strategies actually supported by saved artifacts, not all active strategies automatically.
- If the run stalls, misclassifies success, fails to identify a material flaw, or produces empty/repetitive research, capture the failure with precise artifact references, implement a bounded correction, and rerun an appropriate regression. Do not tune the fixture to hide a real-provider weakness.
- Record limitations honestly. A real model run is an empirical quality check, **not** a guarantee of solving other problems or independent mathematical proof verification. Avoid unbounded paid calls; obtain approval before any extra billable provider experiments outside the existing connected-plan workflow.

## Quality item 2: Final integrated A17.6 verification

After A17.7 is merged, verify the **integrated A17.6 + A17.7** application end to end:

1. Maximum Regions deterministic completed-proof case, no-next-path success, and genuine incomplete/unverified/counterexample cases.
2. Research **objective outcome**, session **lifecycle/execution status**, and **strategy contribution** remain independent. Positive research must not erase stopped/failed/budget-exhausted execution.
3. **Strategy Assessments** table: Contributed to solution, Productive, Unproductive, Not used, Disabled; correct evidence/rationale, all strategies in project order, and historical eligibility snapshots unchanged by later edits/toggles.
4. Persistence and fidelity: save/reload/restart, historical sessions, JSON audit, text/HTML/LaTeX Research Report, and consistent caveats/evidence references. Legacy missing attribution must stay unknown.
5. Stop/resume, provider interruption/timeouts, budget limits, partial/failed assessment generation, toast visibility, and safe recovery without loss of committed artifacts.
6. Browser behavior after A17.7: session lifecycle and outcome summary, action placement, dialogs, export, tooltips and scroll containment. Reuse A17.7's visual checks rather than duplicating implementation work.

## Evidence and exit criteria

- Run `./sigma test`, focused API/unit checks and real Chrome Playwright checks using isolated mock providers; inspect screenshots and recorded data. Add tests for any uncovered regression.
- Run and assess the **actual connected-provider Maximum Regions quality trial** if authorized/available; document model, limits, exact behavior and whether it genuinely met the objective. If it cannot run, explicitly leave real-agent quality **unverified** rather than marking the whole quality item passed.
- Record exact commands, results, costs if available, artifact/session identifiers, screenshots, failures and remaining caveats in `docs/STATUS.md`.
- Human reviews the results and accepts or requests fixes. **A17 is not declared complete, and A18 (Agentic Quality), A19 (Python Sandbox), A22 (Cloud Deployment) do not launch in parallel, until this final A17.8 gate is addressed.**

Out of scope: expanding A18 agentic-research architecture, A19 sandbox execution, A22 cloud work, or treating a solved sample as evidence that RH is solved.
