# Issue 119: longitudinal cross-session research evaluation

**State:** Design proposal only. Not frozen, not executed as a model-quality study, and not authorized for paid inference.
**Base reviewed:** `537c198` (`main`, including merged T146 PR #150 and T147 PR #164).
**Provider calls / cost for this increment:** 0 / $0.

## What the existing evidence establishes

T146 is a real, bounded, single-session comparison: its Skeptic received the Investigator's saved work and completed computation. It was one cycle, not a multi-session persistence trial. T147 established that the T146 baseline's second stateless request omitted its original task; that baseline result cannot establish self-review under full persistent context.

The current implementation has useful engineering coverage, but no unscripted longitudinal result:

- `tests/epistemic_continuity.py` uses the production session/context/export path with scripted responses. Its parity case saves a finding in one session, cites it in a later session, and verifies the historical session is byte-identical. Its graph case carries a failed and then completed execution through follow-up and an approved strategy fork; it also checks the withhold-evidence control and rejects a false foreign-source citation.
- `tests/continuations.py` verifies explicit approval, mandatory negative evidence, exact source identity, frozen dispatch packets, overflow refusal, stale preview detection, and archive preservation.
- `tests/research_feedback.py` verifies exact negative-constraint and source-coverage handling, including refusal when evidence is missing, foreign, or misrepresented.

These are meaningful persistence, provenance, and access-control checks. They do not show that a model reads or uses the saved material well, avoids needless repetition, improves a conclusion, or beats a single researcher. The old increment-14/15 scripts test within-session collaboration only. The increment-21 audit explicitly marks #119 as separate. No product defect was reproduced in this review.

## Proposed study

Use a randomized **2 × 2 factorial, staged-evidence study**. The factors are (a) research organization: SIGMA Investigator/Skeptic versus a strong single-role self-reviewer, and (b) cross-session history: available versus withheld. This permits separate descriptive estimates for persistence within each organization, the organization contrast when both have history, and their interaction. It avoids attributing the single SIGMA-versus-baseline contrast to persistence alone.

### Units, tasks, and sequence

- Commission six previously unseen task families from an independent curator who is not the task author, implementer, provider operator, or grader. Use distinct problem families rather than six cosmetic variants of one puzzle. Each needs a sealed reference, accepted alternatives, explicit scope/uncertainty rules, and a reasoned staged-evidence schedule.
- Each task is a three-session investigation. Its first packet leaves two or more plausible hypotheses and supports two genuinely different strategy branches. Session 2 reveals new evidence that should update at least one branch, such as a failed discriminating test or a counterexample. Session 3 reveals independent corroboration or a boundary condition and asks for a calibrated synthesis. The reveal is identical by task and session across conditions; future evidence and keys are never sent early.
- Create two independent stochastic repeats per task in each condition: six task clusters × two repeats × four conditions = 48 trajectories, 12 task-clustered paired comparisons per contrast. The independent unit remains the six task families (`n=6`), not the 48 trajectories or 144 sessions. This is a small exploratory pilot; report every task-level effect and do not claim confirmatory power.
- Each trajectory uses three saved research sessions and exactly one two-call cycle per session. In SIGMA, the two persistent strategies are branch records: session 1 starts one branch, session 2 uses an explicitly approved fork/transfer to test the rival direction, and session 3 returns to branch A with an explicitly approved transfer of branch B evidence for synthesis. If the ordinary continuation path cannot provide that packet without manual injection, record a product limitation and stop the affected case rather than patching the harness around it. The task key must confirm that the supplied schedule actually needs branch comparison; do not reward branching by itself. The single-role researcher may maintain the same two named hypotheses and an equally complete notebook across its turns.

### Four conditions

| Condition | Roles | Prior-session history |
|---|---|---|
| A | Production SIGMA Investigator/Skeptic pair | Native saved project/session history, evidence, computation provenance, strategy branches and selected continuations |
| B | Strong persistent single-role self-review | Full prior transcript and artifacts in an equivalent persistent store/retrieval packet, with the same task, staged reveal, tools and budgets |
| C | Production SIGMA Investigator/Skeptic pair | Each session begins from the same task statement and newly revealed evidence, with prior model-produced findings/branch history withheld |
| D | Strong single-role self-review | Fresh conversation each session; same task statement and staged evidence as C, without earlier model-produced history |

A versus B is the primary persistent-research workflow contrast with a capable, history-enabled baseline. A versus C and B versus D estimate the value of prior model-produced history within each organization. The difference between those two persistence contrasts is the role-by-persistence interaction. These contrasts still combine role behavior with each system's implementation; they do not isolate a particular software component unless the memory projection, retrieval opportunities, and dispatch records pass the information-equivalence audit below.

The no-history conditions are diagnostic controls, not the primary baseline. They still receive the task's original facts and the current scheduled evidence tranche. They must not receive prior model conclusions, saved tests, artifacts, objections, or branch decisions.

### Matched budget and blinding

Pin one provider, exact model revision, API mode, reasoning/sampling settings, and project configuration before freezing. In every condition, allow three sessions × two calls per session (six call attempts per trajectory), matched input/output token ceilings, wall time, total spending ceiling, and identical deterministic local tool rights. Failed, clipped, interrupted, and uncertain-usage calls count against caps and remain in the record. No retries, fallback, web, or external retrieval. Exact numeric cost ceilings must be set from the selected model's current price and the owner's explicit authorization; this document does not authorize a call or choose a provider.

The single-role baseline must receive the complete task on each stateless API turn or use a verified response chain. Its full-history condition must receive all relevant saved statements, accepted/rejected hypotheses, evidence with provenance and status, computations including failures, open obligations, strategy decisions, and continuation questions under an agreed byte/token cap. Freeze the same deterministic retrieval and truncation rules for both persistent conditions. Compare the actual model-visible request packets, not storage indexes alone. Equal ceilings do not require equal consumption; report actual calls, input/output/reasoning tokens, elapsed time, tool use, costs, clipping, and failure rates.

An independent key custodian seals task keys and reveal schedules outside both model workspaces and scorer packets. Two graders independently score anonymous, normalized session-by-session artifacts; graders are independent of task authors, curator, implementer, and provider operator. Randomize artifact and condition order separately per grader. Record arm guesses and confidence; report blinding accuracy rather than dropping guessed results. Keep raw provider and orchestration traces in a restricted audit bundle. Do not include strategy names or product-specific field names in scorer artifacts; provide a common, provenance-preserving projection with identical field and character limits.

## Outcomes and scoring

Pre-register the hidden task-specific milestones and alternate acceptable paths before any model output is visible. Score each session and the final synthesis. Use two independent graders and preserve both original ratings and adjudications.

**Primary descriptive endpoint:** final task outcome and reasoning validity, with task-anchored 0–4 scores for (1) correct result or justified abstention, (2) valid reasoning/counterexample handling, and (3) calibration to what the staged evidence establishes. Freeze a binary task-key pass rule as a companion endpoint. Do not reward answer length, objection count, citation count, number of strategies, or agreement between same-model roles.

**Cumulative/continuity measures:**

- session-by-session count of independently key-validated obligations newly closed, still open, or correctly re-opened;
- prior finding use: relevant source recall, exact attribution, scope/status fidelity, and whether that finding changed the next strategy question or test;
- negative-evidence retention: whether failed, refuted, superseded, or inconclusive work is kept distinct and not repeated as a successful result;
- branching quality: whether a fork or cross-strategy transfer was justified by the saved evidence, whether contradictory branches were reconciled, and whether a branch was narrowed or retired appropriately;
- unsupported or overconfident conclusions, unsupported citations, evidence/provenance loss, and false claims that a prior test ran;
- repetition rate: repeated claims/tests with no new condition, rationale, or information gain, judged against the actual prior trajectory;
- operational continuity: request-level audit of what history was available, what was omitted by caps, source IDs/statuses, immutable prior records, and whether session restarts preserve access.

Report raw task-cluster outcomes, the 12 paired repeat contrasts for each endpoint, six task-level mean contrasts, cluster-level uncertainty intervals and sign-flip sensitivity as exploratory summaries. Keep ties, task-level losses, adverse integrity failures, grader disagreements, clipped/failed runs, and actual cost/latency visible. No overall “cumulative progress” composite should be introduced unless its weights and task-level anchors are frozen in advance and show added interpretability beyond the separate outcomes.

## Integrity gates and stop rules

Before any freeze or run: independent task/key authorship and contamination review; ambiguity and ceiling-effect review; sealed key custody; model-context isolation checks; exact normalized-output and truncation probes through both real request/parse/save paths; equivalence review of the two persistent memory packets; exact request/response and usage capture; current pricing and enforceable aggregate spend limit; independent graders; and a separately approved provider/model/purpose/cap. These borrow the rigor of T114 revision 2 / T118 but do not reuse its within-session task set or claim its protocol covers persistence.

Stop before scoring if a future evidence tranche leaked early, a model saw a key/other arm, a persistent arm lost required history without a recorded cap/omission, no-history arms received prior model conclusions, budgets or request settings differ, provenance cannot be reconstructed, or unapproved billing/retry/tool behavior occurs. Preserve the partial records and report the violation; do not replace outcomes after inspection.

## Interpretation limits and next step

The offline tests currently show that SIGMA can carry selected evidence and reject several unsafe transfers through production persistence/context code. They do not show that unscripted models exploit that ability. The proposed factorial pilot could produce a bounded signal across six task families, not a general superiority conclusion. If the owner does not authorize model calls, the honest result remains: architecture mechanics exercised offline; longitudinal research quality unmeasured.

Recommended next step is **protocol review only**: have an independent curator and methods reviewer challenge the task family/reveal design, information-equivalence audit, scoring anchors, and cap derivation. Resolve those before any tasks, keys, manifests, or prompts are frozen. Then request explicit authorization for a concrete provider, model, and hard spending cap. Do not add evaluation-specific product behavior to make the study pass.
