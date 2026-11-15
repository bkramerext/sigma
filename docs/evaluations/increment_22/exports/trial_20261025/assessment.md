# T146 live comparison assessment

**State:** One authorized paired trial executed and preserved. The read-only
Models API verification succeeded before the first research-generation call.
The SIGMA session ended after one Investigator/Skeptic cycle with a productive
conclusion; cycle two was not run. This is a single descriptive case, not a
superiority result.

## Verification and protocol

- The latest PR #150 coordinator instruction was read before the checks. The
  project-scoped API credential was used only from the environment and was not
  written to evidence. A read-only `GET /v1/models/gpt-6.1-sol` with the
  configured `OpenAI-Project` context returned HTTP 200 and the exact model ID.
  The successful request ID is in the sanitized preflight record. An earlier
  401 attempt is retained as negative evidence.
- The task, checker, prompts, scoring sheet, settings, execution procedure,
  and the existing budget/session implementation match the frozen SHA-256
  manifest. The trial-local protocol snapshot has its own manifest.
- A fair coin selected baseline first. Both arms used the same project-scoped
  API key, model `gpt-6.1-sol`, high reasoning, `store=false`, a 4,096 output
  token per-call cap, four-call maximum, 200,000 reserved input-token ceiling,
  $0.67 local cost ceiling, and 15-minute arm ceiling. Neither request body
  set `service_tier`; every response reported `default`. OpenAI documents that
  `default` uses standard pricing and performance, and that the omitted
  parameter defaults to project `auto`/`default` behavior ([Responses API
  reference](https://developers.openai.com/api/reference/resources/responses/methods/create)).
- SIGMA ran through its production `research_sessions.start_session` worker,
  with a saved project, strategy, session, Outcome, computation, and normal
  project export. The baseline used the frozen four-turn prompt and the shared
  pre-dispatch ledger. No scripted model responses were used.
- One local SIGMA setup attempt failed before session creation because the
  runner read the project limits from the wrong path. It dispatched no request.
  The corrected run resumed only the not-yet-started SIGMA arm; the completed
  baseline was not rerun. This local setup failure is preserved.
- Runtime-only connection metadata reused the successful model lookup for the
  bounded run, avoiding repeated model-list requests. The SIGMA research worker
  and its hard token/cost ledger remained the production implementation.
- There were no generation retries, fallback models, external searches, or
  timeouts. The baseline made no local computation; SIGMA made one isolated
  Python computation using the available offline image. Neither arm was
  clipped or incomplete.

## Results against the frozen checker

The checker confirms the proposed schedule is valid with makespan 13 and
exhaustively checks 2,016 eligible assignment/order cases. Its exact minimum
is 10, with M1 order D-F-G and M2 order A-B-E-C.

| Measure | Single-agent baseline | SIGMA Investigator/Skeptic |
|---|---:|---:|
| Completed research calls | 4 | 2 |
| Turns / completed cycles | 4 turns | 1 cycle, then productive stop |
| Valid 10-unit witness found | Yes | Yes |
| Correct 10-unit lower bound | Yes | Yes |
| Optimality argument rubric | 3/3 | 3/3 |
| Critique specificity rubric | 2/3, specific but invalid | 0/3, no substantive objection |
| Usage-derived cost at frozen rates | $0.044308 | $0.100792 |
| Conservative settled-ledger cost | $0.045150 | $0.100795 |
| Arm elapsed time | 79.678 s | 104.935 s |

The SIGMA Investigator gave the valid schedule M1 D-F-G and M2 A-E-B-C, the
M1-only workload lower bound of 10, and a separate 20-unit/two-machine bound.
Its isolated program independently considered 2,016 assignment/order cases,
found 808 acyclic cases and 14 optimal orders, and returned makespan 10. The
checker independently confirms the exact minimum and the displayed schedule.

The Skeptic received the Investigator's saved work and the completed
computation result; the exact second request body contains the schedule,
execution status, and enumeration result. It noticed that the Investigator's
proposal-time note predated execution and correctly treated the completed run
as later evidence. It otherwise repeated the schedule and lower bounds. It
raised no objection, changed no schedule or proof, and no second Investigator
turn followed. This is evidence of within-session evidence transfer, but not of
a substantive Skeptic improvement to the research.

The baseline also found a valid 10-unit schedule and a correct capacity lower
bound in turn 1. In turn 2 it claimed the eligibility table and full precedence
graph were missing, although both were present in the frozen task it received.
It adopted that false objection in turn 3 and ended by withdrawing its correct
unconditional optimum claim. The critique was specific but invalid, and it
made the final report less accurate. The checker confirms the original input
was sufficient and confirms the baseline's 10-unit witness and bound.

**Comparison judgment:** In this case the Skeptic did not materially improve
research. SIGMA preserved and passed actual computation evidence to the
Skeptic, while the baseline's stronger self-review opportunity produced a
false concern and a regressed conclusion. Both arms had already found the
same correct mathematical result, so the case supports neither general
superiority nor a reliable advantage for either review arrangement. It
demonstrates evidence accumulation across one SIGMA agent pair, not multiple
rounds of iterative multi-agent revision.

## Usage, cost, and elapsed time

| Arm | Input tokens | Output tokens (including reasoning) | Reasoning tokens | Usage-derived cost | Conservative settled cost |
|---|---:|---:|---:|---:|---:|
| Baseline | 4,264 | 3,449 | 1,787 | $0.044308 | $0.045150 |
| SIGMA | 14,322 | 6,499 | 2,867 | $0.100792 | $0.100795 |
| **Total** | **18,586** | **9,948** | **4,654** | **$0.145100** | **$0.145945** |

These usage-derived charges apply the frozen Standard rates to the actual
provider-reported regular input, cache-write input, cached input, and output
tokens. The six Responses were all completed on the requested model; output
usage included reasoning tokens. No output reached the 4,096-token ceiling.
The $1.32768 total is the frozen full-reservation maximum, not the observed
charge. Brian confirmed the project's $1.40 enforced cap. A provider billing
dashboard export was not available, so the posted invoice/project aggregate
amount and any unrelated pre-existing project usage remain unverified; the
figures above are usage-derived at frozen rates, not a dashboard receipt.

Baseline arm elapsed time was 79.678 seconds; SIGMA arm time was 104.935
seconds. Overall elapsed time from the first arm start through final completion
was 232.236 seconds (3 minutes 52.236 seconds), using the recorded cross-process
UTC interval reconciled with the final monotonic timer. This includes about
47.6 seconds spent diagnosing and repairing the local setup error. The
45-minute overall ceiling was not approached.

## Evidence and follow-up

The raw baseline request/response bodies, full transcript, and settled ledger
are under `baseline/`. The SIGMA project tree, production session export, full
session record, raw request/response bodies, computation source/result, and
ledger are under `sigma/` and `sigma_projects/`. Preflight failures and
successes, randomization, runtime capabilities, checker output, accounting,
and a SHA-256 evidence manifest are preserved beside this assessment. Request
authorization headers and the API key are excluded.

**T147 recommendation:** Warrant a diagnostic follow-up, but do not start it
without the owner's instruction. The saved Skeptic output has
`assessment=stop`, `stop_reason=unresolved`, and
`strategy_contribution=solution`, while the coordinator records
`stop_productive_conclusion`, the objective review is achieved, and there are
no unresolved objections or open obligations. This record-level stop-state
inconsistency should be diagnosed before treating the status fields as reliable
collaboration evidence.
