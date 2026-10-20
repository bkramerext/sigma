# ASN-3.1: Move Fork under Actions

Context: ASN-3 is complete. This is a small UI-only follow-up.

## Change

Move the existing **Fork** command into the strategy's **Actions** menu, alongside the other strategy actions. Do not leave a duplicate Fork control in its previous location.

Preserve the current disabled state and its explanation. Forking is not implemented; do not add any fork behavior, data model, or persistence.

Keep the menu's visual restraint, keyboard accessibility, focus behavior, and narrow-screen usability consistent with ASN-3.

## Verification

- Confirm Fork appears under Actions and nowhere else as a strategy command.
- Confirm Fork remains unavailable with its existing explanation and cannot imply success.
- Run relevant frontend checks and a real-browser interaction check.
- Record actual verification results in `docs/STATUS.md`.
- Commit and push the implementation with a specific message.

Do not change unrelated UI or functionality.
