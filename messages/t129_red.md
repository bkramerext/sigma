# T129 Red handoff

**State:** R4R for offline implementation; hosted acceptance remains pending Brian's T127 handoff.
**Base:** `main` at `583f946ca9a495c44dbef6950dc1d07db1eaf2ac`.
**Branch:** `red/t129-gce-app-deployment`.
**PR:** Pending creation.

## Delivered

- Added a Caddy container healthcheck against its loopback-only admin API.
- Made the GCE preflight require healthchecks for backend, Nginx frontend, and Caddy. The Compose edge still waits for healthy backend/frontend.
- Added focused regressions for the GCE persistent state bind and backend storage paths, backend UID/GID ownership, mount guard, and systemd Docker/rootless/mount startup ordering. Existing recovery tests cover restart, root relocation, backup/restore and fail-closed startup; the preflight test now verifies it rejects a missing edge healthcheck.
- Documented local offline package checks and exact host commands for container health, public routes, persistent mount identity, filesystem ownership, and backend bind inspection.

## Validation actually run

- `./sigma setup` — passed; locked Python/npm dependencies installed in the task worktree.
- `uv run --locked --no-sync python tests/deployment_package.py` — passed.
- `uv run --locked --no-sync python tests/gce_host.py` — 16 tests passed.
- `uv run --locked --no-sync python tests/storage.py` — passed in focused reruns; covers persistent state, restart, backup/restore and mount-absent refusal.
- Final `./sigma test` — passed all scenarios, Ruff, formatting, Pyright, frontend typecheck and production build. One preceding full run had a transient Recent restore response failure in `tests/storage.py`; focused rerun and final full run passed.
- Docker CLI/engine is present (`docker info` reports 29.5.2), but Docker Compose v2 is unavailable (`docker compose version` exits 1: unknown command). Therefore merged Compose rendering, packaged-container smoke, and real Chrome checks were not run.

## Evidence boundary and dependencies

No GCE resource, secret, hosted endpoint, OAuth exchange or provider call was used. No deployment SHA, live disk UUID/mount/ownership, deployed health, or persistence through production container recreation has been observed. Those ticket acceptance items remain blocked on Brian's T127 provisioned-host handoff; this handoff does not claim hosted acceptance. No paid calls or costs occurred.
