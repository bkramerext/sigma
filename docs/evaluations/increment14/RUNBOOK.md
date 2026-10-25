# Increment 14 freeze and execution runbook

**Engineering draft only. Not frozen. No paid inference authorized.** The authoritative design and proposed shakedown are in [T114 revision 2](../T114_MATCHED_BUDGET_PREREGISTRATION.md).

## Offline prepare/check

1. Run `python scripts/increment14_protocol.py --output /tmp/sigma-increment14-draft-manifest.json`. Default is three repeats, 36 pairs, 72 arm runs; all repeats/variants remain clustered in six task units.
2. Run `python tests/increment14_protocol.py`, `python tests/increment14_audit.py`, and `python scripts/increment15_offline_pairs.py --output /tmp/sigma-increment15-offline-pairs.json`. These use synthetic records only.
3. Inspect `scripts/increment14_blinding.py` test artifacts and max-boundary controls. Freeze the six common JSON fields and limits before any provider output.
4. Obtain external curator provenance/contamination signoff. Replace contaminated/ambiguous tasks before freeze and regenerate all hashes. The curator must not see model outputs.
5. Demonstrate allowlist isolation and that scorer packets contain only common normalized artifacts, anonymous IDs and required task packets. Keep arm mapping and keys outside both arm and scorer access. Have independent graders review scoring anchors and blind synthetic controls.
6. Freeze task bytes, answer keys, prompts, provider/model revision, API tier, generation settings, caps, random seed/order, normalizer digest, exclusions (protocol failure only; never outcome-based), scoring, statistical analysis and stop conditions. Timestamp/sign before outputs.
7. Obtain separate owner authorization for the exact provider/account/model/caps. No approval in issue #118 authorizes a paid call.

## Cost control and stop

For the proposed scored study, per-arm ceilings are 48,000 input / 16,000 output tokens, four calls, one local deterministic tool call, 600 seconds and $0.55. At the currently listed OpenAI standard `gpt-6.1-sol` rates ($2/M input, $10/M output), the uncached token-ceiling estimate is $0.256 per arm; $0.55 is the per-arm hard cap. Across 72 arms, hard caps total $39.60. Recheck prices and provider revision at approval; if the exact cap cannot be enforced, do not run.

For the separate one-pair shakedown: direct OpenAI Responses API, exact model `gpt-6.1-sol`, standard tier, two calls per arm, 12,000 input / 4,000 output tokens per arm, 300 seconds and $0.55 per arm; $1.25 total hard cap. Its current uncached token-ceiling estimate is $0.128 total. No tools, web, fallback, automatic retries, or alternate billing. Any model mismatch, clipping/schema issue outside the shared contract, missing provenance/usage, key leak, unexpected tool/retry, wall/cost cap risk or arm contract mismatch stops the run. Preserve partial records; do not retry.

Prices and assumptions are documented with the official [OpenAI API pricing](https://developers.openai.com/api/docs/pricing) in T114. Dollar figures are planning estimates, not permission to spend.

## Reporting

Publish every pair and failure, all raw/normalized digests, truncation metadata, scorer-level ratings and guesses, costs and wall time. Report the 36 paired differences but calculate uncertainty over six task-cluster means (`n=6`), with a t interval and task-level sign-flip sensitivity only. Do not claim general superiority or persistence. Issue #119 separately designs the longitudinal persistence test.
