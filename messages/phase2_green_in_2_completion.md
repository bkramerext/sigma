# Phase 2 iteration 2 — completion and recovery handoff

**Disposition: incomplete research; release remains STAGING.** This report documents the five concurrent attempts, saved partial findings, recovery troubleshooting, and verification. It does not certify scientific validity. All five required 12-turn protocols remain incomplete and must not be consumed by Phase 1 as READY.

## Execution summary

- Five fresh project sessions were launched concurrently using existing SIGMA scheduling and admission. No scheduler, worker configuration, concurrency, UI, paper generation, or Investigator/Skeptic loop changes were made. Existing admission allowed up to 10 strategy calls across the five projects.
- Each project was configured for 2 selected strategies × 3 rounds × (Investigator + Skeptic) = **12 completed role turns** (6 Investigator and 6 Skeptic); 18 call attempts were available except Xenopus (12). A failed, uncertain, or never-dispatched turn is not complete.
- Actual total after recovery attempts: **32 completed role turns / 60**, 15 failed or uncertain call attempts (14 confirmed provider rejections, one dispatch-unknown), and 18 protocol roles never dispatched. Four sessions are paused after explicit recovery attempts; Xenopus remains failed/blocked. There are **zero active provider calls**.
- Initial five-project run: **555.993 seconds** combined (first start through last initial attempt). Per-project initial clocks: Agent 555.993s; Sovereign 483.803s; Xenopus 469.9s; Math 470.2s; Warp 545.0s. The four sequential recovery attempts took 41.632 seconds combined from first to last recovery attempt. Initial execution had 39 provider-call attempts. Four later sequential resumptions added eight rejected attempts. Current total: 47 attempts, 32 completed responses, 14 confirmed subscription-usage rejections, one Xenopus dispatch-unknown attempt, and zero automatic retries.
- Provider was the existing ChatGPT-plan connection (`gpt-6.1-sol`, high reasoning). No API-key fallback or metered API spend occurred. The error was `subscription_sharing_usage_limit_exceeded`; provider did not identify whether the restriction was usage-, app-, concurrency-, burst-, or otherwise account-related, and provided no reset timing. Quota usage units and exact dollar-equivalent cost are unavailable.
- Method selection occurred before research. All completed role request bodies included their selected general, discipline, and branch-specific research-method notes, with per-request digests in the session records. Audited mandatory-source omissions: 0. Prior isolation audit found no cross-project ID/context leakage.

## Per-project saved results

| Project / session | Completed / 12 | Failed or uncertain | Never dispatched | Saved scientific result (unverified) |
|---|---:|---:|---:|---|
| AI Agent Reliability and Evaluation v1 — `e3f02cce-aed5-42f7-aa01-a5cad3c99c18` | 8 | 2 rejected protocol roles (4 attempts) | 2 | Conditional indistinguishability result: a read-only linearizable status query cannot guarantee exactly-once recovery if an original request may execute later; an atomic durable seal contract can provide at-most-once safety, while exactly-once effects require progress/acknowledgment assumptions. Benchmark evaluator acceptance is separated from external correctness. Seal feasibility, independent effect oracle, empirical generality, and literature novelty remain open. |
| Sovereign AI Federation v2 — `d82391f1-956a-4546-adfd-20f030e33688` | 6 | 2 rejected protocol roles (3 attempts) | 4 | Conditional ledger result: reservation before dispatch preserves hierarchical hard caps under complete mediation, atomic durable reservations, bounded liability, and certified settlement/release. An unresolved charged timeout creates a safety-versus-retry availability tradeoff. Revocation racing with transmission, implementation/workload evidence, fairness, and comparative economics remain open. |
| Xenopus Tadpoles v9 — `44e759ac-38bb-4e8d-8c4c-4850541ad3dd` | 5 | 2 failed/uncertain roles | 5 | Conditional identifiability result: unpaired early/late marginals cannot identify animal-level temporal coupling; the proposed stage-summary design has rank at most two. A timing interaction is a candidate only under the specified model. A pulse-time gain can mimic the observed terminal-time pattern under common memory. No expression analysis, novelty, biological effect, or relevance was established. |
| Nonconsecutive Subset Sums Modulo 3 — `6ce6a07a-c844-4681-a6ec-ede98aa923ea` | 7 | 2 rejected protocol roles (3 attempts) | 3 | Candidate order-eight recurrence, initial values `(1,1,1,2,3,5,8,12)`, `a_12=128`, and limit `a_n/F_(n+2) → 1/3`, with a saved period-three residue-vector derivation. It is convincing but unverified: no persisted execution, proof checker, or independent external verification. The session stopped before completing all protocol turns and final required Skeptic review. |
| Warp Drive — `71bc9990-fab0-4c1a-b03c-1d6daa976a3e` | 6 | 2 rejected protocol roles (3 attempts) | 4 | Under the prescribed classical Einstein, unit-lapse, flat-slice, smooth-profile assumptions, saved derivation gives negative normal energy density for nonzero shift with transverse gradient and a wall-energy lower bound. A causal-control obstruction is conditional on stationary-translation assumptions. These are ansatz-specific geometric constraints, not evidence for or against physical realizability; no source model or observational validation is supplied. |

These are reports of what the saved agents derived, not coordinator-validated findings. In particular, cross-strategy agreement is not independent replication, and the session status/outcome labels do not override missing turns.

