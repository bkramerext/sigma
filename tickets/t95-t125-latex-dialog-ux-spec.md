# Academic paper using LaTeX: dialog UX and recovery contract

Status: **Owner-requested revision; manual UI acceptance pending**  
Owner: Green | Branch: `green/t95-t125-ui` | Related UI work: T95/T125 / PR #135  
Scope: The paper generation dialog, not a rewrite of the LaTeX authoring engine.

## Decision and rationale

The current dialog exposes engineering implementation details as user-facing controls, including evidence batches, reduction groups, section counters, hundreds of possible calls, megabyte caps, and a generic "Discard progress and restart" action. The owner could not understand what the checkpoint meant or what would be lost. This fails acceptance. User-facing controls must communicate intent and consequence, not internal pipeline states.

**Do not add an Advanced options section or secondary configuration panel to move these internals out of sight. Remove them from the ordinary workflow.** Do not retain the "Use expanded multi-section authoring for a more detailed paper" checkbox: a complete, well-structured paper is the default goal, and SIGMA should choose the necessary processing strategy automatically within preexisting hard safeguards. A future genuine user-level product choice (e.g. short versus full paper) would require separate rationale and owner approval, not this ticket.

Preserve durable checkpoint and reduction machinery behind the interface if it protects data, supports recovery, or prevents duplicate/billable calls. This request changes **presentation and safely exposed actions**, not persistence guarantees, spending authorization, evidence completeness, or provider controls.

## User-facing content and layout

Title: **Academic paper using LaTeX**.

Use two short explanatory paragraphs at most:
1. "Create a LaTeX paper from this project's saved research, including supporting evidence, unsuccessful approaches, contradictions, and unanswered questions."
2. "The paper is AI-generated and has not been independently verified. Generation uses your selected provider and may consume allowance or incur charges. It does not start a research session."

Display the **actual selected model** in concise secondary text. Do not display fixed example model text. Avoid promises such as complete verification or exhaustive inclusion if the system cannot prove them. Link to deeper technical documentation only if an existing conventional link fits without new UI clutter.

Do not place detailed pipeline bounds, maximum file sizes, timeout seconds, response caps, token limits, total calls, or reduction counts in the default dialog. Internal policies still apply and should be enforced server-side. If a hard budget/authorization condition requires a user action, explain that exact actionable condition at the point it occurs, not a wall of limits on initial display.

Keep a simple creation area followed by **Saved versions**. Preserve current copper/dark visual language, hierarchy, keyboard accessibility, focus behavior, mobile/desktop constraints, and existing version identity. Do not create a new modal or expand into a multistep wizard.

## States and actions

### 1. Idle, no resumable work

Show one primary action: **Generate paper** (when no saved version exists) or **Generate new version** (when versions exist). New generation must not overwrite or discard saved versions. No progress counters or restart action in the idle state. Disable or deduplicate rapid repeated activation so that only one job is created.

### 2. Active generation

Show **Generating paper…** with a truthful short status *if the backend can provide it*, such as "Preparing research evidence", "Writing paper", "Compiling PDF", or "Saving version". If a reliable stage is unavailable, use a generic indeterminate status. Never invent a percentage, time estimate, or remaining-call count.

Prevent conflicting actions and duplicate jobs. Do not imply that closing the dialog or navigating away cancels provider work unless that is actually true. If a Cancel/Stop action exists, explain the actual backend behavior and that already-dispatched calls may still consume allowance or incur charges; preserve safe state. Keep completed versions accessible if it is safe to do so.

### 3. Interrupted and **provably resumable**

Only offer **Resume generation** if there is a durable checkpoint with an explicitly supported safe continuation path. Explain: "Paper generation was interrupted. Completed work was saved. Resume from the saved point or start over."

Offer secondary **Start over…** / **Discard unfinished work…** only in this state, not continuously. Require confirmation specifying exactly what draft/checkpoint data are discarded, whether any provider calls may be repeated, and that *completed saved versions will be kept*. If the implementation cannot make that guarantee, stop and escalate the semantic gap rather than inventing one.

