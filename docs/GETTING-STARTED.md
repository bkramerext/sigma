# Getting Started

SIGMA runs locally. The current application supports project lifecycle and manually authored strategies; agents and automated research are not yet available.

## Install and launch

Prerequisites: Python 3.11+, [uv](https://docs.astral.sh/uv/), Node.js 20.19+, and npm.

From the repository root:

```sh
./sigma setup
./sigma ui
```

Open **http://127.0.0.1:5173**. Choose **Open Project**, enter `projects/rh.sigma` in the dialog, and open it. **New Project** asks for a name, multiline research problem, and research mode (Default or Mathematical), then opens the created workspace. Cancel or Escape returns Home. On the project page, use **New strategy** to save a title and approach. Strategies persist after reload or reopen. **Close project** returns Home. Project details/history are collapsible.

Use the three-dot menu beside a strategy, then **Actions → Edit** to change its
name and description in a dialog. **Actions → Remove** asks for confirmation and
removes it from the active pool while retaining the research record and history.
Cancel/Escape leaves data unchanged; failed saves retain dialog text for retry.
Edit events include **View changes** with before-and-after text.

The launcher starts FastAPI on localhost port 8000 and Vite on port 5173. Both ports must be free. Ctrl+C stops both servers. There is no authentication or remote hosting. Project URLs contain local filesystem paths, not shareable links.

Scheduling, reports and forks are unavailable; the UI explains their status. Optional AI proposal generation is described below.

## CLI

```sh
./sigma create --title 'My investigation' --problem 'Investigate it' --research-mode mathematical
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
records and all audit events. Edit/remove commands return the updated project. Only the canonical RH seed initializes implicitly; other projects require `create` (managed location) or `init` (explicit directory). Both accept `--research-mode default|mathematical`, defaulting to `default`.

## API

The local API exposes the same services:

| Method | Endpoint |
| --- | --- |
| POST | `/api/projects/init` |
| GET | `/api/projects/destination?title=...` |
| POST | `/api/projects/create` |
| POST | `/api/projects/open` |
| GET | `/api/projects/inspect?path=...` |
| GET | `/api/projects/events?path=...` |
| POST | `/api/projects/close` |
| POST | `/api/projects/strategies` |
| GET | `/api/projects/strategies?path=...` |
| POST | `/api/projects/strategies/edit` |
| POST | `/api/projects/strategies/remove` |

Managed create accepts `{title,problem,research_mode?}`; additional fields such as `path` are rejected. Destination preview returns `{root,path,exists}` (omit title for root only). Unknown modes return 400. Init accepts `{path,title,problem,research_mode?}`; open accepts `{path}`; create-strategy accepts `{path,title,approach}`. Strategy titles are 1–200 characters; approaches are 1–10,000 after trimming. Project errors return HTTP 400; invalid bodies 422; creation 201.

Edit accepts `{path,strategy_id,title,approach}`; remove accepts `{path,strategy_id}`.
Both return the updated project (HTTP 200). Unknown or already-removed strategies
produce HTTP 400; removed strategies cannot be edited. Name/description in the
dialog map to the existing title/approach fields and share their length limits.

## Test

```sh
./sigma test
```

Runs lifecycle/strategy scenarios, API/CLI checks, launcher checks, Ruff, Pyright, and frontend typecheck/build. Uses temporary projects and makes no paid calls. Real-browser tests are separate. Run `./sigma setup` first; commands can be launched from outside the checkout. With an activated environment, `sigma setup`, `sigma ui`, and `sigma test` also work.

## Project location

New Project and `sigma create` use this checkout's absolute `projects/` directory, independent of the browser or shell working directory. To choose another root, create a directory owned by the server user and launch with `SIGMA_PROJECTS_ROOT=/absolute/path ./sigma ui` (or the same environment variable for CLI commands). The root must already exist, be absolute, and must not itself be a symlink. Missing parents are not created.

The server derives a lowercase Unicode-normalized directory name, joining punctuation/spacing with hyphens and adding `.sigma`. Names are 1–200 characters, reject path separators/control characters, and must contain a letter or number. Directory stems are limited to 80 characters/180 UTF-8 bytes. Different names can normalize to the same directory: choose another name when a collision is reported; existing files and projects are never reused or overwritten. The dialog previews this destination read-only. Research problems are 1–20,000 characters after trimming. Open Project still accepts arbitrary valid existing local project paths.

Canonical artwork lives in `assets/`; Vite copies its exact bytes into runtime public assets on dev startup and builds. No manual frontend artwork copy is needed.

## Data and limitations

New projects use JSON schema v4 with persisted `research_mode`. Existing v1–v3 documents default to Default without being rewritten; strategy writes retain their established lazy migration behavior. Existing v1 projects open unchanged; their first strategy save preserves an exact `project.v1.json` backup before migration. First edit/removal upgrades v2 to v3, preserving an exact `project.v2.json` backup.
V3/v4 retain removed records and edit/removal events; older clients cannot read newer schemas.
Unchanged edits add no event or migration. Writes use POSIX advisory locks and atomic replacement. Use a local macOS/Linux filesystem; do not edit project JSON while a save is running. Generated RH project state is excluded from Git.

See [Architectural Decisions](DECISIONS.md) for concurrency/crash limitations, [Status](STATUS.md) for verified behavior, and [SPEC-001](../specs/project-lifecycle.md) for the original lifecycle contract.

## Strategies and human-tracked stages

Click a strategy's title/preview to expand the complete approach, actual creation
metadata and UUID. The one-line preview is the accepted AI summary when present,
otherwise whitespace-collapsed full approach; ellipsis affects display only.
Editing the approach clears an old summary so the preview cannot become stale.

The vertical three-dot control opens commands. Under Actions, Edit and Remove
retain earlier text/history; Change stage records an explicit manual update.
Draft, Ready to explore, Exploring and On hold describe the person's tracking.
Exploring does **not** start an agent, evaluate evidence or check a proof.

Drag only the upper-right grip to reorder; ordinary row text remains selectable.
Touch works on the grip. Keyboard: focus a grip, Space to pick up, Up/Down to move,
Enter/Space to drop, Escape to cancel. Preview moves do not save until drop.
Failures restore the previous order. Concurrent order or active-list changes
reject a stale drop: reopen/refresh before retrying. New strategies append to the
active list; removal preserves the underlying record and creation timestamp.

```sh
./sigma stage-strategy /path/project.sigma STRATEGY_ID exploring
./sigma reorder-strategies /path/project.sigma --order ID_B ID_A --expected-order ID_A ID_B
```

API: `POST /api/projects/strategies/stage` accepts `{path,strategy_id,stage}`
(`draft|ready|exploring|hold`). `POST /api/projects/strategies/reorder` accepts
`{path,order:[all active IDs],expected_order:[previous active IDs]}`. Both return
the updated project. `ProjectView.project.active_order` is the authoritative
active list; the stored `strategies` array retains creation order and removed
records. First stage/reorder/AI-assisted save upgrades to schema v5 with an exact
old-version backup; legacy files read as Draft/in creation order without writes.
Existing manual-only create/edit/remove lazy migrations remain unchanged.

## Optional AI proposals (OpenAI)

Use **New Strategy → Generate with AI**. Writing manually remains the primary
click and needs no provider configuration. AI is disabled by default. Configure
these variables in the **server's environment** before launching:

```sh
export SIGMA_AI_ENABLED=1
export SIGMA_AI_MODEL=gpt-4.1
# Set OPENAI_API_KEY securely in your shell/environment; never commit it.
./sigma ui
```

The key must be an OpenAI API key with access/billing for the selected model.
ChatGPT/Codex access does not configure this key or include these API charges.
The model must support Responses strict structured output. `gpt-4.1` is the
explicit default; no model/reasoning settings are added to projects.

The dialog discloses and requires consent for transmission of the project
research problem, mode, **all** existing strategy titles/full approaches (including
removed directions) and optional Starting point. An empty seed requests an
independent direction. There are no provider calls on load or typing. A seed is
context to scrutinize, not a claim to endorse.

Generate draft makes **one** request; Regenerate is a separate explicitly billed
request and replaces editable fields only after success. Review/edit the title,
one-line preview and full approach (including first tests, assumptions and ways
the idea might fail). Save strategy is the only persistence action; it records an
AI-assisted suggestion accepted/edited by a human, with returned provider/model.
Cancel leaves project files unchanged. Failed generation or acceptance retains
existing draft edits. Cancelling a request closes the local connection; provider
processing/billing may already have occurred. No automatic retries.

Operational limits: one proposal request at a time per API process; 60-second
whole HTTP operation deadline; 48,000-character full JSON context (reject rather
than truncate); 4,000-character seed; 3,500 maximum output tokens; 128KB response
cap. Validated fields: title 200, summary 300, approach 6,000, first tests,
assumptions and failure modes 1,000 characters each. Final saved approach stays
within the existing 10,000-character limit. Obvious duplicate titles and strongly
repetitive approaches are rejected; semantic distinctness still needs human review.
No tools, outbound research, code execution, queues or autonomous loops.

Uses pinned `httpx==0.28.1` with the official Responses REST endpoint and
[`text.format` strict JSON schema](https://developers.openai.com/api/docs/guides/structured-outputs).
`store:false` is requested; provider retention policies still apply. SIGMA does
not log prompts, responses or keys by default. Errors expose generic status/help,
not raw provider responses. Proxies/redirects/custom provider URLs are disabled.

`GET /api/projects/proposals/config` reports safe availability/model metadata.
`POST /api/projects/proposals` accepts `{path,seed?,consent:true}` and returns an
unsaved structured draft, provenance and a signed acceptance receipt. Saving uses
`POST /api/projects/strategies` with `{path,title,approach,summary,receipt}`. The
receipt binds provenance to that project, expires after 24 hours, and expires on
server restart. If it expires, copy your edits before regenerating, or write the
text manually (without AI attribution). Receipts contain no request/response dump
or key. There is no persistent draft store.
