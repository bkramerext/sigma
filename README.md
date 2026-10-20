# SIGMA

Strategy Investigation, Generation, Measurement & Assessment. A local research
workspace; the current slice implements project lifecycle only.

## Launch the browser

Prerequisites: Python 3.11+, [uv](https://docs.astral.sh/uv/), Node.js 20.19+ and npm.
Run from the repository root:

```sh
uv run sigma setup
uv run uvicorn sigma.api:app --host 127.0.0.1 --port 8000
```

In another terminal, from the repository root:

```sh
npm --prefix frontend run dev
```

Visit **http://127.0.0.1:5173**, keep `projects/rh.sigma` in the directory field,
and click **Open project**. The first open initializes the checked-in placeholder;
subsequent opens retain its ID and history. Inspect the objective, identity, path,
and initialization event. Close releases the view; enter another existing project
path and Open / switch to switch projects. Errors keep the currently open view.
Paths refer to the API server's filesystem, relative to its working directory.

The development frontend proxies `/api` to the API on port 8000. Keep both servers
on localhost, with the frontend on port 5173. No authentication or remote hosting
is provided. Stop each server with Ctrl+C.

## CLI

```sh
uv run sigma init /tmp/example.sigma --title 'Example question' --problem 'Investigate it'
uv run sigma open projects/rh.sigma
uv run sigma inspect projects/rh.sigma
uv run sigma events projects/rh.sigma
uv run sigma close
```

Successful project commands print one JSON object to stdout (exit 0). Project errors print
`{"error":"..."}` to stderr (exit 2); argparse syntax errors use its standard
stderr usage messages (exit 2). Open/inspect/init return `{path, project}`, events
returns `{events: [...]}`, and close returns `{"closed":true}`. Close is stateless:
commands and API requests hold no persistent handles or global active project.
Only opening the repository's RH seed initializes implicitly; other projects
require `init`. Init requires an existing parent and refuses nonempty directories
apart from `.gitkeep`. It never replaces an existing project or repairs corruption.

The same services are exposed as `POST /api/projects/init`, `POST
/api/projects/open`, `GET /api/projects/inspect?path=...`, `GET
/api/projects/events?path=...`, and `POST /api/projects/close`. POST init accepts
`{path,title,problem}`, open accepts `{path}`. Project errors return HTTP 400 with
`{error}`, invalid request bodies return 422, and initialization returns 201.

## Verify

```sh
uv run sigma setup
uv run sigma test
```

`setup` installs the locked Python dependencies (including development tools) and
runs `npm ci` for the frontend. Install uv and Node/npm first. On a fresh checkout,
`uv run` bootstraps the CLI so it can perform setup. If you prefer bare commands:

```sh
source .venv/bin/activate
sigma setup
sigma test
```

`test` runs lifecycle scenarios and API checks, CLI smoke checks, maintenance
failure checks, Ruff lint/format checks, Pyright, frontend typechecking, and the
production build. Setup and test stream progress and tool output, stop at the
first failure, and return a nonzero exit status if a step fails. They run in the
source checkout regardless of your current directory. `test` uses installed
dependencies without syncing; run `setup` first. It uses temporary projects and
does not modify the RH seed. It does not launch servers or run a browser.

Scenarios call the typed services directly, then exercise the API with TestClient.
They operate on temporary directories, with injected publication failures; they
make no paid calls. See [verification results](docs/STATUS.md),
[storage decisions](docs/DECISIONS.md), and [SPEC-001](specs/project-lifecycle.md).
