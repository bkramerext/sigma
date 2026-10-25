# Actual SIGMA project exports — Increment 3

Application: `373f564ab957a2f13db298c4190e2e29893328b9`. Transport: offline scripted HTTP; **0 live calls / $0 actual cost**. Six new sessions, 21 HTTP attempts, 20 completed role steps, 1 interrupted step, 10 new artifacts. Saved-session observation window: 13.444s; this excludes export/setup and later read-only inspection.

All `.audit.json`, `.current-understanding.json`, `.report.txt`, `.report.html` and `.report.tex` files below are actual SIGMA API response bytes. They were not reconstructed from this manifest. The Markdown assessment/evidence table is evaluator-authored and is not represented as a native SIGMA Markdown report.

| Project | Before | After | Actual activity |
|---|---|---|---|
| nonconsecutive-subset-sums / `1e8625bf-12fd-4148-8db9-8878895466fd` | [subset.before.audit.json](subset.before.audit.json), native [TXT](subset.before.report.txt)/[HTML](subset.before.report.html)/[TeX](subset.before.report.tex) | [subset.after.audit.json](subset.after.audit.json), native [TXT](subset.after.report.txt)/[HTML](subset.after.report.html)/[TeX](subset.after.report.tex) | evidence_off: `eae3bc83-ff07-4325-89ff-6ae635d67f7b` (4 calls); evidence_on: `d6e51a2f-5501-4813-9eb4-7805e9106a63` (4 calls); negative_transfer: `d4c4b994-f9ff-4319-a05b-b976a01c0e62` (4 calls); stop_reload_restart: `63c41856-13d8-43fc-b4a1-84e51d72b6e6` (3 calls) |
| riemann-hypothesis-research / `7f377e9a-0ea4-4005-863c-a02819db09cd` | [rh.before.audit.json](rh.before.audit.json), native [TXT](rh.before.report.txt)/[HTML](rh.before.report.html)/[TeX](rh.before.report.tex) | [rh.after.audit.json](rh.after.audit.json), native [TXT](rh.after.report.txt)/[HTML](rh.after.report.html)/[TeX](rh.after.report.tex) | evaluator_injection: `fb5852e7-80b6-448d-a5e9-297c25dcea8e` (2 calls); approved_followup: `64ad9713-295c-46a6-9ce3-82290ab507b9` (4 calls) |

Subset before-state: five pre-existing deterministic fixture sessions; one additional previously saved manual strategy without a session. RH before-state: fresh stock project and original strategies, zero sessions. New strategies/injection are researcher/evaluator-authored; new role outputs are scripted. Neither is a fresh agent discovery.

The JSON manifest records all project/session IDs, copied-source provenance, isolated paths, limits/omissions and report references. Exact source/call/artifact paths are in [the evidence table](../EVIDENCE_TABLE.md). Native Markdown reports, PDF, AI-authored paper quality and real-provider reasoning are untested/unsupported as identified there. No new live work is authorized.

Retain the working project’s `continuations/` companions when copying it. Packets are also copied into new sessions and exported at top-level `continuations`. Stock-sample conversion of approval-bearing exports is explicitly refused to avoid silently losing lineage. Historical report text is preserved.

Capture revision is above; publishing/evidence commit SHA is recorded in `messages/blue_in_3.md`. The next commit that contains that message is report-only.
