# Cloud 06-oauth: Production OAuth and access controls

**Owner:** Red / owner OAuth; Green acceptance
**Status:** Pending; evidence must come from real deployment unless stated otherwise.
**Depends on:** 04,05
**Master:** [GitHub #98](https://github.com/bkramerext/sigma/issues/98)

## Work
Configure production Google Web client origin and callback; store secret privately; verify hosted sign-in/sign-out, authorized/denied roles and callback, no LOCAL fallback; two real Google identities for cross-user checks.

## Acceptance
Live desktop OAuth acceptance with authenticated user and denied identity, validated session handling; unresolved test-account availability explicitly reported.

## Handoff
Record actual host/release SHA, commands/tests and observed results, failed/blocked checks, owner actions, elapsed time, and links to PR or acceptance evidence. Do not self-merge or weaken coordinator-owned acceptance criteria. Distinguish local/mocked checks from real hosted evidence.
