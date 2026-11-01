# Coordinator independent review 3 — complete three-manuscript baseline and fallback failure

**Reviewed:** 2026-11-01 04:46–04:49 PST (`-08:00`), at Blue completion commit `0f6e86e5201a4f3339dcff9592f6e7a7e1ec035c`. **Decision:** accept iteration 1 as a *frozen comparison corpus*, **reject all three as publication-ready**. Matching completion addendum is `messages/message_in_1_completion.md`. Iteration 2 assigned in immutable `messages/message_out_2.md`; no Blue implementation result is assumed.

## Actual source/artifact identity

| Manuscript | Frozen project | Preflight fingerprint | TXT/PDF | TXT SHA-256 |
|---|---|---|---|---|
| AI Agent Reliability and Evaluation v1 | `da4580f5-7620-49b0-882e-aee34fcdc05d` (seven saved sessions, last ended but mixed/partial) | `080d3b70b67cfbe346acdb0f565d4a61c09ec4819229f2dd92dded43d9` | 5,050 words / 27 pages | `7b4b0f3c9270af76d5b4ff3e022de0440cbaf3c99ee487b202d528315b302074` |
| Sovereign AI Federation v2, user-directed sovereignty sample | `9175d73d-62aa-4523-a286-445f5390ae1d` | `552f9458e600d3e7d0b3aa6c1dd105cc62dab4967db652123d2f134783b76f34` | 9,518 words / 42 pages | `ce2b12a3a5ea99bff7aec41b8e511c7b77b8f41cbd8795b9b006a4187c9e60c8` |
| Xenopus Tadpoles v9 | `01de54c9-9593-413a-9577-1a952d28da70` | `3236a8c66a96d713f28726271169e67c88c8a768f398ab3b9b504fee3cdcc74e` | 5,975 words / 24 pages | `c9e48dd616023d58bb86591f18844f3f9cca5b10cfcc8e66154f9acdab5881fa` |

These are the actual three generated TXT/TeX/PDF sets. I independently read each complete TXT, inspected the exact claim registers, abstracts and conclusions, and inspected `src/sigma/papers.py` around lines 1125–1275 and 1334–1495. I did **not** visually inspect all PDF pages or independently verify every cited frozen artifact; PDF integrity remains an open gate. The Sovereign source's title differs from “AI Sovereignty”; this alignment is explicitly **not** independently verified as a separate named project.

## Cross-paper objective measurements

| Audit item | Agent | Sovereign | Xenopus |
|---|---:|---:|---:|
| Registered claims | 5 | 19 | 12 |
| Abstract words (whitespace tokens) | 113 | 149 | 143 |
| Raw record paths embedded in abstract | **2** | 0 | 0 |
| Claim-register words | 149 | 1,527 | 1,091 |
| Conclusion words | **20** | 134 | 130 |
| Body mentions of `C1` | **8** | 2 | 1 |
| Body mentions of `C5` | **9** | 6 | 7 |
| Indexed fragments omitted | 32,191 | 9,718 | 3,370 |
| Proofreader diagnostics unresolved | 34 | 59 | 21 |
| Accepted proofreader corrections | 0 | 0 | 0 |
| Final PDF overflow page | 16 | 31 | 22 |

Counts above come from the actual TXT and compact metadata; *body mentions* include any occurrence before the claim register, not solely a validated citation. The 32,191/9,718/3,370 omissions are **field fragments, not distinct logical claims**. These counts alone do not establish semantic coverage.

## Agent: severe publication failure despite a useful technical body

**Abstract contamination:** the text literally says `investigator_output/reasoning_steps/0/argument: that a client lacks an acknowledgment` and `come/solution_review/strategy_findings/0/failure_reason: Project or strategy changed; session paused before a new call`. The second is a *truncated field locator*, not readable scholarly prose. It confuses an operational pause with a central negative scientific result.

**Claim-register corruption:** actual register items are:
- `C1 · unresolved: title: AI Agent Reliability and Evaluation v1` — project title, not a proposition.
- `C2 · unresolved: events/4/project_change/previous/reasoning_effort: high` — configuration metadata.
- `C3 · unresolved: events/10/failure_kind: preflight_error` — operational event, not an experimental failure result.
- `C4` generic caveat that agent-reported evidence is unverified.
- `C5` one genuine open obligation about reference adjudication.

The **body** is not uniformly bad: it distinguishes observable outcome correctness from an agent's apparent success, develops retry/acknowledgment indistinguishability, discusses durable effects and fencing, and proposes clustered reliability estimands and fault-injection tests. But it cites `C1` eight times and `C5` nine times even though these claim IDs do not summarize those diverse substantive arguments. Its conclusion is the 20-word boilerplate “Conclusions are limited to the findings and uncertainties documented in the cited saved research, as examined in the sections above.” This is not a research synthesis.

**Confirmed deterministic mechanism:** `_structured_evidence_index` converts qualifying scalar fields into `path: fragment` notes, including nested metadata. `_evidence_based_long_plan` then selects the *first* note in each broad category as the claim statement. The Agent planning stage fell back to this path. It is a **confirmed design vulnerability**, while the precise causal trace from a particular source field to each final sentence should be verified by a deterministic reproduction (assigned to Blue). Filtering only final text is not sufficient: claims, section purposes, and abstract need coherent source-grounded semantics.

