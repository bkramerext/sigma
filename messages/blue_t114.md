# Issue 114 first increment handoff

**Branch:** `blue/t114`  
**Base:** `main` at `8562c89` (rebased after T89 merged during this increment)
**PR:** pending creation
**Elapsed:** approximately 35 minutes
**Provider calls / spend / cloud provisioning:** 0 / $0 / none

## Delivered

- Audited the existing Increment 6 and 14 blind protocols, Increment 15 offline preparation, and Maximum Regions records. The matched-budget blind comparison remains unexecuted. The original stock-sample run is answer-leaked; the later answer-free run is one live observation with missing exact request bodies and material response-field truncation. Neither proves comparative advantage.
- Added [T114 matched-budget preregistration](../docs/evaluations/T114_MATCHED_BUDGET_PREREGISTRATION.md): 12 pairs, 24 arm runs, 96 maximum provider calls, 48,000 input and 16,000 output tokens per arm, maximum 12,000 input / 4,000 output tokens per call, one bounded local tool use, 10-minute arm wall cap, $2 per arm and $48 overall. The single-role baseline gets four turns for self-criticism/revision; output is not limited to one 4,000-token response. Current pricing, hard budget enforcement and explicit owner authorization are still required before use.
- Extended the existing deterministic validator to check per-call and aggregate input/output tokens, total token consistency, finite numeric usage, and existing call/tool/time/cost and pairing constraints. `./sigma test` runs the focused protocol, audit and synthetic pair dry-run.
- Added a short newcomer summary and issue 114 evidence note at the beginning of `docs/STATUS.md`, retaining its chronological entries.
- Inspected `research_sessions.py` at 8,285 lines and documented maintainability seams/risks and a behavior-preserving extraction order. No broad refactor.

## Evidence and limits

- Focused protocol, audit and offline-pair checks passed. The pair run created 24 synthetic records for 12 pairs and reported zero model calls and zero spend. The readiness script reports `BLOCKED_FOR_LIVE_PILOT`, including unproven runner isolation and absent provider/model, graders and authorization.
- Final `env -u SIGMA_CLOUD_BOOTSTRAP_ADMIN_EMAIL ./sigma test` on rebased main passed all scenarios, Ruff, format, Pyright, frontend typecheck and production build. One immediately preceding full run transiently failed at `tests/storage.py`; that test passed alone and the next full run passed. Earlier attempts stopped at Ruff formatting and missing frontend `tsc`; locked dependencies were installed and formatting corrected. `git diff --check` passed.
- No real-browser check was applicable because no UI behavior changed. Deterministic fixtures establish validator behavior only; they are not live trials, proof of model quality, or independent verification of a theorem.

## Handoff / remaining gates

This is a proposal, not a frozen experiment. Before any live run: independent review of tasks and sealed keys; demonstrate isolation of model-visible inputs; test matching request capture for SIGMA and baseline; select provider/model/account and verify current full pricing against the $2/$48 caps; prepare blinded independent graders; and obtain explicit owner authorization for this exact experiment. Stop rather than spend if prices or enforcement do not fit.

Green's active documentation branch also changes `docs/STATUS.md`. This branch's change is additive at the top plus one new dated entry; please reconcile by preserving both the current-state summary and Green's historical/documentation changes. No direct worker coordination occurred.

No live experiment is reported complete, no theorem is claimed as independently verified here, and no PR merge is requested from the author.
