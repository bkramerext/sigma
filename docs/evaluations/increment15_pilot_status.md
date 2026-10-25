# Increment 15: bounded unscripted pilot execution

**State:** Started immediately after Increment 14 merged. **No live provider inference or paid calls authorized.** The approved work at this point is offline execution preparation, not the paid research experiment.

## Pilot goal

Determine whether SIGMA's unchanged Investigator/Skeptic workflow yields higher blinded research-quality scores than a strong single-role self-review baseline, using exactly the same model, source packets, tools and total resource ceilings. Preserve all outcomes, including losses and failed/abstained runs.

## Run sequence

1. Pin merged Increment 14 commit and verify tasks, grader references and arm contract hashes. Independent pre-output challenge is required for benchmark validity.
2. Decide provider, exact model, available tools, aggregate call/input/output/reasoning-token/time/cost ceilings and verified pricing. **Explicit user approval is necessary before any real inference.**
3. Freeze a signed, read-only manifest that records model/settings, budgets, randomization and exclusions. Keep evaluator-only references unavailable to the process or tool sandbox used by either model.
4. Demonstrate negative controls offline: a model-side filesystem listing cannot read reference keys, agent packet cannot include grading fields, mixed arm outputs are rejected, and audit excludes malformed/over-budget/incomplete pairs. Do not confuse the current allowlist with proven filesystem isolation.
5. Execute one blinded matched pair at a time with no unapproved retries. Save complete requests/responses and tool transcripts, measured tokens, actual spend, elapsed time, failures and hashes. Stop on cost or integrity breach.
6. Score with two independent blinded evaluations; preserve original scores and disagreements. Adjudicate without exposing arm identity.
7. Publish raw paired results, domain/variant breakdowns, score difference and uncertainty, cost/latency, failures and caveats. Decide whether 16 should investigate an advantage or simplify after a tie/loss.

## Present blockers

- Model/provider/account and spending cap have not been explicitly selected or approved.
- The runner needs demonstrable key isolation and matching resource accounting. Offline validators alone do not provide these controls.
- The pilot is six short synthetic tasks with 12 paired comparisons. It is insufficient for an overall multi-agent superiority claim; Increment 17's extended unscripted multi-session test is essential.

## Rules

No changes to production research behavior to favor SIGMA. No inference without approval. No silent relabeling of failures, deletion of contaminated outcomes, or post hoc task modifications. When approval is absent, continue the zero-cost offline preparations, not model calls.
