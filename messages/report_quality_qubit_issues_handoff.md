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

## Follow-on review: Agent Reliability

Rebuilt from its archived structured draft. An editorial source override condenses the opening correctness/observation section from ten paragraphs to six while preserving the outcome, acknowledgment, automated-evaluator, sampling-cluster, and frozen-roster distinctions and their saved claim links. The first page now has the structured reader guide; the writing-method list no longer occupies the final page. The reviewed PDF has 25 pages (previously 26), no PDF text-bound warnings, and intact claim/source notes. It remains dense and has not been independently validated against a real external service.

## Follow-on review: Sovereign AI Federation

Rebuilt from the archived structured draft with the current production renderer. The 22-page PDF now opens with a reader guide and ends with the claim/source register rather than an editorial-writing-source list. The comparison contract was read and retained: its four alternatives, root-task denominator, and joint success criterion are necessary to make the federation thesis testable. No PDF text-bound warnings were reported. No live federation or task-quality evaluation was performed.

## Follow-on review: Xenopus Tadpoles

The first rebuild added the reader guide but created a nearly empty 16th page of claim notes, so it was rejected. A structured editorial override condensed the repetitive operational-requirements section while preserving the named-state, input-cessation, stage-specific calibration, specimen-provenance, prediction-baseline, and later-recovery limits. The final PDF is 15 pages, includes the reader guide and complete claim/source notes, and has the same page-6 integral-limit geometry diagnostic as the previous version. The rendered formula was visually inspected and is legible. No biological effect or mechanistic discovery is claimed.

## Production authoring guidance

The shared one-shot and long-form publication instructions now ask for an explicit premise → evidence/derivation → inference → boundary chain within each section, short transitions, immediate interpretation of equations and figures, and a normal 450–750-word section range with exceptions for indispensable proof or contrary evidence. This is a production prompt change for future generations. The current archived papers were rebuilt from their saved drafts with separate structured editorial revisions; no live provider run has yet verified that the revised prompt reduces length or improves argument quality on new output.

## Lower-score follow-up: Warp Drive opening

The source-linked opening was condensed from ten paragraphs to six without changing its geometric premises: compactly supported finite-duration profile, Lorentzian coframe, timelike central carrier, matched exterior-clock comparison, global time function, and the distinction between a prescribed metric and a realized source. The PDF is now 20 pages (previously 21). The model equation and local causal-cone condition are displayed separately. This preview exposed a generic renderer bug: punctuation after an explicit `$$...$$` display had been stranded at the start of the following line. The renderer now places that punctuation inside the display, as it already did for automatically promoted long inline equations. The final preview compiled; pages 2–3 were visually inspected; the only text-bound diagnostic is the previously inspected page-5 integral/lower-limit contact.

## Lower-score follow-up: Agent Reliability evidence contracts

The source-linked evidence-contract section was condensed from twelve paragraphs to eight, preserving the external effect/report oracles, conservative outcome-set mapper, predicates for mapper conformance, evidence validity, containment and certification holds, the soundness implication and counterexamples, conditional roster-audit boundary, and the tick-15/tick-18 report-time truthfulness control. The preview compiled to 24 pages (previously 25) with no text-bound warnings. Pages 15–16 were visually inspected. The formal outcome vectors and table were retained; no measured service reliability was inferred.

## Lower-score follow-up: Operation Narrow Passage

A local Round 10 project export supplied the archived structured paper record. Its paper ID and original TeX SHA-256 were checked against the previously tracked pair before use; the compressed complete record and provenance are now in `docs/evaluations/report_quality/additional/operation-narrow-passage-round10/`. The shared renderer rebuilt the paper with a plain-language reader guide, a worked example separating the political deadline from the medical safety window, source-reference labels, compact claim notes, and a three-path conditional comparison table. A branching diagram preview was rejected because the generic graph renderer duplicated its arrows as a numbered list and wasted a page. The accepted PDF has 14 pages (previously 17), no PDF text-bound warnings, and visually reviewed first, table, and final pages. It retains the fictional-scenario and unvalidated-feasibility limits; no operational recommendation was added.

## Lower-score follow-up: Sovereign AI Federation evaluation protocol

The structured editorial source now revises selected paragraphs of the 90-day evaluation while leaving the mathematical estimands, counterexample, interval construction, and decision inequalities intact. The prose explicitly sequences the decision, sampling denominator, success rubric, safety gate, paired design, independent units, and possible outcomes. A reusable paragraph-replacement facility in the local rebuild script limits edits to the selected source paragraphs. The evaluation diagram's edge labels were shortened after a rendered preview showed awkward hyphenation. The promoted TeX/PDF pair compiles to 22 pages, has no PDF text-bound warnings, and pages 16–20 were visually inspected. No pilot has run, and the statistical proposal has not been independently validated. Provisional presentation score: 62 → 65/100, reflecting clearer signposting and figure legibility; evidence strength is unchanged.

## Lower-score follow-up: Agent Reliability measurement comparison

The structured source now leads its measurement section with the exact reliability question, marks the shift to directional improvement inference, distinguishes the frozen-roster target, and closes by comparing the evidence each certificate needs. The mathematical bounds, assumptions, and preexisting evidence-contract table remain in place. An initial preview added a second comparison table, but visual inspection showed that it repeated the existing one; that preview was rejected and the duplicate removed before promotion. The final TeX/PDF pair has 24 pages, no PDF text-bound warnings, and pages 3–7 were visually inspected. No outcome audit or controlled comparison was performed. Provisional presentation score: 58 → 60/100; the gain is signposting, not stronger scientific evidence.
