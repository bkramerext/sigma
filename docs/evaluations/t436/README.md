# Issue #436 — Project Types acceptance and review handoff

Branch: `red/436-project-types`
PR: [#440](https://github.com/bkramerext/sigma/pull/440)
Integrated base: `main` at `5aaa459d57d20436a2b3dfb8c696fd4a2a154f42` (#439/#444 Research Process/About workflow and #446 Project subtitle alignment).

## Acceptance status

| Requirement | Result | Evidence / limits |
|---|---|---|
| Built-ins have one source-controlled catalog; custom types persist privately per authenticated user | **MET** | `src/sigma/data/builtin_project_types.json`; `tests/cloud_workspaces.py` exercises owner isolation, reload/restart persistence, imports/exports and project data isolation. |
| Required name/scope, optional description/based-on, icon and standards references validate; names are unique | **MET** | `tests/project_types.py`; shared typed services and authenticated workspace binding. |
| Based-on copies values independently, including unsaved parents; deleting the source preserves derived types | **MET** | Backend and Chrome checks create parent/child in one Save, edit/remove the source and inspect the child's independent values. |
| Literature has an open-book icon; the Stories of Your Life sample uses Literature; Other is absent; LEAN is Mathematics-only | **MET** | Built-in catalog and `samples/arrival-sequel/project.json`; `tests/project_types.py` checks open-book icon and Math-only LEAN. |
| Existing projects, samples, saved sessions, papers, evidence, exports and legacy records remain accessible | **MET** | Compatibility, project bundle and cloud workspace tests; Chrome downloads both deleted-type and legacy project exports. The merged Qubit schema-v8 sample is listed and copied with its full problem text and Physics snapshot/icon; its hosted guest copy is covered in `tests/cloud_auth.py`. |
| Qubit sample remains compatible with the unified catalog | **MET** | `tests/recents.py` checks local discovery/copy, schema-v8 read, byte-preserved problem, Physics snapshot and new-project persistence; `tests/cloud_auth.py` checks the hosted guest copy. Qubit's scientific criteria are unchanged. Arrival remains classified as Literature. |
| Project Types UI groups and sorts types, keeps built-ins read-only, supports editable custom types, and saves/cancels atomically | **MET** | `browser_checks/project_types_436.py` verifies compact checkbox dimensions on desktop/mobile, staged Add/Edit/Remove and Cancel, plus exact original names and usage counts when multiple referenced types are removed in one Save. |
| Reference URL inputs remain mounted while typing; URL/action tables use the requested proportions | **MET** | Chrome fills a reference URL while asserting focus remains and verifies the 80/20 column ratio. |
| Malformed reference URLs return validation errors and do not mutate storage | **MET** | `tests/project_types.py` verifies invalid ports, malformed IPv6 brackets, and out-of-range ports return API 400 with unchanged catalog revision/content. |
| Custom types can be saved without AI; placeholder icons are SIGMA-style, encoded, and replaceable | **MET** | Browser and backend tests create/save with the catalog placeholder and replace it with the Literature icon. No image upload or paid provider call exists in this PR. |
| AI-generated custom icons | **DEFERRED** | Per the owner addendum, custom AI generation is being implemented separately. No provider, credential, billing integration, or live generation verification is included. |
| Deleted types preserve project-owned meaning/icon, warn before deletion, and never silently reassign; unsafe snapshots require replacement before dispatch | **MET** | Backend snapshot/session tests and real Chrome check safe continuation, legacy incomplete-snapshot warning, explicit replacement, export retention, and no start/config request before user choice. Continuation request carries the explicit confirmation and creates a session. |
| Running session context stays frozen after type deletion | **MET** | Session snapshot persistence tests; deletion does not mutate existing sessions. |
| Research/publication references are stored without changing methodology or paper-authoring behavior | **MET** | Catalog persistence/API tests. The later #440/#443 integrations remain outside this implementation. |
| Research Process/About disclosure workflow and Project subtitle alignment survive main integration | **MET** | Integrated `main` at `5aaa459d`; `browser_checks/issue441_research_process.py` verifies Research Process, architecture diagram, and persistent disclosure state; `browser_checks/project_types_436.py` verifies the Project subtitle on an affected project page. |
| GitHub CI for the integrated implementation | **MET** | All six PR workflows passed on implementation SHA `1b066a4e15d48a5400a04421d5117542c698e479`: SIGMA verification, T201 obligation recovery, T249 integrated verification, T92 Recent Projects, T200 model availability and Research Outcome. The unrelated scheduled #421 workflow was skipped. |

## Verification run

- `./sigma test` — **PASS** on the integrated tree including the three review fixes and Qubit regression. Includes project type, local/hosted sample, cloud workspace, security, lint/format, Pyright, frontend typecheck and production build checks. The suite reports one existing optional graph-present sandbox scenario as skipped because its local execution image is unavailable; graph-withheld checks pass. Vite emitted its existing non-failing large-chunk advisory.
- `uv run --locked --no-sync python tests/project_types.py` — **PASS**.
- `uv run --locked --no-sync python tests/cloud_workspaces.py` — **PASS**, including two-owner isolation and reload/restart persistence.
- `browser_checks/project_types_436.py` — **PASS** in real Google Chrome at desktop and mobile widths: transactional Save/Cancel, type deletion and warning, saved-settings continuation/session creation, explicit legacy replacement, import/export compatibility, URL focus, keyboard/focus behavior and icon replacement.
- `browser_checks/t201_overflow.py`, `browser_checks/t81_public_legal_pages.py`, and `browser_checks/guest_samples.py` — **PASS** in real Google Chrome against isolated fixtures. The guest check confirms the Qubit sample appears in the Physics group with its Physics icon and copies a guest sample; `tests/cloud_auth.py` covers Qubit's guest API copy.
- `browser_checks/issue441_research_process.py` — **PASS** in real Google Chrome: merged Research Process workflow, preserved architecture diagram, responsive layout and persistent disclosure state.
- `browser_checks/project_about.py` — **PASS** in real Google Chrome at 1440px and 390px, including focus return.
- `git diff --check`, Ruff, Ruff format check, Pyright and frontend typecheck — **PASS**.
- GitHub Actions on `1b066a4e15d48a5400a04421d5117542c698e479` — **PASS**, all six PR workflows; unrelated scheduled #421 parity workflow skipped.
- No paid provider calls were made. Live provider/icon generation verification is **DEFERRED** by the owner addendum.

Chrome screenshots in `evidence/` record the desktop/mobile catalog, deleted-project mobile view, and pre-dispatch warning. The browser harness also exports the affected project and asserts that its saved type snapshot survives catalog deletion.
