# A17.7.1 — UI alignment and dialog refinements

Status: **ready for implementation; unverified**. Follow-up to A17.7. Read `docs/HUMAN-AI-INTERACTION.md`, `docs/ASSIGNMENT-A17.7.md`, and current `docs/STATUS.md` before implementation. Preserve A17.6 research semantics and A17.7 corrections.

## Required corrections

1. **Settings dialog header actions:** Remove Save and Cancel from the bottom/footer of the Settings dialog. Render **Save** and **Cancel** as underlined text actions beside the **Settings** header/title, aligned to the **bottom/baseline** of the heading, rather than as conventional filled/outlined buttons. Preserve validation, dirty-state behavior, keyboard accessibility, save pending/disabled state, cancellation and error recovery. Ensure the controls remain reachable on narrow screens. This applies to Settings, not the Export Project dialog (which retains its copper-filled bottom Download action per A17.7).
2. **Markdown / Edit icon spacing:** Tighten the horizontal gap between the Markdown symbol and pencil/Edit action to match the normal spacing rhythm of adjacent title actions. Do not change icon scale, hit targets, hover styles or tooltips to accomplish this. Verify the actual rendered spacing in Chrome.
3. **Header/title underlined-action baseline:** Bottom-align underlined actions across all applicable header and title rows, **especially the Strategy title**. Use shared flex/grid alignment rather than per-control pixel nudges. Audit Project, Strategy, Research Session and dialog header rows where underlined actions sit beside a title; ensure consistency at normal and narrow pane widths, without overlap or unintentional wrapping. Keep the existing intended placement of actions (including stacked session Resume/Remove from A17.7).
4. **ChatGPT connection dialog spacing:** Introduce a visible, consistent horizontal gap between the **Manage usage** link and **Disconnect** action. They must not appear run together. Preserve both actions' behavior, focus states and narrow-screen usability.

5. **Outcome Markdown toggle:** Add a Markdown control to the **Outcome** content because outcomes may contain mathematical notation. Follow the existing Markdown/plain-text view interaction and visual conventions used elsewhere in SIGMA, including accessible label, tooltip, focus, and consistent icon spacing. Render mathematics legibly and safely. Preserve the underlying outcome text and its saved meaning; switching views must not silently rewrite the research result or call a provider without explicit authorization. Test mathematical notation, ordinary prose, missing/legacy outcome text, and toggling back.
6. **Export dialog filename and action placement (A17.7 correction):**
   - The editable filename stem is **still visibly truncated** (for example, `sigma-Maximum-Regions-Formed-by-`). Fix the **actual usable input width and layout**, not just its CSS minimum width. Use available dialog width, avoid a narrow fixed column, keep the derived extension visible, and support full-name inspection/editing (including horizontal caret navigation for names longer than the viewport). Verify with the full Maximum Regions project name in the actual browser.
   - **Cancel must flow immediately after the Export Project title** on the same header row, bottom-aligned to the title, not positioned at the far edge by `space-between` or auto margins.
   - The copper-filled **Download** button remains at the bottom of the dialog but must be **left-aligned**, not right-aligned.
   - Preserve Project Audit's disabled JSON (.json) format, report formats, edited stem across format switches, and existing download/open-tab behavior.

## Verification and exit

- Add or update focused UI regression coverage for all six corrections. Run relevant frontend checks and `./sigma test`.
- Inspect the **actual Chrome-rendered** Settings header/actions, Markdown/Edit icon pair, Strategy title actions, and ChatGPT connection dialog, Outcome Markdown control (including math), and Export dialog with the long Maximum Regions filename, title-adjacent Cancel, and left-aligned Download. Check normal desktop and narrow/mobile viewport widths; verify geometry/baseline/spacing and keyboard focus.
- Capture/review screenshots; document commands, results, screenshots and any limitations in `docs/STATUS.md`. Do not mark complete based on source inspection or unit tests alone.
- This is a targeted UI follow-up. Do not expand it into the A17.8 agentic-quality investigation or bypass the separate A17.8 final acceptance gate.
