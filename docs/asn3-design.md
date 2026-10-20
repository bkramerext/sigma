# ASN-3 design note

Home (`/`) remains the restrained project launcher. Open navigates to
`/project?path=<canonical project directory>`; the URL is the source of truth, so
reload and browser back/forward reopen the right project. Close navigates Home.
Screen headings receive focus on navigation; Home keeps its established copy.

The project workspace uses a compact branded header with a small Close project
link at its edge, followed by the project title and actual problem statement.
Strategy pool follows as an editorial list separated by rules, with modest New
strategy and unavailable Generate strategy actions. A short empty state explains
how to begin without claiming work has happened. Technical metadata and events
remain accessible in a disclosure below the pool rather than dominating it.

New strategy expands an inline form with title and hypothesis/approach. Focus
moves into it; Cancel/Escape returns to its trigger. Failed saves retain text.
Saved rows show their human authorship and full approach. Each row has a compact
native disclosure for Strategy actions, with nested Schedule and Report artifact
disclosures. Unimplemented commands are disabled beside visible explanations;
Audit describes a future explicit research record, never private model reasoning.
Native disclosures and ordinary controls provide keyboard/mobile affordances.

Storage v2 adds stable strategy IDs, title, approach, author kind, UTC creation
time, and linked creation events. Read v1 unchanged; migrate only on first write,
keeping an exact v1 backup. Cooperative writers lock a separate file, validate
current state, stage/fsync a complete document, and atomically replace it. An
external edit detected before publication aborts. This remains a small local JSON
store, not a scheduler or general transaction engine. POSIX lock and filesystem
crash limitations will be documented alongside existing storage decisions.
