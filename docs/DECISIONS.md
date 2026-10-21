# SIGMA architectural decisions

2026-10-20

## Foundation

- **Project:** Portable `.sigma/` directory; repository RH seed initializes on first open.
- **Services:** Browser, CLI, API, and scenarios share typed Python application services.
- **Stack:** Python/uv, FastAPI, argparse, React/TypeScript/Vite.
- **Research direction:** Strategies and forks, independent evaluation, bounded scheduling, human controls.
- **Testing:** Executable scenarios and real browser checks; agent runtime deferred.

## Storage

- **Schema v1 (SPEC-001):** Versioned `project.json` with UUID, title, problem, and ordered events. Reads validate without mutation. Initialization uses staged, fsynced, no-replace publication; existing research is never overwritten.
- **Schema v2 (ASN-3):** Human strategies have stable UUID, title (1–200 chars), approach (1–10,000 chars), author kind, timestamp, and matching `strategy.created` event. No agent activity or genealogy is implied.
- **Schema v3 (Edit/Remove):** Strategy `removed_at` marks departure from the active pool; the full record remains in the package. `strategy.removed` links to the timestamp/ID. `strategy.updated` retains before-and-after title/approach values. Validation checks edit chains, final values, and removal history; IDs, authorship and creation time stay fixed.
- **Migration:** v1 remains readable unchanged. First strategy save creates an exact `project.v1.json` backup, then publishes v2. First edit/removal upgrades v2 to v3 with an exact `project.v2.json` backup. Backup conflicts abort; older clients cannot read newer formats. Unchanged edits do not migrate or append events.
- **Writes:** Cooperative writers serialize through persistent POSIX advisory lock `.write.lock`. Stage/fsync and atomic replacement keep reads complete; validation and a byte comparison detect some external edits.
- **Limits:** Local POSIX filesystems only. Noncooperating edits can race; directory entries are not fsynced; hard kills may leave staging files. A lost HTTP response can leave an ambiguous completed save. Full-document rewrites scale with project size; SQLite remains a possible later migration.
- **Safety:** Reject corrupt/incompatible state and unsafe lock/state symlinks. Credentials stay outside project files.

## Navigation and interaction

Home `/` launches projects; `/project?path=...` is the research workspace. Strategy creation persists through shared services. Future commands use native nested disclosures with disabled controls, not fake operations. See [design note](asn3-design.md).


## Manual strategy changes

Edit and Remove use the same locked, staged publication path as creation. Edits
replace the current name/description and preserve earlier text in audit events;
concurrent edits serialize with the latest save winning, without a stale-dialog
conflict check. Earlier values remain reviewable. Remove is a pool operation,
not erasure: active-list queries filter removed records, while inspection retains
them. Repeat removal, unknown IDs and edits of removed strategies fail without
rewriting state. Neither restoration nor permanent deletion is exposed.

Both commands live under the chevron's Actions group. Edit uses a prefilled modal;
Remove uses a named confirmation with Cancel focused by default. Native dialogs
trap focus and support Escape. Successful edits focus the strategy heading;
removal focuses Strategy pool; cancellation returns to the chevron. Failed saves
keep the dialog and entered text. The remaining scheduling/report/fork commands
stay unavailable.

## ASN-6: managed creation and research modes

New initialization writes schema v4 with `research_mode` as an extensible string
enum (`default`, `mathematical`), preserving v3 strategy/history semantics. Unknown
modes are rejected. Existing v1–v3 documents read as Default without mutation;
their existing lazy migrations and byte-exact backups are unchanged. Mode is
returned consistently through shared services/API/CLI and displayed in Project
details. Future LaTeX artifacts apply to every mode; Lean applies to Mathematical.
Neither artifact engine is implemented here.

