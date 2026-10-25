# About SIGMA: Interactive Research Flow and Agent Coordination Diagram

**Status:** detailed design and implementation specification for Red.  
**Target branch:** `red/about-green-integration`.  
**Scope:** refine the existing "How SIGMA Works: Multi-Agentic Research" diagram inside the About dialog. Do not redesign SIGMA's Home page or add a separate application surface.  
**Design direction:** copper-led, premium, accessible, expandable, faithful to the actual research architecture.  
**Reference implementation:** `AboutArchitecture` in `frontend/src/main.tsx` and its `.about-*` styles in `frontend/src/project-entry.css`.

## 1. Purpose and desired user understanding

The present diagram is visually polished but largely a one-way information flow. The project, strategies, research session and saved evidence are clear, yet Investigator and Skeptic read like two boxes with a handoff. It does not sufficiently explain *how SIGMA orchestrates multiple specialized AI roles, computation and iterative critique*.

Retain the information-flow story while allowing the reader to reveal the inner coordination:

1. **Research Project:** a hard overarching question.
2. **Project Strategies:** durable, different angles into that question. These are not proposed answers.
3. **Research Session:** a bounded attempt using one or more selected strategies. This is the diagram's **expandable centerpiece**.
4. **Specialized AI roles and orchestration, on expansion:** Investigator, Skeptic, optional tools, evidence, and the session control loop.
5. **Saved Evidence & Outcome:** retained findings, objections, code/execution records, open questions, and uncertainty, which may inform future sessions or revised/forked strategies.

The initial glance should answer "How is SIGMA research organized?" Expanding the session should answer "What makes this a coordinated, multi-agent investigation?" Expanding a strategy should answer "How can different research approaches coexist and contribute?"

This is an **educational architecture diagram**, not a live execution monitor or an alternate research UI. No live states, playback, synthetic activity or provider calls are needed.

## 2. Visual composition and hierarchy

### 2.1 Preserve the top-level diagram

Keep the existing section title **How SIGMA Works: Multi-Agentic Research**. Retain the original vertical visual story, centered inside the About dialog:

```text
                RESEARCH PROJECT
           The overarching hard question
                         |
       Branch into distinct research angles
                         v
                  PROJECT STRATEGIES
    +----------------+----------------+----------------+
    | Strategy A     | Strategy B     | Strategy C     |
    | Explore a      | Try another    | Challenge      |
    | pattern        | model          | assumptions    |
    +----------------+----------------+----------------+
                         |
       Selected strategies are investigated
                         v
                  RESEARCH SESSION
             Bounded research cycles
             [Explore agent coordination v]
                         |
              Work and evidence persist
                         v
              SAVED EVIDENCE & OUTCOME
          Findings, objections, experiments,
              unresolved questions
                         |
       Subtle return path: "Informs later work"
       (not an automatic self-branching claim)
```

Each strategy remains a *persistent direction*, and the session may investigate one **or several** selected strategies. Do not use copy implying every strategy runs simultaneously or that each session is necessarily tied to exactly one strategy.

Keep project and saved outcome as legible top-level copper elements. Keep the strategy group visibly copper. **Do not replace the diagram with an agent-only architecture chart.**

### 2.2 Make the Research Session the center of attention

The session is initially shown as a **compact copper-framed gateway**: "Research Session", "Coordinates bounded investigations", and a clear expand affordance labeled **Explore agent coordination** (down chevron).

When expanded, the *same* session frame grows downward and exposes its internal coordination diagram in place. The project and strategy blocks remain above; the Saved Evidence & Outcome block remains below. Its connecting arrows should reflow as the panel expands rather than becoming detached.

The expanded area should be the most visually informative part of the graphic without feeling like a new modal, a dashboard, or a dense paragraph. At desktop dialog width it should receive approximately half of the diagram's explanatory visual weight. No nested scrollable diagram, no second modal, no horizontal overflow.

### 2.3 Suggested expanded session architecture

Use this as the **semantic topology**, not a mandate to copy ASCII geometry literally:

```text
           RESEARCH SESSION  [Collapse agent coordination ^]
          +-----------------------------------------------+
          | SESSION ORCHESTRATION                         |
          | Selects bounded work, prepares context,      |
          | schedules role calls, enforces limits        |
          |                      |                        |
          |           Assign question + evidence          |
          |                      v                        |
          | +-------------------+    +------------------+ |
          | | INVESTIGATOR      |    | RESEARCH TOOLS   | |
          | | Proposes claims,  |--->| Python; SageMath | |
          | | reasoning, tests  |    | when available   | |
          | +-------------------+    +------------------+ |
          |           |                        |          |
          |           +------------+-----------+          |
          |                        v                      |
          |            WORKING RESEARCH EVIDENCE          |
          |            Arguments, code, outputs,          |
          |            references and uncertainties       |
          |                        |                      |
          |                        v                      |
          |                 SKEPTIC REVIEW                |
          |            Challenges claims, checks          |
          |            assumptions, identifies gaps       |
          |                        |                      |
          |                        v                      |
          |              COORDINATOR DECISION             |
          |           Continue / revise / stop            |
          |                        |                      |
          |          If continued: next bounded question  |
          |          returns to the Investigator          |
          +------------------------+----------------------+
                                   |
                          Persist artifacts / outcome
                                   v
                         SAVED EVIDENCE & OUTCOME
```

In the actual composition, avoid repeating a large "Session Orchestration" and "Coordinator Decision" box if that makes the panel busy. One copper **Orchestration** rail or control band may house two labeled stages: **Assign work** at the start, **Decide next step** at the end. Blue should identify the Investigator and Skeptic role boxes. A neutral/dark evidence area and a compact tools node support them. The loop must be visually apparent.

**Essential arrow semantics:**
- **Solid copper arrows:** structural information flow between Project, Strategies, Session and Saved Evidence.
- **Metallic blue directional arrows:** active role/evidence handoffs inside an expanded session.
- **Curved/dashed return route:** another research cycle *may* begin after review when limits and decisions permit.
- **Faint copper return route** from saved outcomes toward later strategy/session work: findings *can inform* later work. It is **not** an unconditional autonomous feedback loop.

Connector labels should convey verbs, not generic nouns. Recommended: **Assign task + context**, **Propose / execute**, **Review evidence**, **Critique + next question**, **Continue, revise or stop**, **Save findings**. Make arrowheads clear enough that the reader sees direction; never draw decorative arrows that imply unsupported data movement.

### 2.4 Make multiple selected strategies intelligible

The three strategy boxes at the top illustrate diverse **approaches**, not three types of agent. Do not draw an arrow from A to Investigator, B to Skeptic, C to Coordinator, which would incorrectly imply fixed assignments. The session consumes **selected strategy directions** and may maintain separate bounded work on multiple strategies, each with Investigator/Skeptic steps and possible evidence sharing.

A small, optional line inside expanded Session may say:

> "A session can investigate multiple selected strategies; each follows bounded investigation and review, and relevant evidence may inform another."

This conveys the multi-strategy/multi-agent relationship without a spaghetti diagram of nine agent boxes. Do not depict universal concurrent execution. A useful tiny visual cue is a small copper "Selected strategies" strip feeding the orchestration band, distinct from the blue role nodes.

## 3. Interactive behavior: overview first, detail on demand

### 3.1 Session expansion

- The initial state is **overview/compact**. A small but meaningful agent preview can remain visible (e.g. "Investigator ↔ Skeptic"), but the detailed tool, evidence and orchestration loop is initially hidden.
- Put a clearly labeled **Explore agent coordination** control with chevron on or immediately below the Session card. Do not rely solely on an unlabeled icon or tooltip.
- Activate by mouse click, Enter or Space. A second activation collapses the same panel.
- Animate height and reveal subtly (roughly 180-250 ms); do not animate the whole About dialog or move focus unexpectedly. Respect `prefers-reduced-motion: reduce`.
- Preserve the outer vertical connectors in both states. The Saved Evidence card stays below the session and shifts naturally downward when expanded.
- The state belongs only to the currently open About dialog. No project setting, browser persistence, API call or authentication dependency is needed.
- Give the control `aria-expanded`, `aria-controls`, a clear accessible name and an associated panel with an intelligible heading. Do not attach `aria-expanded` to a tooltip-only information button and pretend it controls the architecture expansion.

