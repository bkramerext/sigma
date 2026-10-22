# SIGMA journal

High-level milestones, recorded by day.

## Day 0 — October 20, 2026

- Ideation and initial research model.
- Technology stack selection.
- Basic project skeleton and first working UI.
- Human–AI collaboration workflow.
- Documentation and project conventions.
- Brainstorming future capabilities.

### Learning to collaborate: direction, execution, and trust

The day's most instructive work was not a feature. It was the effort to learn how to work together: how a human conveys intent, how an AI exercises independent judgment, and how an approved idea survives the journey from conversation to implementation.

The human enthusiastically approved SIGMA's original cinematic Home artwork. That should have closed the design exploration. Instead, the AI continued to reinterpret the design, generated a split-screen interface concept that degraded the original artwork, and then conflated approval of the interface layout with approval of the regenerated image. The human repeatedly said to lock in the chosen direction. The AI acknowledged this but failed to preserve it operationally.

The handoff exposed a second failure: the image packaged as the Home background was actually the split-screen mockup. The resulting application first showed no artwork because the runtime asset was missing, then showed the mockup *behind* the live UI. The AI initially diagnosed from assumptions rather than inspecting image contents. Eventually the correct original PNG was identified, repackaged, installed, and the human confirmed the Home page looked right. The final screenshot, not the commit or the explanation, established that milestone.

This revealed a distinction between **agreeing with a decision** and **maintaining it as an invariant**. Approval must be carried into filenames, asset provenance, code, instructions to coding agents, and end-to-end checks. Similarly, “implemented,” “committed,” “served,” and “visually verified” are different states and must never be collapsed into a claim of completion.

We established **“facepalm”** as an escalation signal: a serious assistant error demands immediate evidence-based diagnosis, correction, and verification, not further reassurance or speculative discussion. We also recognized that the human is not a perfect navigator. Feedback can be ambiguous, impulsive, inconsistent, or misleading. The AI must not simply follow the latest steering input; it must independently maintain the established objective, detect contradictions and drift, and challenge them constructively. That responsibility does not authorize unilateral changes to the repository.

The collaboration principle emerging from this experience is **independent judgment in service of durable direction**: explore freely while decisions are open; treat enthusiastic validation as a strong signal that exploration has ended; preserve approved artifacts exactly through execution; verify at each handoff; and own recovery when reality diverges from intent. The goal is not merely to communicate better, but to **land things together** without requiring the human to repeatedly reassert settled decisions or debug preventable mistakes.

The Home artwork is now visually confirmed. The project workspace and cinematic entrance remain separate implementation work; the latter is on hold.

## Still Day 0 — October 20, 2026

- Persistent research workspace and editable project settings.
- Strategy management, history, and human-reviewed AI proposals.
- Recent projects and sample mathematical investigation.
- ChatGPT sign-in and one-time welcome experience.
- A8.2.1 connection-status refresh assignment.
- Exploring independent agents that challenge one another.

### From prototype to working research workspace

The initial sketch has become a working local research application. SIGMA now has a persistent project workspace, editable project settings, human-authored strategies, and a deliberately human-controlled AI proposal flow. The Home page also gained recent projects and an installed sample research problem with three contrasting strategies. The application and its CLI, tests, and documentation have evolved together through versioned assignments handed from Chat to Codex.

A particularly satisfying milestone was **A8.2: Sign in with ChatGPT**. The human tried the implemented connection and reported that it worked smoothly, especially appreciating the one-time welcome toast. This made the collaboration feel tangible: a design discussed with Chat, specified in GitHub, implemented by Codex, and then experienced as a polished working interaction rather than merely a completed checklist.

Normal use also exposed a small but instructive defect: after about a minute, the AI status changed to **“AI connection check expired”**, although the ChatGPT authorization had not necessarily expired. Code inspection traced this to a 60-second connection-health cache and a browser timer that marked the display stale without refreshing it. We wrote **A8.2.1** for Codex to refresh health quietly while the app is visible, preserve truthful failure states, and avoid interrupting the user. **The assignment is committed; the fix is not yet implemented.**

