# IN #2 — OUT #2 corrections and research-quality checkpoint

**Branch:** `blue/sovereign-ai-federation`  
**Implementation/artifact commit:** `c7bdf43f8caf79eaf09d4e080cb1c50597b262bc`  
**Artifact polish commit:** `471152dd80816a8352fca4e69d936e31e6dc7eb1`  
**Current branch HEAD:** `471152dd80816a8352fca4e69d936e31e6dc7eb1`  
**PR #395:** open, Draft, unmerged; `main` untouched. The working tree is clean.

## Completed

- Added bounded `diagrams` to `LongPaperPlan` and exercised the actual checked long-form generation path with mocked structured provider output. Checked diagrams carry source refs and claim IDs; invalid references are rejected/repaired. Default unchecked generation stays diagram-free.
- Changed diagrams to default on in the paper dialog/API, preserving a user option to turn them off. The one-shot and long-form prompts ask for explanatory diagrams and evidence-backed tables where they improve the explanation or comparison. Tables now have bounded validated schemas, evidence/claim provenance, long-form checkpoint persistence, TeX longtable rendering, and compiler-fallback coverage.
- Preserved continuation for old checkpoints without an explicit diagram preference. Regression cases cover long-form default-on and explicit-off calls, saved evidence, continuation/restart paths, frozen-source preservation, compiler fallback, and no extra provider request on fallback.
- Integrated both economics suites into `./sigma test` and fixed Ruff/Pyright issues. Reproduced the deterministic economic outputs and the optional LP with a transient SciPy 1.17.0 environment; SciPy was not added to the lockfile.
- Prepared and compared two offline source-grounded papers from the exact same `paper_body.tex`. They discuss four alternatives; published MindRouter quantities and their limitations; derived energy/break-even arithmetic; hypothetical fixed-allocation and optimization results; quality, cost, fairness, sovereignty and failure counterexamples; falsifiable hypotheses and a 90-day pilot. Invented scenario inputs/results are identified as hypothetical. These papers are explicitly **not** SIGMA Investigator/Skeptic research.

## Validation actually run

- `uv run --locked ruff check ...` on changed Python files: **PASS**.
- `uv run --locked pyright`: **PASS**, 0 errors/warnings/informationals.
- `npm --prefix frontend run typecheck`: **PASS**.
- `uv run --locked python tests/papers.py`: **PASS**, including local Tectonic generation and mocked compile-fallback/recovery cases. The test's negative path logs an expected provider exception; suite passes.
- `uv run --locked python tests/sovereign_cost_model.py`: **PASS**, 14 tests.
- `uv run --locked python tests/mindrouter_empirical_envelope.py`: **PASS**, 8 tests.
- Direct CLI reproduction: `scripts/sovereign_cost_model.py research/sovereign_scenario_hypothetical.json` and `scripts/mindrouter_empirical_envelope.py`: **PASS**. For the illustrative 17-day envelope, 4,675 kWh × $0.12/kWh = $561; with equal hypothetical useful-success probability the non-electric break-even bound is $3,466–$11,335. These are derived/hypothetical quantities, not full TCO or observed quality.
- Fixed-allocation model: campus-only 787 expected useful successes at $15,898/month; hybrid 891.55 at $19,397; federation 882.40 at $22,831. API-only leaves 250 restricted tasks unserved and fails the scenario's coverage constraint. All success probabilities, capacity and campus/partner costs are invented scenario inputs.
- Optional optimizer reproduced its checked-in results using transient SciPy 1.17.0; no project dependency or lockfile change.
- `./sigma test`: **PASS**, all steps passed, including both economics suites, paper regression suite, Ruff check/format, Pyright, frontend typecheck/build. Total command wall time was about 69.4 seconds across the captured execution waits. The repository's existing graph-present local sandbox scenario was skipped because its sandbox image is unavailable; graph-withheld coverage ran.
- Real Chrome: `browser_checks/issue393_diagram_option.py`: **PASS**. Diagram checkbox defaulted on and persisted both on/off choices after reload. A local API/provider fixture was used; **no inference call was made**.
- Tectonic 0.17.0 compiled both paired TeX sources successfully. PyMuPDF rendered pages for inspection: the seven-page variant's cost plot uses unconnected scenario points and its fail-closed policy figure has readable nodes, routing labels, boundaries and captions. Standard PDF: 6 pages. Diagram PDF: 7 pages.
- GitHub Actions: latest HEAD is visible on the PR, but GitHub currently reports **pending with zero check runs/status contexts**. CI result is not available yet. PR remains Draft.

## Artifacts

- [Offline analysis README](../docs/evaluations/issue_393_394/independent_analysis/README.md)
- [Standard TeX](../docs/evaluations/issue_393_394/independent_analysis/paper-standard.tex) · [Standard PDF](../docs/evaluations/issue_393_394/independent_analysis/paper-standard.pdf)
- [Diagram TeX](../docs/evaluations/issue_393_394/independent_analysis/paper-diagrams.tex) · [Diagram PDF](../docs/evaluations/issue_393_394/independent_analysis/paper-diagrams.pdf)
- [Shared evidence/body TeX](../docs/evaluations/issue_393_394/independent_analysis/paper_body.tex) · [Artifact manifest](../docs/evaluations/issue_393_394/independent_analysis/manifest.json)

SHA-256:

- Standard PDF: `b128dcdca1bee31945500f37efa02f81079156cfc192d72ce57ecec6ace8b9ed`
- Diagram PDF: `a9e0e8ce1bb20183d765813dd52f1fc937909a93f4e6a772982a529539a2fe47`
- Shared body: `9ff8c7c5a453b6bb06d1b48b1c79fdb05974fc9041ac38094e79e8e3114929f8`

## Status

- **MET:** Long-form checked diagrams; table support and prompts; default-on diagram UX; old checkpoint compatibility; regression coverage; Ruff/Pyright fixes; economics suite integration and numeric reproduction; `./sigma test`; local Chrome acceptance; paired TeX/PDF compilation and page rendering; clean branch push.
- **UNMET:** The central research objective is not complete. There is no real saved SIGMA Investigator/Skeptic investigation, no independently judged task-quality benchmark, no real institutional TCO data, and no final pair generated from saved real research. The offline paper is a clearly labeled analysis based on published sources plus hypothetical calculations, not a substitute.
- **UNVERIFIED:** CI for HEAD `471152dd80816a8352fca4e69d936e31e6dc7eb1` has not started/reported yet. Published claims are source-attributed, but there has been no external peer review of the manuscript or its synthesis.

No live or paid provider calls, no new spending, no deployment, and no merge to `main` occurred. No OUT #3 was created. The branch is pushed and ready for coordinator review.
