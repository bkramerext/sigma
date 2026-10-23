# A17.7.1 — UI alignment and dialog refinements

Status: **ready for implementation; unverified**. Follow-up to A17.7. Read `docs/HUMAN-AI-INTERACTION.md`, `docs/ASSIGNMENT-A17.7.md`, and current `docs/STATUS.md` before implementation. Preserve A17.6 research semantics and A17.7 corrections.

## Required corrections

1. **Settings dialog header actions:** Remove Save and Cancel from the bottom/footer of the Settings dialog. Render **Save** and **Cancel** as underlined text actions beside the **Settings** header/title, aligned to the **bottom/baseline** of the heading, rather than as conventional filled/outlined buttons. Preserve validation, dirty-state behavior, keyboard accessibility, save pending/disabled state, cancellation and error recovery. Ensure the controls remain reachable on narrow screens. This applies to Settings, not the Export Project dialog (which retains its copper-filled bottom Download action per A17.7).
2. **Markdown / Edit icon spacing:** Tighten the horizontal gap between the Markdown symbol and pencil/Edit action to match the normal spacing rhythm of adjacent title actions. Do not change icon scale, hit targets, hover styles or tooltips to accomplish this. Verify the actual rendered spacing in Chrome.
3. **Header/title underlined-action baseline:** Bottom-align underlined actions across all applicable header and title rows, **especially the Strategy title**. Use shared flex/grid alignment rather than per-control pixel nudges. Audit Project, Strategy, Research Session and dialog header rows where underlined actions sit beside a title; ensure consistency at normal and narrow pane widths, without overlap or unintentional wrapping. Keep the existing intended placement of actions (including stacked session Resume/Remove from A17.7).
4. **ChatGPT connection dialog spacing:** Introduce a visible, consistent horizontal gap between the **Manage usage** link and **Disconnect** action. They must not appear run together. Preserve both actions' behavior, focus states and narrow-screen usability.

## Verification and exit

- Add or update focused UI regression coverage for each correction. Run relevant frontend checks and `./sigma test`.
- Inspect the **actual Chrome-rendered** Settings header/actions, Markdown/Edit icon pair, Strategy title actions, and ChatGPT connection dialog. Check normal desktop and narrow/mobile viewport widths; verify geometry/baseline/spacing and keyboard focus.
- Capture/review screenshots; document commands, results, screenshots and any limitations in `docs/STATUS.md`. Do not mark complete based on source inspection or unit tests alone.
- This is a targeted UI follow-up. Do not expand it into the A17.8 agentic-quality investigation or bypass the separate A17.8 final acceptance gate.
