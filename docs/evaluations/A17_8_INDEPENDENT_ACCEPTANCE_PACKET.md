# A17.8 independent-discovery acceptance packet (2026-10-23)

**Status: prepared, NOT RUN.** This document contains only participant-facing
questions, leakage controls and evaluation logistics. It deliberately contains
**no reference answer, recurrence, extremal construction, or proof outline**.
Do not paste reference material into SIGMA's project, strategy, session prompts,
samples, source comments, or a provider-accessible tool result.

## Participant-facing primary trial: Maximum Regions (answer-free)

**Project title:** Maximum regions formed by straight lines

**Project description:** For each nonnegative integer n, determine the greatest
possible number of regions into which n distinct straight lines divide the
Euclidean plane. Establish an exact answer for all n with a rigorous upper bound
and a construction that attains it. A finite table of examples is insufficient.
State any geometric assumptions required for the argument.

**One initial strategy (bounded, answer-free):** Examine how adding one line
changes the connected regions of an arrangement of earlier lines. Identify what
would need to be proved for an upper bound and what separate evidence would
demonstrate attainability. Do not assume that a particular arrangement or
formula is optimal.

**Research scope:** Ordinary Euclidean geometry and elementary finite
combinatorics. No web retrieval necessary. Python may test small cases if
actually available, but computation cannot certify a universal maximum.
Do not supply the reference formula or sample strategy in a role prompt.

### Fresh-project protocol

1. Use a **new blank project**. Enter only the text above. Do not clone
   `samples/maximum-regions-by-lines`: its original human-written strategy
   already contains solution material.
2. Use the normal SIGMA UI and research-session workflow. Save the project
   export, model/effort and actual provider mode before the run.
3. Proposed bounded run: one strategy, at most **6 model calls / 3 cycles /
   10 minutes**, output limit 4,000 tokens per call. No automatic retry or
   API-key fallback. If the connected plan is unavailable, stop; any billable
   run requires explicit authorization and an agreed budget.
4. Preserve the immutable session JSON export, each Investigator and Skeptic
   output, exact objections, proof obligations, revisions, coordinator
   decisions, usage fields as actually reported, and generated reports.
5. Evaluate after completion against the **separately held evaluator reference**.
   Preserve negative results. Do not manually feed the answer after a failed
   run and then score it as independent discovery.

## Leakage and independence gate (before any model call)

- Confirm that the new project's persisted description and strategies match
  exactly the answer-free text in this document.
- Inspect every generated role context for formulae or complete arguments
  silently inherited from default templates, other projects, example sessions,
  or previous history. The existing Maximum Regions sample and its source
  history are disallowed inputs.
- A model may have learned the problem during pretraining. This experiment
  assesses **independent reasoning from its session input**, not novelty to
  humanity or proof of absence from model training data.
- Keep reference solutions in an evaluator-only location outside the SIGMA
  repo and model-accessible folders. Record its SHA-256 and reviewer ownership
  in the private evidence packet; it must predate inspecting model outputs.
- If any answer-bearing material entered the role context, mark the
  independence criterion UNMET regardless of solution quality.

## Scoring (0 = failed, 1 = partial, 2 = specifically supported)

1. **Correctness:** exact general result and valid proof for every n, including
   both upper-bound reasoning and a matching construction. Require an
   evaluator outside the model-role consensus to inspect each nontrivial step.
2. **Independent input:** no answer or proof outline in project, strategy,
   injected interventions, or tool data. Record prompt leak audit.
3. **Skeptic:** identifies actual unsupported inferences and cites them; accepts
   supported proof without inventing objections or stopping prematurely.
4. **Coordinator:** keeps open obligations open and terminates correctly on
   an accepted, fully supported argument even with no next question.
5. **Calibration:** labels any candidate as unverified absent a human/formal
   check, and distinguishes run status from research outcome.
6. **Attribution and continuity:** evidence-linked strategy assessment and
   faithful multi-cycle objections, revisions, and supporting artifact IDs.
7. **Operational fidelity:** persistence, report exports, no hidden retries or
   costs, and visible provider failures.

**Pass gate:** 2 on correctness and independence, 2 on calibration, and no
material unresolved objection in the alleged proof. All seven dimensions need
saved citations; incomplete evidence is UNVERIFIED, not MET. A failed model
trial is not an automatic software defect. Score individual steps, not
keyword matches or the final outcome badge alone.

## Generalization control: a different proof mechanism

Use an answer-free second *deterministic* adversarial scenario based on
counting fixed-length binary strings with no adjacent ones. The desired
reasoning is a last-symbol partition with an explicit non-overlap/exhaustion
proof, boundary cases and an independently justified recurrence. This
contrasts combinatorial partition with planar region construction.
The existing `test_generic_objective_review_on_binary_strings` exercises
that mechanism with deterministic output. Do not interpret it as a second
live model trial.

## Evidence inventory and decision

A17.8's prior live session `124d2b7f-9f9b-4060-86dd-fa9161f42e62`
achieved a coherent, **unverified** conclusion and a substantive Skeptic
revision; however, the original Maximum Regions strategy disclosed much
of the solution. See `docs/STATUS.md`, heading "A17.8 Evaluation
(2026-10-22)", for exact earlier artifact IDs, defects and engineering tests.

- Existing rubric criteria 2–5, 7–8: MET under the specific evidence/limits
  recorded in STATUS; criterion 6: deterministic only.
- **Independent solution quality / criterion 1: UNMET** on that live run,
  because of answer-bearing strategy text.
- This answer-free trial: **NOT RUN**. No new provider session, participant
  output, screenshots or result can be cited from this packet.
- **Acceptance recommendation: HOLD** until an authorized fresh run and
  independent human evaluation establish the remaining quality gate. Do not
  downgrade previously established engineering work and do not claim A17.8
  complete merely because the acceptance protocol is now prepared.

## Operational blockers

The coordinator currently has repository file/PR access but no access to the
user's local running SIGMA UI, its connected ChatGPT-plan identity or live
research session data. No provider experiment was dispatched from this work.
The experiment also requires an external evaluation of the mathematical proof
against a private, precommitted reference. When execution is available, capture
genuine IDs and recorded cost/usage; never substitute fabricated sample data.
