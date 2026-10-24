# Maximum Regions Formed by Lines — research experience evaluation

Blue · 2026-10-24 · coverage: stock browser workflow plus an unmodified supplementary historical provider record. No new live research.

## 1. Sample identity and research objective

`maximum-regions-by-lines` asks for the greatest number of regions cut by `n` distinct entire straight lines, with a universal bound, an attaining arrangement, `n=0` and small checks. The [stock sample](../../../samples/maximum-regions-by-lines/project.json) has one human-authored insertion strategy and no sessions.

A separate [repository archive](../fixtures/t17-8-answer-free/live-session-91e96112-27ce-412e-841f-5cbf67cbba75.json) contains an earlier, closely matched Maximum Regions investigation. I imported an isolated copy for supplementary review. It is not history shipped with the stock sample. Only `project_path` was relocated; no question, argument, role output or review was supplemented with newer structured fields.

## 2. Researcher expectation

I wanted an upper bound on each insertion, a reason the new line’s pieces split distinct old regions, and an explicit family attaining the bound for every `n`. A formula and successful small checks are insufficient. A productive Skeptic should find a missing geometric step and prompt its repair, then stop once the actual argument is adequate.

## 3. Environment and runs

App `6059d67`, Chrome `156.0.8078.47` through Playwright, desktop 1440×1000, 390×844 and 320×700 emulation for the stock workspace. [METHOD](METHOD.md) describes isolated roots and blocked provider transport. Study sessions/provider calls: **0**; study provider charge **$0**. Both copies are disposable; source hashes and the archived export are unchanged.

Stock preference: `gpt-6.1-sol`, High, access unverified. Default future limits observed: three iterations, 30 calls, one hour, 12,000 output tokens/call and no dollar cap. I did not start that session.

Supplementary session `91e96112-27ce-412e-841f-5cbf67cbba75` is preserved as an earlier ChatGPT-plan provider run, with Sol/High, ended after four of six calls and two of three cycles. Historical metrics report 2m29s wall time, 32,042 input and 6,549 output tokens, no Python/Sage executions, and unknown plan allowance consumption. These are saved metadata, not measurements of a new live run or independently audited billing. The main artifacts are `2a734507-ad3f-4d5b-b00b-80b0e1624717` and `a832588d-9da7-4ceb-b3ff-9451a9922ff5`.

Automated stock capture took 1.23s and manual-continuation capture 1.64s; neither includes reading or independent assessment. The historical 2m29s is disproportionate to a few-line final answer unless the proof repair and educational value matter to the user; it cannot predict current model latency.

## 4. Research journey

From Home → Samples → Mathematics I opened the stock sample and its insertion strategy. No Outcome existed. I forked “Separate the bound from attainment,” saved it, reloaded, disabled/restored it and reopened from Recent. The text export retained the new plan. Generation and paper setup were inspected without submission.

To go beyond an empty workspace, I copied the original archived project/session to the isolated project root. From Home I used Open, entered that local directory and opened its session. The first surprise was its current classification: **“Mixed · substantive argument not captured.”** The original archive calls it a positive unverified candidate. Current rendering downgrades the historical record because it lacks structured argument steps.

Expanding the Outcome reveals a long Skeptic response containing a complete argument. The historical Conclusion itself is unavailable; the new panel honestly shows a historical-session placeholder. Yet the surrounding text says the candidate cannot be assessed as a complete argument “from this record,” while the record visibly contains substantial reasoning. “Findings by strategy” calls the contribution achieved. The user must reconcile these layers.

I opened the artifacts and inspected the objection that drove the second cycle: the proposed family had not yet shown distinct intersections on each new line. The follow-up computes the intersections and completes attainment. That is a real intellectual turning point in the preserved record, not merely an additional status update.

I exported HTML through the browser, then opened the downloaded document in Chrome. It contains the formula, candidate/verification caveats and the archived evidence; the rendered text is 26,723 characters. I also opened the findings-derived fork and inspected its prefill before cancelling. It retains the old attainment objection and further completion obligations even though the final review says they are resolved. The draft is traceable but not a reconciled next research question.

## 5. Substantive findings

The archived argument supports `M(n)=1+n(n+1)/2` under the stated Euclidean interpretation:

- Old regions are nonempty intersections of open half-planes and therefore convex.
- A new line with `t` distinct old intersection points has `t+1` pieces. Convexity ensures different pieces lie in different old regions, each of which is split in two.
- At insertion `k`, `t≤k−1`, so at most `k` regions are added.
- For `L_k: y=kx+k²`, solving with `L_i` gives `(-(i+k),-ik)`. For fixed `k`, distinct predecessor indices give distinct crossings. Every insertion attains the bound.
- The empty arrangement has one region.

This is more than a memorized closed form: it addresses the subtle distinct-region and attainment obligations. The first critique identifies a recoverable gap, and the follow-up resolves it. Nothing here proves novel mathematics or demonstrates the same behavior on hard/open problems.

## 6. Independent critical assessment

I independently checked the algebra of the intersections and read the convexity/splitting argument. The displayed proof is convincing as an elementary mathematical argument; formal verification did not run. The result is standard, and the useful research assistance is explanatory repair and preservation, not novelty.

The second Investigator output is reported as ending before its final conclusion. The saved Skeptic does substantive synthesis: it combines the earlier insertion proof with the explicit calculation and supplies a complete argument rather than requiring another cycle just to restate the conclusion. That is a good example of stopping for an intellectual reason.

The new schema boundary creates a different failure: missing structured steps are treated as missing substantive argument, even though the historical text is inspectable. Conservative labeling is appropriate; “unstructured historical argument available” would be more accurate than implying absence. Conversely, I would not silently fill structured fields from my own proof and present the result as agent-produced. This study deliberately did not apply the enrichment used in an older browser acceptance script.

