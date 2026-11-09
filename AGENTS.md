# SIGMA coding guidance

Read [Getting Started](docs/GETTING_STARTED.md), [software factory guidance](docs/SOFTWARE_FACTORY.md), the active ticket in `tickets/`, and relevant PR handoffs under `messages/`. Follow the repository's current collaboration and authorization rules; assignments need precision, not forced brevity.

For historical milestone context, consult [the development journal](docs/JOURNAL.md) when relevant.

Use shared typed Python services across browser, API, CLI, and executable scenarios. Protect project identity, research history, and existing data. Choose simple implementations; document consequential tradeoffs.

Run `./sigma test` and relevant real-browser checks. Record actual results in the ticket or committed PR handoff under `messages/`; commit and push completed assignments. No speculative agents, paid calls, secrets, force pushes, or private recruiting context.

Blue's ongoing mailbox/implementation cycle follows
[Blue operating protocol](docs/BLUE_OPERATING_PROTOCOL.md): validate and export
actual projects every iteration, push the numbered response, then actively poll
every 30 seconds with a clean tree and fast-forward-only synchronization.

## UI conventions

**All new or modified UI must follow SIGMA's existing design and interaction conventions.** Inspect comparable screens, components, and styles in the current codebase before implementing a control, dialog, icon, layout, tooltip, or interaction. Reuse established SIGMA components and patterns; do not assume browser defaults, framework defaults, generic design conventions, or invent a new pattern just because it seems reasonable.

For example, use SIGMA's standardized tooltip system, **never native browser tooltips** (including HTML `title` attributes or SVG `<title>` hover bubbles). Disclosure tooltips describe the action a click will perform (`Expand` or `Collapse`), not the current state.

**If the applicable SIGMA convention is unclear, inconsistent, or missing, ask the user before choosing a UI behavior or appearance.** Do not silently decide on an assumed default.

## CI failure batching

When running CI, **wait for all workflows and test shards to finish reporting failures** before preparing a correction. Review the complete failure set, fix **all known issues together**, and push **one consolidated batch** rather than pushing a fix after each failure. In particular, collect all Ruff lint and formatting diagnostics, run **both** `ruff check` and `ruff format --check` on the complete patch, and resolve every Ruff finding before the next push. This avoids repeated CI rounds and reduces fix cycle time. Do not launch overlapping CI reruns merely to address individual failures.
