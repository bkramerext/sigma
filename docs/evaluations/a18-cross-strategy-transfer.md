# A18 cross-strategy transfer evaluation

**Purpose:** measure whether a saved finding in one research strategy changes
the next action in another strategy, and whether that change is useful. This is
one bounded exploratory trial, not a general capability claim.

## Fixed task and budget

The project asks SIGMA to count subsets of `1,...,n` with no consecutive
elements whose sum is divisible by three, derive a rigorous recurrence for the
count, evaluate `a_12`, and prove the ratio to `F_(n+2)` tends to `1/3`. The
two strategies use different representations: a finite boundary-state count
and a weighted generating-function method. They state proof obligations but
do not include the target recurrence or answer.

Use the connected ChatGPT-plan provider only, `gpt-6.1-sol` at Medium
reasoning, a 10-call maximum, three research rounds, and the existing 30-minute
session cap. No retry of a timed-out live session. Stop immediately on a 429,
plan-unavailable response, or other explicit usage limit. SIGMA has no exposed
plan-allowance meter, so record dispatched calls and any usage metadata the
provider actually returns; do not estimate token or allowance consumption.

## Precommitted scoring

1. **Research correctness:** compare the claimed recurrence, sufficient initial
   values, `a_12`, and asymptotic argument with the independent derivation in
   [example-math-verification.md](../example-math-verification.md). Check that
   finite enumeration is not presented as the asymptotic proof.
2. **Skeptic quality:** identify whether a Skeptic names a specific mathematical
   gap, counterexample, or unsupported inference, and whether its requested
   next step would resolve that issue.
3. **Transfer trigger:** record whether the source Skeptic cites an exact
   target artifact and gives a material relationship. A vague relation or
   `unrelated` is a no-op, not a success.
4. **Causal execution:** if a valid relation is saved, verify the target's next
   dispatched Investigator call is prioritized when the budget cannot fund
   both routes, includes the source and target artifact IDs, and changes its
   research question to a discriminating comparison. Verify stop/recovery
   preserves that handoff and the resulting artifact records which evidence
   prompted it.
5. **Limits:** count all dispatched calls and elapsed time. A timeout is an
   operational failure, not mathematical evidence. Do not credit handoff
   wiring as proof that a live model used the handoff correctly.

The local finite-state implementation and proof notes are the reference oracle
for arithmetic and recurrence claims. They are evaluator material and are not
included in the project prompt. This task is a Medium reasoning exercise, not
an independent-discovery test: the strategies themselves specify broad
methodological routes. One run cannot establish that coordinator interventions
improve outcomes over fair rotation.
