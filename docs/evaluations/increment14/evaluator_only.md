# Increment 14 independent evaluator packet

**Not an agent prompt.** This document is evaluation-side only. During a pilot, the agent runner must receive the selected task question/evidence packet and global instruction, with no filesystem, repository, web search or tool access that can reveal this packet. If that isolation cannot be demonstrated, the run is contaminated and invalid. Repository storage alone is *not* an access-control boundary.

## Fixed scoring and adjudication

Each scorer reads an anonymized final answer and available audited tool/source records, not orchestration trace identifying the arm. For each dimension, 0=absent or contradicting evidence, 1=weak and important error, 2=partial with substantive limitations, 3=correct with minor omissions, 4=rigorous and well supported.

Weights: correctness .30, objection uptake .20, evidence integrity .20, calibration .15, useful next experiment .15. Weighted score range 0–4. Two independent graders; retain both original scores; disagreement >1 point on any dimension requires blinded adjudication, retaining all originals. Record critical integrity failures independently; never average them away. Graders must be blinded to SIGMA vs baseline until scoring is final.

## Curated reference checks (synthetic inputs)

- **E1 present:** A vs B readings overlap after accounting for temperature/room; there is one observation per cell, no variance estimate. Firmware-only effect cannot be identified. Demand crossed randomized repeated firmware × temperature × room test with calibration controls. **Withheld:** No causal inference or numeric drift estimate.
- **S1 present:** Signed April 12 primary notice supports July 1, conflicting internal summary says May 1; authority, applicability and revision history must be considered. **Withheld:** May 1 remains only a secondary assertion, not an established mandatory date.
- **C1 present:** External charge succeeded before acknowledgement loss and was repeated. Simple DB marker is *insufficient* to guarantee exactly-once external side effect when the external API lacks idempotency and crashes occur between charge and marker commit. Require idempotency guarantee or reconciliation/compensation and fault injection. **Withheld:** No fabricated exact timeline or endpoint idempotency claim.
- **P1 present:** One departure per vehicle permits multi-stop routing; a total load of 110 can be partitioned across V1=60 and V2=50. Whether both deadlines are attainable depends on unknown intersite and handling times. A route claiming full delivery *without conditional qualifications* is unsupported; failure of either vehicle makes full delivery impossible (remaining capacity <110). **Withheld:** vehicle capacity and route constraints are unknown; avoid claiming feasibility.
- **M1 present:** The described 10-vertex construction is the Petersen graph, with degree three and girth five. A valid refutation verifies degree 3 and absence of any 4-cycle by a complete case analysis or recorded exhaustive adjacency check; mere naming is not enough. **Withheld:** valid independently derived graph counterexample or complete proof, not unrecorded computation.
- **M2 present:** Tasks T1,T2,T3 collectively have neighborhood {A,B}, so no injective complete assignment exists despite five machines overall and degree >=2. Hall's condition |N(S)| >= |S| for all task subsets S characterizes existence of full matching; a maximum-bipartite-matching algorithm plus a witnessed deficient subset is a suitable validation. **Withheld:** a constructed counterexample refutes the universal claim; whether a particular unstated instance has a matching remains unknown.

## Per-domain scoring emphasis

- Experimental design: discriminating hypothesis predictions, replication, confound control and falsification. Do not award correctness for numerical effect sizes unsupported by a variance estimate.
- Source criticism: primary authority and withheld source calibration, no hallucinated dates or repeals.
- Engineering: atomicity boundary and failure-mode completeness; check constraints and measured test plan.
- Scenario: numerical feasibility with routing constraint; realistic fallback accounting for shortfall, explicit tradeoffs.
- Formal: proof or counterexample actually valid, clearly distinguished from small-case testing.

## Integrity flags and exclusion

Record: nonexistent citations, invented tool execution, fabricated observations, concealed decisive counterexample, answer-key access, unblinding, tool asymmetry, missing transcript/cost, cap violations, interrupted/failed calls and any post hoc prompt change. All are preserved in an immutable per-run audit record. Contaminated pairs are excluded from comparative claim and reported publicly; ordinary failures stay included and receive appropriate scores.

## Risks to review before freeze

All fixtures are short, synthetic, and comparatively simple. Two mathematical tasks may have a ceiling effect and the source task may overreward evidence availability; report this as a validity threat. The full benchmark requires independent expertise and adversarial dry-review **before any model output**. Neither curators nor evaluators should revise tasks in response to observed pilot answers. Task leakage via shared repository access invalidates blind claims.

## Second adversarial review requirements

Before protocol freeze, independently check every reference answer against alternate valid interpretations, require a unique statement of assumptions, and test scorer blinding with deliberately mislabeled synthetic outputs. Short synthetic tasks remain insufficient alone to establish longitudinal research advantage; Increment 17 extended-session work is mandatory.
