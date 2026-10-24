# Operation Narrow Passage — research experience evaluation

Blue · 2026-10-24 · observation coverage: browser workflow and authored scaffolding; research quality unobserved.

## 1. Sample identity and research objective

`operation-narrow-passage`. Investigate strategic choices in a clearly fictional October 2027 crisis involving Second Thomas Shoal, keeping assumptions and uncertain cooperation explicit. The full canonical brief is in [project.json](../../../samples/operation-narrow-passage/project.json). It was opened from Home → Samples into an isolated editable copy; the source hash remained unchanged.

## 2. Researcher expectation

Within the fictional premises I want a bounded comparison of strategic options, explicit decision dependencies, information gaps and de-escalation tradeoffs. A coherent plan is not a verified forecast; changing one premise should reveal which conclusions depend on it.

## 3. Environment and runs

App revision `6059d67`, branch `blue/research-experience-study`; installed Chrome 156.0.8078.47 through Playwright, real headless browser. Desktop 1440×1000 and mobile emulation 390×844 / 320×700. The latter are viewport checks, not physical-phone testing. [Method](METHOD.md) and [browser inventory](evidence/browser-inventory.json) document isolation and hashes.

Saved preference: Sol (`gpt-6.1-sol`), High, access unverified; no model selected for an actual call. Stock sessions: **0**; study sessions: **0**; session IDs: none. No fixture playback or live research occurred for this sample. Generation was opened as a form only. Default future limits observed: three Skeptic iterations, 30 calls, one hour, 12,000 output tokens/call, no dollar cap; these are ceilings, not actual usage. Paper setup was inspected only. Live/provider calls: **0**, study provider charge **$0**; no token usage or model latency was measured. Automated first-pass navigation/export capture took 1.26s and the continuation capture 1.59s; these exclude reading/assessment and are not a human time-to-insight measure.

## 4. Research journey

I opened the Military sample from Home, read the fictional framing and inspected the long scenario rather than assuming real events. There were no strategies or sessions. I created “Test one decision against changed premises,” focusing on a reversible option and a changed information assumption. I saved, reloaded, disabled/restored it and reopened it from Recent. Text export retained the scenario and branch. The generation starting-point form and paper setup were inspected only; no operational plan was generated.

## 5. Substantive findings

SIGMA produced no scenario analysis, comparison, forecast or recommendation. The explicit fictional framing is valuable, and the workspace preserves a human test plan. Prior STATUS accounts of generation on other copies are not observations from this study and are not credited here.

## 6. Independent critical assessment

A coherent course of action is not evidence that other actors cooperate, information arrives on time or a forecast is accurate. Useful progress would show which recommendation changes when a premise changes. The empty sample does not yet demonstrate this sensitivity analysis. I do not turn unverified or invented crisis premises into factual findings.

## 7. Rubric

Scores concern only the observed layer. Written prompt constraints do not validate agent behavior. N/O means not observed, not failure.

| Dimension | Score | Evidence and rationale |
|---|---:|---|
| Problem orientation | 2 | The scenario is detailed and clearly labeled fictional, but a long incident narrative precedes an empty strategy pool; no first bounded decision is surfaced. |
| Strategy quality | N/O | No stock strategies or generated proposals exist in this study copy. The bounded scenario experiment is evaluator-authored. |
| Intellectual substance | N/O | No saved research session, analytical artifact or generated result exists; evaluator-authored plans do not count as SIGMA intellectual work. |
| Skepticism and epistemic integrity | 3 | The fictional status is explicit. No run tested whether agents distinguish invented intelligence, uncertain cooperation and justified forecasts. |
| Research continuity | 3 | The manual continuation survived reload and Recent reopening. Research-session continuity, uptake and comparison are unobserved. |
| Outcome usefulness | N/O | No research Outcome or Conclusion is available in this stock copy. |
| Evidence inspectability | N/O | There are no research evidence artifacts to trace. Exporting the brief does not test claim support. |
| Researcher agency | 4 | I created a new strategy, saved it, disabled/restored it and reopened it. Active-session intervention and model uptake remain untested. |
| Interaction quality and delight | 2 | A large scrollable scenario and empty execution workspace require substantial reading before the first useful action; mobile width fits but does not remove that burden. |
| Communication and reuse | 3 | Both stock and continued Text file exports downloaded and preserved the question and strategies. They communicate plans; no result-bearing paper was generated. |

## 8. Delight and friction

The scenario is substantial enough to provoke real tradeoff questions. Yet the interface asks me to translate that complexity into a strategy without a decision map. The paper action is visible before there is even one bounded finding to communicate. Neither mobile width produced horizontal document overflow. This is a useful baseline, but does not measure comfort over a long research session.

## 9. Continuation test

Compare two high-level options against one changed premise, record decision dependencies and stop after identifying what information would reverse the choice. The saved strategy makes that possible in prose. Parameterized branches and side-by-side scenario outcomes were not observed.

Saved continuation: **Test one decision against changed premises**. This text was supplied by the evaluator. It is not an AI-generated strategy or completed research finding.

## 10. Defects and opportunities

**Medium — scenario complexity is delivered as undifferentiated text.** Reproduce: Home → Military → sample; compare the long Project area with zero strategies/sessions. Remedy: a compact premise, actor, uncertainty and decision-dependency view that links to the full scenario. **Medium — no demonstrated sensitivity workflow:** the manual branch is a new text card, not a scenario comparison.

Shared observations and proposed remedies are grouped in [SYNTHESIS](SYNTHESIS.md), rather than split into sample-specific implementation tickets. No fixes were made.

## 11. Overall judgment

- **Would I continue? Maybe.** I would try one bounded decision experiment, but the current experience has not shown a benefit over a scenario document and a comparison table.
- **Meaningful research progress: Not observable.** Manual planning advanced; no SIGMA investigation was available to judge.
- **Trust: Conditional.** I trust the observed persistence and explicit no-result state. I have no evidence here for the reliability of generated domain reasoning, source acquisition or conclusions.

## 12. Evidence appendix

- [Initial browser workspace](evidence/operation-narrow-passage-workspace.txt), [expanded view](evidence/operation-narrow-passage-expanded.txt) and [stock downloaded report](evidence/operation-narrow-passage-report.txt).
- [Saved continuation](evidence/operation-narrow-passage-continuation.txt), [continued downloaded report](evidence/operation-narrow-passage-continuation-report.txt), [Recent view](evidence/operation-narrow-passage-recent.txt).
- [Settings](evidence/operation-narrow-passage-settings.txt), [limits](evidence/operation-narrow-passage-limits.txt), [generation setup](evidence/operation-narrow-passage-generation-preflight.txt), [paper setup](evidence/operation-narrow-passage-paper-preflight.txt).
- [Continuation ledger](evidence/continuations.json), [deep checks and unchanged-source result](evidence/deep-observations.json), [actual full offline test log](evidence/sigma-test.log).
- [Desktop screenshot](evidence/operation-narrow-passage-desktop.png) and [390px screenshot](evidence/operation-narrow-passage-mobile.png); selective fresh viewport captures after continuation. Text dumps preserve the initial stock state.
