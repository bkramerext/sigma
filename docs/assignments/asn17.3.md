# A17.3 — Research reliability, settings and workspace corrections

**Status:** Ready for Codex. Implement on main.

Read AGENTS.md, docs/HUMAN-AI-INTERACTION.md, docs/STATUS.md, and A17–A17.2 first. Inspect current implementation and actual UI. Preserve SIGMA's established design, data, provenance, billing safeguards, and research artifacts. This assignment supersedes conflicting A17.2 details.

## Workspace
1. Clicking outside an active inline project/strategy editor cancels without saving. Preserve Save/Cancel/Escape and keyboard accessibility; avoid canceling when clicking editor controls.
2. Strategy generation is background work, not an exclusive editing mode. Allow project/strategy editing during generation; prevent duplicate generation and stale overwrites. Hide the New button within Generate mode.
3. Remove the redundant divider in the Strategies toolbar.
4. Make Project, Strategies, and Sessions sections independently collapsible. Collapsing Sessions does not stop research. Preserve content and focus.
5. Sessions header displays live “n sessions, 1 running” or “n sessions, 0 running”, even when collapsed. Enforce at most one running research session per project in backend, including races and restarts.
6. Align STATUS header with session status data (Model, Current action, etc.) on desktop and mobile.
7. Keep Session #N as the session identity and show the related strategy separately. Present Confirm and start as a clear start confirmation, not visually part of the first session. Show strategy, billing mode, and effective limits before confirmation.
8. Replace rounded View strategy button with an underlined text link reading “Go to <strategy title>”, with the actual title. Expand Strategies, scroll the matching row into view, and focus it; navigate by stable strategy ID, not title.
9. When Plain representation is stale after Markdown edits, offer Convert to Plain using current authoritative content. Never silently revert to outdated text. Preserve data through failure and provide retry; test both directions.

## Project Settings
Make the existing Project Settings dialog conventionally tabbed, accessible, and responsive:
- **Main:** all existing settings, unchanged in behavior.
- **Limits:** five per-project persisted, explained and validated controls:
  - Research rounds: default 3; Investigator/Skeptic iterations.
  - Model calls: default 6; provider request allowance and potential costs.
  - Session duration: default 30 minutes; explain elapsed-time/pause semantics.
  - Maximum output tokens per call: default 4,000; explain provider limitations.
  - Maximum estimated session cost (USD): default unlimited; API-key billing only, not ChatGPT subscription.

Implement standard tablist/tab/tabpanel keyboard interaction, focus, Save/Cancel and atomic persistence. Preserve draft values across tab changes; cancel discards. Existing projects inherit defaults without migration loss. Snapshot effective limits when a session starts, enforce in backend, and retain old-session compatibility. Changing project settings must not silently modify active sessions.

For API-key sessions, capture provider-reported token usage, estimate costs with model-specific published pricing and cached-token adjustments where relevant, and show cumulative estimated spending. Check remaining cost budget conservatively before additional calls. If cost cannot be bounded or measured reliably, display unavailable and fail safely rather than fabricate precision. Distinguish estimated from actual billed amounts. ChatGPT subscription mode has no dollar accounting or budget enforcement.

## Research reliability
- Diagnose observed session failure “Research provider response exceeded the safe limit”. Current streamed response handler caps raw HTTP data at 128,000 bytes; streaming framing may consume the budget. Separate transport framing from final parsed output while retaining finite safety bounds. Do not blindly raise limit.
- Show precise failures in session UI and toast, preserve completed artifacts and history, and avoid a stuck UI. Provide Retry/Resume only when safe from duplicate model calls/charges; otherwise explain ambiguous completion.
- Show research rounds, model calls, elapsed duration, output budget and API estimated cost as applicable. Explain budget exhaustion.
- Enforce limits through concurrency, pause/resume and restart. Preserve per-request timeout separately from session-duration limit. Document any transport that cannot directly enforce output tokens.
- Preserve authentication identity, no silent billing fallback, and session/provenance integrity.

## Verification and delivery
Add regression tests for each requirement: click-away, concurrent editing/generation, collapse and live counts, single active session, status alignment, confirmation, link scroll/focus, stale Plain recovery, tabbed settings and persistence, limits, usage/pricing, streaming bounds, failure recovery and concurrency. Run ./sigma test, frontend typecheck/build, and real-browser desktop/mobile checks. Mock provider responses; no paid calls. Update docs/STATUS.md with actual results and limitations. Commit and push to main without a PR and report commit SHA. Avoid unrelated redesign.
