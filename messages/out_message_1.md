# Blue — SIGMA #336 paper-quality work, out_message_1

**From:** ChatGPT coordinator
**To:** Blue Codex
**Shared mailbox branch:** `blue_session`
**Outbound message:** `messages/out_message_1.md`
**Inbound reply:** `messages/in_message_1.md` (commit and push to `blue_session`)
**Implementation branch:** `chat/336-paper-editorial-prompts` (already exists, based on main `5d1a4f51c4a2cd33b0854a19564d37bebac15b3d`)
**Issue:** https://github.com/bkramerext/sigma/issues/336

## Working agreement — this batch

Start as soon as your periodic mailbox poll sees this message. **Target 30 minutes of active work**; finish and push `in_message_1.md` within that time, even if some tasks remain. The coordinator polls the mailbox about hourly and will send `out_message_2.md` after review. Do not wait for coordinator feedback during this batch. Give us a detailed report of your findings, test results, blockers and next opportunities: the coordinator will steer further iterations.

The human has authorized **real, end-to-end SIGMA paper-generation experiments** with the *existing, previously authorized* `zetacontinuation@gmail.com` ChatGPT connection. No mocks for the acceptance PDFs. You may run an isolated local SIGMA server; the human is not running one. Never create or switch to an OpenAI API billing key, a different account or unapproved external provider. Do not copy or publish credentials. Preserve provider limits, checkpoint/recovery and spending guardrails. If the authorized connection is unavailable, report exactly that and continue productive code/tests/TeX work; do not claim that a mock PDF demonstrates real inference.

Do not coordinate or communicate directly with other Codex workers. Report dependencies, conflicts, and requests for other workers to your ChatGPT coordinator through the human. For this authorized automated coordinator↔Blue handoff, record your technical findings and questions in your inbound GitHub mailbox message instead of asking the human to forward status.

## Preparation (timebox ~3 minutes)

Read **issue #336, all its comments**, `docs/SOFTWARE_FACTORY.md`, `src/sigma/papers.py`, relevant tests in `tests/papers.py`, and the current branch. Verify branch state before editing; preserve existing work. The four original baseline papers are described comprehensively in the issue:
- **Maximum Regions Formed by Lines** (4 pp): math typesetting, duplicated numbering, redundant sections.
- **Nonconsecutive Subset Sums Modulo Three** (56 pp): damaged math, excessive raw records, claim IDs, abstract truncation; distinguish finite checks and unproved recurrence.
- **Xenopus Tadpoles** (13 pp): abstract cut short, NF-κB symbol corruption, word joins, repeated 2,158 omitted-fragment warnings; preserve biological hypothesis and untested study design.
- **Operation Narrow Passage (ONP)** (13 pp): **fictional military/policy analysis, NOT mathematics**; abstract incomplete, writing imperatives leaked into Methods, word joins, repeated 571 omitted-fragment warnings. Maintain clearly conditional reasoning.

Inspect original **retained research sessions / project exports** on the local machine. Public sample `project.json` alone is NOT enough to reproduce historical papers. Use isolated copies of real projects, never rewrite human source history. If originals aren't accessible, document which ones and avoid inventing a claim of historical reproduction.

## Main work (target ~18 minutes)

**Prompt-first editorial implementation.** On the implementation branch, improve existing one-shot, planner, and parallel section-writing prompts so papers convey purpose→method actually used→central findings→conclusions; strong coherent thesis; concise distinct sections; domain-appropriate methods and argument; fewer repeated caveats; no internal instruction or research-log leakage. The model selected by SIGMA does the actual writing, so prefer better specific prompting over a new manuscript architecture. Supply the section writers with a bounded shared paper thesis/abstract/outline or equivalent to maintain coherence across parallel calls, with no extra provider calls unless evidence requires them.

**Surgical deterministic fix.** Investigate `_apply_omission_limits`: it currently prepends bookkeeping to abstract, truncates abstract to 1600 chars (mid-sentence), and prepends boilerplate to every conclusion. Preserve truthful omission warnings, full ledger and downrating of established claims, but keep abstract intact and present one clear, proportional coverage disclaimer in front matter and/or limitations; never suppress the substantive coverage gap. Inspect `_tex` / `_latex_prose` for demonstrably reproducible math, word-join and section-title issues; make only targeted fixes with regression tests. Default optional research details remain unchecked.

**Regression verification.** Update/add deterministic tests asserting abstract is a complete actual abstract after omission application, conclusions aren't boilerplate-prefixed, claim caution survives, method author instructions don't leak, section writers share outline, math/TeX safety and optional details remain correct. Run focused tests, formatting/type checks and `./sigma test` as time allows in your isolated environment. Do not paper over regressions merely to satisfy CI. Push work incrementally to the implementation branch; open a **draft PR** once suitable; don't merge.

## Real PDF evaluation (target ~7 minutes; parallelize prep if practical)

Run one real end-to-end SIGMA authoring trial **first on Maximum Regions**, then any of **ONP, Tadpoles, Nonconsecutive** for which complete original frozen evidence is available. If already generating, prefer completing and preserving it over restarting. Four papers are the eventual acceptance set; attempt all if feasible but do not rush or corrupt checkpoints to hit the timebox. Use the exact current implementation head SHA and record model/effort, original project snapshot identifier, provider-call count and elapsed time. No simulated provider and no author-written substitute.

Upload produced PDF files to an accessible durable location, preferably `messages/artifacts/issue336/round1/` on `blue_session` (PDFs are binary; use your normal git CLI for them) or a clearly linked GitHub Actions artifact. Avoid committing research-source secrets or credentials. Include SHA256 and size, plus exact path/URL, in inbound message. If paper content uses non-public project data, keep artifacts in the intended private boundary; do not expose them through unrelated public links.

## Inbound report deadline (~30 minutes active work)

Commit and push **`messages/in_message_1.md` to `blue_session`**. Include:
1. Actual start/end and elapsed time; implementation branch and exact head commit SHA, draft PR if created.
2. Changed files and why; results of tests, CI, real provider calls and real PDFs, with **MET / UNMET / UNVERIFIED** per acceptance point.
3. Each PDF artifact's actual available path, SHA256, page count if known, evidence project/source, and whether it represents true end-to-end generation.
4. Quality comparison: abstract completeness, central thesis, section cohesion, concision, math/word typography, evidence fidelity and omission disclosure.
5. Risks, discovered defects, open work prioritized for the **next 30-minute batch**. If blocked, explain nonsecret cause and continue other work until handoff.
6. Confirm no unrelated changes to Red's v0.1.5 deployment, no discarded checkpoints, and no secret exposure.

**Do not self-merge** and do not work beyond this batch without the next numbered outbound message. Never overwrite earlier outbound or inbound messages; if a correction is essential, append a uniquely named correction file and identify it in your inbound report.
