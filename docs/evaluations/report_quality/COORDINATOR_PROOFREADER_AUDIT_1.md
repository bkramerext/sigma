# Coordinator proofreader reliability audit — why three fallbacks need separate diagnosis

**Prepared:** 2026-11-01 after iteration-1 completion, code inspection only. **Not a confirmed root cause of the three actual fallbacks.** Full gzip metadata contains per-chunk diagnostics and fallback reasons; the compact metadata alone does not identify which exception path occurred. Do not infer that all provider calls failed or that all proposed corrections were unsafe.

## Observed baseline

| Project | Proofreading provider calls | Accepted corrections | Unresolved diagnostics | Final status |
|---|---:|---:|---:|---|
| AI Agent v1 | 1 | 0 | 34 | fallback/incomplete |
| Sovereignty v2 | 9 | 0 | 59 | fallback/incomplete |
| Xenopus v9 | 3 | 0 | 21 | fallback/incomplete |

All three had valid compiled PDFs but also final layout warnings. The generated manuscripts are **not** proofread-clean.

## Code path and failure classes

`src/sigma/papers.py::_proofread_tex` around lines 5134–5240 performs up to `MAX_PROOFREADER_PASSES=3` and stops on incomplete status or convergence. `_proofread_tex_single_pass` around lines 5240–5525 checkpoints every chunk, sends an exact-TeX patch request, and applies only changes that satisfy all guards.

Potentially distinct outcomes:

1. **Known pre-delivery connection failure:** bounded safe retry; no inferred paid completion.
2. **Malformed/failed/ambiguous provider response:** status fallback; remaining chunks skipped, no unsafe replay.
3. **Returned patch with nonunique `find` string:** patch rejected; other chunks may still be attempted.
4. **Returned patch changing `_tex_semantic_signature`:** rejected to preserve scientific meaning and references. This is a valuable safety gate, not automatically a bug.
5. **No changes proposed:** a valid complete pass with zero corrections is possible. Zero corrections alone does not imply failure.
6. **One rejected chunk after a returned response:** `fallback_reason` is set, which can cause the **entire** pass to end with fallback even if some other chunks were checked or corrected.

The code's `fallback` status therefore conflates several operational situations; full metadata is necessary to classify them. The compact report's `ai_performed=false` across all three suggests no successful complete accepted pass, but is not enough to distinguish provider failure from unsafe-patch rejection.

## Reproducible diagnostic plan (later isolated experiment)

For each paper, extract from `*.metadata.full.json.gz` the **exact saved** `proofreading.fallback_reason`, per-chunk `attempts`, provider-call count, safe retries, diagnostic strings, `initial_sha256`, `final_sha256`, pass history and accepted corrections. Group by failure class; redact any secrets or unnecessary provider payloads. Do **not** rerun paid requests to discover what already exists in the checkpoint.

Create deterministic tests for:
- valid empty correction list → complete/converged without false fallback;
- nonunique `find` → rejected only for affected chunk, with accurate status;
- semantics-changing patch → safely rejected, original TeX retained;
- one rejected chunk among many → clear partial status and precise diagnostics;
- failed connection known pre-delivery → bounded safe retry;
- ambiguous dispatched response → no automatic replay;
- resumed checkpoint → no duplicate charges, preserved accepted chunks;
- three-pass early convergence and cumulative call accounting.

**Quality goal:** a paper with no needed mechanical edits should not be labeled proofread-incomplete; a paper with a genuinely unsafe patch should preserve original text and clearly identify the affected chunk and reason. Do not weaken the semantic signature or permit silent content changes merely to make the status green.

## Sequencing

Keep this separate from Blue's H2-A semantic fallback experiment and from the excerpt-option mismatch, URL line breaking and evidence-critical recall work. Once the exact three fallback reasons are extracted, prioritize the smallest shared root cause, not a speculative broad rewrite.
