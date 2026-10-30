# Round 9 — claim-detail experiment results

Implementation commit verified before generation: d4b9ab0ce55a7f05e053b43f96704528a676248c on chat/336-paper-editorial-prompts.

For every completed generation, I explicitly passed these options to papers.generate; I did not rely on dialog defaults:

- Include claim details: true
- Include validation notes: false
- Include research excerpts: false
- Legacy include research details: false

Generation metadata for the three completed papers records exactly those values. Model: gpt-6.1-sol, high reasoning effort, ChatGPT sponsor mode. Original projects and their earlier paper artifacts were left untouched. No tests, CI, source edits, merges, deployments, or new research sessions were performed.

## Generation results

| Project / source project ID | Paper ID | Elapsed / calls | Sources; omitted fields | Snapshot SHA-256 |
|---|---|---:|---|---|
| Maximum Regions by Lines v2 / 01af8ffa-60c3-4eea-bc15-36dca347ddfa | 4c960d6626db46c69e263401c4b13696 | 136.4 sec / 1 | 5; 0 | 2005c72323f7a950abb220575119ec875e3aab9ceb50fd28d13b5c2fb512701a |
| Nonconsecutive Subset Sums v9 / 57d67c57-15dc-433d-828a-7953f7986ff8 | 5a86804e917e4c07b9ec92df2541bd5f | 306.0 sec / 6 | 15; 1,027 | 648fceaa37a9c18511b277959c3550d06d2b4fc269deffb2f984b8001450d150 |
| Xenopus Tail Regeneration v9 / 01de54c9-9593-413a-9577-1a952d28da70 | d62d7c7a45134b0085cadee89091fa54 | 203.1 sec / 5 | 12; 1,863 | bfcb3190e593cca7cee3494c799348032c53e01de09507ff717fff5e7aeabf47 |
| Operation Narrow Passage v3 / 4060cb04-3ed7-4ae4-9f61-2c3691313759 | No valid completed round-9 paper | See ONP note | Intended input has 4 sources; initial attempt indexed 3 and omitted the saved session | — |

The Maximum Regions, Nonconsecutive, and Xenopus PDFs each have TeX and text companions with the same stem in messages/artifacts:

- maximum-regions-v2_d4b9ab0c_4c960d6626db46c69e263401c4b13696.pdf, .tex, .txt
- nonconsecutive-subset-sums-v9_d4b9ab0c_5a86804e917e4c07b9ec92df2541bd5f.pdf, .tex, .txt
- xenopus-tail-regeneration-v9_d4b9ab0c_d62d7c7a45134b0085cadee89091fa54.pdf, .tex, .txt

Compared with round 8, the project, strategy, and session IDs are unchanged. Snapshot hashes differ in derived operational-summary strings such as elapsed wall time and stored session-record byte labels; I made no research-content edits.

### PDF artifacts

| Path | Bytes | SHA-256 |
|---|---:|---|
| messages/artifacts/maximum-regions-v2_d4b9ab0c_4c960d6626db46c69e263401c4b13696.pdf | 51,160 | 59a96a00ba5150bf573cb315b5fc7fbd5726f0983e1b32f122f37e24a224bc96 |
| messages/artifacts/nonconsecutive-subset-sums-v9_d4b9ab0c_5a86804e917e4c07b9ec92df2541bd5f.pdf | 87,213 | c46ebf018da19e70cc9734244edcdf383f95fb0696453e7249bbe0c57fa004e9 |
| messages/artifacts/xenopus-tail-regeneration-v9_d4b9ab0c_d62d7c7a45134b0085cadee89091fa54.pdf | 57,436 | 1ac8b23f59ef6233ce027e2eeb6e3580b36b88bedc57b4e2a69a67d9189faf54 |

TeX SHA-256 values:

- messages/artifacts/maximum-regions-v2_d4b9ab0c_4c960d6626db46c69e263401c4b13696.tex — 622cb8285ae3e211659265daa2d8a75a65602475276a684d5ed7a66c4c5c7e8a
- messages/artifacts/nonconsecutive-subset-sums-v9_d4b9ab0c_5a86804e917e4c07b9ec92df2541bd5f.tex — 2cd7d297bec455b4c8b42912919d3554966d52b5b7c7ed968df78a23a7537fa7
- messages/artifacts/xenopus-tail-regeneration-v9_d4b9ab0c_d62d7c7a45134b0085cadee89091fa54.tex — 09ee068a81910bfe44a1aba0aa0384483c907dc0258bebb323cf231ceb7a4da2

## Manuscript review

