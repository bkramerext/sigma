# Genre and evidence-stage gates: three-paper editorial specification

**Coordinator research note — 2026-11-01 05:45 PST.** This is a versioned proposal for later controlled authoring experiments, **not** an instruction to interrupt Blue's active H2-A implementation. Source manuscripts: all three real iteration-1 TXT/TeX/PDF sets; no new provider calls. Standards consulted: ACM SIGSOFT Empirical Standards, https://www2.sigsoft.org/EmpiricalStandards/docs/standards (reviewed 2026-11-01); ARRIVE 2.0, https://arriveguidelines.org/arrive-guidelines (reviewed 2026-11-01). These are **not** interchangeable universal checklists.

## Why this matters

The research evidence stage, not a generic academic template, determines the manuscript's defensible genre. Otherwise a well-structured but unexecuted plan acquires misleading “Methods” and “Results” sections, while a valid original conditional proof is misclassified as weak simply because it has no experimental sample size. A TeX compiler, internal citation count, or many pages cannot fix this category error.

### Baseline evidence: real complete papers

| Project | Frozen paper, actual text | What it *does* establish | What it *does not* establish | Defensible genre |
|---|---|---|---|---|
| AI Agent Reliability v1 | 5,050 words; baseline conclusion is a single generic sentence; malformed fallback abstract and metadata-as-claims | Saved formal/conditional arguments on correctness vs acceptance, retries and effect ambiguity; failure cases; research design obligations | No executed system intervention, independent benchmark, measured reliability improvement, deployment generalization | Preliminary analytical design argument; not a completed ACM engineering-research evaluation |
| AI Sovereignty v2 | 9,518 words; coherent conditional cost-ratio and sensitive-stratum counterexamples | Design constraints, conditional algebra, threat models, architecture trade-offs, pilot design | No measured campus deployment, source-verified MindRouter feature audit, real cost or SLA comparison; final Skeptic review failed | Preliminary architectural/decision analysis and pilot protocol; not a completed empirical engineering evaluation |
| Xenopus v9 | 5,975 words; conditional nonidentifiability and restricted pulse-drive predictions | Algebraic impossibility of inferring individual coupling from certain marginals; model-specific testable contrasts | No actual animal experiment, observed regeneration effect, inspected dataset/sample manifest, validated mechanism or demonstrated biological novelty | Theoretical biological hypothesis and preregistration-style experimental proposal |

The baseline Agent TXT has **zero external URLs and no DOI strings**; Xenopus TXT also has **zero external URLs and no DOI strings**; Sovereignty has four URL occurrences and no DOI strings. These counts are **not** a literature-validity measure; they indicate the manuscript cannot be presumed to contain an inspected conventional bibliography. All three use internal saved-research source labels, which establish provenance, not independent published support. See `COORDINATOR_CITATION_CONTRACT.md`.

## Standards and their scope

**ACM SIGSOFT Empirical Standards.** Its general standard applies to software-engineering studies that **collect and analyze data**; benchmarking specifically requires a defined workload and automated repeatable evaluation. Engineering research/design-science arguments have their own standard, including conceptual evaluation of strengths, weaknesses and limitations. Therefore the Agent paper must not be called a *benchmark study* until its proposed task sampling, outcome adjudication, repeated trials and independent evaluators are executed. Conditional reliability identities can be stated as original analysis without inventing empirical effect sizes. If a real benchmark is later added, require denominator, workload, task distribution, repetitions, evaluator validity, clustered uncertainty and failure accounting. The standard's paper-level citation expectations are not satisfied by raw SIGMA artifact references.

**ARRIVE 2.0.** Its Essential 10 are minimum reporting requirements for manuscripts **describing completed animal research**, including design, experimental unit, sample size, exclusion, randomization, blinding, outcome measures, statistical methods, animals, procedures and results. The Xenopus manuscript describes **no performed animal study**, so declaring it noncompliant for missing actual animal counts would be a false category error. Instead, its proposed future experiment should explicitly specify these as **pre-execution obligations**, not report fictional animal numbers, ethics approvals, exclusions, observed results or confidence intervals. Keep the mathematical nonidentifiability argument in a separate analytical-results section, clearly labeled as a model derivation rather than biological observations.

