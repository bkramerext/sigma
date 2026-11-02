# Golden 5 paper production: failures and handoff

Authoring source: merged PR #463, commit `a8a4891fb21352d8467594e976224426f80132ae`. All five canonical project and selected session identities were checked against `projects/complete/README.md`. Provider: connected ChatGPT plan, `gpt-6.1-sol`, high reasoning effort. Output hashes, source archive hashes, snapshot hashes, official writing guides, and cumulative call counts are in each paper's `metadata.json` or failed project's `generation_failure.json`.

## Final output

| Project | Result | Active generation time | Provider calls | Layout |
| --- | --- | ---: | ---: | --- |
| Agent Reliability v1 | TXT/TeX/PDF complete, 50 pages, 13,499 words | 878.64 s | 18 | `needs_review` |
| Sovereign AI Federation v2 | TXT/TeX/PDF complete after checkpoint recovery, 27 pages, 9,865 words | 1,061 s first attempt + 127 s failed continuation + 143.11 s successful continuation | 18 cumulative | `needs_review` |
| Xenopus Tadpoles v9 | TXT/TeX/PDF complete, 21 pages, 6,364 words | 512.24 s | 12 | `no_severe_box_warnings_reported` |
| Nonconsecutive Subset Sums Modulo 3 | No paper published | 249 s | 6 | n/a |
| Warp Drive Design | No paper published | 529 s | 8 | n/a |

The completed PDF/TeX pairs are also in top-level `papers/`, named with the `-golden5` suffix to preserve existing files. The text, full and compact generation metadata, and exact artifact hashes remain in this directory. The first three papers started at 2026-11-02 06:03:47 UTC; the final Sovereign recovery ended at about 06:42 UTC. Generation overlapped, so the per-paper times must not be summed as wall time.

## Failures encountered

1. The initial runner dispatched all five tasks together. SIGMA accepted three simultaneous generators and rejected the fourth and fifth with `Paper generation capacity is full; please try again shortly`. Those rejections made no provider calls. Math and Warp were subsequently dispatched when slots opened. The original batch result is preserved in `dispatch_run_summary.json`.
2. Sovereign's first generation failed in section 6/7: `Long-paper stage exceeded its streamed-response bound. No paper was saved.` The checkpoint preserved the evidence index, outline, and saved sections after 8 provider calls.
3. Math's first actual generation failed in section 1/5: `Provider returned malformed long-paper stage content. No paper was published.` Its checkpoint records 6 provider calls. There is no Math PDF or TeX.
4. Warp's first actual generation failed in section 3/7: `A table in A local stability gate for nonlinear scalar sources cites claims outside its section outline`. Its checkpoint records 8 provider calls. There is no Warp PDF or TeX.
5. Sovereign's first retry preflight reported `ChatGPT temporarily unavailable`; no paper-writing call was made. After the availability check expired, a checkpoint continuation resumed section 6/7 and failed with `A table in The comparison contract cites claims outside its section outline`. This added one provider call; no paper was saved in that continuation.
6. With the user's direction to log the table error and continue, Sovereign was resumed again from the same checkpoint using `include_diagrams=False`. Previously saved sections were reused; the remaining section calls were written without tables or diagrams. The paper completed. This recovery choice and its limitation are recorded in `sovereign-ai-federation-v2/recovery_note.md`.
7. TeX proofreading ran on all three complete papers. Agent: 10 chunks, fallback, 0 accepted corrections; Sovereign: 8 chunks, fallback, 0 accepted corrections; Xenopus: 6 chunks, fallback, 0 accepted corrections. Proposed changes that touched protected scientific or reference content were rejected. Agent and Sovereign retain layout warnings after the bounded three-pass PDF check; their PDFs require review. Xenopus has a sparse final verification page, though its automatic layout check reported no severe box warnings.
8. Before production, a local `./sigma test` run initially stopped at missing frontend `tsc`; `npm ci` restored the locked dependencies, and the full suite passed on the merged source tree. The PR #463 head CI was green; the merge-commit CI later failed with only a generic job-exit detail accessible. No tests were run after paper generation, per user direction.

The paper PDFs and TeX files are outputs of this iteration, not publication acceptance. The coordinator should review all three manuscripts and the two failed projects' preserved failure records before a further production attempt.
