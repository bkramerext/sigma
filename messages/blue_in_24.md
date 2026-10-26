# Blue issue #119 — longitudinal research evaluation design

**Issue:** [#119](https://github.com/bkramerext/sigma/issues/119)
**PR:** Pending creation; branch `blue/issue-119-longitudinal-evaluation` → `main`
**Base reviewed:** `537c198` (includes merged T146 PR #150 and T147 PR #164)

## Win

Read issue #119 and the current T114/T118 and Increment 21 framework. The existing SIGMA production-path offline tests demonstrate persistent context assembly, source IDs, later-session evidence reuse, immutable historical sessions, computation failure/completion provenance, approved cross-strategy transfers, and rejection of foreign, truncated, stale, and misrepresented evidence. Focused tests passed.

Added `docs/evaluations/issue_119/longitudinal-design.md`: a proposed 2×2 factorial design separating history availability from role organization. It uses six independent task families, three staged sessions, two branch strategies, and a capable full-history single-role baseline with equivalent evidence/tools. It predefines quality, continuity, branch-decision, negative-evidence, repetition, cost, blinding, and provenance measures. At two repeats per task/condition and two calls per session, the maximum is 288 call attempts.

## Expectations

The engineering checks establish that the architecture can persist and gate information in scripted scenarios. They do not establish that models use that information effectively or that persistence improves research quality. No product defect was reproduced; no product correction was made. T146 is one within-session cycle and T147 identified missing task context in its baseline's stateless turn-2 request; neither is longitudinal evidence.

## Remaining

This is a proposal, not a frozen or executed model-quality study. Six task clusters support only exploratory results. New task/key curation, information-equivalence and isolation audits, independent blinded grading, exact provider/model and spending caps, and separate owner authorization remain required. No provider calls, Cloud actions, or live research sessions occurred. No actual project was exercised, so no SIGMA project export was created.

## Verification

- PASS: `uv run --locked --no-sync python tests/epistemic_continuity.py`
- PASS: `uv run --locked --no-sync python tests/continuations.py`
- PASS: `uv run --locked --no-sync python tests/research_feedback.py`
- PASS: `git diff --check`, Ruff, format, Pyright (0 diagnostics), frontend typecheck.
- `./sigma test` exited 1 on three existing T128 mount assertions in `tests/deployment_package.py`, `tests/gce_host.py`, and `tests/host_monitor.py`; all expect the former escaped unit dependency while merged `main` uses `RequiresMountsFor=/srv/sigma-state`. The runner skipped frontend production build after those failures.
- No browser check was relevant because no product/UI workflow changed.
- No self-merge.

Full design and evidence classification: `docs/evaluations/issue_119/longitudinal-design.md`.
