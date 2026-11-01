# Coordinator code audit 2 — evidence-index coverage failure modes

**Prepared:** 2026-11-01 ~03:45 PST. **Source inspected:** `src/sigma/papers.py` around lines 1048–1123, 1125–1311, 4062–4089, 4321–4350 and 5770–5888. **No runtime modifications.** This is an adversarial design analysis for a later controlled H2 experiment, not proof that a particular omitted field changes the current paper.

## Actual current mechanism

The structured fast path builds `EvidenceNote` candidates from **field names and values** in frozen project/session/artifact records. It selects paths matching a list of research terms; labels priority **3** for path terms such as `skeptic`, `counterexample`, `failure`, `obligation`, priority **2** for `proof`, `result`, `conclusion`, etc., and priority **1** for remaining context. The ordering rotates among source records within priority bands using pattern `(3,2,3,2,1)`, then packs notes until **150,000 bytes**. The planner itself receives an **80,000-byte** preview. Individual note text is fragmented at roughly **410 characters**, with source IDs retained but without a guaranteed complete argument unit. The path is deterministic and consumes **no extraction model calls**. The full frozen package remains archived, and omitted candidates are recorded.

These are good engineering choices for bounded cost and preserving some skepticism, but **not** a proof of adequate semantic evidence coverage.

## Falsifiable failure cases

1. **Correction hidden under an innocuous field name.** A late correction in a generic `summary` or `content` field can have priority 1 while an older `skeptic` field has priority 3, even if the correction supersedes the older result. With enough data, the current selection can include the obsolete objection and omit its resolution. This is a **possible** behavior, not a demonstrated omission in Sovereignty.
2. **Long reasoning split at arbitrary boundaries.** A multi-step argument in a `reasoning` field becomes many 410-character fragments. At the 150 KB boundary, some fragments may be accepted and later fragments omitted, creating a seemingly cited but incomplete proof. An exact source ID without a field span/fragment range is insufficient to show that the complete derivation was read.
3. **Negative-field dominance without materiality.** A verbose low-value `skeptic` or `obligation` field can consume many high-priority slots while a concise, decisive positive measurement or correction receives lower priority. Round-robin mitigates per-source monopolies, but not **semantic materiality** within each source or across priority bands.
4. **Temporal/version mismatch.** Selection uses source order and field path; it does not explicitly rank `supersedes`, `retracted`, `latest accepted`, or versioned dependency edges. The final paper may mix obsolete and current conclusions unless the saved records and prompts compensate.
5. **False reassurance from counts.** `372` selected vs `9,718` omitted is a count of *text fragments*, not distinct logical claims. One proof may contribute dozens of fragments, while one omitted counterexample may reverse a conclusion. Neither high nor low raw coverage percentage certifies a paper.

## Controlled H2 experiment and regression fixtures

**Do not change this until iteration-1 papers are frozen and H1 is evaluated separately.** Create deterministic fixtures with: (a) an early assertion and a later explicit correction under a generic field, (b) a long proof with a decisive final step at the byte boundary, (c) competing positive and negative evidence from two strategies, (d) an unresolved failed turn, and (e) two independent sessions with same-looking claims but different project/session IDs.

Define a **decision-critical manifest** from the frozen record: stable source + field/fragment span, claim, status, supersession relationship, severity, and why its omission could change the paper. Measure **recall of critical items** in the index, outline and final paper separately. Include negative results and latest corrections as mandatory retained items where feasible; if they cannot fit, mark the affected conclusion **unverified** rather than silently excluding them.

Potential minimal engineering path: preserve existing 150 KB bound and checkpoint schema, but use a deterministic **must-include** pass for structured contradictions, explicit retractions, newest corrections and unresolved high-severity obligations, with complete source spans or explicit continuation pointers; then allocate the remaining budget fairly. Never silently evict a must-include item. If the must-include set exceeds the bound, fail or disclose a precisely identified coverage limitation rather than claiming full review. Preserve the existing safety ceilings and provider-call accounting.

**Acceptance:** on matched frozen inputs, materially higher recall of pre-registered critical items in all three disciplines; no new fabricated references; no loss of a counterexample or a corrected conclusion; no unbounded provider use; and no substantial decrease in main-paper readability. Do not optimize for raw `selected_fragments / total_fragments` alone.
