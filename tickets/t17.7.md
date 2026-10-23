# A17.7 — UI corrections and regression hardening

Status: **ready for implementation; not yet verified**. This is a corrective increment based on observed browser defects after A17.5/A17.6. Do not substitute source inspection or passing unit tests for rendered-browser verification.

Read `docs/HUMAN-AI-INTERACTION.md`, `docs/ASSIGNMENT-A17.5.md`, `docs/ASSIGNMENT-A17.6.md`, and current `docs/STATUS.md` before changing code. Inspect the actual React/CSS structure and existing browser checks. Preserve current research, history, exports, and A17.6 objective/outcome/assessment semantics. Do not call paid providers for UI regression tests.

## Observed failures and exact corrections

### 1. Project header layout

Current browser rendering puts the Back arrow and caption in a vertical stack alongside the project title, crowding/overlapping the title. **Required geometry:**

- **Row 1:** full project title, starting at the intended project-header left alignment, unobstructed.
- **Row 2, beneath the title:** Back arrow icon followed **immediately to its right** by the caption **Back to home**, on the same horizontal baseline/row.
- The title must not share its row with the Back control. No title overlap, clipping, or hover hint obscuring it. Preserve responsive behavior.
- Remove/override the earlier incorrect `.project-back-stack` column layout; do not patch the problem with arbitrary pixel offsets.

### 2. Icon-only button tooltips

- Audit **every actionable icon-only button** in Project, Strategy, Research Session, text-view, and relevant dialog controls. Hover must display a meaningful, prompt, visible description; keyboard focus must expose an equivalent accessible name and a discoverable hint.
- The earlier change `.sigma-render-tooltip { display: none !important; }` suppressed the custom Markdown tooltip in favor of native `title`. Do not assume that constitutes a working tooltip. Implement a consistent, viewport-aware tooltip approach, including near edges, overlays and narrow panes, without clipping or covering important headings.
- Test actual pointer hover, focus, and visible tooltip text in Chrome. Inspect stacking contexts, clipping ancestors and portal placement as needed. Do not merely assert the presence of `title` attributes.

### 3. Consistent icon hover styling

- **Project Document / Export** and **Settings** icon buttons must use the same hover treatment as the adjacent **Edit pencil**: background, foreground/icon color, border, focus-visible treatment and transitions.
- Apply shared classes/tokens rather than isolated one-off overrides. Check normal, hover, focus and disabled states in the actual UI.

### 4. Settings dialog scroll containment

- Settings → **Limits** extends below the viewport. Trackpad/wheel scrolling currently scrolls the underlying page instead of the modal.
- Constrain dialog height to available viewport; make the content body independently vertically scrollable; keep heading/tabs and actions reachable/visible as appropriate.
- Lock underlying document/page scroll while the modal is open; restore prior behavior on close, including Escape and error paths. No scroll leakage at scroll boundaries.
- Browser acceptance: with a short desktop viewport and a narrow/mobile viewport, open Limits, scroll by wheel/trackpad-equivalent input to the final setting, change it, and confirm the background page has not moved. Repeat on other Settings tabs.

### 5. Markdown logo

- The Markdown control must display a recognizable **standalone, larger Markdown symbol**, visually comparable in size to the neighboring pencil.
- **No visible rectangular outline or box in the SVG itself.** The current SVG draws a `rect`; remove that path, not just button CSS.
- Preserve a normal-sized invisible hit target, consistent hover/focus treatment, accessibility and tooltip. Verify visually at normal scale.

### 6. Session summary text alignment

- In every Research Session card, the **outcome line** and **cycle/call progress line** must start at the exact left edge of the **Session #N** text, not at the chevron or left card edge.
- Use a shared layout column/grid anchor for the title and summary, **not** a guessed `margin-left: 21px`. Verify expanded/collapsed, short/long text, and narrow panes.

### 7. Lifecycle status belongs in the summary

- Move the colored dot and lifecycle label (e.g. **Ended**, Running, Stopped, Failed) out of Session Details and into the always-visible Session summary, including when collapsed.
- Do not duplicate lifecycle status in Details. Keep it distinct from research outcome and progress; preserve meaningful status colors and accessible text.

### 8. Narrow session header and action placement

- Narrow panes currently wrap **Resume** into an awkward extra row while **Remove** remains beside the title.
- **Required layout:** chevron + Session #N and summary content occupy the left column; **Resume directly above Remove** in a right-aligned, vertically stacked action column whenever both are present. When Resume is absent, Remove stays in the action column. Stop/other applicable actions should use the same intentional action area without accidental wrapping.
- Outcome, lifecycle and progress align to the Session #N text column. No overlap, clipped labels, or unintended line wraps at the actual research-pane width. Preserve keyboard and screen-reader order.

