# Qubit paper and SIGMA generation issues handoff

Branch: `phase1/golden-5-paper-production` (PR #464)

## Delivered

- Rebuilt the Qubit TeX/PDF from its archived structured draft. An editorial source override condenses the repeated operational interpretation into three signposted paragraphs and an evidence-linked comparison table. The generic renderer now keeps short tables together. The reviewed PDF has 19 pages; the comparison table fits on page 15.
- Added an optional **Include Issues and Bugs section (SIGMA generation only)** checkbox. The API records the choice, and the final TeX/PDF append only observed SIGMA generation diagnostics. Input research defects are excluded. A failed optional appendix compilation falls back to the already compiled paper and records the failure.
- Re-run the deterministic escaped-math repair after AI proofreading, closing a path where a proofreading correction could introduce escaped math before compilation.
- Reproducible source edits live in `scripts/rebuild_golden5_papers.py`, the Qubit `editorial_override.json`, and the shared paper renderer. The generated TeX was not edited directly.

## Review and verification

- Qubit presentation score (TeX/readability/sustained answer/evidence/visuals): 44 → 59 → provisional 65/100. The current breakdown is 5/22/27/6/5. Scientific validity has not been independently checked.
- Rebuilt Qubit with `uv run --locked --no-sync python scripts/rebuild_qubit_golden.py`; PDF compiled and has 19 pages. Inspected page 15 visually. The optional appendix compiled against this TeX with zero and one recorded issue. Both versions had the same pre-existing PDF geometry diagnostic on page 4, previously inspected as an ordinary mathematical overlap.
- `npm --prefix frontend run build`, `ruff check` on changed Python, and `pyright` passed.
- `./sigma test` was attempted. It failed at `tests/papers.py` because that test expects an `About this paper` section which the renderer at the previous branch head already did not emit. The first run also reported branch-local lint and type errors; these were corrected, and focused lint and `pyright` now pass. A full rerun was not completed. No real-browser check or paid provider call was made.

## Next

Review the scientific argument separately from layout quality. Next editorial target is Warp Drive. Reconcile the stale paper-test expectations with the present publication contract before treating the full suite as a merge gate.

## Follow-on review: two math papers and Operation Narrow Passage

The user requested links and best-version retention for Maximum Regions, Nonconsecutive Subset Sums, and Operation Narrow Passage. All three existing TeX files compiled with Tectonic; the PDFs have 6, 10, and 17 pages respectively, with no PDF text-bound warnings. First, middle, and final pages were visually inspected. Recompilation alone did not improve Maximum Regions or Operation Narrow Passage, so their prior tracked pairs remain in `papers/`.

The initial Nonconsecutive rebuild placed its writing-method bibliography on an extra 11th page and was rejected. The renderer now reserves those editorial sources for the opt-in validation appendix; the generation metadata still retains the exact source list. The structured reader guide uses proper math notation. The resulting 10-page PDF retains the claim/source notes on its last page, has no text-bound warnings, and replaces the earlier pair. This is a production renderer and structured-source change, not a manual TeX edit.

## Follow-on review: Warp Drive

The Warp Drive pair was rebuilt from the archived structured draft. The prior PDF stranded punctuation after displayed equations and devoted its final page to editorial writing sources. The current renderer fixes equation punctuation and keeps writing-method provenance in the generation record by default. An evidence-conservative structured editorial override condenses the final research-program section into five explicit gates: source dynamics, finite-duration propagation, quantum backreaction, preparation/control, and empirical comparison. The renderer bolds those signposts generically. The reviewed PDF is 21 pages (previously 22). Its sole text-bound diagnostic is a page-5 integral sign and lower-limit overlap; visual inspection at enlarged scale found the formula legible. No claim of a realized drive or universal prohibition was added. Scientific validity remains unverified.
