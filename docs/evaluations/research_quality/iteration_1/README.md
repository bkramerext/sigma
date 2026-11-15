# Phase 2, iteration 1 — input and execution checkpoint

**Status:** research sessions are not started. The exact Phase 1 frozen export for Xenopus is missing from accessible storage; two candidate exports with the required project ID do not match its Phase 1 hash. Because the addendum requires all three sessions to launch concurrently from the same frozen identities, no subset was launched.

## Frozen input verification

| Subject | Project ID | Phase 1 frozen input | Verification and preserved copy |
|---|---|---|---|
| AI Agent Reliability and Evaluation v1 | `da4580f5-7620-49b0-882e-aee34fcdc05d` | 10,281,881 bytes; SHA-256 `666c96aafcaaec048099f9d25ef57f66fdd284a54fb5e7aad3425fad4fde79e3` | Exact match. Compressed immutable copy: [`ai_agent_reliability_v1_phase1_frozen.bundle.json.gz`](inputs/ai_agent_reliability_v1_phase1_frozen.bundle.json.gz); archive SHA-256 `67a5a32e1989a6d7726065c1af31050daab212c9079346e730f391e270dcbcdb`. |
| Sovereign AI Federation v2 | `9175d73d-62aa-4523-a286-445f5390ae1d` | 2,570,814 bytes; SHA-256 `40cdebb730fb4cef73ea2676e9dba8e6666630ee2ec2976af595365f7b6c5ea5` | Exact match to Phase 1 after-research export on PR #430. Compressed immutable copy: [`sovereign_ai_federation_v2_phase1_frozen_after_research.bundle.json.gz`](inputs/sovereign_ai_federation_v2_phase1_frozen_after_research.bundle.json.gz); archive SHA-256 `ced4c641c4161673aa91c2a5f3d10521e6be36ba3ef8d35e8eef5ff0735ec256`. |
| Xenopus Tadpoles v9 | `01de54c9-9593-413a-9577-1a952d28da70` | 2,149,128 bytes; expected SHA-256 `a7ff404708327b1e1a8c80c19426b0463ab412c61d37fe0406b4c334d9bc28a6` | **Not verified.** Current local project bundle: 2,150,649 bytes, SHA-256 `371e3baf395ba3d66508df1a64d12f4e914e4823dd19c8ec3a66447565be46bb`. Phase 1 scratch-worktree file with the expected frozen filename: 8,175,751 bytes, SHA-256 `6b0172a3d66212eecde973821e3dc8237a487e9d0b4ce1704db5ab5320631d19`. Both contain the required ID/title but differ from the recorded frozen hash and size; neither was used as the Phase 2 input. |

The Agent and Sovereign copies above preserve their complete Phase 1 project bundles, including the saved research records. Original files were read only. No Phase 1 file was changed. The expected Xenopus export was documented in PR #430's `messages/message_in_1.md`, but is not present at the recorded local path, in this checkout, or in the Phase 1 scratch worktree under its stated hash.

## Protocol arithmetic and saved settings

The required protocol is two strategies (`N=2`) × two role turns per strategy per round × three rounds = **12 total Investigator/Skeptic role turns per project**. The 12 is a total across both roles and both strategies, not 12 per strategy. A provider or scheduling failure can still leave an attempted session below 12; the saved status and actual count must be reported without relabeling it complete.

The exact Agent and Sovereign sources contain three strategies, 18-call ceilings, and three rounds. Selecting two strategies with the three-round cap gives a maximum of 12 role turns; the larger call ceiling is not the number of expected turns. Agent and Sovereign each allow one active session per project, which permits one session in each project concurrently. The current local Xenopus v9 project has five strategies and is configured for 12 calls over two rounds. The Phase 1 frozen Xenopus settings cannot be verified until its exact bundle is restored. The requested three-round protocol would require changing `research_rounds` only on the isolated Xenopus copy; its original export would remain unchanged. No scheduler, worker, concurrency, or general loop setting has been changed.

All three source records report model `gpt-6.1-sol` and reasoning effort `high`. Exact selected strategy IDs, session IDs, start/stop settings, timing, usage, and actual turns remain **not applicable / not observed** because no Phase 2 research call was made.

The current code base for this checkpoint is `92bc34eda4c53decd6de29af315100251a5fde62` (Phase 2 branch base from `origin/main`). It is not a research-session execution SHA: no Phase 2 session ran on it.

## Phase 1 research frontier carried into this checkpoint

These are findings from the independent Phase 1 reviews, not Phase 2 results or independent scientific acceptance.

