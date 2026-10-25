# Increment 14 freeze and execution safety runbook

## State and scope

**ENGINEERING DRAFT, NOT FROZEN, NOT AUTHORIZED FOR LIVE INFERENCE.**
PR #90 carries the first six concrete tasks and the validator. No live inference, benchmarks or spending have occurred. This work is independent of any Riemann Hypothesis session.

## Prepare/check

1. Run `python scripts/increment14_protocol.py --output /tmp/sigma-increment14-draft-manifest.json` from the repository root, on a clean pinned commit.
2. Confirm exactly six cases, 12 unique task/variant packets, two arm runs per paired comparison, deterministic seed, and hashes. Preserve the generated manifest as review artifact; do not commit a manifest with secret blinding mapping.
3. An independent reviewer checks all packets for ambiguity, ceiling effects and answer leakage. If revised, regenerate hashes and restart pre-registration; never revise based on observed model output.
4. Store blinded runner allocation and key material outside agent-accessible storage; implement an allowlist runner that transmits *only* the selected question, evidence and global instructions. Disable repository/web access unless explicitly fixed and mirrored in both arms.
5. Freeze task bytes, evaluator checks, arm prompts, model/version, tool access, budget caps, order seed, all exclusions and exact scoring thresholds. Timestamp/sign manifest before any output is observed.
6. Dry-check artifact parsing and budget cutoffs on synthetic fake transcripts only. Dry-check evaluator arm blinding and keep original scorer entries.
7. Obtain user approval identifying model, provider, billing account, per-run maximum and total dollar cap. **Do not initiate Increment 15 before this approval.**

## Identical aggregate resource envelopes

Required config: model provider and exact version; temperature, reasoning effort and all supported generation settings; maximum aggregate input/output/reasoning tokens across *all* calls per arm; maximum model calls per arm; tool-use count/time; wall-clock ceiling; and total dollar ceiling. Same evidence, task, search privileges and compute access. Baseline must self-critique and revise at least once within identical ceilings, without intentionally weakened prompts. Document when platform overhead differs. Unobservable reasoning tokens require explicit comparability caveat.

Billing estimate formula per arm: (input_cap/1e6 × provider_input_price + output_cap/1e6 × provider_output_price + tool_budget), plus separately itemized reasoning charges if any. Compute proposed worst-case ceiling: 24 arm runs for one replicate × per-arm worst case, plus known provider overhead, retry reserve and tax. **Prices must be checked at approval time**; none are asserted here. Abort a run before crossing its agreed ceiling; never silently retry or enlarge it.

## Proposed decision rules (not statistically decisive)

Primary: paired weighted mean gain >= 0.40/4, at least two distinct domains won, no increase in critical integrity failures, median cost and latency overhead each <= 25%. All other cases: **no demonstrated advantage**. Publish each pair, including failures and abstentions, plus uncertainty and variance. With 12 paired comparisons, do not imply a robust generalizable result, and do not treat repeated variants as independent domain evidence. If actual observed billings differ, report raw efficiency rather than forcing mandatory token consumption.

## Approval checkpoint

The user will review the merge-ready protocol and separately authorize provider/model/account and total spend cap. Until then, Increment 14 is an engineering-only ready-for-review artifact, not a completed freeze nor an approved experiment. Increment 15 is explicitly blocked.
