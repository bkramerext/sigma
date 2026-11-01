# Coordinator adversarial review of Blue H2-A candidate ranking — in-flight risk, not a result

**Prepared:** 2026-11-01 ~05:00 PST, after inspecting Blue implementation commits `7cb20f9e33e285b95f75d6f359fa6d7df68d83f4` and `d8a325841e4c08f0659a078ba3dee93cfc1a3ff7`. **Blue is still working; no regenerated three-paper output has been reported.** This is a coordinator-owned code-review finding, not a new numbered assignment or permission to advance iteration 3.

## Positive direction

Blue's change replaces `next(note)` with a ranked candidate, strips `path:` from claim statement text, rejects obvious operational paths, and builds a claim-specific fallback conclusion. Its first fixture verifies that a saved substantive result and counterexample outrank two operational metadata fields. This directly addresses the worst baseline Agent defect.

## Adversarial counterexample: punctuation is not proof of complete evidence

The current `candidate` function treats any `path: value` fragment as a complete sentence if it has at least 35 characters and ends in `.`, `?` or `!`. It assigns a score based on `note.kind` and length (up to 260 characters). But `_structured_evidence_index` cuts long original arguments into approximately **410-character fragments**, without sentence-boundary preservation. A fragment beginning **mid-proof** can end in punctuation and outscore a shorter, complete, decision-critical result.

**Deterministic standalone reproduction of the current scoring formula** (not an executed SIGMA paper run):

- Legitimate result: `investigator_output/result: The observed system behavior requires a durable effect ledger before an acknowledgment can be treated as verified completion.` → **score 46**.
- Middle fragment: `investigator_output/proof/2: and therefore the last step is accepted only if the earlier unobserved premises were satisfied. This fragment begins in the middle of an argument and omits the quantifiers and assumptions that determine its validity.` → **score 50**.

Both have kind `result`, both end in periods; the **incomplete fragment wins**. Stripping its field label then conceals that it was part 2 of a larger proof. The fixture in Blue's current test covers an incomplete fragment **without terminal punctuation**, so it does not catch this case.

**Minimal acceptance test to add before trusting the ranker:** two notes from the same source, one complete substantive result and one later fragment with a terminal period but missing premises. Assert the latter is not promoted to a central claim or abstract. Use original field spans/fragment indices or a conservative provenance rule; a longer-sentence heuristic is not enough. Preserve the original complete argument and decisive final step as archived evidence.

## Additional risks to verify, not yet proven failures

1. **Domain brittleness:** rejecting `preflight_error`, `failure_kind` or `ui_` everywhere can suppress legitimate engineering research *about* those failure classes. Test a project whose scientific question is an operational failure mechanism, not just a paper about unrelated biology.
2. **Question loss:** the same punctuation/length filter is applied to open obligations. A concise, imperative research obligation without a final period may be silently omitted from the authored list, even though it remains in the frozen archive.
3. **Conclusion quality:** the new fallback conclusion concatenates up to three claim statements and truncates to 1,200 characters. It is more specific than baseline boilerplate but is not necessarily a coherent, syntactically complete synthesis; inspect the generated Agent conclusion and its source links.
4. **Controlled A/B:** Sovereignty and Xenopus likely use successful model-generated plans rather than the fallback; they are **negative controls for regression**, not evidence that the fallback change improves all disciplines. Their new text may differ because inference is nondeterministic even with frozen inputs.

## Disposition

No claim that Blue's code is defective in the actual new manuscript is made until the three generated outputs are inspected. This is a **specific deterministic failure mode of the candidate scoring rule** and a high-value focused test opportunity. Do not turn the next iteration into a broad rewrite or add model calls to patch a deterministic issue. The coordinator's current `message_out_2.md` already requires a fragmented-proof negative control; this note refines what that control must cover.
