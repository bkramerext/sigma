# Phase 2 iteration 2 — completion and recovery handoff

**Disposition: incomplete research; release remains STAGING.** This report documents the five concurrent attempts, saved partial findings, recovery troubleshooting, and verification. It does not certify scientific validity. All five required 12-turn protocols remain incomplete and must not be consumed by Phase 1 as READY.

## Execution summary

- Five fresh project sessions were launched concurrently using existing SIGMA scheduling and admission. No scheduler, worker configuration, concurrency, UI, paper generation, or Investigator/Skeptic loop changes were made. Existing admission allowed up to 10 strategy calls across the five projects.
- Each project was configured for 2 selected strategies × 3 rounds × (Investigator + Skeptic) = **12 completed role turns** (6 Investigator and 6 Skeptic); 18 call attempts were available except Xenopus (12). A failed, uncertain, or never-dispatched turn is not complete.
- Actual total after recovery attempts: **32 completed role turns / 60**, 17 failed or uncertain call attempts (16 confirmed provider rejections, one dispatch-unknown), and 18 protocol roles never dispatched. Four sessions are paused after explicit recovery attempts; Xenopus remains failed/blocked. There are **zero active provider calls**.
- Initial five-project run: **555.993 seconds** combined (first start through last initial attempt). Per-project initial clocks: Agent 555.993s; Sovereign 483.803s; Xenopus 469.9s; Math 470.2s; Warp 545.0s. The four sequential recovery attempts took 41.632 seconds combined from first to last recovery attempt. Initial execution had 39 provider-call attempts. Four later sequential resumptions added eight rejected attempts; a later two-strategy Agent canary added two more rejected attempts after a 13m38s cooldown. Current total: 49 attempts, 32 completed responses, 16 confirmed subscription-usage rejections, one Xenopus dispatch-unknown attempt, and zero automatic retries.
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

- PR #434 staging release: [`phase2-i2-v1`](https://github.com/bkramerext/sigma/tree/phase2/research-snapshot-handoff/docs/evaluations/research_quality/handoff/releases/phase2-i2-v1), refreshed after the final canary at commit `a8c264b39ff543e542fb89cc7232dc31e3f5f895`.
- Five full project bundle exports and compressed/uncompressed SHA-256, canonical input hashes, method selections, session IDs, per-turn IDs/body hashes, call statuses, tokens, times, and remaining obligations are enumerated in that release's `MANIFEST.json`. `EXPORT_VALIDATION.md` records gzip/JSON parsing, bundle import/identity checks, input preservation, and request-body/source validation.
- Frozen inputs and full raw bundles remain under `/private/tmp/sigma-phase2-green-i2/`; original inputs were preserved. The fixed exports include all saved project files, including method snapshots, artifacts, steps, peer context, evidence, contradictions, unresolved obligations, execution records, and failed/uncertain calls. No export was edited to manufacture completion.
- Research execution code SHA: `59687773fc5df0ad658538c38e20396add0276b4`.
- Recovery fix commit: `5fc8637535fb4c76f175502645a372e8c569899a` on PR #433, branch `phase2/green-iteration-1`.
- Provider failure telemetry and error-body redaction: `228f281de6403ad65ee362fe99be34dc7c80a10b` on PR #433.
- Initial export commit: `2f6ec92374cc837905469c4f8d44f8fa298a7e03`; prior recovery export: `60092a813f49f0ced3ad565bb3b642fccae4d7b5`; latest canary refresh: `a8c264b39ff543e542fb89cc7232dc31e3f5f895` on PR #434, branch `phase2/research-snapshot-handoff`.

## Troubleshooting and recovery

The provider rejection first terminated all five runs; this is why the processes were terminal rather than active-but-slow. A bounded SIGMA recovery defect made this harder to recover from: quota-limited sessions were marked `failed`/`ended`, but the supported resume action accepted only `paused`/`stopped`.

