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

## Status at the initial recovery checkpoint (superseded by final protocol completion below)

| Requirement | Status at that checkpoint |
|---|---|
| Preserve four projects with 12/12 turns in repo | MET |
| Keep source project directories in place | MET |
| Correctly classify pre-dispatch cancellation; preserve uncertainty for running steps | MET |
| Focused and full repository tests | MET, with documented graph-present sandbox skip |
| Xenopus complete at 12/12 | UNMET at this checkpoint; later completed by same-session continuation below |
| Scientific validity / independent source review | UNVERIFIED |

## Follow-up: supervisor exited on a stale terminal snapshot

The first post-fix resume correctly preserved call 14 as a locally invalid Investigator response, then the supervisor granted exactly one additional attempt because four role turns remained with only three budgeted attempts left. `control_session` queued the targeted continuation, but `_watch` then inspected the pre-resume terminal snapshot and exited before the queued worker dispatched. On process shutdown, the session was safely paused before dispatch; no call was lost or replayed. This was a second orchestration defect, separate from cancellation classification.

The supervisor now records that it queued a targeted continuation and will not terminate on that iteration's stale snapshot. `tests/research_batch.py` reproduces an invalid-response terminal state followed by a queued continuation and asserts the watcher remains alive through completion; it is part of `./sigma test`. The focused test, Ruff, formatting, and Pyright checks passed. The original invalid output and call history remain unchanged.

Post-fix, the same batch supervisor resumed only Xenopus again. The latest checkpoint is 8/12 accepted turns, with a distinct retry for the same missing Round 2 Investigator slot dispatched as call 15/18. That call is in flight; no other project was resumed.

## Follow-up: strict schema guidance for absent reference sets

The recurring `prior failure reference not present` rejection occurred while the exact request context supplied zero `prior_session_failures` and an empty allowed-ID list. The `approved continuation sources` rejection occurred while the exact request context had no `approved_continuation` packet. The validators were correctly enforcing provenance; the model was inventing references for optional arrays that had no allowed members.

Investigator/Skeptic instructions now explicitly say to return an empty `prior_session_failure_attempt_ids` array when no IDs are supplied, and to return an empty `continuation_reviews` array when no approved continuation packet exists. Prior artifacts alone do not authorize that review field. No validator was weakened, no v2 research-method source changed, and no scientific scope or loop/scheduler behavior changed. Focused prompt-contract, cancellation, lint, format and Pyright checks passed. The active Xenopus provider request was already dispatched before this code update and was left untouched; the existing supervisor has the previous prompt code loaded, so this clarification applies only to a later fresh worker process.

## Final protocol completion

The saved Xenopus project was copied into `projects/complete/xenopus-tadpoles.sigma`; its contents match the source project except empty runtime lock files. The five completed project snapshots are listed with deterministic tree hashes in [`projects/complete/README.md`](../projects/complete/README.md). Source project directories remain in place. At finalization, source and archived session records both received the additive protocol-completion label event described below; accepted turns, failed attempts, artifacts, and research conclusions were not rewritten.

| Project | Session | Accepted turns | Provider attempts | Preserved nonaccepted attempts |
|---|---|---:|---:|---|
| Agent Reliability | `e3f02cce-aed5-42f7-aa01-a5cad3c99c18` | 12/12 | 21/21 | 6 provider-limited, 2 interrupted/dispatch-unknown, 1 invalid |
| Sovereign AI | `d82391f1-956a-4546-adfd-20f030e33688` | 12/12 | 18/18 | 3 provider-limited, 3 invalid |
| Xenopus Tadpoles | `44e759ac-38bb-4e8d-8c4c-4850541ad3dd` | 12/12 | 22/22 | 1 provider-limited, 9 invalid |
| Nonconsecutive Subset Sums Modulo 3 | `6ce6a07a-c844-4681-a6ec-ede98aa923ea` | 12/12 | 15/18 | 3 provider-limited |
| Warp Drive | `71bc9990-fab0-4c1a-b03c-1d6daa976a3e` | 12/12 | 16/18 | 3 provider-limited, 1 invalid |
| **Total** |  | **60/60** | **92** | **16 provider-limited, 14 invalid, 2 interrupted** |

Every provider-limit rejection and invalid response remains recorded and is excluded from accepted turns. The two Agent dispatch-unknown attempts were not replayed. Xenopus reached all 12 accepted turns after the supervisor preserved nine invalid responses, one provider-limited response, and issued distinct safe replacement requests; no validation rule was relaxed. No metered API fallback was used.

All five source session records now carry an additive `session.protocol_complete` event and `Completed · configured protocol` action because the 12 expected role slots are accepted. Lifecycle status remains `ended`; each completion message says findings remain unverified. The update did not rewrite accepted steps, invalid attempts, artifacts, or research conclusions.

The label classification and prompt-contract hardening are in the local source commits reported by Git. The live Xenopus calls 14–22 were recorded with backend build SHA `d6a4b74947730d4323a4a2c345b9ab7120c5b572`; the later empty-reference prompt clarification was not loaded by that already-running worker. It therefore has no demonstrated effect on these results. Its focused regression passed, but research validity remains unverified and must be assessed independently.

Final verification after completion-label changes: `./sigma test` passed all steps, including research-session and batch-supervisor regressions, Ruff/format, Pyright (0 errors/warnings), frontend typecheck/build, and browser tests. The graph-present local execution case was explicitly skipped because the sandbox image was unavailable; graph-withheld behavior passed. The existing frontend chunk-size advisory remains.
