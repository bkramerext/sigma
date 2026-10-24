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