## Artifacts and provenance

- PR #434 staging release: [`phase2-i2-v1`](https://github.com/bkramerext/sigma/tree/phase2/research-snapshot-handoff/docs/evaluations/research_quality/handoff/releases/phase2-i2-v1), refreshed post-recovery export commit `60092a813f49f0ced3ad565bb3b642fccae4d7b5`.
- Five full project bundle exports and compressed/uncompressed SHA-256, canonical input hashes, method selections, session IDs, per-turn IDs/body hashes, call statuses, tokens, times, and remaining obligations are enumerated in that release's `MANIFEST.json`. `EXPORT_VALIDATION.md` records gzip/JSON parsing, bundle import/identity checks, input preservation, and request-body/source validation.
- Frozen inputs and full raw bundles remain under `/private/tmp/sigma-phase2-green-i2/`; original inputs were preserved. The fixed exports include all saved project files, including method snapshots, artifacts, steps, peer context, evidence, contradictions, unresolved obligations, execution records, and failed/uncertain calls. No export was edited to manufacture completion.
- Research execution code SHA: `59687773fc5df0ad658538c38e20396add0276b4`.
- Recovery fix commit: `5fc8637535fb4c76f175502645a372e8c569899a` on PR #433, branch `phase2/green-iteration-1`.
- Initial export commit: `2f6ec92374cc837905469c4f8d44f8fa298a7e03`; post-recovery refreshed export commit: `60092a813f49f0ced3ad565bb3b642fccae4d7b5` on PR #434, branch `phase2/research-snapshot-handoff`.

## Troubleshooting and recovery

The provider rejection first terminated all five runs; this is why the processes were terminal rather than active-but-slow. A bounded SIGMA recovery defect made this harder to recover from: quota-limited sessions were marked `failed`/`ended`, but the supported resume action accepted only `paused`/`stopped`.

The fix on PR #433 pauses sessions only after a confirmed rejected provider response, preserves the rejected attempt and completed research, makes no automatic retry, and permits continuation only after explicit resume plus saved-state/call-budget checks. Focused regression tests cover pause, no added calls before explicit resume, preserved failed attempt, and safe continuation. After reviewing the provided Usage page (60% five-hour and 36% weekly allowance remaining; SIGMA plan use enabled, 100% app cap), I resumed Agent as a canary and then Sovereign, Math, and Warp sequentially. Each project dispatched two pending strategy calls; all eight were rejected with the same provider error. Completed turns and contexts were preserved, and all four sessions paused. This happened at two concurrent strategy calls within one project, so the prior five-project peak of 10 is not a sufficient explanation. It does not establish whether a burst/concurrency restriction or another provider/account restriction applies. Request bodies and all selected method-source notes for the eight rejected calls have verified hashes and are preserved in the refreshed bundles. Further attempts were stopped after this repeated shared-provider rejection. Xenopus is correctly blocked: its dispatch-unknown attempt must not be replayed, and only five attempt slots remain for at least seven pending protocol turns. It needs coordinator disposition or a safe, separately authorized recovery plan; do not forge a turn or silently create a replacement session.

## Engineering verification

- Focused provider-limit recovery regressions passed.
- `PYTHONPATH=src uv run --locked --no-sync python tests/research_sessions.py` passed, including persistent research-session and 10-strategy load scenarios.
- `./sigma test` passed all steps, including research-session tests, `ruff check`, formatting check (336 files), `pyright` (0 errors/warnings), frontend typecheck, and production build. The build emitted the existing >500 KB chunk advisory. One epistemic-continuity test reported its documented skip because the local Python sandbox image was unavailable; graph-withheld behavior passed.
- These checks verify execution and code behavior, **not** the truth, novelty, or scientific significance of the research results.

## Gate status

| Requirement | Status | Evidence / reason |
|---|---|---|
| Three-plus-two project identities and frozen inputs preserved | MET | Manifest input hashes, project IDs, full bundle exports |
| Concurrent start with existing scheduler/admission | MET | Five overlapping starts; max observed provider concurrency 10 |
| Correct 2-strategy × 3-round × I/S arithmetic | MET | 12 expected turns each; counted only completed role outputs |
| All 60 required turns and final Skeptics complete | UNMET | 32/60 complete; no session is 12/12 |
| Full exports preserved and hash/import checked | MET | PR #434 STAGING release, manifest and validation |
| Quota-limited explicit recovery implemented and regression-tested | MET | PR #433 commit `5fc8637`; no automatic replay |
| Resume four safe sessions without losing saved context | MET | All four resumed via the fix; each preserved prior work and safely paused on a new provider rejection |
| Complete the five protocols | UNMET | Still 32/60; 14 known rejections, one dispatch-unknown; 18 roles never dispatched |
| Diagnose provider restriction | UNVERIFIED | Four sessions repeated the same error at two concurrent calls; Usage page showed remaining allowance, but provider gave no narrower cause |
| Chat 2 independent scientific review | UNVERIFIED | Not performed; required before any READY transition |
| Scientific validity/novelty established | UNVERIFIED | No independent primary-source review or external verification claimed |
| PR #434 READY / Phase 1 release | UNMET | Must remain STAGING; all sessions incomplete |

No merge, deployment, or paper-generation change was made. This handoff records the provider rejection after explicit recovery attempts plus the recovery fix; it does not mark iteration 2's research objective complete.
