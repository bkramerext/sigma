# SIGMA journal

High-level milestones, recorded by day.

## Day 0 — October 20, 2026

**Theme: establish the local research workspace and development workflow.**

- Initialized SIGMA's Python/FastAPI and React/TypeScript application, CLI, tests, and project conventions.
- Established local-first persisted investigations, editable project settings, strategy creation and history, sample mathematical investigations, and Recent Projects.
- Integrated ChatGPT authentication and the opt-in AI proposal path. AI-generated drafts require explicit user acceptance before being saved.
- Introduced versioned implementation assignments, shared service contracts, and accompanying automated checks for backend and browser behavior.

### Initial integration and verification

The first end-to-end launch exposed two artwork-integration defects: the expected runtime image was missing, and a substitute UI mockup was later loaded as the actual Home background. The correct source image was installed and verified in the running browser. Validation distinguished packaged assets, served output, and observed UI behavior.

SIGMA's initial persistence model supports project identity, reversible edits, event history, and test fixtures. It provides the basis for subsequent research provenance and reproducibility.

### Authentication and connection status

The ChatGPT connection flow was exercised successfully, including the first-connection welcome notification. Subsequent use revealed that the interface displayed an expired connection check after a 60-second cache period, even though account authorization itself had not necessarily expired. A follow-up assignment (`A8.2.1`) was created for quiet status refresh and accurate transient-error handling; it was not yet implemented at the time of this entry.

Independent model review and other autonomous research capabilities were identified as future work, distinct from the single-request proposal feature available at this stage.

## Day 1 — October 21, 2026

**Theme: research-workspace stabilization and preparation for autonomous investigations.**

Day 1 concentrated on core research-workspace interactions, implementation defects, and validation. Work included investigation creation, sample-project lifecycle, mathematical-text editing and conversion, AI strategy proposals, error handling, and development-server recovery. Multi-agent mathematical investigation remained the next major implementation milestone.

### A real workspace, not just a screen

- Consolidated the Home page into a compact **Projects** heading with **New** and **Open**, plus a Samples-first Samples/Recent catalog. Reworked the layout repeatedly across wide, laptop, and narrow viewports so the slogan, project list, and copper artwork no longer compete for space.
- Refined the approved copper beam and slogan placement. A subtle bug emerged when the background used `cover` scaling: a fixed overlay offset drifted away from the artwork as the viewport resized. The beam's dimensions and offset were tied to the same cover-scale factor. The approved underlying image was preserved.
- Unified the investigation header and controls, tightened spacing, removed redundant project labels and visual noise, and made title and description editing more direct. Strategy names became editable in place with explicit Save/Cancel, keyboard submission, Escape handling, and stable focus.
- Reworked strategy creation so **New** and **Generate** sit visibly with the Strategies heading. The generation composer moved inline and gained a truthful working/hourglass state rather than inactive-looking controls or an invented progress percentage.
- Simplified strategy commands, implemented a working **Fork** draft flow, and retained the ability to edit, remove, reorder, and review strategy history. The existing manual stage labels remain manual; `Exploring` does not imply an agent is running.
- Completed substantial groundwork for research text: durable Plain and Markdown representations, deterministic rendered Markdown/LaTeX, in-place edits, source authority and stale-cache behavior. These are presentation and authoring capabilities, **not mathematical verification**.

### Numerous bug fixes and regressions

Much of the day consisted of finding places where plausible behavior broke when used for real.

**Sample projects and naming.** The original sample-open workflow did not match the desired working-copy semantics. Opening a sample template now creates an independent managed copy, retaining the checked-in example unchanged, and records the copy in Recent Projects. We added tests for independent identity, exact fixture preservation, and reopen behavior. We fixed naming collisions across sample, recent, and saved investigations, gave repeated sample copies deterministic display suffixes (`(copy)`, `(copy 1)`, etc.), improved the duplicate-title explanation, and tightened private permissions on the naming lock. An earlier Day 1 note saying that sample opens themselves remained outside Recents is superseded by this final behavior.

**Home and keyboard behavior.** Iterative fixes addressed the overlap between the copper artwork, project controls, and recent list; position and scaling drift after resize; inconsistent Remove-link placement; the order of New/Open actions; and unwanted focus styling on the Projects heading. Strategy inline renaming initially interfered with disclosure-click behavior and keyboard focus; follow-up fixes preserved input focus, enabled Enter to submit, and avoided toggling the strategy row while editing.

