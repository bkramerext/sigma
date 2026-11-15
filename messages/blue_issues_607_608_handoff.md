# Blue handoff: P0 paper failures #607 and #608

## Build and project evidence

The local backend `/api/local-runtime/build` reported running and checkout SHA `f4574f299380b256afb5ed28a1cc75cacd492886` on 2026-11-06. It matches `origin/main` at investigation start. The affected projects are in `/Users/admin/sigma_green/projects/`, not the active checkout's `projects/` folder. Their original bytes were inspected read-only and not modified.

- Maximum Regions Formed by Lines v2: project `01af8ffa-60c3-4eea-bc15-36dca347ddfa`, five saved papers, five saved draft sections. The failed checkpoint retains its frozen snapshot and proofreading attempts.
- Sovereign AI Federation v3: project `95ef7f5c-20cb-4cfd-a295-790a7dccd620`, no published paper, five saved sections out of six (`1,2,4,5,6`), 23 recorded paper provider attempts in the checkpoint and 24 lifetime attempts. The latest progress is `cancelled`; there is no active provider process for this project.

## #607 root cause and fix

Tectonic rejected `report.tex` at line 45 with `Text line contains an invalid character`. The saved section drafts contain U+0002, U+001A and U+001C control bytes inside mathematical expressions. The generated TeX retained those bytes. The AI proofreader rejected a proposed change as a protected content change, then the compile path failed. This is a source-to-TeX robustness defect; scoring never ran for that attempt.

After proofreading, the renderer now converts unreadable control bytes to visible `[U+XXXX]` markers and flags the PDF for review. The exact authored draft and proofreading checkpoint remain intact. This avoids inventing mathematical symbols while producing a readable PDF. On an isolated copy of the original project, with all provider methods guarded against calls and the original claim-details preference, the saved proofreading response was reused; a sixth paper version was published and its PDF was retrieved (valid PDF header, over 72 KB). The original project remains untouched. The mathematics at marked positions still needs human correction before publication.

## #608 root cause and fix

The backend log shows a provider 401 rejection ending an earlier run at 09:06 UTC, a later stream exceeding the 1 MB generated-text cap at 10:02 UTC, and a final run cancelled at 11:20 UTC during a retry of section 3. It was not an infinite retry: code permits three attempts per transient stage, each with up to a 60-minute timeout. The section writer did not classify output-capacity failure as a recoverable section gap; concurrent in-flight siblings could finish, but the job then failed. After cancellation, the old `Retrying section 3` detail remained in stored progress, falsely suggesting ongoing activity.

The output-capacity failure now becomes an explicit labeled section fallback without a repeat request. Each section attempt is durably recorded before dispatch. On Resume, only an unsaved section with a recorded dispatch becomes an interrupted gap; unsent sections still run. This applies equally after cancelled, running, failed, and paused outcomes. Older checkpoints without dispatch records can recover a section explicitly named in a saved retry detail; otherwise an ambiguous old checkpoint stops with an actionable error before another paid call. Cancellation replaces stale retry detail with a terminal explanation. On a copy of the original Sovereign checkpoint, the six-section draft assembled with saved sections `1,2,4,5,6`, one labeled section-3 gap, and unchanged 23-call count. This is an actionable incomplete paper, not a claim that section 3 was authored successfully.

Adversarial review of PR #614 found that the first implementation filled *all* unsaved sections and omitted failed/paused runs. The per-section dispatch ledger above replaces that implementation. A deterministic concurrency test now confirms that a never-dispatched section is authored on Resume while an uncertain dispatched section is represented as a gap. The old test expecting a second paid call for a failed section was corrected to require no automatic replay. New tests are registered in the split test driver, so `./sigma test` executes them.

## Verification and release gate

Focused deterministic checks cover control-byte PDF compilation, output-capacity fallback, per-section dispatch recovery across four previous statuses, legacy retry migration, unknown legacy dispatch rejection, and truthful cancelled progress. The original Maximum Regions source compiled offline to an 11-page PDF after the marker repair. The complete paper suite passed after the dispatch-record revision. Full `./sigma test` passed on the prior PR head; the revised full run was stopped at the user's request before completion. Real Chrome against isolated copies of the original project directories fetched the new Maximum Regions PDF (HTTP 200, `application/pdf`, valid `%PDF-` header), confirmed the saved paper count after refresh, and confirmed Sovereign shows a terminal stopped state after refresh with no stale retry detail. No provider calls were made. All four CI workflows passed on the prior head; the revised head requires fresh CI.

Re-sign-in acceptance on the updated code, live Sovereign PDF publication/scoring, and human correction of the marked math remain **UNVERIFIED**. No paid provider calls were initiated during this investigation. Neither original project was modified. The deployment gate remains closed pending these checks, CI, and coordinator review.

## Paper authoring lesson

Paper authoring should detect nonprinting control characters before TeX compilation, preserve the exact draft, and surface a review marker; a mathematical control byte cannot be interpreted safely by cleanup. Paper-generation checkpoints should durably distinguish calls that were prepared, dispatched, and completed. A progress label alone cannot establish whether a paid call may be replayed after interruption. Output-size limits should produce an explicit bounded recovery state that retains completed sections and provider-call accounting. These findings do not establish a defect in the separate research workflow.
