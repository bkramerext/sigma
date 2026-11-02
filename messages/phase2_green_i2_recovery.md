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

## Follow-up: supervisor exited on a stale terminal snapshot

The first post-fix resume correctly preserved call 14 as a locally invalid Investigator response, then the supervisor granted exactly one additional attempt because four role turns remained with only three budgeted attempts left. `control_session` queued the targeted continuation, but `_watch` then inspected the pre-resume terminal snapshot and exited before the queued worker dispatched. On process shutdown, the session was safely paused before dispatch; no call was lost or replayed. This was a second orchestration defect, separate from cancellation classification.

The supervisor now records that it queued a targeted continuation and will not terminate on that iteration's stale snapshot. `tests/research_batch.py` reproduces an invalid-response terminal state followed by a queued continuation and asserts the watcher remains alive through completion; it is part of `./sigma test`. The focused test, Ruff, formatting, and Pyright checks passed. The original invalid output and call history remain unchanged.

Post-fix, the same batch supervisor resumed only Xenopus again. The latest checkpoint is 8/12 accepted turns, with a distinct retry for the same missing Round 2 Investigator slot dispatched as call 15/18. That call is in flight; no other project was resumed.

## Follow-up: strict schema guidance for absent reference sets

The recurring `prior failure reference not present` rejection occurred while the exact request context supplied zero `prior_session_failures` and an empty allowed-ID list. The `approved continuation sources` rejection occurred while the exact request context had no `approved_continuation` packet. The validators were correctly enforcing provenance; the model was inventing references for optional arrays that had no allowed members.

Investigator/Skeptic instructions now explicitly say to return an empty `prior_session_failure_attempt_ids` array when no IDs are supplied, and to return an empty `continuation_reviews` array when no approved continuation packet exists. Prior artifacts alone do not authorize that review field. No validator was weakened, no v2 research-method source changed, and no scientific scope or loop/scheduler behavior changed. Focused prompt-contract, cancellation, lint, format and Pyright checks passed. The active Xenopus provider request was already dispatched before this code update and was left untouched; the existing supervisor has the previous prompt code loaded, so this clarification applies only to a later fresh worker process.
