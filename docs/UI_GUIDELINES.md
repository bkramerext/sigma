# SIGMA UI Guidelines (draft, pending visual acceptance)

## Purpose and precedence
Preserve SIGMA's approved copper-and-black research-workbench identity. This document records established decisions from SIGMA design conversations and source inspection; it is not permission to redesign accepted screens. Where code and an explicit owner decision conflict, flag the discrepancy for review.

## Visual language
- Deep navy/near-black backgrounds, burnished metallic copper accents, restrained highlights. Never replace copper with bright yellow/gold. Cool blue is the complementary accent, especially for research agents.
- Preserve approved Home artwork and its composition; do not redraw or replace it.
- Use the shared copper control styles in `frontend/src/copper-controls.css` for common actions and status elements. Prefer shared tokens/components over one-off overrides.
- Inter for UI text; serif headings where already established. Preserve readable hierarchy, contrast, and responsive spacing.
- Distinguish selected, enabled, disabled, pending, warning, connected, and actively working states through more than color alone.

## Navigation and page structure
- Home Recent/Stock Projects is a copper-styled toggle. Recent shows at most four; Stock shows all configured samples.
- Home sign-in matches the New Project visual language. Approved copy: “Sign in with approved Gmail account to access projects.” Do not add redundant “Sign in” labels.
- Project title is editable inline; strategy and session sections remain distinct. Sessions display newest first without changing underlying numbering.
- Current Understanding starts expanded; use a recognizable disclosure chevron and prominent heading. Do not repeat the saved-session count in its header.

## Actions and controls
- Primary, secondary, text-link, destructive, and disabled actions should be consistent across Home, Project, Strategies, Settings, and export surfaces.
- Use clear button labels, including Start session #n and Cancel. Do not create sessions or call providers on Cancel.
- Strategy actions include New/Generate, Fork/Remove as underlined links, enable/disable, and title-based collapse.
- The Google and ChatGPT connection controls must align in size, placement, styling and copy. A sign-in status pill initiates sign-in directly, without an intermediate duplicate sign-in button.
- Header About uses a textual “About” control where needed to avoid collisions with authentication pills. Preserve its dialog.

## Dialogs, forms, and export
- Consistent dark panels, copper borders/selected accents, padding, typography, focus states and action placement.
- Project Settings uses Main/Limits tabs; keep field labels, hints, input dimensions, and selected-state semantics consistent.
- Export/Report uses type selection, format dropdown and Download. Preserve user selections where appropriate; errors must not silently navigate into Markdown or another result view.
- Paper preflight must distinguish genuine stale research from volatile display-only changes, and report provider usage accurately.

## Research states
- Strategies are persistent, narrow research ideas; sessions are individual attempts. A failed session must not erase its strategy or evidence.
- Show outcome and conclusion distinctly, with explicit unresolved/paused states and no implication of proof from computational evidence.
- Before starting a subsequent session, distinguish enabled-strategies-only from including prior sessions. Clearly surface context/budget limits and recovery actions without bypassing safeguards.
- Provider/model availability, Google identity, and sponsored-service status are separate signals; a connected identity alone does not imply model availability.

## Notifications and accessibility
- Network-bound failures need a toast and appropriate UI recovery, except expected unauthenticated startup 401 responses.
- Toasts expire after 60 seconds, exit downward, and allow smooth reflow of the remaining stack; honor reduced-motion preferences.
- Provide visible keyboard focus, meaningful labels, non-color status cues, responsive layouts, and accessible disclosure/dialog semantics.

## About
- Explain SIGMA without inflated claims: strategies propose, sessions investigate, outcomes answer, reports communicate.
- Preserve the multi-agent diagram: copper for project/strategy/session structure, metallic blue for Investigator/Skeptic, hover descriptions and responsive accessibility.
- Show version/build details and a collapsible repository link.

## Audit findings to validate visually
1. **Legacy global palette risk:** `frontend/src/style.css` begins with light green/beige global defaults (`:root`, buttons, links, inputs, focus). Check whether any fallback, error, modal, or unscoped control exposes these on dark SIGMA surfaces. Do not remove defaults blindly.
2. **Token drift:** `workspace.css` defines `--workspace-bg: #050c12`, `--workspace-line: #27313a`, while `strategies.css` overrides the same workspace tokens with `#04101b` and `#233c4b`. Determine whether this is intentional page layering or accidental divergence; consolidate if visually inconsistent.
3. **Copper color drift:** shared `copper-controls.css` uses muted copper (`#a96548`, `#cd9270`), while `strategies.css` uses brighter gold-like gradients (`#f0ca94`, `#bb8247`) and `project-settings.css` uses `#edc38d` headings. Review side-by-side against the burnished-copper decision.
4. **About control drift:** `copper-controls.css` defines a 32px circular About action while `workspace.css` overrides project About to a rectangular text button. Verify Home/Project coherence and collision avoidance; standardize intentionally.
5. **Header layout fragility:** `workspace.css` uses a fixed three-column/two-row header grid and a 240px ChatGPT status cap. Test narrow desktop/mobile widths and long account/model labels for overlap and clipping.
6. **Component-specific control styles:** `project-settings.css` and `strategies.css` define distinct form/control treatments. Audit their actual rendered states alongside Home and shared controls.
7. **Toast implementation verification:** `request-toast.css` defines stack appearance but not expiry/exit animation; confirm whether animation/lifetime lives in TSX or another stylesheet, and track issue #215 rather than duplicating it.

## Review procedure
Inspect Home (signed out/in), Recent/Stock, New Project, Project header, Strategies, Sessions, Current Understanding, Settings tabs, Report/Export, About, connection states, error/toast, and narrow viewports. Record screenshots, observed versus expected state, source selectors, and reproducible acceptance checks. Do not turn speculative CSS drift into a confirmed visual defect without rendering verification.
