# Increment 14 arm contract (pre-freeze candidate)

**Purpose:** Make the comparison operational without altering SIGMA's production prompts or research engine. This contract is not evidence that either arm wins and must be frozen before seeing live outputs.

## Shared user task packet

Every arm receives exactly the allowlisted JSON fields produced by `scripts/increment14_agent_packet.py`: `instruction`, `question`, `evidence`. No rubric, evaluator reference, scoring dimensions, prior arm outputs, arm assignment, or execution order may enter model-visible context. Tool permissions and underlying data are identical per task. Where an arm cannot support an identical tool, disable the tool for both or invalidate the pair.

## SIGMA arm

Use the unmodified production Investigator/Skeptic prompts and session implementation at the pinned experiment commit. Do not inject task-specific counterexamples, hints, outcomes, or scoring criteria. Count every Investigator and Skeptic model call, including retries, toward the **aggregate** task budget. Retain complete immutable input/output and tool transcripts with provider usage and elapsed time.

## Strong single-role baseline

The baseline performs deliberate investigation, substantive internal criticism, and revision, not a single-pass answer. All stages use the **same model and total aggregate caps** as SIGMA. A proposed neutral instruction (subject to independent pre-output review):

> Work as a careful researcher. First develop the most defensible answer the evidence supports, including alternative explanations and constraints. Then deliberately challenge your own central claims: search for counterexamples, unsupported steps, missing sources, and decisive objections. Revise the answer to address those objections, clearly distinguish established results from conjecture and report uncertainty. If available evidence cannot settle an issue, identify one bounded discriminating next test. Never claim to have run tools or consulted sources you did not actually use.

The baseline may split its token allocation across multiple calls to preserve an independent self-critique stage. Do not force wasted calls if it has completed a satisfactory response. The baseline cannot see SIGMA's intermediate work; SIGMA cannot see baseline work. Prompt tuning from observed benchmark answers is prohibited.

## Hard comparison controls

- Exact provider/model/version, model settings, allowed tool APIs, starting evidence, and aggregate model calls/tokens/wall-time/spending ceilings are frozen identically.
- The same allowance is not a claim of identical *realized* spend or latency; retain both and report efficiency.
- Model-specific hidden reasoning use must be measured when the provider exposes it; otherwise flag inability to verify this aspect of equal resource use.
- A model call rejected for budget overrun is recorded as a failure, not silently retried.
- Blinded final scoring is separated from arm-internal traces; machine audit may retain arm labels under evaluator-inaccessible access control.
- A valid pilot requires a separate runner integrity demonstration that evaluator files and other arm transcripts are unavailable to either arm. The agent-packet allowlist **alone** does not demonstrate this.

## Pre-output adversarial checklist

Independent reviewers must check: whether the baseline prompt is strong enough; whether SIGMA receives model-visible hidden state beyond task allowance; whether multi-call accounting includes retries and failed requests; whether exact model settings match; whether the task packets are identical; whether grader blinding is enforced; and whether any tool can retrieve evaluation keys.

The experiment remains **not frozen, not authorized for paid calls**. A positive result on six short synthetic tasks can at most motivate larger unseen replication and longitudinal evaluation, not settle multi-agent value.
