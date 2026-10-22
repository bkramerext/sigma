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

To stop the UI from another terminal, run `./sigma shutdown`. It stops only a verified instance belonging to the same checkout; it never stops an unrelated port owner. Running `./sigma ui` again starts or restarts SIGMA, including recovery from a previously suspended (`Ctrl+Z`) launcher when its process identity can be verified. An unverified process is never signalled. `Ctrl+C` in the launch terminal remains the normal clean shutdown.

The launcher starts FastAPI on 127.0.0.1:8000 and Vite on 127.0.0.1:5173. Running `./sigma ui` again automatically restarts a verified instance from the same checkout, reloads local configuration, and lets its old terminal exit cleanly. Ctrl+C or SIGTERM stops both servers; pipe guardians also clean them up if the supervisor crashes. Unrelated listeners, other checkouts and older unverifiable launchers are never killed: SIGMA names the blocking port and asks you to close that service using its own controls. Ports stay fixed; there is no alternate-port fallback. There is no authentication or remote hosting. Project URLs contain local filesystem paths, not shareable links.

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

Runs the workflow tests, API/CLI checks, launcher checks, Ruff, Pyright, and frontend typecheck/build. Uses temporary projects and makes no paid calls. Real-browser tests are separate. Run `./sigma setup` first; commands can be launched from outside the checkout. With an activated environment, `sigma setup`, `sigma ui`, and `sigma test` also work.

## Project location

New Project and `sigma create` use this checkout's absolute `projects/` directory, independent of the browser or shell working directory. To choose another root, create a directory owned by the server user and launch with `SIGMA_PROJECTS_ROOT=/absolute/path ./sigma ui` (or the same environment variable for CLI commands). The root must already exist, be absolute, and must not itself be a symlink. Missing parents are not created.

The server derives a lowercase Unicode-normalized directory name, joining punctuation/spacing with hyphens and adding `.sigma`. Names are 1–200 characters, reject path separators/control characters, and must contain a letter or number. Directory stems are limited to 80 characters/180 UTF-8 bytes. Different names can normalize to the same directory: choose another name when a collision is reported; existing files and projects are never reused or overwritten. The dialog previews this destination read-only. Research problems are 1–20,000 characters after trimming. Open Project still accepts arbitrary valid existing local project paths.

Canonical artwork lives in `assets/`; Vite copies its exact bytes into runtime public assets on dev startup and builds. No manual frontend artwork copy is needed.

## Data and limitations

New projects use JSON schema v6 with persisted research mode, AI model and Thinking level. Existing v1–v5 documents open without rewriting; missing mode defaults to Default and missing AI settings use the documented legacy bootstrap; strategy writes retain their established lazy migration behavior. Existing v1 projects open unchanged; their first strategy save preserves an exact `project.v1.json` backup before migration. First edit/removal upgrades v2 to v3, preserving an exact `project.v2.json` backup.
V3–v6 retain removed records and edit/removal events; older clients cannot read newer schemas.
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
records. Legacy first stage/reorder saves upgrade to at least v5; project settings and
new reasoning-provenance saves upgrade to v6 with an exact old-version backup; legacy files read as Draft/in creation order without writes.
Existing manual-only create/edit/remove lazy migrations remain unchanged.

## Optional AI proposals (OpenAI)

