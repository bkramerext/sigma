# A17: Persistent Research Sessions (first vertical slice)

**Status:** Ready for implementation. **Priority:** Next after A16. **Purpose:** Move beyond strategy generation into research on an **existing, human-accepted strategy**.

## Goal

A user can start a research session for one saved strategy, leave the page, return later, inspect durable work and artifacts, and stop the session. The system performs **multiple genuine research iterations**, not another one-shot proposal or an animation of agents. This is a deliberately small first slice of long-running research, not a claim of autonomous theorem proving.

Do not add more sophistication to Generate Strategy. A16 supplies candidates; A17 begins investigation **after the human accepts a strategy**.

## User workflow

1. Open an existing project and expand a saved strategy. Show **Investigate** (or **Start investigation**) for that strategy.
2. Starting a session is an explicit user action. Display the selected strategy, model/billing mode, finite budget, and the fact that provider usage may accrue. No implicit model switch or billing fallback.
3. Start a persistent session. The user may navigate away, close the browser tab, and later return to the project. The session and its recorded results survive browser disconnection. The server, however, must remain running; no claim of execution while the SIGMA application is shut down.
4. Show session status (queued/running/paused/completed/stopped/failed), recent progress, and a readable list of **research artifacts**. Provide **Stop**; stopping prevents additional model calls and cancels in-flight local work when possible. Report that an already-started provider request may still consume allowance.
5. Reopening the project shows the saved session and all committed artifacts, including after application restart. If a process exits during a call, mark the interrupted step honestly; never invent a completed response.

## Research loop (not Generate Strategy)

Start with **one saved strategy** and the authoritative problem statement. Use separate model invocations for at least two roles:

- **Investigator:** Advance the strategy by deriving a specific claim, lemma, calculation, counterexample candidate, or discriminating test. It must describe the mechanism and distinguish conjecture from demonstrated result.
- **Skeptic:** Independently examine the Investigator's public claim and its stated evidence. Identify a concrete objection, counterexample, missing obligation, or justified reason it can proceed. Do not treat its approval as verification.
- **Coordinator (Python):** Decide the next bounded action based on structured results: continue with a specific question, revisit a failed claim, or stop for lack of progress/budget. Decisions must be actual branches, not scripted labels. Persist the next-step context so iterations build on prior work rather than regenerating the same idea.

For the first slice, cap a session at **three investigation cycles** (one Investigator + one Skeptic call per cycle, at most six calls total). This is a *session* that continues independently of the browser, unlike A16's request-bound generation. Provide an explicit finite budget and truthful completion reason. A later assignment may extend scheduling, duration, and tools.

Every cycle produces a **durable research artifact** containing at least: stable ID, project/session/strategy references, sequence/time, claim or question, method, assumptions, evidence status, concrete skeptical response, open obligations, and coordinator decision/next question. Save the full validated public role outputs as supporting evidence, not private reasoning. Failed/interrupted calls are recorded as incomplete, not as research findings.

**Important:** Without an actual computational or formal tool, the model has not *tested* a claim. Do not present model agreement as a proof, executed experiment, or verified result. In this slice, agent claims and critiques are explicitly *unverified research notes*. Avoid adding an evaluation rubric, proof certification, automatic strategy-stage promotion, or claims of mathematical validity.

## Persistence and lifecycle

- Keep project data local and authoritative. Reuse project identity, path safety, atomic-write patterns, source-revision checks, and A16.1 evidence conventions where practical. Do **not** store research-session records in A16 generation-run evidence or silently mutate saved strategies.
- Use a small local server-side session manager with a **single active research session** initially. Browser requests start/read/stop sessions; the worker must not be owned by the SSE/HTTP response lifecycle. Polling status is acceptable for this slice; no new realtime infrastructure required.
- Persist each step before/after calls and each complete artifact before announcing it. Retain a bounded, ordered record of what the agent actually did, with restart-safe status. After process restart, do not silently resume and spend allowance: show an interrupted/paused session requiring explicit **Resume**, with remaining budget intact.
- A session is bound to the strategy snapshot, project identity, model, reasoning effort, account/billing mode, and strategy text at start. If relevant inputs or identity change, pause or stop with a clear explanation; never silently rebind.
- Enforce finite response/context size, per-call and session deadlines, concurrency gate, cancellation, and errors. Never store tokens, headers, raw provider envelopes, or hidden reasoning.
- On any network-bound UI error, show the existing error toast and recover to an accurate view. A failed request must not leave the UI implying work was started, stopped, or saved when it was not.

## Minimal UI

Stay within the current Project screen and its visual language. One small session control/status surface and a list of artifacts are sufficient. Each artifact should expose the specific claim, Skeptic's objections, evidence status, and next step; no new dashboard, diagram, complex timeline, or unrelated Home redesign. Existing strategy creation and acceptance must remain unchanged.

## Verification

- Deterministic offline mocked-provider test: three distinct cycles with dependent context; verify calls, role isolation, real coordinator branching, six-call ceiling, durable ordered artifacts, and no mutation of strategy text/stage.
- Stop during an in-flight step; verify truthful partial record, released gate, no additional calls, and ability to inspect the record.
- Browser disconnect and page navigation do not cancel server-side work; closing/reopening the project restores status and artifacts.
- Simulate process restart during a step: record interrupted state and require explicit resume; verify no automatic chargeable call.
- Test malformed/refused output, timeout, provider failure, account/model/project change, concurrent start, and persistence failure. No fictitious artifacts and no implicit billing fallback.
- Real browser check of start, status, artifact inspection, stop/reopen, failure toast and recovery, and accessible controls. No paid model calls in automated tests.
- Run `./sigma test`, frontend typecheck/build, and relevant browser checks. Record actual results and limitations in `docs/STATUS.md`.

## Out of scope

Unbounded unattended operation, cloud deployment, tool-using code execution, web browsing, external literature retrieval, formal proof verification, scoring/ranking strategies, automatic acceptance/rejection, multi-strategy scheduling, and elaborate agent frameworks. Those can follow once the persistent research loop and artifact lifecycle are demonstrably real.

**Delivery:** Commit implementation directly to `main` without a PR; report commit SHA, tests actually run, and remaining limitations.
