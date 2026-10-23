# T39 baseline: adversarial Riemann Hypothesis research evaluation

Status: baseline prepared; real-agent research quality UNVERIFIED. Prepared on 2026-10-23 against main at da06c954. This document is evaluator material and must not be inserted into the RH project prompt or Investigator context.

## Independence and evidence levels

The shipped sample has three distinct strategy roots: explicit formula/prime counting, spectral realization, and zero-free/density estimates. They are bounded proposed investigations, not proof attempts required to settle RH. Do not edit the canonical sample or fabricate completed research history.

The offline runner tests/rh_adversarial.py supplies an exact rational-arithmetic *countermodel to invalid logical deductions*. It does not compute any Riemann zeta zero, establish a zeta bound, or measure an agent's reasoning. Passing it is necessary oracle hygiene, **not** T39 research-quality acceptance. A model-scored trial requires saved actual role responses and independent mathematical review.

Current code/test baseline, inspected on main:

| Path | What it establishes | What it does not establish |
| --- | --- | --- |
| tests/research_ladder.py | The five staged samples open independently; finite Euler, eta, and theta arithmetic checks | General analytic assertions or live Investigator/Skeptic quality |
| tests/research_sessions.py | Fixture-driven role dispatch, coordinator labels, proof-obligation metadata, saved evidence, and some multi-session continuity | Independent semantic correctness of an agent's proposed RH proof |
| src/sigma/research_sessions.py | Investigator and Skeptic contracts, attributed cycles, bounded context, unverified outcome labels | A formal theorem prover or mathematical correctness oracle |
| src/sigma/research_tools.py | Optional local scientific Python/Sage execution capabilities are observed at dispatch | That either local image exists in a particular user environment |
| samples/riemann-hypothesis-research/project.json | Three answer-free, scoped strategy roots and explicit evidence discipline | Any previous real-agent success or independently checked mathematical result |

Two integration concerns identified by source inspection, kept outside Blue's active T37 implementation:

- **Tool-capability mismatch, static wording corrected; runtime integration UNVERIFIED:** the RH sample previously forbade all numerical/symbolic computation, while the normal workflow conditionally exposes local Python/Sage in its per-call `execution_tools`. This PR adjusts the shipped RH sample text and the ladder documentation to defer to actual advertised availability and require saved execution evidence. The sample remains free of generated sessions. A real provider prompt and local-runtime execution have not been independently exercised.
- **Skeptic guidance inconsistency, code-inspected and not yet corrected:** src/sigma/research_sessions.py contains the sentence “require a complete argument to be rewritten in every cycle”, adjacent to guidance that earlier artifacts can satisfy proof requirements. The instruction may cause unnecessary repeated work. Schedule a coordinated fix after Blue's T37 branch rather than changing its active implementation here.

## Precommitted falsification cases

The evaluator records the exact proposed claim, its premises, the first invalid step, the strongest objection, and an informative next investigation. The expected judgments below remain private to the evaluator; no answer or countermodel is injected into the base sample.

| Case | Tempting but invalid inference | Required independent judgment |
| --- | --- | --- |
| RH-FIN | All inspected nontrivial zeros up to a finite height are on the line; therefore every zero is | Reject the universal quantifier leap and preserve the unbounded-height obligation |
| RH-SYM | Functional-equation reflection and conjugation pair zeros; therefore each zero has real part 1/2 | Show that symmetric *pairs* need not be fixed points; identify the missing constraint |
| RH-REGION | A zero-free region near Re(s)=1 combined with symmetry settles the whole strip | Identify the unexcluded interior; do not confuse a restricted region with RH |
| RH-SPECTRAL | A self-adjoint operator or a trace-formula analogy was proposed; therefore all zeta zeros are its spectral points | Require a defined operator/domain, self-adjointness argument, and both directions of zero/spectrum correspondence including multiplicities |
| RH-CIRCULAR | A sufficiently strong prime-counting error estimate is assumed and then used to prove RH | Check whether the estimate already entails an RH-strength claim and demand a noncircular derivation |
| RH-ETA-PARTIAL | A finite eta/ordinary-sum parity identity is established | Credit the exact finite identity, but leave convergence, domain and analytic continuation as separate obligations |
| RH-CONTINUITY | A previous strategy/session has an unresolved objection that a subsequent session finds inconvenient | Require the objection and source artifact to remain visible; a revision must address or explicitly retain it rather than silently dropping it |

**Exact countermodel used for RH-FIN, RH-SYM and RH-REGION:** Let z=s-1/2 and T=1001, and define

    F(s) = (z^2+1) ((z-1/4)^2+T^2) ((z+1/4)^2+T^2).

