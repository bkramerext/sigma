# Phase 1 PR #430: pre-CI adversarial integration review

**Date:** 2026-11-01. **Review object:** consolidated rebased candidate `dfc3f5b82b06623078695b4af531cc7e104fbc2d`, parent **main** `37502ecff11a01a4de56a68c309a709bdefa866b`. The candidate was built but not pushed when this review began; no CI on the candidate was used to form these findings. **Merge acceptance remains contingent on required CI passing after this review, and on final merge-base checks.**

## Preservation and merge-conflict audit

- Compared merge-base `92bc34ed` to both branch and main; 110 Phase 1 changed blobs rebased as a consolidated commit. Four overlapping files required explicit three-way integration: `src/sigma/papers.py`, `tests/papers.py`, `tests/cloud_research_api.py`, `frontend/src/main.tsx`.
- The three semantic overlaps in `papers.py` combine **main** publication reference URL safety hints and source metadata with **Phase 1** subject guidance and selected writing excerpts. The frontend overlap keeps main's **paper_version/download_basename** plus Phase 1's **writing_sources/writing_source_selection** and `source_material` stage. No main paper-version logic or newly merged Phase 2 research was overwritten.
- The integration reconciler reconstructed each side exactly before merging; merged text lengths were checked for inexplicable duplication: `papers.py` 7,574 lines, `tests/papers.py` 7,023, `cloud_research_api.py` 1,384, `frontend/src/main.tsx` 5,941. The first failed reconciling approach was rejected **without moving PR refs**; only the validated diff reconstruction was used.
- Strong guards retained: stable saved-paper version sequences/filenames and server-client agreement, bounded research/paper contexts, frozen source hashes, 3 concurrent paper generators and 4th admission rejection, interrupted-call accounting, proofreader semantic-preservation, source-specific claim linking, failed final Skeptic research limitations, and new paper-writing source display in Outcome/TXT/TeX.
- Existing tests from both lines remain present and each has one definition and one scripted runner: stable paper version/downloads, 3-slot concurrency, math/physics genre routing, reference reuse/failure handling, exact duplicate claim aliasing and incomplete final review disclosure. **This is source inspection, not yet proof that tests pass.**

## Adversarial findings and dispositions

| Severity | Finding | Disposition |
|---|---|---|
| **High for next paper iteration (not a regression introduced by merge)** | Source selection still runs `paper_writing_sources.CATALOG` based on category/keyword branch, while main's new `project_types.get_type()` correctly resolves common + recursive inherited `publication_standards_references`. The authoring snapshot contains the configured references, but the selector does **not** prioritize or fetch that configuration. Reuse can persist a prior 2–3-source set after publication references change. | **Must fix before the Golden 5 generation**, independently of this rebase. Do not claim configured publication references are already actively applied; use a bounded, SSRF-safe retrieval policy for user-defined URLs or skip those and report missing material. Reject unreadable links. No paid paper calls until addressed. |
| **Medium, fixed in this pre-CI review** | `messages/EXPERIMENT_COORDINATION.md` described an active hourly automation cancelled by the human. | Mark historical protocol archived, avoid spurious wake/polling claims. |
| **Medium, fixed in this pre-CI review** | Golden-5 draft falsely said `resolve_type_metadata()` picked only nearest ancestor. Main now unions parent references and common references. | Correct factual implementation note; remaining gap is in writing-source selection, not type inheritance. |
| **Medium, needs validation by CI** | Both large Python and frontend changes rely on Pydantic/TypeScript signatures and existing main API paper version fields after squash rebase. | Run Ruff, Pyright, `./sigma test`, frontend TS build, paper & cloud API tests after this review, then inspect actual errors; no preemptive success claim. |
| **Medium, next paper-run risk** | Live source selection has three-second source timeouts, a curated allowlist and a process-level negative cache. Failures are nonblocking, but negative caching and stale type-agnostic reuse may ignore a newly repaired reference. | Improve caching/invalidation before Golden 5; distinguish a source with readable, actually fetched content from a URL-only pointer. |
| **Low, intentional** | All historical I1–I3 PDF/TeX/provenance and handoff docs remain on the PR, increasing repository size. | Preserve as audit baselines for source fidelity and comparative paper quality; future Golden 5 READMEs should link new outputs without claiming old papers were regenerated. |
| **Low, historical** | Original PR description still refers to hourly I1/doc-only scope and never requested merge. | Update PR summary before merging to accurately describe cumulative reviewed implementation. |

## Merge gate

1. Only after this review is durably committed, move PR #430 to rebased commit; preserve the old branch SHA in this report for audit.
2. Observe actual CI results at the exact rebased SHA. Correct Ruff/Pyright/test/UI errors on branch, rerun CI until green.
3. Independently check PR mergeability, no new main changes, no unintended source deletion or Golden project replacement; then merge.
4. The **next paper-generation iteration is separate**: it is one Golden 5 run using the current pinned research in main, verified publication references from type inheritance, PDF/TeX artifacts and README links. No paid run or automatic Blue handoff is part of this merge.

**Conclusion:** Conditional engineering recommendation to proceed to CI on the rebased branch. The project-type/reference-use gap is a **known prerequisite for Golden 5 paper production**, not evidence that scientific-paper quality has been fully validated by this code merge.