### 9. Tests must not pollute real Recent projects

- After restart, the user's Recent list displayed multiple unavailable `edits.sigma` entries. Source inspection found `tests/strategy_changes.py` creates temporary `edits.sigma` projects and calls `open_project`, which records them in the normal application Recent index when the test does not isolate `SIGMA_STATE_DIR`.
- Fix the root cause: **all tests, browser fixtures, and test subprocesses that can record Recent entries must use isolated temporary app state and managed project roots**. No test may write to the user's default Recent index, authentication state or actual project directory. Review other test entry points for the same leak.
- Add a regression that runs the affected workflow with a sentinel external Recent index and asserts it remains byte-for-byte unchanged. Verify temporary test projects never appear in the normal app's Recent list. Do not automatically delete or alter the user's existing Recent entries as part of the fix.

### 10. Export Project dialog (previous A17.5 contract was not fully realized)

The observed dialog has **Create** and **Cancel** in the header, a wide Format dropdown showing HTML while Project Audit is selected, and a filename stem cut off before the separate `.json` extension. Implement the previously specified design precisely:

- **Header:** **Export Project** title, with **Cancel** aligned to the **bottom/baseline of the title**, not floating mid-title. **No Create or Download in the header.**
- **Footer:** prominent primary **Download** button at the **bottom of the dialog**, using SIGMA's traditional **copper-filled** primary button treatment. Keep Cancel in the header as requested in this correction (this supersedes the A17.5 instruction to put Cancel at the bottom).
- **Export type:** Project Audit / Research Report radios. Preserve selection semantics and keyboard accessibility.
- **Format:** always show a **compact-width** dropdown. When Project Audit is selected, it **displays JSON (.json)** and is **disabled**. When Research Report is selected, it enables **Text (.txt)**, **HTML (.html)** and **LaTeX (.tex)**; default Text. Switching back to Audit must visibly show JSON, not the previously chosen report format.
- **Filename:** editable, sanitized project-derived stem must have sufficient usable width to see and edit the **full filename**, not the visibly truncated short input shown in the screenshot. Keep the automatically derived extension beside it and fully visible. Use responsive sizing/appropriate horizontal scrolling or selection behavior for genuinely long names, without clipping the extension or dialog. Changing type/format preserves the edited stem. Never append two extensions or allow an entered extension to override the selected format.
- **Open in browser tab:** checkbox default off, retains A17.5 behavior. Clicking Download initiates the selected download and optionally opens a viewable tab; blocked popup, failed request, cancel, busy state and Escape remain recoverable. Keep the underlying JSON audit/report contents and safe escaping unchanged.
- Test all four output types, downloaded filenames, filename edits/type switches, checkbox on/off, browser tab behavior, error handling, and actual visual layout at desktop and narrow viewport sizes.

## Implementation discipline

1. **Fix layout at its structural cause**, not by accumulating CSS overrides. Consolidate obsolete rules introduced by previous direct edits; inspect specificity and actual DOM geometry.
2. Preserve the project/session semantics established in A17.6. In particular, a positive objective outcome, lifecycle state, and strategy assessments remain separate.
3. Keep the existing workspace/panes; do not add new UX or redesign unrelated screens. All network-bound errors must use a visible toast and leave the UI in a recoverable state.
4. Add focused regression tests for every issue above. Visual/interaction defects require **real Chrome Playwright checks with geometry, scroll, hover, focus and/or screenshots**, not only mocked component assertions. Include a viewport comparable to the user's narrow research pane, plus desktop and mobile.
5. Save before/after screenshots for project header, tooltip/icon row, Settings Limits at bottom, session card, and Export Project dialog. Review screenshots, not merely their successful capture. Report any remaining mismatches honestly.

## Completion gate (UI and isolation only)

A17.7 closes the ten UI/test-isolation defects. **A17.8 owns the deferred agentic-quality and integrated A17.6 acceptance work**; do not conflate them with A17.7's UI completion.

After implementing A17.7:

1. Run `./sigma test` (including Ruff, Pyright, frontend typecheck/build), relevant API/unit tests, and real Chrome UI checks with a mock provider.
2. Inspect the final browser UI against all ten A17.7 issues, at representative pane/viewport sizes, with screenshots and interaction tests. Ensure changes do not regress the already implemented A17.6 contracts, but **do not conduct the deferred real-agent quality evaluation here**.
3. Update `docs/STATUS.md` with exact commands, outcomes, screenshot paths, unverified items and remaining defects. Do not mark A17.7 complete until its checks actually run and pass.
4. Report A17.7 for human review, then execute A17.8 before declaring the A17 sequence complete and starting A18/A19/A22.
