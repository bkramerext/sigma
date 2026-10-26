# T226 rendered UI audit

Audit performed on `gray/t226-ui-consistency`, based on `main` `c6a14de` and the draft `docs/UI_GUIDELINES.md`. Screens were inspected in the local browser using the stock Nonconsecutive Subset Sums sample and synthetic API failures only. No provider was called and no research content was generated or saved.

## Candidate dispositions

| Candidate | Rendered evidence and locations | Expected behavior / disposition |
| --- | --- | --- |
| Global fallback palette | Home, Project, New Project, Settings, Export, paper preflight and toast screenshots below. Source: `frontend/src/style.css`, dialog styles in `frontend/src/project-settings.css` and `frontend/src/project-entry.css`. | Forms, dialogs, and notifications should remain within the dark navy and restrained copper UI. Inspected rendered screens used the intended palette; no light green/beige fallback leak reproduced. No change. |
| Workspace token overrides | Project and Sessions screenshots. Source: `frontend/src/workspace.css`, `frontend/src/strategies.css`. | Related work areas may layer surfaces, but visible contrast and section separation should remain consistent. Project, strategy cards, and session rows retain the established navy layers and readable borders. No defect reproduced; no token consolidation. |
| Copper/gold drift | Home, Project, Settings and New Project screenshots. Source: `frontend/src/copper-controls.css`, `frontend/src/strategies.css`, `frontend/src/project-settings.css`. | Interactive accents should read as restrained burnished copper against navy, preserving the approved Home artwork and metallic blue agent accent. Rendered actions and headings remained legible and within the existing palette. No defect reproduced; no palette edits. |
| About control mismatch | Home and Project screenshots. Source: `frontend/src/copper-controls.css`, `frontend/src/workspace.css`. | About remains accessible and must not overlap the auth status pills. The Home and Project controls both fit their header areas at desktop and mobile widths; their compact/rectangular shapes are existing layout choices. No defect reproduced; no change. |
| Header responsiveness | Home, Project and Sessions screenshots. Source: `frontend/src/workspace.css`. Home checked at 1440, 390 and 320 CSS px; Project About checked at 1440 and 390 CSS px. | Header pills and actions should stay within viewport and retain readable separation. No clipping/overlap reproduced at checked widths. No change. |
| Forms, actions and dialogs | New Project, Settings, Export and paper preflight screenshots. Source: `frontend/src/project-entry.css`, `frontend/src/project-settings.css`, `frontend/src/workspace.css`. | Maintain button hierarchy, labels, focus visibility, selected/disabled states, border radii and spacing. Screens were visually coherent; focus was visible on the Export filename input. No unrelated style differences were changed. |
| Project About dialog | Before/after screenshots. Component: `AboutDialog` in `frontend/src/main.tsx`; rules in `frontend/src/project-entry.css`. | Guidelines call for the established dark panel, copper border, padding and typography. Before: in the workspace, the dialog lacked the `.home-page` styling ancestor and rendered browser fallback appearance (dark default background, 3px white border, square corners, white text). Confirmed defect. Added a `display: contents` styling scope around the existing dialog so the existing Home About rules apply without adding a layout box. After: same navy/copper About panel and typography as Home; no content or interaction changed. |
| Sessions / Current Understanding | Sessions screenshot. Source: `frontend/src/main.tsx`, `frontend/src/workspace.css`, `frontend/src/strategies.css`. | Preserve readable session grouping and the existing expanded Current Understanding pattern. Visual inspection found no spacing, alignment, or overflow defect. No change. |
| Notifications | Toast screenshot from a synthetic 503 on `/api/projects/recent`. Source: `frontend/src/request-toast.tsx`, `frontend/src/request-toast.css`. | Toast should be legible, dismissible, and use the established UI. Rendered toast uses a dark panel, copper border and visible Dismiss control. Expiry, exit animation, reflow and reduced-motion timing are tracked under T215 and were not changed. The existing T215 lifecycle checks ran and passed as part of `./sigma test`. |

## Browser verification

`browser_checks/project_about.py` checks actual Project About appearance at 1440 and 390 CSS px, dialog bounds, no API request on open, and Escape focus restoration. It passed after the correction. A separate Home About run confirmed the existing dialog remains styled and within bounds at 1440, 390 and 320 CSS px. Screenshots were taken from the rendered browser for the screens listed above. No issue was reproduced in Home artwork, strategies split action, session layout, settings, export or paper preflight.

The pre-existing `browser_checks/header.py`, `recents.py`, `strategies.py`, `settings.py`, and `about_dialog_acceptance.py` checks were also attempted during exploration; they stopped on stale selectors/text expectations or a fixture mismatch before exercising the applicable visual acceptance. They were not modified for T226. These are not used as evidence of UI defects.

## Evidence

All images are browser screenshots from this audit. “Before” and “after” refer only to the Project About styling correction; no other visual changes were made.

- [Home](evidence/home.png)
- [Project](evidence/project.png)
- [Sessions](evidence/sessions.png)
- [Settings](evidence/settings.png)
- [New Project](evidence/new-project.png)
- [Export](evidence/export.png)
- [Paper preflight](evidence/paper-preflight.png)
- [Project About before](evidence/about-project-before.png)
- [Project About after](evidence/about-project-after.png)
- [Home About mobile](evidence/about-home-mobile.png)
- [Request failure toast](evidence/toast.png)
