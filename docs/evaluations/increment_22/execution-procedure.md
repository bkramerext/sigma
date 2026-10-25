# Increment 22 execution procedure (frozen before any model output)

This is one exploratory paired case, not a benchmark. These steps are not
authorization to execute. Do not call the provider until the owner approves the
exact request in `preparation.md` and verifies the provider project limit.

## Freeze and isolate

1. Verify each SHA-256 in `evidence/frozen-manifest.sha256`; if any listed
   artifact changes, stop and prepare a newly reviewed freeze before outputs.
2. Create an empty independent SIGMA project using the exact task text and one
   manually saved strategy describing a systematic search over eligible
   machine assignments/orders. Use 2 rounds, 4 calls, 15 minutes, 4,096 output
   tokens/call, 200,000 cumulative input tokens, and $0.67 maximum estimated
   cost. Confirm API-key billing, `gpt-6.1-sol`, high reasoning, standard tier,
   and local tool images. The production Investigator/Skeptic cycle is the
   SIGMA arm. Do not create synthetic provider output or seed history.
3. Give the baseline a fresh single persistent conversation. Its only system
   and task instructions are `prompts/baseline-system.txt`,
   `prompts/baseline-turns.json`, `task.json`, and its own prior turn/computation
   output. Use the identical provider, model, reasoning effort, service tier,
   output limit and arm limits. Return strict JSON and save exact bodies and
   responses with authorization headers removed.

## Compare and preserve

4. Toss and record a fair coin for arm order. Run each arm sequentially. Start a
   monotonic 15-minute timer per arm and 45-minute timer for the pair. Do not
   send a request unless the arm's persisted ledger has reserved call count,
   request input upper bound, maximum output, and maximum applicable cost.
   SIGMA's request ledger is persisted in its session. The baseline invokes
   `sigma.increment22_baseline.dispatch_turn`, which reserves before invoking
   its transport and settles only against provider-reported usage; its persisted
   ledger is saved alongside the transcript. After a response, settle only
   against provider-reported usage.
   Unknown/in-flight outcome or missing usage retains the full reservation and
   blocks another call. Never retry or switch models.
5. A provider response marked `incomplete` for `max_output_tokens` is retained
   byte-for-byte with usage, request hash and reservation, sets that arm to
   incomplete, and terminates its calls. It is not incorrectness evidence, is
   not scored against the checker and is not retried. Preserve transport errors
   and all other negative results too.
6. Export the actual SIGMA project/session and Outcome through SIGMA's normal
   export path. Save the exact baseline transcript, request/response records,
   computation sources/results/status/hashes, both ledger records, timestamps,
   elapsed monotonic times and provider billing dashboard evidence under
   `exports/`. Do not edit, summarize over, or omit the raw records.
7. Only after both records are sealed, an independent assessor scores each
   against `checker.py` and `scoring.md`. Preserve arm order, objections,
   replies, revisions, unsupported claims, evidence links and missing evidence.
   Report the two arms side by side; no superiority inference or post-output
   exclusion is permitted.

## Offline demonstration status

`tests/increment22_budget.py` exercises the common pre-dispatch ledger used by
both arms and the baseline's actual `dispatch_turn` boundary: per-arm
call/output/input/cost refusal; cumulative reservations; settlement;
input/cost over-limit refusal before any transport is called; unknown and
in-flight full holds; and the frozen four-call cost upper bound.
`tests/research_sessions.py` additionally exercises the actual production
SIGMA session request path and inspects saved reservation IDs, request bytes,
input bounds and settled ledger entries. The provider path is replaced by a
deterministic HTTP fixture in those tests; these fixtures are guard tests, not
research outputs. No provider request or spend is authorized by this document.

The baseline adapter has not been executed against a provider or validated
against an active account. Its in-process safety logic must use the shared
budget ledger and retain exact request/response data. Missing local/provider
configuration, the owner's provider project limit, or any cap mismatch is a
stop condition.