**Terminology and compatibility.** The shift toward **Investigation** required more than replacing labels. An initial broad rename was reverted, and the surviving changes were made selectively, including the `investigation_type` model/API field with compatibility for legacy `research_mode` input. Pre-v4 serialization, catalog/recent models, and tests were corrected. Existing project files were not casually rewritten on read.

**Markdown conversion failures.** The reported conversion error was especially instructive: SIGMA surfaced a local HTTP 400 while the ChatGPT-plan provider had actually returned HTTP 200 with an untyped streamed response. The previous adapter attempted JSON parsing, lost the real payload shape, and characterized the placeholder as a provider rejection. The A14.2 repair recognized valid untyped SSE through the strict stream validator, distinguished malformed output from genuine provider rejection, and preserved the original text on failure. A subsequent fix accepted the relevant JSON and SSE response forms and retained actionable sanitized diagnostics. No hidden API-key fallback or billing-mode switch was introduced.

A second conversion defect came from reusing **Generate Strategy's 128 KB response-envelope limit** for potentially larger Markdown conversions. Valid conversion responses could exceed that limit even when the actual converted text was bounded. Text conversion received its own explicit **1 MB envelope cap**, with tests for both large valid responses and oversized rejection without data loss. We also fixed the Σ conversion control's tooltip and working-state feedback: **Convert to markdown**, **Converting to markdown**, then **Show plain text**.

**Request failure behavior.** Network-bound errors needed a single dismissible **Request Failed** toast, followed by a correct feature-specific state. A conversion failure must leave the readable source intact; a generation failure must retain the draft/starting point and permit explicit retry. An HTTP error must never masquerade as a successful conversion or silently navigate to an empty rendered view.

**Development launcher recovery.** Restarting SIGMA exposed a harder operational problem: suspended launcher processes and orphaned FastAPI/Vite servers could retain locks or ports. The launcher gained ownership records and a matching-checkout shutdown path. Further fixes addressed legacy suspended processes without ownership files, multiple verified lock holders, and separately verified orphan listeners. Recovery checks process identity, user, executable/checkout, and server identity before signalling anything; unrelated listeners are intentionally left alone. These fixes were committed with offline tests, **but full macOS restart/suspension verification remained pending**. They should not be described as field-proven yet.

**Test and build stabilization.** The source-controlled scenario suite was renamed to `tests/`, and its launcher/import/test scopes were updated. Several tests had stale expectations for the current investigation schema, Recents semantics, or sample-copy lifecycle; these were corrected rather than changing valid runtime behavior to satisfy obsolete tests. Formatting and type-check regressions found by the full suite were repaired.

### AI strategy generation: a reliable baseline

The strategy-generation work is separated into these implementation milestones:

- **A15:** Make the ordinary, **single-LLM-request** Generate Strategy path function end to end.
- **A16:** Extend that baseline with real independent Explorer/Critic invocations, critique-driven coordination, revision and bounded retries.
- **A17–A21:** Build the larger research engine around persistent artifacts, proof obligations and discriminating tests, strategy-wide orchestration, user control, and auditability.

The A15 investigation found that the UI was calling the streamed A14 agentic endpoint despite an already-existing bounded single-proposal backend. The visible flow was moved to that backend. It now returns an **editable, unsaved draft**; only explicit Save writes a strategy. It retains model, thinking, account and billing identity safeguards, refuses stale results when the investigation changes during inference, and recovers safely from cancellation or provider errors. The underlying A14 agentic code remains available for A16 rather than being discarded.

A15 passed documented mocked-provider/API tests and a real-Chrome UI scenario: the zero-strategy counting example, empty starting point, one request, unsaved result, cancellation without mutation, failure toast, explicit edited Save, reopen, and a further proposal with prior-strategy context. **This was not a live proof-finding run**, and the heavy agentic workflow was not yet certified as the user-facing research engine.

### What we actually verified

The repository's `docs/STATUS.md` contains detailed command-level reports. Across the reported changes, `./sigma test`, Ruff, Pyright, frontend typecheck/Vite build, and several real-Chrome browser checks were run successfully. The text-conversion regression also records a **real connected ChatGPT-plan smoke test** after its fix: the provider returned HTTP 200, the local API returned HTTP 200, a nonempty Markdown representation was persisted, and the original project JSON remained byte-for-byte unchanged. Two earlier diagnostic requests had reproduced the failure and may have consumed plan usage.

The A15 generation checks used deterministic mocks, **not a paid live-model acceptance test**. The launcher recovery patches still need the noted macOS verification. These distinctions matter: committed code, green mocked tests, real-browser validation, successful live provider calls, and proven mathematical results are different kinds of evidence.

