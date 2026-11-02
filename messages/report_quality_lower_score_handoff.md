# Report quality iteration handoff: lower-scoring papers

Branch: `phase1/golden-5-paper-production`

## Completed and pushed

- **Sovereign AI Federation v2** — commit `33f07be6`. Reworked selected paragraphs in the 90-day evaluation to signpost the decision, sampling, success criteria, safety gate, paired comparison, independent units, and reporting outcomes. Preserved the estimands, counterexample, interval construction, and decision inequalities. Shortened diagram edge labels after visual inspection found awkward hyphenation. Presentation score: **62 → 65/100**; evidence strength unchanged.
- **Agent Reliability v1** — commit `998a07f5`. Clarified the difference between population reliability, population improvement, and frozen-roster certification, while preserving the mathematical bounds and existing evidence table. A preview with a duplicate table was rejected; the promoted version omits it. Presentation score: **58 → 60/100**; evidence strength unchanged.

Both updated TeX/PDF pairs are tracked in `papers/`. PDF checks: Sovereign 22 pages, Agent 24 pages; no text-bound warnings. Visually inspected Sovereign pages 16–20 and Agent pages 3–7. `ruff check scripts/rebuild_golden5_papers.py` and `git diff --check` passed. No scientific proof or empirical evaluation was performed.

## Warp Drive preview

An unpromoted prose revision was discarded after visual review showed the existing floating figure interrupts the following section’s opening. The tracked Warp Drive pair was not changed by this preview. Resolve figure placement before another editorial pass.
