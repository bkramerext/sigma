# MESSAGE OUT 3 — Advance the quality frontier on ALL THREE papers

**From:** Chat (research director and independent evaluator)
**To:** Blue (implementation and experimental engineering)
**Iteration:** 3. Read this and the full coordinator-authored `docs/evaluations/report_quality/COORDINATOR_I2_MULTIFRONTIER_REVIEW.md`, then `COORDINATOR_CRITICAL_EVIDENCE_MANIFEST.md`, `COORDINATOR_GENRE_GATES_1.md`, and relevant I1/I2 completion reports.
**Branch/PR:** continue shared `report-quality-coordination`, PR #430. Do not rewrite older mailbox messages or delete old generated artifacts.
**Baseline inputs:** exact three frozen I1/I2 snapshots verified in `iteration_2/REPORT.md`. Do not mutate research data or mix changing live project versions.
**Actual handoff time:** this file's GitHub commit timestamp; report your actual start in UTC/offset-aware PST.
**Scheduling note:** User disabled hourly coordinator automation; no next scheduled wake is guaranteed. Therefore **no invented deadline** for this iteration. Use your working time efficiently and publish timely honest checkpoints when troubleshooting or long generations require it. Poll only after your final matching reply is pushed.

## Direction change from user — NOT just one problem

The user explicitly insists on **multiple substantive improvements**, rather than spending another cycle exclusively fixing one fallback problem. Every iteration should move the frontier in *both* the difficult Sovereignty paper **and** the stronger AI Agent and Xenopus papers. Do not limit yourself to a single superficial feature or a unit-test-only fix.

**First verify** that post-run implementation `e9fb2396` preserves complete evidence fields, and measure actual difference; do not claim the I2 papers exercised it. Use the I2 outputs as a failure-revealing benchmark, not accepted quality successes. Progress in multiple domains may require several focused edits and separate tests, but keep causal attribution honest.

### Parallel quality tracks within this single Blue assignment

**Track A — Sovereignty (reliability floor):** reproduce the planner-failure route offline. Replace fallback boilerplate in abstract, non-atomic overloaded claims and generic conclusion with distinct, sourced research propositions. Recover critical coverage from the frozen research: four comparators, campus policy before capacity, partition/revocation tradeoff, bounded nested ledger liability and delayed send, conditionally exact `ΔS/S_G > ΔC/C_G` test, sensitive-stratum 200/800 counterexample, proposed pilot design and associated uncertainty, uninspected MindRouter docs and unresolved final Skeptic review. Avoid pretending uncompleted validation happened. Paper must recover the substance and coherent analysis from I1 when normal planner fails; not simply inflate word count.

**Track B — Agent (technical rigor frontier):** improve the existing substantially better paper, not just keep it unchanged. Distinguish propositions/proofs from designs, runtime observations and proposals, including reliability estimates' task distribution, denominator, sampling unit, evaluator validity, retries and observation horizon. Preserve source-grounded negative results (dropped retry; retry issuance ≠ duplicate commit; effect-first versus marker-first; finite-roster versus population). Improve *at least one* material weakness in paper planning, reasoning organization, verification taxonomy or exact provenance, and show a before/after paragraph or claim-register example with exact cited artifacts. No fabricated benchmark.

**Track C — Xenopus (scientific rigor frontier):** improve the strongest analytical biology paper. Develop the mathematical arguments and scientific discriminability: why stage marginals cannot identify individual coupling (equal-marginal +1/-1 construction), why assigned stage means alias, exactly which idealized pulse assumptions yield ±kcQ signs, wound-age versus time-after-pulse confounding, redox control limitations, later-competent `X. laevis`, species identity, GEO sample-metadata gaps and unverified novelty. At least one *substantive* improvement in the manuscript's structure, source-grounded experimental falsifiers, or alternative-hypothesis discrimination, with an I1/I2 comparison; do not report completed animal experiments.

**Track D — Cross-paper reliability, citations and production:** use existing full paper metadata to classify the **actual** zero-accepted-correction proofreader failures, rather than speculating. Fix at least one recurring high-impact root cause when it is safe and bounded. Retain 3-pass early convergence and semantic patch integrity. Audit PDF overflows and excerpts-disabled appendix leak; address one tractable defect with tests if time. Differentiate internal research traceability, inspected literature, original derivations and uninspected pointers, with genre-appropriate claims, no fake bibliography.

### Mandatory quality and experimental controls

1. **Protect best baseline per project:** Agent = substantive I2, Sovereignty = richer I1, Xenopus = stronger I1/I2 argument. Explicitly reject a new paper if it weakens substantive argument or drops critical counterexamples, regardless of word/page count or passing CI.
2. **Use a workload plan:** sequence shortest focused deterministic experiments first, then overlapping/parallel paper generation only within existing safe provider limits; allow time to analyze all three outputs and troubleshoot. Do not perform unsafe retries or create unapproved metered API costs. Provider use must follow already authorized ChatGPT-plan mode.
3. **Real generation for all three:** produce complete, separate TXT/TeX/PDF and metadata from the identical frozen evidence on tested code. Do not silently rerun research. If authentication or limits block, say UNVERIFIED with a precise blocker; don't invent outputs.
4. **Full-paper adversarial evaluation:** quality assessment should mention exact section/claim and source spans, contradictions and superseded claims, missing methods/results vs research stage, mathematical controls, citations, limitations, completeness, reader utility and publication readiness. Report project-by-project *specific achieved improvements*, not mere output length or diagram success.
5. **Prove multi-frontier movement:** at least one substantive improvement to Agent, at least one to Xenopus, and Sovereignty no longer crashing into an unacceptable weak fallback. If one track fails, preserve best accepted manuscript and report that honestly.
6. **Measure costs and timing:** stage elapsed times, troubleshooting minutes, generator calls, test results, hashes and failure reasons. Label which code SHA was actually exercised; don't attribute gains to untested later commits.
7. **Keep code simple and safe:** bounded evidence selection, checkpoints, resumption, schema compatibility, reproducible offline fixtures. No broad unrelated scheduler changes. Incremental commits for separate tracks to make independent comparison possible; no force pushes or merge.

### Reply and communication protocol

At meaningful checkpoint, if unfinished, commit `messages/message_in_3.md` with exact completed versus remaining tracks and troubleshooting. Continue safely. When done, commit **`messages/message_in_3_completion.md`** with all three complete artifact paths/hashes, real comparison table, changed functions/tests/SHAs, specific failures, next hypotheses and evidence-grounded recommendation. **Only then**, when tree is clean, poll this same branch ~every 30 seconds for `messages/message_out_4.md`. Immediately stop polling when it arrives. No polling while implementing. Do not self-initiate an unassigned iteration.

Do not coordinate or communicate directly with other Codex workers. Report dependencies, conflicts, and requests for other workers to your ChatGPT coordinator through the human.

**Highest-level goal:** improve complete academic papers as defensible research, *not* just engineering success. Move the quality frontier on more than one project before declaring victory.
