# A8.2.1: Keep AI connection status fresh without nagging the user

**Status:** Implemented and verified. Targeted follow-up to **implemented A8.2**. This is a UI/connection-health fix, not a new authentication feature, a provider redesign or part of A9.

## Problem demonstrated in the current code

During ordinary use, the upper-right header quickly changes from **ChatGPT connected** to **AI connection check expired**. This happens after roughly **60 seconds**, even when the user is actively working and the ChatGPT OAuth session is valid. The user must manually choose Retry connection.

This is caused by two independent existing choices:

- `src/sigma/openai_connection.py` sets `TTL = 60` for a *non-generating* `GET /v1/models` authentication/model-catalog check. This TTL describes freshness of a **health check**, not validity of an OAuth access token or ChatGPT sign-in.
- `frontend/src/ai-connection.tsx` initially invokes `refresh()` once. `ConnectionStatus` independently starts a `setTimeout` based on `checked_at + ttl_seconds` and changes the visible heading to **AI connection check expired**, without triggering a new check.

The result is misleading and disruptive. **Do not make the user manage SIGMA's health-check cache.**

## Required experience

1. On first load, determine the actual connection state as today. No sign-in dialog or billable inference call on load.
2. **While SIGMA is actively visible, silently refresh verified connection health before the cached result expires.** With today's 60-second backend TTL, target approximately 45–50 seconds after the last successful check, derived from server `checked_at` and `ttl_seconds`, with reasonable bounds. Do not poll at subsecond/high frequency, and do not lengthen or remove server-side safety limits merely to disguise the symptom.
3. **Keep the upper-right status stable during a routine refresh.** If it says “ChatGPT connected”, don't flash “Checking AI…” and don't display “AI connection check expired” simply because a scheduled health check is in progress. A discreet internal checking state and/or a small non-disruptive indicator in the expanded details is fine.
4. **Pause periodic network checks when the browser tab is hidden** (Page Visibility API). On visibility restoration, check promptly if the state is due or stale; don't trigger several queued checks. An optional online/resume event may similarly request one coalesced check. Keep the existing account/status label until a check is justified, but don't indefinitely represent a past green check as current verified status if the refresh repeatedly fails.
5. For a **real negative result**, show the actual meaning:
   - OAuth session genuinely needs new authorization: **Reconnect ChatGPT**.
   - Missing plan permission or usage limit: retain A8.2's accurate plan-specific guidance.
   - Provider/network/timeout failure: **temporarily unavailable / Retry**, not “signed out” and not fabricated green; preserve stored account selection and research data.
   - API-key mode: verify the same way, with correct **separately billed API** terminology, and never switch to it from ChatGPT-plan mode automatically.
   - No configured account/manual-only state: **Connect AI** remains usable; background polling must not nag users into connecting.
6. **If a refresh throws or HTTP fails**, don't leave a stuck spinner or silently ignore errors while displaying an indefinitely green connection. Show a calm non-blocking **status unavailable** indication and a working Retry action; preserve existing account data. Retry transient failures with modest capped backoff **only while visible** (e.g. 30 s → 60 s → 120 s, capped at 5 minutes). Reset backoff after success or deliberate account/mode change. No rapid retries, sign-in popup or repeated toast.
7. The existing **one-time “You're using your ChatGPT plan” toast** was explicitly liked. **Preserve its exact one-time welcome semantics**. Automatic health checks must neither retrigger the toast nor dismiss it, create additional notifications, or write a `welcome` acknowledgment repeatedly.
8. Manual **Retry connection** remains available and can force a new check, respecting the backend's existing 3-second anti-hammer cooldown. Show progress only in the popover for an explicit Retry, without interrupting work elsewhere.

## Engineering guidance and boundaries

