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

**Theme: make SIGMA a coherent research workspace and establish the standards for autonomous, evidence-based investigation.**

- Completed the A17 research workspace through successive rounds of **UI cleanup and standardization**, including a dedicated Research Sessions pane, consistent controls, clearer strategy management, and live research supervision.
- Added research outcome and strategy assessments, durable research artifacts, and project-level **Report Artifact** exports. Refined document presentation and PDF/HTML/LaTeX-oriented output.
- Completed A17.8's review of agent coordination and research trustworthiness, strengthening the distinction between an interesting result and a supported finding.
- Implemented and merged **A20: AI-authored research papers**, grounded in recorded research and explicit verification status.
- Added **A23 project difficulty** and three broader investigation samples spanning algorithms, experimental science, and physics.
- Defined the next substantial research milestone, **A18**, and prepared **A19**'s isolated Python execution capability. Finished the day with two independent Codex sessions assigned overnight development.

### A unified research workspace

Most of the day's visible progress came from treating SIGMA as an application people must actually use, not a set of individual features. Across A17.1–A17.7, we standardized titles, section headings, inline editing, disclosure patterns, action placement, hover/focus behavior, and the visual treatment of enabled, disabled, and destructive operations. Home, Settings, the project header, strategy rows, session details, and narrow-screen layouts received coordinated attention. These changes reduced the need for users to rediscover how each part of the interface works.

The investigation view settled into a clearer hierarchy: **Projects**, **Research Sessions**, and **Strategies**, with collapsible sections where appropriate. The new Research Session pane sits between the project and its strategies, providing the place to start, resume, supervise, and inspect actual research activity. We chose not to add previous/next session arrows without a demonstrated need. The goal for the first pass was a productive control surface, not a comprehensive navigation system.

Strategy management also became more direct. We removed the misleading stage column while preserving historical data, clarified disable/enable behavior, made Fork and Remove accessible in the title row, and kept strategy names and ordering unambiguous. Research status belongs primarily to the running session, not to a manually assigned strategy label.

**What we learned:** coherent interaction patterns are functional infrastructure for a complex product. More controls do not necessarily mean more control. The interface should make the current state and next meaningful action obvious.

### From activity to inspectable research

A17 evolved beyond showing that agents were busy. Research sessions gained clearer progress and outcome displays; strategy assessments and attribution; and inspectable artifacts that can be read as source text or rendered Markdown. We refined the distinction between starting fresh work and resuming a previous session, and between a running investigation, a recorded outcome, and a claim about the quality of that outcome.

The **Report Artifact** workflow made research export part of the product rather than an afterthought. It combines selected research material into a document with deliberate layout, format, filename, and presentation choices. We improved typeset mathematical output, browser preview, and the consistency of report/export controls. The point is to produce something another person can inspect and use, not simply download a transcript of agent messages.

A17.8 then challenged the quality of the research process itself. Agent critique and coordination were strengthened around objectives, evidence, limitations, and explicit trustworthiness criteria. Its improvements were merged through PR #4.

**What we learned:** agent activity is not evidence of progress. A useful research system must distinguish hypotheses, tests, counterexamples, assessments, and results, and make it possible to trace important conclusions back to the work that supports them.

### Turning research into publications, without overstating certainty

A20 added an AI-authored research-paper workflow and was merged through PR #5. Papers can assemble and explain recorded research in a more formal structure while using the established export capabilities. We iterated on mathematical exposition, the amount of evidence included, and practical generation limits.

The important design boundary is that **a well-written paper is not a verified proof**. Claims should retain their actual evidentiary status; older records lacking an explicit verification result remain **unknown** rather than being treated as confirmed. We also documented a future path to Lean-based formal verification, while keeping that capability clearly separate from current LLM review and mathematical presentation.

This gave SIGMA two complementary outputs: **research artifacts** that record the investigation and **papers/reports** that communicate it. The latter must remain faithful to the former.

### Broader investigations and deployment direction

The day's work also widened SIGMA's applicability beyond its Riemann Hypothesis showcase. We added sample investigations in **incremental dependency scheduling**, **unexpected experimental oscillation**, and **warp-drive physics**. They provide different kinds of questions against which to evaluate strategy generation, research controls, and the quality of evidence. The new samples were merged through PR #7.

