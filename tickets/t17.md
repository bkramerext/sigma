# A17: Persistent Research Sessions (first vertical slice)

**Status:** Ready for implementation. **Priority:** Next after A16. **Purpose:** Move beyond strategy generation into research on an **existing, human-accepted strategy**.

## Goal

A user can start a research session for one saved strategy, leave the page, return later, inspect durable work and artifacts, and stop the session. The system performs **multiple genuine research iterations**, not another one-shot proposal or an animation of agents. This is a deliberately small first slice of long-running research, not a claim of autonomous theorem proving.

Do not add more sophistication to Generate Strategy. A16 supplies candidates; A17 begins investigation **after the human accepts a strategy**.

## User workflow

1. Open an existing project. In the dedicated **Research session** pane, choose a saved strategy to investigate. A strategy-row shortcut may preselect it, but is not the primary control.
2. Starting a session is an explicit user action. Display the selected strategy, model/billing mode, finite budget, and the fact that provider usage may accrue. No implicit model switch or billing fallback.
3. Start a persistent session. The user may navigate away, close the browser tab, and later return to the project. The session and its recorded results survive browser disconnection. The server, however, must remain running; no claim of execution while the SIGMA application is shut down.
4. Show session status (queued/running/paused/completed/stopped/failed), recent progress, and a readable list of **research artifacts**. Provide **Pause**, **Resume**, and **Stop**: Pause preserves the remaining budget and current question; Stop is terminal. Both prevent further calls and attempt to cancel in-flight local work. Report that an already-started provider request may still consume allowance.
5. Reopening the project shows the saved session and all committed artifacts, including after application restart. If a process exits during a call, mark the interrupted step honestly; never invent a completed response.

## Research loop (not Generate Strategy)

Start with **one saved strategy** and the authoritative problem statement. Use separate model invocations for at least two roles:

- **Investigator:** Advance the strategy by deriving a specific claim, lemma, calculation, counterexample candidate, or discriminating test. It must describe the mechanism and distinguish conjecture from demonstrated result.
- **Skeptic:** Independently examine the Investigator's public claim and its stated evidence. Identify a concrete objection, counterexample, missing obligation, or justified reason it can proceed. Do not treat its approval as verification.
- **Coordinator (Python):** Decide the next bounded action based on structured results: continue with a specific question, revisit a failed claim, or stop for lack of progress/budget. Decisions must be actual branches, not scripted labels. Persist the next-step context so iterations build on prior work rather than regenerating the same idea.

For the first slice, cap a session at **three investigation cycles** (one Investigator + one Skeptic call per cycle, at most six calls total). This is a *session* that continues independently of the browser, unlike A16's request-bound generation. Show calls used/remaining and a truthful completion reason. **Six calls is a request-count limit, not a monetary or token-spend guarantee**; do not display invented cost accounting. A later assignment may extend scheduling, duration, and tools.

Every completed cycle produces a **durable research artifact** containing at least: stable ID, project/session/strategy references, sequence/time, claim or question, method, assumptions, evidence status, concrete skeptical response, open obligations, and coordinator decision/next question. Save the full validated public role outputs as supporting evidence, not private reasoning. Persist each role attempt and outcome separately: a failed/interrupted call is an incomplete step, **not** a completed cycle or a research finding. Later cycles must refer to specific prior artifact IDs and unresolved obligations; keep context bounded without silently erasing relevant prior work.

**Important:** Without an actual computational or formal tool, the model has not *tested* a claim. Do not present model agreement as a proof, executed experiment, or verified result. In this slice, agent claims and critiques are explicitly *unverified research notes*. Avoid adding an evaluation rubric, proof certification, automatic strategy-stage promotion, or claims of mathematical validity.

## Persistence and lifecycle

- Keep project data local and authoritative. Reuse project identity, path safety, atomic-write patterns, source-revision checks, and A16.1 evidence conventions where practical. Do **not** store research-session records in A16 generation-run evidence or silently mutate saved strategies.
- Use a small local server-side session manager with a **single active research session** initially. Browser requests start/read/pause/resume/stop sessions; the worker must not be owned by the SSE/HTTP response lifecycle. Polling status is acceptable for this slice; no new realtime infrastructure required. Start and control requests must be **idempotent** under duplicate clicks, lost HTTP responses, and retries: clients can reconcile the authoritative session state without launching duplicate chargeable work.
- Persist each step before/after calls and each complete artifact before announcing it. Retain an ordered, bounded record of what the agent actually did, with restart-safe status. **Do not apply A16.1’s automatic pruning of generation-run evidence to research artifacts**; completed findings must not silently disappear. If storage reaches its limit, pause with a clear error instead of dropping artifacts. After process restart, do not silently resume and spend allowance: reconcile a formerly running session to interrupted/paused, preserve completed artifacts, and require explicit **Resume** with the remaining budget intact. SIGMA’s foreground `./sigma ui` launcher can terminate or replace the backend, so a session runs only while that backend is alive.
- A session is bound to the strategy snapshot (including its ID, text, and revision), problem snapshot, project identity, model, reasoning effort, and account/billing identity at start. Check those guards before every new provider call and on Resume; if inputs or identity change, pause with a clear explanation, never silently rebind. Do not persist credentials or access tokens; obtain current credentials through the existing connection layer and allow ordinary token refresh only for the same authorized identity.
- Enforce finite response/context size, per-call and session deadlines, concurrency gate, cancellation, and errors. Coordinate with existing generation/conversion requests so the first implementation cannot accidentally exceed its intended concurrent provider-work limit. Count attempted provider calls against the session cap, including calls interrupted after dispatch; never assume an interrupted request was free. Never store tokens, headers, raw provider envelopes, or hidden reasoning.
- On any network-bound UI error, show the existing error toast and recover to an accurate view. A failed or ambiguous request must trigger a read of authoritative session state before offering a retry; never imply work was started, paused, stopped, or saved when it was not.

