# Issue #441 — Research Process diagram polish

Branch: `gray/441-research-process-polish`

Base: `main` at `4b2f34f92264bb6614cbcee0aecc19834dabf85b`

Initial implementation source: `338a3271888f3ac74790bf6c0b46032a78a262e4`

Review-correction source: `e08a1841c502ff08ccddd43975d162626dadbb51`

## Acceptance

| Requirement | Result | Evidence |
|---|---|---|
| First About disclosure is titled exactly “Research Process” and remains first/open by default | **MET** | Real Chrome check confirms first position and visible open state. The saved disclosure key remains `workflow`, preserving existing expansion preferences. |
| All six About stages have exactly two explanatory bullets | **MET** | `browser_checks/issue441_research_process.py` asserts two note list items for every stage, including stage 6's separate research and optional-paper export explanations. |
| Boxes are evenly spaced and connectors touch circles and following boxes | **MET** | Chrome checks compare all five box pitches and pseudo-element connector start/end coordinates against circle bottoms and next box tops (1.5px tolerance). [Desktop](about-workflow-desktop.png), [390px](about-workflow-mobile.png), [320px](about-workflow-mobile-320.png). |
| Mobile connector corridor stays clear of native bullet markers | **MET** | The mobile CSS moves the bullet lane 19px right and uses an even 188px row pitch. The Chrome regression checks that each outgoing connector clears its stage's marker lane by at least 8px at both 390px and 320px, while keeping the arrow endpoints flush. Updated screenshots show the spine in a separate left gutter. |
| Desktop and mobile About layout is legible, stacked where narrow, and not clipped | **MET** | Real Chrome at 1440×960, 390×844 and 320×740. Checks column alignment, mobile note stacking, row fit, text scroll dimensions, no clipping/line clamping and no horizontal dialog overflow. Final-stage screenshots: [390px](about-workflow-mobile-bottom.png), [320px](about-workflow-mobile-320-bottom.png). |
| Existing architecture diagram and sticky disclosure states are preserved | **MET** | Chrome verifies architecture disclosure content and verifies expanded/collapsed section states across close/reopen/reload. The existing `workflow` localStorage key is unchanged. |
| README prominently links to the hosted app, uses the `Workflow` heading, and retains stage explanations and caveats | **MET** | Source assertions in `browser_checks/issue441_readme_mermaid.py` check the exact hosted URL near the top, exact heading, and accurate research versus optional-paper export text. |
| README diagram is horizontal, linear, six boxes and five ordinary links | **MET** | Source assertions and independent real-Chrome render check `flowchart LR`, six nodes, five connectors, left-to-right node order, no branch/special edge syntax and legibility in the 980px render frame. [Independent render](readme-mermaid-independent.png). |
| GitHub's own Mermaid visual rendering | **MET** | Real Chrome loaded the pushed README at HTTP 200. GitHub's Mermaid iframe rendered an SVG with all six labels and five connectors in left-to-right order. [GitHub preview screenshot](github-mermaid-preview.png). |

## Checks run

- `SIGMA_BROWSER_BASE_URL=http://127.0.0.1:5173 uv run --with playwright --no-sync python browser_checks/issue441_research_process.py` — passed in real Google Chrome, including explicit mobile marker-lane clearance, equal pitch, and row-fit/wrapping checks.
- `uv run --with playwright --no-sync python browser_checks/issue441_readme_mermaid.py` — passed in real Google Chrome using Mermaid JS v11 to render the exact README block.
- `./sigma test` — passed after the mobile-collision correction: Python suites, Ruff check/format (337 Python files formatted), Pyright (0 errors, warnings or information), frontend typecheck and production build. The graph-present sandbox subcase skipped because its local image is unavailable; the existing large JavaScript chunk advisory remains.
- `git diff --check` — passed.
- GitHub README preview — passed in real Chrome at HTTP 200; the embedded Mermaid frame rendered the expected six nodes/five connectors. Screenshot preserved above. The viewer's control toolbar overlaps a small part of the final box border, but its `Review/export` label remains fully legible; the independent renderer screenshot is free of viewer controls.
- GitHub Actions on PR head `69a960c591bc79485b8007e703af6019c073f719` — all six workflows passed, including SIGMA verification. The commit only updates report and handoff evidence; focused tests and `./sigma test` passed on the correction source `e08a1841c502ff08ccddd43975d162626dadbb51`.

No provider calls or deployment occurred. No research, paper-generation, About pill/navigation or Project Types behavior changed.
