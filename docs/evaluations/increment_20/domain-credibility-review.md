# Increment 20: newcomer and sample credibility review

**Review date:** 2026-10-25  
**Base:** `ffb008f96a3ad2374e4fcc2eec82a2f9deea7e80` (PR #140)  
**Owner:** Blue  
**Scope:** Domain credibility and research-engine integration review. This is an evidence handoff for the Gray/Green-owned About, newcomer-documentation, and sample-presentation work. It makes no presentation or research-scope change; the sole sample edit adds the missing primary RDB7 data-paper citation described below.

## Findings

### Newcomer comprehension

- `README.md` accurately describes the product boundary: Investigator and Skeptic use the same underlying model; structured challenge is not independent validation; the RH sample is not a claimed solution.
- `docs/GETTING_STARTED.md` explains the workflow and calls a strategy a bounded approach, but it does not define Project, Session, and Outcome as clearly as it defines Strategy. It says the two roles examine and challenge claims without explaining that they currently use the same model.
- The About diagram supplies useful concepts in tooltips, but the expanded explanation says “Different minds take turns” and calls the Skeptic “a separate role-specific AI agent.” Those descriptions can imply different underlying models, contrary to the README. The same paragraph promises “complete recoverability and auditing”; reviewers should verify the exact product guarantee before retaining that absolute wording.
- The Home sample cards currently show a sample title, strategy count, and difficulty. Although the catalog API includes the research problem, Home does not show it before selection. A newcomer must open a sample copy to learn what question it investigates.

These are presentation/documentation decisions for Gray/Green. Keep the copper UI, role semantics, and evidence-integrity warnings. A concise shared vocabulary and explicit same-model caveat would resolve the observed inconsistency without changing the research model.

For owner review, a small remedy would be to define each term consistently across About and newcomer guidance and state plainly that the two role prompts use the same selected model. Candidate definitions consistent with current behavior:

- **Project:** the research question, its strategies, and the saved record of sessions and evidence.
- **Strategy:** a bounded approach to part of the research question, with a test or next step.
- **Session:** a saved attempt using one or more selected strategies, with Investigator and Skeptic turns under configured limits.
- **Outcome:** a session-level assessment and conclusion linked to recorded evidence, objections, and unresolved questions; it is not independent verification.
- **Investigator / Skeptic:** distinct prompt roles that develop and challenge claims while using the same underlying model for the current project configuration.

Handshake Count or Constrained Binary Strings already offer an Easy, bounded starting strategy; choosing one as the suggested first exercise is an editorial decision. Green's open PR #135 explicitly retains Samples cards as strategy/difficulty metadata, so the omitted question text is recorded here as an Increment 20 acceptance question for coordinator review after that PR, not as a competing UI proposal.

### Stock samples

The current typed catalog returns **17** samples with the same canonical IDs assessed in [the T89 stock-sample audit](../t89-stock-sample-catalog.md). The complete current identity/domain/difficulty/strategy-count inventory was read from `sigma.samples.sample_projects()` on this base; RH remains `riemann-hypothesis-research`, Mathematics / Hard, with four active strategies.

T89 inspected each sample’s authored problem and strategy set, and the curation follow-up retained all identities and original histories. I cross-checked its decisions against the current catalog and source records. No new basis was found to delete, consolidate, or substantially rewrite any sample, and this increment makes no such change. The two warp-drive samples have related subject matter but intentionally different physics and engineering scopes; consolidation remains an owner decision. `arrival-sequel` is creative work filed under the available `Other` domain, not a scientific result. `jesus-cannabis` is an explicitly historical/source-critical question, is correctly unrated, and its prompt does not claim a conclusion. The Xenopus and catalysis samples describe proposed investigations and prerequisites rather than asserting new empirical results. The scientific/math prompts keep proof, computation, supplied premises, fictional scenarios, and speculative engineering distinguishable.

| Stable sample ID | Credibility assessment against the current prompt/catalog |
|---|---|
| `algorithm-design` | A bounded scheduler correctness problem; correctness claims are separated from performance benchmarking. Starter work now separates a correctness-first baseline from a dynamic-order experiment. |
| `alternating-zeta-boundary` | Keeps the convergence domain and exact continuation boundary in scope; no completed derivation or result is represented. |
| `arrival-sequel` | An unofficial creative-writing exercise with prior-art and source-work constraints; it must not be presented as scientific evidence. The current `Other` domain reflects the available taxonomy. |
| `counting-constrained-binary-strings` | Correctly includes the empty string and gives an elementary recurrence/counting target; suitable as a first bounded math task. |
| `euler-product-primes` | Restricts the Euler product to absolute convergence and distinguishes prime-power information from RH. |
| `first-principles-catalysis` | Frames a research design with data, leakage, uncertainty, and held-out validation requirements; it does not claim predictive chemistry results. Data availability remains a prerequisite. The prompt identified RDB7 and its 2025 reanalysis but omitted the primary RDB7 dataset paper; this increment adds the 2022 source DOI without changing the question or scope. The [dataset record](https://doi.org/10.1038/s41597-022-01529-6) identifies the work as RDB7 and lists the barrier-height, reaction-enthalpy, and RMG-family data. |
| `handshake-count-easy` | A compact pair-counting task with a direct starter strategy; no result beyond the exercise is claimed. |
| `jesus-cannabis` | Asks a historical/source-critical question and distinguishes evidence about a person from regional context or repeated claims; no conclusion is preloaded. Difficulty remains unset. |
| `maximum-regions-by-lines` | A checkable upper-bound-plus-construction exercise with a non-spoiling active starter. The separate historical evaluator export is not shipped sample research. |
| `nonconsecutive-subset-sums` | The five saved sessions are deterministic fixtures with mixed/unresolved Outcomes; they do not establish the requested general result. A separate human-authored proof note in `docs/EXAMPLE_MATH_VERIFICATION.md` establishes the recurrence and asymptotic density from periodic transfer matrices. It is explicitly outside the sample template and is not a stock provider Outcome or SIGMA discovery. |
| `operation-narrow-passage` | Explicitly fictional scenario and conditional trade-offs; not a factual military forecast. |
| `riemann-hypothesis-research` | Preserves RH as an open flagship question. Finite computation, implications, and candidate routes are not presented as a proof. |
| `scientific-investigation` | Explicitly lacks supplied raw observations; asks for a discriminating study plan rather than asserting an oscillation was observed. |
| `theta-functional-equation` | Tracks its stated theta premise and convergence justifications; zero symmetries are not treated as proving RH. |
| `warp-drive-engineering` | Assesses realizability and engineering constraints for a speculative concept; a proposed metric is not called a complete viable vehicle. |
| `warp-drive-physics` | Separates established physics from conjectural framework changes and defines failure criteria; no effective FTL result is asserted. |
| `xenopus-tail-regeneration` | Constrains the biological question by species/developmental stage, prior art, data, and replication; no new empirical mechanism is asserted. The cited [2024 Genome Biology study](https://doi.org/10.1186/s13059-024-03396-3) and [NCBI GEO GSE245320 record](https://www.ncbi.nlm.nih.gov/geo/query/acc.cgi?acc=GSE245320) match the sample’s stated RIC/data basis. |

There is **no authentic saved stock provider Outcome** to advertise. Sixteen samples have no saved sessions. `nonconsecutive-subset-sums` is the only exception: its five saved sessions are deterministic fixtures, all marked mixed/unresolved, and must not be presented as live research or as a proof. The repository does contain a separate proof of its recurrence and asymptotic density in `docs/EXAMPLE_MATH_VERIFICATION.md`; that human-authored note is explicitly outside the stock sample and is not evidence of SIGMA-generated discovery. Real Chrome confirmed the default Current Understanding and historical-session summary both label the deterministic records; the existing browser check also verifies the label within artifacts and in the exported text report (`browser_checks/nonconsecutive_sample.py`). Maximum Regions’ historical provider export is evaluator material, not shipped sample history. Preserve these provenance boundaries.

The curated catalog offers bounded starting strategies for the elementary Handshake and Constrained Binary Strings samples and a non-spoiling Maximum Regions path; these are credible first mathematical exercises, but the actual research output depends on a user-authorized provider session and is not pre-established. RH remains the flagship and explicitly open problem. No staged success or new research claim was introduced.

## Acceptance evidence and open owner decisions

| Increment 20 criterion | Evidence / result | Remaining work or decision |
|---|---|---|
| Explain SIGMA and define Project, Strategy, Session, Outcome; clarify Investigator/Skeptic roles and evidence/proof boundary | README has accurate proof/model caveats; Getting Started and About have the specific vocabulary and same-model gaps listed above. | Gray/Green: decide and implement concise cross-surface definitions and correct the potentially misleading About phrasing. Confirm any absolute recoverability claim. |
| Newcomer can identify a credible sample to run | Current sample-opening engine creates an editable independent copy; easy samples have bounded starter strategies. Home cards omit the sample problem text available in the catalog API. | PR #135 intentionally retains title plus strategy/difficulty metadata. Coordinator: decide whether that presentation is sufficient for this criterion and whether to recommend an Easy first task after PR #135 review. |
| Assess 17 samples for material scientific/math issues; preserve RH and identities | Current catalog count and IDs match the T89 inventory. T89 prompt/strategy review and the curated follow-up record the sample-specific domains, claims, concerns, and rationale. The RDB7 primary-source omission received a citation-only correction; no sample's question, strategy, or claims were substantially changed. RH and all 17 identities remain unchanged. | Owner decision remains open for the proposed warp-drive pathway/consolidation. No approval for sample removal or substantial rewrite was requested or assumed here. |
| Keep research evidence and success claims honest | Only Nonconsecutive Subset Sums has stock session history; its five records are deterministic, mixed/unresolved fixtures. Existing browser review verifies fixture labeling in an artifact and report. | Preserve the warning in every presentation. No live session or paid provider call was performed. |

## Verification performed for this review

- Read the authoritative Increment 18–21 ticket, current `docs/STATUS.md`, README, Getting Started, T89 catalog audit, T89 curation record, About implementation, sample API, sample-copy engine, and related browser checks.
- Queried `sample_projects()` from the checked-out source: 17 entries; IDs and counts recorded in the catalog report. The only stock sample change is the source citation in `first-principles-catalysis/project.json`; sample identity, question, strategies, and saved histories remain unchanged.
- Read the 17 stock project records and their optional evidence sidecars: only `nonconsecutive-subset-sums` has shipped sessions (five); each assessment is `mixed`, each record explicitly labels deterministic fixture provenance, and no sample ships agentic runs.
- Read `docs/EXAMPLE_MATH_VERIFICATION.md` alongside `tests/example_math.py`. The proof note is a human-authored, standalone verification, outside the stock project and not saved as an Outcome. Corrected the test's printed path casing so it resolves on case-sensitive filesystems.
- Real Chrome confirmed the Home catalog shows all 17 entries and omits problem text from sample cards even though the API supplies it. The expanded About copy visibly says “Different minds take turns” and “complete recoverability and auditing.”
- Real Chrome on a newly opened sample confirmed the Current Understanding and historical-session summary visibly identify the five saved records as deterministic fixtures. All five are mixed/unresolved; artifacts and the report retain the same provenance label.
- `SIGMA_SAMPLE_UI_ORIGIN=http://127.0.0.1:5193 SIGMA_SAMPLE_API_ORIGIN=http://127.0.0.1:8026 uv run --with playwright python browser_checks/nonconsecutive_sample.py` — **PASS**. All five sessions displayed `Mixed · partial progress, unresolved`; the deterministic fixture notice appeared in inspected artifacts and the text report; desktop and 390px/320px mobile views had no horizontal overflow or page errors.
- Exported the actual Chrome-opened sample copy through SIGMA's `/api/projects/export` endpoint. The exact 241,467-byte response, five session IDs, copy ID, SHA-256, and limitations are in [the export manifest](exports/manifest.json); captured desktop/mobile screenshots accompany it.
- `uv run --with playwright python browser_checks/about.py` — **BLOCKED by a stale check selector**: it expects an accessible button named “About SIGMA”, while current Home exposes “About”. A direct real-Chrome check with the current label inspected the expanded About content. No application change was made for this mismatch.
- `./sigma test` — **PASS** after `npm --prefix frontend ci` installed the locked toolchain into this fresh worktree. This included backend research/sample checks, Ruff, Ruff format, Pyright (0 diagnostics), frontend typecheck, and production build. The initial attempt stopped at missing `tsc` before dependency installation.

No production environment, paid inference, or real-provider session was used. Increment 20 full user-facing acceptance is not claimed by this domain review; the presentation changes and any coordinator decisions remain open with their assigned owners.
