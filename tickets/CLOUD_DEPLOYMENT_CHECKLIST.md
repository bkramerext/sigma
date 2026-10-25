# SIGMA Cloud Deployment Checklist

[Cloud master issue #98](https://github.com/bkramerext/sigma/issues/98) · [Operations Runbook](../docs/OPERATION_RUNBOOK.md) · desktop-only deployment acceptance.

**Owner legend:** 👤 Brian (GCP console, authorization, credentials and final launch); 🔴 Red Codex (hosting/backend); ⚪ Gray Codex (backup/operations); 🟢 Green Codex (desktop-browser acceptance); 🔵 Blue Codex (research dependency only, otherwise on iteration sequence); **Coordinator** = ChatGPT (PR review, integration and acceptance).

| Ticket | Deliverable | Responsible owner | Status |
|---|---|---|---|
| [T126](t126.md) | GCP project, trial, access | 👤 Brian + Coordinator | In progress |
| [T127](t127.md) | VM, dedicated disk, static IP, network/IAM | 👤 **Brian** (console actions); 🔴 Red technical guidance | **Next** |
| [T128](t128.md) | Host bootstrap, rootless Docker and preflight | 🔴 Red | Blocked by T127 |
| [T129](t129.md) | Compose app, health and durable state | 🔴 Red | Offline implementation in [PR #152](https://github.com/bkramerext/sigma/pull/152); hosted acceptance pending Brian's T127 handoff |
| [T130](t130.md) | DuckDNS and HTTPS | 🔴 Red; 👤 Brian DNS account changes | Blocked by T127/T129 |
| [T131](t131.md) | Hosted Google OAuth, sign-in | 🔴 Red backend + ⚪ Gray preparation; 👤 Brian OAuth console/secret | **Closed: T131/PR156 and T131/PR158 merged; live OAuth acceptance deferred (unverified)** |
| [T132](t132.md) | Hosted inference, sessions, Python/Sage | ⚪ Gray preparation; 🔴 Red integration; 👤 Brian live access/authorization | **Closed: T132/PR157 merged; hosted research and rootless acceptance deferred (unverified)** |
| [T133](t133.md) | Desktop projects, Outcomes, reports, TeX/PDF | 🟢 Green + ⚪ Gray preparation | T133/PR153 offline preparation integrated; hosted checks remain pending T131/T132 |
| [T134](t134.md) | Two-account workspace/privacy acceptance | ⚪ Gray + 🟢 Green; 👤 Brian test account | **Closed: T134/PR148 merged; hosted A/B test deferred (unverified)** |
| [T135](t135.md) | Backup policy and verified restore | ⚪ Gray | **Closed: T135/PR142 merged; live backup/restore deferred (unverified)** |
| [T136](t136.md) | Monitoring, restart, reboot, rollback | ⚪ Gray + 🔴 Red | **Closed: T136/PR144 merged; live recovery/rollback deferred (unverified)** |
| [T137](t137.md) | Launch go/no-go | Coordinator + 👤 Brian | Blocked by hosted acceptance |

These are repository tickets in the existing T sequence, not GitHub issue numbers. **Codex workers cannot relax acceptance requirements or mark blocked steps complete without observed evidence.** Owner action must be distinguished from worker implementation. Update statuses and evidence as tasks complete. Mobile-specific acceptance is out of scope.

**Owner decision (2026-10-25):** T131, T132 and T134–T136 were closed after offline implementation/preparation. All live GCE, OAuth and provider-backed verification is explicitly deferred to a separate coordinated acceptance effort, not passed. Before public launch, T137 must reassess these risks and record an explicit go/no-go decision; closure alone is not acceptance.