**Hard gate for treatment:** C1–C3 must not remain metadata-as-claims; a meaningful negative research finding must not disappear merely because it uses a `failure` field; source references must stay valid; no new empirical success or invented reliability rate; conclusions must distinguish actual deductions from unrun experiments. A successful full paper must retain at least the outcome-vs-acceptance distinction, ambiguous acknowledgment/retry model, durable external-effect obligation, and limitations of judge-based reliability estimates.

## Sovereignty: preserve correct conditional analysis, improve later

The full 42-page manuscript has a coherent comparison of four service alternatives, home-campus authority, policy-before-capacity, conditional liability/cost derivations, and a hypothetical 90-day pilot. It **does not** establish a deployed federation advantage, campus cost rates, or current MindRouter capabilities. The conclusion is substantive and conditional. The claim ontology remains misleading: C2/C3 are definitions, C11 a conditional identity, C13 a counterexample, C14 a hypothetical worksheet. The unqualified `established` label is insufficient. The four source-global contradiction warnings are lexical false-positive **risks**, not four proven refutations. See `COORDINATOR_CODE_AUDIT_1.md`.

**Negative control for iteration 2:** preserve the conditional cost ratio `ΔS/S_G > ΔC/C_G`, the sensitive-stratum counterexample, the gateway comparator, and the absence of an empirical deployment claim. Do not “fix” the paper by indiscriminately downgrading all mathematics or by silently importing new source material.

## Xenopus: strongest epistemic calibration, not a discovered mechanism

The full 24-page manuscript explicitly distinguishes the nonidentifiability of animal-level early/late coupling from unlinked marginal measurements. Its C3 construction uses `E=U,R=U` versus `E=U,R=1-U` to obtain slopes +1 and -1 under identical marginals; C4 shows assigned stage means cannot identify a stage-by-response interaction; C6 derives `-kcQ` versus `+kcQ` only for restricted, matched-exposure receptivity windows. These are **analytical deductions under stated assumptions**, not measured regeneration effects.

The paper correctly preserves alternative explanations: response latency vs wound age, a redox persistence score proportional to the controlled integral, spatial-structure null inadequacy, missing sample manifest and expression matrices, and absent later-competent `X. laevis` validation. Its abstract and conclusion are specific and scientifically restrained. It cannot be accepted as an empirical biology discovery, and literature novelty has not been independently verified.

**Negative control for iteration 2:** preserve the +1/-1 identifiability construction, restricted `±kcQ` result, latency confound, and absence of new biological measurements. If a semantic filter removes these because they are conditional or mathematical, it has regressed.

## Academic reporting standards applied, with limits

- **ACM SIGSOFT Empirical Standards**, https://www2.sigsoft.org/EmpiricalStandards/docs/standards (consulted 2026-11-01): research-method-specific expectations and a distinction between conceptual engineering research and empirical benchmarking. For Agent, an engineering design analysis is legitimate without invented experiments; a measured reliability claim requires actual units, sampling and observations. The standards are not a blanket score for every research genre.
- **ICMJE manuscript preparation**, https://icmje.acponline.org/recommendations/browse/manuscript-preparation/preparing-for-submission.html (consulted 2026-11-01; 2026 recommendations): methods should explain what was actually done and support reproducibility; conclusions must be supported by the presented evidence, and economic benefits should not be asserted without economic analysis. Use as transferable reporting principles, **not** as medical-journal submission requirements for the SIGMA systems paper.
- **EQUATOR reporting guidelines**, https://equator-network.org/reporting-guidelines/index.html (consulted 2026-11-01): reporting checklists aid transparency and completeness but are **not themselves study-design or quality-appraisal instruments**. Do not award a pass merely because a checklist is filled.

## Experiment disposition and prioritization

The largest *immediate reader-facing* defect is the Agent's deterministic fallback promotion of metadata into central claims. Iteration 2 isolates this mechanism, using identical frozen sources and an A/B evaluation of all three complete papers. The more fundamental evidence-critical recall issue is next (see `COORDINATOR_CODE_AUDIT_2.md`), followed by typed claims/verification H1 (see `COORDINATOR_H1_PREREGISTRATION.md`). This is an order of **causal isolation**, not a claim that the latter defects are unimportant. Proofreader and PDF overflow are tracked separately.

The report's **reliability acceptance** remains failed: three proofreader fallbacks, zero accepted corrections, and later-page overflow in every PDF. Do not claim clean layout until a separate controlled repair and full visual review. There were **46 ChatGPT-plan generation calls** across the three papers, not zero resource usage; no metered API charge was reported.

**Time accounting:** wake scheduled 04:45 PST, Blue completion already published at 04:12:35 PST; matching report was found at ~04:46–04:47. I pushed `message_out_2.md` before 04:49 PST, approximately four minutes after the scheduled wake. Blue's actual work interval begins when it sees the new message, with submission target 05:40 PST. No assumption that Blue immediately started, no change to the fixed 05:45 PST wake.
