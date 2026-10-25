# Issue 114: within-session adversarial collaboration evaluation

**Revision 2, prepared 2026-10-25 after external adversarial review.**
**State: proposed, not frozen, not executed, and not authorized for paid inference.**
**Claim status: no SIGMA advantage has been demonstrated.**

This protocol follows the merged [PR #116](https://github.com/bkramerext/sigma/pull/116) proposal. It tests **within-session multi-role adversarial review against single-role self-critique**, with no cross-session persistence. It does not test cumulative research, saved memory, or persistence. Those are a separate longitudinal design in [issue #119](https://github.com/bkramerext/sigma/issues/119); a result here must not be used to claim or refute persistent-research value.

## Evidence and current limitations

The earlier answer-bearing Maximum Regions run is not evidence of independent discovery. A later answer-free run retained neither exact dispatched inputs nor complete output: structured SIGMA fields hit 2,000/2,500-character limits despite a 4,000-token call ceiling. Its independence and completeness remain unverified. The earlier 12-pair proposal also treated evidence-present and evidence-withheld rows as if they were independent and proposed role-specific scoring dimensions. Neither problem is repaired by synthetic fixtures.

The six current tasks are short, synthetic and partly recognizable (including standard graph/matching material). They are not clean evidence of general research performance. Before any freeze, an external curator must decide whether these packets can support even a bounded pilot or replace them with new, unexposed tasks. If task/key provenance or contamination cannot be established, stop before live evaluation.

## Design and unit of analysis

Keep the six task families and both evidence variants only if the independent curator approves all six. Run **three preregistered stochastic repeats for each task × evidence variant**: 6 tasks × 2 variants × 3 repeats = **36 paired comparisons / 72 arm runs**. Every repeat is a fresh draw under the same pinned settings; execution order and per-pair A/B assignment are randomized using the frozen scheduling seed. Every arm starts with fresh state. No task, answer key, rubric, arm assignment or other-arm output enters model-visible context.

The six underlying tasks are the independent units (`n=6`). Evidence variants and repeated runs are observations clustered within task, not 36 independent tasks. For each scored endpoint, report all 36 paired differences, then average variant/repeat differences within each task and report all six task-cluster means, their mean, standard deviation, a two-sided 95% Student-t interval using 5 degrees of freedom, and an exact two-sided task-level sign-flip sensitivity. Show the six task effects and all adverse cases. The t interval assumes independent task clusters and an approximately meaningful t model for the six task effects; the interval and sign-flip result are exploratory and fragile at six clusters, not confirmatory power or broad generalization. Report repeat-to-repeat variation within each task; record an API sampling seed only if supported, and pair the same seed across arms. If a task cluster is invalidated, report the remaining analysis as incomplete; do not replace it after outcome inspection.

Three repeats improve the view of stochastic variability but do not increase the number of independent tasks. This revised design is materially better than the original 12-pair design for reliability assessment, while preserving the honest `n=6` limit. It is still a pilot, not a powered superiority study.

## Arms and shared budgets

Pin the same provider, exact model identifier/revision, API mode, sampling/reasoning settings, packet, tool policy, context/output caps, call cap, wall limit and dollar cap for both arms. Proposed full-study limits remain at most 4 calls, 48,000 input tokens, 16,000 output tokens, 64,000 total tokens, 1 local deterministic tool call, and 600 seconds per arm. Failed calls and retries count; the proposed protocol permits no automatic retry. Disable web and external retrieval for both arms. Freeze prompts before seeing any live output.

- **SIGMA:** two Investigator/Skeptic cycles, at most four calls, using the frozen production workflow. Capture exact requests/responses, provider usage, native schema-validation/truncation metadata and tool record.
- **Single-role comparison:** one persistent conversation, up to four calls, explicitly instructed to investigate, criticize its own claims, revise, and report remaining uncertainty. It sees only its own prior turns. It receives the same final artifact contract and all the same resource ceilings.

The single-role instruction must not be weakened to one-pass generation. The analysis does not reward SIGMA for having a named Skeptic: `objection_uptake` is removed as a score dimension. Scoring focuses on task outcome and reasoning validity, which both arms can achieve in the same final form.

## Fair output contract and normalization

Before freeze, both arms must produce one common JSON object with exactly these fields: `conclusion`, `reasoning`, `challenge`, `evidence`, `uncertainty`, and `next_test`. Limits are respectively **2,000 / 3,000 / 2,500 / 2,000 / 1,500 / 1,000 Unicode characters**, applied by the same deterministic normalizer. The final normalized artifact has identical keys and limits regardless of arm. Role/arm metadata and explicit references to “SIGMA”, “Investigator”, “Skeptic”, “baseline”, or “arm A/B” are removed by the normalizer. The baseline prompt and SIGMA final-response instructions must ask for these exact fields before freezing.

The upstream 2,000/2,500-character SIGMA schema limits are not ignored: the frozen packet must include a synthetic max-length probe showing every scored field survives request, provider response, parsing, save and normalization. Raw responses and truncation flags are retained. If the normalizer clips a field, it adds the same visible omission marker for either arm and the result remains in the analysis as submitted. If a SIGMA schema/parser truncates upstream, record the affected fields and score the incomplete submission; **never drop or selectively replace a pair after seeing it**. Any unexplained clipping is also a protocol failure and blocks a superiority conclusion.

The runner keeps a per-pair randomized A/B-to-workflow assignment map and execution order in evaluator-only storage, separate from scorer packets. Scorers see only a common-schema artifact, randomly generated anonymous ID, and the task packet needed for grading. They do not see arm labels, call counts, role logs, raw schemas, pair counterpart, cost, order or execution metadata. Randomize artifact order independently per scorer. After scoring, each scorer records their arm guess and confidence; report guess accuracy as a blinding diagnostic, without excluding guessed submissions. This structure reduces obvious cues but cannot guarantee linguistic indistinguishability; if scorers can infer arm above chance or from persistent language cues, report blinding failure.

## Scoring and conclusions

Two independent graders score each artifact separately, without arm labels or paired counterpart. Each dimension is 0–4 with task-specific anchors frozen before outputs:

| Dimension | Weight | Anchor |
|---|---:|---|
| Task outcome | 35% | Correctness/completeness of the task's answer, including justified abstention where the packet is insufficient |
| Reasoning validity | 30% | Key steps follow; assumptions and counterexamples are handled correctly |
| Calibration | 15% | Certainty matches what the supplied packet establishes |
| Evidence quality | 10% | Claims are tied accurately to supplied evidence or explicitly labeled as inference |
| Useful next test | 10% | A concrete, bounded test would distinguish remaining possibilities |

Do not award points for mentioning an objection, listing more steps, or matching SIGMA's output structure. Use the same task-specific hidden-key rubric for both arms. Also report **task-key pass rate** under a preregistered binary pass criterion as a co-primary descriptive endpoint, individual dimension scores and critical integrity failures separately. Critical failures are never averaged away. Preserve both grader scores; blinded adjudication resolves disagreements greater than one point on a dimension without erasing originals. Model-role agreement is not ground truth.

With six independent tasks, a positive result can only be a bounded signal worth testing on more unseen tasks if task-level effects are directionally consistent and integrity is not worse. The previous numeric `+0.40` threshold is not a power calculation and is removed as a decisive threshold. Any mixed, null, negative, underpowered, or invalid result is reported as **no demonstrated advantage / inconclusive**. Do not tune and rerun on the same tasks.

## Independent curator, keys, and grader separation

Before freeze, a human curator who did not author the task packets and is independent of the implementation and provider run must document:

1. task and answer-key authorship/provenance, including whether a model was used and its provider/family/version if known;
2. whether task text, keys, or close variants may have appeared in training or public material, with a recognizability/search review and concrete contamination concerns;
3. ambiguity, alternate valid answers, difficulty/ceiling effects, and whether each evidence variant changes only the intended evidence;
4. any replacements, made before freeze and before all scored output is visible.

Unknown provenance or credible exposure is recorded as unknown/high risk, not assumed clean. The curator signs/hashes the frozen task and key manifests and must not serve as either scorer. The answer key lives outside the runner, model filesystem/network and grader-facing artifact packet. Two graders independent of the task author, curator, implementation and provider run receive only the needed task packet and sealed reference after submissions are frozen; they remain blind to arm identity. A separate key custodian verifies access logs and post-run unsealing. If independent humans cannot be secured, the protocol remains unfrozen.

## Proposed minimal live shakedown (not authorized)

Use this throwaway task, excluded from the six-task scoring set and any later benchmark: **“A detector observed 24 alerts, of which 8 were false positives. It missed 4 of 20 independently confirmed incidents, so assume the other 16 incidents were alerted. Compute precision and recall, state exactly what this tiny synthetic sample does and does not establish, identify the strongest limitation, and propose one follow-up test. Return the shared six-field JSON. For the shakedown only, target 2,100 characters in `conclusion` and 2,600 in `challenge`; make the excess relevant explanation, not padding.”** Run one SIGMA Investigator/Skeptic cycle and one two-call single-role self-review, each in fresh state. This intentionally exercises the known 2,000/2,500-character boundaries; the shared normalizer clips both outputs to identical limits, adds the same omission marker, and preserves both as operational records. An offline synthetic boundary probe separately checks exact Unicode-character limits, persisted bytes, and native truncation-flag detection. No graders, answer-key scoring, benchmark result or persistence inference is part of this shakedown.

**Exact proposed runtime:** direct OpenAI API, Responses API, standard service tier, exact model identifier `gpt-6.1-sol`, same pinned settings for both arms, `store=false`; no ChatGPT-subscription auth, Azure/Bedrock, fallback model, web search, external tools or automatic retries. The final run must record the provider-returned model revision. If this exact model or standard tier is unavailable, stop and seek a new explicit approval rather than substitute.

Per arm, cap at 2 calls, 12,000 input tokens and 4,000 output tokens total (6,000 input / 2,000 output per call), with 300 seconds and $0.55. At the currently listed standard rates of $2/M input and $10/M output, the token-ceiling estimate is **$0.064 per arm / $0.128 for both**; the proposed hard aggregate cap is **$1.25**, including any unanticipated billable overhead. Rates were checked 2026-10-25 at the [OpenAI API pricing page](https://developers.openai.com/api/docs/pricing); recheck before approval. No tools are used, so no tool charge is expected. These figures are estimates, not authorization or a guarantee of actual billing.

Capture raw request/response bytes, usage and charge, model revision, parser/schema result, field lengths before and after normalization, every truncation indicator, and the normalized anonymous artifacts. Stop immediately on any model/revision mismatch, clipping or schema error not explained by the shared contract, missing usage/provenance, unexpected tool or retry, output-contract mismatch, key/context leak, 300-second arm limit, $0.55 per-arm cap risk, or $1.25 aggregate cap risk. Preserve partial records; do not retry or score them. This shakedown is only operational evidence. Owner authorization must name the provider/model, account, exact caps and purpose; this issue does not grant it.

## Offline harness and freeze gates

`scripts/increment14_protocol.py` creates a deterministic three-repeat draft with 36 pairs, randomized arm assignments and task-cluster metadata. The draft manifest itself contains the assignment map; no operational key custody or sealing is implemented. `scripts/increment14_blinding.py` normalizes both arms to a shared schema, records clipping and creates scorer-only packets without arm metadata. `scripts/increment14_audit.py` verifies the complete version-2 design against current task, packet, protocol, and scoring-schema hashes and fixed ceilings before it accepts run records; it then checks budgets, recorded arm-to-assignment consistency, each record's declared schedule position, two distinct scorer IDs and normalized output shape/digest, and computes six-task cluster summaries for both weighted quality and task-key pass rate. The position is only a record assertion until a live runner and trusted dispatch log exist. Synthetic boundary and tamper tests exercise these paths; they prove only local deterministic behavior.

Before a scored study can freeze: curator signoff and contamination assessment; sealed key custody; frozen prompts/schema/model; output-boundary shakedown; demonstrated allowlist isolation and scorer-only packet review; exact provider request/usage/cost capture; current price and enforceable spending cap; two independent graders; and separate explicit owner approval. As of this revision none of those live gates is complete, and no provider call or charge has occurred.