The fix on PR #433 pauses sessions only after a confirmed rejected provider response, preserves the rejected attempt and completed research, makes no automatic retry, and permits continuation only after explicit resume plus saved-state/call-budget checks. Focused regression tests cover pause, no added calls before explicit resume, preserved failed attempt, and safe continuation. After reviewing the provided Usage page (60% five-hour and 36% weekly allowance remaining; SIGMA plan use enabled, 100% app cap), I resumed Agent as a canary and then Sovereign, Math, and Warp sequentially. Each project dispatched two pending strategy calls; all eight were rejected with the same provider error. Completed turns and contexts were preserved, and all four sessions paused. This happened at two concurrent strategy calls within one project, so the prior five-project peak of 10 is not a sufficient explanation. It does not establish whether a burst/concurrency restriction or another provider/account restriction applies. Request bodies and all selected method-source notes for the eight rejected calls have verified hashes and are preserved in the refreshed bundles. Further attempts were stopped after this repeated shared-provider rejection. Xenopus is correctly blocked: its dispatch-unknown attempt must not be replayed, and only five attempt slots remain for at least seven pending protocol turns. It needs coordinator disposition or a safe, separately authorized recovery plan; do not forge a turn or silently create a replacement session.

### Provider-limit follow-up and resilience change

At 19:03:34–19:03:36 UTC on 2026-11-01, after 13m38s without provider calls, I explicitly resumed Agent only as a canary. Both pending R3 Investigator calls (step IDs `d0692479-b1fd-47ce-9815-32e98ea6c56a` and `d12b0e0c-cc4c-453c-9cb7-f8928be4a3e5`) were again rejected with `subscription_sharing_usage_limit_exceeded`; each outer transport was HTTP 200 with an in-band SSE failure, and no `Retry-After` value was present. The session safely returned to paused at 8/12. No other project was resumed after this result. Across observed attempts, rejection duration was about 1.6–3.2 seconds; the 13m38s wait did not clear it. This is evidence against a simple short burst-only explanation, but does not identify the provider's underlying quota/entitlement rule.

I reprocessed the canonical provider request/start and terminal events across all five research logs to count actual in-flight overlap at dispatch. The six confirmed initial rejections arrived at overlaps of 1, 2, 4, 8, 9, and 10 requests; the one dispatch-unknown attempt was at 8. All ten explicit recovery rejections—including the latest two—were dispatched at overlaps of only 1 or 2, with one project active. Thus the 10-request peak cannot explain the repeated failures, and a strict requirement for more than two simultaneous calls is contradicted by observed failures at one call in flight. This does not rule out a separate provider-account/app limit, model-specific rule, or time-varying throttling.

SIGMA previously retained the local request UUID and classified code/status, but dropped OpenAI's `x-request-id` on provider rejection. The session-log HTTP error event also retained the arbitrary response body. Commit `228f281de6403ad65ee362fe99be34dc7c80a10b` on PR #433 now preserves bounded provider request IDs, sanitized machine error codes, response channel/shape, and parsed retry timing in session evidence, while omitting arbitrary error bodies. This makes future failures support-diagnosable without exposing provider text. Ordinary transient HTTP 429s are still distinguished from the sharing-usage-limit response: SIGMA respects `Retry-After` and applies a bounded five-second minimum delay for retryable rate limits; the specific subscription-sharing usage-limit code pauses the portfolio without automatic retry. Replaying that code after 13m38s reproduced the rejection, so treating it as a transient burst and automatically retrying would add calls without evidence of recovery.

