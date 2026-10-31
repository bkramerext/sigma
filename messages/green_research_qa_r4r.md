# R4R — Research Q/A review corrections

## Delivery

- Branch: `green/research-qa`
- PR: [#398](https://github.com/bkramerext/sigma/pull/398), existing PR, open and unmerged
- Review base/head: `cefef4115308d05eea57fe59a91b06347f93041d`
- Review-correction commit: recorded after commit below
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
