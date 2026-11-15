# GREEN R4R — PR #297 Gate 2 corrections

## Revision

- Implementation commit: `1696023c54cec6986cbba51356d21d0c49884830`
- Branch: `coordinator/signin-session-playback-stabilization`
- PR: #297

## Findings and corrections

1. **Credential-global provider state.** `openai_connection` held one `_identity`, cache, pending task, and model catalog for the entire process. A different credential cancelled that one task, and its result could replace the previous account's state. That is why the earlier OAuth/store-isolation tests missed it: they exercised credential ownership and persistence, not overlapping provider catalog requests. Replaced it with a bounded LRU of credential-fingerprint entries. Each entry owns status, catalog metadata, refresh time, generation, and in-flight task. Same-key calls coalesce; different keys do not cancel or overwrite each other. `inference_failure()` now requires and updates only the matching guard.
2. **Zero allowance hid the personal action.** The early return replaced the entire ChatGPT pill with Reload me!, making personal OAuth unreachable. The pill remains visible in sponsored mode, allowance exhaustion remains visible, and Reload me! is a separate action. Real API Play admission remains budget-enforced.
3. **Hosted selected mode disagreed with the pill.** `!!hosted` presented Sponsored ChatGPT even while the backend selected unsupported personal mode. Hosted personal mode now displays “Personal ChatGPT unavailable” with an explicit route back to sponsored mode. A new eligible hosted admin defaults to sponsored; a deliberate no-force personal selection remains unavailable and never borrows the sponsor credential. Forced sponsorship remains backend-enforced.
4. **Setup guidance was stale.** Getting Started now documents that the Sponsored ChatGPT pill starts the user's personal OAuth, that sponsor maintenance is admin-only, and that normal eligible local use does not require `--sponsored`.

## Verification

- `uv run --locked --no-sync python tests/model_connection.py` — PASS. Deterministic overlapping Z/B personal catalog checks produced independent catalogs/results; Z's guarded failure did not contaminate B; same sponsor checks coalesced.
- `uv run --locked --no-sync python tests/cloud_auth.py CloudAuthTests.test_hosted_default_and_explicit_sponsored_selection_match_provider_routing` — PASS. Real hosted API/auth/storage path: new eligible default, deliberate personal selection reports unavailable without using sponsor credentials, explicit sponsored selection routes to the saved sponsor token. Existing forced-mode API regression also passed in the full suite.
- `uv run --with playwright python browser_checks/local_auth_real_backend.py` — PASS. Real SIGMA API subprocess and durable storage; N has zero remaining allowance, sponsored Play is denied, the pill remains available, personal OAuth completes, and the personal-mode pill omits metering.
- `SIGMA_HOSTED_CONNECTION_FOCUSED=1 uv run --with playwright python browser_checks/hosted_sponsored_connection.py` — PASS. New-user sponsored presentation, no-force personal-unavailable state and explicit switch, separate zero-balance Reload action, and forced sponsored presentation.
- `./sigma test` — PASS, all local steps. Ruff check/format, Pyright, frontend typecheck, and production build passed. The graph-present sandbox case was skipped because the local Docker image is unavailable. The build emitted its existing large-chunk advisory.
- `git diff --check` — PASS.

The broader legacy hosted browser script was also attempted without the focused flag. It passed the ChatGPT hosted states, then failed later in its unrelated Invite Me! assertion: the rendered signed-out page had no `.project-invite-me` element. The focused hosted cases pass; the later invitation segment is not covered by this assignment.

## Scope and remaining verification

- Google/OpenAI live OAuth and live provider validation were not run. Browser OAuth and provider catalog responses are simulated external boundaries; local SIGMA API behavior and persistence are real.
- Hosted personal OAuth remains unsupported. The UI reports that state and does not present it as connected sponsorship.
- Seven live session-playback acceptance scenarios remain deferred to the next round.
- No paid provider call, CI wait, merge, or deployment was performed.

R4R requested for independent review.