### 3.2 Strategy A, B, C: independent discoveries about research approaches

Keep A, B and C **equally important** rather than subtly presenting A as the correct choice or C as a failure. Each should have a *different* short visible subtitle. The wording must be domain-independent, accessible and illustrative rather than three fixed SIGMA strategy categories.

| Card | Visible subtitle | Expanded microdescription | Tooltip / richer description |
| --- | --- | --- | --- |
| **Strategy A** | **Explore a pattern** | "Study a promising structure or relationship, then test where it holds." | "A strategy can investigate an observed pattern or relationship. Its objective is bounded: identify supporting evidence, find limits, or expose a useful unanswered question. It does not need to solve the entire project." |
| **Strategy B** | **Try another model** | "Use a different representation or method to expose what another approach misses." | "The same problem may become clearer through a different model, formalism, or computational method. Its results can complement, challenge, or refine the evidence from other strategies, without being assumed equivalent." |
| **Strategy C** | **Challenge assumptions** | "Probe boundary cases, alternative hypotheses or potential counterexamples." | "A strategy may deliberately stress-test an assumption or search for a counterexample. A negative result can rule out a local claim while leaving the wider research problem open and the strategy's history intact." |

Interactions:
- Allow each strategy card to be **expanded for its microdescription** using a small chevron and a genuine button/control. Prefer one expanded strategy at a time to preserve the compact three-card row. A second click on the same card collapses it.
- Keep the **styled information tooltip** on each strategy as an *independent* affordance (the existing circular "i" icon can become a separate help button). Mouse hover over the card may reveal the tooltip if it does not interfere with the expand control.
- On keyboard and touch, the richer tooltip must be reachable without requiring hover, and expansion must still work. Strategy expansion and tooltip opening are different state changes. Tapping the information icon should not accidentally toggle the expanded strategy.
- If the user opens the Session internals while one strategy is expanded, both should remain meaningful. Do not collapse the session unexpectedly.
- Use authentic labels, not "Strategy A means Investigator" or any suggestion that these examples are mandatory categories.

### 3.3 Tooltips and detailed descriptions for all major boxes

Keep the existing polished custom-tooltip visual system but separate "learn what this node means" from "expand the workflow". Provide short box subtitles and informative descriptions:

| Node | Short label / subtitle | Information text |
| --- | --- | --- |
| Research Project | "The overarching hard question" | "A project holds the central research question and multiple persistent research directions. Results from a local investigation do not automatically settle the entire question." |
| Project Strategies | "Different angles into the problem" | "Strategies are durable, bounded research ideas. They may be tested, revised or forked, and failed attempts retain their evidence and history." |
| Research Session | "Coordinates bounded investigations" | "A session is a recorded attempt using one or more selected strategies. It schedules specialist research roles, observes limits, preserves intermediate work and records the outcome." |
| Session Orchestration | "Assign, route, evaluate" | "SIGMA's session engine assembles bounded context, dispatches Investigator and Skeptic work, schedules eligible branches, manages budgets and decides whether another cycle can run." |
| Investigator | "Develop reasoning and experiments" | "The Investigator role develops claims, arguments, testable hypotheses and code proposals, while identifying assumptions and what remains uncertain." |
| Research Tools | "Execute bounded computations" | "Where enabled, proposed Python code is run through the execution subsystem; source and outputs become inspectable evidence. SageMath requires an available, validated runtime. A computation is not a formal proof." |
| Working Research Evidence | "Shared context, traceable sources" | "Claims, objections, code outputs, prior artifacts and source identifiers inform subsequent work. Relevant evidence is selected into bounded role contexts; this is not a magical global chat memory." |
| Skeptic | "Challenge the reasoning" | "The Skeptic role examines claims and assumptions, looks for counterexamples or gaps, and suggests discriminating next tests. Its review is model-reported, not independent proof certification." |
| Coordinator Decision | "Continue, revise or stop" | "After a review, SIGMA applies the recorded assessment, next question and remaining work within resource limits. A strategy can remain available for later revision or another session." |
| Saved Evidence & Outcome | "Retained research and uncertainty" | "Persisted artifacts preserve findings, reasoning, objections, execution results and open questions. Researchers can revisit prior evidence to guide later sessions or strategy revisions." |

