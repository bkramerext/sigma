# Phase 2 Iteration 2 — recovery and preservation update

Date: 2026-11-01. Branch: `phase2/green-iteration-1`, PR #433. This update supplements the earlier partial handoff; it does not replace it or claim scientific validation.

## Four 12/12 project archives

The four project directories with all 12 configured Investigator/Skeptic turns were copied from `/private/tmp/sigma-phase2-green-i2/projects/` into `projects/complete/`. The source directories were left unchanged. Project/session JSON, strategies, artifacts, and saved history were retained; empty ephemeral lock files were omitted. `diff -qr --exclude='*.lock'` found no differences for each archived directory. The deterministic tree digests and session provenance are recorded in [`projects/complete/README.md`](../projects/complete/README.md).

“Complete” in that archive means 12/12 accepted protocol turns. The copied records still show SIGMA's `Ended · research incomplete` action label. No research history or outcome was rewritten, and 12/12 does not establish scientific validity.

## Xenopus cancellation defect and recovery

The Xenopus session is project `01de54c9-9593-413a-9577-1a952d28da70`, session `44e759ac-38bb-4e8d-8c4c-4850541ad3dd`, protocol 8/12, round 3/3, and had 13/17 attempts used before continuation. Its last recorded `resumed` event was sequence 62; sequence 63 was `interrupted`, with no subsequent `call.started`, no running step, and no increase to `calls_used`. The worker cancellation handler nevertheless wrote “Paused after interrupted step” and claimed a provider attempt was interrupted. That classification was inaccurate for this occurrence. Cause of task cancellation is not established by the saved evidence.

The cancellation handler now distinguishes cancellation with a persisted running provider step (still marked dispatch-unknown and never automatically replayed) from cancellation before a provider step starts (paused with no provider call or attempt claimed). Focused regression tests cover both paths. The existing pause/resume/stop integration test remains green.

After tests, the existing five-project batch supervisor was launched against `messages/phase2_green_i2_resume_spec.json`. It skipped the four 12/12 sessions and resumed only Xenopus using its original session and existing scheduler. At the first post-resume checkpoint Xenopus was at 8/12 accepted turns, call 14/17 in flight: Investigator, Round 2, “Find a novel temporal coupling, not another marker.” No other project was resumed and no metered API fallback was used. This remains an in-progress recovery; later results will be appended.

## Verification

- Focused cancellation regression tests: passed.
- Existing `test_pause_counts_interrupted_call`: passed.
- `python3 -m py_compile` for changed source and tests: passed.
- Ruff check and format check for changed files: passed.
- `./sigma test`: passed all steps, including research-session tests, Ruff, Pyright (0 errors), frontend typecheck/build, and browser tests. The graph-present local execution scenario was explicitly skipped because the sandbox image was unavailable; graph-withheld behavior was checked. The existing large-bundle advisory remains.
- No browser workflow or paper-generation code was changed.

## Current gate

| Requirement | Status |
|---|---|
| Preserve four projects with 12/12 turns in repo | MET |
| Preserve source project directories unchanged | MET |
| Correctly classify pre-dispatch cancellation; preserve uncertainty for running steps | MET |
| Focused and full repository tests | MET, with documented graph-present sandbox skip |
| Xenopus complete at 12/12 | UNMET; same-session continuation is in progress |
| Scientific validity / independent source review | UNVERIFIED |
