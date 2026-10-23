# Riemann Hypothesis research ladder

This is a staged capability exercise, not evidence that a model can solve the
Riemann Hypothesis. Its five runnable entries appear in SIGMA's Samples list:

| Stage | Sample | Difficulty | Research skill under examination |
|---|---|---:|---|
| 1 | Counting Pairwise Handshakes | Easy | Derive a finite counting formula from an answer-free prompt, check boundary cases, and make the counting convention explicit. |
| 2 | Prime Factorization and the Euler Product | Medium | Convert a finite factorization into a convergent Dirichlet-series identity; state the half-plane and justify limits. |
| 3 | The Alternating Zeta Series and Analytic Continuation | Hard | Establish complex-series convergence locally uniformly, track the multiplier and exceptional points, and delimit the continuation actually obtained. |
| 4 | Theta Symmetry and the Zeta Functional Equation | Hard | Carry a Mellin-transform argument through normalization, continuation, poles, and zero symmetries without mistaking symmetry for RH. The Gaussian theta transformation is an explicit premise. |
| 5 | Riemann Hypothesis: A Research Portfolio | Hard | Keep proof obligations, counterexamples, source and computation limits, and partial progress separate from proposed research programs. |

The first three projects have two human-authored strategy roots each; the RH
capstone has three: explicit formula and prime-counting consequences, a
spectral realization, and zero-free/density estimates. They are intentionally
distinct routes for testing portfolio comparison and skeptic attribution.
They provide methodological hints, so their runs are **not independent
discovery tests**. The RH strategies are research programs with explicit
obligations, not candidate proofs.

## Run protocol

1. Open a fresh copy of each Sample. Do not run the answer-bearing Maximum
   Regions Sample as an independent-discovery benchmark.
2. Use the same reviewed model and thinking level, and record the actual
   project settings. Select at least two strategies in the A18 session selector
   when the project has multiple strategies.
3. Start with the Easy project at two calls and one round. If its outputs and
   plan status are healthy, advance to the Medium project at eight calls and
   two rounds, then Hard projects with four calls (two-strategy, one-round
   sessions) and the RH portfolio with six calls. Cap each session at ten
   minutes. The calls use the already-connected ChatGPT plan; abort if the
   active mode is not ChatGPT-plan or if a provider limit/throttle occurs. No
   retry loop or API-key fallback is allowed.
4. Preserve every Investigator and Skeptic step. Score a challenge only on
   exact claims and linked evidence; a strategy title or confident conclusion
   is not evidence. Record unresolved objections and unsupported recollections.
5. Independently check any claimed lemma. The offline `tests/research_ladder.py`
   runner verifies finite Euler-product enumeration, finite even/odd eta sums,
   and truncated theta-transform values. Those checks validate examples and
   arithmetic only; they do not prove convergence, analyticity, the functional
   equation, or any zero-location claim.
6. Do not call an RH result successful without a complete proof or valid
   counterexample reviewed by qualified mathematicians. Finite zero tables,
   numerical agreement, a spectral analogy, and model consensus cannot meet
   this bar.

## Scoring rubric

Score each dimension 0 (absent/incorrect), 1 (partial or unsupported), or 2
(specific and justified). Preserve the underlying quotations and artifact IDs.

- **Mathematical correctness:** definitions, domains, quantifiers, and
  implications are exact.
- **Derivation:** each nontrivial step is justified; a recalled theorem is
  named and its required hypotheses are checked rather than silently assumed.
- **Convergence and analytic control:** sums, products, limits, transforms,
  and interchanges have an explicit valid domain and bound.
- **Independent criticism:** the Skeptic identifies a concrete gap,
  counterexample, or missing hypothesis in a cited Investigator claim and
  states what would discharge it. Generic requests to “check rigor” score 0.
- **Coordinator calibration:** status follows the saved evidence and unresolved
  obligations; computational agreement or proof-shaped prose is never labeled
  verified.
- **Reproducibility:** inputs, strategy text, model/effort, call/time limits,
  session ID, role outputs, and independent checks are preserved.

For the RH capstone, an evaluator must separately mark whether an output is a
proof, a valid counterexample, a correct partial theorem, or only a research
proposal. An absent source/computation/proof tool is a product limitation and
must not be hidden by a model's recollection. Do not aggregate scores into a
probability of solving RH.

## Interpretation limits

These scenarios test the current research workflow and mathematical
communication, not real-agent generalization. Strategy prompts leak methods by
design; deterministic provider fixtures test persistence and coordination, not
reasoning quality. Even a correct run of the first three stages would show
prerequisite competence only. SIGMA has no in-session external reference search or formal proof-assistant
integration. Scientific Python and SageMath are optional local computation
runtimes; each Investigator/Skeptic call receives the actually observed
availability in `execution_tools`. The sample must not imply a computation ran
unless a saved execution record establishes it. Finite numerical or symbolic
checks do not prove RH or replace independent mathematical and expert review.
