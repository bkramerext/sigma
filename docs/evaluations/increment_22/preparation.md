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
call, token, wall-clock, and dollar limits. The baseline sees only its own
transcript. The evaluator sees both complete transcripts and checks them against
the frozen checker after both runs. Preserve negative results and every failed
or clipped call.

## Proposed execution limits (not yet authorized)

- Provider and billing: OpenAI API, explicitly selected API-key billing; no
  ChatGPT-subscription fallback.
- Model/configuration: exact model `gpt-6.1-sol`, `reasoning_effort=high`,
  standard service tier; same for both arms. No web, tools, delegation, retries,
  or fallback model.
- Calls: at most four provider calls per arm (eight total); SIGMA uses two
  Investigator/Skeptic cycles. Baseline uses four sequential self-review turns.
- Output: at most 1,024 generated tokens per call (4,096 per arm).
- Input/total: proposed ceiling 12,000 input and 16,096 total usage tokens per
  arm (32,192 total across the comparison). The current SIGMA setting derives a
  much larger `total_token_limit` from context bytes and does not expose this
  useful cumulative input ceiling as a start-session setting. A trial-only
  pre-dispatch guard must enforce the shared cumulative usage ceiling before
  each next request; if it cannot reliably do so, do not run.
- Wall time: 15 minutes per arm, with a 45-minute overall trial window. Stop
  at the limit; do not retry failed calls.
- Estimated-cost reserve: at most $0.55 per arm / $1.10 total, with a proposed
  $1.25 absolute comparison ceiling including any unavoidable provider-side
  accounting difference. This is not a provider-invoice hard cap: SIGMA's
  local limit reserves against published token prices and recorded usage.
  Require an isolated provider project/key budget or another enforceable
  provider-side hard limit before execution; if unavailable, do not run.

At the official OpenAI standard rates checked 2026-10-25, `gpt-6.1-sol` is
$2/M input and $10/M output tokens (cached input and cache writes differ).
The proposed uncached token maxima imply $0.0644 per arm before other billable
items. These are estimates, not authorization or a substitute for a hard spend
control. Recheck the official rate and the exact provider model at approval:
[OpenAI API pricing](https://developers.openai.com/api/docs/pricing).

## Procedure and validation

1. Freeze and hash the task, checker, prompts, settings, output limits, scoring
   sheet, and stop rules before any model output. An independent reviewer checks
   task ambiguity, checker correctness on hand-verified tiny cases, and likely
   contamination without seeing outputs.
2. Demonstrate offline that the exact production SIGMA request path and the
   baseline adapter stop before dispatch when the shared input, output, call,
   time, or cost budget would be exceeded. Confirm no retries and no model
   fallback. Verify exported provider usage and billing-mode attribution.
3. Run the two arms in randomized order within one 45-minute window. Save exact
   request bodies (excluding credentials), response bodies, provider usage,
   status, timestamps, all SIGMA steps/Outcome, and the baseline transcript.
   Hash and retain them before scoring. The trial runner must fail closed on
   missing usage, unexpected model/configuration, clipping, or exceeded limits;
   preserve partial data and stop rather than retry.
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

The live comparison is **not ready to execute** until the cumulative input
budget guard and a provider-side hard spend limit are demonstrated. The
existing per-session SIGMA cost setting is an estimated-cost reservation; it
does not by itself establish an invoice-level hard cap. No changes to Cloud
deployment are in scope.

**Approval requested:** May I run one exploratory comparison using the OpenAI
API on `gpt-6.1-sol` at high reasoning / standard tier, API-key billing only,
with no tools, search, retries, or fallback; up to four calls per arm, 1,024
output tokens per call, 12,000 input / 16,096 total usage tokens per arm,
15 minutes per arm / 45 minutes overall, $0.55 estimated-cost reserve per arm
and $1.25 absolute total spend ceiling? I will start only after demonstrating
the cumulative token guard, confirming the provider-side hard spend limit, and
freezing the task/checker/procedure. If you approve, that approval covers this
single trial under these limits only.

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