| Subject | Correctness and rigor | Evidence and skepticism | Methods, contribution, cumulative progress, calibration | Operational status |
|---|---|---|---|---|
| Agent reliability | Present: conditional outcome/acceptance identity `p=q-f+g`; the assured-commit retry lower bound is explicitly restricted. Sources include artifacts `a1a9ab51-f8d1-4b60-ba10-baad7585a34f:984e8fd3-f76b-46fb-b868-378c2f103425` and `bea430f9-56e7-4ced-aa69-376cee40c523:7d39bad1-603b-43cf-ad04-0d256b837472`. | Present: dropped-retry, split-write, finite-roster, and judge-calibration objections. Unresolved: source references and population assumptions need independent checking. | Conditional impossibility analysis is a substantive analytical result, not an empirical reliability estimate. Fault-injection, external-effect observation, and judge calibration remain proposed. Phase 1 review found metadata presented as central paper claims; that is a reporting weakness, not proof the source arguments fail. | Phase 1 source records seven sessions; latest outcome described as mixed/partial. Phase 2 execution integrity is unverified because no Phase 2 turn ran. |
| Sovereign AI federation | Present: conditional cost threshold, policy/revocation impossibility, and reservation invariant. None establishes deployed advantage. | Present: sensitive-stratum `200/800` counterexample and delayed-send liability. MindRouter source pointers were not retrieved. The saved source has eight artifacts: seven `convincing_unverified`, one `incomplete`, all objective status `partial`. | Pilot and 1,800-pair sufficient-certificate are conditional/prospective, not observed effectiveness or minimum sample size. A final Skeptic attempt failed, leaving 55 obligations unresolved in its selected context. | Session `36e06a52-e138-48ee-9ccf-1519bb6faedc`: 18 calls, 17 completed and call 18 failed (`d9b6ed92-4d4a-4531-9adb-4e225169fed2`, Skeptic, `provider_error`); status ended/incomplete. This failure is retained in the frozen source. |
| Xenopus tadpoles | Present: equal marginal distributions with opposite within-animal slopes; stage-mean aliasing; and `±kcQ` only under the restricted idealized pulse model. These are analytical results, not observed regeneration effects. | Present: latency, redox-persistence, spatial-mixture, species/stage, and missing-sample-manifest concerns. Actual GEO coverage and underlying measurements remain unverified in the Phase 1 review. | Pairing, animal as experimental unit, allocation/blocking, controls, and true falsifiers remain proposed design requirements. No animal intervention, expression-matrix analysis, external validation, or novelty verification is recorded. | Phase 2 source freeze is unverified. No Phase 2 session was started. |

For each project, all seven scientific quality dimensions and the separate operational gate are **unchanged from the reported Phase 1 baseline / no Phase 2 movement observed**. There is no basis to claim improvement, regression, or scientific validity from this checkpoint. The only definite blocker is source reproducibility for the Xenopus freeze; concurrency behavior and research-session behavior remain untested here.

## Execution, billing, and verification

- Phase 2 model/provider calls: **0**; Phase 2 inference cost: **$0**; retries: **0**. No mock research was used as a research result.
- The local credential store is configured for the designated ChatGPT-plan mode and has a refresh credential; the saved access token was expired at the time checked. No token refresh and no provider call were made. The ambient `OPENAI_API_KEY` was not read or used.
- Concurrency/resource contention, rate limits, context integrity, stalled calls, session failures, cost, and session timing: **not observed**, because no sessions launched.
- `./sigma test`: **PASS**, exit code 0. Offline project, research, API, CLI, security, lint, type, frontend typecheck, and build checks completed. The graph-present local execution check was skipped because the optional Python sandbox image is unavailable. Vite emitted its existing large-chunk advisory. No paid inference occurred.
- Real-browser checks: **NOT RUN**; this checkpoint changes no UI or user experience and starts no session.
- No implementation bug was reproduced; no runtime or research code was changed. The reproducible integrity finding is the Xenopus frozen-export mismatch. Replacing a missing snapshot with a different hash would not be a safe repair.

## Gate status

- **MET:** isolated branch `phase2/green-iteration-1` based on current main; one draft PR references #432; exact Phase 1 input hashes verified and complete immutable copies preserved for Agent and Sovereign; N=2/12/3 arithmetic checked; Phase 1 review findings read; offline test suite passed.
- **UNMET:** three concurrent genuine Phase 2 sessions, complete turn-level Phase 2 traces, and the required three-subject research baseline. The Xenopus exact frozen export was not available, so launching only two subjects would violate the addendum's parallel three-project requirement.
- **UNVERIFIED:** Xenopus Phase 1 freeze, refreshed ChatGPT-plan authorization, all live-provider behavior and usage, contention, and every Phase 2 scientific outcome.

Next action: restore the exact Xenopus frozen bundle (`a7ff4047…d9bc28a6`) or explicitly authorize the current export as a different, mismatched baseline. After that input gate is resolved, launch the three isolated sessions concurrently and append complete results to `messages/phase2_green_in_1.md`. Do not start iteration 2 before Chat's review.
