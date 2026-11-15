# #743 Track D — final prototype smoke and evidence

This is the **last human-operated release gate** for SIGMA collaboration, not a
substitute for CI. Record the exact main SHA and result of each observation
before closing #743. Never enter account tokens or credentials into evidence.

## Automated evidence that must be green first

- Ruff; all eight SIGMA verification shards; both Browser verification groups.
- `Two-creator real PDF acceptance (no stub/skip)` with
  `SIGMA_REQUIRE_REAL_PAPER_PDF=1`. It compiles actual TeX and asserts that
  both downloaded PDFs are readable, distinct and attributed to their creators.
- `tests/cloud_process_restart.py` (included in the cloud shard): real SIGKILL,
  replacement interpreter, one original project containing active/queued
  Session and Paper checkpoints plus pending Q/A, no replay of uncertain calls.
- `browser_checks/collaboration_local_accounts.py`: two independently
  authenticated **mock** Google principals exercising the original shared
  project via actual HTTP and live Chromium UI, including six simultaneous
  Session/Paper/Q/A activity rows, controls and Home/Project indicators.

None of these tests proves a live Google OAuth sign-in: do not mislabel the
mock-auth fixture as the human prototype smoke.

## Live two-account smoke (no paid inference)

Use two **genuine, separate Google accounts** and isolated browser profiles,
designated N (owner) and Z (collaborator). Use the ordinary running app, not
the test-only `SIGMA_MOCK_AUTH` endpoint. Start from an actual checkout of
the exact candidate `main` SHA; record it below. A test-only sample project
is safer than a valuable project. Keep AI generation disabled; no paid
provider requests are required for identity, ACL, persistence or UI checks.

1. **Original project and admission.** N signs in and creates one new
   project. Before invitation, verify Z cannot find or open it. N invites Z;
   verify that Z opens the **same project ID and original owner project**, not
   a copied `.sigma` project. Preserve the displayed project ID and initial
   owner model/thinking values as evidence.
2. **Two connected browsers.** Keep N and Z in the same project at once.
   N changes a non-sensitive shared field and saves; Z sees the update
   without a forced reload. Z makes a permitted field update; N sees it.
   Confirm the editor is not silently overwritten if the other user edits a
   stale revision. Exercise shared settings, collaborator list and Source
   Materials; check dialog dismissal only occurs when intended.
3. **Activities and ownership.** Check the UI against the deterministic
   six-way browser acceptance report: Session/Paper/Answer rows have creator,
   model, thinking and queued/active state on separate Home and Project hover
   lines. Do **not** start paid generation merely to reproduce the fixture.
   Confirm that live execution controls are creator-only where an existing
   safe mock run is available; test foreign request-ID rejection through the
   automated fixture, not by issuing a paid request.
4. **Reconnect and restart.** Close and reopen Z's browser window and verify
   remembered identity, project access and saved edits. Restart the backend
   while no paid calls are in flight; reopen from both profiles, verify saved
   project identity and that no activity falsely remains running. Actual
   SIGKILL during active/queued provider-free work is the dedicated automated
   subprocess gate above, not an OAuth requirement.
5. **Revocation.** While Z has the project open, N removes Z. Verify Z's
   next read or mutation is rejected; refresh Z's window and verify no
   subsequent access. Verify N's original project, content and creator
   attribution remain intact. Owner-only terminal deletion must not grant
   owner control over another creator's live work.
6. **Existing saved data.** Back up a **pre-collaboration** project first.
   Record hashes of its project metadata, saved Sessions, published Paper
   PDFs/TeX and Q/A answers, plus Source Materials. Open as owner under the
   candidate build and share with Z; verify titles, session history, PDF
   downloads, Q/A text, citations and artifacts. Revoke Z and confirm that
   hashes and byte content of all existing artifacts remain unchanged. Do
   not modify or delete the original backup.

## Required release record

| Field | Result |
|---|---|
| Exact candidate main SHA | UNVERIFIED |
| Two genuine Google accounts (N/Z), separate profiles | UNVERIFIED |
| Same project ID before/after sharing | UNVERIFIED |
| Live updates, stale-edit rejection, Source Materials | UNVERIFIED |
| Reconnect and backend restart | UNVERIFIED |
| Active revocation, stale-tab mutation denied | UNVERIFIED |
| Pre-collaboration saved Sessions, Papers, Q/A and source hashes | UNVERIFIED |
| Final full CI green on identical SHA | UNVERIFIED |
| Evaluator / date / evidence link | UNVERIFIED |

Mark a check **PASS** only after it is observed on the specified SHA. Mark
**FAIL** with a reproducible error when it fails. If the human smoke cannot
be performed, leave it **UNVERIFIED**, and keep #743 open. Do not claim a live
OAuth smoke was performed merely because CI used independently authenticated
mock principals.