A23 introduced a descriptive **difficulty setting**, merged through PR #6. Difficulty is useful context for evaluation and presentation, not a substitute for measuring research success. Older projects can retain an unknown value without inventing certainty.

We also defined **A22 cloud deployment** requirements, including identity, private workspaces, and secure execution boundaries. Hosting SIGMA will require more than moving the existing UI to a server: research workloads and their artifacts need an isolation and persistence model suitable for remote operation.

### Research autonomy and the overnight handoff

The next major engineering step is **A18**, assigned to **Blue**. Its scope was sharpened throughout the day: multiple agents and strategies should conduct sustained investigations, coordinate findings, challenge each other's reasoning, record dependencies and failures, and expose genuine live status to the user. We added concrete Easy and Medium evaluation targets, stress-testing expectations, and honest reporting of complete, partial, blocked, and failed outcomes. A18 remains underway, not a demonstrated solution to hard mathematical problems.

In parallel, **Green** was assigned **A19**, beginning with a standalone sandbox for agent-generated Python. Research agents need a way to perform computations and experiments with scientific libraries while containing execution through resource limits and disabled network access. This executor will ultimately be callable by the A18 orchestration and may also support A22's cloud architecture. A18 is an integration dependency, but it need not prevent independent A19 implementation and testing.

We finished Day 2 with **two autonomous Codex development sessions running in separate checkouts**: Blue developing A18's research engine and Green developing A19's Python executor. Their work will be reviewed against actual behavior, tests, and recorded artifacts rather than assumed complete because agents were left running overnight.

### Day 2 retrospective

The most significant change was conceptual as well as technical: SIGMA now has a more coherent way to **control research, preserve its work, assess its quality, and communicate its results**. The remaining challenge is to make the research itself genuinely productive.

The day reinforced three standards for that next step: **simplify the user's control surface; make every consequential research claim traceable to evidence; and evaluate agents by reproducible outcomes rather than convincing narratives**. Those standards define the overnight work and the next round of integration.


## Day 3 — October 23, 2026

**Theme: turn the research prototype into an integrated, testable alpha while preparing a controlled cloud launch.**

- Integrated the overnight **A18 multi-strategy research engine** and **A19 isolated Python execution**, then added agent-aware **SageMath** support. Research can now coordinate bounded concurrent investigations and use computational tools while retaining session history and evidence.
- Improved the quality and inspectability of research: richer **Outcome** views, evidence handoffs and citations, research memory, human intervention during active sessions, and adversarial evaluation cases. A bounded **live answer-free trial** produced a mathematically sound candidate with substantive Skeptic criticism, but exposed audit limitations that were corrected in code.
- Completed a broad **local alpha acceptance pass**, including real-browser checks of session controls, settings, samples, exports, and responsive UI. Continued polishing the project header, session controls, and Outcome presentation rather than treating UI quality as a final cosmetic pass.
- Established a **five-worker software factory** with scoped T-numbered tickets, tracked ownership, separate branches, independent reviews, and coordinator-managed merges. Added CI checks to make integration more repeatable.
- Advanced cloud readiness through **Google authentication, private workspaces, durable bounded research execution, public read-only Demo, account administration, and per-user spending limits**. After evaluating Cloudflare and Google Cloud, prepared a Google Compute Engine deployment package and provisioning runbook. Selected `sigma-research.duckdns.org` as the public hostname. **No cloud resources were provisioned today.**

### Research engine and computational evidence

The overnight work moved SIGMA beyond isolated agent responses. **A18** introduced bounded concurrent research across strategies, with explicit coordination and recorded outcomes. **A19** supplied a sandboxed Python execution path for experiments, and **T26** extended computational work to SageMath. These tools support research, but their existence is not evidence that a mathematical claim has been proved.

Subsequent work strengthened the connection between an agent's conclusion and its basis. **T27** improved handoffs and research history; **T28** made computational evidence inspectable and citable; **T29** enabled human intervention during active research; and **T37** addressed selection and reuse of trustworthy research memory. The Outcome UI was reorganized to make results, limitations, and provenance easier to inspect. Together, these changes moved the product toward an evidence-bearing research process rather than a persuasive conversation transcript.

