# I4 academic-writing methods study 1: connect claim, evidence, argument, and conclusion

**Prepared 2026-11-01 by Phase 1 coordinator. Scope:** Writing from the **existing frozen research**. These scholarly sources guide presentation, traceability, conclusion calibration and paper argument; they are not authority to perform new SIGMA investigation. This file is the first targeted I4 source expansion. Do not mistake it for a completed examination of all academic disciplines or of exemplary original research articles.

## Access and study log — actual HTML read

| Source / section examined | Access | Transferable principle | Concrete I3 defect it diagnoses |
|---|---|---|---|
| Brett Mensh and Konrad Kording (2017), *Ten Simple Rules for Structuring Papers*, PLOS Computational Biology, DOI 10.1371/journal.pcbi.1005619. [Full open HTML](https://journals.plos.org/ploscompbiol/article?id=10.1371/journal.pcbi.1005619), specifically Rules 1, 3–5, 7 and 9–10 | Directly readable primary full article, 2026-11-01 | State **one core contribution** in title/abstract, structure each major section as context → result/argument → conclusion, and make the results sequence form a *logical dependency chain*, not a chronological activity log. Choose one paragraph role during planning. | Sovereignty's abstract reports just a sensitive-rate subresult although its main thesis is policy/authorization + usefulness; final conclusion splices disparate long evidence fields. |
| John M. Drake and Barbara A. Han (2025), *How to Write a Scientific Paper in Fifteen Steps*, PLOS Computational Biology, DOI 10.1371/journal.pcbi.1013505, [open HTML](https://journals.plos.org/ploscompbiol/article?id=10.1371/journal.pcbi.1013505), core reasoning vs prose, outline sequence, statement of methods/results/interpretation | Directly readable article; selected methodology sections studied, not a separate independent evaluation of the technique | Construct the main claim/inference architecture first, then map method → evidence/result → implication; never use wordsmithing to substitute for an absent evidence link. | Xenopus central proof is explained in the body but not in claim register; the outline's source/claim map failed even as readable prose improved. |
| [ACM SIGSOFT Empirical Standards](https://www2.sigsoft.org/EmpiricalStandards/docs/standards), General Standard §§Essential Attributes, Quality Criteria, Good Review Practices, Antipatterns; Engineering Research and Benchmarking sections | Complete accessible HTML section text reviewed on 2026-11-01 | A paper's claims need an appropriate method, clear assumptions, limitations that affect conclusions, and a reproducible chain of evidence. Use **method-specific** review; reporting a conceptual systems design is not evidence of deployment reliability. Reject generic, ungrounded criticism. | Sovereignty mixes formal/conditional argument with unverified deployment claims; Agent must separate analytic reliability constraints from nonexistent empirical evaluation. |
| [UCI Library, Scientific Writing: Discussion](https://guides.lib.uci.edu/scientificwriting/discussion), §Discussion and Conclusions Checklist from Chris A. Mack | Accessible full HTML section reviewed 2026-11-01 | Discussion interprets and tests the meaning of results, addresses alternatives and shortcomings; conclusion briefly states the general supported implication, **not a replay of the results, abstract or background**. | Sovereignty I3 3,869-char multi-paragraph conclusion repeats claim and MindRouter descriptions; missing direct implication and decisive future condition. |
| [SIAM Undergraduate Research Online: Instructions for Authors](https://www.siam.org/publications/siam-journals/siam-undergraduate-research-online-siuro/instructions-for-authors/), Abstract, Introduction and References sections | Accessible HTML inspected 2026-11-01. Not generalized into requirements of all math venues. | A math abstract should stand independently, generally minimize symbolic formula and reference clutter, and the introduction should clearly state what was proved and why it matters. | Fourth math subject needs a defensible theorem-level abstract, proof dependencies and honest status, not a raw computational log; Sovereignty abstract formula-heavy fallback is also a general readability warning. |

**Access caveats:** PMC mirror of Mensh/Kording displayed a browser challenge, but PLOS's original directly opened and was readable. Nature Methods source returned an inaccessible login redirect; only a search-result excerpt was seen. Neither is counted as fully read via those failed routes. This study is not exhaustive across genres; select stronger published *exemplars* in later I4 work, distinguishing actually read full text from abstracts, links and publisher checklists. No source text is copied wholesale into SIGMA prompts.

## Operational writing techniques derived from these sources

### 1. One contribution, several necessary arguments

Before outlining sections, write an internal, falsifiable one-sentence statement of what the paper can legitimately contribute. For **Sovereignty**, likely boundary: federation earns additional complexity only by improving *authorized useful research-task completions relative to gateway plus separately approved access* while satisfying separate revocation/liability constraints. This is a bounded **design-analysis conclusion**, not a deployed cost saving. For **Xenopus**, the paper contributes an **identifiability theorem** plus prospective experimental discriminator, not a demonstrated biological mechanism. For **Agent**, fixed-protocol reliability and ambiguous-effect impossibility/conformance distinctions are analytical results, not benchmark outcomes. For **mathematics**, the central item is an exact theorem/formula/characterization or a correct unresolved bound.

### 2. Claim–support map must be closed before authoring sections

For every major body section, the plan needs a concrete *research proposition*, the source's exact evidence span, the methodological claim type (definition, deduction, counterexample, measurement, hypothesis, proposal), the strongest substantive objection and what is *actually established*. A section with a proof but zero corresponding claim entries fails the paper plan, even if it produces 1,000 eloquent words.

**Test:** select the three most decisive proof/contrast propositions for Xenopus and require exactly one source-linked register entry and at least one corresponding section link for each. Verify the source contains the proof; do not invent it by scanning the manuscript and calling it established. Broken linkage is not repaired by adding decorative citations.

### 3. Abstract/section/conclusion coherence

- Abstract: question/gap → bounded main result → why the result matters → central caveat, not source-index activity.
- Section: locally relevant background → actual argument/evidence → what that changes about the paper's thesis. New sections must advance a distinct inferential step, not rehash prior sections.
- Conclusion: one paragraph establishing the **maximally supported answer** plus one decisive limitation/next discriminating action. No wholesale claim-register copy, undocumented new evidence, or repeated external feature description.

**Regression gate:** manually compare abstract, conclusion and strongest body section. Ask whether they state compatible main result and differ appropriately in detail. An abstract beginning with an incidental numeric worksheet result while ignoring the paper's true thesis should be flagged. Any conclusion containing verbatim long source-field fragments or restating a detailed source-feature inventory without explaining implications fails.

### 4. Negative results and missing review are substantive, not rhetorical clutter

Scientific negative cases that **change** a conclusion belong in the relevant main argument. The failed Sovereignty final Skeptic attempt affects the completeness/verification boundary and must appear in the limitations, not be misclassified as a counterexample to the mathematical arguments. Xenopus's redox-persistence equal-exposure null is an intellectual alternative, not an optional literature flourish. Agent's dropped-retry correction narrows a theorem; it belongs in the proof scope and result narrative, not a generic footnote.

### 5. Source-appropriate standards

- **Systems reliability paper:** setup/assumptions, state model, theorem and counterexamples, fault injection proposed vs executed, evaluator ground-truth definition, sampling unit.
- **Architecture/policy paper:** comparative design alternatives, explicit authorization and cost denominators, threats/constraints, quantitative counterexample, sensitivity/decision threshold, no invented campus outcomes.
- **Biological hypothesis paper:** observational identifiability, known biological literature vs uninspected references, latent mechanism vs intervention model, biological unit and causal controls, negative model alternatives.
- **Mathematical proof paper:** definitions and exact quantified statement before lemma chain; proof completeness including existence/uniqueness, both directions or upper/lower as applicable, finite enumerations clearly limited. Avoid porting statistical publication criteria onto pure mathematics.

## Implementation hooks already tested or planned in PR #430

The I3 coordinator implemented bounded fallback conclusion snippets (not verbatim source blocks), source-index kind annotations, exact duplicate-claim aliasing, source-derived incomplete-session limitation and TeX claim-register layout. Those changes **are not evidence that I4 manuscripts improved**; they require regenerated and reviewed papers. Prompt additions in the long-form planner now require critical theorem/counterexample entries and distinct claim links. Future work should strengthen a plan-level coverage check without fabricating source claims or automatically replacing a substantively stronger model outline with a thin deterministic fallback.

**Next study before I4 generation:** independently read exemplary complete published *original* papers in these four genres and prepare a concrete source→claim→section dependency analysis, not only editorial guidelines. Prefer open HTML, inspect citations and limitations, then adapt domain-general techniques. Keep separate the Phase 2 new research source release from Phase 1 changes to authoring logic.

**Synchronization:** PR #434 is producer-owned STAGING and the four-subject `READY` release is absent. This study can proceed immediately; no authoring using these new project exports until the PR's release manifest passes all gates.
