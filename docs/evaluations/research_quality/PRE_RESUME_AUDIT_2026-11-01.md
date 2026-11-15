# Phase 2 I2 — five-project pre-resume audit and Green handoff

**Date:** 2026-11-01 (PST). **Owner:** scientific coordinator. **Single cumulative workstream:** [PR #433](https://github.com/bkramerext/sigma/pull/433), `phase2/green-iteration-1`. **Separate paper-writing lane:** [PR #430](https://github.com/bkramerext/sigma/pull/430). **Related evidence architecture:** [#447](https://github.com/bkramerext/sigma/issues/447).

**Audit basis:** the immutable `phase2-i2-v1` `MANIFEST.json`, `EXPORT_VALIDATION.md`, the I2 recovery handoff, the current branch's methodology and evidence-action docs, PR history and workflow metadata. The manifest is a previously *reported* verified export; this coordinator audit did **not** independently unpack all five gzip bundles or rerun source hashes, provider inference, research-session tests or numerical/biological/physics proofs. No research calls, deployment, or merges were made as part of this audit.

**Latest research-branch HEAD observed when this preflight was drafted:** `1c4a94bc1398bd492f62c8763977c81492f8a4ad`. Its applicable browser jobs for T200, T201, T92 and Research Outcome were successful at the time of observation; its `SIGMA verification` and T249 integrated project verification were **IN PROGRESS**, and strategy scheduler semantic-parity was **SKIPPED by trigger**. These are observational statuses, not a certification of this document's new commit. Requery *the current HEAD* and record final results before live inference.

## Executive disposition

**GO for bounded offline audit / readiness work. NO-GO for unattended provider dispatch until the current HEAD is verified, the actual provider-plan usage gate is checked, and session-specific recovery/authorization is confirmed.** This is neither a new research iteration nor an instruction to start five fresh sessions. Green may inspect exact bundles, independently verify local deterministic fixtures, and diagnose the existing interrupted/invalid calls without spending provider allowance.

**Paper-input decision is separate:** per the November 1 owner decision, [handoff/README.md](handoff/README.md) selects the **strongest independently reviewed research per subject**, whether complete or partial, with explicit limitations. Do not restore the superseded five-at-12/12 atomic publication gate. The **research execution target** remains two strategies × three rounds × two roles = 12 valid turns per project, 60 across five. A completed protocol is not a certificate of valid science.

## 1. Frozen portfolio, budget and recovery state

Source: `docs/evaluations/research_quality/handoff/releases/phase2-i2-v1/MANIFEST.json` on #433. Five frozen project identities, not replaceable by the new Qubit sample #442 or a historical math paper:

| Subject (frozen ID) | Session at archived I2 checkpoint | Valid turns | Attempts / ceiling | Recovery disposition |
| --- | --- | ---: | ---: | --- |
| Agent Reliability `da4580f5-7620-49b0-882e-aee34fcdc05d` | `e3f02cce-aed5-42f7-aa01-a5cad3c99c18` | **10/12** | **18/18** | **HOLD live resume.** Both final Skeptics have dispatch-unknown attempts; do not replay, increase budget, rewrite failure, or start a cosmetic replacement. Investigate receipts/read-only provider resolution if legitimately available; otherwise leave missing final reviews explicitly open. |
| Sovereign Federation `9175d73d-62aa-4523-a286-445f5390ae1d` | `d82391f1-956a-4546-adfd-20f030e33688` | **6/12** | **11/18** | **CONDITIONAL.** Two locally invalid outputs and four not-dispatched turns. Confirm final actual dispatched evidence allowlist and precise local failure type before any supported continuation. |
| Xenopus Tadpoles `01de54c9-9593-413a-9577-1a952d28da70` | `44e759ac-38bb-4e8d-8c4c-4850541ad3dd` | **5/12** | **7/12** | **HOLD for budget/recovery decision.** Five attempt slots cannot cover seven missing turns even without failures; retain invalid/interrupted evidence and compare stronger prior completed I1 science. |
| Nonconsecutive Subset Sums `7a8cbb3-da78-4249-8e9e-8f7c15b8ae7a` | `6ce6a07a-c844-4681-a6ec-ede98aa923ea` | **10/12** | **13/18** | **NO forced restart.** One strategy stopped with `stop_productive_conclusion` before round three. Independently test recurrence, bases, asymptotic argument and stop semantics; preserve the productive partial result and missing turns. |
| Warp Drive `e8211dc4-b70f-49d1-a514-671f44ed7e8c` | `71bc9990-fab0-4c1a-b03c-1d6daa976a3e` | **9/12** | **13/18** | **CONDITIONAL.** One provider-completed response failed local evidence/context validation; remaining roles require correct provenance and explicit safe-resume support, not retroactive validation or restart. |

**Total archived checkpoint:** **40/60** valid turns; 62 provider attempts, 44 completed provider responses (including **four locally invalid**), **16** explicit `subscription_sharing_usage_limit_exceeded` rejections, **two dispatch-unknown** Agent Skeptics, **13** protocol turns never dispatched, **0/5** fully completed sessions. Provider: ChatGPT-plan connection, `gpt-6.1-sol` / high; no metered API fallback or API spend. Observed plan rejections do not identify a reset time; do not infer that the plan is now available. Historical archive state stays `STAGING`, not overwritten.

All originals and failure histories are preserved in the five `*.bundle.json.gz` project files and `provider-response-validation.json.gz`, with uncompressed/compressed SHA-256, source selections, request hashes and identities in the manifest. `EXPORT_VALIDATION.md` previously reports parsing/import/hash checks. Before new export publication, Green must rerun those validations on the *new versioned files* and record exact current source and code SHAs. **Never rewrite the archived manifest to report subsequent progress.**

## 2. Research-method source preflight

The current deterministic, branch-aware selector uses locally readable coordinator-vetted methodological notes before the first role, saved with their source-set digest, included in **both** role request bodies, and disclosed in Outcome. Existing I2 resumes keep pinned `phase2-i2-v2` treatment; **only fresh** sessions use `phase2-i2-v3` evidence-to-action guidance. Changing source notes during an in-progress session would confound comparison.

Archived source-set audit (these are **method references**, not retrieved primary evidence proving scientific results):

| Project | General / discipline / specialized source IDs | Frozen source-set SHA-256 |
| --- | --- | --- |
| Agent | `nasem-scientific-methods` / `acm-software-research` / `acm-engineering-method` | `c3157a3836c5fe2bfce56bef8e0df8594aa14d7c4477ed2fcfdbc6c760dc6ffd` |
| Sovereign | `nasem-scientific-methods` / `acm-software-research` / `nasa-federation-decisions` | `a9ea45d010fb210fb48acfaa3e8badee85dc07cb59d436706fa4f7f9b2897623` |
| Xenopus | `nasem-scientific-methods` / `nc3rs-experimental-design` / `nc3rs-experimental-unit` | `b8f054176cfcdfc0a15994d3996afe04f8c0c07bc54ee40af61639b812f4ba26` |
| Math | `nasem-scientific-methods` / `tao-solving-mathematical-problems` / `applied-combinatorics` | `47b2921da0d7c075fdb3a1ead31f5814f5187524708fd3e7c85d88fba417ecd7` |
| Warp | `nasem-scientific-methods` / `nasem-physical-models` / `tong-einstein-equations` | `561c0007f1f3cee346aca8ba986362f3109343c61ce58700d2bf2635cd5ef896` |

**Minor source hygiene observation:** Agent's discipline and specialized entries have two different IDs/notes but both point to the SIGSOFT standards index URL. The substantive Engineering Research standard has its own readable [specific page](https://github.com/acmsigsoft/EmpiricalStandards/blob/master/docs/standards/EngineeringResearch.md); consider linking the direct branch-specific document **for future fresh selections**. Existing I2 source-set hashes and copied source notes must not be silently changed. There are still two distinct source documents/locations available at the archived selection, so this is not an I2-resume blocker.

## 3. Research integrity acceptance: evidence is not eloquence

Apply existing [EVIDENCE_ACTION_CHAIN.md](EVIDENCE_ACTION_CHAIN.md) and [methodology routing](METHODOLOGY_ROUTING.md). Green must inspect saved *unscripted* output, source bodies, actual provider inputs and execution/obligation logs. For each project reconstruct **1–3 consequential claims**:

`claim ID → supplied actual evidence and type → Skeptic objection/ID → next_question or cross-strategy handoff → actual follow-up action with code/derivation/source or documented blocker → result/ID → revised/narrowed/retracted/unresolved conclusion`.

Classify separately: complete mathematical proof, bounded exact computation **actually run** (code/inputs/output/status), physical/biological observation, primary literature **actually read**, model assumption, inference, proposal, LLM-generated claim, invalid response, missing independent review. No claim of real numerical simulation, Sage/Python run, data collection, literature search, validation, or novelty without corresponding inspectable artifacts. A hypothetical discriminator or cited URL is not executed or inspected evidence. Negative and non-identifiability findings may be strong results.

**Skeptic's measured contribution** (report numerator and denominator, not just a score): number of substantive objections; objections with an actual following opportunity; proportion provoking new computation/derivation/source examination or explicit impossibility; justified revisions/retractions; unaddressed material objections; false/irrelevant objections; last-turn objections with *no opportunity* for follow-up. Distinguish lack of an opportunity from a missed opportunity.

Use `PASS / PARTIAL / FAIL / UNVERIFIED` **per pivotal claim**. Keep the separate eight-domain quality frontier: (1) rigor, (2) evidence discovery, (3) skepticism, (4) testability, (5) originality, (6) cumulative uptake, (7) epistemic calibration, (8) operational integrity. Record `PRESENT / IMPROVED / REGRESSED / UNVERIFIABLE` relative to the strongest previous artifact for each dimension, without fabricating causal effects from unmatched stochastic runs. The coordinator, not Green, owns independent scientific acceptance and best-paper-input selection.

### Critical claims to attack before promotion

- **Agent:** distinguish external-effect truth from evaluator acceptance; model crash/retry/late commits explicitly, challenge exactly-once guarantees without durable atomic seal and liveness assumptions; final Skeptic roles remain absent.
- **Sovereign:** verify atomic reserve/settle assumptions and revocation partition semantics; compare cost-per-useful-task with common denominators; stress test zero-success subgroups, delayed delivery and charged timeouts.
- **Xenopus:** check identical marginal distributions with opposite within-animal coupling, paired biological units, wound age versus intervention time, controls and sample access; do not claim measured regeneration.
- **Math:** verify exact base values, recurrence and the limiting one-third ratio with an independent derivation; finite counts never automatically prove an asymptotic theorem. Historical paper is not a research answer key.
- **Warp:** verify metric assumptions, stress-energy sign/units, energy lower-bound hypothesis and causal-control inference; separate ansatz-internal mathematics from any physically demonstrated warp effect or unverified novelty.

## 4. Execution, verification and release gates

| Gate | Evidence / decision as of audit | Required before action |
| --- | --- | --- |
| Five frozen project identities and historical export preservation | **Recorded; prior export validation reported.** | Confirm exact IDs/hashes on next import; never overwrite source archives. |
| Existing role loop, scheduler, UI, security scope | **Preserved by stated PR scope; not newly re-tested by this audit.** | No topology, concurrency, provider-spend or user-experience changes for quality work. |
| Method note selection and stable version | **Three notes/tier per project documented, frozen v2 hashes.** | Inspect saved provider-input audits and keep old sessions v2; new sessions v3 only with independent authorization. |
| Research-context allowlist mitigation | **Committed, targeted to post-compaction obligation citations.** | Run focused mixed supplied/withheld/pointer-only fixture in both paths and `./sigma test`; verify exact dispatched allowlist, without relaxing validation. #447 is separate later work. |
| Current HEAD CI / focused recovery tests | **Pending** at observed HEAD `1c4a94bc...`: SIGMA verification and T249 still in progress; several browser jobs passed, scheduler-parity skipped. | Record exact verified final head, workflow run URLs and conclusions. New commits require a new checked head. |
| Provider capacity and billing | **UNKNOWN**; sixteen explicit plan sharing-limit rejections in historical execution. | Check current permitted plan usage and explicit owner/worker authorization. Do not probe repeatedly, assume reset, or switch to metered API. |
| Agent uncertain calls / per-session ceilings | **BLOCKED for unattended replay** (two unknown dispatches, 18/18 attempts). | Only proof of safe reconciliation or coordinator-approved non-destructive disposition; otherwise retain honest gap. |
| Green scientific evidence-chain review | **ASSIGNED, not completed** merely because a prompt and rubric exist. | Inspect all five archives offline, report pivotal claims, counterexamples, actual follow-through and comparison to strongest previous work. |
| Research → paper release | **Per-subject independent review not yet supplied.** | Scientific coordinator pins chosen bundle, commit, hashes, strongest claim and limitations as `SELECTED_FOR_PAPER_INPUT`, `CONDITIONAL`, or `HOLD`. PR #430 can use an individually reviewed partial candidate; there is no portfolio-wide 12/12 release gate. |

## 5. Green next action and stop/go decision

1. Pull **current** PR #433 HEAD; check GitHub CI at that exact SHA. Run local deterministic `./sigma test` and focused evidence/obligation selection, failed-response and resume/checkpoint regressions. Report `NOT RUN` for checks not executed. If CI fails, fix only the narrowly reproducible defect with a focused failing test, preserving prior archives and role protocol.
2. Independently re-read the five archived project bundles (all strategies and rounds), validate recorded compressed/raw hashes and required-role accounting against `MANIFEST.json`. Inspect the four invalid-response envelopes separately; **do not accept them**. The two Agent uncertain calls remain outstanding.
3. Complete the **offline** five-subject evidence-action and Skeptic contribution scorecard, comparing each to its strongest prior science. Keep distinctions among planned work, executed work, conditional mathematics, checked primary literature and observed data. Report evidence/source omissions and contradiction retention, not mere method-note inclusion.
4. Prepare a **per-project safe-recovery plan**: terminal status, actual remaining attempts, exact missing roles, whether existing app exposes a non-destructive resume, unresolved provider dispatch, and whether a near-complete run should remain partial. **No reset to improve appearance.** Do not continue blocked Agent/Xenopus attempts without resolving explicit gates.
5. If latest HEAD has certified verification **and** real permitted ChatGPT-plan usage is confirmed **and** existing session-specific checks authorize a safe continuation, resume only genuinely safe work within persisted limits; record old v2 treatment. A recurring sharing-limit rejection ends further attempts, not a retry storm. Do not launch five new v3 sessions without a separate explicit scientific-iteration decision and usage authorization.
6. Publish *new versioned* bundles, hash manifests, tests, provider-call state, elapsed/tokens/usage, per-project quality comparison, and unresolved blockers **on PR #433 only**. Do not publish or merge to `main`, start a new #434, silently update #430, or mark best-paper input without the coordinator's independent verdict.

**Scope/cleanup disposition:** #430 remains Phase 1 (fixed research → papers), #433 remains cumulative Phase 2, #447 remains the nonblocking longer-term evidence catalog design, #442 the separate future Qubit sample. PR #450 and UI/Project Type changes are independent and should not collide with Green's research restart. Do not close unrelated tickets merely for tidiness.

**Green bootstrap:** “Read `docs/evaluations/research_quality/PRE_RESUME_AUDIT_2026-11-01.md` on PR #433, then `messages/phase2_green_out_2_consolidation.md` and `messages/phase2_green_out_evidence_action.md`. Begin with the offline, no-provider-call audits and current-HEAD tests. Do not resume live calls until all explicit gates are verified. Commit the next numbered Green report and any new immutable research artifacts to #433; report blockers honestly.”
