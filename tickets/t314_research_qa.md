# T314 — Research Q/A over saved project research

## Objective

Let a project member ask a direct question about work already preserved in the
project and receive an answer grounded in frozen evidence, with validated
citations that reopen the relevant sessions and artifacts.

## Scope and constraints

- Add a project-scoped Research Q/A dialog and durable, newest-first answer
  archive, including safe standalone browser presentation and removal.
- Use saved sessions, artifacts, findings, and Current Understanding only. Do
  not start Investigator/Skeptic work, make strategies, or alter research.
- Validate provider citation IDs against the selected frozen snapshot. Preserve
  evidence provenance in each saved answer and mark unavailable navigation when
  a cited session or artifact has been removed.
- Reuse the project model/provider configuration and existing TeX/UI conventions.
- Add clipboard copy for saved Q/A and TeX text while retaining TeX download and
  browser actions.
- Use deterministic provider fixtures, protect workspace isolation, and avoid
  paid acceptance calls. Do not merge or deploy this assignment.

## Acceptance

1. Supported, unsupported, and uncertain/contradictory questions produce
   proportional answers based on saved evidence.
2. Citations are validated, navigable, and remain recorded if navigation later
   becomes unavailable.
3. Save, reload, copy, browser presentation, removal, export/import, and restart
   persistence work without changing research state or duplicating a request.
4. The standalone view safely escapes content and has usable desktop/mobile
   layouts.
5. TeX copy preserves human-readable text; existing TeX download/browser
   behavior remains intact.
6. Ruff, focused checks, frontend typecheck/build, `./sigma test`, and real
   Chrome fixture checks run and are reported accurately.

## Ownership and delivery

Owner: Green. Branch: `green/research-qa`, based on current `main`. Open one
reviewable PR; do not merge or deploy. Deliver a `messages/` R4R handoff with
MET / UNMET / UNVERIFIED findings, exact commit SHA, files, test results,
screenshots, and limitations.
