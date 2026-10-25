# Blue Increment 22 offline preparation handoff

**Issue:** [#146](https://github.com/bkramerext/sigma/issues/146)  
**PR:** [#150](https://github.com/bkramerext/sigma/pull/150) — R4R  
**Branch:** `blue/increment-22-issue-146` → `main`  
**Starting main:** `19e5bd7`; reconciled current main `8c3741a` without conflicts  
**Head:** `731da459d04070d82af40bea882f7528304a5017`

## Work completed

- Read issue #146 in full and the required repository guidance/current status.
- Audited the prior Increment 21 readiness result and SIGMA's actual research
  call, output, duration and estimated-cost settings.
- Authored a custom seven-job/two-machine scheduling task, separate exhaustive
  checker and retained offline result/hash manifest. The proposed schedule is
  valid at makespan 13. Enumeration of all 2,016 eligible machine assignment
  and order cases gives minimum 10; M1-only workload supplies an independent
  lower bound of 10.
- Prepared a four-call-per-arm comparison: actual saved SIGMA Investigator /
  Skeptic session versus a persistent four-call single-agent self-critique
  baseline. The same task/configuration and comparable calls, output, time,
  tools and spend caps are proposed. Scoring covers correctness, valid
  objections, change to subsequent work, evidence survival, unsupported claims,
  costs and elapsed time.
- Identified an execution gate: SIGMA's default total token limit is derived
  from a large request-context byte bound; it is not the proposed cumulative
  input ceiling. Its local cost budget is an estimate based on observed usage,
  not by itself an invoice-level hard spending ceiling. No provider call may be
  sent until the cumulative budget guard and provider-side spend control are
  demonstrated and the owner approves the exact run.

## Checks and evidence

- `./sigma test` — PASS twice, including once after reconciling current `main`;
  deterministic/offline fixtures only.
- `python3 docs/evaluations/increment_22/checker.py` — PASS; 2,016 cases.
- `git diff --check` — PASS.
- Provider calls: 0. Spend: $0. No live project/session or export was created.
- No real-browser check was relevant to the documentation/oracle preparation.
- No Cloud deployment changes and no Increment 23 work.

## Approval requested

See the exact proposal and conditions in
[`docs/evaluations/increment_22/preparation.md`](../docs/evaluations/increment_22/preparation.md).
The proposal is OpenAI API `gpt-6.1-sol`, high reasoning, standard tier,
API-key billing, no tools/search/retries/fallback; four calls per arm, 1,024
output tokens per call, 12,000 input / 16,096 total usage tokens per arm,
15 minutes per arm, $0.55 estimated-cost reserve per arm, and a proposed $1.25
overall spend ceiling. These limits remain proposed; no live execution occurred.
