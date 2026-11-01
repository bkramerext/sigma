# Phase 2 — Green iteration 1 handoff

**Status:** checkpoint only; three-subject research execution is held at the input-verification gate. This is not an iteration acceptance claim and does not authorize iteration 2.

## Branch, PR, code

- Branch: `phase2/green-iteration-1`, based on current `origin/main` at `92bc34eda4c53decd6de29af315100251a5fde62`.
- Draft PR: references master issue #432. No merge or deployment.
- Exact code SHA for this checkpoint: `92bc34eda4c53decd6de29af315100251a5fde62`. No Phase 2 session ran, so this SHA is the branch base, not a session-execution SHA.
- No source research, Phase 1 code, scheduler, loop, worker configuration, UI, paper generator, or user data was changed.

## Inputs and protocol

Agent Reliability and Sovereign AI Federation Phase 1 source bundles were verified byte-for-byte and copied into `docs/evaluations/research_quality/iteration_1/inputs/`. Their project IDs, source SHA-256 values, sizes, archive hashes, and paths are in `docs/evaluations/research_quality/iteration_1/README.md` and `inputs/phase1_verified_inputs.json`.

The recorded Xenopus Phase 1 frozen file is 2,149,128 bytes with SHA-256 `a7ff404708327b1e1a8c80c19426b0463ab412c61d37fe0406b4c334d9bc28a6`. The expected file is absent. The current local bundle and a file in the Phase 1 scratch worktree both have the correct ID/title but different hashes and sizes; neither is treated as the frozen input. No Xenopus replacement was made.

Arithmetic is `N=2 strategies × 2 role turns × 3 rounds = 12 total role turns`. Agent and Sovereign frozen settings are 18 calls / 3 rounds over three strategies. Selecting two strategies yields a 12-turn three-round maximum; the 18-call value is a ceiling, not the expected turn count. Current local Xenopus settings are 12 calls / 2 rounds over five strategies. Its exact Phase 1 settings remain unverified. The requested three rounds can be set only on the isolated Xenopus copy after the exact frozen bundle is supplied; no scheduler or general loop setting is required.

## Why no sessions launched

The addendum requires all three independently isolated projects to launch concurrently. Starting Agent and Sovereign without the verified Xenopus input would create a different, incomplete experiment. Therefore all three starts were held. There are no Phase 2 session IDs, turn records, results, session hashes, elapsed times, provider calls, retries, or inference costs to report.

The configured ChatGPT-plan credential store has a refresh credential but an expired access token. No token refresh or model request was made. The ambient `OPENAI_API_KEY` was not used. Resource contention, provider limits, rate limiting, context selection, execution failures, and research outcomes are unobserved.

## Scientific and engineering observations

See `docs/evaluations/research_quality/iteration_1/README.md` for the three-subject Phase 1 baseline frontier, including conditional Agent reliability bounds, Sovereign's saved turn-18 Skeptic failure and incomplete review, and Xenopus' mathematical identifiability results with unresolved biological validation. Those are Phase 1 observations, not new Phase 2 findings. The precise Sovereign failure is call 18 / attempt `d9b6ed92-4d4a-4531-9adb-4e225169fed2`, role `skeptic`, status `failed`, `failure_kind=provider_error`; all eight saved artifacts remain partial (seven `convincing_unverified`, one `incomplete`).

No research-engine defect was reproduced, and no runtime fix was made. The confirmed gate is source-provenance mismatch for the frozen Xenopus export. The focused safe disposition is to preserve the two exact source bundles and wait for the exact third bundle or an explicit decision to use a differently hashed baseline.

## Methods and verification

Relevant public method sections and their limits are recorded in `docs/evaluations/research_quality/iteration_1/METHODS_READ.md`. `./sigma test` exited 0: repository offline scenarios, ruff lint/format, pyright, frontend typecheck, and frontend production build passed. The graph-present local execution check was skipped because the optional Python sandbox image is unavailable. Vite emitted its large-chunk advisory. No live inference occurred. Real-browser checks were not run; this branch changes no UI.

## MET / UNMET / UNVERIFIED

- **MET:** isolated Phase 2 branch and one draft PR; verified and preserved exact Agent and Sovereign Phase 1 exports; read the complete master ticket and latest Phase 1 scientific review, including PR #430, the I3 deep review, and Issue #431; verified protocol arithmetic; ran offline repository checks.
- **UNMET:** fresh isolated sessions for all three projects launched concurrently; full 12-turn/3-round execution; complete Phase 2 turn-level exports; Phase 2 scientific frontier comparison.
- **UNVERIFIED:** exact Xenopus frozen input; plan credential refresh/authorization during actual inference; actual provider performance, cost, contention, session integrity, and scientific outcomes.

**Required next action:** provide the exact Xenopus frozen bundle with SHA-256 `a7ff404708327b1e1a8c80c19426b0463ab412c61d37fe0406b4c334d9bc28a6` or direct Green to use a differently hashed baseline with the mismatch explicit. Then launch all three isolated sessions concurrently, preserve their complete exports, and append a completion addendum here. Do not begin iteration 2 before the coordinator's review.
