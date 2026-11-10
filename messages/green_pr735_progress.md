# Green PR #735 progress handoff (not R4R)

Branch: `feature/project-evidence-pdfs`. This batch is incomplete and must not be merged.

## Changes

- Nov 10 follow-up: public import now rejects v1-v3 uploads (legacy live .json files
  remain readable and export as v4), with API acceptance coverage.
- V4 artifacts can exceed the old 256 MiB single-frame ceiling by using bounded,
  concatenated zstd frames within the same TAR archive; frame tampering and
  combined metadata/artifact size limits have regression tests.
- Repaired v4 Save As import/rebind and updated directory-project recents and collaboration browser assumptions.
- Removed guest Source Material API reads and guest edit controls; corrected the project subsection heading and link editor Escape behavior.
- Failed Source Material compilation blocks role dispatch. Completed linked and attached documents now retain session-scoped original-byte snapshots on disk, with hash and provenance; successful links are reused on resume. Failed extracts are retried. Saved compilation integrity is checked before reuse.
- Removed silent 6,000-character agent evidence clipping. The current 60,000-character bound fails explicitly before dispatch; this is still a temporary limitation, not the required long-document synthesis path.
- Isolated `./sigma test` state per script; corrected obsolete v4 import and macOS memory-test fixtures.
- Added mocked barrier/partial-resume, source snapshot, bundle round-trip and real Chrome Source Material checks.

## Actual verification

- **Nov 10 follow-up commits are not yet CI-verified.** GitHub reports the #735
  branch as non-mergeable against current main and no PR workflow runs were
  returned for its new head. Do not interpret earlier local passes as green CI.
- `./sigma test`: passed on the batch before the last focused source-snapshot and browser-check additions; all four research-session shards, Ruff, Pyright and frontend typecheck passed. The earlier failed run and fixes are in this branch history's local verification record; no new CI claim is made here.
- Focused: `tests/project_creation.py`, `tests/recents.py`, `tests/project_evidence.py`, `tests/project_transfer.py`, `tests/research_supplied_evidence_integration.py`, `tests/project_collaboration.py`, `tests/deployment_package.py`, `tests/research_sessions_part2.py`, `tests/proposals.py`, and the emailed v4 import/resume scenario passed locally with mocks.
- `ruff check src tests browser_checks`, `ruff format --check src tests browser_checks`, `pyright`, frontend build, and `git diff --check`: passed after the final local edits.
- Real Chrome: `browser_checks/guest_samples.py`, `t47_conclusion.py`, `collaboration_local_accounts.py`, and `source_material_735.py` passed. `collaboration_settings.py` passed but was served by a pre-existing Vite process from another checkout, so it is not counted as verification of this branch.
- No paid provider calls. No merge.

## Still required

- Replace the explicit 60,000-character context bound with a bounded, resumable compilation/synthesis or lookup path that makes all processed premises available without silent omission.
- Verify the new bounded multi-frame v4 archive path under CI and with a real
  larger-than-256 MiB project fixture; current tests force small frame boundaries
  to cover the same framing logic without excessive test memory.
- Inspect CI after push, resolve any failures in batches, rerun affected real-browser checks, and update this handoff before R4R.
