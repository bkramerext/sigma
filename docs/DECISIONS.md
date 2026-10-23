# SIGMA architectural decisions

2026-10-20

## Foundation

- **Project:** Portable `.sigma/` directory; repository RH seed initializes on first open.
- **Services:** Browser, CLI, API, and scenarios share typed Python application services.
- **Stack:** Python/uv, FastAPI, argparse, React/TypeScript/Vite.
- **Research direction:** Strategies and forks, independent evaluation, bounded scheduling, human controls.
- **Testing:** Executable scenarios and real browser checks; bounded research agents are active, while arbitrary code execution was deferred until A19.

## Storage

- **Schema v1 (SPEC-001):** Versioned `project.json` with UUID, title, problem, and ordered events. Reads validate without mutation. Initialization uses staged, fsynced, no-replace publication; existing research is never overwritten.
- **Schema v2 (ASN-3):** Human strategies have stable UUID, title (1–200 chars), approach (1–10,000 chars), author kind, timestamp, and matching `strategy.created` event. No agent activity or genealogy is implied.
- **Schema v3 (Edit/Remove):** Strategy `removed_at` marks departure from the active pool; the full record remains in the package. `strategy.removed` links to the timestamp/ID. `strategy.updated` retains before-and-after title/approach values. Validation checks edit chains, final values, and removal history; IDs, authorship and creation time stay fixed.
- **Migration:** v1 remains readable unchanged. First strategy save creates an exact `project.v1.json` backup, then publishes v2. First edit/removal upgrades v2 to v3 with an exact `project.v2.json` backup. Backup conflicts abort; older clients cannot read newer formats. Unchanged edits do not migrate or append events.
- **Writes:** Cooperative writers serialize through persistent POSIX advisory lock `.write.lock`. Stage/fsync and atomic replacement keep reads complete; validation and a byte comparison detect some external edits.
- **Limits:** Local POSIX filesystems only. Noncooperating edits can race; directory entries are not fsynced; hard kills may leave staging files. A lost HTTP response can leave an ambiguous completed save. Full-document rewrites scale with project size; SQLite remains a possible later migration.
- **Safety:** Reject corrupt/incompatible state and unsafe lock/state symlinks. Credentials stay outside project files.

## Navigation and interaction

Home `/` launches projects; `/project?path=...` is the research workspace. Strategy creation persists through shared services. Future commands use native nested disclosures with disabled controls, not fake operations. See [design note](../tickets/t3-design.md).


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

## A8: project settings and connection proof

Schema v6 persists `ai_model` and `reasoning_effort` alongside existing project
metadata. Every new init/create writes v6. Existing v1–v5 reads derive a reviewed
legacy bootstrap (Sol/High by default) without rewriting. Metadata updates use the
existing lock/stage/full validation/atomic replace and exact old-version backup.
`project.updated` retains complete old/new five-field snapshots, checks chain
continuity and final state, and forbids no-op audit entries. A compare of all five
expected settings under lock rejects stale editors, while independent strategy
writes retain their updates. UUID/path are never mutable settings. V6 is never
downgraded by stage/order/manual strategy operations. Old provenance retains null
thinking; new signed receipts include actual returned model and requested effort.

The one shared Create/Edit form saves once per explicit submit, restores focus,
and retains drafts on failure. New uses the derived readonly destination; Edit
shows the unchanged location. Unsupported new model/effort pairs require explicit
correction; unavailable stored pairs can survive metadata-only edits. The main
heading's 44px pencil is the only project-settings entry in the workspace. Close
remains navigation only; future real active agents will require confirmation and
a clear continue/stop policy, not an imaginary A8 runner or Close-time save.

A reviewed server catalog includes the verified Responses/text/strict-JSON/
reasoning aliases Sol, Luna, Astra, deliberately offering the common four levels
Low/Medium/High/Extra high. Official model links and verification date are in
Getting Started. Account IDs are intersected with that catalog; unknown IDs and
raw provider metadata never become UI options. Relative $/$$/$$$ cost labels are
editorial tiers linked to official pricing, not inferred token prices. No pricing
lookup or cost accounting is claimed. The form prefers verified Sol/High, explicitly
discloses a different initial default when necessary, and qualifies offline
Sol/High. Saved choices never change because discovery fails or a model vanishes.
`SIGMA_AI_MODEL` affects only missing legacy settings when it names a reviewed
model; an unreviewed override is called out. V6 project choices always win.

