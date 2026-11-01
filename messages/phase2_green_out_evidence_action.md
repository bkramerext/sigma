# Green: Phase 2 research-quality addendum — evidence versus plausible reasoning

**Scope:** same cumulative Phase 2 [PR #433](https://github.com/bkramerext/sigma/pull/433). This adds a **scientific-content evaluation dimension**, not a new iteration, paid-run authorization, requirement to start Qubit #442 immediately, or any change to Investigator/Skeptic round order, scheduler, concurrency, UI or paper generation.

Read [the cross-disciplinary evidence-action audit](../docs/evaluations/research_quality/EVIDENCE_ACTION_CHAIN.md) and the latest [single-PR/best-available source handoff](phase2_green_out_2_consolidation.md). The new question is whether SIGMA **actually obtains and uses evidence to correct consequential claims**, rather than producing persuasive critical prose.

## Current implementation (coordinator-owned)

The coordinator added optional evidence-to-action guidance for **new** research sessions, with `research_method_version=phase2-i2-v3` pinned at session creation. Existing I2 sessions without a version retain `phase2-i2-v2` instructions on safe continuation; do not silently compare their prompted behavior as if both used v3. `src/sigma/research_sessions.py` and `tests/research_sessions.py` contain the version guard and regression. It encourages actual supported evidence, next-action follow-through and honest novelty uncertainty, but this is **not scientific proof or demonstrated improvement**. No live external-source retrieval tool was added.

## Immediate evaluation assignment (offline, no paid provider calls)

For **each of the five saved I2 subjects**, and comparison to its prior strongest available source when possible:

1. Identify one to three pivotal scientific claims, their actual supporting record, status and IDs (project/session/strategy/round/turn/artifact/execution/source).
2. Distinguish **actual executed computation** (code, parameters, observed output, execution status and limitations), mathematical deduction, inspected primary scientific source, real observational data, model assumptions, hypothetical experiment and raw LLM assertion. Never treat a planned test as an executed test, a document URL as read content, or model agreement as verification.
3. Find the strongest material Skeptic objections. Trace the actual `next_question`, obligations and following Investigator or peer actions. Did the next research step actually test, calculate, source-check or change its claim? If none exists because of failure, final-turn stopping or tool limitations, record the **unmet opportunity**, not imaginary follow-through.
4. Distinguish actual corrections/retractions and valid negative findings from mere rephrasing. Check important rival hypotheses or explain why available data do not identify a unique mechanism.
5. Check any novelty claim against genuinely inspected literature. Since the research agent currently has **no live literature-retrieval tool**, unsupported novelty is **NOT ASSESSED**, not novel. A coordinator may separately inspect primary sources and record exactly what was checked.
6. Produce the per-claim audit matrix and honest PASS/PARTIAL/FAIL/UNVERIFIED judgments in the new `docs/evaluations/research_quality/EVIDENCE_ACTION_CHAIN.md` format, with numerator/denominator summaries and 1–3 highest-impact weaknesses for direct coordinator review. Avoid an inflated single score and avoid counting extra words/calls as progress.

**Domain-specific checks:** quantum/other physics: definitions, physical validity, rival dynamical models, units, controlled numerical verification and relevant prior art; biology: paired unit, measurements and confounding; mathematics: full proof gaps and countermodels, no theorem from finite search; software systems: external-effect oracle/failure histories; engineering/economics: matched baselines, sensitivities and subgroup controls. These are *examples*, not mandated universal methods.

## When research is next run (separately authorized)

Green may continue safely recoverable existing I2 sessions under their **frozen v2 version**. For later fresh v3 runs (including Qubit #442 only when its own work-phase gate is satisfied), inspect the actual saved provider request versions and resulting traces, compare whether Skeptic objections cause **real action and calibrated revisions**. Provide a substantive failure reproduction and focused tests for each discovered defect before proposing further runtime/context changes. Preserve provider limits, prior artifacts, uncertain/failed dispatch and original hashes. Existing validated research must never be reset for prettier metrics.

**Acceptance:** actual traceable scientific improvement on unscripted sessions and/or a correctly preserved negative or unresolved result. Prompt content, green CI, stylistic fluency, formatted paper and synthetic compliance fixtures alone are not proof.

## Reporting

Commit the evidence-action scientific audit and concrete high-impact issues to **PR #433**; cite this message and the latest source/code SHA. Keep paper-authoring improvements on PR #430. The #434 archive was previously merged into #433's feature branch; do not reopen an independent snapshot PR. Do not claim current 40/60 partial I2 source or any new Qubit result is independently validated merely from this addendum.
