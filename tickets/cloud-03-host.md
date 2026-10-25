# Cloud 03-host: Harden GCE host and research sandbox

**Owner:** Red
**Status:** Pending; evidence must come from real deployment unless stated otherwise.
**Depends on:** 02
**Master:** [GitHub #98](https://github.com/bkramerext/sigma/issues/98)

## Work
Run existing installer and read-only preflight on actual Ubuntu host; install separate rootless sigma-sandbox daemon; build Python/Sage runner images; verify no rootful socket, network, secrets or state-disk access from jobs.

## Acceptance
Production preflight PASS; rootless runtime proof on host; reproducible host logs, without exposed secrets.

## Handoff
Record actual host/release SHA, commands/tests and observed results, failed/blocked checks, owner actions, elapsed time, and links to PR or acceptance evidence. Do not self-merge or weaken coordinator-owned acceptance criteria. Distinguish local/mocked checks from real hosted evidence.
