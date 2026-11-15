# Coordinator code audit 3 — disabled excerpts rendered, operational JSON leaked, and three distinct overflow triggers

**Prepared:** 2026-11-01, independent inspection of all three iteration-1 TeX manuscripts, compact metadata, and `src/sigma/papers.py` at PR #430. **No runtime changes made.** This is a *new finding after* the iteration-2 handoff; do not silently add it to Blue's controlled H2-A treatment. Address in a later isolated fix.

## Confirmed option mismatch

All three compact metadata files report `generation.include_research_excerpts=false`. All three TeX files nevertheless contain a `\section{Selected source-linked research excerpts}` appendix:

| Paper | TeX appendix start | Number of `\subsection{Research excerpt N}` | Metadata flag |
|---|---:|---:|---|
| AI Agent v1 | line 330 | **16** | false |
| Sovereignty v2 | line 577 | **13** | false |
| Xenopus v9 | line 287 | **9** | false |

**Manuscript-space impact (exact TeX slice from the excerpt heading to the next validation section):** Agent **26,377 characters / 32.1%** of the entire TeX file, Sovereignty **19,876 / 15.4%**, Xenopus **14,985 / 19.3%**. These percentages measure TeX source characters, **not PDF pages or scholarly word counts**; they demonstrate substantial unnecessary appendix weight even with the excerpt option explicitly false.

**Root cause confirmed in source:** `src/sigma/papers.py::_tex`, around line **3041**, unconditionally applies
`include_research_excerpts = include_research_excerpts or include_research_details`.
The actual generation set `include_research_details=true`, so the explicit `include_research_excerpts=false` is overridden. Around line **3430**, `_tex` renders the appendix whenever the resulting flag is true and integrity records exist. The persisted metadata at line ~5862 retains the original false value, and the call around ~5935 passes it unchanged. Thus the **saved option disagrees with the generated TeX**. This is deterministic and directly reproduced by the three manuscripts, not an inference about model behavior.

It is possible the UI intended `include_research_details` to imply excerpts, but then a separate disabled excerpts flag is misleading. Clarify the product contract, make rendering honor the explicit setting, and test combinations (details true/false × excerpts true/false). The setting must not silently mean something different in the report from the metadata.

## More severe: provider request-schema material is printed as a research excerpt

In **Xenopus TeX lines 339–341**, `Research excerpt 7` is sourced from:
`steps/0/provider_input_audit/request_body/text/format/schema/properties/reasoning_steps`.

The printed excerpt is a JSON Schema fragment containing `items`, `$ref`, `maxItems`, `title`, and `type`, not biological evidence or a research conclusion. Its appearance under “source-linked research excerpts” can falsely signal evidentiary importance and bloats the manuscript with provider plumbing. The current `_structured_evidence_index` recursively visits research-labeled parents; nested audit/schema fields can pass through as candidate notes or integrity excerpts. The exact route to this appendix entry requires further source tracing, but **its inclusion is directly observed**.

**Acceptance requirement for later isolated experiment:** provider request/response envelopes, JSON Schema, prompt contracts, tool invocation configuration, UI metadata and progress events should remain archived for provenance but **must not appear as research findings or selected excerpts** unless the paper's research question is itself about that infrastructure. Use a structured provenance/evidence distinction, not a broad “delete JSON” heuristic that would suppress legitimate software-engineering research artifacts. Provide a fixture with meaningful algorithmic JSON as a positive control.

## Distinct overfull-line causes in the same baseline

- **Sovereignty:** TeX line **526** includes a long raw escaped MindRouter PEARC PDF URL; metadata reports `Overfull \hbox` ~100 pt at line 526 and page 31 extends horizontally. Breakable URL rendering is a plausible targeted remedy.
- **Xenopus:** TeX line **340** contains the provider JSON Schema fragment above; metadata reports `Overfull \hbox` ~167 pt at line 340 and page 22 extends horizontally. Removing irrelevant excerpts when explicitly disabled would remove this trigger; do not conflate that with general TeX line breaking.
- **AI Agent:** metadata reports an overfull box near TeX line **298** (~115 pt, PDF page 16). The nearby open-obligation items at lines **295–300** include long unbreakable hex ledger IDs (line 300 has two) and dense raw field paths; the exact offending token at the line-298 paragraph boundary is **not independently localized**. Robust formatting may be required even after excerpt filtering.

These are **observed correlations between exact TeX lines and compiler warnings**, not yet independently confirmed via matched TeX recompilation. The causes differ, so a single blanket layout patch should not be assumed to fix all three. Tests should retain the exact text, avoid unsafe TeX injection, preserve source IDs and report warning counts separately.

## Controlled follow-up plan

1. **H2-A** (already assigned): fix semantic fallback claim selection, preserve the frozen source/index/options and generate all three full papers. Record the excerpt flag mismatch as a *baseline defect* but do not mix the option fix into this treatment.
2. **H2-C** (future): honor explicit excerpts setting; filter provider plumbing from scientific excerpts without losing legitimate technical data; compare TeX/PDF page count and source-linked evidence retention across all three. Validate all four option combinations and metadata fidelity.
3. **Layout follow-up:** after H2-C, retest the three specific overflows; apply narrowly scoped safe URL and long-identifier line-breaking fixes only for remaining cases. Keep proofreader fallback as a separate reliability problem.

**Why this matters academically:** the source archive should be exhaustive, but a publication's selected evidence must be relevant, interpretable and traceable. The inclusion of schema plumbing as biology evidence is not a cosmetic layout problem; it is a failure to distinguish research content from operational provenance. A cleaner PDF is not sufficient if it hides the misclassification instead of correcting it.