The "Project Strategies" group may use a group-level information affordance only if it is genuinely useful. Do not duplicate every strategy's text in the default visible layout.

For the tooltip system:
- Do not use browser-native `title` alone.
- Show on mouse hover and keyboard focus; support tap to open/tap again or outside to dismiss.
- Allow Escape to dismiss a tooltip without inadvertently closing the About dialog.
- Ensure no tooltip is clipped by the scrolling dialog. Prefer stable inline placement or a deliberate anchored positioning strategy with measured bounds rather than an uncontrolled overlay.
- Avoid tooltip-induced jitter when moving between a node, the info affordance and its tooltip.
- Do not auto-scroll the entire About dialog every time a mouse grazes a node; reveal content only as needed to preserve keyboard/touch visibility.
- Provide focus restoration and appropriate `aria-describedby` or descriptive association. Do not have multiple visible elements with the same tooltip `id`.

## 4. The copper motif is the unifying design language

This design should unmistakably belong to SIGMA's **Home page**. Use its existing **metallic copper** as the dominant structural language, with **metallic blue** as a subordinate accent that identifies AI activity. The user explicitly wants to *reinforce the copper motif*, not introduce a blue-themed application inside About.

### 4.1 Palette and treatment

Inspect the Home page's live CSS tokens and visual surfaces first, then reuse compatible treatments. Existing About references include:

| Use | Existing reference | Intended treatment |
| --- | --- | --- |
| Primary copper edges | `#a96548`, `#8a6846` | Outer project, strategies, session shell, saved outcomes |
| Highlighted copper / text | `#e0ad74`, `#f0c999`, `#edc38d` | Warm top-edge catches, card titles, interactive emphasis |
| Deep copper / black | `#231b17`, `#111820`, `#0b121a` | Subtle metallic gradients, restrained recesses |
| Agent blue edges | `#4c83a8`, `#75b7ef` | Investigator and Skeptic cards, active role connectors |
| Blue highlights | `#acd9fa` | Agent labels, return/critique line |
| Supporting text | `#c4ced8`, `#b9c2cc` | Descriptions on dark backgrounds |

These are references from the existing implementation, not a request to hard-code a disconnected new palette. Prefer reusing established gradients, shadows, tokens and radii already present in `frontend/src/project-entry.css` and the Home page.

**Balance:** Copper is the architectural frame, headings, outer connectors and closing evidence. Metallic blue is visibly concentrated in the **Investigator**, **Skeptic** and *active internal agent-to-agent feedback paths*. Research Tools and Working Evidence should be dark neutral/steel with copper accents, rather than additional bright blue agent lookalikes. A thin copper frame around the entire expanded session keeps the composition cohesive.

### 4.2 Metal, not ornament

- Use subtle directional gradients, edge highlights, soft inner shadows and occasional controlled specular lines to suggest brushed copper.
- Keep borders fine and purposeful. No thick orange outlines, large glowing blobs, chrome reflections, neon streaks or excessive animation.
- Keep text comfortably legible and high-contrast; never sacrifice readability for the metallic effect.
- Connector nodes and arrowheads should share the same material language, not generic solid-white arrow icons.
- When expanded, the diagram should feel like an **opened research instrument**, revealing engineered internals inside its copper case.
- If any visual animation is used, animate **expansion** and perhaps a restrained one-shot connector reveal. Do not animate fictitious ongoing agent activity or pulses that imply real model calls.
- Preserve the Home page's serif display-heading / clear sans-serif label hierarchy and its established radius, spacing and dark background.

### 4.3 Spatial economy

The About dialog currently has a `min(680px, viewport - 32px)` width and scrolls vertically. Design within its **actual content width**, not a full-screen mockup.

