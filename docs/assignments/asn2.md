# ASN-2: Refine the project browser copy and header

Status: Ready for Codex
Context: The initial landing page and opened Riemann Hypothesis project have been reviewed visually. ASN-1 is implemented; preserve its working behavior.

## Assignment

Make a focused **frontend copy and presentation** pass. Retain the current visual identity: restrained typography, muted green palette, generous whitespace, and clear project controls. Do not redesign the application or alter project persistence.

### 1. Show the complete SIGMA expansion once, beneath the logo

The current page shows a partial slogan near the top and the full expansion in the footer. Replace that duplication with **one full expansion directly below the SIGMA logo in the header**:

**Strategy Investigation, Generation, Measurement & Assessment**

Keep it readable but subordinate to the logo. Remove the duplicate full expansion from the footer and remove the partial `STRATEGY · INVESTIGATION · MEASUREMENT` eyebrow above the hero. The full expansion should appear **only once** on the page.

### 2. Update the landing-page copy

| Location | Replacement |
| --- | --- |
| Hero headline | **Explore the paths to discovery.** |
| Hero description | **Investigate competing ideas, test their assumptions, and preserve what each exploration reveals.** |
| Project input label | **Project directory** (retain; it accurately describes the path input) |
| Project input helper | **Open a local SIGMA project directory.** |
| Primary action | **Open project** when no project is open; **Open / switch** or equivalent when a project is already open |
| Empty-state headline | **Every investigation starts somewhere.** |
| Empty-state description | **Begin with the included Riemann Hypothesis project.** |
| Workspace indicator | **Local workspace** (retain) |

Use concise, grounded language. Do not promise that investigations will necessarily produce discoveries or proofs.

### 3. Preserve the opened-project view

The second screenshot shows the RH project opening successfully, including title, objective, identity, directory, format version, and the `project.initialized` event. Keep those details visible and preserve the working close/switch behavior.

A few small refinements are appropriate if they improve clarity:
- Keep **Open / switch** and **Close project** clearly distinct; do not accidentally change their behavior.
- Keep the statement that finite experiments are not proofs in the RH project's objective, rather than diluting its meaning for marketing copy.
- Do not expose new agent features or invent research events.

### 4. Verification and delivery

- Exercise both the empty and opened-project browser states, including close and reopen.
- Confirm the full SIGMA expansion appears exactly once, beneath the logo, and that the former partial eyebrow and footer duplicate are gone.
- Run the existing `./sigma test` checks and any appropriate frontend checks.
- Update `docs/STATUS.md` with actual commands and results.
- Commit and push with a message describing the UI copy/header changes.

## Boundaries

This assignment is a **small UI polish increment**, not an architecture or storage redesign. Keep the browser-first cadence and existing CLI/scenario behavior intact. Do not add agent execution, scheduling, rubric evaluation, cloud hosting, or paid services.
