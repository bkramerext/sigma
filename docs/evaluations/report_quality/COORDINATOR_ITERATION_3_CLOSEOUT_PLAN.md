# Iteration 3 coordinator implementation closeout and paper acceptance plan

**Scope:** Phase 1 only: write materially better scientific/technical papers from three immutable research snapshots. The separate Phase 2 research-agent improvement backlog is `PHASE2_RESEARCH_QUALITY_BACKLOG.md` and is **not authorized work in I3 or I4**. User explicitly directed that the academic-writing reference library gap be addressed in **iteration 4**, not while closing I3.

**Status at authoring:** Code and regression updates are committed to `report-quality-coordination` / PR #430, **but newly generated I3 papers have not yet been reviewed or accepted**. No claim of quality convergence or full CI green is made until the tests and artifacts are checked. A previous complete CI at SHA `6661f277` failed because (a) the fallback conclusion omitted a conflicting "no stable difference" result, and (b) Ruff formatting in the coordinator's edits. These issues were fixed in commits `c9ed846`, `fcfa0c0`, `79c7c75`; verify at later head rather than assuming success.

## Coordinator's actual implementation, all on I3

| Review item | Implementation | Required verification |
|---|---|---|
| Empty/generic abstract | Fallback filters operational fields and certain research-process scaffolding; no longer promotes "structured argument steps" into reported results | Deliberate planning failure with real Sovereignty snapshot; no generic findings or missing critical context |
| Compound incoherent claims | Individual complete source fields form atomic claims with exact refs, retain independent opposing claims; discarded operational evidence cannot create sections | Source-specific claim register and cited exact artifact, separate support vs contradiction |
| Weak conclusions | Provisional thesis, recorded main result, contrasting findings, negative evidence, limits, unresolved specific question and verification boundary | No claim-register dump; conclusion and abstract support same bounded answer; citation links valid |
| Project-question clipping | Fallback bounds at question/sentence or word boundary, avoiding clipped URLs | Deterministic long-question fixture with DOI/URL crossing prior cutoff |
| Research-quality academic structure | General publication contract and distinct CS/engineering/biology genre guidance; stronger section-purpose constraints | Whole-paper structure/argument test, no fabricated methods, measurements or animal research |
| Proofreading none accepted | Each proposed TeX patch evaluated independently against chunk and whole-paper semantic signatures; accept only safe mechanical corrections; unsafe changes remain rejected, zero-effect proposals not counted | Mixed-safe/unsafe correction fixture, three passes max and early convergence, result provenance, no repeated ambiguous calls |
| Research-details appendix leakage | Respect explicit `include_research_excerpts=false` independently of broad detail checkbox | TeX option matrix and no raw transcript/JSON appendix unless requested |
| TeX/PDF Unicode and URL issues | Greek math symbols including eta normalized; breakable URL markup in prose and validation notes | Real PDF visual inspection of previously broken Agent/Sovereignty/Xenopus pages; inspect overflows, missing glyphs, source citation fidelity |
| Three-paper generation capacity | Max three different projects concurrently under existing atomic admission lock and project exclusion; adapted tests | Three providers and compilers admitted, fourth rejected, concurrent research unaffected; no separate budget claims |
| Scientific tests | Correct Xenopus binary vs continuous identifiability witnesses; exact arithmetic both, preserve conditional +/-kcQ limits | Reader-facing proof and alternatives unaffected and not treated as animal observations |

## Frozen corpus (never edit or rerun research)

| Project | Frozen source SHA-256 | Baseline for I3 |
|---|---|---|
| AI Agent Reliability v1 | `080d3b70b67cfbe346acdb0f565d4a61c09ec4819229f2dd92dded43d9de40d9` | I2 manuscript, 8,849 words, 42 pages |
| Sovereign AI Federation v2 (AI Sovereignty) | `552f9458e600d3e7d0b3aa6c1dd105cc62dab4967db652123d2f134783b76f34` | I1 manuscript, 9,518 words, 42 pages |
| Xenopus Tadpoles v9 | `3236a8c66a96d713f28726271169e67c88c8a768f398ab3b9b504fee3cdcc74e` | I1/I2 strongest supported argument per item |

Same ChatGPT-plan, `gpt-6.1-sol`, high thinking, full paper options; separate exactly changed options (explicit excerpts off) from treatment comparison. Do not authorize metered provider calls, API-key fallbacks, or repeats of uncertain paid calls. Do not mistake 3-way throughput for content-quality gain.

## Blue execution and coordinator evaluation responsibilities

Blue should use the new head after green CI and **generate all three complete TXT/TeX/PDF manuscripts and metadata**, leveraging three simultaneous independent paper slots if allowed. It must attach generator SHA, frozen SHA, elapsed time, model/effort, provider calls, proofreading accepted/rejected patches, TeX compiler warnings, PDF page review, source-critical item table and before/after excerpts to `iteration_3/REPORT.md`. It must clearly report any provider/CI blocker instead of substituting drafts or assuming success. Blue owns safe provider execution, reproducible test harness, artifacts, and truthful `messages/message_in_3_completion.md`. Blue should not overwrite coordinator edits with stale local files.

Chat independently assesses the complete result against `COORDINATOR_I3_DEEP_REVIEW.md`, `COORDINATOR_CRITICAL_EVIDENCE_MANIFEST.md`, `COORDINATOR_GENRE_GATES_1.md`, `COORDINATOR_RUBRIC_V1.md`, and source SHA constraints. Reject projects that lose important math or scientific negative cases. I3 is **not** finished merely because a branch test succeeds; the complete reports must stand or the strongest earlier paper remains the baseline. No merge/deploy or next numbered iteration before review.

## Iteration 4 reserved work — expand academic-writing sources, not research

At I4, fill the reference-library gap: retrieve and read accessible, legally usable primary guidance plus strong exemplary published papers in CS systems/verification, systems architecture/policy, biological mechanistic hypotheses, methodology and scientific argument craft. Distill **specific transferable techniques** into source-cited editorial rules and adversarial examples. Distinguish read/full-text sources from abstracts or links only; never assert comprehensive coverage without verification. Extend the current ~seven institutional-source families toward the previously planned broader reference library. Use sources to improve paper *writing and evidentiary presentation from saved research*; do not gather new SIGMA research or run new investigators. Compare I4 papers against the **best** I1–I3 papers and keep iterations going until quality plateaus without critical regressions.

**No active hourly coordinator automation.** Timing and new handoffs require actual user/agent actions, not claimed background activity.
