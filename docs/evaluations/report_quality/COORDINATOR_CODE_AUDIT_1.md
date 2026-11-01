# Coordinator code audit 1 — false-positive contradiction warnings and epistemic schema gap

**Prepared:** 2026-11-01 ~03:45 PST. **Read-only review** of `src/sigma/papers.py` at branch state inspected this turn. This identifies concrete implementation mechanisms behind the first Sovereignty manuscript's status warnings. **No runtime change is authorized before the three-project baseline is complete.**

## Confirmed defect: global contradiction-marker leakage

In `_validate(draft, package)`, around lines **2323–2370**:
1. `source_map = {item["id"]: item["data"] for item in package["sources"]}` is correctly built.
2. `source_text = json.dumps(package["sources"], ensure_ascii=False).casefold()` serializes **every source in the entire paper**, before iterating claims.
3. For **every** claim labeled `established`, the code checks `if any(marker in source_text for marker in ("counterexample", "contradicts", "contradictory", "refutes", "disproves"))` and appends the warning `{claim.id} is labeled established while the frozen evidence contains counterexample or contradiction language`.

This check is **not claim-local**: a counterexample concerning C13 in one source can cause a warning on a completely unrelated C2 definition or C11 algebraic identity. Its text suggests a source-claim conflict that has **not been established**. The first Sovereignty metadata has exactly four such warning strings, for C2/C3/C7/C9; they cannot be counted as four verified claim-specific contradictions. The other five warnings about unverified/conjectural source statuses use each claim's `evidence_refs`, although they too may include unrelated nested fields.

**Minimal reproduction:** two independent evidence sources, A containing the word “counterexample” about hypothesis A and B containing only the definition of B; an `established` B claim referencing **only B** still receives the global contradiction warning. This is a deterministic logical consequence of the source-global scan, not a hypothesis about model behavior.

**Safe correction after baseline:** restrict candidate contradiction search to the **claim's cited source data**, and name it only as a lexical **review prompt**, not a verified contradiction. Better: use structured contradiction/retraction links with exact artifact and target claim IDs, then flag only when an actual linked counterclaim applies. Preserve a separate global `paper_contains_conflicts` signal for paper-level review, without attaching it to every established claim. Do not delete a genuine negative finding to make the warnings disappear.

**Regression tests required:** (1) unrelated counterexample in A does not flag B; (2) direct contradiction in B does flag B for review; (3) unresolved source status on B is still surfaced; (4) true hand-worked counterexample C7 and conditional identity C11 retain accurate claim types, not automatically downgraded to false; (5) unknown or malformed source IDs remain rejected.

## Schema limitation: claim status is overloaded by construction

`PaperClaim` around lines **173–179** currently has exactly `id, statement, status, evidence_refs, reasoning`. The only `status` values are `established, conjecture, unresolved, limitation`. The generator **cannot** structurally express the difference between a stipulative definition, conditional algebraic deduction, hand counterexample, proposed architecture, independently validated result, and an unverified agent argument. This is not merely a prompt-quality defect.

For controlled iteration 2, add **optional, backward-compatible** `kind` and `verification` (or an equivalently minimal typed publication-readiness record), with clear defaults for existing checkpoints and persisted drafts. Keep `status` for legacy display/export compatibility until migration is proven. Validation must not turn `kind=conditional_deduction` into `verification=independently_verified` automatically. Source refs remain exact immutable IDs. The authoring prompt and output renderers should surface both dimensions without exploding the main paper into a 19-subsection claim register.

**Avoid a premature one-line “fix” to the model prompt alone:** `PaperClaim` is a strict Pydantic schema (`extra="forbid"`); unsupported new fields would be rejected, and changing fields during an in-flight checkpoint may invalidate existing generation. A bounded migration test across legacy records, interrupted/resumed long-paper checkpoints, full TXT/TeX/PDF, and all three frozen projects is required.

## Claim-link normalization and silent loss risk

`_repair_paper_references` around lines **3774–3820** only accepts exact claim IDs in `links(values, label)`. `C02` is not equal to `C2`; if the model emits zero-padded section links, the routine removes them and adds a diagnostic. The first Sovereignty metadata explicitly reports this author-plan mismatch. A narrowly scoped canonicalizer can accept `C02` as `C2` **only when the target exists and normalization is unambiguous**; reject collisions and unknown IDs. Test abstract, section, conclusion, table and diagram claim links, not just bracketed TXT citations.

## Methodological disposition

This code review explains why the initial 9 provenance warnings cannot be treated as 9 demonstrated contradictions. It strengthens, rather than weakens, the need for an explicit claim ontology and precise source linkage. Keep the current three-paper baseline frozen. No runtime files were changed and no tests against SIGMA itself were run in this review. The coordinator-owned offline auditor is a separate reproducibility aid, not a substitute for source-span verification.
