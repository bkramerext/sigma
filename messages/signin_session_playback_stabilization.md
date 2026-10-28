# Sign-in and session playback stabilization

Status: draft work in progress.

Base: PR #296 head `62af6bf8a27954d363f9ca3c8623dc68ff5fcc5c`.

## Scope

- Inventory and reproduce sign-in, account authorization, invitation/membership, and mode-switching defects.
- Inventory and reproduce research-session loading, saved-session playback, event ordering, resume, and error-display defects.
- Fix related defects together on this branch, with deterministic regression coverage and browser verification.
- Preserve correct personal-versus-sponsored provider behavior and error provenance.

## Integration and release

This draft PR targets PR #296's branch while #296 is stabilized. After #296 merges, retarget this PR to `main`, then reconcile with the actual merge commit. Keep draft until functional review is satisfactory; perform final full CI verification before marking ready and merging.

Do not create separate PRs for fixes in this scope.
