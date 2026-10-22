# A16.1: Preserve agentic generation evidence

**Status:** Ready for Codex. **Priority:** Complete before A16 real-model quality trials. **Scope:** Capture and inspect evidence from strategy-generation runs, not A17's general research-artifact/provenance system.

## Why

The current `src/sigma/agentic.py` workflow emits a useful public progress stream, but `activity.completed` events omit the complete structured Explorer and revision candidates. Critic events expose selected review fields, not the full validated review. A terminal event contains only the accepted draft, or a brief failure/stop summary. Intermediate and rejected work is lost after the run. We therefore cannot independently judge whether a Critic found a substantive defect, whether revision actually addressed it, or whether the coordinator made a defensible decision.

## Deliverable

Create a **durable, bounded, human-inspectable evidence record for each A16 generation run**, including runs that stop, fail, time out, or are cancelled. Keep the existing public progress protocol and explicit human Save semantics intact.

1. **Capture validated public outputs, not private reasoning.** Record each complete, schema-validated Explorer `Candidate`, Critic `Review`, and revised `Candidate`, in execution order. Include coordinator decisions, effective assessment (including local overlap overrides), explicit reason for overrides, attempt/revision/call indexes, and terminal disposition. Never infer missing steps or present a proposed solution as verified. Record a step that started but did not complete as such, without fabricating its output.
2. **Reconstruct context and identity.** Include a stable run ID, timestamp(s), project ID and a nonsecret digest/version of the problem and existing strategy corpus used, starting-point text or an explicitly documented safe reference to it, role, selected model/thinking effort, provider mode, prompt/instruction version or digest, structured-output schema version, and final draft when one exists. Do not store authentication identity, tokens, request headers, raw provider envelopes, or private chain-of-thought. Capture enough *public input data* to distinguish trials without depending on later mutations of the project.
3. **Persist independently of strategy acceptance.** Evidence is an artifact of the attempted run, **not** a saved strategy. An unsaved or rejected proposal still has a run record. Use the project's existing safe local storage conventions, atomic writes, bounded sizes and safe filenames; do not change `project.json` schema merely to store run traces. Ensure records survive application restart and are associated with the correct project copy. No cross-project contamination. Keep sample source directories immutable.
4. **Make it inspectable.** Provide a simple supported way to list/open/export a run as a readable, structured JSON artifact (CLI or API plus minimal UI link, whichever fits the current architecture). The record must preserve exact validated text and step ordering, not just a condensed summary. A human reviewer should be able to compare the initial candidate, critique, revision, and final decision without consulting live logs.
5. **Safe lifecycle.** Capture ordinary completion, retry, revision, no-proposal stop, provider error, timeout, cancellation and client disconnect. Make the final state explicit even when work terminates early. Failed storage must not corrupt project data or accidentally save a strategy; surface an actionable error, with a request-error toast for network-bound UI failures and a recoverable interface. Do not claim a trace was saved unless it was persisted.
6. **Security and bounds.** Restrict read/write access to the project and existing local trust model; validate paths, bound record size and total retention, and avoid sensitive connection data. If retaining the starting point or problem text, clearly treat it as user-provided investigation data and do not log it to unrelated telemetry. No hidden reasoning or speculative model internals.

## Tests and acceptance

- **Offline deterministic tests:** Script distinct/present, critique-driven revision, overlap/retry, two-attempt stop, malformed/refused provider response, timeout, cancellation, disconnect, concurrent request, and storage failure. Assert exact role-output round-trip, ordered call/decision history, correct terminal state, safe handling of incomplete steps, and no saved strategy unless the human explicitly saves. Verify persistence after restart and immutable Sample sources.
- **Inspectability:** From one stored record alone, a reviewer can identify the original candidate, each specific objection, the revision (if any), the coordinator's decision, and the evidence boundary. Show that the record retains rejected attempts, not just the final candidate.
- **Compatibility:** Existing A15 one-shot generation, A16 public progress events, account/model guards, cancellation, receipt verification, and explicit Save behavior must continue to work. Do not silently change the strategy schema or introduce a general evaluation rubric.
- **Verification:** Run `./sigma test`, relevant browser tests and frontend build/typecheck. Report executed commands, actual results, limitations, and sample record locations in `docs/STATUS.md`. Automated tests must use fixtures; do not incur model charges without explicit authorization.

## Quality-trial handoff (after this assignment)

Use **Operation Narrow Passage** as the primary qualitative case and **Counting Constrained Binary Strings** as the secondary mathematical case. Preserve a single-request A15 baseline and A16 multi-agent runs in comparable, labeled artifacts. Examine: concrete solution vs. investigation plan; substantive independent critique; targeted revision; defensible present/retry/stop decision; and whether claims exceed evidence. Compare quality rather than merely counting calls or observing a successful terminal state. A16.1 enables this review; it does **not** itself establish that multi-agent generation improves outcomes.

**Out of scope:** A17's general research journal/DAG, agent memory, automatic rubric generation, feasibility scoring, autonomous experiments, artwork, or UI redesign.

**Delivery:** Commit to `main` without a PR; report commit SHA, tests actually executed, and any gaps.
