# A14: Agentic Generate Strategy prototype

**Status:** Historical agentic design reference. The basic functional Generate Strategy work is now **A15**; the heavier independent Explore → Challenge → Decide agentic scope is **A16**. Preserve any existing implementation; this document is not an additional active assignment.

## Goal

Turn the existing **Generate with AI** action under **New Strategy** into a genuinely **agentic strategy-generation workflow**. SIGMA should independently develop a mathematically (or otherwise domain-) motivated idea, subject it to substantive criticism, decide what to do with the criticism, and present a **human-reviewable, editable, unsaved strategy**. The important outcome is a defensible, **appreciably distinct** approach, not an impressive performance of multiple agents or a stream of invented activity.

The prior single-request Generate Strategy flow and its connected-account, model/thinking and explicit-acceptance contracts are the starting point. **Do not build a new AI scenario/project creation flow:** A12 concerns a separate AI-generated scenario feature. A14 lives entirely inside the existing project Strategy generation entry point.

Read `docs/HUMAN-AI-INTERACTION.md`, `docs/agent-output-design.md`, `docs/READINGS.md`, and the current proposal/connection code before implementation. Keep scope modest enough to land and validate a real vertical slice.

## Research quality: the gates that matter

1. **Substance and mechanism.** The proposal must identify a concrete mechanism plausibly connecting its approach to the project's research objective. It must state the relevant assumptions, what needs proof/verification, useful initial tests, and ways the approach might fail. A fascinating observation, tautological re-expression, or stylish analogy is not enough.
2. **Appreciable difference from the project's prior strategies.** Compare each candidate against **all** strategies (active, abandoned/removed, and otherwise recorded), including **underlying approaches and mathematical mechanisms**, not merely titles or terminology. Renaming a known technique, adjusting a parameter or applying the same necessary condition in different wording is not new. A candidate closely related to an existing strategy must make the substantive difference explicit; otherwise revise/try another route. No need to assert novelty in published literature.
3. **Adversarial challenge.** A fresh, separately invoked skeptical reviewer should check the candidate against the actual problem, prior strategies, mathematical proof obligations, counterexamples and likely failure modes. It should not simply cheerlead. The proponent should not be allowed to declare its own idea sound without independent review.
4. **Judgment, not forced success.** The coordinator should make a reasoned decision to **accept for human review, revise, try an alternative, or stop without a viable proposal**, bounded by the run budget. Failure to find a distinct substantive idea is a legitimate result; never fabricate novelty or certainty to fill the form.
5. **Evidence levels.** Distinguish established facts, proposed derivations, numerical/finite checks, hypotheses, and unresolved obligations. No claims of proof or research execution without actual verification. No need to reproduce our prior Riemann Hypothesis ideas; inherit only the discipline of developing genuinely justified ideas and critically rejecting weak ones.

## Agentic execution: initial architecture

Use a small **bounded coordinator**, not an open-ended swarm and not one model request with a decorative progress sequence.