If a dispatched provider request has unknown completion or billing status, show that uncertainty and advise inspecting provider usage before initiating potentially additional calls. Do not automatically retry that request. Do not call a full restart "resume".

### 4. Interrupted but **not safely resumable**, or failed

Do not show Resume or claim a checkpoint is usable. Show a short error and known cause where reliable. Offer **Try again** / **Start new generation**, with warning that provider work may repeat and incur additional charges. Preserve completed saved versions. Do not promise refunds or free retries.

### 5. Successfully completed

Show success only after the saved version is durably recorded. TeX generation and PDF compilation are distinct: if TeX exists and PDF compilation fails, identify that partial success; allow valid TeX access, but do not display broken Download/Open PDF actions.

## Saved versions

List each with title, version number, timestamp, and only actually available actions: **Download TeX**, **Download PDF**, **Open PDF**. Existing expandable details may remain where meaningful. A destructive **Remove** must target the selected completed version and make the consequence clear; it must not be conflated with discarding unfinished generation. No auto-removal of old versions on new generation, resume, or restart.

## Engineering and data-integrity invariants

- The paper must be based on the persisted evidence snapshot and represent unsuccessful approaches, objections, uncertainty, and missing proof obligations faithfully. Formatting or authoring is not mathematical verification.
- Preserve historical completed papers, project isolation, auditability, provenance, evidence pointers and server-side call/cost/response limits.
- UI state must derive from authoritative backend job state, not synthesized counters or optimistic local assumptions.
- Across refresh, navigation, server restart and possible provider interruption, test exactly what persists, and do not promise recovery paths that the backend cannot actually execute.
- No new provider calls for automated UI/Chrome tests; fixtures must distinguish simulated from real work.
- Any current server implementation that exposes no reliable resume capability should use the *unrecoverable* UI state. Report the backend gap separately rather than adding an inert Resume button.
- Do not alter T95/T125 functionality or broaden this into an Outcome or papers library redesign.
- Avoid ambiguous language such as "checkpoint", "reduction group", "calls left", "progress discarded", "expanded multi-section authoring" in ordinary UI.
- Do not implement a hidden "Advanced options" drawer containing those same controls.

## Acceptance matrix

1. **Idle with no saved papers:** one primary Generate action; no checkpoint/count/advanced controls.
2. **Idle with existing versions:** Generate new version preserves prior papers and their links.
3. **Active:** only truthful activity message; repeated clicks cannot create duplicate provider jobs; sensible behavior on navigation.
4. **Recoverable interruption:** only when backend actually supports durable resume; Resume and confirmed Start over have correct effects without replaying uncertain calls silently.
5. **Nonrecoverable failure:** clear safe retry and billing caveat; no fake Resume; old versions persist.
6. **Successful TeX but failed PDF:** TeX available, unavailable PDF actions hidden/disabled with explanation.
7. **Save/list/delete:** no cross-version or cross-project damage; Remove scoped correctly.
8. **Integrity:** explicit AI/not independently verified caution remains visible, no evidence or provenance lost.
9. **Layout/accessibility:** actual Chrome at desktop and narrow mobile (including 390px and 320px), accessible button names, tab/focus, no clipped actions; no new panel.
10. **Regression:** focused backend tests for semantics, browser fixture tests for UI states, full `env -u SIGMA_CLOUD_BOOTSTRAP_ADMIN_EMAIL ./sigma test` when integration is complete. No paid provider calls.

## Handoff requirements

Before implementation, inspect the current actual backend job/checkpoint semantics. Summarize to coordinator:
- Does a paper job continue after closing dialog/browser?
- Does the backend support safe restart/resume after browser refresh, backend restart, and uncertain dispatched provider calls?
- What exactly does "Discard progress and restart" remove today, and what does it preserve?
- Is the expanded multi-section checkbox merely implementation mode, or a materially different output/cost product choice?

Then implement the smallest safe UI change consistent with verified semantics. **Ask coordinator before inventing a new user-visible behavior or changing backend guarantees.** Report any gap as open rather than weakening acceptance. Commit on the named branch, push, update PR/handoff with a concise before/after behavior explanation and real-Chrome tests. No self-merge. Manual owner signoff is required for this UI.
