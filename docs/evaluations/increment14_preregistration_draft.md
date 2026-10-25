# Increment 14: preregistered research-quality comparison (draft freeze candidate)

**Status:** Protocol design only. No experimental runs authorized. No evidence of SIGMA research advantage is claimed.

## Hypothesis and design

Primary hypothesis: under equal total model resources and available evidence, a two-role SIGMA Investigator/Skeptic workflow improves *blind research-quality score* versus a strong single-role self-review workflow.

Null: no repeatable advantage after accounting for added latency, orchestration, and cost. A tie or loss favors the simpler workflow unless a specific independently demonstrated benefit warrants additional complexity.

The unit of randomization and scoring is one task/variant/replicate run; the unit of paired comparison is both arms on the same task/variant and replicate index. Run order is independently shuffled within each pair, with no answer keys in prompts, memory, tools, or agent-facing files.

**No output may be observed before the protocol, prompts, evidence packs, keys, rubrics, budget, and seeds are frozen and recorded with SHA-256 hashes and a signed/dated freeze manifest.** If any are amended after freeze, record the change and conduct a new preregistration before execution.

## Task matrix (six bounded tasks, answer-free wording)

Each task must be written as a standalone, domain-specific research request with identical context for both arms. An independent curator prepares hidden answer/evidence keys separately.

| Code | Domain | Proposed research assignment | Variant |
| --- | --- | --- | --- |
| E1 | Experimental design | Design a discriminating experiment to distinguish two plausible mechanisms behind a noisy signal, with controls, confounds, power limitations and a falsifying result. | Present a fixed synthetic measurement log with distractors; withhold the log in companion variant and require uncertainty/next-observation design. |
| S1 | Source criticism | Evaluate two conflicting historical/technical claims from a small curated documentary packet, distinguishing primary evidence and inference. | Include a dated primary excerpt plus an attractive incorrect secondary summary; companion variant omits the primary excerpt. |
| C1 | Constrained engineering | Diagnose failure modes and propose minimal risk-reducing checks for an intermittently failing distributed work queue under explicit cost/latency limits. | Supply a fixed trace and budget sheet; companion variant omits the decisive trace. |
| P1 | Scenario reasoning | Produce an actionable contingency plan for a logistics shortfall with competing objectives, quantified constraints and a plausible adversarial perturbation. | Include a verified capacity table; companion variant lacks one key capacity observation. |
| M1 | Formal reasoning | Establish or refute a bounded combinatorial conjecture, separating exhaustive small-case checks from a general proof. | Supply a known counterexample-bearing finite dataset; companion variant provides only conjecture and definitions. |
| M2 | Mathematical research | Critique a plausible but incomplete lemma, identify the earliest unjustified step and devise a test or repair that distinguishes possible failure. | Include a short argument with a hidden invalid implication; companion variant omits the key lemma prerequisite. |

These are *task blueprints*, not yet executable prompts or keys. Curator must finalize actual concrete numbers, documents, artifacts, and scoring references; do not substitute well-known SIGMA sample solutions, RH explorations, or previously viewed benchmark answers. Do not include any benchmark-specific code paths.

## Arms

- **SIGMA:** existing Investigator/Skeptic orchestration and normal persisted evidence/follow-up semantics, within the common cap. Do not add a special evaluation prompt or task-specific heuristics.
- **Baseline:** same model/provider, task text, evidence/tool access, generation configuration and total resource envelope. Single conversational role performs deliberate self-criticism and final revision; may use multiple calls within the same aggregate cap. No deliberately weakened baseline prompt.
- Both arms are stateless across tasks; prompts and tool outputs can contain task-relevant content but no keys, hidden grading rubric, other arm's transcript, or previous test feedback. Hide arm identities from evaluators.
- Tool allowance (Python/SageMath/search or none) must be frozen per task and identical. Missing, failed or malformed tool calls are retained and scored; no selective reruns.

## Budgets and execution safeguards

Freeze one concrete model version/provider and identical per-task caps on: maximum model calls, summed input tokens, summed output tokens, reasoning tokens where observable/configurable, tool invocations, wall-clock cutoff, and total charged dollar cost. Record observed tokens, billable cost, wall time and exact settings for every run. Equal ceilings, not equal mandatory consumption; report efficiency separately.

**Preapproval required before first paid call:** user chooses provider, model/version, funding account, per-arm/task and full-study spending caps, and permitted tools. The current authorization covers only offline design and test infrastructure.

## Blind scoring rubric (0-4 per dimension)

Score each dimension from 0 (missing/actively misleading) to 4 (strong, independently substantiated), anchored to the precommitted hidden key and evidence packet. Weights are fixed: correctness 30%; objection uptake 20%; evidence integrity 20%; calibration 15%; useful discriminating next experiment 15%.

- **Correctness:** claims follow from supplied/actually obtained evidence, and constraints/assumptions are satisfied. Partial insight is not full proof.
- **Objection uptake:** decisive counterexamples/criticisms are correctly confronted, not buried in an appendix.
- **Evidence integrity:** reported computations/sources are traceable; no invented execution, citation, or observation.
- **Calibration:** uncertainty and withheld evidence are explicit; conjecture, computation, and proof are never collapsed.
- **Next experiment:** actionable, bounded, and predicts outcomes that distinguish competing claims.

A fabricated execution/source or knowingly hidden decisive objection is a **critical integrity failure**, recorded regardless of weighted score. Two independent scorers assess blinded final research artifacts, then adjudicate disagreement without revealing arm identity. Record inter-rater agreement and retain raw scores.

## Precommitted decisions (design proposal, to freeze before pilot)

- **Positive pilot signal:** mean paired weighted score gain >= 0.40/4 across the precommitted pairs, wins on at least two distinct domains, *no increased critical-integrity-failure rate*, and added median cost and latency each <= 25%. With six tasks and variants, report uncertainty and individual cases; positive signal is not proof.
- **Tie/negative:** any other result, including inconclusive uncertainty, supports *no demonstrated advantage*; analyze but do not claim superiority.
- **Stop / invalidate comparison:** contaminated keys, asymmetric tool or prompt access, exceeded approved spending or resource cap, missing request/response provenance, unblinded scoring, or deviations without an audit trail. Preserve all run outcomes and exclusions.
- Independently report per-domain pairs, evidence-present vs withheld deltas, failure rate, actual cost, and elapsed wall time. Do not use a post-hoc narrower sample to declare victory.

## Deliverables required to move from draft to frozen protocol

1. Six fully instantiated answer-free task prompts, each with present/withheld evidence pack, fixed references and provenance.
2. Hidden key(s) and anchored rubric inaccessible to agents; clean separate evaluator interface.
3. Canonical run manifest with hashes, independent seeds and blinded arm IDs; independent evaluator checks reproducibility.
4. Identical model and resource limits with a defensible priced cost estimate and explicit user authorization.
5. A dry-run of only parsing, hashing, scoring form and budget cutoff on synthetic placeholders; **no model calls**.
6. Signed freeze note and completed preregistration before first actual output.

## Increment boundaries

Increment 14 succeeds only when the experiment is reproducibly preregistered, independently inspectable and cost-authorized; preparation alone is not equivalent to authorization or execution. Increment 15 is the first real unscripted pilot. Increment 16 is conditional ablation/repair. Increment 17 requires unseen replication plus extended cumulative research.
