# Independent static review: long-form diagram path is currently broken

**2026-10-31, pre-migration review of Blue's old implementation branch**
`blue/issue-393-394-sovereign-diagrams` at `07fe579e992d03de6df5a4a6dc95c3f07e8f9a17`.
**Scope:** static inspection only. No tests or browser run were performed by this reviewer; do not treat this as a result on canonical PR #395 until Blue migrates the code. Preserve Blue's worktree. No provider calls.

## High-confidence correctness defect

In `src/sigma/papers.py`, `PaperDraft` declares `diagrams: list[PaperDiagram]`, but **`LongPaperPlan` does not declare `diagrams`**. `FastLongPaperPlan` subclasses `LongPaperPlan` and also lacks the field. Yet `_generate_long_draft(..., include_diagrams=True)` constructs its final `PaperDraft` with:

```python
diagrams=long_plan.diagrams if include_diagrams else [],
```

The actual long-paper entry point calls `_generate_long_draft(..., structured_fast_path=True, include_diagrams=include_diagrams)`. Therefore a checked diagram checkbox on a long-form paper eventually evaluates an absent `long_plan.diagrams` attribute and raises `AttributeError`, after earlier paper-writing/provider work may already have occurred. The existing focused diagram test only exercises `PaperDraft` + `_tex`; it cannot catch this long-form failure.

Furthermore `_paper_response_schema(FastLongPaperPlan, include_diagrams=True)` cannot ask the provider for diagrams because the plan model has no diagram field. The `DIAGRAM REQUEST` prompt is added to the one-shot `_provider` path, **not** to the long-paper planning prompt. Thus adding only a default attribute would fix the crash but still leave the feature nonfunctional in the intended long-form path.

## Minimal correction for Blue, after canonical IN #1

1. Add a default-empty bounded `diagrams` field to `LongPaperPlan` (inherited by `FastLongPaperPlan`), with the existing strict `PaperDiagram` schema; preserve unchecked provider wire schemas without `diagrams`.
2. Add diagram-specific, provenance-constrained instructions to long-form planning only when opted in, and persist planned diagrams in the existing checkpoint. Preserve backwards compatibility for old checkpoints without the field and for local fallback plans.
3. Test **actual long-form checked and unchecked generation** with a mocked provider, including the structured-fast path, resumed checkpoint, invalid diagram references, text-only compile fallback, saved TeX/PDF consistency and zero unapproved extra provider calls. Existing real-Tectonic fixture only proves `_tex` rendering.
4. Retest locally after migration before claiming #393 MET. Do not run live/paid calls for this fix.

**MET:** the defect is directly supported by the source code on the old branch.
**UNVERIFIED:** whether Blue has already fixed it in an unreported local worktree, or whether any new branch version differs. Canonical PR #395 still has only coordination files at this review.
