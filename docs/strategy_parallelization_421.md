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
3. Admit up to **32 provider requests globally** across users, projects, and sessions, with one active role per strategy. Hosted requests may overlap when separately funded by atomic durable reservations. In-process fair admission is owner-grouped; private OS file-lock slots bound multiple backend processes sharing storage. The slot currently also covers preflight and settlement, not just remote I/O.
4. Test overlap, stalled sibling, I/S ordering, fairness, cancellation, retries, cost reservations, and persisted artifacts, including old sequential behavior.
5. Preserve cross-strategy shared knowledge: provider inputs contain a frozen, persisted snapshot of completed peer evidence and explicit handoffs available at each turn boundary. In-flight outputs cannot retroactively alter another prompt. Existing cross-strategy evidence and handoff regression tests remain part of acceptance. Cross-host coordination, provider-specific throttling, and adaptive limits remain #419.

## Integration ownership

One implementer owns the backend scheduler, reservation/safety tests, UI status, and integration in this branch. No parallel Codex workers or conflicting edits. Regression tests cover fanout, turn ordering, fair admission, duplicated dispatch, cancellation, peer evidence, and handoffs.

No merge or deployment without approval.
## Open validation and architectural limitations

- The dispatcher remains session-worker driven rather than a centralized persisted ready-turn queue. This is intentional scope control but allows coordinator synchronization at round boundaries; full cross-round dynamic dispatch is not yet provided.
- File-lock global capacity is enforced only for backend processes sharing the same private storage directory. It is not a multi-host distributed lease service. The default value is 32 and the environment override is bounded to 32; some lower operational ceilings may be configured.
- Existing per-project session admission and sponsored per-workspace budgets remain independently enforced; extra strategy parallelism is allowed only when reservations fit.
- Full test suite and browser acceptance must pass on the final commit before review-ready status.
