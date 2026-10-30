# Round 10 — final controlled paper-quality acceptance (issue #336)

Blue: This is the **final planned independent paper-quality evaluation round** on the four saved projects. It follows your detailed `messages/in_message_9.md` report and is separate from the new optional iterative-review enhancement, issue #347. Do **not** implement or enable #347 in this round.

## Candidate and preflight

- Coordinator implementation branch: `chat/336-paper-editorial-prompts`.
- Exact current candidate SHA: `5066703702c9777f1fe7ee4b8125e43060445e3c`. Verify the commit object and exact checked-out SHA before proceeding; report a changed/missing ref instead of silently substituting another commit.
- Since round 9 (`d4b9ab0ce55a7f05e053b43f96704528a676248c`), the candidate has expanded the safe-math command set and stopped indiscriminately downgrading independently supported claims merely because unrelated evidence fields were omitted. **Neither fix is presumed validated.**
- First perform a cheap, isolated **no-provider** check of the previously broken TeX/math cases using existing manuscript examples: Maximum Regions' escaped `$x=-(i+k),\\qquad y=-ik$`; and Nonconsecutive's residue-state inclusion transition, `\\#\\{...\\}`, Gaussian/binomial formula, powers, comparison signs, braces and escaped math delimiters. Confirm they survive the current `_latex_prose`/`_safe_math` path as valid math rather than `\\$`, `\\textbackslash{}` or `\\textasciicircum{}` text.
- If any core math case is still broken, **do not spend sponsored provider calls on a known-bad candidate**. Send a concise blocker in `messages/in_message_10.md` with exact failing input, output and code SHA, and request a corrected SHA through the human/coordinator. After a corrected SHA is explicitly provided, continue the same round, not an untracked round 11. Do not patch application source yourself.

## Primary generation matrix (after preflight passes)

Regenerate isolated copies of these exact **saved** projects, preserving research content and all existing artifacts:

1. Maximum Regions by Lines v2 — source project `01af8ffa-60c3-4eea-bc15-36dca347ddfa`.
2. Nonconsecutive Subset Sums v9 — `57d67c57-15dc-433d-828a-7953f7986ff8`.
3. Xenopus Tail Regeneration v9 — `01de54c9-9593-413a-9577-1a952d28da70`.
4. Operation Narrow Passage v3 — `4060cb04-3ed7-4ae4-9f61-2c3691313759`.

For each primary generation explicitly submit:
- Include claim details: **ON**
- Include validation notes: **OFF**
- Include research excerpts: **OFF**
- Legacy include research details: **OFF**

Use the same authorized sponsor/provider model and high reasoning effort as round 9, subject to current explicit account authorization. Do not silently switch provider/model or rely on dialog defaults. Record actual settings from the call and metadata.

**ONP is critical:** Import the saved bundle via `project_bundle.import_bundle` rather than copying its JSON/project file directly. Before making any provider call, verify that `export_project_view` exposes the saved research session `62290dab-19f0-4c6e-9785-7c8e02193a18` and the expected **4 evidence sources** (project, two strategies, one session). If absent, stop ONP and report a source-integrity blocker. Do not reuse round 9's invalid 3-source / 829-second paper, interrupted checkpoint, or its output as valid test evidence. A fresh isolated project copy is required.

## Two independent detail-option probes

On **Maximum Regions only**, using fresh isolated copies with otherwise identical source input/model/effort and an exact reported SHA, additionally generate:

A. **Claim details ON / Validation notes ON / Research excerpts OFF**.
B. **Claim details ON / Validation notes OFF / Research excerpts ON**.

Keep legacy include research details **OFF** for both. Evaluate whether each switch changes only the intended publication material, whether claims still resolve, and whether optional content remains coherent, nonduplicative and bounded. Do not mistake the option-comparison probes for separate source research sessions.

## Evaluation: manuscript quality first

Read the **complete generated .tex** manuscripts (and .txt companions as useful) for substantive evaluation; this is not primarily a PDF conversion/layout test. Nonetheless verify that every completed run produces normal PDF/TeX/TXT artifacts and that visible high-value notation can actually compile/display. Evaluate each as a prospective **discipline-appropriate paper**:

- Substantive thesis, clear abstract and conclusion, continuous argument, publication-appropriate section structure, useful detail without repetitive throat-clearing or internal pipeline chatter.
- Fidelity to recorded evidence, inclusion of salient contradictory/negative findings, accurate claims, meaningful limitations and genuine open research/proof obligations (not raw JSON schema/path keys or administrative to-dos).
- Mathematical proof completeness vs. conjectures and finite computations; correct formulas throughout, especially Nonconsecutive, and no literal escaped dollar signs, `\\textbackslash{}`, `\\textasciicircum{}` or malformed set notation.
- Xenopus: consistent statistical expression, study-design cautions, developmental-stage distinctions, scientific terminology and punctuation; no fabricated numerical result or validation.
- ONP: conditional operational/planning reasoning rather than generic scenario paraphrase, no internal session-status string presented as a finding, no invented recommendations; assess planning latency separately from end-to-end generation.
- Claim register and references: every referenced `[C#]` / 'Claims discussed' ID should resolve; flag unused/redundant claims, especially ONP. Verify independently supported established findings remain established despite unrelated evidence-index omissions; report unsupported established claims, if any.
- Evidence indexing: compare **exact** material omission counts and affected-source counts across PDF/TeX disclosure, metadata and the persisted omission ledger. Round 9's Nonconsecutive **996 vs. 1,027** inconsistency must be checked. Disclose limitations in a way that does not overpower the scientific argument.
- Do not require external citations for a self-contained elementary proof, but note any unsupported bibliographic or DOI assertions and any missing bibliographies where they actually matter.

Compare with valid round-9 artifacts and identify **improved / unchanged / regressed** outcomes with concrete quotations or exact TeX fragments. Do not claim success from PDF compilation alone, nor score the ONP round-9 incomplete paper as a comparison.

## Report and boundaries

Publish `messages/in_message_10.md` with: exact implementation SHA, source/session validation, actual submitted settings, each paper ID, duration and provider calls, evidence source/omission counts, snapshot hash, PDF/TeX/TXT paths and relevant artifact checksums, plus a concise per-paper **pass / defect / blocker** assessment. Preserve all artifacts in `messages/artifacts/` with unique round-10 stems. If stopped by preflight, report the blocker and spend **zero** provider calls.

This is **execution/evaluation only**. No source edits, product changes, GitHub merges, deployments, unrelated tests/CI, server-disruptive suites, new research sessions, or direct cross-worker coordination. Preserve the original projects, paper archives and source bundles. Report dependencies and next actions through the human/coordinator. Do not begin an unsolicited round 11. Round 10's remaining defects are for the coordinator to disposition before final acceptance.

**Issue #347 (self-adversarial .txt review, 0–3 passes) is deferred and outside this matrix.** It must not add iterations, change default behavior or increase the above provider-call budget.
