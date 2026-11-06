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

The output-capacity failure now becomes an explicit labeled section fallback without a repeat request. When a previous run ended during section writing or retry, Continue marks all unsaved sections as interrupted gaps before dispatch; completed sections are reused and the provider-call count does not increase. This conservative rule avoids replaying an ambiguous paid call when concurrent dispatch history is incomplete. Cancellation replaces stale retry detail with a terminal explanation. On a copy of the original checkpoint, the six-section draft assembled with saved sections `1,2,4,5,6`, one labeled section-3 gap, and unchanged 23-call count. This is an actionable incomplete paper, not a claim that section 3 was authored successfully.

## Verification and release gate

Focused deterministic checks cover control-byte PDF compilation, output-capacity fallback, interrupted-section recovery with a provider-call guard, and truthful cancelled progress. The original Maximum Regions source compiled offline to an 11-page PDF after the marker repair. Full `./sigma test` passed, including Python checks, frontend typecheck and build, after installing frontend dependencies. Real Chrome against isolated copies of the original project directories fetched the new Maximum Regions PDF (HTTP 200, `application/pdf`, valid `%PDF-` header), confirmed the saved paper count after refresh, and confirmed Sovereign shows a terminal stopped state after refresh with no stale retry detail. No provider calls were made.

Re-sign-in acceptance on the updated code, live Sovereign PDF publication/scoring, and human correction of the marked math remain **UNVERIFIED**. No paid provider calls were initiated during this investigation. Neither original project was modified. The deployment gate remains closed pending these checks, CI, and coordinator review.

## Research and authoring lessons

Research ingestion should detect nonprinting control characters before they enter a claim or section draft, preserve the exact source, and surface a review marker. A mathematical control byte cannot be interpreted safely by TeX cleanup. Long-running research and authoring stages should durably distinguish provider calls that were prepared, dispatched, and completed; a progress label alone cannot establish whether a paid call may be replayed after interruption. Finally, output-size limits should result in an explicit bounded fallback with preserved completed evidence and sections rather than an unbounded-looking retry or loss of the whole job.
