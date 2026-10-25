# SIGMA Cloud Deployment Ticket Index

Source of truth for implementation steps under [Cloud master issue #98](https://github.com/bkramerext/sigma/issues/98). These are **repository tickets**, separate from GitHub issues. Check the linked tickets for evidence and requirements. See [Operations Runbook](../docs/OPERATION_RUNBOOK.md) for recurring actions. **Desktop-only release acceptance; mobile testing is out of scope.**

| Step | Ticket | Lead | Status |
|---|---|---|---|
| 1 | [GCP project/access](cloud-01-gcp-access.md) | Coordinator | In progress (project confirmation outstanding) |
| 2 | [VM, disk, static IP](cloud-02-compute.md) | Red | Pending hosted acceptance |
| 3 | [Host/rootless sandbox](cloud-03-host.md) | Red | Pending hosted acceptance |
| 4 | [Compose deployment/state](cloud-04-app.md) | Red | Pending hosted acceptance |
| 5 | [DuckDNS/HTTPS](cloud-05-public.md) | Red | Pending hosted acceptance |
| 6 | [Production Google OAuth](cloud-06-oauth.md) | Red/Green | Pending hosted acceptance |
| 7 | [Research/Python/Sage parity](cloud-07-research.md) | Red/Blue | Pending hosted acceptance |
| 8 | [Desktop reports/TeX/PDF](cloud-08-exports.md) | Green/Gray | Pending hosted acceptance |
| 9 | [Real two-user isolation](cloud-09-isolation.md) | Gray/Green | Pending hosted acceptance |
| 10 | [Snapshot/restore drill](cloud-10-backup.md) | Gray | Pending hosted acceptance |
| 11 | [Monitoring/reboot/rollback](cloud-11-operations.md) | Gray/Red | Pending hosted acceptance |
| 12 | [Hosted go/no-go](cloud-12-release.md) | Coordinator | Pending hosted acceptance |

Status must be updated with observed evidence as work completes. Code merged locally does not imply live GCE acceptance. Coordinator owns any scope/acceptance change and final go/no-go. Existing GitHub tickets #88/#99/#66 and #98 remain authoritative for their broader requirements.
