# Phase 2 I2 export validation — STAGING

This is an execution and provenance report for five incomplete research sessions. It does not assess scientific validity and does not satisfy the READY gate.

## Current session status

Each project requires 2 strategies × 3 rounds × (Investigator + Skeptic) = 12 validated role turns. call_limit=18 is an attempt ceiling with recovery headroom; attempts rejected by the provider, invalid outputs, and interruptions do not count as completed research turns.

| Project | Session | Valid turns | Failed roles | Never dispatched | Calls used | Terminal status |
|---|---|---:|---:|---:|---:|---|
| AI Agent Reliability and Evaluation | e3f02cce-aed5-42f7-aa01-a5cad3c99c18 | 10/12 | 2 | 0 | 18/18 | Paused; final two Skeptic requests remain dispatch-unknown |
| Sovereign AI Federation | d82391f1-956a-4546-adfd-20f030e33688 | 6/12 | 2 | 4 | 11/18 | Failed; two Skeptic outputs failed local evidence-context validation |
| Xenopus Tadpoles | 44e759ac-38bb-4e8d-8c4c-4850541ad3dd | 5/12 | 2 | 5 | 7/12 | Failed; one completed provider response failed local context validation and one confirmed provider limit rejection remains |
| Nonconsecutive Subset Sums Modulo 3 | 6ce6a07a-c844-4681-a6ec-ede98aa923ea | 10/12 | 0 | 2 | 13/18 | Ended; one strategy selected “stop productive conclusion” in round 2, so round 3 did not dispatch |
| Warp Drive Design / Physics | 71bc9990-fab0-4c1a-b03c-1d6daa976a3e | 9/12 | 1 | 2 | 13/18 | Ended; one Skeptic output failed local evidence-context validation |

Totals are **40/60 valid turns**, 7 failed protocol roles and 13 required roles never dispatched. There are 62 provider attempts: 44 completed provider responses, comprising 40 accepted role outputs and 4 outputs rejected by local validation; 16 confirmed subscription_sharing_usage_limit_exceeded rejections; and 2 Agent Skeptic calls whose provider completion is unknown. No call was automatically retried.

## Export and input checks

- All five output bundles were regenerated directly from the saved projects, decompressed, parsed, and imported through SIGMA's import_bundle service into disposable isolated workspaces. Project IDs match the pinned IDs.
- Compressed and uncompressed bundle SHA-256 values and byte counts are in MANIFEST.json.
- All five frozen input files were rehashed against the recorded input SHA-256 values before export. Original input files were not modified.
- All **62** exact provider request bodies stored in session steps were decompressed and checked against their recorded SHA-256. All three selected general, discipline and branch method notes appear in all 62 request bodies. These were the methods furnished to the investigators; this is not evidence that the agents inspected the linked literature.
- The four completed but invalid provider responses were matched by request ID, step ID and provider response ID against the durable session logs. Their complete response envelopes and wire captures, token usage, selected context manifests and validation failures are in provider-response-validation.json.gz. They remain failed outputs and are not counted as research turns. Original pre-reconciliation session JSON copies are retained in Green's private runner evidence directory.
- The two Agent requests canceled by the local observer have no matching completed provider response in the durable log. Their request bodies remain in the project bundle, and both attempts remain dispatch-unknown. They were not replayed.
- Session and method snapshots remain tied to their original project IDs. No credential or authorization headers are present in the response-validation sidecar.

## Throughput and provider behavior

The initial five sessions started concurrently through SIGMA's existing scheduling mechanisms. Initial combined wall time was **555.993 seconds**; the original initial-run timing is preserved in MANIFEST.json. A later three-project resume used existing scheduling with up to six provider calls in flight across the projects. No scheduler, concurrency, worker configuration, general Investigator/Skeptic loop, or architecture change was made.

Provider behavior observed:

- subscription_sharing_usage_limit_exceeded arrived as an in-band error over HTTP 200 in the ChatGPT-plan stream, with no Retry-After value. The limit response did not reveal a reset timestamp or identify whether the limit is account-, app-, model-, concurrency- or usage-related.
- One canary dispatched 13m38s after a confirmed rejection was rejected again. Following the latest rejection at 19:03:36 UTC, new Agent Investigator calls dispatched at 19:19:01 UTC (15m25s later) completed successfully. This is one observed interval, not a provider-published cooldown or a guarantee. Subsequent resumed requests also returned completed provider responses but four were rejected locally for context-evidence validation.
- Rejections occurred initially at observed provider in-flight overlaps of 1, 2, 4, 8, 9 and 10; later explicit recovery rejections occurred at overlap 1–2. Peak concurrency alone does not explain the rejections. No inference about the provider's actual quota rule is justified.
- No API-key fallback or metered API spending occurred. ChatGPT-plan token usage is reported where available (1,176,717 tokens across the recorded responses); exact account quota units and dollar-equivalent plan cost are unavailable.

OpenAI's [Sign in with ChatGPT recovery guide](https://developers.openai.com/siwc/token-sharing-open-source/errors-and-recovery) classifies this code as a 429 and recommends pausing requests and checking Usage; it does not publish a reset time. The [OpenAI status page](https://status.openai.com/) was operational when checked. Public reports in [openai/codex #51043](https://github.com/openai/codex/issues/51043) are anecdotal and do not diagnose this account.

## Defects and fixes on PR #433

- control_session() extended deadline_at in memory, then a guarded re-read discarded that extension. Sovereign consequently stopped on its original one-hour wall-clock deadline despite long, preserved provider-limit pauses. Commits 27074a75b... and d8774dfbf89771686803665abc213aad3aaa5aa9 persist paused duration and begin the pause clock at the confirmed rejection. Sovereign's start time, active-time allowance and call budget were preserved; only event-history-proven no-research intervals were excluded. A first repair resume made no provider call because the legacy deadline had not yet been reconciled; the correction was then applied from the saved start, limit, resume and termination timestamps and recorded in the session.
- A completed HTTP response that failed local Skeptic evidence/context validation was recorded as call_failed_dispatch_unknown. The exact response already existed in the session log. Commit 93588d9bf... records the response ID and usage, classifies the output as response_invalid, and retains the specific context-validation category. Four existing records were reconciled only when a complete response matched the step's request ID and response ID. No rejected output was promoted and no call was replayed.
- The exact failure “Skeptic cited obligation evidence not selected into its context” occurred in Sovereign and Warp; Xenopus had a separate context-validation failure. This is a research-context/provenance defect, not a provider cooldown. The current release preserves all four raw responses for Chat 2 to inspect. The context-selection method itself remains unresolved.
- The Agent observer reached a five-minute process wait cap and canceled its final two Skeptic tasks. This was an orchestration/observation error, not a provider rejection. The saved steps remain interrupted/unknown; no blind replay was attempted.
- Math's strategy-level stop decision terminated one branch before round 3. The configured protocol requires 12 completed role turns; the scheduler's early-stop behavior left 2 roles undispatched. Resolving that mismatch would require a coordinator decision about protocol completion semantics; the general loop was not changed.

## Engineering verification

At source commit 93588d9bf89771686803665abc213aad3aaa5aa9, ./sigma test passed all repository steps, including tests/research_sessions.py, tests/session_log.py, lint, formatting (336 files), Pyright (0 errors/warnings), frontend typecheck and production build. The epistemic-continuity test recorded its documented skip for graph-present execution because the local Python sandbox image was unavailable; graph-withheld checks passed. The build emitted the existing large-chunk advisory. A focused new regression verifies that a completed provider response rejected by local evidence validation retains its response ID and token usage and is not mislabeled dispatch-unknown.

Passing tests verify implementation behavior, not scientific truth, novelty, source coverage or external validation.

## Gate

The release remains STAGING, ready=false. All five protocols are incomplete. Chat 2's independent scientific review is pending, and Phase 1 must not consume this release as READY.