We also expanded the sample catalog beyond mathematics, including biology, chemistry, and a creative-research investigation, and added workflows for turning exported projects into reusable samples. An exact Riemann Hypothesis adversarial oracle and other evaluation cases provide ways to challenge agent behavior without assuming that an attractive response is a correct discovery.

### Live research trial and the limits of acceptance

A key test was the **answer-free “Maximum Regions Formed by Lines” investigation**, run through the connected ChatGPT provider within an explicitly bounded budget. The Investigator first established an upper bound but had not justified attainability. The Skeptic identified that gap, and a later cycle supplied a line construction with distinct pairwise intersections, supporting the result `1 + n(n + 1)/2`. The session correctly labeled its outcome a **solution candidate (unverified)**, not a formally verified theorem.

The trial demonstrated meaningful mathematical criticism and revision. It also exposed important audit weaknesses: exact role inputs had not been preserved, long outputs were truncated without clear signaling, aggregate token usage was inconsistent, and some obligation and portfolio labels disagreed. The original run's answer independence therefore **cannot be established retrospectively**. Green's independent assessment documented those limits; Blue implemented request-input auditing, usage and outcome corrections, saved-session browser checks, and a final concurrency fix binding each audit to its exact call step. The corrected implementation passed the full suite and was merged through **PR #53**. No second live trial was run, and the original trial is not retroactively certified by the repair.

**What we learned:** a good answer and a good critique are necessary but insufficient. Trustworthy autonomous research also requires faithful request records, consistent accounting, reproducible evidence, and a clear distinction between a candidate result and verification.

### Local alpha quality and the software factory

The day's acceptance work exercised SIGMA as a product: project and strategy workflows, session supervision, settings, generated reports and audit exports, saved-session inspection, and desktop/mobile browser behavior. **T21** recorded a full local acceptance pass, with targeted corrections to session and header behavior. Further improvements to the Outcome hierarchy, model/thinking controls, keyboard and control placement, and launcher reliability helped bring previously separate features into a coherent interface. A green local suite and successful browser checks establish a stronger alpha baseline, not universal reliability.

The development process matured alongside the product. **Blue, Green, Red, and Gray** worked in separate Codex checkouts, with **ChatGPT** coordinating architecture, tickets, review, integration, and merges. The human remained responsible for product direction, manual visual judgment, and relaying messages among isolated workers. We replaced informal handoffs with **T-numbered tickets**, a tracking ledger, branch/PR ownership, documented acceptance conditions, and CI coverage for tests, lint, types, and frontend build.

This organization made substantial parallel progress possible, but the final T17.8 review also revealed the cost of excessive handoffs. The useful discipline is to **converge on a bounded correction and merge decision**, not to create repeated review loops after the material issues have been identified.

### Cloud architecture and launch preparation

Cloud work progressed from feasibility to a concrete deployment plan. The team evaluated Cloudflare's constraints, then pursued a **Google Cloud trial-based alpha** with Google sign-in, invited access, per-user private workspaces, durable bounded jobs, and a curated public Demo. Local account-management UI and per-user spending controls were added to support an operator-controlled launch. The cloud deployment package, authentication fixes, and provisioning documentation were integrated; local Compose and test validation were reported passing.

The chosen hostname is **`sigma-research.duckdns.org`**, with DuckDNS intended to point to a static cloud IP. The runbook separates pre-launch preparation from actions that create billable resources and documents staged checks for authentication, persistence, access isolation, and cost. **Actual Google Cloud provisioning and public launch were deferred to Day 4.** Passing local cloud-mode tests is not the same as validating a running public service.

### Day 3 retrospective

SIGMA finished the day with a materially stronger **research engine, computational tooling, evidence model, operator interface, and deployment foundation**. The team integrated a large amount of parallel work and completed local acceptance without claiming that the live trial proved general mathematical reliability or that the cloud service was already online.

Three lessons stand out: **research progress must be backed by inspectable evidence; a polished control surface is part of operational correctness; and parallel AI development succeeds only when review and integration converge.** Day 4's priority is provisioning and validating the hosted alpha, with real access, isolation, persistence, and spending behavior checked against the prepared launch gates.
