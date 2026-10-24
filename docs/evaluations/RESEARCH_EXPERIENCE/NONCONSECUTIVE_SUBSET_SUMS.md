# Nonconsecutive Subset Sums Modulo 3 — research experience evaluation

Blue · 2026-10-24 · coverage: actual Chrome interaction with five archived deterministic fixture sessions, plus manual continuation. No live research.

## 1. Sample identity and research objective

`nonconsecutive-subset-sums` asks for an integer constant-coefficient recurrence for nonadjacent subsets of `{1,…,n}` whose sum is divisible by three, sufficient initial values, the exact count at `n=12`, and a proof of limiting density `1/3` among all nonadjacent subsets. See the [canonical project](../../../samples/nonconsecutive-subset-sums/project.json) and [saved fixture evidence](../../../samples/nonconsecutive-subset-sums/sample-evidence.json).

Unlike the other stock samples, this one arrives with a research history. Its three approaches are periodic state transitions, root-of-unity filtering and gap removal. The source remained unchanged; all interaction used the browser-created working copy.

## 2. Researcher expectation

I wanted a recurrence derived from state transitions rather than fitted to numbers, an independently checkable `a_12`, and control of nontrivial residue modes for the limit. A failed conjecture would count as progress if the next attempt used its counterexample. A corrected derivation should retain the old error but make its supersession obvious.

## 3. Environment and runs

App `6059d67`, Chrome 156.0.8078.47 through Playwright, desktop 1440×1000 and 390×844/320×700 mobile emulation. The recorded exact Chrome version is authoritative in the [inventory](evidence/browser-inventory.json). Isolated project/history/auth roots and provider-blocking transport are described in [METHOD](METHOD.md). No study research sessions or provider calls were started; study provider cost **$0**. Generation and paper dialogs were opened without submitting inference.

All five saved sessions identify `gpt-6.1-sol`, High, `api_key` mode, two calls used of six, one cycle, 60-minute limit and 12,000 output tokens/call. **These are archived deterministic fixtures, not actual paid sessions or fresh model behavior.** Their metrics have incomplete token/cost metadata and round wall time to zero seconds. Those values cannot estimate real research speed or plan consumption. The saved executions report Python 3.12.8, completed status, source/output and sandbox provenance; this study inspected them and separately ran evaluator checks, without rerunning them inside SIGMA.

| Session | Saved session ID | Main artifact ID | Recorded contribution |
|---|---|---|---|
| 1 | `1a9a0c44-48ae-49e7-8bea-0e8d47297f9d` | `1cc6ec50-87c0-46f4-b1dd-a82857d74f9e` | Refutes a guessed short recurrence |
| 2 | `1aabbfc0-e642-4581-a96f-2e33ac17ee19` | `ccc1045f-479d-4018-b8ed-42a60b94e567` | Candidate order-12 relation and `a_12=128` |
| 3 | `f7301d22-fd90-4675-95cd-17b006262ef9` | `02ca743b-d66f-41c0-8692-34579ea5adfa` | Gap-removal identity with an erroneous explanation |
| 4 | `6c552b3c-44e4-4b57-8b93-e5a645d057d1` | `5e15b337-adf1-483c-8ba6-7cd2de5f500b` | Revisit using prior findings and DP through 60 |
| 5 | `7c70ca6e-3fb2-4cda-b75a-72702ee10d97` | `516c2288-3458-40b2-9e02-87a918c35a3a` | Repairs the Gaussian-binomial normalization explanation |

The automated catalog capture took 13.51 seconds and continuation capture 3.31 seconds; these exclude reading and assessment. They are not human task-completion times.

## 4. Research journey

From Home → Samples → Mathematics I opened the sample, expanded its three approaches and each of the five session rows. All were ended, with “Mixed · partial progress, unresolved.” This was immediately more engaging than the empty samples: there was a specific claim to doubt.

Session 1 supplied the first useful turning point. The guessed `a_(n+3)=a_(n+2)+a_n` fails at `n=2`: `a_5=5`, whereas `a_4+a_2=4`. The review correctly says this refutes the guess, not the counting problem. I opened Citations, Evidence & Obligations, expanded its artifact and inspected the execution source/output. The failure is small enough to understand without trusting an agent.

