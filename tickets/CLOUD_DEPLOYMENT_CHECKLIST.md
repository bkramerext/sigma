# SIGMA Cloud Deployment Ticket Index

Source of truth for implementation steps under [Cloud master issue #98](https://github.com/bkramerext/sigma/issues/98). Numbered **T126–T137** in SIGMA's existing T sequence. These are **repository tickets**, separate from GitHub issues. Check the linked tickets for evidence and requirements. See [Operations Runbook](../docs/OPERATION_RUNBOOK.md) for recurring actions. **Desktop-only release acceptance; mobile testing is out of scope.**

| Step | Ticket | Lead | Status |
|---|---|---|---|
| 1 | [GCP project/access](t126.md) | Coordinator | In progress (project confirmation outstanding) |
| 2 | [VM, disk, static IP](t127.md) | Red | Pending hosted acceptance |
| 3 | [Host/rootless sandbox](t128.md) | Red | Pending hosted acceptance |
| 4 | [Compose deployment/state](t129.md) | Red | Pending hosted acceptance |
| 5 | [DuckDNS/HTTPS](t130.md) | Red | Pending hosted acceptance |
| 6 | [Production Google OAuth](t131.md) | Red/Green | Pending hosted acceptance |
| 7 | [Research/Python/Sage parity](t132.md) | Red/Blue | Pending hosted acceptance |
| 8 | [Desktop reports/TeX/PDF](t133.md) | Green/Gray | Pending hosted acceptance |
| 9 | [Real two-user isolation](t134.md) | Gray/Green | Pending hosted acceptance |
| 10 | [Snapshot/restore drill](t135.md) | Gray | Pending hosted acceptance |
| 11 | [Monitoring/reboot/rollback](t136.md) | Gray/Red | Pending hosted acceptance |
| 12 | [Hosted go/no-go](t137.md) | Coordinator | Pending hosted acceptance |

Status must be updated with observed evidence as work completes. Code merged locally does not imply live GCE acceptance. Coordinator owns any scope/acceptance change and final go/no-go. Existing GitHub tickets #88/#99/#66 and #98 remain authoritative for their broader requirements.
