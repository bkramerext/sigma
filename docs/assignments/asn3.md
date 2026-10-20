# ASN-3: Project page and strategy pool foundation

Status: Implemented and verified; see [results](../STATUS.md)
Context: ASN-1 and ASN-2 are implemented. This assignment establishes the main research workspace, its first meaningful interactions, and the visual language for later work.

## Primary objective

Transform SIGMA from a project-document viewer into a **task-oriented research application** with two distinct screens:

1. **Home:** The launcher for choosing/opening a project. Preserve the established SIGMA branding and refined copy.
2. **Project page:** A separate navigable page that becomes the actual working environment. The **project name and description are prominent at the top**, with a **strategy pool** below. A small, unobtrusive **Close project** control returns to Home.

Do not merely append the strategy pool beneath the home page's project-opening form. Treat opening a project as navigation to a different screen, with clear route semantics and sensible browser back/forward behavior.

## Design responsibility: deliberate first-pass product design

**Invest more thought in the user experience before implementing.** The goal is a simple, elegant, aesthetic interface that earns immediate human acceptance because it is legible, predictable, restrained, and helps people do the next meaningful task.

This is not an instruction to generate a generic AI dashboard. Avoid UI slop: oversized gradients, gratuitous cards, decorative badges, redundant headings, indiscriminate icons, noisy toolbars, cramped controls, and placeholder metrics. Do not let buttons dominate the research content.

Make well-chosen first passes rather than rapidly assembling arbitrary components and polishing afterward. Consider information hierarchy, typography, spacing, empty states, interaction affordances, accessibility, and the difference between primary and contextual actions. Maintain continuity with ASN-2's muted green palette and editorial restraint, but adapt the layout appropriately for a full research workspace.

Before coding, briefly record the proposed interaction model and key visual decisions in your own working notes or a concise design note; do not create a lengthy speculative design document. You own the detailed design, not a pixel-by-pixel prescription from this assignment.

## Project page: initial strategy pool

The project page should show:

- Project title and its actual description/problem statement at the top.
- A **Strategy pool** section, initially empty for the RH project.
- Two discoverable, visually restrained next actions: **New strategy** (user writes an idea) and **Generate strategy** (eventually agent-generated).
- A thoughtful empty state that explains the first step without suggesting research has already occurred.
- A small **Close project** action, visually secondary and away from the main task flow, returning to Home.

**New strategy must work end-to-end**: let the user supply a concise title and hypothesis/approach, save it through the shared application layer, and see it in the pool after reopening. This is the first persistent strategy record. Use a minimal defensible model; do not prebuild the full genealogy or evaluation engine.

**Generate strategy must not fake AI work.** With no agent runtime in place, show a clear unavailable/coming-later state or disable it with an accessible explanation. Keep it visible as an anticipated task, not an active fake operation.

## Strategy contextual commands

Each strategy has a compact, discoverable action menu with the following hierarchy:

```text
Strategy actions
├── Schedule
│   ├── Promote
│   ├── Demote
│   ├── Pause / Resume
│   └── Remove
├── Report artifact
│   ├── Audit
│   └── Other artifact types (to be specified)
└── Fork
```

The menu should feel like a natural part of the strategy row/detail view, not a forest of permanent buttons. It must be keyboard accessible and usable on a narrow viewport.

**Implementation boundary:** This assignment establishes the menu and its understandable affordances, not the entire research engine. Do not fake scheduling, agent-generated audits, or autonomous forks. Commands without implemented semantics must be visibly unavailable with a brief explanation; do not silently do nothing or create misleading success states. In particular, `Report artifact → Audit` is a future durable report containing an explicit investigation-step record, evidence/tests, and answers to rubric questions. Do not present hidden model chain-of-thought as an artifact. Other artifact types were discussed conceptually but are not specified here; do not invent them.

If a modest subset of commands can be made genuinely functional without expanding the scope or compromising the first-pass design, exercise judgment, but **persistent manual strategy creation and the distinct project page take precedence**. Do not build a scheduler, evaluator, agent runtime, or report generator as part of this assignment.

## Engineering and data integrity

- Preserve existing project opening, identity, and event history; keep the home page and CLI/scenarios operational.
- Add strategy persistence through the **same typed application services** used by the UI, CLI, and scenarios. Avoid frontend-only state masquerading as saved research.
- Consider the current versioned `project.json` design: introduce any necessary schema evolution deliberately, protect existing projects, and avoid unsafe overwrites or loss of history. Explain any migration choice and its limitations.
- Keep strategy IDs stable and distinguish user-authored strategies from later agent-generated ones.
- A new strategy should be visible after closing/reopening the project. Error handling should preserve the user's entered text where feasible.
- Maintain accessibility, focus behavior, mobile layout, and consistent route/navigation behavior.

## Verification and delivery

1. Use a real browser to navigate Home → open RH → Project page → close → Home, including back/forward and narrow viewport checks.
2. Create a manual strategy through the UI; verify it persists after reload and reopen.
3. Exercise the contextual command hierarchy; confirm unavailable actions are clearly explained and cannot imply success.
4. Extend executable scenarios for strategy creation, persistence, validation, and safe failure; exercise API and CLI integration as appropriate.
5. Run `./sigma test`, frontend typecheck/build, and real browser checks. Report actual results, including any incomplete interactions, in `docs/STATUS.md`.
6. Commit and push with a **specific, accurate commit message** describing the project page and strategy pool work.

## Scope discipline

Favor a coherent, polished and genuinely usable small vertical slice over a broad mockup. No autonomous generation, scheduler, evaluator, audit production, speculative dashboards, remote hosting, or paid API usage. Preserve the existing SIGMA visual identity and build a foundation we can extend incrementally.