- Put the periodic refresh lifecycle at the **shared `AIProvider` level**, not in each `ConnectionStatus` component. Home and workspace must not create two timers or two competing network requests. Keep status display in `ConnectionStatus` a presentation of central state.
- **Separate `initialLoading`, `backgroundRefreshing` and `manualRetry` (or equivalent) so background freshness maintenance does not replace the entire header with a loading state. Reuse the existing `check.current` request coalescing for overlapping manual, background, sign-in completion and account changes; strengthen it where necessary.
- Use response `checked_at` **only as the timestamp for that particular successful provider check**, not as evidence of OAuth token expiration. Do not conflate provider status TTL with `chatgpt_auth.session()` `expires_at`; session refresh stays backend-owned. Handle missing, malformed, future-skewed, or null `checked_at` defensively without a zero-delay loop. Account for tab suspension and browser clock shifts.
- Avoid old in-flight results overriding an explicit Disconnect, switch-account, switch-mode or newly successful Sign in. Deduplicate checks or discard stale responses against the current identity/generation; ensure timers are cleaned up at unmount and recreated appropriately after state transitions.
- Do not launch a new OAuth attempt, open tabs, make any `POST /v1/responses`, or send a generation just for health. Provider checks may continue to use the existing bounded `GET /v1/models` through `GET /api/ai/connection?refresh=true`. Do not alter A8.2 billing boundaries or save any research data on connection checks.
- Retain localhost security, private credential storage, refresh-token serialization, A8.1 launcher behavior and approved Home/workspace artwork. No new configuration flags, preference screens or gates.
- Keep the frontend understandable; do not build a general-purpose polling infrastructure merely for this small status control. Avoid event-listener leaks, duplicate intervals, race-induced React updates after unmount, and repeated checks due to rerenders.
- The existing 60-second backend cache is a legitimate rate-control choice; prefer to solve lifecycle/status semantics client-side. A small documented backend adjustment is permissible only if tests prove it necessary. Never make an unsupported guarantee that `/v1/models` confirms generation entitlement, credits or remaining usage.

## Verification

Implement runnable regression coverage in existing `browser_checks/chatgpt.py` and/or a focused browser scenario, plus backend tests if any backend behavior changes.

1. **Time travel / controlled clock:** With a confirmed ChatGPT state and `ttl_seconds=60`, after 45–50 seconds of foreground activity, exactly one silent refresh occurs. The header **never** says “AI connection check expired” or flashes “Checking AI…” during ordinary success; it remains “ChatGPT connected”. Advance beyond 60 seconds and verify a fresh `checked_at` and continued connection. Repeat across several cycles, verifying no increased request rate.
2. **Visibility:** Hidden tab makes no periodic provider requests. Returning to a visible tab after TTL causes one prompt coalesced refresh and recovers current state. Switching Home ↔ workspace doesn't multiply polling. Re-rendering the status control doesn't multiply timers.
3. **Failed checks:** Network failure, 5xx/timeout and provider `unavailable` produce neutral/warning status with Retry and no infinite green. Capped backoff is demonstrable and stops when hidden; eventual success restores green automatically without manual intervention.
4. **True account transitions:** Expired/revoked authorization, declined plan scope, plan usage limit, explicit API-key billing, account switch and Disconnect retain the exact A8.2 behavior. A stale response can never resurrect a disconnected or differently selected account.
5. **Sign-in interactions and toast:** No refresh poll interrupts OAuth or causes duplicate requests; test welcome toast displayed **once** and not again after multiple routine refreshes, switching pages, or reloading. No new OAuth popup or generation on refresh.
6. **Manual Retry and errors:** Retry can trigger a fresh verification without duplicate concurrency. Errors don't leave the control disabled or spinner stuck; focus/keyboard interaction remains correct.
7. Run `./sigma test`, frontend build/typecheck, existing provider/auth scenarios and real Chrome checks at MacBook and 390/320px widths. Tests use controlled fake OAuth/provider responses, **no live sign-in and no billable requests**. Preserve the documented A8.2 test boundaries.
8. Update `docs/STATUS.md` and any truly impacted user documentation with actual results and precise limits. Commit the implementation after verification.

## Acceptance criteria

Leave SIGMA open and in use for several minutes while signed in. **The small AI status control remains reliably “ChatGPT connected” as routine health checks refresh**, without manual Retry or a distracting expired-check label. Real authorization loss, usage limits or provider/network failure surface truthful actionable states. The toast remains a one-time pleasant confirmation. No incidental billing, new flags, sign-in prompts, browser navigation, project writes or UI redesign.
