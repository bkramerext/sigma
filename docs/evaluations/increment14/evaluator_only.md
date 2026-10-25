# Increment 14 independent evaluator packet

**Evaluation-side only; never include in an agent prompt.** The agent runner receives only the selected `instruction`, `question`, and `evidence`. No filesystem, repository, web search, answer key, rubric, or other arm output is available. Repository storage alone is not an access-control boundary.

## Scorer input and dimensions

Scorers receive the common normalized six-field submission, a randomized anonymous ID, and the matching task/evidence packet. They never receive arm labels, role logs, raw schemas, call counts, paired counterpart, costs or execution order. The key custodian holds the arm map separately. Do not award points for the presence of a named critic or for a particular structure beyond compliance with the shared output contract.

Score 0–4 (0 wrong/absent or actively misleading; 1 major errors; 2 partially correct with material gaps; 3 correct with minor omissions; 4 fully correct and supported for packet scope):

| Dimension | Weight |
|---|---:|
| Task outcome | 35% |
| Reasoning validity | 30% |
| Calibration | 15% |
| Evidence quality | 10% |
| Useful next test | 10% |

Also record a task-key binary pass/fail endpoint and critical integrity failures separately. Preserve both graders' scores. Disagreements greater than one point on a dimension receive blinded adjudication; retain original scores. After scoring, graders guess the arm and confidence. Guesses are a diagnostic, never an exclusion rule.

## Frozen task-specific reference checks

- **E1 present:** A/B readings overlap after accounting for temperature/room, with one observation per cell and no variance estimate; firmware-only effect is not identified. A crossed randomized repeated firmware × temperature × room test with calibration controls is discriminating. **Withheld:** no causal estimate.
- **S1 present:** signed April 12 primary notice supports July 1; conflicting internal summary says May 1. Assess authority, applicability and revision history. **Withheld:** May 1 is secondary assertion, not established mandatory date.
- **C1 present:** an external charge succeeds before acknowledgement is lost and repeats. A DB marker alone cannot guarantee once-only external effect without external idempotency or reconciliation/compensation. **Withheld:** do not invent endpoint semantics or timeline.
- **P1 present:** a vehicle can make multiple stops; V1 delivers 60 to A, V2 can deliver 10 to A then 40 to B if route and handling times meet deadlines. Unknown A-to-B time prevents unconditional feasibility. **Withheld:** capacity/routes unknown; avoid unsupported feasibility.
- **M1 present:** the 10-vertex graph is the Petersen graph, degree three and girth five. A valid refutation verifies no 3/4-cycle by argument or complete adjacency check; naming alone is insufficient. **Withheld:** require a valid derivation, not unrecorded computation.
- **M2 present:** T1/T2/T3 have only A/B, so no injective assignment exists; Hall's condition characterizes complete matching. **Withheld:** a valid counterexample refutes the universal claim; unstated instance matching is unknown.

Domain anchors: experimental design rewards identification, replication and falsification; source criticism rewards primary authority and uncertainty; engineering rewards failure-mode completeness; scenario work checks numerical feasibility and constraints; formal work requires a valid proof/counterexample distinguished from finite computation.

## Independence, custody and provenance

An external human curator who did not author the tasks, implement/run the experiment, or score it must review packet/key provenance (including whether a model and which family/version helped author them), recognizability and likely training contamination, ambiguity, alternate valid answers, evidence-variant validity and ceiling effects. Unknown provenance is documented as unknown/high risk. The curator signs task/key hashes before any model output and does not see outcomes.

Two independent graders must be separate from task authorship, curation, implementation and provider execution. After submissions are frozen, they receive the key material needed to grade but remain blind to arm identity and paired counterparts. A separate key custodian controls unsealing and records access. If these independent humans or the access boundary are unavailable, protocol stays unfrozen.

## Failures and interpretation

Record all failures, abstentions, clipping, native schema truncation, guessed identities, interruptions, invalidation, leaked keys, missing provenance/cost, cap breaches, tool asymmetry and prompt changes. Keep ordinary failures and clipped submissions in the analysis; they are not grounds for post-hoc deletion or replacement. A protocol violation blocks a superiority conclusion and remains visible.

The six synthetic tasks are short, partly recognizable, and may have ceiling effects. The experiment only tests within-session adversarial review against single-role self-review. Persistent cross-session value is a separate question in issue #119.
