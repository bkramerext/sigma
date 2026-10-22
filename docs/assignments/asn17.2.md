# A17.2: Workspace Interaction Consistency and Layering

**Status:** Ready for Codex. **Priority:** Focused UX correction after A17.1. **Scope:** Existing UI only; no redesign.

## Intent and authority

Apply SIGMA's established UI conventions consistently. This assignment records the user's observed A17.1 feedback, not a request for a new layout or additional features. Read `AGENTS.md`, `docs/HUMAN-AI-INTERACTION.md`, `docs/PROJECT.md`, `docs/DECISIONS.md`, `docs/STATUS.md`, A17 and A17.1. Inspect the actual running workspace and current source before changing it. Preserve the approved navy/copper styling, data, research history, and A17/A17.1 functionality.

## Required changes

1. **Sessions are not collapsible.** Remove session-row disclosure/collapse behavior and its chevrons. Keep the existing `Sessions` heading, singular/plural count, `SESSION` table header, `Session #N` rows, statuses, and all session activity/artifact details available and inspectable. Do not hide information previously accessible through expansion; use the established table/detail presentation without introducing a nested bounded box or a new pane. Preserve session ordering and durable identity.

2. **Header control flow:** Header actions should follow their associated heading/content naturally, not start at the left edge of a group pinned to the far right of the screen. Reuse existing inline spacing/alignment conventions, including responsive behavior. In the **Strategies** header, the static `n strategies` text is followed immediately by a small visual **divider**, then the **Play/Pause** controls, in that order. Keep **New / Generate** in the same header flow before the count. Avoid absolute positioning, large spacer gaps, or a separate action bar. Check Project and Sessions header alignment for consistency where applicable.

3. **New / Generate reveals its workspace.** Clicking either **New** or **Generate** Strategy automatically expands the Strategies section if it is collapsed, then presents/focuses the appropriate creation interface. Do not leave the user in a hidden mode. Keep the existing draft, generation, acceptance and cancellation behavior.

4. **One editing/creation mode at a time.** Whenever the user enters a project/strategy **edit**, **New**, or **Generate** mode, disable *conflicting* buttons and mode-entry actions elsewhere in the workspace so a second mode cannot be opened concurrently. Keep the active mode's Save/Cancel, necessary inputs, accessibility controls, and error/retry/exit affordances operable. Restore other controls on successful save, cancel, or terminal exit. Preserve unsaved content on failures. Distinguish UI modes from an already-running backend research request: do not falsely imply provider cancellation or interrupt ongoing research merely by disabling controls. Apply the guard consistently to keyboard and pointer interactions, including rapid successive clicks; avoid trapping the user in a mode. Controls should appear disabled and have truthful accessible disabled state.

5. **ChatGPT connection dialog stacking:** The connection dialog/popover must render above all workspace controls, including Project controls. Fix the actual stacking-context/portal/z-index issue, not by restyling the dialog or globally raising arbitrary controls. Ensure backdrop, focus, pointer interaction, Escape/close behavior and small-screen placement still work; underlying controls must not visually cover or receive clicks through the dialog.

6. **Back navigation label:** Display **Back to Home** immediately to the right of the existing Back icon. Preserve its actual navigation behavior, keyboard access, focus styling, and responsive layout.

## Constraints

- No unrelated layout or styling changes, new controls, modal workflows, research engine changes, persistence migrations, or extra features.
- Keep A17.1 inline Project/Strategy title editing, strategy table layout, Sessions placement below Strategies, AI activity pulse, and existing Play/Pause backend semantics.
- Preserve project identity, drafts, strategy provenance, research session artifacts and history; no paid provider calls for verification.
- If a control's enabled state depends on backend state, reflect actual state rather than inventing success, cancellation, or readiness. Handle request failures with existing toast and recovery conventions.

## Verification and delivery

Add focused regression tests for: noncollapsible Sessions with details still accessible; Strategies header ordering and responsive control flow; New/Generate auto-expansion and focus; cross-workspace mutual exclusion of edit/new/generate modes including rapid click, cancellation, save failure and keyboard entry; connection dialog stacking and blocked underlying interaction; Back to Home label/navigation. Test that Play/Pause, session history/artifacts, and provider-activity pulse remain intact.

Run `./sigma test`, frontend typecheck/build, and **real-browser** desktop and narrow/mobile interaction checks. Report actual tests and any limitations in `docs/STATUS.md`. Commit and push directly to `main` without a PR, and report the commit SHA. Keep the implementation limited to A17.2.
