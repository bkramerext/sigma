# Coordinator publication citation contract — source type, support relation, verification

**Design note, 2026-11-01.** This is an editorial/architecture specification for later controlled implementation, **not a claim that SIGMA currently supports it**. It does not authorize new provider calls or changing the frozen three-project A/B. Source principles: ACM SIGSOFT Empirical Standards (https://www2.sigsoft.org/EmpiricalStandards/docs/standards), ICMJE Recommendations (https://www.icmje.org/recommendations/), and EQUATOR guidance (https://equator-network.org/reporting-guidelines/index.html), all consulted 2026-11-01. These authorities cover different disciplines; transfer only appropriate reporting principles.

## Defect revealed by three complete papers

SIGMA currently uses internal `[C#]` pointers and source IDs such as `artifact:session_uuid:artifact_uuid`. Those are **research provenance**, not conventional scholarly references. The Sovereignty TeX itself states that no external bibliography was added, even while citing two external MindRouter starting URLs that were not retrieved by the saved research. Xenopus lists GEO accessions and DOI pointers without confirming the underlying sample manifest or reading all primary papers. Agent cites saved session artifacts but its fallback `C1`–`C3` register points to metadata rather than scientific claims.

A paper can therefore have dozens of bracketed references and still lack **externally verifiable literature support**. Conversely, a rigorous original analytical derivation can be meaningful without an external source asserting the same theorem. These must not be collapsed into a single “citation count.”

## Minimal typed source record (conceptual)

```text
source_id                immutable identifier
kind                     frozen_research_artifact | external_primary |
                         external_secondary | dataset | protocol |
                         original_analysis | other
locator                  internal project/session/artifact ID OR canonical DOI/URL/accession
version_or_snapshot      immutable revision, content hash, accession version or access date
retrieval_status         retrieved_and_inspected | supplied_pointer_uninspected |
                         unavailable | partial | not_applicable
support_relation         supports | refutes | qualifies | background | method |
                         unverified_candidate
claim_id                 stable claim ID
evidence_span            exact passage/field/fragment range or section locator
scope_and_assumptions    conditions under which this evidence bears on the claim
verification_basis       author_assertion | agent_review | deterministic_check |
                         independently_reproduced | external_measurement |
                         independently_validated
```

The source's **kind**, whether its content was **actually retrieved**, and the **relation to a particular claim** are separate dimensions. An uninspected DOI or URL is a pointer, not a verified fact. A cited counterexample must retain its *refutes/qualifies* relation; it is not merely another supporting citation. Source status is never automatically upgraded because a model agrees.

## Rendering contract

1. **Core manuscript:** use conventional in-text citations for retrieved external sources with a bibliography of identifiable authors/title/venue/year/DOI or stable URL. Use internal claim references only where they help navigate a structured argument. Do not substitute `[C13]` for a literature reference.
2. **Provenance appendix or digital companion:** provide precise frozen research project/session/artifact references and spans for each consequential claim, including negative findings and unresolved obligations. Readers must be able to distinguish “the SIGMA agent wrote this” from “this was externally demonstrated.”
3. **Uninspected pointers:** list separately as *starting references not retrieved or verified*; do not use them to support current capabilities, biological novelty, or empirical effect sizes. Report access failures explicitly.
4. **Original derivations:** present premises, steps and falsifiers; link to the frozen research source that contains the derivation, but do not imply that source is an independent formal proof checker. A separately executed arithmetic check may be identified as such with code/version.
5. **Safe typesetting:** render URLs using a validated breakable URL mechanism and preserve literal target bytes. The independent local `tex_url_break_ab.py` experiment demonstrates that `xurl` can eliminate URL overflow in a comparable paragraph, not that the deployed SIGMA renderer is already fixed.

## Three discipline-specific acceptance cases

**AI Agent Reliability:** a reliability percentage needs task distribution, sampled independent unit, denominator, run horizon, failure/nonexecution policy, model/tool version, evaluator accuracy assumptions and artifact IDs. Distinguish measured trials from conditional impossibility arguments and proposed fault-injection tests. Internal run traces can support “this run ended” but not “agents are reliable in deployment” without sampling and independent outcome evidence.

**AI Sovereignty:** claims about MindRouter features require retrieval of its exact documentation/paper version and a support span. Hypothetical cost comparisons cite the saved worksheet and clearly label assumptions; they are not vendor prices or measured campus costs. Authorization constraints may require primary policy/contract sources, not just a model's interpretation.

**Xenopus:** biological mechanisms require primary literature with species, developmental stage, tissue, intervention, time, endpoint and control. GEO accessions require an inspected sample manifest, animal/pool identity and version. Original algebraic nonidentifiability can be source-linked as a derivation without pretending to be an observed biological effect. A cited `X. tropicalis` result cannot silently establish a `X. laevis` developmental claim.

## Falsifiable publication gates

- Every central external factual claim has a **retrieved** supporting source with an exact relevant span, or is explicitly marked source-limited/unverified.
- Every internal analytical claim has an inspectable derivation or a precise saved-artifact link and declared assumptions.
- Bibliography entries correspond to actually cited external sources; no fabricated authors, DOIs, venues, access dates or uninspected full-text claims.
- Contradictory and superseding evidence is not silently dropped. The relation is claim-specific, not a source-global keyword match.
- References survive TXT, TeX and PDF rendering and preserve exact identifiers; no unsafe URL injection or unbreakable-token overflow.
- Quality measures distinguish **citation presence**, **source retrieval**, **support relevance**, **verification**, and **decision-critical recall**. A large count in one dimension does not substitute for the others.

## Implementation sequencing

Do **not** mix citation enrichment with Blue's iteration-2 semantic fallback treatment. First repair metadata-as-claims (H2-A), then evidence critical-recall and claim-kind/verification as separate experiments. Introduce typed citations only when the source and claim semantics are stable; otherwise the bibliography would merely polish unsupported prose. All three frozen baselines remain untouched until a separately approved retrieval/enrichment study.