Authentication status is an independent, bounded GET /v1/models proof, not a key
presence indicator or proof of model generation/billing. A valid 200 list is
required for fresh green. Missing/auth/permission/rate/network/invalid response
states have generic safe guidance. Backend requests share one 60-second cache
and pending task, with a 3-second manual Retry cooldown, 8-second deadline and
1MB/10,000-model cap. Key changes invalidate cache; secrets are never returned.
Frontend checks once per App mount, reuses it across routes and marks expired
checks stale using a timer without polling. Settings discovery/proposal readiness
share the backend cache. Workspace status space is reserved to avoid content
jumps between longer labels; Home's status occupies existing header/empty sky
space without moving the accepted hero. The browser can retain stale local status
until Retry even if another client refreshes the server cache; it never falsely
claims current success from that older check.

Generation snapshots project/context/model/effort before awaiting discovery. The
selected reviewed pair plus fresh cached account membership are required, then
`reasoning.effort` is sent explicitly. Max output is 25,000 tokens including
reasoning (per official initial-budget guidance), while visible field limits and
the 60-second hard HTTP deadline remain. High/Extra high may still time out or
return incomplete: failures never retry, lower thinking, substitute models or
save automatically. Receipts use the immutable snapshot even if settings change
while generating. No live billable calls were used to test this integration.

A clean-checkout comparison exposed A6's dev asset copy running after Vite's
public-file scan. Copy now happens during config evaluation, before that scan;
canonical PNG bytes are unchanged. This fixes first-launch artwork availability
and requires no human file copying.

## A23: descriptive project difficulty

Schema v8 adds `difficulty` with the stable values `easy`, `medium`, and `hard`.
New projects default to `medium`; documents from v1–v7 read with unknown
difficulty (`null`) without being rewritten. The UI omits the header badge and
project-details row when difficulty is unknown, and reports omit the field. An
edit that leaves a legacy difficulty unknown retains its existing schema; the
first edit that chooses a difficulty upgrades the document through the
existing exact-version backup, lock, validation, and atomic replacement path.
Project settings audit snapshots include difficulty; historical snapshots that
predate the field are interpreted as unknown. Invalid stored values are
rejected as invalid project data. Difficulty is descriptive metadata only and
does not affect agent prompts, scheduling, budgets, or outcomes. The Maximum
Regions sample is explicitly `easy`, and the sample-copy path preserves the
source value. JSON audit exports and deterministic reports include the field.

## A8.1: local configuration and foreground instance ownership

Use pinned python-dotenv 1.2.1 parsing (without shell/variable expansion or parser
logging). Validate the complete checkout-root `.env` before setting missing
process environment values; exported variables win. UI, CLI project commands and
the standalone backend factory share this loader. Setup/test avoid loading it.
Configuration errors occur before replacing the current UI. Provider enablement
and per-generation consent remain separate.

Serialize startup/replacement using a no-follow owned regular lock and a private
Unix control socket under fixed `/tmp/sigma-ui-<uid>/<hash>/` directories verified
0700/owned/non-symlink. Canonical checkout path plus device/inode form the identity;
no PID file or port listener grants shutdown authority. A live identity handshake
requests shutdown, then waits for a cleanup acknowledgement before binding new
servers. Kernel locks and verified refused sockets recover crashes. A stalled
launch lock times out safely. Same-user malicious processes are outside this OS
account trust boundary.

Each server runs inside a session-leader pipe guardian. Closing the supervisor's
private pipe, including on SIGKILL/crash, causes the guardian to TERM its own
actual process group and bound cleanup with KILL while retaining group ownership.
The supervisor never signals stored PIDs. This adds two small foreground lifecycle
helpers, not daemons or research agents. Existing instance replacement exits the
old terminal cleanly. Fixed ports and current strict localhost host/origin checks
remain; unrelated/different-checkout/unverified listeners produce a named safe
conflict rather than automatic alternate ports. This avoids extra dynamic proxy
and origin configuration. A per-launch public non-secret readiness ID must match
through both backend and frontend proxy before the URL is announced. Project
storage, Close semantics, frontend design and artwork are unchanged.

## A8.2: explicit billing modes and remembered ChatGPT authorization

The default connection path is ChatGPT plan with no key/flag requirement for
manual research or sign-in. Header and on-demand proposal auth share one account
control; OAuth alone never generates. A pending generation retains seed/draft,
checks project/account bindings, resumes once, and still needs explicit Save.
API-key billing is a persisted explicit application choice, never a fallback.
The old enable gate and recurring consent checkbox are removed. Mode/account
stay outside research packages; schema v6, High and historic provenance remain.

Use documented OSS SIWC dynamic registration with stable host UUID, PKCE/state/
nonce, an exact loopback callback and validated RS256/JWKS identity. Credentials
and issued-client/account mappings use a portable private 0700/0600 no-follow
app store, atomically replaced under a cross-process refresh lock. A Keychain
integration is deferred; same-OS-account code remains the trust boundary. Rotate
refresh tokens together, respect earliest refresh, retain account mapping after
terminal errors, and disclose unconfirmed remote revocation. An unreadable
account store leaves the unverified model defaults usable for manual creation.

