# PR #297 Green consolidated R4R — adversarial corrections

Repository: `bkramerext/sigma`
Branch: `coordinator/signin-session-playback-stabilization`
Reviewed starting HEAD: `86b6b6ea6889271d50b6d9c69ce9af5a9bbd1724`
Validated correction HEAD: `fecf49f610d0d70ee7963003541891d1f6767cb3`
Reconciled `origin/main` base: `4cff1e544bc30f14096073ee6c7440c45bb5e499`
PR #297 remains open and unmerged; no deployment or paid provider calls.

## Corrections

### Guest workspace identity isolation

Temporary guest workspace tokens are now bound to the first verified Google subject that uses them. A later authenticated request with a different subject cannot resolve that workspace; it receives a fresh guest workspace and cookie. The Google callback copies a guest project only when the cookie's workspace is bound to the callback subject. Signed-out browser continuation remains available, while a different authenticated identity is checked against the binding.

`browser_checks/local_auth_real_backend.py` starts a separate local API process with deterministic Google session fixtures for two uninvited subjects. It retains the same guest cookie while switching the session cookie, proves the original owner can read its project, session, and artifact, then verifies the second subject gets 404 for all three and a replacement guest cookie.

### Guest cache protections

All guest project responses, including authenticated guests, now receive `Cache-Control: no-store`, `Referrer-Policy: no-referrer`, `X-Content-Type-Options: nosniff`, and `Content-Security-Policy: frame-ancestors 'none'`. API and real-Chrome checks assert these headers for project, saved-session, paper, and research-artifact reads.

### Authorization handler audit

Server-side default denial remains in place. The test inventory asserts the exact registered method/path allowlist. Direct HTTP tests exercise the real guest handlers for samples, project inspect/open/close, strategies, events, limits, current understanding, saved sessions, execution records/artifacts, paper metadata/PDF/TXT/TeX, proposal configuration, text inspection, and recents. Test records are owned by the guest workspace. Cross-workspace project/session/artifact/paper requests fail. Project audit, export/download/report, writes, research dispatch, provider-backed routes, and admin routes are denied. Provider discovery and queued dispatch are guarded in tests so safe reads cannot invoke them.

### Monthly spending-window checks

New `tests/cloud_research_windows.py` checks that calendar-month policy excludes old settled (`usage_estimated`) costs, while cumulative policy retains them; old `reserved` and `unknown` provider obligations remain counted across rollover. It verifies an unresolved obligation prevents a reservation that would exceed the global ceiling and that two concurrent $0.06 reservations against a $0.10 global ceiling serialize to exactly one reservation. Existing explicit global and per-user spend admission tests remain passing.

## Main reconciliation and dependency

Fetched `origin/main` at `4cff1e544bc30f14096073ee6c7440c45bb5e499` and reconciled it with the PR branch. Blue #314's context-aware math rendering and the approved About diagram changes from #315 are present and verified by the T301 Chrome check and responsive About Chrome check.

Red's happy-path work is PR #317, currently open and unmerged at lookup time; it is not in current main. Therefore the requested post-Red-merge reconciliation remains **UNMET** until that PR lands and #297 is refreshed against the resulting main.

The published PR branch already contains history beyond its original remote HEAD. Repository instructions prohibit force pushes. To preserve the remote branch and avoid overwriting concurrent work, current main was integrated with a merge commit rather than rewriting published history with rebase. The requested rebase is therefore **UNMET**; the branch is based on current main without force-pushing.

## Verification

`./sigma test` — PASS, all steps on correction HEAD `fecf49f610d0d70ee7963003541891d1f6767cb3`. This includes 71 `tests/cloud_auth.py` cases, `tests/cloud_research_windows.py`, cloud research and deterministic sponsored API calls, Ruff check/format, Pyright, frontend typecheck, and production build. One existing graph-present sandbox scenario remains skipped because the local Python sandbox image is unavailable; the graph-withheld branch passes. Frontend dependencies were installed with `npm --prefix frontend ci` from the lockfile after the first run found the newly declared `remark-gfm` package absent locally.

Real Chromium checks — PASS against the updated tree:

- `browser_checks/local_auth_real_backend.py`: two-identity cookie switch, workspace/project/session/artifact isolation, guest cache headers, plus prior auth/membership/invitation coverage.
- `browser_checks/guest_samples.py`: public guest sample flow.
- `browser_checks/issue279_invite_me.py`: invitation request, retry/reload, member behavior.
- `browser_checks/local_admin_sponsor_pill.py`: admin/member sponsorship behavior.
- `browser_checks/t17_8_saved_session.py`: saved session playback, no provider calls.
- `browser_checks/about_dialog_acceptance.py`: About diagram behavior at 1440/390/320 and touch help at 390.
- `browser_checks/t301_markdown_math.py`: Blue #314 math rendering and semantic preservation.

`git diff --check` — PASS for PR changes. No paid provider calls. Automated OAuth and sponsored responses use deterministic fixtures.

## Acceptance matrix

| Criterion | State | Evidence |
|---|---|---|
| Guest cookie cannot be reused across verified Google identities | MET (automated + real backend Chrome) | Two identity switch retains cookie then proves project/session/artifact denial and cookie rotation |
| Authenticated guest project/artifact responses are non-cacheable | MET | API tests and browser response-header assertions |
| Actual handlers behind guest allowlist are ownership-scoped | MET | Owned project/session/paper/artifact reads plus other-identity 404s; exact route inventory |
| Guests cannot export, mutate member data, dispatch research, call providers, or access admin operations | MET (automated) | Direct HTTP route inventory and handler/provider guards |
| Monthly rollover preserves unsettled obligations and respects global ceiling | MET (automated) | Rollover, cumulative policy, unknown/reserved and concurrent reservation tests |
| Blue #314 and approved About diagram changes remain intact | MET (automated + Chrome) | Full suite; T301 math and About diagram Chrome checks |
| Reconcile after Red PR #317 merges | UNMET | #317 was still open/unmerged; latest available main is `4cff1e5` |
| Rebase published PR branch on main | UNMET | Used non-rewriting merge to preserve remote history under the repo's no-force-push rule |
| Live Google sign-in → invitation → approval → member → Easy sponsored session as N | UNVERIFIED (human acceptance gate) | Not run; no live Google or paid provider call |

Keep PR #297 open and unmerged. Do not deploy. After Red #317 merges, fetch that new main and re-run the affected full suite and browser checks before another review handoff.