Session 2 offered a more credible root-of-unity route and a candidate relation. Its objections require ordered phase products, boundary handling and an asymptotic bound. Session 3 offered an independent encoding, but reading its exponent calculation exposed an error hidden by the correct displayed formula. The scripted Skeptic endorsed the result without catching that explanation. Session 5 repaired it explicitly. This was the most revealing trust test in the stock inventory: the history preserves both a mistake and a later correction, but a reader must reconcile them.

I expanded Provenance in Session 4 and clicked its prior-source control for Session 1. The target session expanded and the browser moved to it. That navigation worked. By contrast, “Outcome evidence: Artifact 1” is plain text rather than a clickable evidence reference, requiring manual opening and matching elsewhere.

I inspected “Fork strategy from findings” from Session 4. Its prefill carries the claim, objections, obligations and parent approach into an editable draft. It also repeats related obligations and says “Next question: None recorded,” despite the saved Skeptic asking about exact phase products and eigenvalues. I cancelled that draft, then used a normal strategy fork to save my own bounded continuation, “Close the phase-matrix proof obligation.” Reload, Disable/Enable, Recent reopening and text export all preserved it. This was manual steering, not agent uptake.

## 5. Substantive findings

The saved history supports three concrete kinds of partial progress:

1. A counterexample rejects one attractive short recurrence and prevents its reuse in the later narrative.
2. Exact finite computations agree on `a_0,…,a_12 = 1,1,1,2,3,5,8,12,19,31,49,79,128`, and support the candidate relation
   `a_(n+12)-5a_(n+9)+2a_(n+6)+5a_(n+3)+a_n=0` over recorded finite ranges.
3. A gap-removal identity provides another encoding, and the later session corrects its normalization explanation without discarding the valid formula.

The saved record does **not** close the general recurrence or density proof. More zero residuals do not establish an all-`n` identity. The fixture narrative in Session 4 uses earlier findings, but it cannot establish that real agents retrieve and reason from prior work reliably.

## 6. Independent critical assessment

I independently enumerated subsets through `n=16`, confirming `a_12=128` and the short-rule failure. Exact integer-pair arithmetic in `Z[ω]/(ω²+ω+1)` verified that each of the three ordered three-phase products has trace one and determinant minus one. This supports a concrete next derivation, rather than an indefinite request for more computation. See [independent checks](evidence/independent-checks.json) and its [source](evidence/scripts/independent_checks.py). This is evaluator work outside SIGMA, not formal proof verification or a completed app research session.

The Session 3 explanation says that both shifts contribute `k(k−1)/2`, then concludes their sum is `k²`. It is not: at `k=2` that would yield two rather than four. Under the standard partition-normalized Gaussian-binomial convention, the ordinary subset sum contributes `k(k+1)/2`; adding the gap shift then gives `k²`. Session 5 gets this right. The lesson is specific: a correct formula and successful finite check can conceal a faulty written derivation, even after a reviewer agrees.

A separate UI issue overstates confidence. The saved review is `incomplete`, and Metrics says “Incomplete,” while the expanded Solution review shows **“Convincing but unverified.”** Static inspection of `frontend/src/main.tsx` confirms that every known non-`verified` status is mapped to that label there. This is a reproduced presentation defect, not a conjecture about model behavior.

The app commendably avoids manufacturing a new Conclusion for historical sessions. Yet a raw `### Historical session` placeholder occupies the primary conclusion position, and several layers repeat the question, claim and caveats. Preservation is strong; synthesis for the reader is weaker.

## 7. Rubric

Scores concern this archived fixture experience, not live-agent competence.

| Dimension | Score | Observed evidence and rationale |
|---|---:|---|
| Problem orientation | 4 | Exact objectives and three distinct encodings; an actual false guess makes the local question intelligible. |
| Strategy quality | 4 | State transitions, root filters and a bijection provide discriminating alternatives with tests; the pool is human-authored. |
| Intellectual substance | 4 | Checkable counterexample, finite exact counts and a repaired algebraic explanation. The global proof is still absent. |
| Skepticism and epistemic integrity | 2 | Good finite-versus-proof caveats coexist with a missed explanatory error and an `incomplete` review labeled convincing. |
| Research continuity | 3 | Prior-source navigation and historical correction work; duplicates and stale next-question/obligation text require reconstruction. |
| Outcome usefulness | 3 | Correctly calls the work partial and leaves global goals open; repeated detail and the historical Conclusion placeholder obscure the immediate next move. |
| Evidence inspectability | 3 | Source/output and provenance are saved and readable; local Outcome references are plain text and the nested view is verbose. |
| Researcher agency | 4 | Findings-derived drafts and a saved manual fork support redirection; reload, eligibility changes and Recent reopening worked. No live intervention was tested. |
| Interaction quality and delight | 3 | Finding and checking a counterexample is intellectually satisfying; nested repetitive sections make five modest sessions feel much larger. Both mobile widths fit. |
| Communication and reuse | 3 | Downloaded text retains failures, corrected reasoning and caveats; it reads like an organized record rather than a compact mathematical account. Paper authoring was only inspected. |

