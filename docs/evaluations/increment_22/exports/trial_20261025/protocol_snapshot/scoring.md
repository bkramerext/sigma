# Increment 22 single-case scoring sheet (freeze before model outputs)

Do not collapse the comparison into one aggregate score. Record arm IDs only
after each transcript has been scored from its actual saved records. The
checker and answer stay outside both model contexts.

## Correctness anchors

- Proposed schedule validity: verify every job exactly once, eligibility,
  duration, no machine overlap, and predecessor completion. Record valid/invalid.
- Best schedule found: compare makespan to the exact optimum 10. Record the
  lowest valid makespan present in that arm's saved work: 13 or worse, 11–12,
  or 10. A malformed/unsupported schedule is not a candidate.
- Optimality argument: 0 = none/invalid; 1 = plausible but incomplete; 2 = a
  correct lower bound or a correct schedule, but not both; 3 = valid 10-unit
  witness and valid 10-unit lower bound. The lower bound may use the M1-only
  jobs D/F/G (durations 3+2+5).
- Unsupported assertions: list each claim that exceeds the saved evidence.
  Distinguish a failed or clipped call from a mathematical counterexample.

## Collaboration and self-review

For every Skeptic objection or baseline self-critique, record its source turn,
verbatim bounded excerpt, validity against the frozen task/checker, whether it
identifies a specific flaw or discriminating check, and what the next work does
with it. Classify the next work as adopted with a concrete change, explicitly
rejected with a reason, acknowledged without a change, or ignored. A role label,
generic warning, agreement, or self-reported uptake earns no substantive
collaboration credit. Record whether the objection changed the candidate
schedule, lower-bound argument, computation, or conclusion.

Rate critique specificity separately: 0 = none/repetition; 1 = generic doubt;
2 = specific but invalid/unresolved objection; 3 = specific valid objection or
test that changes subsequent work. Report both whether SIGMA's Skeptic adds a
valid intervention and whether the single-agent baseline finds an equally valid
self-objection.

## Evidence, completeness, resources

- Evidence survival: compare each relied-on claim with its saved source,
  provider input hash, call usage, computation source/result/status/hash and
  export. Record missing, omitted, corrupt, or truncated evidence explicitly.
- Clipping: if the provider stops at `max_output_tokens`, or a structured
  response is incomplete, label the arm/run **incomplete**. Preserve the exact
  partial response, usage, request hash and budget reservation. Do not score it
  as an incorrect research answer or retry it. Report this separately from a
  completed but wrong result.
- Cost: report provider-returned token usage and billing dashboard amount when
  available; also report the conservative reserved upper bound and distinguish
  them. Never treat a reservation as an invoice.
- Time: report arm wall time and whole-trial elapsed time from monotonic clocks.
- Keep every adverse/negative result. No post-output exclusions or task
  replacement. This one custom case is descriptive only, not a superiority test.
