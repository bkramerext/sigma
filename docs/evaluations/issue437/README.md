# Issue #437 — Workflow onboarding evidence

Branch: `gray/issue-437-workflow`

Base: `main` at `92bc34eda4c53decd6de29af315100251a5fde62`

## Acceptance

| Requirement | Result | Evidence |
|---|---|---|
| New first About disclosure explains project → research → optional paper → user-decided publication | **MET** | Six linked stages in `.about-workflow`; concise notes alongside every stage. |
| First visit opens the workflow; all About disclosures persist across close/reopen and reload | **MET** | `browser_checks/issue437_workflow.py` checks first-visit default and all five rendered disclosures (workflow, features, architecture, provenance, feedback) across close/reopen and reload. It also checks stale/invalid saved section values fall back to defaults. |
| Desktop left-column boxes and right-column notes; responsive narrow layout | **MET** | Real Chrome at 1440×960 and 390×844. Harness checks stage/notes alignment and no horizontal dialog overflow. |
| Existing multi-agent diagram and About content remain | **MET** | Existing architecture disclosure and component remain; Chrome harness confirms architecture diagram is present. |
| README has an equivalent inline diagram with stage notes | **MET** | GitHub Mermaid flowchart and associated bullets directly below “Using SIGMA.” |
| Welcome tells newcomers to open About SIGMA | **MET** | `browser_checks/guest_samples.py` checks the new line during the real Chrome guest workflow. |
| No autonomous verification or automatic publication claims | **MET** | Copy states that a draft is not proof or independent verification, and publication is the user's decision. |
| GitHub-rendered README Mermaid appearance | **UNVERIFIED** | The pushed GitHub README returns HTTP 200 and labels the block as a Mermaid rendered-output container, but real Chrome showed a loading spinner and no completed graph after 15 seconds. |

## Checks run

- `./sigma test` — **passed**: all steps including Python scenarios, Ruff lint/format, Pyright (0 diagnostics), frontend typecheck, and production build. Existing large JavaScript chunk advisory remains. The optional graph-present Python sandbox case skipped because its local image is unavailable.
- `SIGMA_BROWSER_BASE_URL=http://127.0.0.1:5173 uv run --with playwright --no-sync python browser_checks/issue437_workflow.py` — **passed** in real Google Chrome. Verified disclosure order/defaults, saved states through close/reopen/reload, six stages, desktop alignment, mobile stacked notes, no horizontal overflow, and preserved architecture diagram. Screenshots: [desktop](about-workflow-desktop.png), [mobile](about-workflow-mobile.png).
- `uv run --with playwright,httpx --no-sync python browser_checks/guest_samples.py` — **passed** in real Google Chrome; included Welcome guidance assertion.
- `git diff --check` — **passed**.
- A real-Chrome visit to the pushed GitHub README (`https://github.com/bkramerext/sigma/blob/gray/issue-437-workflow/README.md`) returned HTTP 200 and exposed `data-type="mermaid"` with the flowchart source. The GitHub Mermaid viewer still showed a loading spinner with no diagram after a 15-second wait, so completed GitHub visual rendering remains **UNVERIFIED**.

No paid provider calls or deployments occurred. Product logic, research scheduling, and paper generation were not changed.
