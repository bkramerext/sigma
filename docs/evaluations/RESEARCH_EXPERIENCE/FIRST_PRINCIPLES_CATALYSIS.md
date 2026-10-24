# Can We Predict Chemical Reactions from Quantum Mechanics? — research experience evaluation

Blue · 2026-10-24 · observation coverage: browser workflow and authored scaffolding; research quality unobserved.

## 1. Sample identity and research objective

`first-principles-catalysis`. Find a physically interpretable predictor of out-of-family barrier-error or pathway-order failures, tested without leakage and without equating theoretical energies to experimental kinetics. The full canonical brief is in [project.json](../../../samples/first-principles-catalysis/project.json). It was opened from Home → Samples into an isolated editable copy; the source hash remained unchanged.

## 2. Researcher expectation

A useful first advance is an auditable data-coverage and leakage audit, followed by one preregistered pathway-order diagnostic against a cheap baseline. Reference electronic energies are not experimental product yields, and a novel chemical mechanism needs evidence beyond polished proposals.

## 3. Environment and runs

App revision `6059d67`, branch `blue/research-experience-study`; installed Chrome 156.0.8078.47 through Playwright, real headless browser. Desktop 1440×1000 and mobile emulation 390×844 / 320×700. The latter are viewport checks, not physical-phone testing. [Method](METHOD.md) and [browser inventory](evidence/browser-inventory.json) document isolation and hashes.

Saved preference: Sol (`gpt-6.1-sol`), High, access unverified; no model selected for an actual call. Stock sessions: **0**; study sessions: **0**; session IDs: none. No fixture playback or live research occurred for this sample. Generation was opened as a form only. Default future limits observed: three Skeptic iterations, 30 calls, one hour, 12,000 output tokens/call, no dollar cap; these are ceilings, not actual usage. Paper setup was inspected only. Live/provider calls: **0**, study provider charge **$0**; no token usage or model latency was measured. Automated first-pass navigation/export capture took 1.54s and the continuation capture 1.76s; these exclude reading/assessment and are not a human time-to-insight measure.

## 4. Research journey

From Chemistry I opened the five strategies and read the distinction between reference energies and experimental rates. My first practical question was whether comparable multi-channel reactant groups exist at all, so I forked “Audit whether pathway pairs exist.” I saved it, verified persistence and toggling, reopened it through Recent and exported the revised brief. I inspected authoring setup without submitting it. Outside SIGMA, I attempted the two cited publisher pages; the retrieval service returned an access/redirect failure for the 2020 page and 403 for the PCCP page. Those failures do not establish that the citations or datasets are invalid.

## 5. Substantive findings

No structures, energies, splits, model fits or calculations are present in the observed sample. SIGMA has not found a chemical relationship. Its valuable starting distinction is that a known reference dataset and a repeated benchmark are not a novel prediction. Dataset usability and paired-channel coverage remain unresolved.

## 6. Independent critical assessment

The pathway-order objective is only identifiable if the data contain comparable channels, methods and conformer assumptions. A descriptor correlation can otherwise measure family or reference-method differences. My continuation puts that gate before mechanism discovery. The cited-source access attempts were evaluator actions, not searches performed or preserved by SIGMA.

## 7. Rubric

Scores concern only the observed layer. Written prompt constraints do not validate agent behavior. N/O means not observed, not failure.

| Dimension | Score | Evidence and rationale |
|---|---:|---|
| Problem orientation | 3 | The objective is unusually careful about novelty and validation, but the long brief combines data audit, quantum methods, modeling and external testing before any record exists. |
| Strategy quality | 3 | Five approaches distinguish baseline, mechanism, channel ranking, artifacts and held-out validation. The prior-art/baseline stage still contains several substantial jobs and depends on data access not demonstrated here. |
| Intellectual substance | N/O | No saved research session, analytical artifact or generated result exists; evaluator-authored plans do not count as SIGMA intellectual work. |
| Skepticism and epistemic integrity | 4 | The brief explicitly rejects random-split novelty, leakage and an energy-to-yield inference. These are strong authored constraints; none was tested on an actual dataset. |
| Research continuity | 3 | The manual continuation survived reload and Recent reopening. Research-session continuity, uptake and comparison are unobserved. |
| Outcome usefulness | N/O | No research Outcome or Conclusion is available in this stock copy. |
| Evidence inspectability | N/O | There are no research evidence artifacts to trace. Exporting the brief does not test claim support. |
| Researcher agency | 4 | I forked an existing strategy, saved it, disabled/restored it and reopened it. Active-session intervention and model uptake remain untested. |
| Interaction quality and delight | 3 | Manual branching is smooth, but the current workspace offers prose where this investigation first needs a data-coverage decision and a small inspectable table. |
| Communication and reuse | 3 | Both stock and continued Text file exports downloaded and preserved the question and strategies. They communicate plans; no result-bearing paper was generated. |

## 8. Delight and friction

The brief resists several common ways to manufacture novelty, which earns initial trust. The disappointment is that those requirements are not yet backed by a visible imported-data or coverage artifact. The text report faithfully exports a research proposal, not a chemical result. Neither mobile width produced horizontal document overflow. This is a useful baseline, but does not measure comfort over a long research session.

## 9. Continuation test

Produce a small provenance/coverage table, decide whether pathway ranking is identifiable, then freeze parent-reactant and family groups before any fitting. If the data fail the gate, retain that negative feasibility result. The fork stores the plan; access, ingestion, computation and prospective validation remain unobserved.

Saved continuation: **Audit whether pathway pairs exist**. This text was supplied by the evaluator. It is not an AI-generated strategy or completed research finding.

## 10. Defects and opportunities

**High product dependency — evidence acquisition precedes the advertised scientific task.** Reproduce: open the first strategy and find the actual data/reference artifacts; there are none. Remedy: an explicit capability and data-readiness checkpoint, with an importable source/metadata ledger and an honest blocked outcome if unavailable. **Medium — stage size:** separate prior-art, coverage and baseline gates so a negative audit can count as useful progress.

Shared observations and proposed remedies are grouped in [SYNTHESIS](SYNTHESIS.md), rather than split into sample-specific implementation tickets. No fixes were made.

## 11. Overall judgment

- **Would I continue? Maybe.** I would use this as a planning scaffold only until it can preserve an actual dataset audit and a reproducible baseline. No evidence yet supports selecting it for chemical discovery.
- **Meaningful research progress: Not observable.** Manual planning advanced; no SIGMA investigation was available to judge.
- **Trust: Conditional.** I trust the observed persistence and explicit no-result state. I have no evidence here for the reliability of generated domain reasoning, source acquisition or conclusions.

## 12. Evidence appendix

- [Initial browser workspace](evidence/first-principles-catalysis-workspace.txt), [expanded view](evidence/first-principles-catalysis-expanded.txt) and [stock downloaded report](evidence/first-principles-catalysis-report.txt).
- [Saved continuation](evidence/first-principles-catalysis-continuation.txt), [continued downloaded report](evidence/first-principles-catalysis-continuation-report.txt), [Recent view](evidence/first-principles-catalysis-recent.txt).
- [Settings](evidence/first-principles-catalysis-settings.txt), [limits](evidence/first-principles-catalysis-limits.txt), [generation setup](evidence/first-principles-catalysis-generation-preflight.txt), [paper setup](evidence/first-principles-catalysis-paper-preflight.txt).
- [Continuation ledger](evidence/continuations.json), [deep checks and unchanged-source result](evidence/deep-observations.json), [actual full offline test log](evidence/sigma-test.log).
