# A17.5 — Project report and regression stabilization

Status: **assigned to Codex; not yet implemented or verified.**

Read `docs/HUMAN-AI-INTERACTION.md` and current `docs/STATUS.md` before implementation. Inspect current code; do not assume A17.4 documentation still describes the current UI.

## Feature: combined Project export dialog

- Replace the existing Project Download control and the proposed separate Report control with **one Export Project icon button** (file-down icon) in the Project title actions beside Settings. Provide accessible label, keyboard focus and native hover title.
- The **Export Project** dialog offers **Export type** radio buttons: **Project Audit** (selected by default) and **Research Report**. Project Audit must preserve the existing JSON audit export content and semantics.
- Show a **Format** dropdown at all times. It is **disabled/gray for Project Audit** (whose format is fixed to JSON). When Research Report is selected, enable the dropdown with **Text (.txt)**, **HTML (.html)** and **LaTeX (.tex)**; default Text. (The latest user specification intentionally excludes Markdown from this dropdown.)
- Display an **editable filename stem** initialized safely from the project name. Keep the extension separate and automatically determined: **.json** for Project Audit, and **.txt / .html / .tex** for the selected Research Report format. Switching export type or report format must **preserve the user's edited stem** and change only the extension. Validate/sanitize unsafe filename characters and empty stems, and never allow a manually entered extension to override the selected format.
- Provide an **Open in browser tab** checkbox (not a radio button), default unchecked, and standard dialog-styled **Create** (primary) and **Cancel** buttons.
- Research Report is generated deterministically from saved data, with no model calls or billing. Include project title/problem, strategies/approaches, sessions in durable order, execution status distinct from outcome, outcomes/caveats, artifacts' claims/methods/assumptions/evidence status, objections, decisions and open obligations. Preserve chronology and explicitly distinguish provisional/unverified findings. Gracefully handle empty projects, legacy records and missing optional fields.
- Generate usable escaped UTF-8 text, standalone safe HTML (no model-output script injection), and compilable escaped LaTeX. Preserve mathematical notation where feasible; test injection and special-character handling.
- Create downloads the chosen audit or report using the derived filename. If the checkbox is checked, also open a viewable representation in a new browser tab; avoid popup blockers by opening during the initiating gesture and handle blocked tabs gracefully. Verify JSON/text/HTML/LaTeX behavior in a real browser. Handle object URL cleanup.
- Keep modal visuals consistent with existing SIGMA dialogs, including narrow screens, Escape, focus management, Cancel, and error recovery.

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