Plan and API-key providers have different model-list and inference contracts.
Plan requests stream SSE through a validated completion with no preview-forbidden
fields; key mode retains bounded non-streaming Responses. Both use reviewed
models/efforts, immutable request snapshots and common structured validation.
Limits/outages/unsupported capability errors never retry or change billing.
The exact docs, storage/security limits and fixture-only verification boundary
are recorded in [A8.2 security notes](../tickets/t8.2-security.md). Existing art stays fixed;
only the unmodified official ChatGPT sign-in mark is added. A9 remains separate.

## A9: application recents, exact example import and bounded dialogs

Use a separate versioned four-entry index under XDG/per-user state. Records carry
existing canonical UUID, canonical path, actual access time, and an honest included
example flag. A private no-follow lock serializes multiprocess read/modify/atomic
replace; publication fsyncs the file and directory. List refresh fully validates
at most four actual project documents and returns minimal metadata; titles are
not a stale parallel authority. Missing/corrupt/identity-changed paths are shown
unavailable without writes. Forget only changes the index. Successful shared
create/open services record access; explicit init adapters do the same. Inspect,
metadata edits and Close stay read-only with respect to access order. Home passes
the already opened/created view into the workspace, avoiding an incidental second
Open write during navigation.

Import the supplied v5 example byte-for-byte through an exclusive reservation,
validated schema/UUID and no-replace publication. Never synthesize research or
reset an existing copy. Root-specific bootstrap facts are committed with initial
index inclusion under the same lock; deletion, eviction and forgetting do not
reseed. Four genuine accesses take priority. Existing same-UUID evolved copies
are preserved, different occupants/symlinks report conflicts. Project data and
index cannot form one cross-file atomic transaction: an index failure is reported
as a secondary warning, not a failed research creation that encourages duplicates.
A bootstrap crash after project publication is recoverable from its UUID. A hard
crash can leave an empty project reservation requiring inspection; no empty
existing directory is silently reused.

The shared settings dialog remains one native form with a non-scrolling header
and one scrolling body. Buttons are title-adjacent; narrow screens use a deliberate
second header row. Both busy buttons and Escape consult the submit guard. Accepted
Home/workspace artwork and strategy layouts remain unchanged. Independent DP,
exact transfer identities and an analytic recurrence/density derivation live
outside the unproved example. Mathematical transcript rendering is design-only.

## A11: sample catalog and persistent projects

Discover shipped `samples/*/project.json` documents as a read-only catalog. A sample
selection opens directly with no dialog by creating an independent working copy
under the configured projects root. Each copy receives its own project identity
and a distinct path/name, while retaining the sample's strategies and event
history. This keeps the source-controlled file intact and lets the user run and
edit the copy as a regular project. Existing files are never overwritten; a
catalog directory with invalid project data is reported unavailable.

Recents records actual user creates/opens, excluding sample project identities. The old
four-entry index and access ordering remain; reads migrate out legacy automatic
example entries and canonical sample identities without touching project files.
The catalog lists all discoverable shipped projects, with the Jesus example placed last
as a presentation choice. Home presents Samples before Recent and selects Samples
by default per the later UI request.
The existing index schema retains its dormant bootstrap metadata for backwards
compatibility; no startup bootstrap or automatic example installation runs.

## A14: bounded role-isolated strategy generation

Keep the prior single-call proposal API for compatibility, but route the browser's
Generate with AI action through a shared Python coordinator and an SSE endpoint.
The coordinator invokes exploration and skeptical review separately with the
project-selected model and thinking level, then branches on the review. It can
revise once per candidate or try a second candidate; six calls, two candidates,
per-call deadlines and a two-minute overall deadline cap the work. A global
single-run gate avoids overlapping local generation. Project content is bounded
and passed whole, including removed strategies; overflow fails before omission.
No code, literature, proof or external research tool is executed.

The browser validates event order and waits for a terminal stream event before
showing a successful draft. It retains a human-editable unsaved draft and uses
the existing signed acceptance receipt when explicitly saved. This keeps
generation read-only and separates model review from verified research. The
cost is that the first slice runs one local generation at a time and rejects
large corpora rather than searching or summarizing them automatically.

## A15: text representations and in-place edits

Keep the current `project.json` problem and strategy approach fields as the sole
current authored source consumed by API, CLI, and strategy generation. Store
format identity, authored revisions, and AI-derived Plain/Markdown revisions in
an adjacent versioned `text-representations.json`, written with the existing
project lock and atomic staging. This avoids rewriting v1–v6 or sample fixtures
when a conversion is first requested. Source revisions are keyed by the exact
UTF-8 SHA-256 digest; a conversion records source format/digest, time, model,
provider, thinking level and warnings. Edits promote the saved representation
to source and leave the counterpart inspectable but stale. The companion is
published before a source edit so a crash cannot label an old body as a new
source; a failed project publication can leave an unused future revision in the
companion, but current reads only match the actual project body digest.

