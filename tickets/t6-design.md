# ASN-6 interaction and persistence note

Keep the Home artwork, positioning and typography. Replace the exposed path form
with adjacent Open Project (copper) and New Project (outlined translucent) commands;
stack on small screens. Recent Projects remains an honest secondary empty state.
Both commands open a compact dark native dialog, focus its first field, retain
text on error, prevent repeated submits, and restore the initiating button on
Cancel/Escape. Busy requests cannot be dismissed accidentally.

Open uses the existing path API and a prefilled local path with clear examples;
no fake Browse control. New asks only for name, problem and mode. Its read-only
destination preview comes from the same server-side naming function as creation.
Successful open/create navigates directly to the existing workspace.

Managed creation defaults to the repository's absolute projects directory, with
an optional absolute SIGMA_PROJECTS_ROOT override. The root must already exist,
be owned by the server user and not be a symlink. Reject path-like names; normalize
other names to a deterministic slug. Reserve the destination with exclusive mkdir,
then use existing atomic project-file initialization. On failure remove only the
empty directory owned by that attempt. Concurrent/existing destinations never
get replaced. A partial directory is not an openable project before publication.

Schema v4 persists a research_mode enum and retains v3 strategy/history semantics.
Older documents load as Default without writes; their established lazy migration
and exact-backup behavior stays intact. New Default and Mathematical projects use
the same services and model. Artifact engines remain deferred: LaTeX is universal,
while future Lean support is mathematical-mode-specific.
