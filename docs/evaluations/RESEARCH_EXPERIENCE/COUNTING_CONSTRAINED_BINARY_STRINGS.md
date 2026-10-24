# Counting Constrained Binary Strings — research experience evaluation

Blue · 2026-10-24 · observation coverage: browser workflow and authored scaffolding; research quality unobserved.

## 1. Sample identity and research objective

`counting-constrained-binary-strings`. Count strings with no adjacent ones, including the empty string, and justify a recurrence or formula with base cases. The full canonical brief is in [project.json](../../../samples/counting-constrained-binary-strings/project.json). It was opened from Home → Samples into an isolated editable copy; the source hash remained unchanged.

## 2. Researcher expectation

A brief decomposition by the final bit, correct empty-string and length-one bases, and small enumerations would be enough. The tool should make a simple insight easier to see without requiring a research bureaucracy.

## 3. Environment and runs

App revision `6059d67`, branch `blue/research-experience-study`; installed Chrome 156.0.8078.47 through Playwright, real headless browser. Desktop 1440×1000 and mobile emulation 390×844 / 320×700. The latter are viewport checks, not physical-phone testing. [Method](METHOD.md) and [browser inventory](evidence/browser-inventory.json) document isolation and hashes.

Saved preference: Sol (`gpt-6.1-sol`), High, access unverified; no model selected for an actual call. Stock sessions: **0**; study sessions: **0**; session IDs: none. No fixture playback or live research occurred for this sample. Generation was opened as a form only. Default future limits observed: three Skeptic iterations, 30 calls, one hour, 12,000 output tokens/call, no dollar cap; these are ceilings, not actual usage. Paper setup was inspected only. Live/provider calls: **0**, study provider charge **$0**; no token usage or model latency was measured. Automated first-pass navigation/export capture took 1.17s and the continuation capture 1.56s; these exclude reading/assessment and are not a human time-to-insight measure. The binary-counting copy was subsequently reduced to one iteration/two calls and verified after reload; canonical settings were untouched.

## 4. Research journey

I opened the Mathematics sample, saw zero strategies and zero sessions, and created a final-bit decomposition plan. After saving, I reloaded, disabled/restored the strategy and reopened it from Recent. I inspected the generation context, paper dialog and default limits. In a further browser pass I changed the isolated copy from three Skeptic iterations and 30 calls to one iteration and two calls, saved, and verified those values after reload. The duration remained one hour. No session was started.

## 5. Substantive findings

No recurrence was derived by SIGMA. The app successfully stored a proof plan and a deliberately smaller future run budget. The parameter change is itself an evaluation observation: the user can reduce orchestration overhead without modifying the canonical sample.

## 6. Independent critical assessment

A correct solution should partition the last-bit cases and establish two bases; the empty string cannot be silently omitted. My plan requests that work, but the app has not performed it. Even a correct eventual answer would need to justify the interaction cost against solving this short exercise directly.

## 7. Rubric

Scores concern only the observed layer. Written prompt constraints do not validate agent behavior. N/O means not observed, not failure.

| Dimension | Score | Evidence and rationale |
|---|---:|---|
| Problem orientation | 4 | The problem is short, exact and visibly includes n=0 and small checks. |
| Strategy quality | N/O | The stock pool is empty; “Partition by the final bit” was my manual plan, not a generated strategy. |
| Intellectual substance | N/O | No saved research session, analytical artifact or generated result exists; evaluator-authored plans do not count as SIGMA intellectual work. |
| Skepticism and epistemic integrity | 3 | The question requires justification and does not prescribe a method. No review of an actual recurrence was available. |
| Research continuity | 3 | The manual continuation survived reload and Recent reopening. Research-session continuity, uptake and comparison are unobserved. |
| Outcome usefulness | N/O | No research Outcome or Conclusion is available in this stock copy. |
| Evidence inspectability | N/O | There are no research evidence artifacts to trace. Exporting the brief does not test claim support. |
| Researcher agency | 4 | I created a new strategy, saved it, disabled/restored it and reopened it. Active-session intervention and model uptake remain untested. |
| Interaction quality and delight | 2 | A simple counting insight opens into an empty pool, research controls and a paper action. The interface provides no shorter explanatory path. |
| Communication and reuse | 3 | Both stock and continued Text file exports downloaded and preserved the question and strategies. They communicate plans; no result-bearing paper was generated. |

## 8. Delight and friction

The limits were editable and durable, which gives the user practical control. It is frustrating to discover that the default is 30 calls for a question whose useful explanation should fit on a small card; this is a ceiling, not a claim that 30 calls will be used. Neither mobile width produced horizontal document overflow. This is a useful baseline, but does not measure comfort over a long research session.

## 9. Continuation test

Run the single pair only with separate authorization, inspect the two bijections and bases, and stop if the explanation is complete. The smaller limit persisted. Whether SIGMA stops for intellectual completion rather than merely reaching a cap is unobserved.

Saved continuation: **Partition by the final bit**. This text was supplied by the evaluator. It is not an AI-generated strategy or completed research finding.

## 10. Defects and opportunities

**Medium — simple questions inherit heavyweight controls and generic limits.** Reproduce: open this empty sample and inspect Settings → Limits; defaults are three iterations, 30 calls, one hour and 12,000 output tokens per call. Remedy: suggest a short explanation mode with a clear completion criterion, while preserving user control. Do not equate the default cap with actual consumption.

Shared observations and proposed remedies are grouped in [SYNTHESIS](SYNTHESIS.md), rather than split into sample-specific implementation tickets. No fixes were made.

## 11. Overall judgment

- **Would I continue? No.** For this elementary question the observed planning overhead exceeds the benefit. I would use it as a calibration example, not my preferred research environment.
- **Meaningful research progress: Not observable.** Manual planning advanced; no SIGMA investigation was available to judge.
- **Trust: Conditional.** I trust the observed persistence and explicit no-result state. I have no evidence here for the reliability of generated domain reasoning, source acquisition or conclusions.

## 12. Evidence appendix

- [Initial browser workspace](evidence/counting-constrained-binary-strings-workspace.txt), [expanded view](evidence/counting-constrained-binary-strings-expanded.txt) and [stock downloaded report](evidence/counting-constrained-binary-strings-report.txt).
- [Saved continuation](evidence/counting-constrained-binary-strings-continuation.txt), [continued downloaded report](evidence/counting-constrained-binary-strings-continuation-report.txt), [Recent view](evidence/counting-constrained-binary-strings-recent.txt).
- [Settings](evidence/counting-constrained-binary-strings-settings.txt), [limits](evidence/counting-constrained-binary-strings-limits.txt), [generation setup](evidence/counting-constrained-binary-strings-generation-preflight.txt), [paper setup](evidence/counting-constrained-binary-strings-paper-preflight.txt).
- [Continuation ledger](evidence/continuations.json), [deep checks and unchanged-source result](evidence/deep-observations.json), [actual full offline test log](evidence/sigma-test.log).
