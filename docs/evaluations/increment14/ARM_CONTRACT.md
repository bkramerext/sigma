# Increment 14 arm and output contract (pre-freeze candidate)

The authoritative protocol is [T114 revision 2](../T114_MATCHED_BUDGET_PREREGISTRATION.md). This file summarizes the operational contract; neither document authorizes inference.

## Shared task and final artifact

Every arm receives the exact allowlisted JSON fields `instruction`, `question`, and `evidence`. No key, rubric, score dimension, arm assignment, execution order, project history, other-arm output, repository or network access is allowed.

Both arms must return one JSON object with exactly: `conclusion` (2,000 chars), `reasoning` (3,000), `challenge` (2,500), `evidence` (2,000), `uncertainty` (1,500), and `next_test` (1,000). Apply the same normalizer and clipping rule to both. Store raw provider bytes and native validation/truncation metadata for audit, then create a scorer packet with only the normalized fields and a random anonymous ID. Never send arm code, role labels, call trace, paired counterpart or run costs to graders.

The common structure does not itself guarantee language-level blindness. Remove explicit role/arm identifiers deterministically and ask graders to guess arm plus confidence after scoring. Report the guesses. Do not exclude guessed or clipped artifacts.

## SIGMA arm

Freeze the production Investigator/Skeptic workflow and use two cycles, at most four calls. Do not inject task hints or scoring criteria. Map final structured role records into the six common fields. Keep exact requests/responses and each `potential_truncation_fields` value. A scorer-visible omission marker is added for any common-field clipping; upstream schema truncation remains a reported incomplete outcome. It does not justify dropping the pair.

## Single-role arm

Use one persistent conversation with up to four calls to investigate, deliberately challenge its central claims, revise, and produce the exact same six-field JSON. It sees only its own turns. Freeze its prompt before any live output; no tuning from these tasks.

## Matched controls

Pin exact provider/model revision, API tier, supported generation settings and state policy. Per arm: 4 calls, 48,000 input tokens, 16,000 output tokens, 64,000 total tokens, one local deterministic tool call at most, 600 seconds and a fixed dollar cap. No web or external retrieval. Failed calls count and automatic retries are disabled. Same task/evidence and identical tool permissions. Preserve actual usage/cost rather than forcing equal consumption.

## Blinding and invalidity

The runner creates scorer-only packets without execution metadata and randomizes order independently per grader. The identity map is held by a separate custodian, not in the scoring workspace. An independent curator reviews task/key provenance and contamination before freeze; graders are independent of the author, curator, implementation and run. Preserve every failed, clipped, guessed, interrupted or otherwise invalid record. Protocol violations block a superiority conclusion; they do not trigger post-hoc replacement.
