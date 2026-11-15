# A14.1: Rename Project to Investigation across SIGMA

**Status:** Ready for Codex implementation **after the test/stabilization pass**. This assignment lives in the repository; GitHub issues are not the assignment mechanism.

## Objective

An **Investigation** is SIGMA's top-level research object. Replace **Project** with **Investigation** wherever it names that object in the UI, code, API, storage, documentation, and tests. This is a terminology and compatibility migration, **not** a redesign of Generate Strategy or Home.

Read the existing project/strategy persistence code and tests before editing. Follow established SIGMA assignment and delivery conventions.

## Required product terminology

- Home: **New Investigation**, **Open Investigation**, **Recent Investigations**, with matching dialog titles, prompts, empty states, errors, tooltips, and accessibility labels.
- The workspace becomes the **Investigation** workspace/page where applicable.
- **Precisely rename the existing “Project description” section heading to “Investigation”** (not “Investigation description”).
- **Project Settings** becomes **Investigation Settings**.
- Update buttons, notifications, browser titles, tests, and docs accordingly.
- Preserve **Strategy**, **SIGMA**, and unrelated uses of “project” (such as external product names or project-management terminology).

## Code, API, storage, and migration

1. Rename project-specific types, components, functions, variables, modules, filenames, directories, tests, and fixtures where they denote SIGMA's top-level research object. Prefer `investigation` / `investigations` in code and paths.
2. Migrate legacy `projects/` storage paths, HTTP `/api/projects` routes, and `/project` browser routes to investigation-based equivalents, **without breaking existing installations or bookmarks**. Explicit compatibility aliases are acceptable where needed; document them.
3. If on-disk document keys or API fields use `project` for this object, introduce a deliberate, versioned or otherwise unambiguous migration. Existing files must load safely; repeated migration must be idempotent. Do not silently duplicate or overwrite investigations.
4. Preserve all investigation/strategy IDs, source text, event history, ordering, model/thinking settings, investigation type, connection behavior, and locally persisted UI preferences.
5. Do not rewrite historical records or user-authored research text solely to change terminology. Keep the `.sigma` extension unless there is a genuine technical reason to change it.
6. Update imports, CLI commands, routes, tests, fixtures, documentation, and any other references consistently. Enumerate intentional remaining legacy references and why they are retained.
7. Keep the current **six-entry Recent Investigations capacity** and its ordering, Remove action, unavailable states, and persistence behavior. Do not revert it to four.

## Acceptance criteria

1. No user-facing **Project** remains where it refers to an Investigation. The description heading reads exactly **Investigation**.
2. Both newly created investigations and legacy projects open, edit, generate strategies, and save successfully without data loss.
3. Existing IDs, strategies, event history, settings, bookmarks, and recent entries survive migration and repeated restarts.
4. Compatibility for old on-disk data, routes, and UI preferences is tested and documented.
5. Renamed files, imports, APIs, CLI commands, schemas, and docs are coherent. Intentional compatibility shims are clearly marked.
6. Relevant backend tests and frontend typecheck/build/tests pass, or any remaining failures are reported with commands and causes.
7. No collateral changes to approved artwork, Home layout, workspace visual design, or strategy-generation behavior.

## Tests and delivery

- Start from the stabilized baseline. Run focused tests for create/open/edit/save, legacy-file migration and repeat migration, API and browser-route compatibility, recent investigations, settings, event history, and strategy persistence.
- Run the frontend production build/typecheck and relevant backend suites; state actual commands and results.
- Keep changes focused; **commit and push directly to `main`**, no pull request. Report the commit SHA and any intentionally retained legacy identifiers.

## Out of scope

Fixing or redesigning the Generate Strategy workflow beyond mechanical terminology updates and regression checks; new research capabilities; broad UI redesign; any modification of the approved SIGMA imagery.
