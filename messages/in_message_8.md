# Round 8 results

Completed the four saved-project paper regenerations assigned in `out_message_8.md` using coordinator implementation branch `chat/336-paper-editorial-prompts` at available HEAD `332a51b692902531e9b2b36187f5c615892ca47b`. The assignment named a hash ending in `c`; that object was not present on the remote. I fetched and verified the available branch HEAD, whose final character is `b`, and used it for every run. No source code, saved source project, or existing paper artifact was modified. Each run used a fresh isolated bundle copy with the pre-existing `papers/` artifacts excluded.

All runs used ChatGPT mode through the authorized sponsor connection, model `gpt-6.1-sol`, high reasoning effort, with zero prior calls in each isolated copy. Snapshot hashes below identify the exact frozen generation inputs. Elapsed values are generation metadata seconds; the process wall time was within roughly two seconds of those values.

| Project | Saved project ID / source version | Snapshot SHA-256 | Paper ID | Elapsed / calls | Output |
|---|---|---|---|---:|---|
| Operation Narrow Passage v3 | `4060cb04-3ed7-4ae4-9f61-2c3691313759` | `aa0e96894c3b8af852fb248e1fb4a70cba59ae8b3542164144a0cf538d96a6e5` | `c7c43eb9c5c444738acfad15c5ab00f3` | 986 sec / 7 | PDF, TeX, text |
| Xenopus Tail Regeneration v9 | `01de54c9-9593-413a-9577-1a952d28da70` | `f271b8434c7a594c565a56b31bfa6996bb42286d942746a144b05fa4480d93d2` | `b6f4cddf6f9a43e4a3c8765b9ea010ba` | 215 sec / 5 | PDF, TeX, text |
| Maximum Regions by Lines v2 | `01af8ffa-60c3-4eea-bc15-36dca347ddfa` | `91bc37d6eb7c3f2f5b854c5c2c939c2ada0ee947901ac3f2a31b4e60753d96dc` | `68c23aea32ad438780bb8b19e06dba9c` | 132 sec / 1 | PDF, TeX, text |
| Nonconsecutive Subset Sums v9 | `57d67c57-15dc-433d-828a-7953f7986ff8` | `9a20c0ff7171238e2e110b72ead2e3831517b1e7731e14caeaf90e1fc26bd0bf` | `5ac114454ab94f6dba32b28e2bb0b80c` | 326 sec / 6 | PDF, TeX, text |

## Output review

- **Operation Narrow Passage:** The first-page PDF preview is legible, but the abstract substantially restates the fictional research question and exposes a weak saved-session summary (“The session ended before a complete research cycle was saved”). The planning call did not produce a usable outline; the implementation correctly continued using its conservative evidence-based fallback and completed all six sections. There is no mathematical notation or Greek text expected for this project. The generated paper has no citations. This run took much longer than the other three: the planning phase consumed about 900 seconds before fallback/section writing proceeded; it was slow, not stuck.
- **Xenopus:** The abstract presents the injury–epidermal coupling idea as a hypothesis, explicitly says the available evidence establishes no numerical association, predictive improvement, or independent biological confirmation, and names replication and sampling needs. The PDF includes an evidence-coverage limitation. It also reports 1,863 omitted saved research fragments over six sources, so the synthesis is explicitly provisional. The PDF preview's title appears to omit the en dash in “Injury–Epidermal.” TeX contains two escaped dollar signs and eight `\textbackslash{}` sequences; an illustrative expected-value expression is emitted as literal escaped TeX text, so that formula is not properly typeset. No Greek macros or citations were found.
- **Maximum Regions:** The PDF preview shows readable mathematical notation and a clear abstract stating the sharp bound `M(n) = 1 + n(n + 1)/2`, the incremental-region argument, and an attaining line family. This is a self-contained deductive result; no citations were generated. TeX had 136 math delimiters, zero escaped dollar signs, and no `\textbackslash{}` sequences. No Greek characters are expected.
- **Nonconsecutive Subset Sums:** The abstract is grammatical and substantive, separating exact identities and the finite value `a_12 = 128` from the unproved order-twelve recurrence and unproved density limit. The PDF explicitly warns that saved evidence was omitted. Its first-page preview shows a serious TeX escaping defect: notation such as the subset `S` is printed literally as `\{1,\ldots,n\}` instead of as a set, and later formulas contain escaped control sequences. Across the TeX source there are 22 escaped dollar signs and 47 `\textbackslash{}` sequences, though valid `\omega` appears for roots of unity. The PDF therefore compiles but some mathematical expressions are visibly corrupted. The generation record says 1,027 evidence fields were omitted; a coverage warning in the PDF says 996, while a separate warning reports 1,027. The discrepancy should be reconciled. No citations were generated.

The first page of each PDF was visually inspected through Quick Look previews; TeX and plain-text exports were also examined. All four records report `pdf_available: true`. Each paper's generated citation count is zero. Round 7 had 88 escaped dollars / 124 `\textbackslash{}` in Nonconsecutive; this round improves those counts to 22 / 47, but still produces visibly broken math. Xenopus also has a smaller instance of the same escaping defect. These remaining cases need implementation-level attention before the notation-rendering issue can be considered fixed.

No tests or CI were run, in accordance with the assignment. No source edits or new research sessions were made.

## Artifacts

Each stem below has `.pdf`, `.tex`, and `.txt` companions in `messages/artifacts/`.

| Stem | PDF bytes | PDF SHA-256 | TeX SHA-256 |
|---|---:|---|---|
| `operation-narrow-passage-v3_332a51b6_c7c43eb9c5c444738acfad15c5ab00f3` | 50,835 | `adc775abb37ddd9e53609a3230d16414962f9f274ecfe9134de0090bb0c4882f` | `f9edc403cb6b37e8aac47f4314e767afb8f6ac835111bcf81c948e6e025f8fee` |
| `xenopus-tail-regeneration-v9_332a51b6_b6f4cddf6f9a43e4a3c8765b9ea010ba` | 46,847 | `edfd56180a94fddad30dbbb6a34d4be192f46705835091612d4f00c75d69e337` | `755f9e86574cb0ac23a2f8698c8b4485f0f843b8451ef5b9bd05212579ffa248` |
| `maximum-regions-v2_332a51b6_68c23aea32ad438780bb8b19e06dba9c` | 41,083 | `adf5c4ce824c7b9a38fefeb9e97609cd464b5d5c7176c366d65cb02389ebe329` | `dcdd782f7ddb17ce795f875a048048cbc06101821fc1788072e6eee027463efd` |
| `nonconsecutive-subset-sums-v9_332a51b6_5ac114454ab94f6dba32b28e2bb0b80c` | 67,722 | `62e816f7103d576048916d1c593e9877e3e22d4a6ba60b392db2e93f49414e4b` | `7a7b27fdcc2a2f7ce043645c2713cc48dc585640e8bae19a168c838c2bd48815` |

## Remaining work / requests

1. Re-run the two affected projects after fixing escaped-math handling and verify the rendered PDFs, especially set-builder notation in Nonconsecutive and the statistical expression/title dash in Xenopus.
2. Review the Operation Narrow Passage abstract/fallback behavior against the incomplete saved-session status; the current output is cautious, but not a strong paper abstract.
3. Reconcile the Nonconsecutive omitted-evidence counts (996 in the coverage paragraph versus 1,027 in the generation record/another warning).
4. Resolve the one-character commit-hash discrepancy with the coordinator; artifacts here were generated from the available `...47b` HEAD.