Open obligations also need lifecycle handling. In the current UI and fork, “finish … attainment and n=0” persists alongside the final review’s resolution. A user resuming work could waste a run repairing an already repaired gap. This is not a conflict between two mathematical findings; it is inconsistent projection of research state.

## 7. Rubric

The rows concerning actual reasoning refer to the **supplementary historical provider record**. The stock sample alone would have N/O for substance, Outcome and evidence. Scores do not validate current live-model behavior.

| Dimension | Score | Observed evidence and rationale |
|---|---:|---|
| Problem orientation | 4 | The stock question and insertion strategy clearly separate upper bound and attainment; supplementary history supplies a concrete local gap. |
| Strategy quality | 4 | Insertion has a meaningful local test and explicit construction duty; a manual bound/attainment fork is easy to formulate. Stock strategy is human-authored. |
| Intellectual substance | 4 | Archived convexity proof, exact intersection calculation and repaired attainment are independently checkable. |
| Skepticism and epistemic integrity | 3 | The saved Skeptic identifies and repairs a genuine gap without claiming formal verification; current historical labels are inconsistent with the available argument. |
| Research continuity | 2 | Original evidence survives, but resolved objections and “still open” work carry into the continuation draft; the user reconstructs the final state. |
| Outcome usefulness | 2 | A correct candidate exists in detailed prose, while the headline says substantive argument not captured and the new Conclusion is only a historical placeholder. |
| Evidence inspectability | 3 | Both artifacts and role outputs are present; local “Artifact 1” references are text, and the reader must navigate nested sections manually. |
| Researcher agency | 4 | Stock fork, save/reload, eligibility changes and Recent work; the findings-derived draft is editable and cancellable. Agent uptake is untested. |
| Interaction quality and delight | 3 | Understanding why each crossing creates a region is satisfying; conflicting status layers and dense repetition detract. Stock mobile widths fit. |
| Communication and reuse | 3 | Browser-exported HTML opens and retains the argument/caveats, but a 26K-character record is much longer than the useful proof and carries stale obligations. Paper authoring was not run. |

## 8. Delight and friction

The best moment is the attaining family: a small calculation turns “generic position should work” into a concrete construction for every `n`. The saved Skeptic’s decision to supply the missing synthesis also feels like useful collaboration.

The most frustrating moment is seeing that argument underneath a warning that substantive argument was not captured. The interface is faithful to the presence or absence of new fields, but not yet faithful enough to what a human can learn from the historical evidence. The enormous record compared with the compact mathematics also matters for reuse.

## 9. Continuation test

For the historical question, I would first independently review the compact proof and mark its obligations reconciled. I would not rerun the same attainment check just because the fork lists it. A genuinely new branch might change assumptions, such as restricting line directions, but that would be a different objective and should retain its new assumptions explicitly.

SIGMA can preserve and fork the evidence. It does not currently make the distinction between “verify the already completed elementary argument” and “continue unresolved research” sufficiently clear in this historical experience.

## 10. Defects and opportunities

- **High — structured-field absence obscures available historical reasoning.** Reproduce: import the unchanged linked archive, open its Outcome, compare the headline with the full Skeptic response. Remedy: preserve a distinct historical/unstructured-evidence status and expose the saved argument without inventing a newly structured proof.
- **High — resolved work survives as open continuation work.** Reproduce: compare final resolved objections with “Still open,” then inspect Fork strategy from findings. Remedy: a claim/obligation ledger with explicit supersession, source links and a human-reviewable current state before branching.
- **Medium — outcome packaging is too large for the useful argument.** Reproduce: download HTML and compare its 26,723 rendered characters with the five-step proof above. Remedy: a concise mathematical narrative with expandable audit details, retaining the failed first attempt and caveat.
- **Medium — source labels are not direct navigation.** Reproduce: try to follow “Artifact 1, Artifact 2” beside Outcome. Remedy: link the claim to the exact saved argument and objection, with stable cross-session identity.

No implementation changes were made. Historical behavior does not imply the same omissions in newly structured provider outputs; fresh live behavior remains untested.

## 11. Overall judgment

- **Would I continue? Yes, conditionally.** I would use the preserved argument as a basis for review and a precisely changed question. It is the strongest substantive example examined, despite poor current packaging.
- **Meaningful research progress: Partial.** The historical provider record contains useful proof repair and a complete elementary argument. This study performed no new live research; the stock sample alone has no result.
- **Trust: Conditional.** The readable proof earns more trust than either the original positive label or the current downgraded label. I trust the mathematics after inspection, not because two agents agreed.

## 12. Evidence appendix

- [Stock initial workspace](evidence/maximum-regions-by-lines-workspace.txt), [stock report](evidence/maximum-regions-by-lines-report.txt), [manual continuation](evidence/maximum-regions-by-lines-continuation.txt).
- [Supplementary archive initial rendering](evidence/maximum-regions-archive-initial.txt), [expanded evidence](evidence/maximum-regions-archive-expanded.txt), [Conclusion screenshot](evidence/maximum-regions-archive-conclusion.png), [mobile screenshot](evidence/maximum-regions-archive-mobile.png).
- [Downloaded historical HTML report](evidence/maximum-regions-archive-report.html), [Chrome report screenshot](evidence/maximum-regions-html.png), [HTML inspection results](evidence/deep-observations.json).
- [Findings-fork prefill](evidence/maximum-regions-archive-fork-prefill.txt), [paper setup only](evidence/maximum-regions-archive-paper-preflight.txt).
- [Independent arithmetic checks](evidence/independent-checks.json), [archive browser driver](evidence/scripts/archive_pass.py), [offline test results](evidence/sigma-test.txt).
