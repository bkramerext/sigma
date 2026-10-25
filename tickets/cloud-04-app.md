# Cloud 04-app: Deploy packaged SIGMA and durable state

**Owner:** Red
**Status:** Pending; evidence must come from real deployment unless stated otherwise.
**Depends on:** 03
**Master:** [GitHub #98](https://github.com/bkramerext/sigma/issues/98)

## Work
Configure protected deploy.env and Secret Manager files; mount auth/workspaces/SQLite/ledger on state disk; deploy reviewed SHA via sigma.service with backend, frontend and Caddy; confirm restart ordering and health.

## Acceptance
Actual deployed SHA, healthy services, filesystem mount proof, persisted project/state after container recreation; no ephemeral state fallback.

## Handoff
Record actual host/release SHA, commands/tests and observed results, failed/blocked checks, owner actions, elapsed time, and links to PR or acceptance evidence. Do not self-merge or weaken coordinator-owned acceptance criteria. Distinguish local/mocked checks from real hosted evidence.
