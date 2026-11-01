# Phase 2 I2 export validation — STAGING

This validates bundle integrity and provenance for five partial project exports only. It is not a scientific review and does not satisfy the READY gate.

## Results

- Five project IDs match the pinned I2 identities, and each frozen input SHA-256 was rechecked before copying.
- Each output gzip stream decompressed and parsed as a portable project bundle. Compressed and uncompressed hashes and byte counts are in `MANIFEST.json`. All five bundles were also imported through SIGMA's project-bundle service into disposable isolated workspaces; each imported project retained its pinned ID.
- Each session ID matches its project. The saved protocol requires 12 completed roles per project: two strategies × three rounds × Investigator and Skeptic.
- Completed role turns: **32/60**. Distinct protocol roles with a failed/uncertain attempt: **10**. Failed or uncertain provider-call attempts, including explicit recovery attempts: **15** (14 confirmed provider rejections and one dispatch-unknown attempt). Required turns never dispatched: **18**. Duplicate attempts do not count as additional completed turns.
- Every completed-turn provider request audit was decompressed, its request-body SHA-256 verified, and all selected general, discipline and branch method notes found in that exact body. Mandatory context-source omissions across the saved role steps: **0**. All eight explicit recovery request bodies also match their saved request hashes and contain all three selected method-source notes.
- Original frozen input files remain unchanged. The exports add fresh I2 session records and preserve every recovery attempt.
- Provider: ChatGPT plan, `gpt-6.1-sol`, high reasoning. No API key or metered API spend was used. No automatic retry occurred; four explicit resumptions are separately recorded.

## Timing and call accounting

The five initial launches overlapped. Their combined wall time from first project start to last recorded initial attempt end was **556.0 seconds**. Per-project initial-run wall times are recorded in `MANIFEST.json`. After the recovery fix, Agent, Sovereign, Math and Warp were explicitly resumed sequentially, with two concurrent strategy calls within each project. This added **8 attempts**, all rejected; no new role turn completed. Across the initial run and explicit recovery, there were **47 provider-call attempts**: 32 completed responses, 14 confirmed subscription-sharing rejections, one dispatch-unknown request, and zero automatic retries. Exact plan quota units and dollar-equivalent cost are unavailable.

## Failures and recovery

All five initial runs stopped after the provider returned `subscription_sharing_usage_limit_exceeded`. The response does not identify whether this is plan-wide, app-specific, concurrency-related, or another provider guard. The initial implementation marked quota-limited sessions `failed`/`ended`, while `control_session(resume)` accepted only `paused`/`stopped`; this recovery defect was fixed in PR #433 commit `5fc8637535fb4c76f175502645a372e8c569899a`. The fix allows explicit resume only for definite provider rejections, checks remaining call budget, preserves failed attempts, and never retries automatically. Its focused regression test and full repository suite passed.

Agent, Sovereign, Math and Warp were each explicitly resumed sequentially after the fix. SIGMA retained their completed turns and context, dispatched the pending work, and paused them when all eight new calls received the same `subscription_sharing_usage_limit_exceeded` response at two concurrent strategy calls per project. No new completed turn resulted. This makes the original five-project peak of 10 concurrency insufficient by itself to explain the rejection, but does not distinguish a burst guard from another account/provider restriction. The user's saved Usage page showed 60% five-hour and 36% weekly allowance remaining, with SIGMA plan usage enabled and a displayed 100% app cap; those figures do not explain the error. It arrived as an `error` event over HTTP 200, with no request-level usage or retry-after details. Further repeated attempts are stopped pending clarification of the provider cause.

Xenopus was not resumed. Its dispatch-unknown Investigator request (`b0ee377a-c83c-4687-8a4a-8180252c8a2e`) is preserved and was not replayed. Only five call attempts remain for at least seven pending protocol roles, so the safe recovery check blocks continuation.

## Incomplete / not ready

No project completed its full 12 role turns; every final Skeptic is missing. Chat 2 has not independently evaluated the research. None of these projects is approved for Phase 1 consumption. This candidate remains **STAGING / NOT READY**.
