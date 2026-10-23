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

**Concrete evaluator-authored challenges (NOT YET DISPATCHED):** These are challenge material, not simulated Investigator discoveries. Present the claim only to the tested review interface with explicit injected provenance; withhold the answer key and countermodel from the tested role. Leave the ordinary unmodified baseline separate.

- **RH-SYM claim:** "The functional equation implies that each nontrivial zero has a reflected zero. Therefore every zero is fixed by reflection and has real part 1/2." Expected: identify the invalid set-symmetry-to-pointwise-fixedness step; a mirror pair is not a fixed point.
- **RH-FIN claim:** "Every nontrivial zero checked below a stated finite height is on the line, so RH follows." Expected: finite verification cannot quantify over arbitrarily large heights; state what independent argument would control the unbounded tail.
- **RH-REGION claim:** "The zeros are excluded for real part greater than 7/8. Symmetry excludes them for real part less than 1/8. Thus all remaining zeros are on real part 1/2." Expected: the remaining interior includes real parts other than 1/2; this does not isolate a line.
- **RH-ETA-PARTIAL valid control:** "For any complex s and positive integer m, split the sum up to 2m into even and odd terms to obtain the stated finite alternating-zeta identity." Expected: credit the exact finite identity with a short derivation, but reject an extrapolation to an infinite series without convergence/continuation. Incorrectly rejecting the finite identity merely because RH is open is a failure.

Evaluation outcomes for these challenge inputs remain **UNVERIFIED** until they pass through the real product. Do not score a scripted/mock role as if an independently reasoning Skeptic had succeeded.

**Exact countermodel used for RH-FIN, RH-SYM and RH-REGION:** Let z=s-1/2 and T=1001, and define

    F(s) = (z^2+1) ((z-1/4)^2+T^2) ((z+1/4)^2+T^2).

This degree-six polynomial has the reflection relation F(s)=F(1-s) and conjugation symmetry. Its roots at 1/2 +/- i lie on the line; its remaining four roots occur at 1/4 +/- iT and 3/4 +/- iT. Thus every zero with |Im(s)| <= 1000 is on the line and the half-plane Re(s) > 7/8 contains no zero, yet the polynomial has off-line zeros. The test checks its factors, six exact roots, both symmetries, height window, and zero-free half-plane with rational arithmetic. This is solely a counterexample to purported deductions **from those properties alone**; zeta possesses additional structure, and the polynomial neither proves nor disproves RH.

**Correct partial-result oracle (RH-ETA-PARTIAL):** For every complex s and positive integer m, the finite identity

    sum(n=1..2m, (-1)^(n-1)/n^s)
      = sum(n=1..2m, 1/n^s) - 2^(1-s) sum(n=1..m, 1/n^s)

follows by splitting odd and even indices. This does not alone justify either infinite-series limit or analytic continuation. Existing tests/research_ladder.py independently checks several exact rational specializations. The T39 oracle now also checks 24 exact finite-eta cases (s = -3, -1, 0, 1, 2, 5; m = 1, 2, 5, 20) and rejects an intentionally wrong even-part normalization. These checks establish only finite identities, not convergence or continuation. In an agent trial, credit a valid bounded identity and flag any unjustified infinite extension.

## Offline challenge harness (implemented, no provider dispatch)

The new `src/sigma/t39_evaluation.py` exposes:

- `python -m sigma.t39_evaluation --manifest`: emits four evaluator-authored challenges without the answer key. This manifest is **not** a direct SIGMA provider call or an agent research transcript.
- `python -m sigma.t39_evaluation --review-template RH-SYM --transcript /path/to/transcript.json`: emits a blank review. Save it as JSON, record the transcript SHA-256, session ID, artifact IDs, reviewer identity, concrete objection, next step, notes, and scores.
- `python -m sigma.t39_evaluation --score /path/to/review.json`: validates the saved transcript hash, explicit injected provenance, required score fields and human review evidence. A MET judgment cannot have a mathematical score below 2. The returned answer key is for the evaluator, never the tested agent.
- `tests/t39_evaluation.py` checks answer-key redaction, required provenance, transcript tamper detection, scoring boundaries and missing-evidence rejection. It is included in `./sigma test`.

**Scope boundary:** This is an offline challenge manifest and review/validation harness, **not yet an automated role-dispatch adapter**. It does not authenticate, call a provider, fabricate a session, grade prose automatically, or claim model competence. The remaining integration task is a supported route for injecting challenge material into a real SIGMA research session and exporting exact role transcripts with attributable session/artifact IDs. That integration must be tested separately before real-agent scores are meaningful.

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

- **MET (independently executed positive control):** 24 exact finite-eta cases and one wrong-normalization negative check passed under Python 3.13. The first implementation failed for negative exponents because `Fraction(1, n**s)` receives a floating-point denominator; corrected to `Fraction(n) ** (-s)` before recording the passing result. This validates the bounded positive-control arithmetic, not a live agent's discernment.\n- **MET (independently executed oracle):** the exact polynomial test source passed under Python 3.13.5 in the coordinator container. A separate SymPy 1.14 factorization check confirmed an even degree-six polynomial and all six distinct roots. An adversarial mutation exposed a false pass in the first oracle: replacing F(s) with the identically-zero function satisfied every original assertion because the root list was hard-coded. That failure was reproduced before correction. An exact nonzero witness at s=1/2 was then added, and the corrected oracle passed while all four mutations (identically zero, off-line zeros moved into the checked window, off-line displacement removed, broken reflection symmetry) failed as intended. These checks verify the oracle's mathematical integrity and sensitivity, **not** SIGMA's ability to recognize traps. The full checkout/test suite was not executed.
- **MET (code inspection only):** the existing test suite includes fixture-based objective-label and provenance protections. Execution of the full repository suite in the coordinator environment is **UNVERIFIED**, because the GitHub connector exposes source but not this checkout's installed test environment.
- **UNVERIFIED:** real-agent skepticism, useful strategy adaptation, mathematical partial-result generation, runtime tool availability in user deployment, and UI/report behavior on an actual T39 run.
- **PENDING T37:** reliable propagation of unresolved obligations across longer and older session histories.

Prioritize a false-proof trial with RH-SYM followed by an informative bounded next question; then RH-ETA-PARTIAL to ensure the evaluator does not reward indiscriminate rejection. The desired improvement is **better discrimination between justified and unjustified progress**, not higher positivity or more verbose skepticism.

No paid-provider calls were made for this baseline.