- **Explore:** one role-isolated model invocation develops a concrete candidate based on project problem, mode, user's optional starting point, and the complete existing-strategy corpus.
- **Challenge:** a separate, fresh model invocation critiques the candidate and evaluates mechanism overlap with existing strategies. Give it the candidate, original objective, and relevant strategy corpus; do not reuse a hidden chain-of-thought transcript. Its result should contain explicit public objections, missing obligations, and a supported **distinct / overlapping / unconvincing** assessment.
- **Decide / refine:** coordinator interprets the critique and either returns a sufficiently justified proposal, requests a targeted revision, requests a genuinely different candidate, or ends with no acceptable candidate. Real branching based on reviewer findings is necessary for the word `agentic` to mean something here.
- Role isolation can initially use separate calls to the **same project-selected model and thinking setting**. Do not imply different vendors/models if that is not what ran. Keep agent roles visible as roles, not fake named personas.
- Set explicit ceilings, initially **no more than 6 AI model calls per user-triggered run and no more than 2 distinct candidate attempts**, with a finite overall deadline and bounded per-call deadlines. No indefinite internal loops, concurrency explosion, implicit model downgrade, silent account/billing switch, or automatic HTTP retries. Expose the approximate call cap before the user starts; report failures/limits clearly.
- Reuse the existing OpenAI account/auth integration and selected project `ai_model`/`reasoning_effort`, identity/billing-mode binding, model availability checks, sanitization, bounded context/response, and cancellation guards from `src/sigma/proposals.py`. Do not leak raw model reasoning, credential material, unfiltered provider errors or private chain-of-thought.
- Give the reviewer all relevant strategy approaches, including removed ones. Fail transparently if the required project context exceeds the bounded size; **do not silently omit previously tried strategies** to squeeze the prompt.
- Never execute user-supplied instructions embedded in strategy text as system/controller instructions. Project content and seed are data.
- The process may reason about tests; it does **not** claim it ran a Python experiment, literature search, proof assistant or external tool unless an actual, bounded, auditable tool was explicitly implemented and executed. Tool orchestration beyond this slice is out of scope.
- Preserve project/source data while generating. Nothing is persisted as a strategy until the human explicitly clicks **Save strategy**. Reuse the existing editable form, signed acceptance receipt and provenance, adapting the receipt if necessary to attribute the coordinator's actual model/settings honestly. Do not let a reviewer verdict silently become a verified research claim.

## Progress experience (approved direction; exercise restrained visual judgment)

Keep **Generate with AI** as the existing New Strategy split-button choice, and the same modal/dialog. During a run, display a refined **deep-navy / burnished-copper** activity surface within that dialog, visually consistent with the project's approved copper controls. Do not touch Home, project-header, or other raster artwork.

- Show the actual current activity and a short **ordered ledger of completed activity** such as `Exploring a direction`, `Challenging assumptions and overlap`, `Revising after critique`, `Reviewing the result`. Because the coordinator can branch, **do not hardcode a fictitious linear three-step sequence or mark stages complete before they are**.
- The backend must emit **typed, sequential, truthful progress events** describing stages actually started/completed and public, concise outcomes (e.g. `Candidate proposed`, `Reviewer found mechanism overlap`, `Trying a different approach`). A bounded streaming response (e.g. one fetch-driven SSE stream) is reasonable; implement and test actual transport, disconnection and cancellation. No simulated timers, client-invented percentages, fabricated token streams or pretend intermediate results.
- A subtle **indeterminate copper filament** or soft activity glow is preferable to a percentage bar, since individual model-call durations are not predictable. The ledger remains readable when motion is disabled via `prefers-reduced-motion`. Screen readers get concise live updates without repeated chatter.
- One clear current action, completed steps, and meaningful `Cancel request` and failure/limit states. Cancelling must interrupt/abort local work and release the single-run gate; explicitly acknowledge that provider billing/computation cannot always be undone. Avoid duplicate submit and preserve the typed starting point.
- Don't expose hidden reasoning. Public generated candidate summaries and reviewer critiques may be displayed as explicit authored summaries, carefully distinguished from verified research or tools performed.
- When a viable proposal completes, transition to the **existing editable draft** with title, summary and approach/first tests/assumptions/failure modes. Retain the possibility to regenerate through a fresh explicit run. The user decides whether to save.

### Example event shape (illustrative; may adjust names while keeping typed contracts)

```text
run.started {run_id, model, thinking, max_calls}
activity.started {step_id, kind:"explore", attempt:1}
activity.completed {step_id, kind:"explore", public_summary:"Candidate prepared"}
activity.started {step_id, kind:"challenge", attempt:1}
activity.completed {step_id, kind:"challenge", public_summary:"Reviewer found ..."}
decision {outcome:"revise"|"retry"|"present"|"stop", public_summary:"..."}
...
run.completed {draft, receipt, provenance, public_review_summary}
```

