# Coordinator-owned SIGMA research work: Increments 8–12

**Base:** `main` merge `617570bbb8c7bf000c294d528b120d5f51800b77` (reviewed cumulative Blue Increments 6–7, PR #80). **Implementation branch:** `coordinator/research-increments-8-12`, draft [PR #82](https://github.com/bkramerext/sigma/pull/82). **Owner:** ChatGPT coordinator; Blue/Codex remain paused. No paid model/provider calls, cloud provisioning or new research execution was authorized or performed.

## Increment 8: carry a bounded, sourced question across sessions

**Problem observed:** Increment 7's saved graph follow-up contained a specific Skeptic `next_question`, but a new same-strategy session reset to generic “Advance this strategy...” wording. Under the existing `coordinate_decision`, budget exhaustion deliberately clears the artifact's active `next_question`, even though the original Skeptic's proposed next question is retained in `skeptic_output.next_question`. An unscripted role might recover it from the prior finding index, but that choice has not been observed.

**Change:** `src/sigma/research_sessions.py` now selects the latest *eligible* per-strategy, terminal saved artifact when starting a new session. It reuses `artifact.next_question` where still actionable, or the original Skeptic proposal after budget exhaustion. The proposal must be in the frozen, strategy-scoped prior finding index. A newer ineligible terminal artifact blocks fallback to stale older suggestions. The source carries its session/artifact/strategy IDs, exact source field and `model_suggested_unverified` qualifier. This is **a question, not evidence, approval, verification or proof**. It appears as `initial_question_source` in the immutable session snapshot and `question_source` in first-cycle role dispatch, while later cycles can change the active question without making the initial provenance stale. Explicit researcher-approved continuations take precedence. No original session is edited.

**Adversarial controls:** `tests/research_sessions.py` exercises (a) newer-vs-older and missing/foreign source rejection; (b) retracted, decisive-counterexample, productive-conclusion and no-progress exclusions; (c) a real saved two-role offline session whose budget ends with a nonempty Skeptic question but empty artifact active question; (d) next multi-strategy session with scoped carry and unrelated history inquiry retaining its generic question; (e) actual first Investigator HTTP context containing the exact question and source IDs; (f) prior session byte-for-byte immutability and researcher-approval precedence. Model roles are deterministic fixtures. This is domain-general logic; no graph/parity answer strings or benchmark-specific hooks are used.

**Actual commits:** `20b378c` implementation, `1f10e15` initial controls, `088f528` dispatch race correction, `02bd0e4` / `b48e680` initial-question provenance clarification, `31e7cd7` / `fe8d8a2` synthetic approval fixture correction. All are on PR #82; exact current head must be checked before integration.

**Verification:**
- **MET (source/code inspection):** Session selection, source IDs, priority of approved continuations, and no mutation of old records are directly represented in the changed implementation.
- **MET (negative test detection):** Initial CI `40182283261` failed in the new synthetic approval fixture with `KeyError: 'parent_strategy_id'`, *not* in the carry logic; the fixture was corrected to include the packet fields required by native Outcome rendering. This failure is retained, not described as a pass.
- **MET (engineering regression):** GitHub Actions [run 40182584352](https://github.com/bkramerext/sigma/actions/runs/40182584352) **passed** `./sigma test` on app-code/test head `bb448c6` after correcting the synthetic approval fixture and applying Ruff formatting. The suite exercised real persisted dispatch with offline role fixtures and the existing project-wide regressions. This is an actual CI execution, not an independently run local test or a live unscripted provider experiment. No new real Python/Sage experiment was needed to test question selection.
- **UNVERIFIED (research usefulness):** We have not measured whether a real model actually pursues the carried question productively, whether source context is sufficient, or whether a matched-budget single-role baseline performs as well.

**Elapsed:** Began 2026-10-25 **02:46:47 Pacific** (09:46:47 UTC); completed app-code/test review and CI at **02:58:13 Pacific** (09:58:13 UTC), approximately **11 minutes 26 seconds**. This included source implementation, independent diff review, test writing, PR creation, two substantive fixture corrections, Ruff formatting, and CI failure diagnosis. GitHub runner wall time is separate from coordinator execution time. No Codex or provider calls were made.

**Would I use it?** For a bounded investigation, I prefer a sourced, specific next action to a generic reset, particularly when a round budget was exhausted. I would not treat the model's question as a valid research direction merely because SIGMA carried it. The agent must still examine the source and unresolved objections, and a researcher-approved continuation must override the automatic suggestion.

## Increment 9: provenance before authored conclusions

**Observed gap:** A saved Conclusion and exported report put fluent agent-authored claims before the saved execution ledger. A graph-withheld control from Increment 7 demonstrated the hazard: an authored Conclusion could imply computational support even when no code executed. This is a **presentation/provenance gap**, not evidence that a model's text can be reliably classified by keywords.

**Implementation:** A read-only `execution_provenance(record)` inventory derives execution IDs, runtimes, statuses, owning artifact/step IDs, source presence and output presence from saved Investigator artifacts, provider steps and pending branch executions. It deduplicates repeated references to one execution and refuses to count conflicting saved statuses as completed. Missing execution IDs remain explicit. It neither interprets the program output nor asserts that a successful run verifies an authored claim. `_outcome` exposes this inventory without rewriting historical sessions. The existing Simple and Advanced Outcome UI now displays the recorded-computation prelude *before* the authored Conclusion. TXT, HTML and TeX project reports render the same provenance inventory before the narrative, with a clear zero-record statement when no execution was persisted. Authored conclusions are preserved verbatim; noncomputational reasoning remains available, not automatically downgraded.

**Adversarial controls:** `tests/project_reports.py` checks a falsely confident model-authored measurement claim with zero persisted executions, ordering across TXT/HTML/TeX, one successful Python execution referenced twice (deduplicated), a timed-out SageMath execution, inconsistent statuses for one ID, and an unidentified execution. `tests/research_sessions.py` checks derived Outcome provenance and source-record immutability. These are synthetic records and scripted controls, **not** autonomous model research. No stock sample was modified.

**Commits:** `c6360aa` conservative inventory; `aa0f04b` Outcome projection; `6f5be40` report ordering; `8129ce0` UI ordering; `9b2ad5b` minimal copper/dark styling; `1e209d0` report regression controls; `cb9a112` Outcome test; `032361f` complete synthetic fixture; `e01dc59` tolerate absent legacy collections. Final CI status must be checked on the **latest head**, including this audit update.

**Assessment at checkpoint:**
- **MET (implementation inspected):** An explicit persisted-execution ledger now precedes authored Conclusion in the UI and all report formats; provenance derives from saved records, not from model prose; duplicate IDs are not double-counted.
- **UNVERIFIED (CI pending):** Full test suite and frontend build on final exact head, until GitHub Actions finishes. No local or paid provider run was performed.
- **UNVERIFIED (semantic claim verification):** The inventory does not prove that a specific conclusion is justified by a recorded computation. It is intentionally not a natural-language entailment checker. Human readers must inspect source/output and claim scope.
- **UNVERIFIED (research benefit):** No blinded unscripted, matched-budget baseline or usability evaluation.

**Time and cost:** Began approximately 2026-10-25 03:44 Pacific; source/test implementation checkpoint at approximately 03:48 Pacific (~4 minutes), excluding GitHub runner time and subsequent CI correction/review. No Codex, live model-provider call, or cloud resource was used. The incremental complexity is one small shared read projection, one read-order prelude, and report rendering; no new research agent or workflow.

## Remaining work (not yet complete)

- **Increment 9 — IMPLEMENTED, CI PENDING:** Provenance-first Outcome/report with explicit persisted execution inventory. Research usefulness and semantic entailment remain UNVERIFIED.
- **Increment 10 — UNMET:** Domain-general assumption and evidence-readiness boundaries, selected only after auditing actual deficiencies and complexity.
- **Increment 11 — UNMET:** Cross-domain offline continuation controls with different epistemic standards, including science, history, and scenario work; no scripted fixture should be described as autonomous judgment.
- **Increment 12 — UNMET:** Final cumulative CI/reproducibility and quality review, matched-budget blind gate *design* without unauthorized paid execution, clean PR and integration recommendation.

**Research-quality status:** A matched-budget, unscripted blinded comparison remains **UNVERIFIED**. Twelve is a planning horizon, not a completion quota. No work has been merged from PR #82 into main.
