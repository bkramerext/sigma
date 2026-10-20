# Getting Started

SIGMA runs locally. The current application supports project lifecycle and manually authored strategies; agents and automated research are not yet available.

## Install and launch

Prerequisites: Python 3.11+, [uv](https://docs.astral.sh/uv/), Node.js 20.19+, and npm.

From the repository root:

```sh
./sigma setup
./sigma ui
```

Open **http://127.0.0.1:5173**. Choose `projects/rh.sigma` and **Open project**. On the project page, use **New strategy** to save a title and approach. Strategies persist after reload or reopen. **Close project** returns Home. Project details/history are collapsible.

Use the chevron beside a strategy name, then **Actions → Edit** to change its
name and description in a dialog. **Actions → Remove** asks for confirmation and
removes it from the active pool while retaining the research record and history.
Cancel/Escape leaves data unchanged; failed saves retain dialog text for retry.
Edit events include **View changes** with before-and-after text.

The launcher starts FastAPI on localhost port 8000 and Vite on port 5173. Both ports must be free. Ctrl+C stops both servers. There is no authentication or remote hosting. Project URLs contain local filesystem paths, not shareable links.

**Generate strategy**, scheduling, reports, and forks are unavailable; the UI explains their status.

## CLI

```sh
./sigma init /tmp/example.sigma --title 'Example' --problem 'Investigate it'
./sigma open projects/rh.sigma
./sigma inspect projects/rh.sigma
./sigma events projects/rh.sigma
./sigma new-strategy /tmp/example.sigma --title 'Idea' --approach 'Test this hypothesis'
./sigma strategies /tmp/example.sigma
./sigma edit-strategy /tmp/example.sigma STRATEGY_ID --title 'Revised idea' --approach 'Updated description'
./sigma remove-strategy /tmp/example.sigma STRATEGY_ID
./sigma close
```

Successful commands print JSON to stdout (exit 0). Project errors print `{"error":"..."}` to stderr (exit 2); argparse syntax errors also exit 2. `close` is stateless. `strategies` lists the active pool; `inspect` retains removed
records and all audit events. Edit/remove commands return the updated project. Only the canonical RH seed initializes implicitly; other projects require `init`.

## API

The local API exposes the same services:

| Method | Endpoint |
| --- | --- |
| POST | `/api/projects/init` |
| POST | `/api/projects/open` |
| GET | `/api/projects/inspect?path=...` |
| GET | `/api/projects/events?path=...` |
| POST | `/api/projects/close` |
| POST | `/api/projects/strategies` |
| GET | `/api/projects/strategies?path=...` |
| POST | `/api/projects/strategies/edit` |
| POST | `/api/projects/strategies/remove` |

Init accepts `{path,title,problem}`; open accepts `{path}`; create-strategy accepts `{path,title,approach}`. Strategy titles are 1–200 characters; approaches are 1–10,000 after trimming. Project errors return HTTP 400; invalid bodies 422; creation 201.

Edit accepts `{path,strategy_id,title,approach}`; remove accepts `{path,strategy_id}`.
Both return the updated project (HTTP 200). Unknown or already-removed strategies
produce HTTP 400; removed strategies cannot be edited. Name/description in the
dialog map to the existing title/approach fields and share their length limits.

## Test

```sh
./sigma test
```

Runs lifecycle/strategy scenarios, API/CLI checks, launcher checks, Ruff, Pyright, and frontend typecheck/build. Uses temporary projects and makes no paid calls. Real-browser tests are separate. Run `./sigma setup` first; commands can be launched from outside the checkout. With an activated environment, `sigma setup`, `sigma ui`, and `sigma test` also work.

## Data and limitations

New projects use JSON schema v2. Existing v1 projects open unchanged; their first strategy save preserves an exact `project.v1.json` backup before migration. First edit/removal upgrades v2 to v3, preserving an exact `project.v2.json` backup.
V3 retains removed records and edit/removal events; older clients cannot read v3.
Unchanged edits add no event or migration. Writes use POSIX advisory locks and atomic replacement. Use a local macOS/Linux filesystem; do not edit project JSON while a save is running. Generated RH project state is excluded from Git.

See [Architectural Decisions](DECISIONS.md) for concurrency/crash limitations, [Status](STATUS.md) for verified behavior, and [SPEC-001](../specs/project-lifecycle.md) for the original lifecycle contract.
