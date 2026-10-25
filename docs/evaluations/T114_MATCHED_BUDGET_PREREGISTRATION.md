# Issue 114: matched-budget blind comparison proposal

**Revision:** 1, prepared 2026-10-25 and rebased onto `main` `8562c89`
**State:** proposed and dry-run validated; **not frozen, not executed, not authorized**.  
**Claim status:** SIGMA's multi-agent research advantage remains unverified.

This document consolidates and tightens the existing [Increment 6 blind gate](increment_6/BLIND_GATE_FROZEN.md), [Increment 14 protocol](increment14_preregistration_draft.md), and [Increment 14 runbook](increment14/RUNBOOK.md). It does not claim new research results or authorize a provider request.

## Evidence audit and present state

- **Live trial:** the earlier Maximum Regions run from the stock sample used an answer-bearing strategy and cannot establish independent discovery. A later answer-free run produced a substantive proof candidate and a material Skeptic correction, but its exact dispatched inputs were not retained, so independence cannot now be verified from that run alone. Its configured 4,000 output tokens per call did not prevent structured method/response fields from ending at their 2,000/2,500-character schema limits. Those outcomes and limitations are documented in [T17.8 trial record](T17_8_LIVE_TRIAL_2026_10_23.md) and [A17.8 packet](A17_8_INDEPENDENT_ACCEPTANCE_PACKET.md).
- **Deterministic fixtures:** existing Increment 14/15 scripts validate task packets, deterministic randomization, pairing, transcript digests, score shape and fail-closed budget audits on synthetic records. These are setup checks, not research or model-quality evidence.
- **Blind comparison:** the matched-budget blind study has **not been run**. No result from scripted roles, fixtures, one live task, or agreement between Investigator and Skeptic substitutes for it.
- **Proof / independent verification:** no result in this proposal is a proof of SIGMA's advantage. A human scorer's mathematical review is independent of role consensus but is not a formal proof checker unless one is actually used.
- **Conjecture:** SIGMA may improve objection uptake and continuity; a strong single-role researcher may tie or outperform it with the same budget. Both remain hypotheses.

## Proposed comparison

Use the six concrete, synthetic task packets in `increment14/tasks.json` only after an independent curator confirms they remain answer-free for participants, identifies any recognizable/pretraining exposure, and approves a fresh sealed evaluator key outside all model-readable files and tools. Each packet has an evidence-present and evidence-withheld variant. Run one pair for each task/variant: **12 paired cases, 24 arm runs**. No stock sample, project history, earlier answer, evaluator key, scoring rubric, or other arm transcript is given to either condition. The model process receives only an allowlisted task/evidence packet and fixed instructions; disable repository and network access. If a clean blind packet/key boundary cannot be demonstrated, do not run this task set.

For every pair, pin one exact provider/model version and all generation settings. Randomize A/B execution order from the preregistered seed. Use fresh state for every arm. Give the same user task, evidence, allowed local Python tool (at most one execution, 15-second sandbox limit; network disabled), evidence timing, context ceiling, call ceiling, output ceiling, and wall-time ceiling to both conditions. No Sage or web access. Tool unavailability or failure is retained and treated identically.

**Arm A — SIGMA:** unmodified Investigator/Skeptic workflow, two cycles, at most four model calls. Preserve each role request/response, structured field truncation metadata, tool record, and final export.

**Arm B — strong single-role baseline:** one persistent conversation using the same model. Up to four sequential calls: investigate; deliberately self-criticize; revise in response to that critique; produce a concise final account with remaining uncertainty and a next falsifying test. It receives its own prior messages only, never SIGMA output. The prompt must be independently reviewed before freeze and cannot be tuned after any scored response.

Four turns at up to 4,000 output tokens each give the baseline **up to 16,000 output tokens total** (and SIGMA the same aggregate ceiling). This permits self-criticism and revision instead of forcing a single answer into a 4,000-token allowance. The historical 4,000-token setting was not itself a guarantee against truncation: the archived SIGMA run also hit per-field character limits. Preserve exact provider usage and SIGMA truncation flags; score a cut-off argument as incomplete. If SIGMA's fixed schema creates a material output-capacity asymmetry under these limits, invalidate the affected pair and report it; do not repair it after seeing outputs.

