# Evidence index and reproduction

The human-facing reports are one directory above. This directory preserves raw observations so that the prose is reviewable. Do not mistake the large amount of retained text for a large amount of intellectual progress.

- `browser-inventory.json`: all 17 samples, exact Chrome version, isolated copy paths, session inventory, actual per-capture times, mobile widths, source SHA-256 values and page errors. Capture time excludes reading and assessment.
- `<slug>-workspace.txt` / `-expanded.txt`: initial stock browser text and fully expanded saved research sections. Sixteen have no stock sessions; Nonconsecutive has five deterministic fixtures.
- `<slug>-report.txt`: actual Text file download from each initial browser state.
- `<slug>-continuation.txt` / `-continuation-report.txt` / `-recent.txt`: evaluator-authored continuation, downloaded report and Home Recent state.
- `continuations.json`: plans, manual save/reload/toggle/reopen results and request inventory from the completed continuation pass. This does not represent an uninterrupted first attempt: navigation automation was corrected during pilot passes, with already saved evaluator plans preserved.
- `<slug>-settings.txt` / `-limits.txt` / `-generation-preflight.txt` / `-paper-preflight.txt`: actual dialog/form text. The generation form was opened but never submitted; paper setup was viewed but no authoring was submitted.
- `deep-observations.json`: actual prior-source navigation, findings-fork prefill, saved binary-counting parameter adjustment, HTML browser inspection and final source-hash comparison.
- `maximum-regions-archive-*`: supplementary original historical provider record rendered in current UI, separate from the empty stock sample. The only relocation is its saved `project_path`; no argument enrichment. HTML is a downloaded research report, not an AI-authored paper.
- `independent-checks.json`: evaluator arithmetic outside SIGMA. Its source explicitly states this boundary.
- `SOURCE_CHECKS.md`: external evaluator source-access attempts and limits.
- `sigma-test.txt`: complete actual successful offline test run on evaluated app `6059d67`, including scenarios, Ruff, format, Pyright, frontend typecheck/build. `sigma-test-post-merge.txt` records the second full passing run after merging main `e7fa678` for review integration; it does not expand the scored browser coverage.
- PNGs: selective new viewport captures, not stitched representations of every screen. Mobile emulation is not physical-device testing. Initial full-page captures were intentionally replaced to avoid bulky transient artifacts; initial text dumps remain.

## Reproduction

Use an isolated checkout of app revision `6059d67` with the repository's normal dependencies, `uv`, npm, Playwright and installed Google Chrome. The scripts were research instruments, not additions to SIGMA or a general regression suite. Run them from the repository root. Review the fixed scratch root and ports first; ports 8067 and 5267 must be unused. They do not stop other servers or access personal auth.

```sh
uv run python docs/evaluations/RESEARCH_EXPERIENCE/evidence/scripts/isolated_server.py
```

In a second terminal:

```sh
SIGMA_API_TARGET=http://127.0.0.1:8067 npm --prefix frontend run dev -- --host 127.0.0.1 --port 5267 --strictPort
```

With both running, execute sequentially:

```sh
uv run --with playwright python docs/evaluations/RESEARCH_EXPERIENCE/evidence/scripts/catalog_pass.py
uv run --with playwright python docs/evaluations/RESEARCH_EXPERIENCE/evidence/scripts/continuation_pass.py
uv run --with playwright python docs/evaluations/RESEARCH_EXPERIENCE/evidence/scripts/archive_pass.py
uv run --with playwright python docs/evaluations/RESEARCH_EXPERIENCE/evidence/scripts/deep_pass.py
python3 docs/evaluations/RESEARCH_EXPERIENCE/evidence/scripts/independent_checks.py
env -u SIGMA_CLOUD_BOOTSTRAP_ADMIN_EMAIL ./sigma test
```

These scripts write evidence files and disposable working copies; run in a study checkout to avoid overwriting the reviewed evidence. `isolated_server.py` removes inherited SIGMA/provider configuration, sets private owned state/auth directories, does not load dotenv, and rejects outbound asynchronous provider HTTP transport. It imports the real API. Browser routes forward only local API traffic with the same allowed-origin adaptation used by existing repository Chrome checks. This adaptation is test setup, not a bypass used against another service. Read-only external literature retrieval is not part of the scripts.

The initial pilot hit a Recent-state permission error because the evaluator created a scratch directory with ordinary permissions; changing it to 0700 fixed setup. Another pilot hit the API's expected origin rejection on the nonstandard test port; forwarding with the approved local origin fixed setup. Neither is reported as a normal-product defect. The selected Samples tab's collapse-all behavior, by contrast, is intentional product behavior and is assessed as a discoverability issue.

No fresh provider research, AI papers, live OAuth, active-session pause/resume/stop, agent feedback uptake, or new Python/Sage sandbox run was exercised. Historical recorded computations and the evaluator's arithmetic remain distinct. Stop only these isolated terminal processes when done; no canonical samples need cleanup.