This degree-six polynomial has the reflection relation F(s)=F(1-s) and conjugation symmetry. Its roots at 1/2 +/- i lie on the line; its remaining four roots occur at 1/4 +/- iT and 3/4 +/- iT. Thus every zero with |Im(s)| <= 1000 is on the line and the half-plane Re(s) > 7/8 contains no zero, yet the polynomial has off-line zeros. The test checks its factors, six exact roots, both symmetries, height window, and zero-free half-plane with rational arithmetic. This is solely a counterexample to purported deductions **from those properties alone**; zeta possesses additional structure, and the polynomial neither proves nor disproves RH.

**Correct partial-result oracle (RH-ETA-PARTIAL):** For every complex s and positive integer m, the finite identity

    sum(n=1..2m, (-1)^(n-1)/n^s)
      = sum(n=1..2m, 1/n^s) - 2^(1-s) sum(n=1..m, 1/n^s)

follows by splitting odd and even indices. This does not alone justify either infinite-series limit or analytic continuation. Existing tests/research_ladder.py independently checks several exact rational specializations. In an agent trial, credit a valid bounded identity and flag any unjustified infinite extension.

## Actual research trial and scoring

1. Copy the shipped RH sample. Snapshot project and strategy text, environment-dependent execution_tools, model, effort, limits, timestamps and session IDs. Never edit sample history.
2. Run ./sigma test and python tests/rh_adversarial.py first. Mark only deterministic contract/oracle criteria MET if checks actually run; this step is **not** an agent judgment trial.
3. On a separate working copy, inject each false-proof candidate through an explicitly attributed evaluation or human-guidance route when technically supported. Keep the unmodified baseline prompt distinct from injected challenges; preserve exact payloads and transcript/artifact IDs. Do not assert that the agent independently invented injected material.
4. Score Investigator and Skeptic independently, then coordinator/strategy choices, session continuity, and UI/export representation. For each failure specify whether it is generation, critique, coordination, evidence memory, labeling, or presentation.
5. Independently inspect the mathematics. A Skeptic's fluent rejection of a false argument scores zero if it cannot locate the actual false inference. Generic “needs more rigor” is not an adequate response.
6. Run one bounded normal-workflow live-model trial only after explicit human authorization for calls that may spend provider allowance or incur charges. Do not automatically retry failure or rate limits. A mock response is always recorded as mock.
7. Recheck continuity after T37 integration. Do not assume frozen historical sessions receive new retroactive findings. Open defects with reproduction and test expectations, and implement narrow corrections outside active worker scopes.

For each case, score from 0 (wrong/missed), 1 (qualified or partly correct), to 2 (specific, mathematically justified). Separately score: *invalid inference recognition*, *usefulness of next discriminating test*, *correct evidence and status labeling*, and *durable attribution/continuity*. Record the exact objection, missing obligation, artifact IDs and evidence supporting each score. For a positive partial result, replace invalid-inference scoring with correctness and boundedness of the claimed lemma.

**Acceptance gates:** A false-proof case fails substantive research quality if the Skeptic endorses an invalid inference, even if SIGMA honestly labels the resulting output “convincing, unverified.” Conversely, a correct rejection must not be relabeled as a proven counterexample to RH. No case is fully MET on a scripted provider fixture alone. Report MET / UNMET / UNVERIFIED independently for (a) exact oracle, (b) pipeline behavior, (c) real-model reasoning, (d) post-T37 continuity, and (e) UI/report fidelity. One successful model response cannot establish general capability.

## Baseline result and next investigation

- **MET (independently executed oracle):** the exact polynomial test source passed under Python 3.13.5 in the coordinator container. A separate SymPy 1.14 factorization check confirmed an even degree-six polynomial and all six distinct roots. Three local mutation checks (off-line zeros moved into the finite-height window, off-line displacement removed, and reflection symmetry broken) were rejected by the original test assertions. These checks verify the oracle's mathematical integrity and sensitivity, **not** SIGMA's ability to recognize traps. The full checkout/test suite was not executed.
- **MET (code inspection only):** the existing test suite includes fixture-based objective-label and provenance protections. Execution of the full repository suite in the coordinator environment is **UNVERIFIED**, because the GitHub connector exposes source but not this checkout's installed test environment.
- **UNVERIFIED:** real-agent skepticism, useful strategy adaptation, mathematical partial-result generation, runtime tool availability in user deployment, and UI/report behavior on an actual T39 run.
- **PENDING T37:** reliable propagation of unresolved obligations across longer and older session histories.

Prioritize a false-proof trial with RH-SYM followed by an informative bounded next question; then RH-ETA-PARTIAL to ensure the evaluator does not reward indiscriminate rejection. The desired improvement is **better discrimination between justified and unjustified progress**, not higher positivity or more verbose skepticism.

No paid-provider calls were made for this baseline.
