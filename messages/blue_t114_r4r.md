# Blue T114 R4R — cumulative comparison preregistration

**Branch:** `blue/t114-preregistration`

**Base:** current `main` `429b4d7` (branch started from `58b360e`, then rebased)

**Implementation commit:** `a89edf0d894bb4357b1308f71207d69ca5c1e832` (PR head also includes the tracker/handoff link update)

**PR:** [#216](https://github.com/bkramerext/sigma/pull/216), open, not merged

**Provider calls / spend / cloud operations:** 0 / $0 / none

**Elapsed time:** not captured by the command log; do not infer from test runtime.

## Delivered

- Read the complete issue #114 through the GitHub API, repository guidance,
  T114/Increment 14–15 protocols, Increment 21 readiness review, T146
  preparation and complete preserved trial assessment/artifacts, tracker, and
  current `research_sessions.py` plus test seams.
- Distinguished evidence: T146 is one genuine, authorized, same-model paired
  live case on one scheduling problem; both arms found the optimum, SIGMA's
  Skeptic made no substantive correction, and the single-role baseline adopted
  an invalid self-critique and weakened its correct conclusion. It tests one
  within-session case only. Increment 14/15 checks and the new T114 planner are
  synthetic/deterministic engineering checks; Increment 6/7 and T17.8 records
  are historical single-arm or incomplete/answer-exposed observations. No
  cumulative unfamiliar-task comparison has been run or scored.
- Added a cumulative multi-strategy / multi-session preregistration with a
  sealed independent 12-problem / six-domain selection, blind randomized pairs,
  equal-context multi-turn baseline, task-keyed scoring for correctness,
  evidence, reasoning, error correction, assessable novelty, calibration,
  unsupported claims, cost and time, plus failures and stopping rules.
- Authorization sheet proposes 192 maximum calls, 1.44M input tokens, 786,432
  output tokens, 15.6 total arm-hours, $0.65 per arm / $15.60 total. It uses
  the official GPT-6.1 Sol Standard 12-hour cache-write rate ($5/M input) and
  output rate ($10/M) checked 2026-10-26. These are planning caps only; prices,
  provider/model choice, enforcement, and Brian's explicit approval remain
  required before any live call. The document authorizes zero calls.
- Added a deterministic schedule/cap auditor and seeded 12-pair dry-run using
  synthetic opaque commitments; it retains failures and rejects missing or
  duplicate arm records. Wired its test into `./sigma test`.
- Recorded bounded maintainability assessment: 8,666-line source count,
  responsibilities/hotspots, large focused test coverage, a lazy
  python_sandbox-to-session back-edge, and low-risk extraction order. No broad
  refactor.
- Updated the front-of-file status and canonical tracker. Existing T146 actual
  project/session exports are retained; no new research session/export was
  created because no provider call was made.

## Verification

- PASS: `tests/t114_cumulative_dry_run.py` — deterministic schedule, ceiling
  arithmetic, pair coverage, invalid commitments and failure retention.
- PASS: `tests/increment14_protocol.py`, `tests/increment14_audit.py`, and
  `scripts/increment15_offline_pairs.py` — 72 synthetic records / 36 pairs / 0
  model calls / $0.
- PASS: focused Ruff; focused Pyright (0 diagnostics); frontend typecheck;
  `git diff --check`.
- `./sigma test`: all scenarios completed and repository Pyright reported 0
  diagnostics. The overall command exited 1 at existing Ruff/format findings
  in unchanged `browser_checks/model_availability.py` (B023 closure and
  formatting). The runner therefore skipped the frontend production build.
  No real-browser check was applicable to the documentation/offline-harness
  change.

## Remaining / UNVERIFIED

Independent curator and sealed-key custodian; unfamiliar-task provenance and
contamination review; grader recruitment; frozen provider/model/settings and
prompts; output-boundary exercise through both actual adapters; effective
model-visible isolation; live resource/cost enforcement and current prices at
approval; owner authorization; and all cumulative research outcomes remain
UNVERIFIED. No superiority claim is made. T114 does not authorize paid or live
provider use. No self-merge requested.