On desktop:
- Project centered, three strategy boxes in one copper group, one wide Session frame, saved evidence below.
- Expanded session may use a compact two-column Investigator / Skeptic composition with a clear routed feedback loop; place tools adjacent to the Investigator and evidence centrally or below.
- Distinguish orchestration control from the AI roles via material, layout and labels.

At narrow widths:
- Stack strategies as needed without truncating subtitles.
- Stack expanded role nodes in **logical reading order**, with labeled down-arrows and a visible small "Feedback returns to Investigator" element; never rely on a microscopic horizontally stretched loop.
- Keep tool/evidence relation intelligible without crossed arrows.
- Avoid small tap targets and illegible connector labels. The information flow must remain understandable even if SVG connectors are hidden at the smallest sizes.

## 5. Architectural accuracy: statements the diagram may and may not make

The diagram must educate without overselling current capabilities. Review source behavior rather than making product claims from the picture alone.

### 5.1 Grounded behavior

- A project owns an overarching question and multiple durable strategies.
- A research session may involve **one or more selected strategies**.
- SIGMA invokes specialized **Investigator** and **Skeptic** role prompts and uses a bounded orchestration loop to manage steps, budgets and durable artifacts.
- A role may propose code; **actual** Python or optional SageMath execution depends on runtime availability and the execution path. Execution data can become part of subsequent review.
- A Skeptic's review can change the next bounded question, or a branch can end after a failure, conclusion or budget limit.
- Selected prior artifacts and cross-strategy evidence may be shown to another role when relevant. Not every finding transfers automatically, and not all transfers are correct.
- Research sessions record findings, claims, objections and uncertainties; previous attempts remain inspectable when history is retained.
- Strategies are not discarded merely because a particular session failed.

### 5.2 Explicit boundaries

- **"Session Coordinator" means orchestration logic and decisions**, not a guaranteed third independently reasoning foundation-model agent. Use **Session Orchestration** or **Coordinator Logic** as the primary visual label. Do not give it the same blue agent identity as Investigator/Skeptic.
- Do not imply Investigator, Skeptic and the coordinator are different commercial models or are always invoked simultaneously.
- Do not imply three selected strategies are always concurrently active. The platform can schedule multiple branches subject to limits; a session can involve fewer.
- Do not imply all work always uses Python or SageMath; tools are optional and environment-dependent.
- Do not claim the Skeptic formally verifies proofs. Its judgments and model-reported verification statuses are not independent mathematical certification.
- Do not imply automatic generation, creation, or branching of durable strategies without user action. A revised/forked strategy is persistent and should be explicitly approved as appropriate.
- Do not portray saved evidence as an autonomous global learning system. It is durable research state supplied selectively to subsequent sessions, not automatic truth synthesis.
- Do not present a computation or a finite experiment as proof of a general theorem.

These caveats need not flood the visible diagram. Preserve them through truthful visible labels and accessible information descriptions.

## 6. Implementation guidance

Stay within the existing About architecture component and stylesheet. Prefer semantic React elements and lightweight CSS/SVG connectors; no image asset, external charting library, animation dependency, canvas scene, new API or backend work.

Suggested local state responsibilities:
- `sessionExpanded: boolean` for the internal agent coordination diagram.
- `expandedStrategy: 'A' | 'B' | 'C' | null` for expanded examples.
- `activeInfoNode: NodeId | null` for transient custom help text.
- Keep keyboard/touch interaction state separate where necessary.

Do not reuse one boolean/`aria-expanded` state for both tooltips and diagrams. Keep node IDs and `aria-controls` stable. Use separate interactive controls for (a) expand/collapse and (b) show more information. The existing `AboutArchitecture` currently couples a node's button and its transient tooltip; adjust carefully, preserving keyboard and touch support while avoiding nested buttons.

Consider defining the static node copy in one typed local data structure to prevent mismatched visible and tooltip descriptions. All copy can be local/static; this is not a live data view. Avoid building a generic visualization framework for this one section. Keep the component small and maintainable; extract focused subcomponents if that simplifies the implementation.

