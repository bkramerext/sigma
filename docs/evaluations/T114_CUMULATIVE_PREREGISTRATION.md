# T114 cumulative research comparison — preregistration draft

**Revision 1 · 2026-10-26 · DRAFT, NOT FROZEN · NO PROVIDER CALLS AUTHORIZED**

This is the active design for issue #114. It addresses cumulative research
across strategies and saved sessions. The earlier [within-session proposal](T114_MATCHED_BUDGET_PREREGISTRATION.md)
and the single-case T146 comparison are historical evidence/designs; neither
tests cross-session cumulative value. No SIGMA superiority claim follows from
this preregistration or from engineering checks.

## Question and estimand

On unfamiliar, curator-approved research problems, does the production SIGMA
workflow that carries evidence and objections across strategies and at least
two saved sessions produce a better final research result than one persistent
single-role researcher given the same task, model, tools, context access and
total provider budget, with equal time and call ceilings? The single-role arm
may self-criticize, revise, and use its entire budget; it is not a one-response
baseline. This is an exploratory comparison of these workflows on this frozen
task set, not a general claim about multi-agent systems.

## Task selection, blinding, and leakage controls

Use 12 independently curated problem packets across at least six research
domains, two problems per domain. A curator who did not implement SIGMA or
write this protocol must author or select them from material unavailable to
the implementers and provider runner. Each packet must require evidence-based
reasoning, have a checkable outcome or explicit uncertainty rubric, and offer
at least one plausible falsification or error-correction opportunity. Include
different difficulty levels, set before any run. Exclude stock SIGMA samples,
public benchmark tasks already present in this repository, and task families
used in T146. The curator records provenance, dates, prior publication or
training exposure risk, near-duplicate search, ambiguity, difficulty, and
retain/replace reasons before freezing. Unknown exposure remains a stated risk.

Keep task text and answer keys in evaluator-only storage. The implementation,
runner, and both arms receive only the common task packet and source corpus.
Commit only per-task SHA-256 commitments and opaque IDs before the experiment;
do not publish packet text or keys until all outputs are frozen. The custodian
publishes the reveal and hashes after scoring. Select all 12 tasks before any
output; do not replace a task after unblinding. If a pre-run curator review
finds contamination, replace it before freeze and regenerate every hash.

Randomize pair order, arm labels, and which arm runs first within each pair
from a recorded seed after task selection. Reset each arm to a fresh project
state for each problem. Do not share state or outputs between arms. SIGMA's
within-arm state carries across four preselected strategy passes and at least
two persisted research sessions; all four passes are planned even if SIGMA
would ordinarily stop early, unless a preregistered safety/budget stop fires.
The baseline is one continuing conversation with its own transcript and may
allocate its four work passes as it judges useful. Both arms see the same
source packet and their own complete history. Store randomized identity keys
outside both model and scorer workspaces.

Two independent graders receive the same final artifact contract, task
packet, and sealed rubric, with anonymous IDs and randomized order. They do
not see arm, role, call, cost, timing, order, intermediate transcript, or pair
counterpart. They independently score first; preserve both score sets and
resolve disagreements over one rubric point with a blind adjudicator. After
scoring, each grader records an arm guess and confidence as a blinding check.
Do not exclude correctly guessed or imperfectly blinded outputs; disclose the
diagnostic.

## Matched arms and resource limits

Before freeze, pin the exact provider, model revision, API mode, reasoning and
sampling settings, and output schema. Both arms use that same model and
settings, identical source packets, retrieval policy, local Python/Sage
availability, tool limits, context window, output contract, and overall
budgets. Disable web search and network retrieval for both; any supplied
corpus is identical and hashed. Both arms get up to four work passes and
eight provider calls, up to 4,096 output tokens per call, 60,000 cumulative
input tokens and 32,768 cumulative output tokens, 900 seconds per arm, and
the same local compute/time ceiling. The single-role arm may use multi-turn
self-review, and the output ceiling allows substantially more than one short
answer. SIGMA may distribute calls across Investigator/Skeptic roles and
sessions but may not exceed these same aggregate limits.

