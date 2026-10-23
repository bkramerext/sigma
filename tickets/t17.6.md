# A17.6 — Research outcome recognition and strategy assessments

Status: **ready for implementation**. Scope is frozen for this increment.

Read `docs/HUMAN-AI-INTERACTION.md`, `docs/ASSIGNMENT-A17.5.md`, and current `docs/STATUS.md` before implementation. Preserve existing session controls, historical records, and A17.5 UX. Implement, test, and record results in `docs/STATUS.md`.

## Objective

SIGMA must distinguish (1) whether the research objective was achieved, (2) whether a session executed successfully, and (3) which strategies materially contributed. A completed solution is not a negative outcome merely because no further research path remains.

## Required behavior

1. **Recognize a completed solution.** The coordinator must explicitly assess whether the saved research artifacts satisfy the project's stated objective. A justified completed solution yields a positive research outcome even when no further investigation is recommended. Do not infer failure from an empty next-step list. Preserve execution errors, stopped states, and budget exhaustion as separate facts; a positive research finding must not erase an operational failure.
2. **Evidence-based verification.** Identify the exact claim, argument or construction, assumptions, proof obligations and supporting artifact references. An agent's assertion that a proof is correct is not independent verification. Distinguish a convincing but unverified candidate from a verified solution; do not claim formal verification or independent checking that did not occur. Surface unresolved objections and uncertainty.
3. **Strategy Assessments table.** For each strategy in project display order, assess its contribution **to the project's objective**, not just whether it ran. Use these human-readable assessments: **Contributed to solution**, **Productive**, **Unproductive**, **Not used**, **Disabled**. Multiple strategies may contribute to the same solution. Attribute credit only to specific strategy-linked evidence, with concise rationale and references to relevant session artifacts. Merely being enabled, selected, or active is not evidence of contribution. Keep disabled-versus-unused semantics and historical eligibility snapshots from A17.5; later strategy edits or toggles must not rewrite past assessments.
4. **Consistent durable results.** Persist the evidence, rationale, outcome, and strategy assessments so reloads, exports and session history report the same result. Preserve compatibility with legacy sessions, and label missing historical evidence as unknown rather than fabricating attribution.
5. **Failure and error handling.** If assessment generation fails, report a recoverable error through the normal toast/UI path, preserve already saved research, and do not silently assign a negative outcome or present partial assessment text as a completed result.

## Deterministic regression: Maximum Regions Formed by Lines

Given a project seeking the maximum number of regions formed by `n` lines and a strategy of incremental region counting with an explicit general-position maximizing construction, a completed argument should establish:

- Adding line `k` creates at most `k` regions.
- A general-position arrangement attains the bound for every step.
- Therefore `R(n) = 1 + n(n+1)/2`.

When the agents produce a complete, supported proof with no unresolved material objection, the research outcome must be **successful / objective achieved**, not **Negative — no useful next path identified**. The incremental-counting strategy should be **Contributed to solution** with evidence references. If the proof is incomplete or unverified, preserve the appropriate provisional assessment rather than asserting verified success.

The broader live-agent solution-quality evaluation and final integrated A17.6 acceptance pass are assigned to **A17.8**. Preserve the deterministic regression here as an implementation contract; do not rerun live quality trials as part of A17.7.

## Tests and acceptance

- Deterministic fixture for the Maximum Regions success case, including strategy attribution and no-next-path termination.
- Countercases: incomplete proof, unsupported claim, material objection, plausible but unverified proof, operational failure after useful research, budget exhaustion, multiple contributing strategies, productive-but-noncontributing strategy, unproductive strategy, eligible-unused strategy, disabled strategy, and legacy session with absent attribution.
- Verify backend state, reload, historical immutability, export/report semantics, and visible table labels/rationales; ensure the agent/coordinator contract uses the same meanings.
- Run `./sigma test`, relevant real-browser checks with mock provider, and record what was actually verified. No paid live-model run is required for acceptance; explicitly state if live-model quality remains untested.

## Out of scope

No new agent roles, open-ended research framework redesign, new strategy-generation UX, or unrelated interface changes. Do not expand scope without a separate assignment.