### Proposed hard ceilings

| Limit | Per arm | Full study (12 pairs / 24 arms) |
|---|---:|---:|
| Provider model calls, including failed calls/retries | 4 | 96 |
| Input tokens | 48,000 total; at most 12,000/call | 1,152,000 |
| Output tokens | 16,000 total; at most 4,000/call | 384,000 |
| Tool executions | 1 | 24 |
| Wall time | 600 seconds | 240 arm-minutes maximum |
| Hard charged-cost limit | USD $2.00 | USD $48.00 |

These are ceilings, not spending authorization or expected usage. Before any run, the owner must separately approve the provider, exact model/version, account/mode, tool policy, and **$48 maximum**. At that time, check current pricing and all billable input, output, reasoning, cached tokens and overhead. If any run could exceed $2 or the study could exceed $48, reduce and preregister a new budget; if cost cannot be bounded/enforced, do not start. No silent retry, mode fallback, or budget extension. Every failed or timed-out request counts toward four calls; unknown usage/cost blocks the next call unless the remaining worst-case exposure stays under the approved cap.

### Frozen scoring and interpretation

Two independent scorers receive randomly relabeled final artifacts without arm identity or paired counterpart. They score correctness, objection uptake, evidence integrity, calibration and useful next experiment from 0–4 using the existing fixed weights 30/20/20/15/15. They separately classify each material claim as proof, independently checked result, computation, conjecture, or unsupported/failed. A model-role agreement is never ground truth. Preserve individual scores, disagreement, blinded adjudication and the sealed-key check.

Report every paired result, variant, failure, abstention, contamination, usage, cost and latency. The pilot may be called a **bounded positive signal** only if paired weighted gain is at least 0.40/4, wins occur in at least two distinct domains, critical integrity failures do not increase, and median cost and latency overhead are each at most 25%. Otherwise report tie, loss or inconclusive as **no demonstrated advantage**. Twelve pairs cannot establish broad generalization. A null or negative result counts against adding multi-agent complexity; it is not a reason to tune and rerun the same set.

Stop and preserve the record on any key/context leak, arm/tool/model mismatch, missing request/response provenance, per-call or aggregate ceiling breach, dollar cap risk, unblinded scoring, unexplained truncation asymmetry, provider throttle, or reviewer safety concern. No selective restart. An invalid pair stays visible and is not silently replaced.

## Deterministic setup and remaining gates

`scripts/increment14_protocol.py` now emits a deterministic, unapproved draft manifest with the proposed resource ceilings and randomized pair order. `scripts/increment14_audit.py` checks per-call and aggregate input/output tokens, call/tool/time/cost caps, pair integrity and blind score shape. `scripts/increment15_offline_pairs.py` exercises this audit with explicitly synthetic records. These checks establish only that the local validator rejects malformed/over-budget fixtures; they do not demonstrate provider isolation, actual billing enforcement, scorer blinding, model behavior or task validity.

Before calling this frozen or ready for live use, require: independent task/key review; an isolation demonstration for the allowlist runner; matching SIGMA and baseline request capture; current pricing and provider budget controls; two blinded graders; and explicit owner authorization of this exact $48 / 96-call proposal. No live call is included in issue 114's first increment.

## Maintainability assessment: `research_sessions.py`

At the pinned `main` revision the module is **8,285 lines**. It combines API-facing session controls, persisted session schema and migration/recovery, provider request construction and accounting, role dispatch/worker lifecycle, context and source selection, obligation reconciliation, portfolio decisions, and Python execution feedback. The file already delegates epistemics, feedback validation, state projection, computational evidence and tool capability to adjacent typed modules; that is evidence of viable seams, not a reason for a wholesale split.

Main risks are broad helper reach across one mutable session record, intertwined local/cloud worker paths, persistence and recovery invariants, and implicit imports of private helpers from other services. Moving code without first recording those contracts can change historical-file behavior, call budgets, durable task recovery, or context provenance. Keep the module as orchestration/persistence owner for now. If a later assignment authorizes extraction, start with pure role schema/request/audit helpers, then pure source-selection/obligation-ledger functions with focused fixtures, and only then consider provider accounting or worker lifecycle. Preserve import direction and old serialized records; do not combine this maintenance work with experiment behavior changes.
