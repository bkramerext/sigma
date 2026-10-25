# Blue Increment 22 offline-preparation handoff

**Issue:** [#146](https://github.com/bkramerext/sigma/issues/146)  
**PR:** [#150](https://github.com/bkramerext/sigma/pull/150) — R4R  
**Branch:** `blue/increment-22-issue-146` → `main`  
**Starting main:** `19e5bd7`; reconciled current main `8c3741a` without conflicts  

## Prepared comparison

- The authored seven-job/two-machine scheduling problem and independent
  exhaustive checker are retained under `docs/evaluations/increment_22/`. The
  proposed schedule is valid at makespan 13. All 2,016 eligible machine
  assignment/order cases were checked; the exact optimum is 10, with a matching
  lower bound from M1-only jobs D/F/G.
- The frozen arms are a real SIGMA Investigator/Skeptic portfolio session and
  one persistent single-agent self-review conversation. They share the same
  task, OpenAI API model `gpt-6.1-sol`, high reasoning, standard service tier,
  maximum four calls, 1,024 output tokens/call, 200,000 reserved input tokens,
  4,096 output tokens, $0.55 local cost cap, and 15-minute arm limit. At most
  two offline Python/Sage computations are allowed per arm. The baseline has
  four turns: initial analysis, self-critique, revision, and final critique.
- Prompts, checker, scoring rubric, settings and procedure have a frozen
  SHA-256 manifest at `docs/evaluations/increment_22/evidence/`.

## Guard and clipping evidence

The persisted research ledger reserves exact serialized request bytes plus an
8,192-token structural allowance, full per-call output ceiling, call count and
conservative cost before any SIGMA HTTP request. It settles only against
reported usage. Unknown/in-flight calls retain the full reservation and block
future dispatch. The baseline adapter uses the same ledger. Offline tests
exercise both, including refusal before dispatch, unknown/in-flight holds,
four-call ceiling calculation, and the SIGMA production session path's saved
reservation IDs/bytes and settlement. Four maximum input reservations plus
4,096 output tokens imply $0.54096 per arm / $1.08192 combined at the checked
upper input cache-write and output prices.

SIGMA now retains a provider `max_output_tokens` partial response and usage as
an **incomplete** result. It is not counted as an incorrect answer and is not
retried. The 1,024 output ceiling includes reasoning tokens. Without the live
trial, meaningful completion at high reasoning cannot be empirically verified.

## Verification and authorization

- `./sigma test` — PASS, including backend research suite, budget/clipping
  regressions, Ruff, formatting, Pyright, frontend typecheck and production
  build.
- `git diff --check` and frozen SHA-256 manifest check — PASS.
- Existing Chrome settings fixture check did not initialize its expected
  API-key state; it opened with “ChatGPT sign-in · Google sign-in required” and
  failed its initial fixture-status assertion. No provider request was made.
- GitHub Actions run listing for the final SHA returned no workflow run at the
  time checked.
- Provider calls: 0. Spend: $0. No SIGMA trial session or export exists yet.
- No Cloud changes, Increment 23 work, or self-merge.

**Authorization request:** May I run this one comparison using OpenAI API
API-key billing only, `gpt-6.1-sol`, high reasoning, standard tier, no external
tools/search/retries/fallback or extended cache retention; four calls per arm,
1,024 output tokens per call, 200,000 reserved input and 4,096 output tokens
per arm, 15 minutes per arm / 45 minutes overall, and $0.55 local pre-dispatch
cost ceiling per arm? Before any provider request, please explicitly authorize
the one trial and confirm the OpenAI project hard spend limit is set and
verified at $1.10. The provider-side limit can lag and slightly overshoot.
The output cap's adequacy for high-reasoning completion remains an empirical
question; clipping is preserved as incomplete, never scored as a wrong answer,
and never retried. No live calls or spend will happen before approval.
