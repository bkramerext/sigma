# SIGMA coding guidance

Read `docs/PROJECT.md`, `docs/DECISIONS.md`, `docs/STATUS.md`, and the active `specs/*.md` before implementing.

## Specification-driven workflow
1. Implement only the active, approved specification. The current first task is `specs/project-lifecycle.md`.
2. Translate its acceptance criteria into automated tests, implement the smallest code that passes, and check error paths and invariants.
3. If a specification is ambiguous or conflicts with the architecture, surface the issue and propose a precise amendment. Do not silently invent product requirements.
4. Keep product specs, implementation status and decisions separate. A change in behavior must be reflected in the spec; implementation progress belongs in STATUS.
5. Run tests and relevant static checks, record exact results in STATUS, then commit and push a coherent increment.

Use Python, uv, pytest, Ruff, Pyright, and argparse. Models belong under `models/`; application services are shared by CLI and future FastAPI UI. Ordinary tests must be offline. Avoid secrets, force pushes and speculative features. Do not build later milestone features until the current spec passes. Favor working, reviewable software over documentation volume.
