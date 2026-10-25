# T134 hosted two-identity privacy acceptance

**State:** Preparation only. Run against the deployed hosted application only after T131 and the application deployment are ready. Offline fixtures are not hosted acceptance.

## Preconditions

- Record the public origin, deployed release SHA, UTC start time, tester, and approved test window.
- Confirm T131 Google sign-in and the target deployment are ready. Use two distinct, owner-authorized Google identities (A and B); include one admin and one member when those roles are available. Never substitute the same Google subject with two email aliases. Do not use production user data.
- Use clean, separate desktop browser profiles. Do not copy session cookies between profiles. Sign in as A only in profile A and B only in profile B.
- Agree on disposable test project titles and unique marker strings. Keep identity emails, tokens, cookies, project content, and private response bodies out of tickets, PRs, screenshots, and logs. Record only redacted IDs or short hashes.
- Provider-backed research or paper generation is not part of this procedure unless separately authorized. Without that authorization, verify existing usage views and rejected requests only; record paid/provider usage as UNVERIFIED.

## Procedure and evidence matrix

For each row record **A result**, **B result**, expected result, observed status, and a sanitized evidence reference. A denied response must not include the other identity's title, problem, strategy text, session/artifact content, paper metadata, or file bytes.

| Area | Hosted action | Required result |
|---|---|---|
| Identity and initial state | Sign in A and B in separate profiles; record role and redacted stable identity reference. Open Recent in both. | Distinct identities and independently empty/private Recent lists. No cookie or client-supplied identity header can switch the server principal. |
| Projects and strategies | Each identity creates a project with a unique marker and a strategy. Open each project's details and strategy list. | A sees A only; B sees B only. A strategy and project IDs from B do not grant access. |
| Direct API references | While authenticated as A, request B's project by direct path/ID for inspect, open, strategies, events, text, export/report, sessions, executions, artifacts, and papers. Repeat representative requests in B against A. Try a normalized traversal and a symlink reference if a safe disposable hosted fixture can be made. | Private resource requests return the application's indistinguishable not-found/denied result (currently 404); unauthenticated requests return 401. No private fields or bytes are present. Do not test traversal by writing outside test data. |
| Research sessions | With separately authorized bounded inference, create one session for each user and capture each session ID. As the other user, request session list, status, controls, interventions, deletion, and any session artifact through a direct API reference. Without provider authorization, use only existing saved sessions and keep creation UNVERIFIED. | Owner can read/control their own session; other identity gets denied/not-found with no session or step data. Denied operations do not stop, alter, or delete the owner's session. |
| Artifacts and downloads | Each user saves or obtains a deterministic disposable artifact through approved application features. Attempt other user's artifact download by direct project path, execution ID, artifact name, and paper PDF URL. | Owner receives byte-for-byte expected content; other user receives denied/not-found and no bytes. Rejected download does not change owner data. |
| Papers | If already saved fixture papers exist, list/read/download TeX/PDF per owner. Do not invoke generation without separate provider authorization. Try the other user's paper ID and path. | Paper records and downloads remain owner-scoped; denied response contains no paper metadata or file data. |
| Recent Projects | Refresh, reopen, and forget one of A's projects; request the other user's project ID directly through Recent endpoints. Repeat in B. | Each Recent list tracks only that principal. A's attempted forget of B's ID cannot remove or reveal B's entry. |
| Usage accounting | Record each owner's displayed/API budget counters before and after the procedure. Try a request as A containing B's direct project/session reference; inspect counters for both identities. If bounded sponsored usage is separately authorized, record the approved call ID and counters before/after one run per identity. | Rejected access creates no job, reservation, charge, counter change, or state mutation for either identity. Any authorized usage is attributed only to its owner; global totals reconcile with owner totals. Unknown provider outcomes remain reserved/unknown and are never replayed or cleared. |
| Sign-out and account switch | Sign out A and verify the old browser session cannot access protected APIs. In that browser profile sign in as B; then sign out and sign back in as A. Repeat in the other profile if practical. | Logout invalidates the prior session. Every transition loads only the new principal's projects, Recent, sessions, artifacts, papers, and budget. No stale UI cache or old API credential reveals the prior account's data. |
| Persistence | Reload both profiles, then perform an approved service restart/recovery check only as part of its own authorized operation. Reopen saved projects and compare redacted IDs/hashes and owner usage against baselines. | Stable Google subject maps back to the same private workspace. A/B workspace mapping, saved content, and accounting remain intact and separate. |

For every denied write (including strategy mutation/removal, session control/deletion, Recent forget, and download attempts), capture owner state before and after: project revision or sanitized project hash, strategy IDs, session status, artifact/paper hashes, Recent IDs, and budget counters. Require exact equality unless an explicitly authorized owner action explains the change. Never use database edits to manufacture expected counters.

## Completion record

```text
Ticket: T134
Outcome: MET / UNMET / UNVERIFIED (preparation is not acceptance)
Host/origin:
Deployed release SHA:
UTC start/end; elapsed:
Tester:
Identity A/B: authorized roles and redacted stable references:
Browser profiles / desktop browser version:
Rows completed and sanitized evidence links:
Denied API routes/statuses and disclosure check:
Before/after owner-state and usage comparison:
Provider calls/costs (authorization reference, or none):
Failures, deviations, owner actions, hosted dependencies:
```

Do not mark T134 accepted until the actual hosted A/B matrix is complete and reviewed. Required hosted dependencies include T131 sign-in and a deployed application; provider-backed session/usage checks additionally require separate provider-call authorization. Preserve remaining gaps as UNVERIFIED.
