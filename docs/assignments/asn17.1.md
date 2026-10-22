# A17.1: Project and Strategy Titles, Disclosure, and Research Controls

**Status:** Ready for Codex. **Priority:** UI correction and consistency pass after A17. **Scope:** Surgical changes to the existing application; no redesign.

## Intent

Restore the established SIGMA navy/copper styling and reduce UI clutter. Project and Strategy are consistent collapsible sections with editable **titles**. The **Strategies** section has compact top-level Play/Pause controls for the research process. Preserve all working A17 research-session behavior, backend safeguards, data, and artifacts.

**Read** `AGENTS.md`, `docs/PROJECT.md`, `docs/DECISIONS.md`, `docs/STATUS.md`, `docs/HUMAN-AI-INTERACTION.md`, and A17 first. Inspect the actual current UI and existing components before editing. Do not interpret prior generated mockup images as approved design specifications. Existing application styling is authoritative.

## UI changes

1. **Project header:** Show `Project: <title>` as the clickable top-level disclosure header. Put a small pencil control beside it for editing the **title**, without toggling collapse. Remove the redundant truncated project description to the right of the header. The full problem/description stays in expanded content. Retain existing project actions and editors; do not duplicate the description.
2. **Strategy headers:** Each individual strategy has a clickable disclosure header `Strategy: <title>` with a small pencil control for editing the **title**, without toggling collapse. The full strategy description stays inside expanded content. Keep individual strategy collapse states independent. Remove previous/next navigation arrows, not disclosure chevrons. No extra explanatory copy or Add strategy button; existing New Generate remains the creation entry point.
3. **Strategy titles throughout workflow:** Titles are explicit persisted fields, not computed from the description. Support them in strategy generation drafts, review, explicit Save strategy, subsequent edit, reload, and display. Encourage concise, bounded-investigation titles in generation instructions and validation. Preserve existing strategy IDs, descriptions, revisions, provenance, artifacts, and prior strategies. For legacy strategies without a title, use a deterministic, non-destructive display fallback; do not overwrite the description or silently migrate history.
4. **Top-level Strategies header:** Add small, existing-style **Play** and **Pause** icon controls aligned to its right. These are for the overall research process, **not** controls on each strategy. No strategy-selection dropdown or giant Start investigation button. SIGMA, not the user, selects which eligible strategy to investigate. Reuse A17's authoritative session start/pause/resume state, budgets, identity checks, idempotency, error toast and reconciliation. Do not implement an unbounded scheduler or automatic multi-session chaining in this UI correction. Play should initiate/resume a single bounded session through the existing backend; Pause should pause the active session. If autonomous selection is not yet supported, add only the minimal deterministic selection/validation needed and document the rule; never silently select a different strategy while one is actively bound. Disable unavailable actions truthfully. Do not invent model costs or completion claims.
5. **Research session label:** Use compact `Session #N` for an existing session, retaining the A17 status/artifacts view and durable session identity. Avoid inventing new panels or horizontal pane arrangements. Preserve existing page flow, widths, spacing, hierarchy, and responsive layout.
6. **Styling:** Reuse existing classes/tokens and icon sizes. Do not change palette, borders, typography, general spacing, navigation, or global layout. No new mockups, dashboard cards, commentary text, or other UI features.

## Interaction and correctness

- Pencil click and keyboard activation enter title editing without collapsing; Save persists; Cancel restores previous title. Blank/invalid title is rejected with actionable feedback. Failed save leaves user content intact and uses existing toast/error handling.
- Disclosure controls remain keyboard accessible with accurate expanded state. Editing titles must not lose unsaved description edits or change research-session strategy snapshots silently; preserve A17 guards and require explicit handling of revision mismatch.
- Play/Pause reflect actual backend state, including pending, completed, stopped, interrupted, and disconnected states. Never claim a provider call was canceled or paused without confirmation. A17's bounded call cap remains intact.
- Preserve existing New Generate, strategy editing, Markdown display, project controls, artifacts, and session history.

## Verification and delivery

Add focused tests for project/strategy title editing, persistence and legacy fallback; independent collapses; no click propagation from pencil; generation-to-save title flow; Play/Pause state and idempotency; errors and reconciliation. Perform a **real browser** visual/interaction check against the existing UI at desktop and narrow widths. Run `./sigma test` and frontend typecheck/build. No paid provider calls. Record actual outcomes in `docs/STATUS.md`.

**Deliver:** Commit and push directly to `main` without PR, report commit SHA, tests actually run, and remaining limitations. Keep changes limited to this assignment.