### Layout and animation resilience

- Expanding the session changes normal document flow. Avoid absolute-positioned panels that cover Saved Evidence.
- Inline or responsive SVG connectors are acceptable. Ensure visual arrows are decorative to assistive technology when the same sequence is represented in text; avoid duplicated screen reader announcements.
- The expanded panel must not require sideways scrolling at 390px or 320px viewport widths.
- Collapsing while focus is inside the panel should return focus to the session's expand control; hidden controls must not remain in tab order.
- If the screen height is short, the reader must be able to scroll through the expanded detail naturally inside the existing About dialog.
- Subtle transition timing is acceptable only if reduced-motion users receive an instant, readable state.

## 7. Acceptance and evidence

Red should provide meaningful real-Chrome acceptance, not only screenshot inspection. No live OAuth, paid provider call or cloud side effect is needed. Use existing test patterns and local fixtures. Verify at least the following:

| Area | Required evidence |
| --- | --- |
| Default composition | Project → three distinct strategies → compact Session → Saved Evidence, all connected and readable |
| Expanded composition | Inner orchestration, Investigator, optional tools, working evidence, Skeptic, decision and return path are comprehensible together, without losing outer flow |
| Control semantics | Session expander toggles only the session; strategy expander toggles only strategy text; info affordances show descriptions without toggling their parents |
| Strategy education | A/B/C have distinct visible subtitles and distinct explanatory text, no domain-specific claims or implicit winners |
| Agentic accuracy | Reviewer can identify which elements are AI roles, which are deterministic orchestration/tools, and where critique changes the next question |
| Persistence story | Saved evidence remains part of the same diagram and its path back to later work is labeled as conditional |
| Keyboard | Tab and focus visible, Enter/Space expansion, Escape tooltip dismissal, collapse focus recovery, dialog close still works |
| Touch | Tap to expand, tap info for descriptions, outside tap dismisses only transient info; no hover dependency |
| Responsive | Real Chrome at desktop (e.g. 1440px viewport), 390px and 320px; no clipping, overlapping connector text or horizontal overflow |
| Visual consistency | Home metallic copper remains the dominant design; internal agent blue stays subordinate and legible; reduced motion works |
| Regression | Existing About intro, features, Close button, scrollability, headers, sign-in pill and Green's Outcome/Preferences changes untouched |
| Build | Frontend typecheck/build and `env -u SIGMA_CLOUD_BOOTSTRAP_ADMIN_EMAIL ./sigma test` pass |

Capture **collapsed and expanded** screenshots at desktop and mobile, plus expanded strategy and tooltip states. Record the tested branch SHA and any genuine limitations. Use the current About dialog's actual viewport width, not a standalone page mockup.

## 8. Non-goals and implementation boundary

- No new Home page artwork, extra About modal, live graph inspector, execution animation, persisted diagram preferences, external illustration assets, real-time backend integration or changes to research behavior.
- No separate app page or distracting second explanatory graphic. This redesign **replaces and improves the existing diagram**.
- No gratuitous styling changes outside About. Do not affect the Project workspace, Green's Outcome hierarchy or model controls.
- No attempt to certify research correctness or benchmark agent outcomes through this visual design.

## 9. Completion standard

A reader unfamiliar with SIGMA should be able to do the following without reading all About prose:

1. Follow the overall **information flow** from project to strategies to session to retained research.
2. Understand that **strategies are alternative bounded investigative directions**, illustrated by three distinct examples.
3. Expand Session and identify **two specialized AI roles**, not just generic chat bubbles.
4. See **how orchestration routes work, evidence and optional computation through an iterative critique cycle**, including decisions to continue, revise or stop.
5. Understand that **saved research may inform later work**, but that neither agent agreement nor computation constitutes a certified proof.
6. Recognize this as **SIGMA's copper-first design**, with blue highlighting the AI roles and their communication.

**Editorial summary:** *Copper shows the structure of a persistent research investigation. Metallic blue reveals the coordinated AI work inside it. Expansion joins the two stories without breaking the research flow.*
