# Issue #436 browser evidence

`project_types_436.py` was run in installed headless Google Chrome against the Vite UI and the repository's isolated deterministic API fixture. No provider requests or paid calls were made.

- `evidence/types-desktop.png` — built-in catalog and open Literature icon.
- `evidence/deleted-project-mobile.png` — affected project remains available and presents the missing-type notice at mobile width.
- `evidence/missing-type-start-warning.png` — modal appears before any research config or start request.

The browser check also downloads the project and asserts that the saved project-type snapshot remains in the export bundle after deleting the catalog entry.
