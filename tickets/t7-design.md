# A7 implementation choices

Use the exact 1672×941 approved reference for visual comparison only. Keep Home
and branded PNG bytes unchanged. Place the split action in the project intro;
compact rows expose title/one-line real-text preview, stage with ring and text,
three-dot commands, and a separate upper-right grip. Expanding row details shows
full approach, real provenance and creation date. No invented research IDs.

Stages are manually tracked Draft, Ready to explore, Exploring and On hold.
A native dialog records explicit stage changes. The grip uses pointer capture
with touch-action disabled only on the grip; keyboard Space/arrows/Enter/Escape
shares the same preview/drop/cancel path. Reorder submits the exact active ID
set and previous order to reject stale concurrent changes. New items append;
removed records retain creation order in storage. Failed saves revert previews.

Schema v5 adds one authoritative active_order, stage and optional preview plus
AI provenance. Legacy reads derive creation order and Draft without writes.
Existing manual create/edit/remove migrations remain compatible; the first
stage/reorder/AI-assisted save upgrades to v5 with an exact old-version backup.
Strict replay validates order/stage history as well as existing audit chains.

AI is a nonmutating, explicit opt-in proposal service using OpenAI Responses
strict structured output. A bounded full context is sent or rejected (never
silently truncated). One request at a time, hard timeout, no retries/tools or
background jobs. Review is editable; only Save persists. A signed short-lived
receipt binds returned provider/model metadata to the project on acceptance.
Cancellation aborts the local HTTP request; provider billing may already occur.
Tests use a clearly identified HTTP fixture, never pretend it is live AI.
