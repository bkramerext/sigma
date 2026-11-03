# Research outcome quality contract

Research Session outcomes are durable research artifacts, not display summaries.
An outcome should let a reader identify the objective and bounded strategy,
follow the evidence-linked reasoning, examine the challenge, reproduce or reject
the result, and see what remains uncertain. This is an explanatory research
record; it is not unrestricted model chain-of-thought.

## Pipeline and root cause

Research information flows through a bounded Investigator response, optional
local computation, a Skeptic response, coordinator reconciliation, an atomic
session record, a derived outcome projection, the Research Session view, and
project report/paper evidence exports. Full role responses and methods were
already saved on each artifact. The main loss was at the synthesis and
presentation boundary: a short `argument_summary` could support an achieved
candidate, while the actual method and objections lived separately in the
artifact disclosure. The outcome projection and report preferred the summary.
Some prior context extracts also omitted structured argument material even
though the source artifact remained intact.

History review found no evidence that a later persistence change deliberately
deleted the original research method. A17.4 introduced a compact outcome plus
separate artifact disclosure; T20.1 refined that presentation and T24 added
metrics/provenance. Those changes kept records but did not require the outcome
summary/report to carry the underlying derivation. The regression is therefore
an outcome-contract gap, with reasoning often generated and persisted but
compressed or separated before synthesis and human review. Older records may
contain useful prose methods without enough structured evidence to assess a
complete proof; the read projection now marks those candidate outcomes as
incomplete rather than silently upgrading them.

## Generation and preservation

- Investigator `reasoning_steps` are ordered, explicit claims with their
  justification, epistemic kind (deduction, assumption, computation, or
  conjecture), and source artifact references.
- Skeptic `reasoning_assessments` address each step by number, state the
  disposition and rationale, and preserve any precise objection.
- An achieved outcome requires every step to have a corresponding accepted
  review with a substantive rationale, plus the existing objective, obligation,
  counterexample, and evidence checks. A missing or challenged step remains
  visible but prevents complete status.
- Mathematical `assumption` steps are premises, never proven facts. They can
  support only a claim explicitly marked conditional by both Investigator and
  Skeptic, and only when the exact premise appears in both the declared and
  reviewed assumptions. The saved claim and report say “Conditional on …”. A
  disagreement about scope blocks completion. The Maximum Regions theorem is
  conditional on the ordinary domain premise of distinct Euclidean lines; its
  attaining construction must still establish general position rather than
  assume it for every arrangement.
- A reasoning step can preserve 12,000 characters. The 24-step bound remains a
  schema and context safety ceiling. Prompts require an explicit partial result
  and named omitted obligation when these bounds are insufficient; validation
  rejects over-bound output rather than truncating it into apparent support.
- The artifact stores both role outputs and their joined, source-linked
  reasoning. The outcome projection, JSON export, text/HTML project reports,
  and paper evidence snapshot retain the same material. Context compaction keeps
  these fields or fails closed at the existing context bound; it must not turn a
  truncated extract into support for a proof.
- Agent agreement is agent-reviewed, unverified evidence. Computation is not a
  proof of a universal claim; formal verification and human review are claimed
  only when those events actually occurred.

## Human review contract

Within the existing Research Session Outcome area, show the investigated
objective and strategy, result, stepwise reasoning and Skeptic assessment,
assumptions, source artifact references, objections, open proof obligations,
and verification limits. Existing Markdown rendering supports mathematical
notation. Full original role outputs and computations remain available through
the existing artifact/provenance disclosures. Reports must carry the actual
argument steps, not just the summary.

Missing reasoning in a historical record is reported explicitly. Do not infer a
proof from a formula, sample-value agreement, a `stop` decision, or agreement
between agents. Do not fill missing steps in synthesis or paper generation.

## Showcase interpretation

For a multi-strategy session, the session-level lifecycle status is `failed`
only when every selected branch fails. If one branch fails while another
produces findings or ends at its budget, the session ends as `ended`; its
portfolio decision retains the failed branch as `hold_after_failure` and keeps
the sibling evidence. This represents a completed portfolio execution with a
mixed branch result. A17's browser check now asserts this behavior instead of
expecting one provider failure to erase successful sibling work.

The Maximum Regions sample is the positive mathematical acceptance case: a
complete candidate must state the domain and general-position construction,
justify the insertion upper bound and splitting argument, exhibit attainment,
derive the recurrence and closed form from the base case, and preserve Skeptic
review and caveats. Its deterministic tests exercise the saved pipeline; they
do not establish live-provider quality.

The Riemann Hypothesis showcase remains a bounded research portfolio, not a
claim to solve RH. Its seeded objective and three strategy descriptions require
finite computations, zero-free regions, spectral analogies, and other partial
results to remain scoped to their actual hypotheses. Unbounded-height,
convergence, correspondence, and other unresolved proof obligations must stay
visible. The sample has no generated research history, and this change does not
fabricate one or claim live agent performance.