The published [OpenAI status page](https://status.openai.com/) reported fully operational at the time checked. The provider's [Sign in with ChatGPT recovery guide](https://developers.openai.com/siwc/token-sharing-open-source/errors-and-recovery) classifies `subscription_sharing_usage_limit_exceeded` as a 429 and directs clients to pause new requests and check Usage; it does not reveal a reset time or distinguish plan-wide from app-specific limits. An [open Codex issue](https://github.com/openai/codex/issues/51043) contains independent user reports of the same code despite visible remaining usage; this is anecdotal corroboration, not confirmation of the cause in this SIGMA account. Historical failures predate the new telemetry and have no provider request IDs; the new fields apply to subsequent failures.

A second, more directly relevant [open SIWC telemetry issue](https://github.com/openai/codex/issues/54219) reports that a token-sharing client cannot read the documented UI usage/reset data through a supported API: its report says `/backend-api/wham/usage` returned 401 `no_matching_rule`, and successful `/v1/responses` calls had no `x-codex-primary-*`/`secondary-*` headers or rate-limit event. This is a third-party report, not an OpenAI confirmation. SIGMA will not call that undocumented endpoint with the user's ChatGPT token. The diagnostics change now under test will retain only safe `x-ratelimit-*` and `x-codex-primary/secondary-*` response metadata when the provider supplies it; absence will remain an explicit absence, not inferred quota state.

## Engineering verification

- Focused provider-limit recovery regressions passed.
- New provider-diagnostic fields, redaction, HTTP 429/SSE status handling, request-ID propagation, and safe usage-limit pause passed focused coverage in `tests/research_sessions.py`.
- `PYTHONPATH=src uv run --locked --no-sync python tests/research_sessions.py` passed, including persistent research-session and 10-strategy load scenarios.
- `./sigma test` passed all steps, including research-session tests, `ruff check`, formatting check (336 files), `pyright` (0 errors/warnings), frontend typecheck, and production build. This run included the substantive telemetry change; the final header-sanitization tweak was then verified by rerunning `tests/research_sessions.py`. The build emitted the existing >500 KB chunk advisory. One epistemic-continuity test reported its documented skip because the local Python sandbox image was unavailable; graph-withheld behavior passed.
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
| Complete the five protocols | UNMET | Still 32/60; 16 known rejections, one dispatch-unknown; 18 roles never dispatched |
| Diagnose provider restriction | UNVERIFIED | Sixteen confirmed rejections across 1–10 overlapping calls; same error after 13m38s; visible usage remained, no reset hint; provider/app/account cause remains unidentified |
| Chat 2 independent scientific review | UNVERIFIED | Not performed; required before any READY transition |
| Scientific validity/novelty established | UNVERIFIED | No independent primary-source review or external verification claimed |
| PR #434 READY / Phase 1 release | UNMET | Must remain STAGING; all sessions incomplete |

No merge, deployment, or paper-generation change was made. This handoff records the provider rejection after explicit recovery attempts plus the recovery fix; it does not mark iteration 2's research objective complete.

## Recovery completion update (supersedes execution counts above)

This update follows the recovery runs and local-validation reconciliation. The five studies remain incomplete; no scientific conclusion is certified. Their full latest exports and validation are committed to PR #434 at `8cb66b9646969d9740c563f833ef52862bb24109` (branch `phase2/research-snapshot-handoff`). PR #434 remains **STAGING**, `ready=false`.

| Project | Valid role turns / 12 | Failed roles | Required turns never dispatched | Attempts | Current session status |
|---|---:|---:|---:|---:|---|
| AI Agent Reliability and Evaluation | 10 | 2 | 0 | 18 | paused; two final Skeptics are dispatch-unknown |
| Sovereign AI Federation | 6 | 2 | 4 | 11 | failed; two completed outputs failed local context validation |
| Xenopus Tadpoles | 5 | 2 | 5 | 7 | failed |
| Nonconsecutive Subset Sums Modulo 3 | 10 | 0 | 2 | 13 | ended early after strategy stop decision |
| Warp Drive | 9 | 1 | 2 | 13 | ended |
| **Total** | **40 / 60** | **7** | **13** | **62** | **0/5 complete** |

The 62 attempts comprise 44 completed provider responses (40 locally accepted outputs and four locally invalid outputs), 16 explicit provider-limit rejections, and two Agent requests with unknown provider completion. There were no automatic retries and no API-key or metered fallback. Reported response-token usage is 1,176,717. Three projects ran concurrently initially; later recovery used existing admission with up to six calls in flight. Initial combined wall time was 555.993 seconds. No active call remains.

### Cooldown diagnosis

The provider returns `subscription_sharing_usage_limit_exceeded` in-band over outer HTTP 200 in this connection. We observed no `Retry-After` or reset timestamp. A canary 13m38s after a confirmed rejection failed again; a later Investigator dispatched 15m25s after the latest rejection succeeded. That is a single observed recovery interval, not a known cooldown duration. Rejections happened at overlaps from 1 through 10 and later at 1–2, so observed peak concurrency does not identify the quota rule. The status page was operational. SIGMA cannot detect the state before a provider response or infer its reset from missing headers; the official [recovery guide](https://developers.openai.com/siwc/token-sharing-open-source/errors-and-recovery) recommends pausing and checking Usage but publishes no reset time. Do not automatically retry this specific usage-limit code based on an assumed fixed delay.

### Evidence and fixes

PR #434 contains regenerated bundles for all five projects, `MANIFEST.json`, `EXPORT_VALIDATION.md`, and `provider-response-validation.json.gz`. All five original input hashes were rechecked; all bundles were parsed and imported into isolated temporary projects with matching identities. All 62 saved provider request bodies matched their stored SHA-256 values and contained the selected general, discipline and branch method notes. The sidecar preserves all four completed-but-invalid provider response envelopes, request/step/response IDs, usage, context manifests, wire captures, and local validation failure details. The two unknown Agent requests were not replayed. Pre-reconciliation session copies remain under `/private/tmp/sigma-phase2-green-i2/runner/provider-response-audit-pre-fix`; raw session logs remain under `/private/tmp/sigma-phase2-green-i2/projects/.sigma-session-logs`.

Bounded fixes already pushed to PR #433 (branch `phase2/green-iteration-1`, head `93588d9b8d22c43e4b4ff9c47e24e35388e72937`) preserve request IDs and safe allowlisted provider metadata, account for confirmed paused time in session deadlines, and classify completed responses rejected by local validation as `response_invalid` rather than dispatch-unknown. A focused regression covers the latter. The resume deadline correction used saved event timestamps, did not reset elapsed active work or call budgets, and made no speculative replay. The context-evidence selection defect remains unresolved; fixing it safely needs another engineering iteration. Math's early strategy stop and the Agent observer's cancellation of two calls also remain protocol-completion/orchestration issues; I did not change the general loop or scheduler.

At source commit `93588d9b8d22c43e4b4ff9c47e24e35388e72937`, `./sigma test` passed the repository checks: 336-file format check, Ruff, Pyright (0 errors/warnings), frontend typecheck/build, and research-session coverage. The documented graph-present sandbox skip occurred; graph-withheld checks passed. Existing large-chunk advisory remains. Passing tests are not evidence of scientific validity.

### Scientific record and disposition

The saved findings remain provisional and should be read from the complete per-project bundles, including all round-level Investigator/Skeptic records and cross-strategy context. In brief: Agent contains a conditional exactly-once recovery indistinguishability argument; Sovereign a conditional reservation-ledger hard-cap argument; Xenopus an identifiability limitation for unpaired early/late marginals; Math a candidate order-eight recurrence and Fibonacci-ratio limit; Warp an ansatz-specific negative-energy and wall-energy derivation. Their assumptions, counterexamples, evidence gaps, unresolved obligations, and full research artifacts are in the exports. None has independent source verification, and incomplete Skeptic coverage means none is ready for Phase 1. Chat 2's independent scientific review is pending.

| Gate | Status |
|---|---|
| Five project identities, frozen input provenance and full partial exports preserved | MET |
| Concurrent initial launch via existing execution mechanisms | MET |
| Configured arithmetic (2 strategies × 3 rounds × Investigator/Skeptic = 12 each) | MET |
| All 60 completed role turns, including final Skeptics | UNMET (40/60) |
| Context-validation defect fixed | UNMET; evidence is preserved, safe correction still needed |
| Provider cooldown duration known | UNVERIFIED |
| Independent scientific review / validity established | UNVERIFIED |
| PR #434 READY for Phase 1 | UNMET; must remain STAGING |

No merge, deployment, or paper-generation change was made. This handoff reports the execution and stopping conditions accurately; it does not complete the five required investigations.
