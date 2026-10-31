# R4R — Research Q/A

## Delivery

- Branch: `green/research-qa`
- Base: `main` at `2d0a564c731655d4ba7264fab826f96b12c63b96`
- Commit SHA: pending final commit
- PR: pending push/open
- Merge/deploy: not performed
- Provider cost: no paid provider calls; browser checks used the deterministic
  local provider fixture

## Result

Added a Research Q/A dialog beside TeX, using saved project evidence and the
configured project model. Answers are stored with the exact question, selected
evidence snapshot, snapshot hash, model/thinking metadata and validated source
IDs. Request IDs and a persisted pre-dispatch marker prevent an interrupted
request from being silently repeated. Q/A does not create sessions or modify
strategies/findings. The archive survives bundle export/import and supports
removal without touching research.

Session, artifact and Current Understanding citations are rendered from stored
validated source identifiers. Session/artifact links use the existing reveal
flow; disappeared evidence retains its citation with navigation marked
unavailable. The browser view escapes question/answer content, uses a restrictive
CSP, and generates links from stored references. TeX and Q/A saved records now
reuse the existing clipboard button; TeX copies the human-readable `/txt`
representation.

## Changed files

- `src/sigma/research_qa.py` — bounded evidence selection, provider synthesis,
  validation, persistence, navigation availability and safe browser HTML.
- `src/sigma/api.py` — list/answer/get/remove/browser endpoints and shielded
  idempotent request task handling.
- `src/sigma/tooling.py` — deterministic service test registered in `./sigma test`.
- `tests/research_qa.py` — multi-session citations, unsupported/uncertain
  evidence, forged citations, deleted-source navigation, idempotency,
  persistence/export-import, escaping and no project mutation.
- `frontend/src/main.tsx` — Q/A dialog/archive, citations, reveal query handling,
  Q/A clipboard and TeX text clipboard.
- `frontend/src/workspace.css`, `frontend/src/strategies.css` — existing-style
  spacing, input and citation highlight.
- `browser_checks/provider_fixture.py` — deterministic `sigma_research_qa`
  mock-provider output.
- `browser_checks/research_qa.py` — Chrome flow for Q/A and responsive browser
  presentation.
- `browser_checks/saved_paper_library.py` — TeX clipboard regression coverage.
- `docs/evaluations/research_qa/research-qa-browser-desktop.png`
- `docs/evaluations/research_qa/research-qa-mobile.png`
- `docs/evaluations/research_qa/research-qa-browser-mobile.png`
- `tickets/t314_research_qa.md`, `docs/STATUS.md`, this handoff.

## Checks actually run

- `./sigma test` — passed. Included Ruff check/format, Pyright (0 errors),
  frontend typecheck/build, existing TeX tests and `tests/research_qa.py`.
  The suite noted the pre-existing optional graph-present Python sandbox case
  skipped because its local image is unavailable.
- `uv run --with playwright --no-project python browser_checks/research_qa.py`
  — passed in real Chrome against the local deterministic fixture: Q/A action
  placement, question, archive open/collapse/expand, citations, session reveal,
  browser open, desktop/mobile view, copy success/failure, removal, and unchanged
  session count.
- `SIGMA_PAPER_UI=http://127.0.0.1:5174 SIGMA_PAPER_FIXTURE=http://127.0.0.1:8012 uv run --with playwright --no-project python browser_checks/saved_paper_library.py`
  — passed in real Chrome against the local fixture: saved TeX human-readable
  clipboard success/failure, text/TeX/PDF payloads, PDF browser view, responsive
  layout and removal.
- `uv run --locked --no-sync ruff check` on changed Python files — passed.
- Vite emitted its existing large-chunk advisory during build; the build passed.

## Screenshots and observations

- [Standalone desktop](../docs/evaluations/research_qa/research-qa-browser-desktop.png)
- [Standalone mobile](../docs/evaluations/research_qa/research-qa-browser-mobile.png)
- [Q/A dialog mobile](../docs/evaluations/research_qa/research-qa-mobile.png)

The visual flow follows the existing dark/copper SIGMA styling. The standalone
mobile check caught and fixed an unbroken snapshot hash causing horizontal
overflow; metadata now wraps safely.

## Acceptance status

- **MET** — project-scoped Q/A archive, frozen saved-evidence synthesis,
  validated source IDs, exact question and evidence provenance, unsupported and
  uncertain answers, session/artifact deep links, unavailable-source behavior,
  browser presentation, safe escaping, copy controls, TeX regression, remove,
  export/import, and no research mutation in deterministic tests.
- **MET** — local Chrome desktop/mobile checks and required repository suite.
- **UNMET** — none identified in implemented scope.
- **UNVERIFIED** — live external provider behavior intentionally not exercised;
  cross-user denial and path-traversal attacks were not separately exercised in
  dedicated adversarial API tests; process restart was not performed as a
  separate browser acceptance step. Durable storage was verified by reloading
  records and export/import.

No PR review, merge, or deployment was performed.
