# A17.5 — Project report and regression stabilization

Status: **assigned to Codex; not yet implemented or verified.**

Read `docs/HUMAN-AI-INTERACTION.md` and current `docs/STATUS.md` before implementation. Inspect current code; do not assume A17.4 documentation still describes the current UI.

## Feature: Project report

- Add a **Report** icon button (document/file-text icon) to the Project title actions, alongside Download and Settings. Provide accessible label, keyboard focus, and visible-on-hover native title tooltip.
- Clicking opens an accessible modal **Report** dialog with a suggested editable filename (derived safely from project name), required format selection: **Plain text (.txt), Markdown (.md), HTML (.html), LaTeX (.tex)**, and a checkbox **Open in new browser tab** (default unchecked). Show **Create** and **Cancel** buttons in the application's usual dialog button styling (Create is the primary action); show failure feedback and preserve dialog state on errors.
- Generate a human-readable research **report**, not a raw project archive/export. Include project title/problem, strategies (including their approaches), sessions in durable order, execution status distinct from outcome, outcomes and caveats, artifact claims/methods/assumptions/evidence status, objections, decisions and open obligations. Preserve meaningful chronology, provenance and explicit provisional/unverified distinctions. Do not fabricate findings. Gracefully handle projects without sessions or strategies, legacy records, and missing optional fields.
- Ensure each format is actually usable: valid UTF-8 plain text; well-structured Markdown; standalone escaped HTML with safe rendering (no unsanitized model text as executable HTML); compilable/escaped LaTeX document including mathematical content where feasible. Prevent injection and unsafe filename/path behavior. Prefer deterministic report generation from saved data, no model calls or billing.
- Download the chosen file using the chosen name and extension. When the checkbox is checked, also open the generated report in a new tab, avoiding popup blockers by opening on the initiating user gesture, with safe object URL lifetime/cleanup and graceful fallback when the browser blocks the tab. A download must still work independently. Test this behavior in Chrome; choose practical handling for plain text/Markdown/LaTeX display in the tab.
- Keep the report dialog visually consistent with Settings/Download, usable on narrow screens, with Escape, focus management, cancel and error recovery.

## Stabilization: assistant direct edits after A17.4

The assistant committed the following directly to `main`, **without local build/browser verification**. Codex owns integration review, correction and regression coverage. Inspect Git history/current tree rather than blindly applying this list; work may have changed concurrently.

1. Session Play confirmation moved inline to underlined **Start session #N / Cancel**, replacing the controls. Ensure numbering is from the durable sequence counter, not `max(existing sessions)+1` after deletion.
2. Session title row uses inline underlined **Stop / Resume / Remove**. Stop is immediate and resumable (`stopped`); natural completion is `ended`; legacy `completed` remains readable. Stopped time should not count against the deadline. Check interrupted-provider-attempt semantics and avoid unintentional double billing/replay.
3. Deterministic role context continuation from saved research records (recent full artifacts, obligation ledger, question, strategy and Skeptic pending Investigator output), fail-closed size limit, recorded provenance. Verify correct reconstruction after stop/resume/restart and guard context budget.
4. Session subtitle displays color-coded outcome (without `Outcome:` prefix), independent of lifecycle status. Session header uses **SESSION / DETAILS** at **20/80** width on desktop, responsive on mobile. Verify CSS cascade and real rendered geometry.
5. Fork composer title says **Forked strategy**; strategies no longer expose manual stage in table or controls. Preserve legacy stage data/history for backward compatibility; audit whether stage is still used in current workflow.
6. Strategy kebab menu removed; **Fork / Remove** appear as underlined actions immediately right of the title pencil. Remove matches Fork color. Drag grip moved from upper-right to upper-left with adequate spacing, accessible keyboard drag behavior.
7. Hover tooltip regression: assistant started restoring native `title` attributes for strategy pencil/Fork/Remove/grip (commit `2db3f97`), but **the broader audit is unfinished**. Audit all actionable Project, Strategy and Session icon buttons and relevant controls for meaningful native hover descriptions, retaining accessible names.
8. Project Settings/Download positioning, session title alignment, lifecycle CSS, and related direct edits since A17.4 need a consistency pass.

Representative direct-edit commits: `f540d783`, `7cc2874`, `0f5d532`, `c2de6a5`, `800a116`, `d4b39f9`, `895d0f4`, `dda9d54`, `31c9cab`, `64e95d9`, `0265cd8`, `57bc81c`, `9a5b6d5`, `e39683d`, `4250496`, `49bc713`, `470ed4a`, `5df30be`, `ac2d988`, `ccbc379`, `2db3f97`.

## Required verification and completion

- **First stabilize existing tests** against intended current behavior; distinguish stale expectations from real bugs. Add/repair unit, API, session lifecycle, project serialization, report-format and escaping tests. Test zero sessions, removed sessions and monotonic session numbering, interrupted calls, resume/restart, error/toast recovery, legacy records, output filename safety and special-character/LaTeX/HTML escaping.
- Update existing Playwright/browser scenarios and add report-dialog end-to-end coverage: all four formats, checkbox both states, new-tab behavior, download name/type, modal keyboard/focus/escape, narrow layout, stage/kebab absence, inline strategy actions, grip placement, hover titles, session controls and outcome alignment. Mock providers; **no paid calls**.
- Run `./sigma test`, Ruff checks/format, Pyright, frontend typecheck and Vite build, and real Chrome desktop/mobile browser checks. Fix failures and flakiness rather than merely updating snapshots to pass.
- Record exact commands, results, remaining known limitations and screenshots in `docs/STATUS.md`. Only mark A17.5 complete after implementation and actual verification. Do not claim unrun tests passed.
