# Increment 1 verification evidence

This is new, narrowly scoped implementation evidence; the earlier PR #74 study
was read from its branch and was not copied or merged into `blue_session`.
The initiative report is [RESEARCHER_CENTERED_SIGMA](../../RESEARCHER_CENTERED_SIGMA.md).

## Actual coverage

`browser_checks/epistemic_integrity.py` launches isolated real API and Vite
processes, with private temporary project/state/auth roots, no dotenv loading,
scrubbed provider configuration and a rejecting external HTTP transport. Installed
Chrome 156.0.8078.47 is driven through Playwright. The original Maximum Regions
archive is copied with only `project_path` relocated; no argument enrichment or
fabricated steps. Four explicitly synthetic declaration variants exercise
`incomplete`, `unknown`, `verified` and missing verification, without representing
new research. The Nonconsecutive sample is opened through Home and supplies its
five archived deterministic sessions. This is not a live-provider quality test.

For each declaration, the browser checks Conclusion source/rendered modes,
normal/rendered Outcome, detailed Solution review, Status and Metrics against the
service label. It checks the historical availability notice, inspectable original
Skeptic prose and 1440px/390px layouts. It confirms no JavaScript errors, no
inference POSTs, unchanged original source hashes and unchanged copied archive
session files. Processes and temporary projects are removed after the check.

- [Observation ledger](observations.json): exact declarations, browser version,
  source hashes, widths and no-inference results.
- [Historical archive at desktop](archive-1440.png) and [390px](archive-390.png).
- [Incomplete declaration at desktop](incomplete-1440.png) and [390px](incomplete-390.png).
- [Deterministic subset fixtures at desktop](nonconsecutive-1440.png) and [390px](nonconsecutive-390.png).

## Commands

```sh
uv run python tests/project_reports.py
uv run python - <<'PY'
import runpy
checks = runpy.run_path('tests/research_sessions.py')
checks['test_epistemic_presentation_is_conservative_and_read_only']()
checks['test_outcome_classification']()
PY
npm --prefix frontend run typecheck
uv run pyright
SIGMA_EPISTEMIC_EVIDENCE=docs/evaluations/INCREMENT_1 \
  uv run --with playwright python browser_checks/epistemic_integrity.py
env -u SIGMA_CLOUD_BOOTSTRAP_ADMIN_EMAIL ./sigma test
```

Focused report regressions cover text, HTML and TeX source, including stale cached
metrics, structured/unstructured representations, unknown/unrecognized/missing
fields and provenance-cautious `verified`. Session regressions cover the same
status matrix in ended/failed records, partial and absent results, generated
Conclusions, public projection, metrics and input immutability. Existing broader
session and report scenarios run in the full suite.

The first browser pilot could not launch a missing `uvicorn` executable; using
`python -m uvicorn` fixed the harness. A later pilot's final hash comparison also
counted the newly created subset working copy against the preexisting archive
inventory. The final check compares the original files individually. The browser
assertions themselves passed before that harness correction; the corrected
complete run also passed. These were test-instrument issues, not app defects.

No new paid/live calls, sandbox experiments, independent checker execution,
AI-authored paper, PDF compilation or physical-device testing is claimed.

## Results

**PASS:** focused report tests; session status/archive/classification and
Conclusion regressions; standalone frontend typecheck; standalone Pyright;
complete `./sigma test` (including Ruff/format, Pyright, typecheck and build).
[Full final suite output](full-suite.txt) preserves actual commands/results.
The success fixture for generated Conclusions now explicitly declares its
agent-reviewed state; the separate unknown/missing regressions verify that its
absence cannot silently establish a positive candidate. A tightening run caught
that old fixture assumption before correction; no failing check is reported as
passed.

The Chrome check passed its complete assertion set, including statuses and both
viewports; [browser output](browser.txt). No actual model inference, independent
verification or fresh scientific discovery was tested. The original archived
provider record and deterministic fixtures remain different evidence classes.