The emerging lesson is that removing friction is part of correctness. A technically defensible cache timeout should not become a recurring chore for the person doing research. The human should be spending attention on mathematical questions, not on authentication status housekeeping.

We also considered adding Claude as another provider, and a longer-term idea surfaced: **independent agents using different models to challenge each other's reasoning**. That remains a future research-engine possibility, not current implementation scope. For now, the priority is to build on the working ChatGPT connection and turn SIGMA into a useful engine for mathematical investigation.

## Day 1 — October 21, 2026

**Theme: hardening the research workspace before the multi-agent push.**

Day 1 was not a single feature launch. It was the accumulation of product decisions, UI refinements, integration repairs, and many small but consequential bug fixes needed to make SIGMA dependable. We spent considerable time removing friction from ordinary use: creating investigations, opening stock problems, editing mathematical text, connecting AI, generating a strategy, and restarting the development application. The application became more coherent, but the more important result was a clearer separation between a polished demonstration and a trustworthy research system.

The **Monday, October 26 delivery target** is now explicit. The next major step is multi-agent mathematical investigation, followed by cloud migration, documentation, stock investigations, integration testing, and the Onebrief demonstration. This entry records what was completed or diagnosed on Day 1; it does **not** report the research engine as finished.

### A real workspace, not just a screen

- Consolidated the Home page into a compact **Projects** heading with **New** and **Open**, plus a Recent-first Stock/Recent catalog. Reworked the layout repeatedly across wide, laptop, and narrow viewports so the slogan, project list, and copper artwork no longer compete for space.
- Refined the approved copper beam and slogan placement. A subtle bug emerged when the background used `cover` scaling: a fixed overlay offset drifted away from the artwork as the viewport resized. The beam's dimensions and offset were tied to the same cover-scale factor. The approved underlying image was preserved.
- Unified the investigation header and controls, tightened spacing, removed redundant project labels and visual noise, and made title and description editing more direct. Strategy names became editable in place with explicit Save/Cancel, keyboard submission, Escape handling, and stable focus.
- Reworked strategy creation so **New** and **Generate** sit visibly with the Strategies heading. The generation composer moved inline and gained a truthful working/hourglass state rather than inactive-looking controls or an invented progress percentage.
- Simplified strategy commands, implemented a working **Fork** draft flow, and retained the ability to edit, remove, reorder, and review strategy history. The existing manual stage labels remain manual; `Exploring` does not imply an agent is running.
- Completed substantial groundwork for research text: durable Plain and Markdown representations, deterministic rendered Markdown/LaTeX, in-place edits, source authority and stale-cache behavior. These are presentation and authoring capabilities, **not mathematical verification**.

### Numerous bug fixes and regressions

Much of the day consisted of finding places where plausible behavior broke when used for real.

**Stock projects and naming.** The original stock-open workflow did not match the desired working-copy semantics. Opening a stock template now creates an independent managed copy, retaining the checked-in example unchanged, and records the copy in Recent Projects. We added tests for independent identity, exact fixture preservation, and reopen behavior. We fixed naming collisions across stock, recent, and saved investigations, gave repeated stock copies deterministic display suffixes (`(copy)`, `(copy 1)`, etc.), improved the duplicate-title explanation, and tightened private permissions on the naming lock. An earlier Day 1 note saying that stock opens themselves remained outside Recents is superseded by this final behavior.

**Home and keyboard behavior.** Iterative fixes addressed the overlap between the copper artwork, project controls, and recent list; position and scaling drift after resize; inconsistent Remove-link placement; the order of New/Open actions; and unwanted focus styling on the Projects heading. Strategy inline renaming initially interfered with disclosure-click behavior and keyboard focus; follow-up fixes preserved input focus, enabled Enter to submit, and avoided toggling the strategy row while editing.

