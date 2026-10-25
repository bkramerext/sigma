# Cloud 10-backup: Automated backup and verified restore

**Owner:** Gray; Red disk support
**Status:** Pending; evidence must come from real deployment unless stated otherwise.
**Depends on:** 04
**Master:** [GitHub #98](https://github.com/bkramerext/sigma/issues/98)

## Work
Implement approved scheduled consistent snapshots/retention; prevent writes for consistent SQLite+project capture; test restore to separate disk/isolated host, validate mapping, projects, paper files and ledger; document recovery limits.

## Acceptance
Successful nonproduction restore evidence, recovery point and retention verified, restore steps in docs/OPERATION_RUNBOOK.md.

## Handoff
Record actual host/release SHA, commands/tests and observed results, failed/blocked checks, owner actions, elapsed time, and links to PR or acceptance evidence. Do not self-merge or weaken coordinator-owned acceptance criteria. Distinguish local/mocked checks from real hosted evidence.
