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