**Authorization sheet — proposed maximums, not permission to run:**

| Limit | Per arm | Whole study (12 pairs / 24 arms) |
|---|---:|---:|
| Provider calls | 8 | 192 |
| Input tokens | 60,000 | 1,440,000 |
| Output tokens, including reasoning | 32,768 | 786,432 |
| Wall time | 900 seconds | 6 hours total arm time |
| Estimated API cost ceiling | $0.65 | $15.60 |

Planning estimate uses current listed GPT-6.1 Sol Standard 12-hour cache-write
rate ($5/M input) and output rate ($10/M output):
`60,000 × $5/M + 32,768 × $10/M = $0.62768 per arm`, rounded to a $0.65
local hard cap and $15.60 study cap. Price source checked 2026-10-26: [official
API pricing](https://developers.openai.com/api/docs/pricing). Recheck exact
model availability, service tier, cached-token/write treatment, regional
uplifts, and all applicable prices before any authorization. If the model or
rates change, stop and seek approval for a revised sheet. Provider-side spend
limits can lag; require both a local pre-dispatch reservation ledger and an
operator-verified provider project limit. No automatic retries, fallback
model, delegation, unpriced tools, or charges beyond these caps. Every failed,
ambiguous, or clipped call counts against its reservation.

**Stop immediately** before additional dispatch if a call, input/output token,
cost, elapsed-time, or tool ceiling would be exceeded; provider usage or model
identity is missing/mismatched; an outcome is uncertain; a request/response is
clipped or schema-incomplete; shared task access differs; cross-arm or answer
leakage occurs; the runner cannot prove isolation; the budget guard or provider
limit is not enforceable; or any implementation/prompt/task/rubric changes
after freeze. Preserve partial requests, responses, failures, ledgers, and
timestamps. Do not retry, discard, replace, or score a failed pair as a
completed result. Report all 12 pairs and all stop cases.

## Frozen output and scoring plan

Both arms return the same final fields: `answer_or_conclusion`,
`supported_reasoning`, `evidence_and_citations`, `checks_and_errors_found`,
`uncertainty_and_verification_status`, `novel_contribution_if_assessable`,
and `next_test`. Apply one deterministic normalizer and identical character
limits after capturing raw outputs; record all clipping and parser failures.
Scorers see final normalized outputs only. Keep full unnormalized transcripts
and operational records in restricted evidence storage.

Score each dimension 0–4 with task-specific anchors written and hashed before
outputs. Report dimensions separately; do not collapse costs into a quality
score:

| Dimension | Weight | What earns credit |
|---|---:|---|
| Correctness and verification status | 30% | Correct answer at the warranted confidence level; distinguishes proof, verified computation, conjecture, and unresolved work |
| Evidentiary support | 20% | Important claims trace to accurate supplied sources/data or are explicitly marked as inference |
| Reasoning quality | 15% | Valid steps, assumptions exposed, task constraints respected |
| Error detection and correction | 15% | Finds material errors and makes a justified correction; count resolved and unresolved material errors separately |
| Novelty, where assessable | 10% | Specific nontrivial insight absent from supplied references and confirmed by a blinded post-run literature/source search; mark N/A when not assessable |
| Calibration and uncertainty | 10% | Confidence, caveats, and stopping claims match what the packet establishes |

Also record unsupported material claims as a count and severity (minor,
material, critical), task-key pass/fail, independent checker results, final
artifact completeness, calls/tokens/cost, wall time, compute/tool use, and
failure/clipping status. Cost and time are efficiency outcomes reported beside
quality, not reasons to prefer an incorrect result. Two blinded graders score
all submissions. Independent subject-matter verification checks mathematical,
computational, and empirical claims against sealed references or executable
checkers where feasible. Shared-model correlated failure remains a design
limitation; same-model role agreement is not independent verification.

## Analysis and decision rule

The independent unit is the problem (`n=12`); each problem contributes one
paired SIGMA-minus-baseline difference per primary rubric dimension. Report
all 12 differences, mean and median, a paired randomization interval/test, and
the full task/domain breakdown. No dropping, replacement, post-hoc subgroup,
or repeated scoring until favorable. Treat this small study as a screening
signal only; disclose low power and domain limits. A positive signal requires
the correctness/support composite to favor SIGMA, no increase in critical
unsupported claims or failed integrity cases, and directionally consistent
effects across domains. Any null, mixed, negative, underpowered, or invalid
result is **no demonstrated advantage / inconclusive**. Do not tune to these
tasks or rerun them as a new scored sample.

## Reproducible preparation and freeze gates

`scripts/t114_cumulative_dry_run.py` creates a deterministic blinded schedule
from opaque task IDs and commitment hashes, validates aggregate budgets and
retains synthetic complete/failed records without invoking a model. It does
not generate benchmark tasks, establish key custody, prove process
isolation, or constitute research evidence. Existing Increment 14/15 audit
tests remain useful for paired-record integrity, normalization, token
accounting, and adverse mutation rejection; their public six-task benchmark is
not eligible for this comparison. Run the exact commands in its module docstring
and `./sigma test` before freeze.

Freeze is prohibited until an independent curator and key custodian sign the
task/rubric commitments; exact prompts, model, baseline and SIGMA adapters,
normalizer, checker, randomization and analysis are hashed; local and
provider-side budget enforcement is demonstrated; the scorer packets and
model-visible isolation are independently reviewed; and two independent
graders are secured. Then obtain Brian's separate explicit authorization for
the exact provider/model and caps in the authorization sheet. This ticket does
not authorize any live or paid provider call. Until every gate passes the
status is **NOT FROZEN / NOT READY TO RUN**.

## Evidence inventory and limits

- T146 preserved one live, authorized, same-model paired comparison on one
  newly authored scheduling problem. Both arms found the exact optimum, but
  SIGMA's Skeptic added no substantive correction and the baseline regressed
  after an invalid self-critique. It used one SIGMA session, one strategy,
  four baseline turns, and one SIGMA cycle. This is a descriptive within-session
  case, not evidence about cumulative cross-strategy/cross-session benefit.
- T114 Increment 14/15 scripts, Increment 21 readiness audit, and offline
  dry-runs validate parts of the protocol and accounting with synthetic data;
  they are not model comparisons.
- Increment 6/7 archived sessions and T17.8 live observations are historical
  single-arm or answer-exposed/incomplete records; do not treat them as matched
  comparisons. Scripted provider fixtures test application behavior only.
- The 36-pair public Increment 14 task set has recognizable/public answers and
  is excluded from the unfamiliar-task study.
- No unfamiliar-task cumulative experiment has been frozen or run. No general
  research superiority is established.

## Bounded maintainability assessment

On current base `58b360e`, `src/sigma/research_sessions.py` is 8,666 lines
(verified with `wc -l`). It combines request schemas, limits and persistence,
Outcome projections/metrics, intervention APIs, provider dispatch/accounting,
context selection, cross-strategy portfolio decisions, peer handoffs,
computation orchestration, and longitudinal memory indexing. The strongest
coupling hotspots are `_agent_context`, `_portfolio_decision`,
`_portfolio_role_call`, `_worker`, and the persistence/public projection
functions; they exchange large mutable session dictionaries. Focused unit
functions and extensive `tests/research_sessions.py` coverage are a strength,
but shared locks, fixture/global worker state, and async lifecycle paths make
module moves regression-prone. No top-level import cycle was found among
`research_sessions`, projects, budget, and execution; `python_sandbox` does
have a lazy runtime back-edge that imports `_read` from `research_sessions`
inside a helper. The implementation depends on project, budget, AI, and
execution services. No wholesale refactor is recommended for this assignment.

If separately prioritized, extract in this order with unchanged public APIs and
focused tests: (1) stable request schemas and truncation helpers; (2) pure
Outcome/metrics projections; (3) token/cost accounting adapters (shared typed
budget service already exists); (4) persistence snapshot/locking; then (5)
portfolio selection/handoff logic behind explicit typed inputs. Move one seam
per change, preserve serialized records, and run focused session, budget,
computation, and full-suite checks after each. Do not refactor as part of the
scored experiment.