### Next: multi-agent mathematical investigation

The next research-engine requirements draw on earlier Riemann Hypothesis investigations: speculative mathematical approaches should identify their mechanisms, proof obligations, boundary conditions, negative controls, and explicit failure criteria.

That leads to several nonnegotiable requirements for the next implementation:

1. **Strategies carry active proof obligations and falsification tests.** A proposed rubric is not a generic confidence score. It specifies conditions, discriminating checks, failure criteria, evidence quality, and reasons to continue, revise, pivot, or stop. A decisive counterexample outranks an attractive numeric rating.
2. **Agents perform recorded work.** Generators, critics, test executors, and coordinators must leave behind typed, durable public artifacts and results. No fictitious progress, fabricated tool execution, or retroactive invention of evidence.
3. **Research spans multiple strategies and iterations.** Each attempt has a bounded budget and explicit states such as investigating, blocked, failed, or awaiting human review. One strategy can contribute a lemma or constraint to another without erasing either one's history.
4. **Lineage is first-class.** A result must be traceable backward through the **actual recorded dependencies** among claims, tests, agents, strategies, and human decisions. A plausible-sounding LLM narrative written afterward is not provenance.
5. **Success claims are gated.** A model can propose a candidate solution and independent agents can critique it. Neither a high rubric score nor agent agreement proves a mathematical theorem. Verified results require evidence commensurate with the claim.
6. **Human control remains explicit.** The user can inspect, prioritize, intervene, pause, override, and resume. Such changes must themselves be recorded with attribution rather than silently altering research history.

The planned implementation sequence is **A16 → A17 → A18 → A19 → A20 → A21**, followed by hosting, sample-investigation content, documentation, and end-to-end verification. Agentic investigations, cross-strategy research, and lineage tracing remain requirements in progress.

### Day 1 retrospective

The day's fixes strengthened capabilities needed by the research engine: stable identity, model/account binding, atomic persistence, reversible user actions, guarded concurrency, truthful error reporting, compatibility across versions, and tested failure paths.

**Auditability begins in the supporting services.** Accurate response parsing, safe process ownership, immutable source data, persistent provenance, and reproducible tests are prerequisites for attributing future mathematical claims to actual evidence.

The next implementation step is a constrained research loop with checkable actions, critic-reviewed claims, durable state changes, and traceable paths from findings to their supporting evidence.


## Day 2 — October 22, 2026

**Theme: turn SIGMA's research workspace into an auditable research system, then hand off sustained development to two autonomous coding sessions.**

- Advanced the research-session UX and agentic workflow through **A17.8**, then reviewed and merged its evidence-based coordination improvements.
- Defined **A18** as a substantial autonomous research milestone: multiple active strategies and agents, live supervision, honest benchmarks, concurrent execution, and durable evidence. Assigned it to **Blue**.
- Implemented and merged **A20**, the AI-authored research-paper workflow, with attention to evidence reconciliation, mathematical presentation, exports, and response-size limits.
- Added and merged **A23**, a descriptive project-difficulty setting, and expanded the sample catalog beyond mathematics.
- Documented research trustworthiness expectations and a future **Lean verification** plan without treating model agreement as formal proof.
- Prepared **A19**, an isolated Python research executor, for **Green**; its standalone implementation can proceed while Blue builds A18.
- Ended the day with **two independent Codex CLI sessions** assigned overnight work in separate checkouts, after resolving Green's startup configuration and working around a locked previous conversation.

### Research sessions and the A17.8 handoff

The investigation interface evolved toward a clearer hierarchy: collapsible **Projects** and **Strategies** sections surrounding a dedicated **Research Session #n** pane. That middle pane is where a user should start, control, and observe research, rather than mistaking a strategy's manually assigned status for live agent activity. Navigation among older sessions remains a possible future enhancement, not a first-pass requirement.

A17.8 focused on making the existing research workflow more credible: agent review, objective coordination, explicit evidence, and improved trustworthiness assessment. The work was reviewed and merged through PR #4. A central lesson was that attractive narratives and agent consensus are insufficient. Research must preserve its actual supporting observations, obligations, limitations, and provenance. The resulting trustworthiness guidance was carried forward into A18.

### A18: autonomous research that can be evaluated

A18's scope was deliberately strengthened from a narrow agent loop into a sustained research mission. Blue is responsible for the full strategy lifecycle, concurrent agents, cross-strategy cooperation, recorded findings, and live human supervision. A session must expose what is actually running, what each agent has attempted, which claims remain open, and why work was continued, rejected, or blocked.