## P0 Scientific Outcome policy (scientific-v2)

Research Session Outcome describes the *scientific acceptability of saved
evidence*, never the execution lifecycle (Ended, Failed, etc.). The public
assessment enum remains pending, positive, mixed, negative. Retain the current
Outcome section and Simple/Advanced presentation; no separate scoring UI.

| Outcome label | Required scientific disposition |
| --- | --- |
| Positive · solution candidate (unverified) | A complete, scoped, evidence-linked, critically reviewed candidate answer with no outstanding essential dependency or material conflict |
| Mixed · promising finding; validation needed | Substantial finding, but essential validation or evidence is missing |
| Mixed · partial progress, unresolved | Supported partial work with unresolved objective requirements |
| Mixed · inconclusive | Neither a supported positive nor meaningful negative finding |
| Mixed · conflicting findings, unresolved | Materially incompatible claims with cited unresolved conflict |
| Mixed · claim retracted | Withdrawn candidate without a surviving complete result |
| Negative · supported negative finding (unverified) | Reviewed and scoped objective-level counterexample or exclusion, not merely a failed strategy |
| Negative · counterexample reported | Historical, agent-reported counterexample without a fully supported negative-evidence review |

A supported negative result is valuable scientific work, not a low grade. A
proof that impossibility holds is a Positive candidate when proving
impossibility is the objective. Failure to find a proof, failure of one strategy,
and execution failure are **not** negative findings.

### Separate obligation status from objective dependency

All obligations stay in the original ledger, even when a complete candidate
is admitted. An unresolved item is objective_blocking, nonblocking_followup,
or undetermined. Unknown dependencies block completion. A typed dependency
review identifies the exact obligation text, an argument-step basis and a
specific rationale; reviewer agreement alone does not establish closure.

A historical mathematics-only compatibility path allows an explicitly
independent peer-source inspection to remain open alongside a complete
reviewed argument. The note must expressly disavow dependence on the proof
and all critical argument steps must have accepted reviews. Merely containing
words such as peer, citation, reference, literature or source does not suffice.
A novelty claim may depend on source research even when a mathematical
derivation does not.

No automatic global closure of Investigator obligations is allowed just
because a Skeptic reports objective achieved. Only separately evidenced
dispositions resolve obligations. Unknown and truncated evidence remains
visible, unresolved and ineligible for a candidate promotion.

### Scientific sufficiency

Candidate admission checks saved claim, scope, assumptions, evidence links,
distinct objective/proof obligations, supporting cycle IDs, accepted
stepwise criticism, and unresolved scientific dependencies. Mathematical
conjectures and finite computations do not establish universal proofs.
Conditional premises must be explicitly declared and independently reviewed
as premises, not converted to theorems.

Nonmathematical evidence review must connect stated objective requirements
to concrete saved sources, models or observations. Mathematics needs sound
inference, physical claims must separate consistency/simulation from
realizability, biology needs relevant observational units and controls,
AI engineering needs actual execution and meaningful test oracles, literature
needs inspected primary text for text-dependent claims, and military planning
needs scoped scenarios, alternatives and explicit uncertainty. These
requirements depend on the **actual claim**, not a discipline stereotype.

A complete but independently unverified solution remains an unverified
candidate. Successful code execution, source URL retrieval, the Investigator
agreeing with the Skeptic, and a legacy verified flag do not provide
independent scientific verification. The conservative verification-label
contract remains unchanged.

### Portfolio and historical interpretation

Determine each strategy's final applicable finding from strategy identity and
cycle, not arbitrary global artifact completion order. Use concrete,
scope-compatible, cited contradictions and retractions. Different wording is
not contradiction; two partial arguments do not automatically make a proof.
One complete candidate can coexist with another compatible incomplete or
failed strategy. An objective-level contradiction must block an unqualified
Positive candidate.

Outcome is a read-only projection with a policy-version identifier.
Frozen saved sessions and artifacts are never rewritten. A past mistaken
partial review can be interpreted as an unverified candidate **only** when
the saved original evidence passes the new scientific predicate. Historical
incomplete arguments or missing evidence must fail closed.

### Maximum Regions v4 calibration

The original archive contains 12/12 accepted research turns, six artifacts,
and final Skeptics claiming achievement with eight and nine accepted
argument steps. The old objective gate treated peer-only proof-source
inspection as blocking and also conflated scheduling stop with scientific
completion. The derived Outcome may now be Positive · solution candidate
(unverified) when the saved proof dependencies support this classification.
The optional peer/source inspections remain visibly open. This is not formal
or independent verification of the mathematics.

Provider-free regression tests cover complete candidates with optional peer
inspection, missing attainments or critical steps, unknown dependencies,
conflicting/retracted claims, negative findings, order invariance, empirical
data gaps and preservation of frozen records. Integrated engineering gates
remain Chat A's responsibility.
