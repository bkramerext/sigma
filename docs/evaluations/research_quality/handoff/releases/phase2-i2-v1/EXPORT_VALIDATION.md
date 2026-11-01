# Phase 2 I2 export validation — STAGING

This validates bundle integrity and provenance for five partial project exports only. It is not a scientific review and does not satisfy the READY gate.

## Results

- Five project IDs match the pinned I2 identities, and each frozen input SHA-256 was rechecked before copying.
- Each output gzip stream decompressed and parsed as a portable project bundle. Compressed and uncompressed hashes and byte counts are in `MANIFEST.json`. All five bundles were also imported through SIGMA's project-bundle service into disposable isolated workspaces; each imported project retained its pinned ID.
- Each session ID matches its project. The saved protocol requires 12 completed roles per project: two strategies × three rounds × Investigator and Skeptic.
- Completed role turns: **32/60**. Failed or uncertain attempts: **7**. Required turns never dispatched: **21**. Failed/uncertain calls are not counted as completed.
- Every completed-turn provider request audit was decompressed, its request-body SHA-256 verified, and all selected general, discipline and branch method notes found in that exact body. Mandatory context-source omissions across the saved role steps: **0**.
- Original frozen input files remain unchanged. The exports add fresh I2 session records to the full project bundles.
- Provider: ChatGPT plan, `gpt-6.1-sol`, high reasoning. Provider usage-limit failures were not retried. No API key or paid inference call was used.

## Timing and call accounting

The five launches overlapped. Combined wall time from first project start to last recorded attempt end was **556.0 seconds**. Per-project wall times are recorded in `MANIFEST.json`. There were **39 provider-call attempts**: 32 completed responses, six confirmed subscription-limit rejections, one dispatch-unknown request, and zero automatic retries. No metered API spend occurred; ChatGPT-plan quota was consumed, but provider quota units and reset time were unavailable.

## Failures and recovery

All five sessions stopped after the provider returned `subscription_sharing_usage_limit_exceeded`; the response does not identify whether this is plan-wide or app-specific. Six attempts are known provider rejections and one Xenopus Investigator attempt (`b0ee377a-c83c-4687-8a4a-8180252c8a2e`) is `call_failed_dispatch_unknown`. That call is preserved and must not be blindly replayed. The initial implementation marked quota-limited sessions `failed`/`ended`, while `control_session(resume)` accepted only `paused`/`stopped`; this was a recovery defect. The bounded fix at PR #433 commit `5fc8637535fb4c76f175502645a372e8c569899a` adds an explicit-resume path only for definite provider rejections, validates remaining call budget, preserves failed attempts, and does not retry automatically. A deterministic regression test verifies pause, no work until explicit resume, and non-replay of the rejection. Agent, Sovereign, Math, and Warp satisfy the saved-state recovery checks once the provider limit is confirmed reset; no resume was attempted because the provider had rejected work and reset state was unavailable. Xenopus remains blocked: its one dispatch-unknown call cannot be safely replayed, and only five call attempts remain for at least seven pending protocol roles. Research bundles were not rewritten by the fix. Findings, skeptic outputs, context manifests, method-source snapshots, provider request audits, failures, and unresolved obligations remain in the bundles.

## Incomplete / not ready

No project completed its full 12 role turns; every final Skeptic is missing. Chat 2 has not independently evaluated the research. None of these projects is approved for Phase 1 consumption. This candidate remains **STAGING / NOT READY**.
