# A18 follow-up — Attribute concurrent research preflight failures

Status: **implemented and verified offline**.

## Problem

When a local portfolio worker prepares several strategy branches in one wave,
provider preflight can fail for one branch before a durable model-call step is
created. The session may retain the branch reason and a general session event,
but the event stream does not identify the affected strategy, role, preflight
stage, or whether dispatch occurred. If another branch in that wave succeeds,
the audit requires correlating step rows and mutable branch state to understand
the mixed result.

## Scope

Add a durable, typed `call.preflight_failed` event for branch-local failures
before provider dispatch. Include strategy ID/title, role, failure stage, a safe
failure kind, and `dispatched: false`. Do not persist raw exceptions, provider
payloads, or credential material. Cover context assembly, project snapshot and
binding checks, account verification/binding, and model configuration checks.

Keep worker scheduling, shared budgets, provider dispatch, retry behavior,
session/branch terminal policy, and user pause/resume behavior unchanged.

## Acceptance

- A failed branch in a mixed concurrent wave has an audit event naming its
  strategy and role; successful sibling calls retain their own completed step
  records.
- A preflight failure records zero calls for that branch and explicitly states
  that provider dispatch did not occur.
- Configuration timeout still pauses with zero calls and can resume; ordinary
  preflight errors retain the existing terminal/paused behavior.
- The event contains no raw exception text, request content, or credential.
- Existing offline research-session tests pass. No live provider calls are
  permitted or required.
