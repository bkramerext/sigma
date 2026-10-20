# ASN-6: New Project creation and research mode

**Status:** Ready for Codex after ASN-5 is complete or in a nonconflicting implementation branch.

## Purpose

Replace the Home page's exposed project-directory text field with a deliberate **Open Project** / **New Project** command pair. Creation must work end-to-end, persist a research mode, and open the newly created project. This is a functional enhancement, not a redesign of the accepted Home artwork.

**Numbering:** ASN-4.1 already specifies the cinematic Home entrance and remains on hold. Do not overwrite or implement that assignment. This new work is ASN-6.

## User experience and visual direction

**Design the complete interaction, not merely the minimum controls listed here.** The Home screen is an invitation into research, not a filesystem utility. Keep its original approved cinematic artwork **byte-for-byte unchanged** and respect its existing negative space, focal points, typography, metallic copper/gold hierarchy and restrained translucency. Do not let a large form, oversized dialog or extra decorative chrome compete with the art. Think through button prominence, spacing, alignment, labels, transitions, empty/error states and narrow screens as one coherent design before coding. Prefer a quiet, polished solution over a collection of generic form widgets. Do not invent additional Home features.

### Home: two clear entry points

- **Remove the always-visible editable project-path field and its form** from Home. Replace it with two adjacent, legible commands: **Open Project** and **New Project**. They should read as a deliberate pair with consistent proportions and spacing, a clear but not garish primary/secondary hierarchy, and accessible hover/focus/disabled states. At mobile widths, stack them cleanly. Do not place a path input next to or underneath these buttons on the resting Home screen.
- **Open Project** opens a focused, accessible dialog/surface for choosing an **existing** project. Use a real filesystem picker only if supported by the local application architecture; browsers cannot generally provide arbitrary server-side directory paths. If there is no supported native picker, use a **directory-path input inside the Open Project dialog**, not on Home, with helpful examples and the existing path-based API. Never display a fake Browse button. Retain the ability to open `projects/rh.sigma` and arbitrary valid existing local project directories, including meaningful errors. Cancel must return to the unchanged Home screen.
- **New Project** opens a visually matched creation dialog/surface. Include **Project name**, **Research problem** (multiline), and **Research mode** dropdown (`Default` preselected, `Mathematical` alternative). These are the principal choices. Do **not** ask the user to edit a raw directory path as part of normal creation. Instead, create in a predictable, documented local projects location following existing SIGMA conventions (e.g. under the configured projects root), with a safe, deterministic directory name derived from the project name. Show the destination unobtrusively as **read-only contextual information** before creation. If the existing backend has no suitable projects root, introduce a simple explicit server-side default/configuration and document it; do not assume the browser's working directory or home directory. Handle name/path collisions explicitly without overwriting data.
- Provide Create/Cancel actions, clear validation and error states, keyboard focus management and restoration, disabled/busy states, Escape handling, and duplicate-submit protection. Both flows must work with keyboard and screen reader. On successful create/open, navigate to the existing real project workspace. Keep the dialog typography, inputs, overlay, buttons and contrast faithful to the SIGMA visual identity; avoid default browser-white dialog styling.
- Existing **Recent Projects** messaging should remain truthful. If there is no persisted recent-project index, don't fabricate one. Avoid letting it distract from the two principal commands.
- Evaluate the resulting Home at desktop, tablet and 390/320px. Check the actual artwork composition with both the resting Home and dialogs open, not just component-level screenshots. Use judgment to resolve visual conflicts while preserving approved art and working functionality.

## Data model and API

- Add a persisted project field `research_mode` with initial values `"default"` and `"mathematical"`. Use an extensible enum/string representation, not separate booleans or divergent project implementations.
- **Backwards compatibility:** Existing project documents lacking `research_mode` must load as `"default"` without losing existing data, changing strategy/history semantics, or requiring manual migration. Preserve any existing schema-version/migration conventions.
- Extend project serialization, validation, load/save, and frontend `ProjectView` typing consistently. Reject unknown values on project creation rather than silently coercing them. Plan the implementation so future modes can be added deliberately.
- Implement an actual backend project-creation operation using existing filesystem/project repository conventions and a clearly defined local projects root, integrated with the frontend. Inspect existing project initialization and routes before choosing an endpoint or directory layout. Derive a safe directory name server-side; don't trust client-supplied filesystem paths for creation.
- Do not overwrite an existing project or arbitrary user files. Validate path existence/ownership, missing parent directories, malformed inputs, and partial failure; use atomic/rollback-safe creation where practical. Preserve existing Open/Close behavior and navigation.
- Persist name, problem, and mode. Reopening a created project must return the same values.

## Artifact capabilities (scope boundary)

- **LaTeX artifacts are universal**, available to all research modes when artifact support is implemented.
- **Lean artifacts are specific to mathematical mode**, including future formal proof checking.
- For this assignment, implement **project creation and the research-mode model**, not a speculative artifact manager, Lean engine, LaTeX editor, or proof checker. The stored mode must be accessible for later capability gating. Do not display working artifact controls that have no implementation.

## Interaction with ASN-5 and artwork

- ASN-5 owns the approved dark Strategy Pool workspace redesign. Do not undo or restyle it; work against the current implementation after ASN-5 lands and resolve conflicts intentionally.
- `assets/` remains authoritative for artwork. Codex owns any runtime frontend integration; the human should not have to copy artwork into `frontend/`.
- Keep the accepted Home art pixel-identical. New controls may be added to the existing Home interface, but not by altering the image or substituting a different background.
- ASN-4.1 cinematic Home animation remains on hold.

## Tests and verification

1. Inspect current frontend, backend project schema, persistence, initialization code, and tests before editing.
2. Test creating a Default project and a Mathematical project, including actual files and serialized `research_mode`.
3. Test reopening both, loading a legacy project with no mode (defaults to `default`), and rejecting invalid mode, empty fields, duplicate project names/directory collisions, and unsafe generated destinations.
4. Verify **Open Project** opens the dialog (with no resting Home path field), successfully opens an existing path, and handles bad paths/cancel; verify project title/problem, existing strategy operations, project history, Open/Close, browser navigation, and error recovery still work.
5. Run `./sigma test` and frontend build/type checks; exercise **both** project commands and dialogs in a real browser at desktop and narrow mobile. Confirm the accepted Home artwork is unchanged and ASN-5 workspace design remains intact.
6. Update `docs/STATUS.md` with exact checks/results and any limitations. Commit implementation only after verification; report unavailable checks accurately.

**Definition of done:** Home presents a refined pair of **Open Project** and **New Project** commands, **without a visible path-edit field**. Opening an existing project remains fully functional through its dedicated surface. A user can create and reopen a real SIGMA project without manually entering a destination path, choose Default or Mathematical research mode, and see the choice faithfully persisted. The original Home artwork and working Strategy Pool remain intact.
