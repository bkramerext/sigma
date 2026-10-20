# SIGMA

**Strategy Investigation, Generation, Measurement & Assessment**

Local research workspace with persistent projects and human-authored strategies.

## Run

Requires Python 3.11+, [uv](https://docs.astral.sh/uv/), Node.js 20.19+, and npm.

```sh
./sigma setup
./sigma ui
```

Open http://127.0.0.1:5173 and select `projects/rh.sigma`. The project opens on its own page. **New strategy** saves a title and approach across reloads. **Close project** returns Home. Project details/history are collapsible.

Generate strategy, scheduling, reporting, and forks are **not implemented**; the UI explains their unavailable state.

The launcher serves FastAPI on port 8000 and Vite on 5173, localhost only. Ctrl+C stops both. Run setup first; both ports must be free. No authentication or remote hosting.

## CLI

```sh
./sigma init /tmp/example.sigma --title 'Example' --problem 'Investigate it'
./sigma open projects/rh.sigma
./sigma inspect projects/rh.sigma
./sigma events projects/rh.sigma
./sigma new-strategy /tmp/example.sigma --title 'Idea' --approach 'Test this hypothesis'
./sigma strategies /tmp/example.sigma
./sigma close
```

Project commands return JSON on stdout (success, exit 0) or `{"error":"..."}` on stderr (project error, exit 2). Argparse syntax errors also exit 2. `close` is stateless. Only the RH seed initializes implicitly; other projects require `init`.

API equivalents: `POST /api/projects/init`, `POST /api/projects/open`, `GET /api/projects/inspect?path=...`, `GET /api/projects/events?path=...`, `POST /api/projects/close`, `POST /api/projects/strategies`, `GET /api/projects/strategies?path=...`. Create-strategy body: `{path,title,approach}`. Titles: 1–200 characters; approaches: 1–10,000 (trimmed). Invalid project operations return HTTP 400; invalid bodies 422; creation 201.

## Test

```sh
./sigma test
```

Runs scenarios, API/CLI checks, Ruff, Pyright, frontend typecheck/build. Uses temporary projects; no paid calls. Browser tests are separate. `./sigma setup` installs locked dependencies. Commands work from outside the checkout. An activated environment also supports `sigma setup`, `sigma test`, and `sigma ui`.

## Data

Project URLs include local filesystem paths, not shareable links. New projects use schema v2; existing v1 projects migrate on first strategy save with an exact `project.v1.json` backup. Writes use POSIX locks and atomic replacement; use a local macOS/Linux filesystem and do not edit project JSON during saves. See [DECISIONS](docs/DECISIONS.md) for limitations, [STATUS](docs/STATUS.md) for checks, and [SPEC-001](specs/project-lifecycle.md) for the original lifecycle contract.
