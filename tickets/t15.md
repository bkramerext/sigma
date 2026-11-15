# A15: Make basic Generate Strategy work

**Status:** Implemented and verified. **Scope:** Single-request Generate Strategy, **not** the multi-agent research workflow.

**Assignment history:** A14 described and may already have implemented agentic behavior. The heavier Explore → Challenge → Decide orchestration and its detailed requirements are assigned to **A16** (`docs/assignments/asn16.md`). This A15 focuses on the minimal functional user-facing Generate Strategy path. **Do not delete or regress working agentic code** to enforce a single-call design; isolate or bypass it only if needed to make the basic path reliable. The original A15 text-representations specification is preserved in `docs/assignments/asn15-text-representations-original.md`. A14.2 separately covers Markdown conversion.

## Objective

Make **New Strategy → Generate with AI** work end to end for a real investigation using the **simplest existing supported generation path**: one bounded LLM generation request, validated response, editable **unsaved** draft, and explicit Save. Fix actual integration failures rather than expanding agent orchestration.

Read the current implementation, existing tests, `docs/STATUS.md`, and `docs/HUMAN-AI-INTERACTION.md`. Identify the first broken step in the actual UI → API → model → draft → save path before modifying code. Reuse current auth, request, receipt and persistence services. Do not introduce a second competing generation framework.

## Required behavior

1. From an investigation with **zero or more strategies**, the existing **Generate with AI** action opens its existing dialog and accepts an optional user starting point. An empty starting point is valid.
2. Send the authoritative current research problem, relevant existing strategy context, selected model and thinking effort through the **current connected account and billing mode**. Keep untrusted investigation text as data. Reject oversized context clearly rather than silently truncating important strategy history.
3. Generate **one** proposed strategy with a concrete mechanism, title, summary, approach, assumptions/obligations and plausible initial tests/failure modes as supported by the existing draft schema. Ask the model to avoid duplicating previous strategies, but **do not claim independent adversarial review** in A15.
4. Validate provider completion, structured output, source/account/model binding, response bounds and receipt/provenance. Handle both API-key and ChatGPT-plan response contracts without silently switching billing mode or model. No automatic retries or unbounded loops.
5. Display a truthful pending indicator while the request runs; show the result in the existing **editable unsaved** strategy draft. Nothing is added to the investigation until the user explicitly selects **Save strategy**. Closing/cancelling/rejecting preserves existing strategies and research.
6. Save through the existing guarded service, then reopen and confirm the strategy persists with its identity, event history and attribution. Preserve the user's typed draft on save errors and recover focus/UI state appropriately.
7. On provider rejection, malformed output, timeout, network failure, cancellation, changed account/model, concurrent run or incomplete response, preserve source and strategy pool; restore a usable dialog with an explicit retry path. Use the existing **single dismissible error toast** and appropriate inline state. Do not show an empty draft or claim success on failure.

## Acceptance test

Use `samples/counting-constrained-binary-strings/project.json` without changing the canonical fixture.

- Open a managed copy and confirm it starts with **zero strategies**.
- Choose Generate with AI with **no starting point**. Verify one actual bounded generation request yields an editable **unsaved** candidate with a substantive mathematical approach.
- Cancel or reject and confirm the pool remains empty.
- Generate again, explicitly Save, reopen and verify **exactly one** strategy persists with correct metadata.
- Generate with an existing strategy present, verify prior context is supplied and the output does not simply copy the existing title/approach. This is a prompt/quality check, **not** A16's independent mechanism-review guarantee.
- Simulate provider failure and cancellation; verify unchanged research, one error toast, usable recovery and no saved draft.

## Verification and delivery

Add deterministic **no-paid-call** backend/API and browser tests for successful generation, empty optional seed, existing strategy context, invalid/missing output, provider rejection including HTTP 200 error envelopes, cancellation, timeout, account/model changes, conflict and explicit save/reopen. Verify any progress shown is truthful; **multi-stage agent progress is not required by A15**.

Run `./sigma test`, frontend build/typecheck and relevant browser tests. Record commands and results in `docs/STATUS.md`; don't claim a live provider run unless actually executed. Keep changes focused; preserve approved artwork, Home, text representations, and unrelated migration work.

**Commit and push directly to `main`**, no pull request. Report commit SHA, root causes, tests actually run and remaining limitations.

## Explicitly deferred to A16

Independent Explorer/Critic calls; Python critique-driven coordinator; multi-attempt revision/retry; mechanism-aware independent overlap assessment; multi-stage typed progress ledger; no-viable-proposal decision from a bounded agentic search. These are **not A15 acceptance criteria**.

**Definition of done:** Generate Strategy reliably produces a single-model, reviewable, editable draft and persists it **only** after explicit user acceptance, with safe failure/cancellation behavior.
