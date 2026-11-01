# Phase 2 → Phase 1: four-subject immutable research handoff

**Producer:** Phase 2 / Better Research (owner Chat 2, execution worker Green). **Consumer:** Phase 1 / Better Papers (owner Chat 1, paper worker Blue). **Tracking:** Phase 2 [#432](https://github.com/bkramerext/sigma/issues/432) and implementation [PR #433](https://github.com/bkramerext/sigma/pull/433); Phase 1 [PR #430](https://github.com/bkramerext/sigma/pull/430).

**CURRENT STATE: STAGING / NOT READY.** This PR is an intentionally separate producer-owned publication surface. **It contains no approved Phase 2 iteration-2 research exports yet** and is **not a claim that iteration 2 has run**. Consumer **MUST NOT** use any staging files as replacement source research until a complete four-subject release passes the checks below and a versioned release manifest explicitly says `status=READY`.

## Scope and relationships

- The producer completes a *fresh full investigation* for **all four** subjects in the next Phase 2 iteration: 2 selected strategies × 3 rounds × 2 Investigator/Skeptic roles = **12 expected role turns per subject**, 48 expected turns overall. Concurrency is attempted using the **existing** research scheduler/admission without changing architecture, scheduler, UI, role order or defaults.
- The producer commits the **entire frozen research project bundle** for each subject, with its saved original plus all new session artifacts, exact identity and version, trace provenance, evidence/obligation manifests and honest terminal status. The project source and research evidence must be the same bytes Chat 2 scientifically reviews; no regenerated or edited agent findings for paper production.
- The consumer performs authoring-only A/B work against **these frozen exports**, never against moving local project files or prior Phase 1 snapshots. All four must be from **one named release** and frozen at the same publication checkpoint. Do not silently combine one or two I1 projects with I2 projects, or convert a paper-evidence projection into a raw project export.
- Publication into this handoff PR **does not merge Phase 2's runtime changes**, and PR #433 does not merge Phase 1's paper generator changes. The published snapshot is a source-data interface between the phases.
- The original three topics remain; add precisely one math topic. Publication does not certify scientific validity, independent verification, novelty, external-source verification or successful objective completion. These are research outputs, not proof certificates.

## Pinned subject identities

| Subject | Frozen source project ID | I2 input basis | Notes |
|---|---|---|---|
| AI Agent Reliability and Evaluation v1 | `da4580f5-7620-49b0-882e-aee34fcdc05d` | Exact original Phase 1 bundle recorded at PR #433 I1 | Re-run fresh under I2; do not repurpose I1's 11/12 paused session as I2 |
| Sovereign AI Federation v2 | `9175d73d-62aa-4523-a286-445f5390ae1d` | Exact original Phase 1 after-research bundle recorded at PR #433 I1 | I1 paused at 8/12; record new I2 turns explicitly |
| Xenopus Tadpoles v9 | `01de54c9-9593-413a-9577-1a952d28da70` | Coordinator-authorized same-ID Xenopus baseline SHA-256 `371e3baf395ba3d66508df1a64d12f4e914e4823dd19c8ec3a66447565be46bb` | Historical Phase 1 raw-project SHA differs; don't mislabel provenance |
| Nonconsecutive Subset Sums Modulo 3 | `7a8cbb3b-da78-4249-8e9e-8f7c15b8ae7a` | `samples/nonconsecutive-subset-sums/project.json` seed / clean isolated clone | New mathematical research: this seed has **no verified frozen I2 session** yet. Never feed historical paper/answer key into research |

**Math strategy choice:** roots-of-unity weighted Fibonacci polynomials `00469f7f-ba53-4a12-944d-2d3295e48d1f` plus gap removal/Gaussian-binomial sums `9ad51640-ff9a-4d22-a928-518f032003bf`; periodic transfer-matrix strategy remains unselected. Record actual selected strategy IDs in release.

## Required versioned payload (when I2 is complete)

Publish a new immutable directory `releases/phase2-i2-v1/` with:
- `MANIFEST.json` (release ID; `status` = `READY` **only after full validation**; completed_at UTC; source PR and exact commit SHA used for research; code commit plus methodological instruction version; model, effort and provider mode; per-project original input SHA, project identity and problem hash, selected strategies and why, session ID, original/new session separation, rounds expected and actual role turn counts, interrupted/failed/never-dispatched records, output bundle filename, compressed SHA-256, **uncompressed canonical source SHA-256**, byte size, relevant saved artifact hashes, per-project epistemic outcome, and external source inspection status).
- Four complete `*.bundle.json.gz` binary source exports, preserving exact original research, saved turns, source evidence, role outputs, peer transfers, failed or interrupted records and unresolved obligations. Do not include credentials, private identifiers or other secrets. Stable file names `agent-reliability.bundle.json.gz`, `sovereign-ai-federation.bundle.json.gz`, `xenopus-tadpoles.bundle.json.gz`, `nonconsecutive-subset-sums.bundle.json.gz`.
- `SCIENCE_REVIEW.md` authored by Chat 2: four-topic factual assessment, valid bounded results, strongest counterexamples, open obligations, cross-strategy gains, explicit validation limitations, regressions and pointers into saved steps; not Green's self-report.
- `EXPORT_VALIDATION.md`: reproduce all hashes locally, raw gzip parse, original project+session record identity, exact role turns/rounds/strategies, no fabricated provider completion, original immutable I1 sources, empty/not-available evidence distinctions, no secret leakage, paper-reader compatibility, and source coverage. Include actual SHA of a full `./sigma test` run where applicable; not equivalent to science verification.
- `PAPER_CONSUMER_GUIDE.md`: safe commands to import each isolated project bundle, generate new frozen paper snapshots, extract comparison data, maintain proof/claim epistemic status and ensure math-specific theorem/proof formatting. Consumer must avoid copying mutable local projects. Do not claim exact old paper source hashes when new I2 findings differ.

**Atomic publication protocol:** commit payloads first with staging manifest `status=STAGING`; validate all four, then **last commit** changes only manifest/release marker to `READY`, recording immutable release paths/checksums and validation result. No publication with `READY` if any archive is absent, corrupted, materially misidentified, has unreported interruption, or is known to be silently truncated. A genuinely incomplete scientific objective **can** be published when explicitly marked unresolved; an execution interruption may also be published transparently if the owner accepts it as a bounded sample, but must never be called 12/12.

Do not edit files under a released directory after `READY`; fix with `phase2-i2-v2` rather than overwriting evidence. A future iteration publishes a new directory and manifest; prior releases remain immutable. Pin the exact **commit SHA** and per-file SHA-256, not a moving branch HEAD alone. Phase 1 should record the specific release ID, commit and input hashes in its own authoring run metadata.

## Phase 1 handoff condition

The consuming coordinator Chat 1 should use this PR's versioned **READY** release only when Phase 2 explicitly links the final commit, confirms four archives, verified SHA-256 and scientific status, and Phase 1 acknowledges it as the frozen replacement for its last three-iteration papers. Until then, its current frozen source protocol remains authoritative. Do not interrupt in-flight Blue work, change paper generator code here, or cherry-pick incomplete sources.

## Current I1 context (not the I2 release)

Green I1 ran three concurrent projects at research code `4b0243e3cac2e926345dc3f447725cdf4a9c5690`: Agent completed **11/12**, Sovereign **8/12**, Xenopus **12/12** (execution complete but scientifically negative/unresolved); three in-flight calls were interrupted and two never dispatched. All saved I1 research is in PR #433; **none is a substitute for a fresh I2 four-project release**.

## Ownership, review and publication

Phase 2 Chat owns the release contract, science review, integrity gate and publication; Green may prepare and hash exports in PR #433 and commit release-candidate bundles **only when instructed**. Phase 1 Chat/Blue read this PR's `READY` release but do not modify it. No Phase 1 authoring commands, provider inference calls, merges or deployment are requested by this staging PR.

**DO NOT publish `READY` until actual I2 source evidence exists and passes all four-project checks.**
