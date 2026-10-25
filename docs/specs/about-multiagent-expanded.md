# Specification: About SIGMA, expanded multi-agent research explanation

**Owner:** Green  
**Branch:** `green/about-polish` (PR #87)  
**Status:** Coordinator direction; implement and demonstrate before R4R  
**Scope:** The interactive About dialog's expanded *Research Session / Investigator–Skeptic* view. Preserve the other About and account-entry fixes in PR #87.

## Why this is needed

The latest polish improved the dialog's footprint but compressed the expanded multi-agent explanation too far. The result shows two named agents and a short feedback arrow, without telling the visitor what makes SIGMA an orchestrated, cumulative multi-agent research application. The user previously invested considerable time specifying this depth and wants it back, **without reverting to a visually cluttered or text-heavy panel**.

**Design principle: progressive disclosure, not progressive deletion.** Keep the closed view immediately legible and compact; make the opened view a thoughtful, substantial explanation with an elegant information hierarchy. Optimize for comprehension, not lowest dialog height or fewest words.

## The story a first-time visitor must understand

Within ~20–30 seconds of opening the detail view, a visitor should be able to explain:

1. **Different research directions.** A project can hold several persistent, bounded strategies. Selected strategies may be investigated in a session, rather than forcing a single giant answer to the whole question.
2. **Distinct specialized agent roles.** An **Investigator** develops a claim or test and supplies arguments or computational evidence. A **Skeptic** challenges assumptions, checks the stated support, identifies gaps or counterexamples, and proposes what to test next. These are separate role-conditioned AI turns, not a formal proof checker or a promise of different model vendors.
3. **An iterative feedback loop.** The critique is fed back into later Investigator work; the agent must respond to objections and can refine, retract, or narrow claims. Illustrate *Investigate → Challenge → Revisit*, not merely a one-way arrow.
4. **Coordination and bounded execution.** SIGMA orchestrates the turns and the selected strategies in a research session, subject to explicit call/iteration limits. This is structured, inspectable execution, not an endless autonomous conversation.
5. **Cumulative work, including between strategies and sessions.** Claims, objections, calculations, outcomes, and unanswered questions become durable, attributed evidence. Later work can reuse or challenge relevant earlier findings, including related strategy findings, without silently rewriting the past. Represent cross-strategy handoff accurately: evidence-linked and selective, **not** a claim of guaranteed synthesis or universally verified findings.
6. **Truthful boundaries.** A Skeptic's agreement and a numerical experiment are **not proof**; humans can inspect and redirect the work. Computational tools are conditional on availability.

The expanded view must connect *agents* to *orchestration* and *retained research state*. Showing only two chatbots talking misses the product's core distinction.

## Proposed information architecture

### Closed (unchanged in spirit)

Keep the tidy four-stage overview from PR #87:

**Research project → Persistent strategies → Bounded research session → Outcome & saved evidence**

Inside the session, show the two role labels and a clearly identifiable **"Explore multi-agent research"** or **"How the agents collaborate"** action. The current generic "Details" label undersells what the user will learn. Do not flood the collapsed diagram with text.

### Expanded (purposeful, informative, visually elegant)

Within the existing expansion surface, use **three digestible visual chapters** rather than a large paragraph or repeated card boilerplate:

**A. Specialist critique loop (hero illustration)**

- Three distinguishable *turns* connected with intentional directionality:
  - **01 INVESTIGATE — Investigator:** Proposes an approach, develops an argument, or runs a test.
  - **02 CHALLENGE — Skeptic:** Examines assumptions, probes evidence, raises objections.
  - **03 REVISIT — Investigator:** Responds to critique; revises, tests, or narrows the claim.
- Show a visible **return/iteration connector** so visitors understand that the Skeptic *changes what comes next*. A small "repeat within limits" annotation is helpful.
- Avoid implying three permanent independent named agents: this is a sequence of role-specific AI turns. Keep the artwork schematic rather than theatrical.
- A concise one-line setup above the diagram: **"SIGMA runs different research roles in a bounded critique loop, so the next step is informed by the last challenge."**
- Labels should be meaningful at a glance, with one short subordinate sentence per turn. No duplicated explanatory paragraph repeating each card.
- Use distinct but cohesive copper/blue hierarchy; typography and layout should carry meaning. Avoid unnecessary glows, decorative pills, multiple nearly identical arrow graphics, or huge whitespace.

**B. Coordinated across strategies (a second concept, not another copy of A)**

Visually tie the session to *selected persistent strategies* and their shared research record:

```text
Strategy A ── Investigator ⇄ Skeptic ── Findings A ┐
Strategy B ── Investigator ⇄ Skeptic ── Findings B ├─ Saved research record
Strategy C ── Investigator ⇄ Skeptic ── Findings C ┘        ↓
                                               Subsequent sessions
```

This ASCII is conceptual, **not mandatory UI artwork**. Prefer a compact three-lane mini-diagram or concise paired callouts as space allows, not a giant second architecture graphic. Make clear that:
- Different strategies pursue genuinely different approaches to one project.
- Evidence-linked findings/objections may inform later work on a peer strategy; a fresh session can revisit a strategy with accumulated context.
- The shared record does **not** mean all agents have unrestricted memory of every past interaction, or that cross-strategy relationships are automatically verified. Keep claims aligned with actual code.

Suggested heading: **"Several approaches, one inspectable research history"**.

**C. Why this is more than a conversation (compact footer / takeaway)**

Use 2–3 short icon/label + single-sentence facts, e.g.:
- **Orchestrated:** Selected strategies and specialized turns run under session limits.
- **Adversarial:** Skeptic objections have a place in the next research step; disagreement and failed paths remain visible.
- **Cumulative:** Each outcome links to saved reasoning and evidence for later review or reuse.

Then a quiet but explicit integrity note: **"Agent critique and computational evidence support investigation, not independent proof verification."**

## Copy guidance

Suggested lead copy (may refine for clarity, but do not silently eliminate its substance):

> **SIGMA does not ask one model for a final answer.** It coordinates distinct research roles across multiple strategies. Investigators propose and test ideas; Skeptics challenge the reasoning and evidence. Their objections can shape subsequent turns. Each bounded session saves what was tried, what held up, and what remains unresolved, so later sessions can build on prior work.

Do not present this as a marketing claim of automatic discovery, guaranteed improvement, fully autonomous consensus, or formal correctness. Use **agents**, **roles**, **strategies**, **research sessions**, **evidence**, and **objections** consistently with the product. Prefer "multi-agent" or "multi-agent research" to unnecessary "agentic" jargon, but make the architectural distinction explicit.

## UX and engineering constraints

- **Preserve PR #87's other fixes** (Google sign-in direct path, pill layout/order, Project About placement, etc.) and its closed-view simplification.
- The expanded view can legitimately be taller and vertically scrollable; **do not sacrifice content to meet the earlier 5% height-reduction target**. Closed dialog remains compact. No horizontal overflow at 1440, 390, or 320 CSS-pixel viewports.
- Prefer **one high-quality hero loop** plus **one lighter coordination/evidence illustration**. Avoid repeating the same agent-card diagram in both chapters.
- Readable text is more important than tiny cards. Desktop may use columns; mobile should stack in reading order. Maintain the established copper/black identity and restrained blue for roles/flow.
- Interaction: one obvious expand/collapse control; correct `aria-expanded` and `aria-controls`; keyboard/touch access, focus restoration on collapse, tooltip handling, Escape/close behavior, and scroll containment.
- Avoid fake animation suggesting live agent work. This is a conceptual diagram, not a real session or live status feed.
- Avoid architecture misstatements: do not promise parallelism for every execution, independent model backends, automatic proof checking, perfect transfer of all old context, or verified synthesis. Verify statements against current implementation and documentation.
- Preserve the current interactive info tooltips where useful, but **core meaning must be readable without hover**. Tooltips are optional elaboration, not the only place to learn what agents do.
- Don't re-introduce lengthy paragraphs from the old UI verbatim. Restore the **explanatory substance** and the explicit third turn and cumulative collaboration, while improving visual presentation.

## Acceptance criteria

1. A first-time visitor can see the **Investigator → Skeptic → Investigator** sequence and understand how the challenge influences the next turn.
2. The expansion explains multi-agent orchestration **across persistent strategies**, not only one two-role exchange.
3. The expansion explains **durable evidence** and how subsequent sessions may use or challenge it.
4. The distinction between *agent review*, *experimental evidence*, and *proof* remains clear.
5. The opened view is visibly richer than the closed overview but clean, elegant, and scan-friendly; no wall of text, tiny fonts, duplicative graphic elements, or clipping.
6. Real Chrome visual captures at desktop and 390/320 mobile widths, both collapsed **and expanded**, demonstrate the final design and no horizontal overflow.
7. Browser acceptance exercises expand/collapse, keyboard, touch, accessible naming, tooltip interactions and focus restoration; `./sigma test` passes.
8. Add a short walkthrough of the multi-agent explanation to the PR/handoff and link updated screenshots. **Request Brian's visual/content approval before merging.**

## Requested Green workflow

1. Read this spec, and compare current `green/about-polish` expanded rendering with the earlier richer design on `main` (especially the previous 01/02/03 turn story and saved-history explanation). Do not mechanically revert the old clutter.
2. Implement in the existing PR #87 / `green/about-polish` branch, without a new PR. Avoid unrelated UI changes.
3. Run real Chrome desktop and narrow-mobile acceptance with screenshots, full tests, and summarize how the expanded view covers the six story requirements.
4. Commit/push, report updated SHA and R4R, **but do not merge**. Brian's approval is required for this redesign.
