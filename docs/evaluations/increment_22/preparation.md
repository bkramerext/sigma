# Increment 22: offline trial preparation

**Issue:** [#146](https://github.com/bkramerext/sigma/issues/146)  
**Prepared from:** `main` at `19e5bd7`  
**State:** Offline preparation only. No provider calls, billing, or Cloud work.  
**Empirical result:** None. Awaiting explicit approval and closure of the budget-enforcement gate.

## Question and comparison

Test whether a saved SIGMA Investigator/Skeptic session accumulates useful
evidence and whether a skeptical intervention causes a substantive change in
the next Investigator work, compared with a strong same-model single-agent
conversation that explicitly critiques and revises its own work. This is one
exploratory case, not a general superiority or cross-session-persistence claim.

Use the newly authored two-machine, seven-job nonpreemptive scheduling problem
in [`task.json`](task.json), not a stock project or benchmark item. It gives
durations, machine eligibility, two precedence relations and a valid proposed
schedule claimed to be optimal. That concrete overclaim creates an opportunity
to reject an attractive but suboptimal answer and revise the plan. The task is
an authored finite instance; workshop scheduling is a familiar topic, and no
domain novelty is claimed. Its small size is intended to make exact checking
practical while still requiring resource-order reasoning.

Before either arm ran, [`checker.py`](checker.py) was written to validate the
proposed schedule and enumerate every eligible machine assignment and machine
order, rejecting cyclic precedence orders and computing each acyclic order's
earliest feasible makespan by longest paths. It checked 2,016 assignment/order
cases. The proposed schedule is valid with makespan 13; exhaustive enumeration
finds a minimum of 10, with M1 order D-F-G and M2 order A-B-E-C. A separate
hand-checkable lower bound is that D, F and G are M1-only and require 10 total
machine-time units. The checker and this answer must be kept out of both model
contexts. Freeze/hash the task and checker before calls; the providers receive
only the task question, job data and proposed schedule. The eventual exports
must retain full role work, objections and any failed path even if neither arm
finds the 10-unit schedule.

The SIGMA arm is a real saved project and research session with the production
Investigator/Skeptic cycle and Outcome. The baseline is one persistent
same-model conversation: first analysis, explicit self-critique, revision,
second self-critique, and final revision. Give both arms the same task, model,
reasoning effort, no external search, no computational tools, and comparable
call, token, wall-clock, and dollar limits. Both arms may use at most two local
computations total in the same offline Python/Sage runtimes and limits; no
external tools, web, delegation, or package installs. The baseline sees only its own
transcript. The evaluator sees both complete transcripts and checks them against
the frozen checker after both runs. Preserve negative results and every failed
or clipped call.

## Proposed execution limits (not yet authorized)

- Provider and billing: OpenAI API, explicitly selected API-key billing; no
  ChatGPT-subscription fallback.
- Model/configuration: exact model `gpt-6.1-sol`, `reasoning_effort=high`,
  standard service tier; same for both arms. No external tools, web,
  delegation, retries, or fallback model.
- Calls: at most four provider calls per arm (eight total); SIGMA uses two
  Investigator/Skeptic cycles. Baseline uses four sequential self-review turns.
- Output: at most 4,096 generated tokens per call (16,384 per arm).
- Cumulative input: at most 200,000 reserved input tokens per arm and 16,384
  generated output tokens per arm (4,096 per call). Before dispatch, input is
  reserved as the exact UTF-8 serialized request-body byte count plus 8,192
  structural-token allowance per call. The hard ledger blocks dispatch when
  cumulative input, output, calls, or cost would exceed the ceiling. An
  unsettled/in-flight or unknown call retains its full reservation and blocks
  later dispatch. Four requests each reserve at most 41,808 input tokens, so
  four full-size calls fit within the arm ceiling; larger actual requests may
  make the ledger stop earlier. Combined ceiling: 400,000 reserved input and
  32,768 output tokens.
- Wall time: 15 minutes per arm, with a 45-minute overall trial window. Stop
  at the limit; do not retry failed calls.
- Cost: local pre-dispatch cost ceiling is $0.67 per arm. At the configured
  ceilings, the highest applicable listed Standard short-cache write rate
  ($2.50/M) plus output rate ($10/M) reserves at most $0.66384 per arm /
  $1.32768 total. The operator must set the monthly limit to $1.40 for the exact API project and
  turn on **Enforce a hard limit** before any request. A threshold without this
  toggle only alerts. OpenAI says enforcement
  is not instantaneous and may slightly overshoot the setting, so that control
  alone is not the absolute cap. Before any call, demonstrate a local
  pre-dispatch token guard and reserve for any ambiguous in-flight call; if it
  cannot enforce the token ceilings, do not run.

At the official OpenAI Standard rates checked 2026-10-25, `gpt-6.1-sol` is
$2/M input, $0.10/M cached input, $2.50/M short cache writes and $10/M output
tokens. At the revised ceilings, short cache writes and output give a
conservative $0.66384 per arm / $1.32768 combined upper bound, assuming no
extended cache retention or external tools. The $1.40 provider hard limit is a backstop; the pre-dispatch guard is needed
because provider enforcement may lag. Recheck pricing and model availability
before approval:
[OpenAI API pricing](https://developers.openai.com/api/docs/pricing).

### Output-cap reassessment

The Responses API defines `max_output_tokens` as including both visible and
reasoning tokens; the reasoning guide also confirms internal reasoning tokens
consume that same budget ([API reference](https://developers.openai.com/api/reference/resources/responses/methods/create),
[reasoning guide](https://developers.openai.com/api/docs/guides/reasoning)).
Thus 1,024 total tokens leaves an unpredictable, potentially small visible
budget for SIGMA's strict structured role output and the baseline's research
note. Recommend 4,096 per call as the smallest defensible cap for this task:
four times the prior limit, with a 16,384-token arm maximum. This gives room for
high-effort internal reasoning plus concise structured findings without
increasing call count or duration. It cannot guarantee completion; clipping
remains an incomplete run and stops that arm without a correctness penalty or
retry. No provider inference was used to tune this number.

With 200,000 reserved input tokens/arm at the maximum applicable $2.50/M input
cache-write rate, and 16,384 output tokens/arm at $10/M, the conservative cap is
`(200,000 × $2.50 + 16,384 × $10) / 1,000,000 = $0.66384` per arm, $1.32768
total. Use $0.67 as the local cost ceiling per arm. Before any request, the
operator must open OpenAI Platform organization settings, select the exact API
project, open Limits, set Monthly spend limit to $1.40, and enable **Enforce a
hard limit**. Confirm that the enforcement toggle is on for that project, the
API key is scoped to it, and `gpt-6.1-sol` is allowed. A budget threshold alone
only alerts. Provider enforcement can lag and overshoot; the local request
ledger enforces the token and estimated-cost ceilings. See [OpenAI project spend
limits](https://help.openai.com/en/articles/9186755-managing-projects-in-the-api-platform).

## Procedure and validation

1. Freeze and hash the task, checker, prompts, settings, output limits, scoring
   sheet, and stop rules before any model output. An independent reviewer checks
   task ambiguity, checker correctness on hand-verified tiny cases, and likely
   contamination without seeing outputs.
2. Demonstrate offline that the exact production SIGMA request path and the
   baseline adapter reserve cumulative input, output, call, and cost before
   dispatch; unknown/in-flight calls retain their full reservation. Confirm
   over-limit cases are refused before transport invocation, no retries, and no model
   fallback. Verify exported provider usage and billing-mode attribution.
3. Run the two arms in randomized order within one 45-minute window. Save exact
   request bodies (excluding credentials), response bodies, provider usage,
   status, timestamps, all SIGMA steps/Outcome, and the baseline transcript.
   Hash and retain them before scoring. A `max_output_tokens` response is
   preserved with its exact partial text and usage, terminates the arm as
   **incomplete**, is not scored as incorrect, and is not retried. The runner
   fails closed on missing usage, unexpected model/configuration, or exceeded
   limits.
4. Independently check every schedule/objective claim against exhaustive
   enumeration. Score factual/correctness claims, evidence citations, errors,
   unsupported claims, and the baseline/Skeptic's substantive critique. For
   collaboration, identify an objection, whether it is valid, whether the next
   Investigator step engages with it, and whether the resulting research
   changes. Distinguish model self-report from transcript evidence.
5. Export the actual SIGMA project/session/Outcome and reports through SIGMA's
   export path under `docs/evaluations/increment_22/exports/`. Preserve the
   complete baseline record and checker outputs alongside it. Record actual
   calls, usage, spend, elapsed time, failures, and omissions. No synthetic
   response may be called live research.
6. Report correctness, substantive collaboration, evidence/provenance survival,
   costs, and time with the single-case limitation. No provider inference or
   spending occurs until the owner approves the exact provider, model, caps,
   and procedure below.

## Authorization gate and request

The live comparison is **not ready to execute** until the owner verifies the
provider-side hard spend limit and account/model availability. The local
cumulative input guard is implemented and has offline tests. The
existing per-session SIGMA cost setting is an estimated-cost reservation; it
does not by itself establish an invoice-level hard cap. No changes to Cloud
deployment are in scope.

**Authorization request (no calls made):** May I run one exploratory comparison using the OpenAI
API on `gpt-6.1-sol` at high reasoning / standard tier, API-key billing only,
with no tools, search, retries, fallback, or extended cache retention; up to
four calls per arm, 4,096 output tokens per call, 200,000 reserved input and
16,384 output tokens per arm, 15 minutes per arm / 45 minutes overall, and a
$0.67 local pre-dispatch cost ceiling per arm? Before any request, will the
operator set the exact API project's monthly spend limit to $1.40 and enable
**Enforce a hard limit** in its Limits settings? The conservative local upper
bound is $0.66384 per arm / $1.32768 combined; provider enforcement can lag and
slightly overshoot. I recommend 4,096 because output caps include hidden reasoning and
visible text, but no live run has established that this prevents clipping.
Clipped responses remain incomplete, are not scored incorrect, and are not
retried. The operator must verify that the correct project/key is selected, hard-limit
enforcement is on, the model is enabled, and the account is eligible; I will
make no request before explicit approval and that verification. Approval covers this one trial under only these stated limits.

## Offline review notes

- Increment 21 showed that the larger 36-pair design's task set, isolation,
  baseline adapter, cost enforcement, and scoring gates were not ready. This
  plan does not run that design or reuse its public benchmark tasks.
- The model and API mode are proposals based on current repository artifacts
  and official pricing, not evidence of account availability or authorization.
- The one-case custom scheduling task tests cumulative within-session
  challenge/revision and persisted SIGMA records. It does not establish a
  longitudinal cross-session benefit; that remains outside this increment.
- No engineering defect or product-quality conclusion is asserted here.
