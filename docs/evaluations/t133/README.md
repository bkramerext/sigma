# T133 cloud desktop workflow and export acceptance preparation

## Coverage audit

The hosted acceptance remains **UNVERIFIED**. Existing local deterministic
coverage is substantial and should be run before the hosted pass:

| Surface | Existing evidence/check | Limit |
| --- | --- | --- |
| Packaged desktop Chrome; project copy/edit/recent/reopen | `deploy/validate-local.sh` runs `browser_checks/t91_packaged_compose.py` against the packaged Compose stack | Two simulated Google identities; not the hosted deployment or OAuth |
| Strategy edits; session and Outcome; saved artifacts | T91 packaged workflow and `browser_checks/t17_8_saved_session.py` | T91 reads deterministic sample research; T17.8 projects archived saved records |
| Outcome Markdown rendering | `browser_checks/t17_8_saved_session.py`; added explicit rendered Outcome assertion to T91 | Does not call hosted text-conversion or model services |
| Project Audit, text, and HTML report downloads | T91 exercises all three through the real packaged UI; report unit/API coverage is in `tests/` | Local packaged app only |
| TeX/PDF creation, validation, and persistence | T91 compiles deterministic TeX with packaged Tectonic, parses the PDF, checks authenticated retrieval and hashes across backend restart/restore; `tests/papers.py` covers paper service behavior | It seeds a deterministic paper; it does not call a hosted paper-generation provider |
| Saved state through reload, backend restart, restore | T91 checks UI reload/reopen, backend container recreation and fresh-volume restore; T100 checks persistent-disk browser reload and backend process restart | Local fixtures and storage, not GCE disk/systemd recovery |

Do not add another browser suite for these already-covered paths. The T91
packaged browser regression now explicitly checks the Outcome Markdown toggle
and downloads Project Audit, text, and HTML reports from the UI. Focused paper
dialog/download links and artifact persistence are also covered by T45 and
T91.2. See [the status record](../../STATUS.md) and
[the desktop cloud operating steps](../../OPERATION_RUNBOOK.md).

## Repeatable hosted acceptance procedure

Run only after T127/T129/T131/T132 dependencies are ready and the coordinator
provides the approved host/release and two authorized test identities. Use an
isolated desktop Chrome profile and the live HTTPS origin. Record UTC start/end,
Chrome version, host and deployed SHA, test identity labels (redacted), and
each result as PASS/FAIL/BLOCKED. Do not include cookies, tokens, email
addresses, project contents, or unredacted screenshots in the handoff.

1. Confirm the operator runbook's mount, preflight, service, HTTPS/API health,
   backup recovery point, and monitoring checks. Record the release SHA. Stop
   if storage is not mounted or preflight/health fails.
2. Sign in as authorized identity A. Open a stock sample as a copy or create a
   disposable acceptance project. Record its project ID. Edit and save its
   title/problem; edit and save a strategy. Return Home, reload Chrome, reopen
   the project from Recent, and confirm the same IDs and edits.
3. Review the project's saved sessions. Open one session and confirm the
   Outcome, its verification/provisional state, provenance, and cited research
   artifacts. Toggle the Outcome Markdown reading view and back; inspect the
   saved text and confirm rendering has not changed the saved record. Do not
   start or resume research as part of this read-only pass.
4. Download Project Audit, text, and HTML reports using the UI. Confirm each
   file opens and contains the acceptance project identity and saved research
   records. Record filenames, sizes, and SHA-256 digests. Treat exports as
   findings, not independent verification.
5. If an existing authorized test paper is available, open it, download its
   TeX and PDF, inspect the TeX source, open the PDF, and record paper/project
   IDs and SHA-256 digests. If no paper exists, paper generation requires
   explicit provider/budget authorization before proceeding; do not make a
   paid call under T133. Report that check BLOCKED when authorization or a
   prepared test paper is unavailable.
6. Close and relaunch Chrome, sign in again as A, reopen the same project, and
   verify strategy, session Outcome, saved artifacts, reports, and paper files
   still match the recorded IDs/digests. After an approved application restart
   window, repeat the same checks and record the new boot/release state. Never
   restart production outside the operator's approved maintenance procedure.
7. Sign in as authorized identity B in a separate profile. Confirm A's project
   is absent from Recent and direct access to A's project/session/paper/export
   is denied without revealing content. Confirm B can still see only B's own
   workspace. Do not create cross-user links or copy private test data.
8. Write the sanitized evidence matrix and any failure, blocker, owner action,
   actual host/release SHA, commands, artifact digests, and elapsed time into
   the T133 acceptance handoff. Keep hosted results distinct from the local
   fixture results above.

| Hosted check | Result | Evidence / note |
| --- | --- | --- |
| HTTPS, release SHA, health, mount/preflight and recovery point | BLOCKED | |
| A: project/strategy save, reload and reopen | BLOCKED | |
| A: saved session, Outcome, Markdown and research artifacts | BLOCKED | |
| A: Audit/text/HTML report downloads | BLOCKED | |
| A: TeX/PDF download and open | BLOCKED | |
| A: browser restart persistence | BLOCKED | |
| A: approved application restart persistence | BLOCKED | |
| B: workspace isolation and denied A-record access | BLOCKED | |
