# Pre-registered H1: claim-kind and verification separation across three frozen papers

**Prepared:** 2026-11-01, coordinator-owned. **Not dispatched:** iteration 1 still lacks final Agent and Xenopus papers. This is an experiment design, not authorization to change the live generator or make provider calls.

## Hypothesis

**H1:** The existing four-valued `PaperClaim.status` schema causes false impressions of verification because it conflates definitions, conditional deductions, counterexamples, hypotheses and unverified evidence. Adding an explicit **claim kind** and **verification basis** to the planning/authoring contract, without changing the evidence index or frozen research, will reduce materially misleading claim-status wording **across all three complete papers**, while preserving the same counterexamples, unresolved obligations and technical depth.

## Frozen comparison and controls

- Three immutable source snapshots, selected from Blue's iteration-1 report (final IDs/hashes must be confirmed in its completion addendum). Preserve the exact source files, generation options, model/mode and source index selection. Do not rerun the Investigator/Skeptic agents.
- Baseline: all three actual iteration-1 TXT/TeX/PDF papers and their metadata. A baseline is not accepted as complete until every artifact and hash is present.
- Treatment: authoring/claim schema + editorial prompt only. **No external source retrieval, evidence-index expansion, layout changes, diagram feature changes or new research** in the same experiment.
- Nondeterministic inference: compare *semantic defect classes and source spans*, not byte identity. If a new paper has changed wording, record the specific evidence link, not just a model's self-assigned score.
- Preserve actual provider usage and time; never claim zero inference resource use because the ChatGPT plan has no metered API charge.

## Engineering design constraints

- `src/sigma/papers.py:PaperClaim` is a strict Pydantic model with `status: Literal["established","conjecture","unresolved","limitation"]`. Add **optional/backward-compatible** fields or a minimal companion record, not a breaking replacement; legacy checkpoints and exports must load.
- Proposed `kind` values: `definition`, `conditional_deduction`, `counterexample`, `hypothesis`, `design_proposal`, `empirical_observation`, `unresolved_obligation`, `limitation`. Avoid proliferating categories without evidence.
- Proposed `verification` values: `source_unchecked`, `agent_reviewed_unverified`, `arithmetic_checked`, `external_source_checked`, `implemented_tested`, `independently_verified`. Require explicit evidence for each upgrade; `kind` alone never implies verification.
- Render plain-language status next to consequential claims in core paper and compact appendix register. Preserve original source IDs and negative results. No automatic promotion from `established` to `independently_verified`.
- **Separate bug**: `_validate` currently scans `source_text` for contradiction words **globally**; this produces claim-specific false-positive warnings. Fix with claim-local source checks or structured target links, but record this as a distinct deterministic correction and do not attribute its effect to H1 unless a factorial design separates it.
- **Separate bug**: zero-padded claim links `C02` vs `C2` may be discarded by `_repair_paper_references`; normalize only when target is unambiguous and test all linkage surfaces.

## Pre-registered adversarial acceptance set

**Sovereignty (19 claims):** `C2,C3` must be definitions; `C7,C9,C13` hand counterexamples; `C11,C14,C15` conditional deductions/hypothetical calculations; `C4,C8,C16` proposals; `C5,C6` conditional proof candidates; `C18` unverified numerical certificate with explicit IID and effect/discordance assumptions; `C1,C12,C19` remain source-limited/unresolved. The exact mapping may be refined by inspecting original claim text, but **none** may become a measured deployment success. Source-global contradiction warnings are not proof of claim-specific conflict.

**AI Agent:** classify architecture proposals separately from observed session traces, failed turns, tests and any independent verification. Every reliability number must have a denominator, failure/retry policy, project/version and sampling unit. An agent's positive self-review cannot become a measured reliability improvement.

**Xenopus:** classify literature observations separately from hypothesized causal mechanisms, interventions in cited studies, proposed new experiments and speculative cross-study synthesis. No animal experiments or effect sizes may be invented. Refractory-stage mechanisms must preserve stage, treatment, tissue and alternative explanation.

## Outcome measures and gates

| Measure | Before/after evidence | Acceptance |
|---|---|---|
| False verified-sounding central claims | Claim-by-claim audit with exact paper/source spans | **Zero** confirmed unsupported independent-verification assertions after treatment; fewer than baseline |
| Counterexamples and negative evidence | Frozen source-ID list for each project | **100% retained** for designated critical examples, or explicitly documented as unreviewed and downgraded |
| Source traceability | Exact project/session/artifact refs for central claims | No invented references; fewer unsupported assertions |
| Genre fitness | Methods/results/abstract/conclusion consistency | No unrun experiments represented as results; no unjustified empirical genre |
| Reader comprehension | Read core sections and claim register | More interpretable statuses without large new diagnostic dumps |
| Reliability and cost | Same generator options, all three full artifacts | No corrupted checkpoint, unbounded retry or unreported provider call; capture time/call changes |
| Rendering | TeX/PDF presence and actual diagnostics | No new regressions; existing layout failures separately reported, not disguised |

**Falsifiers:** any critical counterexample disappears; source IDs fabricated; conditional proof is described as independently checked; the new schema breaks legacy checkpoint resume; paper substance shrinks to superficial summaries; or status language improves only by indiscriminately marking everything unresolved.

## Execution and scheduling

The next coordinator `message_out_2.md` is **not authorized until** Blue's complete iteration-1 addendum is committed and independently reviewed. Once ready, Chat should adapt the scope to the actual :45 wake and target :40 next-hour submission, accounting for implementation and troubleshooting. If H1 takes longer than one work window, Blue should checkpoint honest progress and preserve the work; **never** manufacture three successful full papers or abandon safely running generation merely to meet the deadline.

This preregistration itself performs **no inference, no code change to SIGMA runtime and no experimental result**.
