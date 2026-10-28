# Pilot inference readiness: coordinator handoff

Base: `main` at merge commit `14e59461ab813697d93fe8f178dff63add73b7cb` (PR #293). No changes to #293.

## Scope implemented

- Global sponsored API inference ceiling remains **$15 by default**, but an operator may deliberately set `SIGMA_CLOUD_GLOBAL_SPEND_CEILING_USD` as high as $1000. The established $15 per-user allowance maximum, existing member grants, and current production environment remain unchanged.
- The **per-user token counter** uses the same authorized allowance window as per-user spending. An administrator's existing Reload operation starts a fresh user dollar/token window without deleting old call rows, outstanding unknown charges, or global cumulative obligations.
- The existing session header now includes **Est. cost** using saved `estimated_cost_usd` and `cost_status`, showing unavailable instead of an invented zero when accounting is incomplete; small positive estimates display `<$0.01`.
- Deployment instructions distinguish current production defaults from configurable maxima and clarify that there is **no automatic global reset**.
- No new research workflow, settings control, dialog, or dashboard.

## Added deterministic coverage

- Ten distinct workspace subjects, two sessions each, $16 in aggregate charges under an explicitly configured $20 global ceiling, with blocked overspend.
- Per-user token allowance reuse after the pre-existing administrator Reload operation, while the original historical global charges remain recorded.
- Existing real-Chrome Home running-session fixture now tests the visible session-cost estimate and the unavailable state.

## Verification / outstanding gates

- Changes committed through GitHub; no local code runner, browser runtime, or OpenAI provider was invoked by the coordinator.
- Await GitHub CI; these tests are authored, **not yet claimed passed**.
- Human local browser assessment requested before merge after CI. Real provider-backed multi-session quality, actual API charges, service billing/project limits, and production configuration remain **UNVERIFIED**. No paid provider request, credential change, deployment or spend-ceiling change was made.
- For diagnosis of a failed investigation, use the existing **Report / Export → Project file** JSON and attach it to ChatGPT. The export includes session history, steps, and cost estimates, but intentionally does **not** include the service-wide private SQLite spend ledger. If a failure is funding-related, compare the administrator's Account usage amounts and obtain a separate privacy-safe operator ledger snapshot; do not infer global spending solely from the project JSON.

## Pilot acceptance

A 5–10-person pilot should complete representative real multi-session investigations without avoidable SIGMA admission/accounting failures, using an approved funded API-key provider and conservative limits. Passing deterministic tests and PR merge **does not** constitute live provider or full pilot acceptance.
