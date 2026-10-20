# ASN-6: New Project creation and research mode

**Status:** Ready for Codex after ASN-5 is complete or in a nonconflicting implementation branch.

## Purpose

Add a first-class **New Project** command to the SIGMA Home page. Creation must work end-to-end, persist a research mode, and open the newly created project. This is a functional enhancement, not a redesign of the accepted Home artwork.

**Numbering:** ASN-4.1 already specifies the cinematic Home entrance and remains on hold. Do not overwrite or implement that assignment. This new work is ASN-6.

## User experience

- On Home, retain the working **Open Project** path-based workflow. Add a prominent **New Project** command in the same dark navy, copper/gold, restrained SIGMA visual language. Preserve the exact accepted Home background image, its composition, and existing layout intent. Do not replace artwork or add fake controls.
- Clicking **New Project** opens an accessible creation dialog/panel containing:
  1. **Project name** (required).
  2. **Research problem** (required, multiline).
  3. **Research mode** (native or accessible dropdown), with **Default** selected initially and **Mathematical** as the other choice.
  4. A usable **project directory** destination control: reuse existing local-directory conventions and clearly explain where the project will be created. Do not silently choose a surprising location or pretend a browser can freely select local folders. Ensure the path is available and validated before writing.
- Provide Create and Cancel actions, clear validation and error states, keyboard focus management, disabled/busy state during creation, and protection against duplicate submissions.
- On successful creation, navigate to the existing project workspace at its real path, with no intermediate fake project.
- Home and project workspace must remain responsive and usable at narrow widths.

## Data model and API

- Add a persisted project field `research_mode` with initial values `"default"` and `"mathematical"`. Use an extensible enum/string representation, not separate booleans or divergent project implementations.
- **Backwards compatibility:** Existing project documents lacking `research_mode` must load as `"default"` without losing existing data, changing strategy/history semantics, or requiring manual migration. Preserve any existing schema-version/migration conventions.
- Extend project serialization, validation, load/save, and frontend `ProjectView` typing consistently. Reject unknown values on project creation rather than silently coercing them. Plan the implementation so future modes can be added deliberately.
- Implement an actual backend project-creation operation, using existing filesystem/project repository conventions, and integrate it with the frontend. Inspect existing project initialization and routes before choosing an endpoint or directory layout.
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
3. Test reopening both, loading a legacy project with no mode (defaults to `default`), and rejecting invalid mode, empty fields, path collision, and unsafe destination.
4. Verify project title/problem, existing strategy operations, project history, Open/Close, browser navigation, and error recovery still work.
5. Run `./sigma test` and frontend build/type checks; exercise New Project in a real browser at desktop and narrow mobile. Confirm the accepted Home artwork is unchanged and ASN-5 workspace design remains intact.
6. Update `docs/STATUS.md` with exact checks/results and any limitations. Commit implementation only after verification; report unavailable checks accurately.

**Definition of done:** A user can create and reopen a real SIGMA project from Home, choose Default or Mathematical research mode in a dropdown, and see the choice faithfully persisted, without changing the accepted artwork or disrupting the working Strategy Pool.