Events must be ordered, schema-validated and escaped as plain content in the UI. A complete outcome must not be shown before it is generated. Handle stream failures and bad/missing terminal events as failures, not as implicit success.

## A14 happy-path sample project (committed fixture)

**The required no-strategies testing project is already checked in at**
`samples/counting-constrained-binary-strings/project.json`.

- **Title:** Counting Constrained Binary Strings
- **Research mode:** Mathematical
- **Research problem:** For each integer `n >= 0`, count binary strings of length `n` with no adjacent `1`s, including the empty string when `n = 0`; derive and justify a general formula or recurrence, its initial conditions, and small cases. No method is prescribed.
- **Initial state:** Exactly **zero strategies**, `strategies: []`, `active_order: []`, and one `project.initialized` event. **Do not pre-populate a recurrence or a proposed strategy.**
- The sample catalog discovers this project automatically alongside the existing examples. Use its current, stable **open sample project** behavior: first use installs one managed project, later uses reopen the same project and retain human-accepted edits. The canonical source JSON must remain byte-for-byte unchanged. Do not put sample projects into Recent Projects simply because they were discovered/opened.
- **First happy-path run:** Open this sample project in SIGMA. Verify there are zero strategy rows. Choose **Generate with AI** without a starting point. The application should visibly progress through real explore/challenge/decision events and present an editable, unsaved strategy with a substantive mathematical mechanism. Cancel/reject leaves the pool at zero; saving explicitly creates exactly one persistent strategy with correct attribution and history.
- **Second run / difference check:** With one strategy saved, generate again. The coordinator/reviewer must compare the new idea to the saved strategy; don't merely reword the same counting recurrence. Possible different mechanisms include combinatorial position selection or generating functions, but **do not hardcode or bias the generator to produce either**. Show/reject overlapping attempts based on substance rather than literal text.
- Correctness oracle (for independent tests only; not fed to the agent as a chosen method): counts at `n=0,1,2,5,10` are `1,2,3,13,144`. A candidate's concrete tests should not contradict these values. Explanatory derivations still require proof obligations; numerical agreement alone is not a proof.
- Validate the committed fixture with SIGMA's real project parser and sample catalog. Add explicit scenario/browser tests for sample enumeration, zero strategies before generation, an unsaved agentic draft, explicit human acceptance, post-save re-open, subsequent novelty challenge and immutable source.

## Verification and acceptance

- Add controlled mock-transport/fixture tests with **no paid API calls** that exercise actual coordinator branches: acceptable distinct proposal; rejected duplicate with retry; skeptical revision; exhausted attempts with no proposal; malformed/refused output; timeout; cancellation mid-stage; disconnected browser; identity or account binding change; max-call budget; invalid progress event; duplicate request gate and clean release.
- Test both ChatGPT-plan and API-key modes insofar as their existing transport adapters permit; do not silently change billing modes or bypass plan-stream handling.
- Add real browser tests for the modal start, progress state, chronological event ledger, cancellation, reduced motion, final editable draft, Save, and untouched projects when a run is abandoned.
- Cover zero and nonzero existing-strategy sets; failed attempts should not corrupt strategy state or overwrite human edits.
- Keep CLI/API/browser interfaces consistent through shared services, and update scenario/test coverage and relevant documentation. A CLI may expose a minimal explicit run command if needed to keep surfaces aligned; do not invent background scheduling.
- Execute `./sigma test`, frontend build, and relevant browser checks; record actual results and limitations in `docs/STATUS.md`. No unverified live-model success claims.
- Preserve existing visual assets **exactly**. No new Home/project art, no unrelated UI redesign, and no work on A12.

## Definition of done

SIGMA can take the shipped empty-pool mathematical test project, conduct a **real bounded multi-call exploration with an independent skeptical review and conditional decision**, show truthful progress, and present a justified proposed strategy **only after** the human decides to accept it. A later generation from the same project must meaningfully account for earlier approaches instead of returning a cosmetic duplicate. Both success and legitimate no-viable-strategy outcomes are supported and tested.