Managed creation reserves a deterministic normalized name with exclusive mkdir
under an explicit owned local root (checkout `projects/`, or absolute existing
`SIGMA_PROJECTS_ROOT`). Preview and creation share the server naming function;
create accepts no client path. Reject final-root symlinks, missing/foreign roots,
unsafe names, and any existing destination, including broken symlinks. Reserve
first, stage/fsync the project document, and publish without replacement. Failure
removes only an empty reservation; concurrent files are retained. A crash may
leave an empty reserved directory requiring inspection/removal before retry. This
is a cooperative local-filesystem design, not protection against a noncooperating
process swapping parent directories or changing ownership during a request.

The Home command pair uses native modal dialogs for focus trapping and Escape,
with focus restoration on cancellation, retained inputs on error and synchronous
duplicate-submit guards. Creation shows server-derived location context rather
than a path editor. Canonical artwork is copied byte-for-byte by Vite on startup
and build; accepted Home art is committed unchanged from its pre-assignment bytes.
ASN-5 workspace styles and ASN-4.1's on-hold animation remain untouched.

## A7: Strategies, manual stages and proposal review

Schema v5 adds a single `active_order` list, per-strategy `stage`, optional one-line
`summary` (empty means derive preview), and nullable provider/model `provenance`.
The underlying strategies array stays in creation order, including removals;
active order is the sole presentation order. New items append; removal drops its
active ID. Legacy reads derive order and Draft without mutation. Existing manual
write/migration behavior remains; first stage/reorder/summary/provenance write
upgrades to v5 through the existing lock/stage/exact-backup path. All later writes
preserve v5. No-op stages/orders do not migrate or append events.

Validation replays creation/removal/reorder events to the exact active ID set and
order, and replays manual stage transitions from Draft to the final record for
every strategy. Unsupported stages, mismatched before-values, duplicate or removed
IDs and incomplete orders are rejected. Reorder requires the caller's prior order
to match under the same write lock; stale concurrent creates/removes/reorders fail
instead of clobbering newer ordering. Concurrent independent stage/edit writes
serialize; last stage write wins with every transition retained. Existing edit and
removal semantics/identities/timestamps remain intact. Editing an approach clears
its summary to prevent a misleading old preview; the full previous approach is
still audited.

Rows use a native details expansion and a separate three-dot command disclosure.
Only the corner grip begins dragging. Pointer capture plus document-level move/up
handling survive keyed DOM relocation on touch; removing an old error during
pickup was avoided to keep targets stationary. Keyboard and pointer share the
same preview/drop/cancel logic; save failures revert. Menus are viewport-clamped,
with mobile bottom surfaces. Home rules/artwork are untouched.

The opt-in OpenAI adapter uses the documented Responses REST API, strict JSON
schema and runtime-pinned httpx. Configuration is server-wide, AI off by default,
model `gpt-4.1` unless explicitly overridden. Full bounded context is sent or
rejected, never silently truncated. One request per process, no retries/tools,
60-second HTTP deadline, bounded response and independent field validation.
Exact/strong lexical duplicates are rejected; this cannot establish semantic
novelty or mathematical validity, which require human review.

Generation never saves project state. Save accepts editable fields and a signed
24-hour receipt binding returned provider/model metadata to project identity.
Process-local receipt secrets are never persisted or returned; restart invalidates
receipts. This keeps provenance honest without a parallel draft store. Drafts may
be edited before acceptance and are lost on dialog close. Lost save responses can
still be ambiguous under the existing persistence contract. A cancelled local
request cannot guarantee the provider stops billing or computation.

The endpoint awaits ASGI disconnect events directly and cancels/joins both the
provider and connection-watcher tasks. Polling `Request.is_disconnected()` missed
receive-channel events behind middleware in an actual HTTP disconnect test; it
was replaced before completion. Provider errors are generic and never include raw
request/response dumps or keys. No configurable external endpoint, redirects,
ambient proxy forwarding, or browser credentials are introduced. `store:false`
does not override provider retention policies. Live billing/quality is unverified:
all development integration tests use clearly identified controlled HTTP fixtures.