Conversion is one bounded provider call with the project's selected
model, thinking level and connected account/billing mode. The service rejects
concurrent calls, validates the binding again before saving, and rechecks the
source/model under the project lock. It neither interprets Markdown into Plain
with string stripping nor asks a model to render Markdown: the latter is a
local, read-only React Markdown/KaTeX preview. Markdown HTML, external images,
unsafe links and KaTeX trust are disabled. Validation catches malformed,
truncated and obvious raw-TeX Plain output, but cannot prove semantic or
mathematical equivalence; the UI labels AI-derived text for human review.
Per the later UI request, selecting a missing or stale view initiates its
conversion automatically; cached switches remain local and free. Failure or
cancellation retains the source and exposes Retry. This means a view switch
may incur provider usage. Project title and Plain/Markdown description edits
start in place and save only when requested; Rendered activates the Markdown
source editor. Other project options remain in Project Settings. Home stores
only the last opened path as a convenience pointer and validates it on display;
the sidebar collapse preference is kept locally across navigation.

## A19: isolated research Python execution

Provide `sigma.python_sandbox.execute_research_code` and a local project API as
the stable seam for A18 agents. The Investigator may propose one optional
program, which runs once before the Skeptic review; the Skeptic receives the
code and its returned status, execution ID, output, and artifact metadata. The
record is linked from the role step and saved research artifact. Each call runs
once in a locally built image resolved to its immutable image ID, with no
network, host mounts, or automatic image pull. One backend process admits at
most one run to bound aggregate local resource use. Persist the exact code,
output, exit state, image ID, limits, captured-file metadata, and optional
session/strategy/cycle references under a private project sidecar. Execution
results are finite computation evidence, not mathematical verification. Lean
remains a separate optional checker as specified by `LEAN_VERIFICATION_PLAN.md`.

Use a standalone Docker proof of concept first, then the same fixed isolation
boundary in the SIGMA service. Pin the Python base image by digest and pin all
Python dependencies. Build-time downloads are permitted; runtime networking is
disabled. Container escape protection depends on the trusted host kernel and
Docker daemon.


## T26: SageMath as an explicit research runtime

Keep the scientific-Python contract and add a mutually exclusive `sage_code`
proposal with `sage_execution` evidence. Share the fixed stdin protocol,
container isolation, durable reservation, capture/storage and admission gate.
Record runtime/version/native syntax and source hash rather than inferring an
interpreter from source text. Historical records without runtime mean Python.
Sage failure reuse across cycles requires the same version/syntax/image profile;
recovery within the original cycle preserves its reservation without rerunning.

Every role call gets a locally observed capability snapshot and explicit
instructions; only Investigators dispatch, while Skeptics request follow-ups
through the next Investigator. Prompt/schema construction is shared with cost
reservation. This adds no model call, automatic retry or billing fallback.

Use an optional, digest-pinned official Sage 10.8 amd64-derived image with
native Sage preparsing. Keep all isolation controls but advertise distinct
Sage limits (60 seconds, 1 GiB memory, 128 MiB temporary storage): emulated cold
startup alone took approximately 20–30 seconds here. Python retains its
15-second/512-MiB/64-MiB limits. No image build/pull occurs during execution.
Stopping dispatched work preserves Python's bounded-completion and evidence
capture semantics; queued work never starts after stop. Exact computations
and agent agreement do not establish formal verification. See
[Sage execution](SAGE-EXECUTION.md) for setup, contracts and measured limits.

## T22.2: opt-in cloud identity boundary

Cloud authentication is disabled by default and sits at the FastAPI API boundary.
When enabled, use Google authorization-code OIDC with PKCE, one-use server-side
state/nonce, strict signed ID-token validation and exact verified-email
authorization. Store hashed opaque sessions, access rules and change audit in a
private SQLite database outside research packages. Recheck authorization on
every request so revocation takes effect without waiting for cookie expiry.
Keep the configured bootstrap administrator bound to its first stable Google
subject. Preserve local ChatGPT authorization; hosted Google identity does not
authorize provider calls, and cloud mode denies the existing process-wide AI
routes. This ticket establishes access to the current API but deliberately does
not migrate or isolate project storage by user; it is not a completed
multi-tenant deployment. Unapproved verified identities get an access screen,
the configured public invitation contact through `mailto:`, a fresh Google
account-selection flow, and a no-workspace `/demo` handoff. The curated
read-only Demo itself remains in parent T22. See [cloud authentication](CLOUD-AUTH.md).