**Terminology and compatibility.** The shift toward **Investigation** required more than replacing labels. An initial broad rename was reverted, and the surviving changes were made selectively, including the `investigation_type` model/API field with compatibility for legacy `research_mode` input. Pre-v4 serialization, catalog/recent models, and tests were corrected. Existing project files were not casually rewritten on read.

**Markdown conversion failures.** The reported conversion error was especially instructive: SIGMA surfaced a local HTTP 400 while the ChatGPT-plan provider had actually returned HTTP 200 with an untyped streamed response. The previous adapter attempted JSON parsing, lost the real payload shape, and characterized the placeholder as a provider rejection. The A14.2 repair recognized valid untyped SSE through the strict stream validator, distinguished malformed output from genuine provider rejection, and preserved the original text on failure. A subsequent fix accepted the relevant JSON and SSE response forms and retained actionable sanitized diagnostics. No hidden API-key fallback or billing-mode switch was introduced.

A second conversion defect came from reusing **Generate Strategy's 128 KB response-envelope limit** for potentially larger Markdown conversions. Valid conversion responses could exceed that limit even when the actual converted text was bounded. Text conversion received its own explicit **1 MB envelope cap**, with tests for both large valid responses and oversized rejection without data loss. We also fixed the Σ conversion control's tooltip and working-state feedback: **Convert to markdown**, **Converting to markdown**, then **Show plain text**.

**Request failure behavior.** Network-bound errors needed a single dismissible **Request Failed** toast, followed by a correct feature-specific state. A conversion failure must leave the readable source intact; a generation failure must retain the draft/starting point and permit explicit retry. An HTTP error must never masquerade as a successful conversion or silently navigate to an empty rendered view.

**Development launcher recovery.** Restarting SIGMA exposed a harder operational problem: suspended launcher processes and orphaned FastAPI/Vite servers could retain locks or ports. The launcher gained ownership records and a matching-checkout shutdown path. Further fixes addressed legacy suspended processes without ownership files, multiple verified lock holders, and separately verified orphan listeners. Recovery checks process identity, user, executable/checkout, and server identity before signalling anything; unrelated listeners are intentionally left alone. These fixes were committed with offline tests, **but full macOS restart/suspension verification remained pending**. They should not be described as field-proven yet.

**Test and build stabilization.** The source-controlled scenario suite was renamed to `tests/`, and its launcher/import/test scopes were updated. Several tests had stale expectations for the current investigation schema, Recents semantics, or stock-copy lifecycle; these were corrected rather than changing valid runtime behavior to satisfy obsolete tests. Formatting and type-check regressions found by the full suite were repaired.

### AI strategy generation: a reliable baseline

An important architectural clarification came late in the day. We had allowed **Generate Strategy** to inherit an unexpectedly heavy agentic ambition. After inspecting the code, we separated the work:

- **A15:** Make the ordinary, **single-LLM-request** Generate Strategy path function end to end.
- **A16:** Extend that baseline with real independent Explorer/Critic invocations, critique-driven coordination, revision and bounded retries.
- **A17–A21:** Build the larger research engine around persistent artifacts, proof obligations and discriminating tests, strategy-wide orchestration, user control, and auditability.

The A15 investigation found that the UI was calling the streamed A14 agentic endpoint despite an already-existing bounded single-proposal backend. The visible flow was moved to that backend. It now returns an **editable, unsaved draft**; only explicit Save writes a strategy. It retains model, thinking, account and billing identity safeguards, refuses stale results when the investigation changes during inference, and recovers safely from cancellation or provider errors. The underlying A14 agentic code remains available for A16 rather than being discarded.