Use **New Strategy → Generate with AI**. Writing manually remains the primary
click and needs no account, key, `.env`, or feature flag. **Connect AI** in the
existing upper-right control offers **Continue with ChatGPT**. Eligible requests
use your ChatGPT plan allowance or credits, subject to plan/app/workspace limits.
The connection is remembered and refreshes when necessary. **Manage usage** opens
[ChatGPT usage settings](https://chatgpt.com/settings/usage). A one-time dismissible
welcome explains this; it never blocks generation or repeats after presentation.

You can instead open Generate, type a Starting point, and continue sign-in there.
Successful sign-in resumes that one pending request with its seed preserved.
Cancel/decline/failure retains your starting point in the generation dialog.
Header-only sign-in never generates. Account/project changes,
unmounts, cancelled attempts and stale callbacks cannot authorize duplicate work.

The advanced **Use API key · billed separately** action explicitly selects the
optional `OPENAI_API_KEY` from checkout `.env` or server environment. It is separate
API billing. No `SIGMA_AI_ENABLED` gate remains, and a present key never selects
billing by itself. ChatGPT errors or limits never use a saved key automatically.
Choose model/Thinking in New/Edit Project; mode/account are application preferences,
not project credentials or research settings.

The dialog permanently explains transmission of the project
research problem, mode, **all** existing strategy titles/full approaches (including
removed directions) and optional Starting point. An empty seed requests an
independent direction. There are no generation calls on load or typing; a cached, non-generating
model-list check supplies connection status and model availability. A seed is
context to scrutinize, not a claim to endorse.

Generate draft makes **one** intentional request; Regenerate is a separate request
using the selected billing mode and replaces editable fields only after success. Review/edit the title,
one-line preview and full approach (including first tests, assumptions and ways
the idea might fail). Save strategy is the only persistence action; it records an
AI-assisted suggestion accepted/edited by a human, with returned provider/model and the requested thinking level.
Cancel leaves project files unchanged. Failed generation or acceptance retains
existing draft edits. Cancelling a request closes the local connection; provider
processing/billing may already have occurred. No automatic retries.

Operational limits: one proposal request at a time per API process; 60-second
whole HTTP operation deadline; 48,000-character full JSON context (reject rather
than truncate); 4,000-character seed; API-key mode 25,000 output-token/128KB response bounds;
ChatGPT-plan mode 1MB/4,096-event stream bound. Validated fields: title 200, summary 300, approach 6,000, first tests,
assumptions and failure modes 1,000 characters each. Final saved approach stays
within the existing 10,000-character limit. Obvious duplicate titles and strongly
repetitive approaches are rejected; semantic distinctness still needs human review.
No tools, outbound research, code execution, queues or autonomous loops.

Uses pinned `httpx==0.28.1` with the official Responses REST endpoint and
[`text.format` strict JSON schema](https://developers.openai.com/api/docs/guides/structured-outputs).
`store:false` is requested; provider retention policies still apply. SIGMA does
not log prompts, responses or keys by default. Errors expose generic status/help,
not raw provider responses. Proxies/redirects/custom provider URLs are disabled.

`GET /api/projects/proposals/config?path=...` reports the saved project model/effort
and account eligibility separately from authentication health; it does not prove
generation or billing readiness.
`POST /api/projects/proposals` accepts `{path,seed?,expected_binding?,expected_project_id?}` and returns an
unsaved structured draft, provenance and a signed acceptance receipt. Saving uses
`POST /api/projects/strategies` with `{path,title,approach,summary,receipt}`. The
receipt binds provenance to that project, expires after 24 hours, and expires on
server restart. If it expires, copy your edits before regenerating, or write the
text manually (without AI attribution). Receipts contain no request/response dump
or key. There is no persistent draft store.

## Project settings and curated models (A8)

**New Project** opens the **New Project** dialog. On the workspace, the pencil immediately
beside the main project name opens **Edit Project**. Both use the same fields:
name, research problem, research mode, AI model, Thinking level. Name/problem are
required; Low, Medium, High and Extra high map to `low`, `medium`, `high`, `xhigh`.
High is the default. Edits save together on **Save Changes**; Cancel/Escape does
not save, and a no-op save does not rewrite files or append an event. Errors keep
your edits. Stale editors must refresh/reopen before retrying; the app does not
overwrite another editor's settings. Strategy edits can proceed independently.

Changing display name never moves the directory or changes the existing UUID.
Create still derives a safe readonly destination. Mode can change in either
direction; no strategies, stages, order, archived records or provenance reset.
Project details expose identity/settings and before/after `project.updated` audit.
Close Project simply returns Home, with no save/flush/confirmation or work teardown.

The backend-reviewed capability catalog (verified 2026-10-20) includes:

| Choice | Model | Offered thinking levels | Relative cost |
| --- | --- | --- | --- |
| Sol · Balanced | `gpt-6.1-sol` | Low, Medium, High, Extra high | $$ |
| Luna · Economy | `gpt-6-luna` | Low, Medium, High, Extra high | $ |
| Astra · Advanced | `gpt-6-astra` | Low, Medium, High, Extra high | $$$ |

Sources: official [Sol](https://developers.openai.com/api/docs/models/gpt-6.1-sol),
[Luna](https://developers.openai.com/api/docs/models/gpt-6-luna), and
[Astra](https://developers.openai.com/api/docs/models/gpt-6-astra) model pages
verify text, Responses, structured output and these effort values. We deliberately
offer a common four-level subset. These tiers describe relative cost; no numerical
rate is inferred from `/v1/models`. Consult [current pricing](https://developers.openai.com/api/docs/pricing)
for input/cache/output rates and processing-tier differences. There is no documented
per-model price-lookup endpoint in the model-list API. Actual cost also depends on
usage and reasoning. This assignment does not implement cost accounting.

New forms prefer Sol/High when the account list verifies Sol access. If only
another reviewed model is accessible, the form explicitly identifies its initial
default. With no verified access, Sol/High is a clearly labeled offline preference;
manual research remains available. Catalog entries carry available/unavailable/
unverified labels and only the reviewed IDs are returned, never a raw account
catalog. Stored choices stay visible, even after disappearance or network failure.
Metadata can be saved offline. Generation requires a reviewed compatible pair and
current cached account access; it never substitutes a different model/effort.

All new init/create operations write v6. Legacy v1–v5 reads do not change bytes;
missing model/effort defaults to Sol/High, or a reviewed `SIGMA_AI_MODEL` bootstrap
override plus High. Unreviewed overrides (including A7's `gpt-4.1`) are explicitly
qualified in discovery guidance and do not enter the reasoning catalog. Once v6
settings are saved, environment model overrides have no effect on that project.
Old AI provenance retains unknown thinking as null; no historical effort is invented.
New proposals snapshot context/model/effort at request start, send actual
`reasoning: {effort: ...}`, and bind returned model/requested effort into acceptance
receipts. A concurrent settings edit cannot misattribute a generated draft.

In explicitly selected API-key mode, the 25,000-token maximum includes reasoning
and visible output, following the
official [reasoning budget guidance](https://developers.openai.com/api/docs/guides/reasoning).
It is an upper bound, not a requested output size or cost estimate. High/Extra high
can still timeout (60 seconds) or exhaust budget; failures are explicit and no
retry, downgrade or save happens automatically. Visible draft fields retain A7's
limits. ChatGPT-plan requests omit the preview-prohibited output-token limit and
instead bound the total stream (1MB, 4,096 events) and whole request (60 seconds).
They require `store:false`, `stream:true`, array input, documented instructions,
strict JSON fields, actual reasoning effort and `response.completed`. Partial,
refused, malformed, failed, oversized and incomplete results are never drafts.
Unsupported structured-output/model/effort capabilities fail explicitly without
fallback. No per-strategy configuration or agent loop is added.

```sh
./sigma init /tmp/settings.sigma --title 'Question' --problem 'Investigate it' --model gpt-6.1-sol --thinking high
./sigma create --title 'Question' --problem 'Investigate it' --model gpt-6-luna --thinking high
```

`./sigma edit-project PATH --title ... --problem ... --research-mode mathematical
--model gpt-6-astra --thinking high --expected 'JSON'` takes the five previous
settings as JSON (`title`, `problem`, `research_mode`, `ai_model`,
`reasoning_effort`) for conflict detection. The equivalent API is
`POST /api/projects/update` with `{path,title,problem,research_mode,ai_model,reasoning_effort,expected:{...}}`.
It returns the complete updated ProjectView. No UUID/path mutation fields exist.
Init/create bodies now accept `ai_model` and `reasoning_effort`. The shared service
uses the existing lock, full-document validation, exact backup and atomic replace.

## Connection state and local configuration

The upper-right control reports the selected path: **ChatGPT connected**,
**Connect AI**, **Reconnect ChatGPT**, plan permission/usage/outage alternatives,
or **OpenAI API · key billing**. Green requires usable session/permission and a
valid account catalog, never just a key or identity-token presence. It does not
promise inference entitlement, unlimited usage, remaining credits or billing.
Expired health checks become subdued and offer Retry. Usage limits retain plan
mode and direct users to Manage usage. No inference is performed for health.

`GET /api/ai/connection` returns only sanitized mode/status/account labels,
actions, last check/TTL and the welcome flag. `/api/ai/models` returns the curated
intersection with the selected account’s list. Plan models use `models[].slug`,
`display_name`, and `visibility:list`; API-key models use `data[].id`. Saved model
choices are never silently rewritten when accounts change. Cached non-generating
checks have a 60-second TTL/3-second Retry cooldown, 8-second deadline and 1MB/
10,000-record bound. Tokens, raw provider bodies and full catalogs never reach React.
Account mutations require exact local Origin and JSON; auth responses are no-store.

The documented OSS SIWC flow uses discovery, a persisted host UUID, state/nonce,
PKCE S256, an already-listening exact 127.0.0.1 `/auth/callback`, the issued client
ID, and RS256 ID-token/JWKS verification. It checks issuer, audience, expiry,
nonce, subject/account binding and granted plan scopes before activation.
Returning accounts reuse their client registration. Rotating refreshes serialize
across processes and atomically replace tokens; terminal errors clear unusable
tokens while preserving the account/client mapping. Disconnect attempts provider
revocation; unconfirmed revocation is disclosed while local secrets are cleared.

Storage is `~/.config/sigma/credentials.json`, outside this checkout/projects:
owned 0700 directory, no-follow 0600 files, file locking, atomic replacement and
fsync. This portable local-file choice avoids a platform Keychain dependency;
other processes already running as your OS account remain a trust boundary.
`SIGMA_AUTH_HOME` can select an owned private test/storage directory outside the
checkout and project packages. Never copy tokens from another app or put them in
`.env`, Vite, URLs, browser storage, logs or project JSON. Only a retained ID-token
hint is sent directly to the trusted authorization endpoint through a backend
redirect, never in a React payload. See [security notes](asn8.2-security.md).

Optional API keys use `.env`; no configuration is needed for manual or ChatGPT
work. Restart with `./sigma ui` after changing a file key. The launcher
reads this checkout’s `ROOT/.env`, even when invoked from another directory;
manual sourcing is unnecessary. Existing environment variables win, including an empty key. The old enable variable is ignored. To use a changed file value, unset a
previously exported shell override before restarting. Simple dotenv assignments,
`export`, quotes, blank lines and comments are supported. Values are literal:
no shell execution or variable expansion. Missing files are normal; malformed or
unreadable files stop startup with a safe line/permissions instruction before
replacing the running instance. Never use frontend `.env` files or `VITE_` variables
for secrets. The pinned parser is python-dotenv 1.2.1. `.env.example` is a template.
CLI project commands use the same loader; setup/test do not load local credentials.
A standalone backend can use `uv run uvicorn sigma.server:create_app --factory
--host 127.0.0.1 --port 8000` for the same configuration behavior.

Replacement uses an exclusive launch lock and checkout-identity handshake over a
Unix socket in an owned 0700 `/tmp/sigma-ui-<uid>/<checkout-hash>/` directory.
Identity includes canonical path and directory device/inode; symlink aliases
resolve to the same checkout, while changed targets and other checkouts do not.
The supervisor signals no stored PIDs. Its pipe guardians own the actual server
process groups, give them SIGTERM, and bound cleanup with SIGKILL. A refused stale
owned socket is recovered under the lock; suspicious files/permissions or an
unverified live endpoint cause safe refusal. This is a local same-user trust
boundary, not protection from another process already running as your account.
Readiness checks a fresh non-secret instance ID at both API and Vite proxy, keeping
fixed routing and existing origin/host restrictions intact. Starting/restarting
never writes projects; Close Project remains navigation only.

Tests use explicit no-network fixtures. Live provider billing/quality is
unverified and no billable request is made by setup. With free 8000/5173 ports,
run the separate real-process/Chrome regression:
`uv run --with playwright python tests/ui_lifecycle.py`. It uses disposable
checkouts and fixture credentials, exercises restart/crash/conflicts, and leaves
normal project files untouched. Chrome is expected at the standard macOS path.

## Recent Projects and the included mathematical example (A9)

Home lists up to four distinct projects, newest successful access first. Create,
Open Project and recent-row clicks update the same application index; CLI
create/open/init and API create/open/init do likewise. Inspect, settings edits,
cancel and Close do not change access order. Titles refresh from the actual
project. Forget (the small ×) removes only the index entry, never research.
Missing/corrupt/moved entries remain clearly unavailable until located with
Open Project or forgotten. Opening a moved copy updates its path by stable UUID.

State is `~/.local/state/sigma/recents.json` (or `$XDG_STATE_HOME/sigma/`), with
an owned 0700 directory, 0600 index and persistent lock, atomic replacement and
fsync. `SIGMA_STATE_DIR` can point to an existing-parent absolute private directory
outside the checkout/project packages. The index holds only UUID/path/access
metadata and bootstrap facts; it is separate from OAuth credentials and project
JSON. Index failure warns without reporting a successful research save as failed.
The Home list then reports the state problem; Open/New Project remain available.

The first successful UI launch/Home setup copies the immutable v5 source
`samples/nonconsecutive-subset-sums/project.json` into the configured projects
root as `nonconsecutive-subset-sums.sigma/project.json`, with exclusive publication.
The provided Mathematical exercise opens with exactly three real Draft
strategies. It is initially labeled Included example, with no invented human
access time; opening it makes it a normal recent. Installation never overwrites
an existing project. An evolved same-UUID copy is preserved; other collisions are
reported. A per-root bootstrap fact prevents reseeding after deletion/forgetting,
and four genuine entries are never evicted merely to include the sample.
Changing the root installs its copy independently while UUID deduplication still
limits the installation's index to four. User edits never alter the Git template.

New/Edit Project now have a fixed title/action header: Create or Save Changes,
plus Cancel. Only the body scrolls, so controls remain visible on laptop and
phone screens. Busy saves disable both buttons and Escape; native required-field
validation, keyboard submit, retry and focus restoration remain in place.

The independent mathematical verification is in
[example-math-verification.md](example-math-verification.md), outside the active
project. The future [agent output reader design](agent-output-design.md) is only
a proposal; no autonomous work, proof execution or transcript renderer is added.
