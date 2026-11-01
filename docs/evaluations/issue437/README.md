# Issue #437 — Workflow onboarding evidence

Branch: `gray/issue-437-workflow`

Base: `main` at `92bc34eda4c53decd6de29af315100251a5fde62`

## Acceptance

| Requirement | Result | Evidence |
|---|---|---|
| First About disclosure explains project → research → optional paper → user-decided publication | **MET** | Six connected stages in `.about-workflow`. Stage 6 distinguishes research records/reports from paper PDF/TeX export. Paper sharing/publication is the user's choice. |
| All About disclosure states persist across close/reopen and reload | **MET** | `browser_checks/issue437_workflow.py` checks first-visit defaults and all five available About disclosures in the cloud-enabled fixture across close/reopen and reload, plus stale/invalid saved values. |
| About diagram fits desktop and narrow screens without truncated notes | **MET** | Real Chrome at 1440×960, 390×844, and 320×740. Narrow notes use 12px. The harness checks stacked layout, text scroll/clip metrics, no horizontal overflow, and reachability of the final stage through normal dialog scrolling. |
| Keyboard operation of disclosures | **MET** | Chrome harness toggles workflow and architecture disclosures with Enter and Space. |
| Existing multi-agent architecture content remains | **MET** | Existing disclosure and component remain; the Chrome harness confirms architecture content is present. |
| README has an equivalent inline flow and stage notes; its lead-in is concise | **MET** | The original walkthrough is condensed, session settings link to Getting Started, and the six-stage diagram/bullets directly follow the short lead-in. Diagram arrows distinguish research export from the optional-paper route. |
| Mermaid source renders as a complete, legible diagram | **MET** | [Independent Mermaid JS v11 Chrome render](readme-mermaid-independent.png) shows six labeled nodes and six connectors. `browser_checks/issue437_mermaid_render.py` extracts the exact README block and checks nodes and route labels. |
| GitHub's own rendered Mermaid display | **UNVERIFIED** | Real Chrome loaded the corrected pushed README at HTTP 200 and recognized the Mermaid block, but after 15 seconds GitHub's render target remained empty/loading (the target contained only action icons and no diagram SVG). Independent Mermaid rendering confirms the source itself renders. |
| Welcome points newcomers to About SIGMA; no proof/publishing overclaims | **MET** | Real Chrome guest-flow check asserts the Welcome line. About and README say a paper is optional and publication is user-decided; they do not claim independent verification or automatic journal submission. |

## Checks run

- `./sigma test` — **passed after review corrections**: Python scenarios, Ruff lint/format, Pyright (0 errors/warnings/information), frontend typecheck, and production build. Existing large JavaScript chunk advisory remains. Optional graph-present sandbox scenario skipped because its local image is unavailable.
- `SIGMA_BROWSER_BASE_URL=http://127.0.0.1:5173 uv run --with playwright --no-sync python browser_checks/issue437_workflow.py` — **passed** in real Google Chrome. Checks About order/defaults, keyboard Enter/Space, persistence after close/reopen/reload, stale defaults, six stages, responsive alignment, 12px notes, full wrapping, no horizontal overflow, and final-stage visibility after scrolling. Screenshots: [desktop](about-workflow-desktop.png), [390px top](about-workflow-mobile.png), [390px bottom](about-workflow-mobile-bottom.png), [320px top](about-workflow-mobile-320.png), [320px bottom](about-workflow-mobile-320-bottom.png).
- `uv run --with playwright --no-sync python browser_checks/issue437_mermaid_render.py` — **passed** in real Chrome using the independent Mermaid JS v11 renderer; rendered all six stage labels and six connectors, including the optional paper branch and separate research/paper export paths. Screenshot: [independent Mermaid render](readme-mermaid-independent.png).
- `uv run --with playwright,httpx --no-sync python browser_checks/guest_samples.py` — **passed** in real Google Chrome; included the Welcome guidance assertion.
- `git diff --check` — **passed**.
- GitHub preview recheck after push — HTTP 200, Mermaid block recognized, but no completed diagram was visible after 15 seconds. GitHub visual rendering remains **UNVERIFIED**. The independent rendering is complete and captured above.

No paid provider calls or deployments occurred. No research scheduling, paper-generation, or project API code changed.
