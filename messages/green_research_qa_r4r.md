# R4R — Research Q/A review corrections

## Delivery

- Branch: `green/research-qa`
- PR: [#398](https://github.com/bkramerext/sigma/pull/398), existing PR, open and unmerged
- Review base/head: `cefef4115308d05eea57fe59a91b06347f93041d`
- Review-correction SHA: `592ebd684b542fc9280ea518c43b6823bbbbd90a`
- Merge/deploy: not performed
- Provider cost: no paid provider calls; browser checks used a deterministic local fixture

## Corrections delivered

- Failed and interrupted requests retain a per-project recovery marker across dialog closure. Reopening Q/A restores the question and request ID. Recovery checks the saved archive before allowing an explicitly confirmed fresh request, and explains that it may incur another charge.
- Archive read/modify/write operations share a short project write transaction. Provider inference runs outside the filesystem lock; the final save rereads the archive so concurrent deletes and answer writes are preserved.
- Detached request tasks clean their own registry entries after either success or failure, while same-request in-flight deduplication remains active.
- API adversarial coverage checks unauthenticated and cross-user list/get/delete/browser/generation, traversal and symlink paths, forged project and connection identifiers, invalid IDs, oversized questions, workspace isolation, and zero provider calls for denied requests.
- Artifact navigation now enables Advanced Outcome, expands the evidence section, opens and scrolls the exact cited artifact, and highlights it. Session links scroll the session heading into view. Current Understanding navigation is also covered.
- A subprocess restart test verifies persisted answers can be read after a real process restart. Malformed imported Q/A records fail safely.

## Tests actually run

- `uv run --locked --no-sync ruff check src/sigma/api.py src/sigma/research_qa.py src/sigma/tooling.py tests/research_qa.py tests/research_qa_security.py browser_checks/research_qa.py browser_checks/provider_fixture.py` — passed.
- `uv run --locked --no-sync pyright` — passed, 0 errors, warnings, or information.
- `npm --prefix frontend run typecheck` — passed.
- `npm --prefix frontend run build` — passed; Vite reported its existing >500 kB chunk advisory.
- `./sigma test` — passed all configured steps. The optional graph-present local sandbox check was skipped because its configured Python sandbox image is unavailable. New registered Q/A functional and security tests passed, including archive concurrency, interrupted/failure/restart paths, subprocess restart durability, malformed import, and API authorization cases.
- `uv run --with playwright python browser_checks/research_qa.py` — passed in real Chrome against the local deterministic provider fixture: close/reopen recovery, interrupted and failed/restarted request flows, session-heading scroll, artifact and Current Understanding deep links, standalone browser view, desktop/mobile layout, clipboard success/failure, removal, and no new research session.
- `uv run --with playwright python browser_checks/saved_paper_library.py` — passed in real Chrome: TeX human-readable clipboard success/failure, preserved TeX/PDF actions, inline PDF browser view, mobile layout, and confirmed removal.

No live paid provider call was made.

## Screenshots and browser observations

- [Standalone desktop](../docs/evaluations/research_qa/research-qa-browser-desktop.png)
- [Standalone mobile](../docs/evaluations/research_qa/research-qa-browser-mobile.png)
- [Q/A dialog mobile](../docs/evaluations/research_qa/research-qa-mobile.png)

Chrome confirmed the artifact citation opens Advanced Outcome and its evidence subsection, then scrolls the target artifact into view with a temporary highlight. The historical session link brings its heading into view with a temporary highlight. Current Understanding opens and highlights the correct section. The standalone page remained within the mobile viewport width.

## Acceptance status

- **MET** — explicit interrupted/failed request recovery, saved-answer check, charge confirmation, deterministic in-flight deduplication and cleanup.
- **MET** — concurrent archive delete/generation preservation, restart persistence, malformed import rejection, user/project isolation and adversarial API security coverage.
- **MET** — session, artifact, and Current Understanding citation navigation; browser rendering; Q/A/TeX clipboard behavior; no research mutation; responsive Chrome acceptance.
- **MET** — Ruff, Pyright, frontend checks, `./sigma test`, and affected real-Chrome checks.
- **UNMET** — none identified in the requested review corrections.
- **UNVERIFIED** — live external provider behavior and paid request cancellation behavior were not exercised, as requested. The local sandbox image was unavailable for the optional graph-present test.

No merge or deployment was performed. PR #395/Blue changes were not included.

## Second review correction addendum

- Recovery `refresh()` now reports failure distinctly from a valid empty archive. `checkRecovery()` and `startOver()` both stop and retract stale confirmation when the saved-answer read fails; no new provider request is sent until a successful read.
- Failed/interrupted request markers do not consume the 50 completed-answer slots. Exact unresolved request IDs are retained and bounded by the established 30 MB archive limit; at the limit, writes fail closed without replacing saved data. There is no separate 1,000-entry cutoff.
- Regression coverage proves archive read errors in both UI recovery actions result in no additional deterministic provider call; many older pending markers do not block a new completed answer; storage-limit failure preserves the archive and makes no provider call.
- Review correction implementation commit: `c426ac47`.

Checks for this correction: focused `tests/research_qa.py` and `tests/research_qa_security.py`, Ruff, Pyright (0 errors/warnings), frontend typecheck/build, full `./sigma test`, and `browser_checks/research_qa.py` in real Chrome all passed. Chrome verified archive failure recovery in both check and restart actions without a repeated fixture call. `./sigma test` skipped only the optional graph-present sandbox check because the local image is unavailable. No paid provider calls were made.

## Presentation and citation navigation update

- Presentation/citation implementation commit: `fc250801` (`Improve Research Q/A citations and Markdown views`).
- The Answer heading now has the Markdown Copy control immediately beside it. The top-level actions expose Markdown source and Open in browser. Both use the server's single Markdown document; the browser renders it with SIGMA's existing safe Markdown/math renderer.
- Rendered Markdown navigation is restricted to the exact, server-generated URLs in the saved record's validated citations. Model-generated HTML remains inert, and model output cannot create arbitrary same-project navigation targets.
- Source labels and reveal routes now distinguish Project, Strategy, Session, Artifact, and Current Understanding. Missing or removed targets retain their source identity and a navigation-unavailable explanation. Browser acceptance verifies the project section, active strategy, historical session, exact artifact, and Current Understanding routes.
- The dialog displays a short **Research version** fingerprint with the requested tooltip. Technical details expand to the full SHA-256 and a copy control. The Q/A project action height now matches TeX and Lean.
- `browser_checks/research_qa.py` was rerun in real Chrome with the deterministic fixture. It passed source/raw Markdown equivalence, formatted headings/lists/math, hostile HTML and forged-link handling, all five citation types, Research version display/copy, recovery/archive behavior, clipboard success/failure, desktop/mobile layout, and no new research session. Screenshots: [Markdown source](../docs/evaluations/research_qa/research-qa-markdown-source.png), [browser desktop](../docs/evaluations/research_qa/research-qa-browser-desktop.png), [browser mobile](../docs/evaluations/research_qa/research-qa-browser-mobile.png), and [dialog mobile](../docs/evaluations/research_qa/research-qa-mobile.png).
- `browser_checks/t125_saved_paper_library.py` passed in real Chrome for saved TeX downloads, PDF browser view, safe preview, mobile layout, and removal. Its confirmation selector was corrected to match the existing **Confirm** button label; no TeX UI behavior changed.
- Focused Q/A functional/security tests, Ruff, Pyright, frontend typecheck/build, `./sigma test`, Q/A Chrome, and saved-paper Chrome passed. `./sigma test` skipped only the optional graph-present sandbox test because its local image is unavailable. No paid provider calls, merge, or deployment.

### Acceptance status

- **MET** — Markdown copy/source/browser equivalence, safe citation URL allowlist, type-aware links and labels, Research version UI, Q/A/TeX regression coverage, responsive Chrome checks.
- **UNMET** — none identified.
- **UNVERIFIED** — live external provider behavior was not exercised; no paid calls were made. The optional graph-present local sandbox could not run because its image is unavailable.


## Third review correction addendum

- Portable `.json` archive mutations now use `project_bundle.transform_members()` as the single read/modify/write boundary. Directory-project archives use the existing project write lock. Provider inference remains outside both transactions. The timeout-bounded subprocess regression imports a `.json` project, concurrently generates two answers, lists both, removes one, and verifies the other remains.
- In-flight API tasks are coalesced only when project ID, connection ID, and exact question match. A concurrent reuse of the same request ID with changed parameters is rejected; matching requests still share one task.
- Recovery list responses report whether the archive exists. Missing archives cannot be mistaken for a successful empty history; unreadable archives remain errors and their bytes are preserved. The Q/A recovery browser test covers missing and failed archive reads.
- The 1,000-marker threshold has been removed. Unresolved marker data remains protected by the archive's existing 30 MB byte limit; exceeding that limit fails closed before provider dispatch and leaves the archive intact.
- Implementation SHA: `10b2b46fa136491d4636b30689a7a909a60a1d15`.

Focused Q/A and security tests, Ruff, Pyright, frontend typecheck/build, full `./sigma test`, and both Q/A and saved-paper real Chrome checks passed. The optional graph-present sandbox check was skipped because its local image is unavailable. No paid provider calls, deployment, or merge were performed.

## Final saved-title and toolbar corrections

- Implementation commit: `4e555df2201c966f726a6bc2fd00cc2c2898ebd5`.
- This placement supersedes the earlier presentation note above: the Answer heading no longer carries Copy; Copy follows the saved question title.
- Q/A Copy now follows the full saved question, on its final wrapped line. The Answer heading no longer has a copy action. TeX Copy now follows the complete paper title; Download text, Download TeX, Download PDF, and Open PDF in browser remain in the existing action column.
- Saved-title disclosure controls and Copy buttons are separate, keyboard-accessible controls with no nested interactive buttons. Both browser regressions confirm Copy preserves the current expanded/collapsed state and copies the full document/text.
- The normal and Copied SVGs now share a fixed 28px control and 18px icon box. The confirmation check uses an inset path; Chrome verifies it is within the viewBox and its bounding box does not move during the transition.
- Q/A toolbar text is now 17px bold, while its 50×34px footprint remains equal to TEX and LEAN. Chrome checked computed type size/weight, equal control heights, and captured the toolbar.
- `./sigma test` passed, including Ruff, Pyright (0 errors/warnings/information), frontend typecheck/build and deterministic Q/A/TeX regressions. The optional graph-present sandbox check was skipped because its local image is unavailable; Vite reports the existing large-chunk advisory.
- Real Chrome checks passed with local deterministic fixtures and no paid calls. They verified two-line desktop and mobile Q/A/TeX titles, Copy placement after the final word, immediate Copied-state rendering without clipping/movement, disclosure state, clipboard content/failure, TeX download and PDF actions, and existing Q/A Markdown/browser/citation/Research version behavior.
- Screenshots: [Q/A title normal](../docs/evaluations/research_qa/research-qa-title-normal.png), [Q/A title Copied](../docs/evaluations/research_qa/research-qa-title-copied.png), [Q/A mobile title](../docs/evaluations/research_qa/research-qa-title-mobile.png), [TeX title normal](../docs/evaluations/research_qa/tex-title-normal.png), [TeX title Copied](../docs/evaluations/research_qa/tex-title-copied.png), [TeX mobile title](../docs/evaluations/research_qa/tex-title-mobile.png), and [toolbar](../docs/evaluations/research_qa/research-qa-toolbar.png).

### Status

- **MET** — Q/A and TeX title copy placement/wrapping; stable copied icon; clipboard payload and disclosure behavior; Q/A toolbar typography and retained footprint; Chrome desktop/mobile acceptance and feature regressions.
- **UNMET** — none identified.
- **UNVERIFIED** — live external provider behavior. No paid calls were made. All six GitHub workflows passed on implementation commit `4e555df2201c966f726a6bc2fd00cc2c2898ebd5`; workflow status for the final documentation-only follow-up will be reported with the final PR head.

No merge or deployment was performed. PR #398 remains open for coordinator review and owner smoke testing.
