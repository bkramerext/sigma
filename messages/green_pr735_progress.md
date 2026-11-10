# Green PR #735 progress handoff (not R4R)

Branch: `feature/project-evidence-pdfs`. This batch is incomplete and must not be merged.

## Changes

- Repaired v4 Save As import/rebind and updated directory-project recents and collaboration browser assumptions.
- Removed guest Source Material API reads and guest edit controls; corrected the project subsection heading and link editor Escape behavior.
- Failed Source Material compilation blocks role dispatch. Completed linked and attached documents now retain session-scoped original-byte snapshots on disk, with hash and provenance; successful links are reused on resume. Failed extracts are retried. Saved compilation integrity is checked before reuse.
- Removed silent 6,000-character agent evidence clipping. The current 60,000-character bound fails explicitly before dispatch; this is still a temporary limitation, not the required long-document synthesis path.
- Isolated `./sigma test` state per script; corrected obsolete v4 import and macOS memory-test fixtures.
- Added mocked barrier/partial-resume, source snapshot, bundle round-trip and real Chrome Source Material checks.

## Actual verification

- `./sigma test`: passed on the batch before the last focused source-snapshot and browser-check additions; all four research-session shards, Ruff, Pyright and frontend typecheck passed. The earlier failed run and fixes are in this branch history's local verification record; no new CI claim is made here.
- Focused: `tests/project_creation.py`, `tests/recents.py`, `tests/project_evidence.py`, `tests/project_transfer.py`, `tests/research_supplied_evidence_integration.py`, `tests/project_collaboration.py`, `tests/deployment_package.py`, `tests/research_sessions_part2.py`, `tests/proposals.py`, and the emailed v4 import/resume scenario passed locally with mocks.
- `ruff check src tests browser_checks`, `ruff format --check src tests browser_checks`, `pyright`, frontend build, and `git diff --check`: passed after the final local edits.
- Real Chrome: `browser_checks/guest_samples.py`, `t47_conclusion.py`, `collaboration_local_accounts.py`, and `source_material_735.py` passed. `collaboration_settings.py` passed but was served by a pre-existing Vite process from another checkout, so it is not counted as verification of this branch.
- No paid provider calls. No merge.

## Still required

- Replace the explicit 60,000-character context bound with a bounded, resumable compilation/synthesis or lookup path that makes all processed premises available without silent omission.
- Review oversized v4 artifact archives (one TAR frame is capped at 256 MiB although valid runtime projects can exceed it).
- Inspect CI after push, resolve any failures in batches, rerun affected real-browser checks, and update this handoff before R4R.
