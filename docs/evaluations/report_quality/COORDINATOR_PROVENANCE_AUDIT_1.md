# Coordinator provenance-warning audit — Sovereignty iteration 1

**Prepared:** 2026-11-01 03:45 PST. **Source:** `docs/evaluations/report_quality/iteration_1/papers/ai-sovereignty-v2.metadata.json`, the corresponding TXT and Blue's immutable checkpoint. This is a separate coordinator-owned supplement; the generated files remain untouched.

The generator's **own validation warnings** explicitly identify five `established` claims with suspect support: **C2, C3, C7, C9 and C11**. C2, C3, C7 and C9 each have **two** warning strings (unverified/incomplete/conjectural source material; and counterexample/contradiction language). C11 has **one** warning string (unverified/incomplete/conjectural source material). There are **nine warnings across five distinct claims**, not nine independently proven errors.

This does **not** mean that the claims themselves are false. C2/C3 are definitions; C7/C9 are concrete arithmetic counterexamples; C11 is a valid conditional cost-ratio identity under its declared assumptions. The failure is that a flat `established` status obscures whether the claim is a definition, a sound calculation, a self-asserted theorem, or a claim supported by independently examined evidence. The source metadata already knew these warnings, yet the paper still displayed the unqualified labels.

**Testable defect:** A publication-readiness pass should preserve each claim's **kind**, **source evidence status** and **verification status** separately. For C2/C3 it should say “definition/stipulation,” for C7/C9 “hand-worked counterexample, arithmetic check pending/complete,” for C11 “conditional algebraic identity,” and for external MindRouter capability claims “supplied description, primary sources not retrieved.” In the rendered paper, no warning may be silently discarded; it should either be resolved with explicit source-span checks or reflected in the claim's uncertainty language.

**Negative control:** The claim `C11` must **not** be downgraded to false or speculative merely because it cites incomplete research. Its algebraic identity can be independently verified while the economic inputs and real-world applicability remain unknown. This distinction is a particularly valuable adversarial regression test.

**Additional structural issue:** `validation_warnings` reports author-plan links using `C02` while the register uses `C2`. The offline auditor `analysis/manuscript_audit.py` normalizes bracketed `[C02]` and `[C2]` references numerically, but the generator should normalize claim IDs at source-linking boundaries. The auditor checks *surface existence only*, not semantic equivalence of references or whether a source span actually proves a claim.

**Render status from metadata:** `publication_status=needs_review`; `proofreading.status=fallback`; 59 unresolved diagnostics; 0 accepted corrections; five layout warnings, including an overfull box of 100.03801 pt and PDF page 31 exceeding horizontal bounds. These are **engineering acceptance failures independent of academic claim quality**.

**Interpretation:** The highest-leverage next authoring experiment remains epistemic typing with a claim-source matrix. The above nine warnings provide a **frozen, pre-registered hard-case set** to test. Do not silently change the research snapshot, add new literature, or combine source retrieval with the editorial treatment in the same causal A/B.