## Project workspace UX: three vertical panes

The project workspace should have **three top-level sections in this order**:

1. **Project** (collapsible): the existing project problem, description, Markdown view/editing, and settings. Preserve the existing content and its resizable behavior when expanded; do not rebuild the editor.
2. **Research session #N** (primary work surface): a separate project-level pane **between Project and Strategies**, with live execution status, controls, recent activity, and research artifacts. It is not nested inside an individual strategy row. The pane remains visible and usable when Project and Strategies are collapsed.
3. **Strategies** (collapsible): the existing strategy pool, creation/generation, expansion, ordering, stages, and actions. Preserve all behavior when expanded. A session references its chosen strategy by name and ID, with a **View strategy** action that expands Strategies and focuses that row.

**High-level collapse:** Give Project and Strategies independent, accessible top-level disclosure headers. These are distinct from existing nested strategy details and the separate `Project details & history` disclosure. Keep each header, title, and relevant concise count/summary visible when collapsed. Research session remains expanded by default and is the center of attention during work. Do not use collapsing as a substitute for saving: keep drafts, focus, and unsaved edits safe; if unmounting would lose them, retain the component or prevent destructive collapse. Preserve keyboard access, heading hierarchy, sidebar anchor navigation, focus restoration, and mobile layout. The Project header is separate from the global application/header navigation. Avoid nesting interactive controls inside a disclosure `summary` element.

### Research session pane: first-pass controls

- **No session yet:** Show `Research session` with a compact strategy selector listing saved, eligible strategies and a primary **Start investigation** button. No eligible strategies? Explain that the user must first create/accept one and provide a link to expand Strategies. Do not bury the entry point in strategy-row menus.
- **Session exists:** Title the pane **Research session #N**, numbering sessions monotonically **within the project** (stable across restarts; no reuse). Show the selected strategy title, current status, model/thinking/billing mode, call budget used/remaining, and the **current agent action** (Investigator, Skeptic, or Coordinator). The session number is not the cycle number. The active or most recent session opens by default; a minimal session picker/list allows inspecting earlier sessions without confusing them with the running session. **Defer previous/next arrow navigation**: it may become useful once sessions accumulate, but do not add arrows or a carousel in A17 without evidence that the simpler history selector is insufficient.
- **Running:** **Pause** and **Stop** controls; avoid offering duplicate Start/Resume. **Paused/interrupted:** **Resume** and **Stop**. **Completed/stopped/failed:** read-only results plus **New session** (with strategy selection); never relabel an old session as running. Confirm Stop as terminal, but do not require confirmation for Pause. Disable controls while the request is pending and reconcile authoritative state after ambiguous responses.
- **Live status:** Show `Cycle X of 3`, `Y of 6 calls used`, last activity timestamp, current role/action, and a short chronological list of **actual persisted events**. Use modest polling while the pane is visible and the backend is reachable; refresh immediately after user actions and when returning to the tab/project. No simulated progress percentages or invented time-to-completion. An accessible status announcement should fire on meaningful transitions, not on every poll. A disconnected/unknown state must not be presented as running with certainty; show last confirmed state and retry/reconnect.
- **Research artifacts:** Show each completed cycle as a selectable/collapsible artifact entry, with claim, evidence status, Skeptic's objection, open obligations, and coordinator next question. Keep full validated outputs accessible, without forcing the user into raw JSON or overwhelming the live pane. Show an incomplete/interrupted step distinctly from a completed artifact. All artifacts remain readable after a session ends or the application restarts.

**Usability criterion:** In one glance, a user can answer **what is being investigated, whether it is running, what it is doing now, how much of the finite budget remains, and what it has produced**. The next action (Pause, Resume, Stop, or New session) must be unambiguous. Do not add cost dashboards, multiple simultaneous agent cards, separate agent-chat windows, complex timelines, or a global research dashboard in A17.

## Verification

- Deterministic offline mocked-provider test: three distinct cycles with dependent context; verify calls, role isolation, real coordinator branching, six-call ceiling, durable ordered artifacts, and no mutation of strategy text/stage.
- Pause and Stop during an in-flight step; verify truthful partial record, released gate, no additional calls, and ability to inspect the record. Resume a paused session with the remaining call budget; a stopped session must not resume.
- Browser disconnect and page navigation do not cancel server-side work; closing/reopening the project restores status and artifacts.
- Simulate backend shutdown/replacement and process restart during a step: reconcile interrupted state, preserve committed artifacts, and require explicit resume; verify no automatic chargeable call. Include duplicate/lost-response start and control requests to prove no duplicate sessions or model calls.
- Test malformed/refused output, timeout, provider failure, account/model/project change, concurrent start, and persistence failure. No fictitious artifacts and no implicit billing fallback.
- Real browser check of the three-pane hierarchy, independent Project/Strategies collapses, preserved unsaved editor state, start from the session pane, accurate live status/polling, artifact inspection, Pause/Resume/Stop, session numbering and history, stop/reopen, failure toast/reconciliation, and accessible controls. No paid model calls in automated tests.
- Run `./sigma test`, frontend typecheck/build, and relevant browser checks. Record actual results and limitations in `docs/STATUS.md`.

## Out of scope

Unbounded unattended operation, cloud deployment, tool-using code execution, web browsing, external literature retrieval, formal proof verification, scoring/ranking strategies, automatic acceptance/rejection, multi-strategy scheduling, and elaborate agent frameworks. Those can follow once the persistent research loop and artifact lifecycle are demonstrably real.

**Delivery:** Commit implementation directly to `main` without a PR; report commit SHA, tests actually run, and remaining limitations.
