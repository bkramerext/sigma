# Sign-in, research execution, and saved session playback stabilization

Status: draft, under functional review. Base: `main` (PR #296 already merged).

## Correctness fixes

- Display one-time invitation welcome based only on the server's durable `invitation_welcome_pending` state.
- Distinguish individual sponsored allowance from the independent, cumulative global inference ceiling. Report exact pre-dispatch shortfall and expose aggregate remaining capacity without revealing other users' activity.
- Reject a second claim against a running cloud job; only unclaimed queued jobs are eligible for dispatch.
- Recover a queued session with a stale running/stopping ledger slot under the exclusive worker lock. Pause it and preserve saved events/artifacts rather than duplicating a provider attempt or waiting indefinitely.
- On a cloud hard-budget call, reserve each token allocation once and release it once; retain independent global/per-user spend reservations.
- Preflight funding on resume before requeueing a saved session, preserving saved playback when funds are unavailable.
- Cover completed fake-provider Investigator/Skeptic execution, exact spend-cap denial, and restart recovery with deterministic regression cases.

## Functional acceptance remaining

The hosted production application's configured inference provider, actual global spending ceiling, and live provider-call availability have not been verified. No change to production spending limits or paid-provider credentials is included here.

After deploying a testable build with authorized funding, the owner should sign in, open an existing project, execute an Investigator/Skeptic pair, reload the page, and inspect its persisted session history, events, saved artifacts, cost state, and replay. Repeat with a second eligible user and with an exhausted-global-funding state. Keep the PR draft until those paths work as intended.

Do not split related fixes into separate PRs.
