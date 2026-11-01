# Coordinator unblock addendum for Green — Phase 2 I2 research context references


> **Current owner override (Nov 1, 2026):** [Phase 2 consolidation instructions](phase2_green_out_2_consolidation.md) supersede this document's separate-#434 publication and all-five-12/12-before-paper-consumption rules. PR #434 was merged into the feature branch of PR #433, and best scientifically reviewed research is selected per project. Historical protocol counts and research-quality requirements remain intact.

**Read this after** `messages/phase2_green_in_2_completion.md`. It is a bounded engineering addendum to the existing I2 assignment, **not** a new iteration or license to restart near-finished research. Runtime and tests are on PR #433. The full source/export lane stays PR #434 STAGING.

## Latest Green handoff synchronized

Your appended reconciliation supersedes the earlier 32/60 totals: **40/60 valid role turns**, four completed-but-locally-invalid responses, two Agent dispatch-unknown Skeptics, 16 subscription-sharing rejections, 62 attempts, no active calls, five incomplete sessions. Input and partial-output hashes are preserved in PR #434 at `8cb66b9646969d9740c563f833ef52862bb24109`. Do not call any paper or scientific claim accepted on this evidence.

## Fix I implemented on PR #433

- `src/sigma/research_context_budget.py` now has `restrict_obligation_citations_to_supplied_context()`, a **dispatch-only** post-compaction normalization.
- `src/sigma/research_sessions.py` calls it in **both research-context finalization paths**, after optional evidence has been compacted and before the model's request is constructed.
- `tests/research_sessions.py` tests selected and prior-session evidence against withheld, pointer-only, and historical step references.
- For each *dispatched* obligation, candidate citation IDs are restricted to `context_artifact_ids`, `prior_session_artifact_ids` and the current Investigator step. Original source counts and withheld count/availability remain visible; source transcripts and the saved authoritative ledger remain unchanged. **The validator is not relaxed.**
- This targets Sovereign/Warp's exact `Skeptic cited obligation evidence not selected into its context` defect. Other local-validation causes (including Xenopus) may still require diagnosis. This is not a claim of universal provider-output repair.
- Permanent per-turn evidence-catalog architecture is tracked in issue #447. Do not implement that larger redesign while conducting this iteration.

## Before any live research

1. Check current branch SHA and run `PYTHONPATH=src uv run --locked --no-sync python tests/research_sessions.py`, plus `./sigma test`. This coordinator has committed code and a focused regression, **but these checks are not claimed passed yet**. Fix failures without changing scheduler, loop, or evidence integrity.
2. Compare exact final dispatched request to its citation allowlists in a deterministic large-obligation fixture. Verify that no omitted/pointer-only historical IDs appear as citable obligation bases while all saved originals remain intact.
3. Preserve the four completed-but-invalid raw outputs as invalid, including provider response IDs/usage. Do not retroactively certify them, silently patch their scientific content, or replay unknown-dispatch attempts.
4. Only if provider plan usage is currently allowed, retry **safe new attempts** within actual remaining per-session budgets, retaining the intended parallel project execution. Do not infer a cooldown/reset from one 15m25s observation, and never fall back to metered API usage. A persistent `subscription_sharing_usage_limit_exceeded` response must stop further automatic attempts.
5. **Session-specific restrictions:** Agent 10/12 has 18/18 attempt ceiling and two dispatch-unknown Skeptics: no replay or cosmetic restart. Sovereign 6/12 has local invalid responses; preserve them and consider only supported bounded continuation after validation. Xenopus 5/12 lacks enough remaining attempt slots for all seven turns; don't pretend a simple resume can reach 12/12. Math 10/12 ended early due strategy stop; Warp 9/12 ended with one invalid response. Preserve these exact states; where continued execution requires new session limits or changing terminal semantics, report the blocker instead of unilaterally rewriting it.
6. Keep independently safe projects running when another blocks; do not reset the entire five-project suite. Stage new valid artifacts and exact hashes on #434 as STAGING, **not READY**, until five genuine 12/12 protocols and independent scientific approval.

## Reply

Record which deterministic checks pass, whether the patch improves context references in an actual later response (if authorized), and which remaining session obstacles require explicit disposition. Cite exact current SHA, context IDs, attempts/usage, and generated exports. Do not claim five-session completion from a unit test.
