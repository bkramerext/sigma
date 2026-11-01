# Phase 2 → Phase 1: best-available research handoff

**Research and implementation home:** [PR #433](https://github.com/bkramerext/sigma/pull/433), branch `phase2/green-iteration-1`. **Paper-writing consumer:** [PR #430](https://github.com/bkramerext/sigma/pull/430). **Historical snapshot PR:** [#434](https://github.com/bkramerext/sigma/pull/434) was merged **into #433's feature branch**, not into `main`. Its exports and original manifest remain preserved below.

## Governing rule (owner decision, November 1, 2026)

**Provide paper writing with the strongest scientifically reviewed research available for each subject, not necessarily the newest or most complete scheduled investigation.** The two-strategy, three-round, 12-turn-per-project protocol remains the intended **research execution target**, not a gate that forces paper writing to wait for all five projects to reach 12/12.

Completion of protocol and suitability of research for writing are separate judgments:

- An unfinished or scientifically unresolved study can contain a valid conditional theorem, counterexample, limitation or negative finding. It can be selected as paper input **only after an explicit review** of the actual supporting record, assumptions, missing Skeptic work and conflicting evidence.
- The latest iteration is not automatically the best. Compare the latest against prior I1/I2, previous finished papers' underlying research, and any independently tested results. Select the strongest grounded record **per subject**. There is no five-project atomic replacement requirement.
- No unsupported result may be declared established because it appears in an unfinished session. Never promote an invalid provider response, a dispatch-unknown call or a missing review to an accepted Investigator/Skeptic turn.
- The paper coordinator independently assesses what source material is usable, retains explicit open obligations, and can defer one weak subject while proceeding with stronger subjects. Phase 1 still **does not rerun or modify** Investigator/Skeptic research.
- Green continues improving, completing and archiving research where safe; one project's stoppage does not block other projects or force restarts of nearly finished research.

## Preserved iteration-2 snapshot (historical, not automatically selected)

`releases/phase2-i2-v1/` contains five original complete **project bundle exports** from the partial I2 attempts, along with `MANIFEST.json`, `EXPORT_VALIDATION.md` and `provider-response-validation.json.gz`. The original archive and its `STAGING` status are **preserved as historical execution truth**, not rewritten to imply protocol completion.

At that archived checkpoint: **40/60 valid role turns**, none of five sessions at 12/12; 62 provider attempts, 44 provider-completed responses (four locally invalid), 16 confirmed plan-limit rejections, two dispatch-unknown Agent Skeptic attempts, and 13 required turns not dispatched. The records have exact project identities, request and artifact hashes, method-source selections, and a validation report. The four invalid provider responses remain invalid. Research claims have **not** yet received complete independent scientific acceptance in this snapshot.

**STAGING means incomplete research execution, not a permanent prohibition against using any of its sound findings.** Do not present `phase2-i2-v1` as one collectively READY/complete 60-turn release. A newly reviewed, per-project best-available selection can cite this version with explicit qualifications even if other subjects remain incomplete.

## Per-subject inventory and selection

| Subject | Original project ID | Archived I2 position | Scientific-selection requirement |
|---|---|---|---|
| AI Agent Reliability and Evaluation | `da4580f5-7620-49b0-882e-aee34fcdc05d` | 10/12 valid; final Skeptics dispatch-unknown, attempt ceiling exhausted | Compare conditional recovery argument to I1 and earlier source research; missing final Skeptics remain a substantive limitation |
| Sovereign AI Federation | `9175d73d-62aa-4523-a286-445f5390ae1d` | 6/12; local context-validation failures | Review reservation invariant, assumptions, fairness and charged-timeout objections versus I1 and original source |
| Xenopus Tadpoles | `01de54c9-9593-413a-9577-1a952d28da70` | 5/12; invalid response and provider failure | Compare identifiability and timing-mechanism arguments with prior 12-turn I1; distinguish model predictions from biological evidence |
| Nonconsecutive Subset Sums Modulo 3 | `7a8cbb3-da78-4249-8e9e-8f7c15b8ae7a` | 10/12; early productive stop | Verify recurrence, initial values and limiting ratio with an actual checked derivation; incomplete rounds alone are not proof of invalidity |
| Warp Drive Design / Physics | `e8211dc4-b70f-49d1-a514-671f44ed7e8c` | 9/12; one local invalid response | Check energy-geometry result under stated metric assumptions, prior art and the scope of causal-control claims |

These are **review priorities**, not scientific acceptance decisions.

## Publication and consumption in the single PR

1. **Green publishes on #433**, under versioned, immutable research paths. Each export includes the full original project bundle and genuine completed/failed/interrupted provider histories. Report raw and compressed SHA-256, project/session/strategy identities, research method sources, completed turns, outstanding obligations and provider-call uncertainty. Historical files remain untouched; subsequent outcomes receive new versioned paths.
2. **Phase 2 coordinator reviews per subject** and records a selection decision: chosen research bundle/path, Git commit SHA, raw/compressed hash, comparison candidates, strongest credible result, crucial counterevidence, missing verification, whether paper writing may use it, and why. Mark results `SELECTED_FOR_PAPER_INPUT`, `CONDITIONAL`, or `HOLD` with explanatory prose. These are authoring-source judgments, **not claims of full protocol completion or scientific proof**.
3. **Phase 1 consumes the best reviewed candidate for each subject** from a pinned commit and immutable SHA, maintaining provenance and research limitations in its paper. It may use different projects from different iterations, with each source version identified. It must not silently blend contradictory findings or use invalid provider outputs as evidence.
4. **Keep improving research.** A later, better finding supersedes the earlier selected source through a new review decision and pinned version, not in-place mutation. Phase 1 may refresh its next writing iteration when a clearly stronger candidate becomes available, without resetting already-running paper generation.

No separate PR is required for snapshot transport or for a collective READY marker. **#433 is the sole cumulative research workstream**; #430 remains the independent paper-writing workstream.

## Research execution remains rigorous and honest

The research protocol target is two selected strategies × three rounds × Investigator/Skeptic, 12 authentic completed turns per project. Count only validated persisted role outputs. A successful protocol may still yield a negative or scientifically unresolved result; a partial protocol can never be labeled 12/12.

Green should safely continue available projects in parallel using current scheduler/admission; preserve completed work and unknown-charge attempts. Do not replay an uncertain provider request, force a full restart near completion, fabricate a final Skeptic, increase budgets without authorization, or silently switch to metered API billing. Record local blockers and their effect on the *scientific* conclusion, not just the completion count. Provider `subscription_sharing_usage_limit_exceeded` remains a separate usage restriction with no established reset interval.

Methodological source material must be 2–3 readable, appropriately general/disciplinary/branch-specific guides selected before research, accurately preserved in both role contexts and disclosed in Outcome; it is **method guidance**, not empirical evidence.

## Stable identity and audit

Preserve both old and new scientific archives with honest source identity and frozen snapshots. The authorized Xenopus input differs from the historic Phase 1 hash; never imply they match. The stock Warp physics project is not demonstrated identical to historical Warp Drive Feasibility v2. The historical Math paper is not an Investigator source or answer key. Reviewers must verify the specific provenance before asserting comparisons.

The next-best-paper-input decision lives in a separate per-subject review document on **#433**, identifying the exact bundle and Git SHA. A green CI run or a full turn count does not independently validate scientific truth. Publication to `main` is a separate release/deployment decision; consolidation of #434 into #433 does not deploy anything.
