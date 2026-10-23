# A23 — Project difficulty setting

Status: Assignment ready; not started.

## Objective

Add a user-editable project difficulty setting with exactly three values: **Easy**, **Medium**, **Hard**. Show the selected difficulty clearly on the project page. The existing Maximum Regions Formed by Lines sample is **Easy**.

## Scope and behavior

1. Add a persistent `difficulty` property to the project model, serialization, validation, project creation, project editing/settings, and project import/export where project metadata is represented. Use stable machine values (`easy`, `medium`, `hard`) and human-facing labels (`Easy`, `Medium`, `Hard`).
2. Expose the setting in the existing **Project Settings** interface, using the existing Save/Cancel and validation conventions. Do not add a separate settings surface or extra navigation.
3. Render the selected difficulty as compact, readable project metadata on the **project page**, near the existing project identity/details. Match current typography, spacing, and visual conventions. It must remain legible on narrow screens and accessible to assistive technology.
4. Set the shipped **Maximum Regions Formed by Lines** sample to `easy`. Preserve difficulty when users open/fork/copy that sample and when they edit other projects.
5. Backward compatibility: projects saved before this field existed must load without error. Choose a consistent default for missing values (recommended: `medium` for new and legacy projects, unless existing architecture offers a more coherent default). Do **not** silently classify all historical projects as Easy. Invalid stored values should be handled safely and predictably.
6. Difficulty is **descriptive project metadata**, not an agent capability or quality claim. Do not change strategy generation, agent prompts, execution budgets, coordinator logic, scoring, or research outcomes based on difficulty in this increment.
7. Keep all other UI flows and styling unchanged. No unrelated redesigns, new controls, or navigation changes.

## Verification

- Tests cover new-project default, valid/invalid values, persistence and reload, edits with Save/Cancel, legacy project migration/default, import/export round trip where applicable, sample difficulty, and fork/copy behavior.
- Browser check confirms project page displays the selected label and settings edits update it; inspect responsive layout and accessibility.
- Run `./sigma test` and relevant browser checks, recording actual results and any limitations.
- Include before/after screenshots or a concise visual description of the **only** intended UI changes in the PR. Explicitly flag any incidental UI differences.

## Delivery

Work on a dedicated A23 feature branch; open a PR targeting `main`. Do not merge it yourself. Keep the change small and focused; avoid modifying other workers' active files when practical. Include implementation summary, test evidence, and migration/default behavior in the PR. Human/ChatGPT review and merge follow.