A15 passed documented mocked-provider/API tests and a real-Chrome UI scenario: the zero-strategy counting example, empty starting point, one request, unsaved result, cancellation without mutation, failure toast, explicit edited Save, reopen, and a further proposal with prior-strategy context. **This was not a live proof-finding run**, and the heavy agentic workflow was not yet certified as the user-facing research engine.

### What we actually verified

The repository's `docs/STATUS.md` contains detailed command-level reports. Across the reported changes, `./sigma test`, Ruff, Pyright, frontend typecheck/Vite build, and several real-Chrome browser checks were run successfully. The text-conversion regression also records a **real connected ChatGPT-plan smoke test** after its fix: the provider returned HTTP 200, the local API returned HTTP 200, a nonempty Markdown representation was persisted, and the original project JSON remained byte-for-byte unchanged. Two earlier diagnostic requests had reproduced the failure and may have consumed plan usage.

The A15 generation checks used deterministic mocks, **not a paid live-model acceptance test**. The launcher recovery patches still need the noted macOS verification. These distinctions matter: committed code, green mocked tests, real-browser validation, successful live provider calls, and proven mathematical results are different kinds of evidence.

### Preparing for the big push: mathematical research, not AI theater

The rest of the evening was spent defining what SIGMA must become for a strong **Onebrief** demonstration. The Riemann Hypothesis work gave us the clearest design guidance. A speculative mathematical approach is only useful if we can identify **what mechanism it relies on, what it would have to prove, which boundary cases or negative controls might break it, and when to stop spending effort on it**.

That leads to several nonnegotiable requirements for the next implementation:

1. **Strategies carry active proof obligations and falsification tests.** A proposed rubric is not a generic confidence score. It specifies conditions, discriminating checks, failure criteria, evidence quality, and reasons to continue, revise, pivot, or stop. A decisive counterexample outranks an attractive numeric rating.
2. **Agents perform recorded work.** Generators, critics, test executors, and coordinators must leave behind typed, durable public artifacts and results. No fictitious progress, fabricated tool execution, or retroactive invention of evidence.
3. **Research spans multiple strategies and iterations.** Each attempt has a bounded budget and explicit states such as investigating, blocked, failed, or awaiting human review. One strategy can contribute a lemma or constraint to another without erasing either one's history.
4. **Lineage is first-class.** A result must be traceable backward through the **actual recorded dependencies** among claims, tests, agents, strategies, and human decisions. A plausible-sounding LLM narrative written afterward is not provenance.
5. **Success claims are gated.** A model can propose a candidate solution and independent agents can critique it. Neither a high rubric score nor agent agreement proves a mathematical theorem. Verified results require evidence commensurate with the claim.
6. **Human control remains explicit.** The user can inspect, prioritize, intervene, pause, override, and resume. Such changes must themselves be recorded with attribution rather than silently altering research history.

The execution sequence is now **A16 → A17 → A18 → A19 → A20 → A21**, then cloud migration, high-quality stock investigations and documentation, followed by integration testing and a Monday, October 26 delivery. The assignments are milestones, not a rigid hour-by-hour calendar. We will preserve scope and track unfinished work honestly instead of declaring a feature complete because a coding agent produced a commit.

### Day 1 retrospective

The number of follow-up fixes was not a distraction from SIGMA's mission. They exposed the engineering substrate that an autonomous research system will need: stable identity, correct model/account binding, atomic persistence, reversible user actions, guarded concurrency, trustworthy error reporting, compatibility across changes, and tests that exercise actual failure paths.

Day 0 taught us to preserve approved intent. **Day 1 taught us that auditability starts long before research agents arrive.** If a simple Markdown conversion cannot distinguish a successful HTTP response from a rejected payload, or a launcher cannot safely identify its own processes, then a multi-agent run that claims to have evaluated a theorem will be difficult to trust.

The next step is therefore not to make SIGMA *look* agentic. It is to give agents a constrained research loop in which each action can be checked, each claim can be challenged, every significant state change is durable, and a human can reconstruct how the system reached its conclusion.
