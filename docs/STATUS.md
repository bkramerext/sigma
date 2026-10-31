# SIGMA status

## 2026-10-31 — Issue #407 / PR #406 reliability pass

Research duration defaults to 60 minutes for new sessions. Saved project settings and existing session snapshots remain authoritative. Hosted and local sponsorship preserve the project's configured duration; sponsorship enforcement remains in money allowance and spending ledgers. The seven-day project duration bound, per-call timeout, cancellation, and existing request/storage bounds remain technical safeguards.

Project Settings no longer shows an output-token control or session provenance token ceiling. Older saved/API values remain readable. API-key requests use the reviewed model output maximum; ChatGPT requests leave that parameter to the provider. A completed schema-valid response is retained and its reported usage settled even when it exceeds SIGMA's soft reservation estimate. Actual usage/cost blocks later work that cannot safely be reserved. Clipped responses preserve partial text and known usage, use one bounded concise retry when safe, and otherwise remain incomplete. Ambiguous attempts retain their reservation and are not replayed automatically.

The AI Agent Reliability sample retains its three complementary strategies and explicit success criteria. Its optional validated `limits.json` installs with each copy: three rounds, 18 scheduled turns, and 60 minutes. Deterministic coverage runs all 18 turns and a 12-turn budgeted partial run. A short ambient quality rubric covers correctness, evidence, assessable novelty, usefulness, reproducibility, objective coverage, and unresolved uncertainty; project criteria remain authoritative.

`make_sample` accepts complete project bundles and preserves validated paper JSON/TeX, PDF bytes, research evidence, and provenance in reusable copies. Paper file paths, identity links, checksums, PDF headers, file counts, and sizes are validated. Audit-only JSON remains accepted for non-binary research history and is not treated as containing restorable PDF bytes. Blank catalog samples remain free of fabricated findings or papers.

### Verification

- `./sigma test` — passed all checks, including Ruff, Pyright, frontend typecheck, and production build.
- Focused reruns: `tests/research_sessions.py`, `tests/make_sample.py`, `tests/increment22_budget.py`, project settings, and cloud research/API sponsorship checks — passed.
- `browser_checks/guest_samples.py` in real Chrome — passed against an isolated backend; no provider call was made.
- No paid provider calls were made. Six GitHub Actions workflows passed on implementation commit `6629c221341afa6ea7330344ccfb5648af683be0`: Research Outcome browser acceptance, T200 Model availability browser acceptance, T249 integrated project verification, SIGMA verification, T92 Recent Projects browser acceptance, and T201 obligation recovery browser acceptance.

### Remaining acceptance work

Real Chrome verified the sample catalog and guest/sample lifecycle. A signed-in UI Play/Resume/interruption smoke was not established locally; backend pause/resume, timeout, restart, clipping, and partial-retention behavior is covered by deterministic service tests. Run the manual investigation smoke procedure attached to PR #406 before the next AI Agents research run, and the six implementation commit CI results are green; rerun the manual smoke before acceptance.