- **Maximum Regions:** The manuscript gives a coherent deductive argument: sign cells establish region convexity, an inserted line adds exactly m+1 regions, summation proves the universal bound, and the explicit family L_i: y=ix+i^2 attains the bound for every n. The prior assessment disagreement is now in a separate verification-status section, outside the proof. There are 9 claim definitions; all 8 referenced IDs resolve, with C9 unused. One construction equation is still incorrectly escaped in TeX: the source contains escaped dollar signs around x=-(i+k), plus a literal escaped qquad before y=-ik. Across the manuscript I counted 2 escaped dollar signs and one textbackslash escape. The validation warnings still note conflicting source-level assessments and that the AI-authored proof was not independently checked. No citations were generated; that is not a problem for this elementary self-contained proof.

- **Nonconsecutive Subset Sums:** The abstract and section structure distinguish the exact weighted recurrence and residue filter, finite value a_12=128, rejection of the short recurrence, and the unproved order-twelve candidate and density limit. The targeted set notation is correct in the TeX source: S subseteq \{1,...,n\}. However, other escaped-math errors remain: 24 escaped dollar signs, 37 textbackslash commands, and 8 textasciicircum commands. Examples include the six-state inclusion transition, counterexample arithmetic, and Gaussian-polynomial formula in the claim register; these are literal escaped text in TeX, not valid math. All 13 claim definitions are referenced and resolve. The substantive open proof obligations are specific: finish the all-index Gaussian identity under its stated convention; derive the phase-ordered three-step matrix identities and recurrence; justify the boundary and sufficient initial values; and bound the nontrivial root-of-unity contribution for the density limit. Reviewing omitted evidence is a coverage task, not itself a mathematical proof gap. The PDF coverage notice says 996 fields were omitted, while generation metadata says 1,027. Valid omega macros occur. No citations were generated.

- **Xenopus:** The abstract gives a clear, falsifiable conditional-coupling hypothesis and says no numerical association, predictive improvement, or independent biological confirmation is established. The statistical contrast is properly written as E[R | E=e, S=46] < E[R | E=e, S=40], with the variables defined in prose. There are no escaped dollar signs or literal TeX commands; the title avoids the prior dash-punctuation issue. The coverage paragraph and metadata agree on 1,863 omitted fields across 6 sources. All 9 claim definitions are referenced and resolve. The manuscript separates mathematical/mechanistic unknowns from pending study work such as prior-art review and verifying GEO samples, replicates, batches, and measurement linkage. A DOI occurs in prose but there are no structured citations or bibliography entries. It presents a hypothesis framework, not a completed analysis or executable intervention protocol.

- **Operation Narrow Passage — incomplete first attempt:** Directly copying the prior round's single-file project bundle failed to rebase its embedded research-session path. Paper 806af64aa9d14db7b5235b5cba88ccd7 records only 3 sources (project plus two strategies); export_project_view returned zero research sessions despite intended session 62290dab-19f0-4c6e-9785-7c8e02193a18. This one-shot generation took 829.1 seconds and one provider call, so it is not an apples-to-apples result and its PDF/TeX/text files are intentionally excluded from the inbound artifacts. In that incomplete manuscript the abstract and scenario analysis were coherent and conditional, and its open obligations were readable rather than raw schema/path keys, but the missing session prevents concluding that the round-8 abstract or provenance problems are fixed. It has 191 claim definitions, 70 uniquely referenced, many redundant entries, and a warning that source claim IDs C01–C09 were missing and links removed.

  I created a corrected isolated copy from the saved project using project_bundle.import_bundle; it exposed the expected session and 4 sources. At the human's direction, I did not rerun the paper. A replacement generation had already started just before that direction and was stopped during planning after 29 seconds; its checkpoint records one provider call attempted and no completed paper/PDF. That request may have consumed provider usage. Corrected-copy snapshot hash: 7ab8795d99dec6347036ae7669be5cac6687f6aafb5c0e6ad9760bf04db7399d. ONP quality and planning latency on the complete saved project remain unverified; the 829-second timing belongs only to the invalid session-omitting attempt. A complete-source run requires later explicit authorization.

The claim-reference audit counted “Claims discussed” and bracketed [C#] references against claim-status definitions. No dangling references were found in the three valid manuscripts. This does not remove the ONP warning that C01–C09 were missing from its source claims and their links were dropped.

All three valid paper records report pdf_available=true. The complete generated TeX for those three was reviewed. As clarified in the assignment, I did not spend time visually auditing PDF-to-TeX conversion. Citation counts were zero for all completed papers. No tests or CI were run.

## Outstanding work

1. Regenerate Operation Narrow Passage only after authorization, importing the saved project so its session is available. Do not reuse the incomplete paper or duplicate the interrupted attempt.
2. Fix remaining TeX escaping in Maximum Regions and Nonconsecutive; correct set braces alone do not address other literal TeX commands.
3. Reconcile the Nonconsecutive coverage count (996 in PDF, 1,027 in metadata).
4. Review ONP claim-link loss and its unused/redundant claim register on a complete-input run.
