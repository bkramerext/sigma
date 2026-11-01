# Issue #436 — Project Types acceptance and review handoff

Branch: `red/436-project-types`
PR: [#440](https://github.com/bkramerext/sigma/pull/440)
Integrated base: `main` at `4b2f34f9` (#439, Research Process/About workflow).

## Acceptance status

| Requirement | Result | Evidence / limits |
|---|---|---|
| Built-ins have one source-controlled catalog; custom types persist privately per authenticated user | **MET** | `src/sigma/data/builtin_project_types.json`; `tests/cloud_workspaces.py` exercises owner isolation, reload/restart persistence, imports/exports and project data isolation. |
| Required name/scope, optional description/based-on, icon and standards references validate; names are unique | **MET** | `tests/project_types.py`; shared typed services and authenticated workspace binding. |
| Based-on copies values independently, including unsaved parents; deleting the source preserves derived types | **MET** | Backend and Chrome checks create parent/child in one Save, edit/remove the source and inspect the child's independent values. |
| Literature has an open-book icon; the Stories of Your Life sample uses Literature; Other is absent; LEAN is Mathematics-only | **MET** | Built-in catalog and `samples/arrival-sequel/project.json`; `tests/project_types.py` checks open-book icon and Math-only LEAN. |
| Existing projects, samples, saved sessions, papers, evidence, exports and legacy records remain accessible | **MET** | Compatibility, project bundle and cloud workspace tests; Chrome downloads both deleted-type and legacy project exports. |
| Project Types UI groups and sorts types, keeps built-ins read-only, supports editable custom types, and saves/cancels atomically | **MET** | `browser_checks/project_types_436.py` confirms staged Add/Edit/Remove and Cancel leaves the catalog revision and values unchanged; Save warns before deleting a referenced type. |
| Reference URL inputs remain mounted while typing; URL/action tables use the requested proportions | **MET** | Chrome fills a reference URL while asserting focus remains and verifies the 80/20 column ratio. |
| Custom types can be saved without AI; placeholder icons are SIGMA-style, encoded, and replaceable | **MET** | Browser and backend tests create/save with the catalog placeholder and replace it with the Literature icon. No image upload or paid provider call exists in this PR. |
| AI-generated custom icons | **DEFERRED** | Per the owner addendum, custom AI generation is being implemented separately. No provider, credential, billing integration, or live generation verification is included. |
| Deleted types preserve project-owned meaning/icon, warn before deletion, and never silently reassign; unsafe snapshots require replacement before dispatch | **MET** | Backend snapshot/session tests and real Chrome check safe continuation, legacy incomplete-snapshot warning, explicit replacement, export retention, and no start/config request before user choice. Continuation request carries the explicit confirmation and creates a session. |
| Running session context stays frozen after type deletion | **MET** | Session snapshot persistence tests; deletion does not mutate existing sessions. |
| Research/publication references are stored without changing methodology or paper-authoring behavior | **MET** | Catalog persistence/API tests. The later #440/#443 integrations remain outside this implementation. |
| Gray's #439 About workflow, architecture content, and disclosure persistence remain intact | **MET** | Rebased/merged #439 commit `4b2f34f9`; real Chrome `browser_checks/issue437_workflow.py` covers keyboard disclosure operation, close/reopen, reload persistence, responsive layout and retained architecture content. |
| GitHub CI for the implementation head | **MET** | GitHub Actions on `6575f1eeca34fa8cfb6446fc813c7a78674dcfdf`: SIGMA verification, T201 obligation recovery, T249 integrated verification, T92 Recent Projects, T200 model availability and Research Outcome all succeeded. The unrelated scheduled #421 parity workflow was skipped. |

## Verification run

- `./sigma test` — **PASS** on the final merged implementation tree after the hosted user-isolation correction. Includes project type, cloud workspace, security, lint/format, Pyright, frontend typecheck and production build checks. The suite reports one existing optional graph-present sandbox scenario as skipped because its local execution image is unavailable; graph-withheld checks pass.
- `uv run --locked --no-sync python tests/project_types.py` — **PASS**.
- `uv run --locked --no-sync python tests/cloud_workspaces.py` — **PASS**, including two-owner isolation and reload/restart persistence.
- T201 workflow acceptance (`browser_checks/t201_overflow.py`, `t81_public_legal_pages.py`, `guest_samples.py`) — **PASS** in installed real Google Chrome against isolated local fixtures. T201 verifies bounded repeatable recovery, provenance, start controls and immutable history; guest and public legal-page checks also pass.
- `browser_checks/project_types_436.py` — **PASS** in real Google Chrome at desktop and mobile widths: transactional Save/Cancel, type deletion and warning, saved-settings continuation/session creation, explicit legacy replacement, import/export compatibility, URL focus, keyboard/focus behavior and icon replacement.
- `browser_checks/issue437_workflow.py` — **PASS** in real Google Chrome: About workflow, keyboard controls, persistent disclosures across reopen/reload, desktop/mobile layout and preserved architecture content.
- `browser_checks/project_about.py` — **PASS** in real Google Chrome at 1440px and 390px, including focus return.
- `git diff --check`, Ruff, Ruff format check, Pyright and frontend typecheck — **PASS**.
- No paid provider calls were made. Live provider/icon generation verification is **DEFERRED** by the owner addendum.

Chrome screenshots in `evidence/` record the desktop/mobile catalog, deleted-project mobile view, and pre-dispatch warning. The browser harness also exports the affected project and asserts that its saved type snapshot survives catalog deletion.
