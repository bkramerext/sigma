# Strategy parallelization — implementation notes (#421)

**Scope:** independently progressing, serial Investigator → Skeptic pipelines within each strategy. No general scheduler rewrite, report code, frontend project loading, or turn-14 remediation.

## Current architecture (main `48c1fb2`)

- `research_sessions._portfolio_worker` schedules selected branches using `_affordable_portfolio_branches` and a rotating cursor.
- Investigators currently execute in a gather wave, then Skeptics in a second gather wave. A slow Investigator blocks the Skeptic of an unrelated completed Investigator.
- Per-session `asyncio.Semaphore` permits three requests for non-hosted mode; hosted mode permits one to avoid overlapping allowance reservations.
- `_portfolio_role_call` persists step records and call/cost/token reservations under a per-session lock, then releases the lock around provider I/O. In-flight requests already have unique IDs and saved status.
- Saved current turns, pending Investigations, completed artifacts, peer handoffs, stopping reasons, retries, and reservations must remain intact.

## Focused integration boundary

1. Run each selected branch's required role transitions as a **single coroutine**; `investigator` must complete before its corresponding `skeptic`, while other branches progress independently.
2. Remove the cross-branch Investigator→Skeptic barrier; retain deterministic per-branch commits and existing peer-evidence context snapshots at step boundaries.
3. Add bounded provider request admission with tunable concurrency. A provider request slot covers the remote call only, never a session-wide state lock. Maintain conservative hosted funding admission.
4. Test overlap, stalled sibling, I/S ordering, fairness, cancellation, retries, cost reservations, and persisted artifacts, including old sequential behavior.
5. Coordinate general cross-process, per-user fairness and adaptive limits with #419. This PR must not silently claim distributed global guarantees from an in-process semaphore.

## Non-overlapping worker assignments (when available)

- **Execution:** targeted `_portfolio_worker` branch-pipeline change; owns only `src/sigma/research_sessions.py`.
- **Tests:** deterministic fake-provider tests; owns a new isolated test module.
- **Adversarial review:** inspect funding reservation, stop/resume, double dispatch, peer handoff, and provider-limit paths; report findings without editing main code.

No merge or deployment without approval.