We added explicit acceptance and reporting requirements, including representative **Easy** and **Medium** problems, complete-solution targets, and honest accounting for partial results and failures. Concurrent research stress testing and remediation are part of Blue's assignment. Blue was instructed to work autonomously and interrupt only for genuine global blockers, while reporting incomplete work accurately. This is an engineering and evaluation target, **not a claim that SIGMA can already solve hard mathematical problems**.

### A20: turning recorded research into a paper

A20 introduced an AI-authored research-paper workflow, with mathematical exposition, claim and evidence handling, and reuse of the existing export path. Iteration addressed paper structure, evidence-volume limits, stream-response limits, and preservation of export choices. The interface now communicates generation limits instead of allowing size failures to appear mysterious.

A key correctness concern was reconciliation: paper prose must not silently upgrade an unverified claim into a proven result. Legacy verification status defaults to **unknown** rather than acquiring unwarranted certainty. After review and fixes, A20 was merged through PR #5. Its presence provides a paper-generation capability, not independent mathematical verification.

### Broader projects and verification planning

A23 added a descriptive **project difficulty** setting, including a safe unknown value for older projects. The setting supplies useful context without asserting that a project's mathematical difficulty has been measured objectively. PR #6 was merged.

The sample catalog was expanded with an incremental dependency-scheduler design problem, an unexpected-oscillation scientific investigation, and a warp-drive physics concept. The new examples were brought into line with the strict project schema and difficulty metadata; PR #7 was merged. Together they demonstrate that SIGMA is intended for algorithm design, experimental science, and speculative physics as well as the Riemann Hypothesis.

A future Lean integration plan was committed at `docs/LEAN_VERIFICATION_PLAN.md`. Formal verification remains future work. We explicitly separated AI-written arguments, empirical checks, agent critique, and machine-checked proof, because each warrants a different level of confidence.

### A19 and the path toward cloud execution

Green's next assignment is **A19: autonomous Python execution for research agents**. It begins with a standalone proof of concept: agent-generated Python runs inside an isolated, resource-limited environment, with scientific libraries such as NumPy, SciPy, pandas, SymPy, and Matplotlib, and no network access for executed research code. The executor should retain useful results and artifacts and present a stable interface for the A18 agents.

Green identified A18 as a prerequisite for full integration. We clarified the dependency: **A18 is an integration dependency, not a reason to idle A19**. Green can build and validate the executor contract independently while Blue develops the orchestration. Docker isolation is also a useful foundation for **A22 cloud deployment**, although containerizing the research executor alone does not deploy the entire application.

### Two Codex sessions, and what the lock taught us

We split overnight work across two checkouts and two Codex CLI sessions: **Blue** in `~/sigma` on A18, and **Green** in `~/sigma_green` on A19. Each has a distinct assignment and can work without overwriting the other's checkout. The handoff explicitly requires Green to read `AGENTS.md`, A19's specification and prerequisites, relevant architecture documents, and the Lean verification plan before implementing.

Green's restart exposed a Codex configuration migration: the installed CLI rejected the older `[profiles.green]` form and required a separate `~/.codex/green.config.toml`. Once configured, resuming the old conversation still produced **“This conversation is open in another app.”** Process inspection found no second Green terminal, but the shared Codex app-server had Green's session file open. Its session metadata named `sigma_green` and `source: "vscode"`, even though the user was working in the CLI. We deliberately left the shared app-server and Blue's active process alone. The practical recovery was to start **a new Green conversation** with `codex --profile green` and supply the assignment and document-reading instructions again.

This episode reinforced an operational rule for parallel agent development: isolate workspaces and permissions, preserve active sessions, and prefer a clean new conversation over destructive attempts to clear ambiguous ownership locks. A session's availability and a checkout's code state are separate concerns.

### Day 2 retrospective and overnight handoff

Day 2 moved SIGMA beyond a polished research UI toward a system that can **perform, record, challenge, and communicate research**. The most important conceptual distinction remained stable: generating a strategy, running a test, writing a paper, and verifying a proof are different accomplishments. The product should expose those differences rather than smoothing them away.

The day closes with **Blue continuing A18's autonomous multi-agent research implementation** and **Green beginning A19's isolated Python executor in a fresh Codex session**. Their overnight work is in progress, not yet accepted or merged. Tomorrow's work is to review their actual artifacts and tests, resolve the A18/A19 integration boundary, and continue toward cloud deployment without sacrificing the evidence and failure-handling discipline established today.