## 8. Delight and friction

The product earned trust at the explicit counterexample: failure produced knowledge. It earned more at Session 5’s distinction between correcting the explanation and retracting the formula. These are useful research events.

It lost trust at the uniform convincing label and at the original review’s endorsement of incorrect algebra. It lost momentum when a budget-ended artifact said there was no next question even though the Skeptic had supplied one. The correct next intellectual task is already in the evidence; the reader should not have to extract it from several copies of the same prose.

## 9. Continuation test

A real next step is to write the phase-ordered matrix identity, account for initial indices, and compare nontrivial-mode growth with Fibonacci growth. Repeating finite tests to 600 instead of 60 would add less value. My saved continuation states that distinction and preserves the corrected Gaussian convention.

The app lets me make that branch and resume it. It has not demonstrated that a subsequent live session will execute the proof, reuse the correction or retire discharged obligations. “Fork from findings” is useful raw material, but needs judgment before submission.

## 10. Defects and opportunities

- **High — confidence status is mistranslated.** Reproduce: open Session 1 → Citations, Evidence & Obligations → Solution review; compare its Verification text with Metrics and saved `incomplete`. Remedy: preserve all distinct epistemic states consistently in UI, Markdown and reports.
- **High research-quality warning — agreement misses a derivation error.** Reproduce: read Session 3 Method and Skeptic response, then Session 5. Remedy: require criticism to inspect the decisive algebra or test a small symbolic case; do not advertise reviewer agreement as independent verification. This particular error is fixture-authored, so its frequency in live models remains untested.
- **Medium — next question is lost at the artifact/fork boundary.** Reproduce: inspect Session 4’s saved Skeptic next question, artifact “None recorded” and findings-fork draft. Remedy: preserve the intellectually useful next question independently of why execution stopped.
- **Medium — repetition replaces reconciled research state.** Reproduce: expand the five sessions and the findings-fork draft. Remedy: show one current obligation ledger with superseded/resolved/open links, keeping original records accessible.
- **Medium — local evidence labels are not navigation.** Reproduce: try to follow “Artifact 1” beside the Outcome; manually opening evidence works, but that label is not a control. Remedy: stable, direct claim-to-artifact/source navigation, including a cross-session identifier.

These are themes for product prioritization, not seventeen new tickets. No fixes were implemented.

## 11. Overall judgment

- **Would I continue? Yes, conditionally.** There is enough checkable partial work to make a precise next proof attempt worthwhile.
- **Meaningful research progress: Partial, in the archived fixture content.** A conjecture is refuted and an explanation repaired. No new live research was performed, and fixture behavior does not validate autonomous research quality.
- **Trust: Conditional.** I trust the inspectable computations more than labels or reviewer assent. The incorrect confidence label and repaired prose error make direct evidence reading essential.

## 12. Evidence appendix

- [Initial browser state](evidence/nonconsecutive-subset-sums-workspace.txt), [fully expanded evidence text](evidence/nonconsecutive-subset-sums-expanded.txt), [artifact screenshot](evidence/nonconsecutive-artifact.png).
- [Stock text report](evidence/nonconsecutive-subset-sums-report.txt), [continued text report](evidence/nonconsecutive-subset-sums-continuation-report.txt), [saved manual branch](evidence/nonconsecutive-subset-sums-continuation.txt).
- [Desktop](evidence/nonconsecutive-subset-sums-desktop.png), [390px viewport](evidence/nonconsecutive-subset-sums-mobile.png), [deep navigation/fork observations](evidence/deep-observations.json).
- [Paper setup only](evidence/nonconsecutive-subset-sums-paper-preflight.txt); no paper or PDF was generated. [Full offline check log](evidence/sigma-test.log).
