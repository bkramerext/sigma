# Design and Verify an Incremental Dependency Scheduler — research experience evaluation

Blue · 2026-10-24 · observation coverage: browser workflow and authored scaffolding; research quality unobserved.

## 1. Sample identity and research objective

`algorithm-design`. Design a fully dynamic dependency scheduler at 100,000 vertices and 1,000,000 edges, with exact update semantics, correctness and honest complexity. The full canonical brief is in [project.json](../../../samples/algorithm-design/project.json). It was opened from Home → Samples into an isolated editable copy; the source hash remained unchanged.

## 2. Researcher expectation

A correct recomputation baseline, precise update semantics, a cycle witness, and an adversarial update sequence should precede any incremental speed claim. Useful progress is a proved invariant or a benchmark that rejects a proposed optimization at the stated graph scale.

## 3. Environment and runs

App revision `6059d67`, branch `blue/research-experience-study`; installed Chrome 156.0.8078.47 through Playwright, real headless browser. Desktop 1440×1000 and mobile emulation 390×844 / 320×700. The latter are viewport checks, not physical-phone testing. [Method](METHOD.md) and [browser inventory](evidence/browser-inventory.json) document isolation and hashes.

Saved preference: Sol (`gpt-6.1-sol`), High, access unverified; no model selected for an actual call. Stock sessions: **0**; study sessions: **0**; session IDs: none. No fixture playback or live research occurred for this sample. Generation was opened as a form only. Default future limits observed: three Skeptic iterations, 30 calls, one hour, 12,000 output tokens/call, no dollar cap; these are ceilings, not actual usage. Paper setup was inspected only. Live/provider calls: **0**, study provider charge **$0**; no token usage or model latency was measured. Automated first-pass navigation/export capture took 1.27s and the continuation capture 1.65s; these exclude reading/assessment and are not a human time-to-insight measure.

## 4. Research journey

I opened the Computer Science sample from Home and found a precise specification above an empty strategy pool. Rather than asking for a complete dynamic-graph solution, I created “Baseline before incremental claims.” I made duplicate insertions and absent-edge removals idempotent, requested a recomputation baseline and explicit adversarial workloads, then saved and reloaded it. Disable/Enable and Recent reopening retained the branch. Generate exposed a starting-point editor and connection requirement; I cancelled before inference. The paper dialog offered authoring bounds despite there being no research record.

## 5. Substantive findings

SIGMA preserved a useful human research plan. It derived no algorithm, ran no workload, produced no cycle witness and established no complexity bound. The prompt itself has a valuable separation between an implementable baseline and an optimization conjecture.

## 6. Independent critical assessment

Returning a complete order already has output-size cost; a meaningful incremental claim needs an update/query workload and a cost model. The prompt asks for these distinctions but the current empty experience gives no worked example or benchmark artifact. My manual text supplies the first discriminating test, so its quality cannot be credited to model assistance.

## 7. Rubric

Scores concern only the observed layer. Written prompt constraints do not validate agent behavior. N/O means not observed, not failure.

| Dimension | Score | Evidence and rationale |
|---|---:|---|
| Problem orientation | 4 | The question names graph scale, adversarial tests and the recomputation baseline; opening the sample immediately exposes the required deliverables. |
| Strategy quality | N/O | There are zero stock strategies and no generated candidate. The saved baseline was written by the evaluator. |
| Intellectual substance | N/O | No saved research session, analytical artifact or generated result exists; evaluator-authored plans do not count as SIGMA intellectual work. |
| Skepticism and epistemic integrity | 3 | The prompt explicitly rejects unproved efficiency claims; no Investigator/Skeptic behavior was observed. |
| Research continuity | 3 | The manual continuation survived reload and Recent reopening. Research-session continuity, uptake and comparison are unobserved. |
| Outcome usefulness | N/O | No research Outcome or Conclusion is available in this stock copy. |
| Evidence inspectability | N/O | There are no research evidence artifacts to trace. Exporting the brief does not test claim support. |
| Researcher agency | 4 | I created a new strategy, saved it, disabled/restored it and reopened it. Active-session intervention and model uptake remain untested. |
| Interaction quality and delight | 3 | The empty workspace is readable and responsive, but the only session guidance is to use Play; it does not help choose the first correctness obligation. |
| Communication and reuse | 3 | Both stock and continued Text file exports downloaded and preserved the question and strategies. They communicate plans; no result-bearing paper was generated. |

## 8. Delight and friction

Saving a narrow baseline was effortless, and reopening it did not require reconstructing intent. The disappointment is the gap between a demanding specification and an empty pool with execution controls: the first intellectual move is still entirely mine. Neither mobile width produced horizontal document overflow. This is a useful baseline, but does not measure comfort over a long research session.

## 9. Continuation test

Implement or import one baseline and a fixed adversarial update trace, then compare correctness before speed. The saved strategy makes the question resumable, but executable benchmarking and uptake by agents remain unobserved.

Saved continuation: **Baseline before incremental claims**. This text was supplied by the evaluator. It is not an AI-generated strategy or completed research finding.

## 10. Defects and opportunities

**Medium — no bridge from specification to first experiment.** Reproduce: Home → Computer Science → this sample; inspect the empty pool and Sessions guidance. Remedy: offer a small correctness-first investigation card with input semantics, expected artifact and stop criterion. This is an onboarding opportunity, not a failed algorithm implementation.

Shared observations and proposed remedies are grouped in [SYNTHESIS](SYNTHESIS.md), rather than split into sample-specific implementation tickets. No fixes were made.

## 11. Overall judgment

- **Would I continue? Maybe.** I would return if SIGMA can turn this saved baseline into an inspectable implementation and workload comparison. Today it functions as a durable planning notebook.
- **Meaningful research progress: Not observable.** Manual planning advanced; no SIGMA investigation was available to judge.
- **Trust: Conditional.** I trust the observed persistence and explicit no-result state. I have no evidence here for the reliability of generated domain reasoning, source acquisition or conclusions.

## 12. Evidence appendix

- [Initial browser workspace](evidence/algorithm-design-workspace.txt), [expanded view](evidence/algorithm-design-expanded.txt) and [stock downloaded report](evidence/algorithm-design-report.txt).
- [Saved continuation](evidence/algorithm-design-continuation.txt), [continued downloaded report](evidence/algorithm-design-continuation-report.txt), [Recent view](evidence/algorithm-design-recent.txt).
- [Settings](evidence/algorithm-design-settings.txt), [limits](evidence/algorithm-design-limits.txt), [generation setup](evidence/algorithm-design-generation-preflight.txt), [paper setup](evidence/algorithm-design-paper-preflight.txt).
- [Continuation ledger](evidence/continuations.json), [deep checks and unchanged-source result](evidence/deep-observations.json), [actual full offline test log](evidence/sigma-test.txt).
- [Desktop screenshot](evidence/algorithm-design-desktop.png) and [390px screenshot](evidence/algorithm-design-mobile.png); selective fresh viewport captures after continuation. Text dumps preserve the initial stock state.
