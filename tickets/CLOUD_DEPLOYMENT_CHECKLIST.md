# SIGMA Cloud Deployment Checklist

[Cloud master issue #98](https://github.com/bkramerext/sigma/issues/98) · [Operations Runbook](../docs/OPERATION_RUNBOOK.md) · desktop-only deployment acceptance.

**Owner legend:** 👤 Brian (GCP console, authorization, credentials and final launch); 🔴 Red Codex (hosting/backend); ⚪ Gray Codex (backup/operations); 🟢 Green Codex (desktop-browser acceptance); 🔵 Blue Codex (research dependency only, otherwise on iteration sequence); **Coordinator** = ChatGPT (PR review, integration and acceptance).

| Ticket | Deliverable | Responsible owner | Status |
|---|---|---|---|
| [T126](t126.md) | GCP project, trial, access | 👤 Brian + Coordinator | In progress |
| [T127](t127.md) | VM, dedicated disk, static IP, network/IAM | 👤 **Brian** (console actions); 🔴 Red technical guidance | **Next** |
| [T128](t128.md) | Host bootstrap, rootless Docker and preflight | 🔴 Red | Blocked by T127 |
| [T129](t129.md) | Compose app, health and durable state | 🔴 Red | Blocked by T128 |
| [T130](t130.md) | DuckDNS and HTTPS | 🔴 Red; 👤 Brian DNS account changes | Blocked by T127/T129 |
| [T131](t131.md) | Hosted Google OAuth, sign-in | 🔴 Red backend + 🟢 Green browser; 👤 Brian OAuth console/secret | Blocked by T129/T130 |
| [T132](t132.md) | Hosted inference, sessions, Python/Sage | 🔴 Red; 🔵 Blue only for specific research blocker; 👤 Brian live access/authorization | Blocked by hosted app |
| [T133](t133.md) | Desktop projects, Outcomes, reports, TeX/PDF | 🟢 Green | Blocked by T131/T132 |
| [T134](t134.md) | Two-account workspace/privacy acceptance | ⚪ Gray + 🟢 Green; 👤 Brian test account | Blocked by T131 |
| [T135](t135.md) | Backup policy and verified restore | ⚪ **Gray** | **[Offline preparation PR #142](https://github.com/bkramerext/sigma/pull/142); hosted acceptance after T127/T129 and owner-approved backup IAM** |
| [T136](t136.md) | Monitoring, restart, reboot, rollback | ⚪ Gray + 🔴 Red | Blocked by T129/T135 |
| [T137](t137.md) | Launch go/no-go | Coordinator + 👤 Brian | Blocked by hosted acceptance |

These are repository tickets in the existing T sequence, not GitHub issue numbers. **Codex workers cannot relax acceptance requirements or mark blocked steps complete without observed evidence.** Owner action must be distinguished from worker implementation. Update statuses and evidence as tasks complete. Mobile-specific acceptance is out of scope.