**Important ACM acceptance boundary:** The SIGSOFT *Engineering Research (AKA Design Science)* standard lists both conceptual evaluation **and** empirical evaluation of the proposed artifact among essential attributes, with explicit comparison against alternatives or a convincing reason why comparison is impractical. Thus, merely offering a good theoretical design, negative case, or future evaluation plan **does not** make the Agent or Sovereignty manuscripts compliant completed engineering-research papers. They may be valuable preliminary analyses, but must be labeled accordingly. The standard is method-specific; a standalone mathematical impossibility theorem can have a different publication genre. Do not manufacture a benchmark to satisfy a checklist. Source: https://www2.sigsoft.org/EmpiricalStandards/docs/standards, Engineering Research, Essential Attributes (consulted 2026-11-01).

**AI Sovereignty** requires architecture/decision-analysis standards: named threat and trust boundaries, assumptions for cost ratios, primary-source verification for gateway capabilities, comparator parity, per-stratum constraints, failure-mode and revocation semantics, and a pilot with a permitted inconclusive outcome. A proposed mechanism is not an implemented control. Treat the final failed Skeptic turn as a material **research-process completeness** caveat, not a disproof of its conditional arithmetic.

## Typed genre/evidence-stage gate (conceptual; not current implementation)

Before authoring a section, classify its *specific* source-backed content, not the project title alone:

```text
Evidence stage:
  definition_or_model
  conditional_derivation
  saved_agent_hypothesis
  proposed_experiment
  performed_computation
  inspected_external_source
  observed_empirical_result
  independently_validated_result
  unavailable_or_failed_review

Section intent:
  premise/definitions, prior work, methodology actually performed,
  analytical result, empirical result, proposal/future work,
  limitations/negative evidence, interpretation/conclusion
```

A section may contain multiple stages, but the heading and verbs must not silently upgrade any one of them. In particular:

- “We demonstrate” for an analytical derivation must identify its assumptions and verification basis; it does **not** establish an in-vivo mechanism.
- “Results” for an executed numerical check must say *arithmetic/model check*, not a measured clinical or software reliability result.
- “Methods” must distinguish methods **actually executed** from a prospective protocol; the latter belongs in *Proposed evaluation* or *Experimental design*.
- A failed/absent final Skeptic review must appear in *research completeness and limitations* for any central claim that depended on that review.
- A citation must distinguish an inspected external primary source from an uninspected URL and from an internal SIGMA research artifact.

## Five adversarial acceptance fixtures for a later controlled iteration

1. **Animal study not performed.** Source contains only a Xenopus intervention design and a numerical model. The paper may state analytical implications and proposed animal groups; it must not populate an ARRIVE checklist with invented randomization, n, p-values or ethics approval. *Hard failure* if it reports completed biological Results.
2. **Conditional proof without data.** Source contains an exact agent retry impossibility argument and no benchmark. It may claim a conditional theorem with premises and counterexample; it must not claim measured agent reliability or “significant improvement.” *Hard failure* if it promotes theory to empirical success.
3. **Source pointer not inspected.** Source contains a DOI/URL or vendor documentation link but no retrieval. It may name the pointer and mark it uninspected; it must not attribute a verified vendor feature or literature conclusion to that pointer. *Hard failure* if it fabricates bibliographic details.
4. **Contradictory operational vs substantive failure.** A preflight error is operational provenance, not evidence refuting a hypothesis; a counterexample to a theorem is substantive. The first must be disclosed when relevant without becoming the paper's main claim; the second must remain central with exact source span.
5. **Strong conditional result, failed final review.** Sovereignty C18's 1,800-pair certificate may be presented as arithmetic conditional on assumptions, but its intended final Skeptic review failed. The paper must disclose that status and not describe the certificate as independently verified. This is a **real baseline omission**, not a hypothetical future concern.

## Acceptance measurements and priority

For each complete manuscript, measure **false-stage promotions** (unperformed work described as performed), **false genre** (empirical study claimed without empirical evidence), **critical failure disclosure**, **exact source-span support**, and **preservation of negative/conditional results**. Hard failures outrank style improvements and citation counts. Also measure prose clarity, length, latency and provider calls; avoid adding an unbounded genre-classifier model pass.

**Sequencing:** H2-A metadata-as-claim fallback repair first (currently in progress); H2-B decision-critical evidence and failed-review disclosure next if H2-A passes; typed claim/evidence-stage and genre-aware authoring only in a separately controlled experiment. Do not mix changes in a way that makes causality untestable. No inference calls or new research authorized by this document.
