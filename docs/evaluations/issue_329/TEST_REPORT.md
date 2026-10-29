# Issue #329 independent test report

Base under test: implementation commit `6fbd6ae914f352dd20a1525b0255342991847181`.
Test branch: `blue/329-paper-test-pyramid`. This branch changes tests, a local
deterministic provider fixture, browser acceptance, and this report only.

## Findings

| Acceptance area | Result | Evidence |
| --- | --- | --- |
| Evidence provenance, negative/contradictory results, numeric/short evidence, open proof obligations, bounded index and omissions | MET | `tests/papers.py` adversarial ONP-shaped synthetic record tests |
| Research-type-specific TeX styles | MET | deterministic default, mathematical, military, and biology style checks |
| Safe pre-dispatch retry vs unknown post-dispatch consumption | MET | mock call accounting and retry tests |
| Concurrent sections, ordered durable checkpoints, resume without replay, cancellation, duplicate admission | MET | controlled asynchronous provider fixtures in `tests/papers.py` |
| Stale snapshots, legacy checkpoint migration, compiler/publication failures | MET | existing and extended local paper tests |
| Responsive browser progress, retry, Continue, incompatible restart, PDF | MET | `browser_checks/issue329_fast_paper.py` in real Chrome against local fixture |
| Five-session Tadpoles-shaped mock project to PDF under five minutes | MET (mock only) | local deterministic run completed in 0.37 s during full-suite run; Tectonic PDF produced |
| Tadpoles representative live-provider five-session target | UNVERIFIED | no live representative run was authorized or made |
| ONP mathematical argument fidelity on the actual production project | UNVERIFIED | synthetic ONP-shaped evidence was used; no project export or live model run was used |
| Full suite on updated implementation branch | UNMET | `./sigma test` has one formatting check failure described below |

## Commands and actual results

- `.venv/bin/python tests/papers.py` — PASS; deterministic five-session mock
  paper-to-PDF run completed in 0.34 s on the focused run and 0.37 s in the
  full-suite run. These are mock timings, not a live-provider SLA result.
- Ruff check and format for the three changed test/fixture/browser files — PASS.
- `.venv/bin/pyright src/sigma/papers.py tests/papers.py` — PASS (0 errors,
  0 warnings, 0 informations).
- `browser_checks/issue329_fast_paper.py` — PASS in real Chrome against the
  deterministic local fixture: normal long-form progress and PDF, safe retry,
  narrow-screen provider failure with Continue, changed-snapshot restart, and
  PDF completion. No provider service was contacted. The incompatible-restart
  screen is preserved as [`browser-incompatible-restart.png`](browser-incompatible-restart.png).
- `./sigma test` — FAIL on the updated target branch because `ruff format
  --check` reports `src/sigma/papers.py` would be reformatted. The prior
  `tests/cloud_research_api.py` failure is resolved by the target branch's
  structured-path fixture update. Ruff check, Pyright, cloud research API
  tests, and frontend typecheck passed. The production frontend build was
  skipped by `./sigma test` after the formatting failure. Production source is
  outside this testing assignment and was not edited.

The remaining suite steps completed where safe. The optional graph-present
epistemic-continuity scenario was skipped because the required local Python
sandbox image is unavailable.

## Gaps and handoff

No paid inference, external provider calls, or credentials were used. The
Tadpoles timing target is verified only for deterministic local fixtures. The
ONP checks establish that the pipeline retains source IDs, skeptic objections,
negative and contradictory evidence, and unresolved proof obligations in a
bounded synthetic example; they do not assess whether a real model produces
mathematically correct ONP research. Implementation owners should update the
cloud research API fixture for the structured fast path and format/lint
`src/sigma/papers.py`; rerun `./sigma test` after those fixes.
