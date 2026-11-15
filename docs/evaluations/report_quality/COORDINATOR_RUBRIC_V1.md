# SIGMA publication-quality rubric v1 — coordinator-owned working standard

**Prepared:** 2026-11-01 (PST). **Scope:** substantive paper writing from frozen SIGMA evidence, not research-agent quality or TeX layout alone. **Status:** provisional operational rubric for the three-project experiment, not a claim of journal acceptance or a completed 20-source survey. No live provider calls or new project data were used to develop this rubric.

## Source-backed guidance reviewed

These are **primary institutional guidance**, not model training weights or copyrighted texts imported into prompts. Retrieved/inspected on 2026-11-01; distill the rules, link to sources, and do not copy their full text.

| ID | Primary authority | Applicable guidance and limits |
|---|---|---|
| S1 | [ICMJE Recommendations, January 2026](https://www.icmje.org/recommendations/) and [manuscript preparation](https://icmje.acponline.org/recommendations/browse/manuscript-preparation/preparing-for-submission.html) | Clearly separate objectives, methods, findings and interpretation; provide enough methodological and statistical detail to judge conclusions. **Medical journal guidance**, not mandatory for an architecture proposal. |
| S2 | [EQUATOR reporting guidelines index](https://equator-network.org/reporting-guidelines/index.html) | Match reporting checklists to **study design**, not to superficial subject keywords. Reporting completeness is **not evidence of good study design or scientific truth**. |
| S3 | [Nature Portfolio reporting and availability standards](https://www.nature.com/ncomms/editorial-policies/reporting-standards) | Explain reproducibility, data/code access or restrictions, protocols, and evidence necessary to examine claims. Journal policy applies only when submitting there; general principle transfers. |
| S4 | [ARRIVE 2.0](https://arriveguidelines.org/arrive-guidelines) | Animal **experiments** require transparent design, units, controls, sample sizes, bias safeguards, methods, outcomes. **Do not fabricate ARRIVE experimental sections for a Xenopus literature/hypothesis paper without new animal experiments**. |
| S5 | [NeurIPS Paper Checklist](https://neurips.cc/public/guides/PaperChecklist) | Claims match actual evidence; limitations and assumptions explicit; proofs inspectable; empirical comparisons reproducible. Useful for AI-agent evaluation, but not proof that a SIGMA output satisfies NeurIPS review. |
| S6 | [ACM Artifact Review and Badging policy](https://www.acm.org/publications/policies/artifact-review-and-badging-current) | Separate artifact availability, artifact evaluation and independent result validation; an executable artifact is not an independently validated result. |
| S7 | [IEEE Author Center: structure a paper](https://conferences.ieeeauthorcenter.ieee.org/write-your-paper/structure-your-paper/) | A specific title, self-contained abstract with conclusions, and a coherent progression are useful editorial constraints, not mechanical score targets. |

Additional study still needed before claiming a complete reference library: discipline-specific review/synthesis standards for biological hypothesis papers, systems measurement and workload-design literature, causal inference and qualitative methodology, statistical planning and uncertainty, technical-writing examples with reusable licenses, publication ethics and citation practice. This rubric is intentionally **seven** examined source families, not the previously discussed full ~20.

## Core epistemic contract (hard gates)

A paper is **not accepted** if any critical violation below is confirmed, even if it is long, attractive, compiled, or passes CI.

1. **Claim identity and type.** Every central claim has an explicit kind: `definition`, `conditional deduction`, `independently checked result`, `saved agent argument (unverified)`, `empirical observation`, `hypothesis`, `design proposal`, `counterexample`, `negative result`, or `unresolved obligation`. Claim **type** and **verification status** are separate fields. A definition may be established by stipulation; a proposed mechanism is not a deployed feature; a model-authored proof is not independently verified. [S1, S5, S6]
2. **Claim–evidence mapping.** Each consequential claim links to immutable source identifiers and to the **exact supporting span or calculation**, plus source class (primary publication, project record, test, model assertion, hypothetical assumption). Internal `[C7]` references alone do not constitute a scholarly bibliography. External claims need conventional author/title/date/URL or DOI entries and clear retrieval/verification status. A source's presence in the appendix does not prove the cited proposition. [S1, S3, S5]
3. **Contradiction and omission ledger.** Negative findings, failed turns, unresolved objections, conflicting sources, evidence-index truncation, and incomplete methods cannot be silently omitted. State **what** was omitted and whether the omitted material could reverse the conclusion; a count alone is insufficient. If essential evidence is not inspected, downgrade the affected claim and document the coverage gap. [S2, S3, S5]
4. **No invented research.** Do not imply an experiment, statistical estimate, implementation, institutional approval, formal proof, source inspection, or external verification happened unless the frozen records establish it. Do not manufacture Results, N, controls, effect sizes or p-values. A conceptual paper can legitimately have no empirical Results; choose a genre reflecting available evidence. [S1, S4, S5]
5. **Reproducible reasoning.** Definitions, denominators, constraints, equations, assumptions and relevant derivations must be inspectable. Distinguish hand-worked counterexamples, formal deductions, simulation, real experiments, and retrospective observations. A failure to reproduce a derivation is `unverified`, not an established theorem. [S3, S5, S6]
6. **Conclusions do not exceed evidence.** Abstract, results and conclusion must communicate what was actually learned, what remains conditional, what was disproved and what would discriminate alternatives. A proposed pilot is not evidence of pilot efficacy. [S1, S5]
7. **Reader accessibility.** A substantial paper has coherent sections and meaningful, readable paragraphs; claim registers, exhaustive warnings and source excerpts should not crowd out the main argument. Avoid circular repetition, gratuitous length and appendix-like raw data dumps. For output forms, source-text paragraphing and TeX readability are separate checks. [S7]

## Genre-specific tests

**AI Agent Reliability and Evaluation — software/systems empirical or analytical study**
- Precisely define reliability and evaluation target: unit of analysis (task/session/turn/strategy), success criteria, denominators, workload mix, error classes, cost, concurrency and confidence.
- Separate measured SIGMA behavior from proposed architecture; provide reproducible traces, baseline comparisons, negative cases, confounding factors and failed sessions.
- Trace cross-session evidence and explain whether stabilization or scheduler changes affect comparability; do not claim reliability from one completed run or green CI.
- For a conceptual paper, use design/analysis/limitations genre; no invented quantitative performance gains. [S5, S6]

**AI Sovereignty — systems architecture and policy/economic analysis**
- Define the **actual** comparator (campus gateway with separately approved external access), institutional policy boundaries, data classes, authorization, liability and budget semantics.
- Label conditional proofs, hypothetical cost/task worksheets, documented existing features and new proposed federation mechanisms distinctly.
- Require source-verified primary references before treating vendor/product claims as independently confirmed; policy claims require identified legal/institutional scope, not generalized compliance assertions.
- Quantitative pilot thresholds need exact assumptions, population/independence, pre-specified gate, sample-size justification and cost feasibility. [S3, S5, S6]

**Xenopus Tadpoles — scientific literature synthesis / hypothesis / research agenda**
- First identify whether saved evidence is actual animal experiments, a literature synthesis, a hypothesis, or a proposal; **never misclassify a thought experiment as measured biology**.
- Name competing mechanisms for temporary loss of tail regeneration, developmental stage, tissue/cell context, intervention/observation differences, contradictory reports and discriminating predictions.
- If actual experiments exist, apply relevant ARRIVE items: controls, experimental unit, sample size, randomization/blinding, outcomes, methods and limitations. If not, mark those items **not applicable**, not passed.
- Distinguish causal mechanism, correlation, model extrapolation and untested inference; source studies must be traceable and reproducible where available. [S2, S3, S4]

## Operational review card for each complete frozen-source manuscript

Record a **row per paper and per major claim**:
- `project_id, source_sha256, paper_sha256, generated_at, model/mode/calls, genre, words/pages, index_coverage, omitted_evidence, complete_source_list`.
- `claim_id, exact_claim, claim_kind, claimed_verification, actual_verification, source_id+span, supports/contradicts/unknown, severity, remedy`.
- `abstract_conclusion_match, strongest_negative_result_retained, unresolved_obligations_retained, alternative_hypotheses, methodological_completeness, paragraph/readability_findings, bibliography/links, TeX/PDF integrity, latency/cost`.
- For each dimension use `PASS / FAIL / UNVERIFIED / NOT_APPLICABLE` with a quoted **short** artifact pointer and concrete reason. Do not collapse into an opaque numerical score. A project without a completed paper is `UNVERIFIED`, not a zero-quality paper.

## Experimental discipline

Use the same **frozen input project** and generator settings for baseline versus intervention. Separate changes into (a) authoring/genre/claim-plan only, (b) evidence-index selection/retrieval, (c) external-source enrichment, (d) proofreading/layout. Do **not** attribute changes across several simultaneous interventions to one cause. Prefer a hard case in each domain; after a pass, escalate evidence volume, contradictions, source gaps or long-session synthesis. Preserve complete before/after artifacts and provenance, including failures. A/B comparisons with nondeterministic generation must be judged on *specific* source-backed defects and, when feasible, replicated runs—not assumed byte equality.

**Acceptance:** all three complete manuscripts are present; no hard-gate failure; claims/evidence independently audited at least for the major conclusions; any residual limitations clearly marked; no substantive regression against the strongest accepted baseline. Reviewable does **not** mean journal-ready or independently validated research.
