# A14.2: Restore Markdown conversion on ChatGPT-plan transport

**Status:** Ready for Codex implementation. This is a focused regression investigation and repair, separate from A14 agentic strategy generation and A14.1 terminology migration. Use this repository assignment, not a GitHub issue.

## Reported failure

Converting research text to rendered Markdown no longer works. The UI shows a **Request Failed** toast with the following message (user screenshot, 2026-10-21):

> HTTP 400 Bad Request: ChatGPT rejected the request (HTTP 200, code: unspecified, shape: other-object). Account retained; no automatic billing fallback occurred.

The toast is **evidence that failure reporting is working**, not the underlying bug. The embedded provider HTTP 200 and outer HTTP 400 are distinct; diagnose why the ChatGPT-plan response is classified as `other-object`. Do not assume the response was a successful conversion or that the toast itself needs redesign.

## Scope and investigation

1. Reproduce using an existing **mathematical investigation** with plain research problem or strategy approach, connected through **ChatGPT-plan mode**. Click the Σ Markdown/render control when no current Markdown conversion exists. Record the actual local endpoint status, provider status/content type, sanitized response envelope shape, and UI state. Do not log raw source text, tokens, cookies, credentials, or private model reasoning.
2. Trace `frontend/src/main.tsx` `TextViews.convert` → `POST /api/projects/text/convert` in `src/sigma/api.py` → `src/sigma/text_conversion.py` → `src/sigma/plan_stream.py` and the current ChatGPT authentication/transport adapter. Inspect the actual contract for `/v1/responses`, including streaming SSE, completed JSON, and error envelopes returned with HTTP 200. Determine whether the request payload is rejected, the response parser rejects a valid shape, or the provider/account genuinely rejects the operation. State the evidence before selecting a fix.
3. Repair the **underlying conversion path**, including request/response contract or shared adapter only where justified. Preserve the selected investigation model, thinking level, authenticated identity, ChatGPT-plan billing mode, and bounded response/cancellation behavior. Do not silently switch to an API key, charge a different account, downgrade models, or automatically retry a rejected request. If the provider genuinely disallows this request, surface an accurate actionable error rather than fabricating a successful conversion.
4. Keep plain source text authoritative and unchanged on any failure. Only persist a derived Markdown representation after a fully validated successful response, matching source digest and account/model binding. Retain provenance, warnings, format validation, and safe Markdown rendering. The Σ control must switch to rendered Markdown **only after success**; on failure remain in the appropriate plain/source view with retry possible. Do not display an empty Markdown panel or treat a failed conversion as saved.
5. Preserve the existing request-failure toast and its Dismiss action. Show **one** meaningful error for one failed conversion, not duplicated notifications. Avoid exposing raw provider objects, sensitive data, or confusing nested status messages when a clearer diagnosis is available. The UI should recover correctly from cancellation, timeout, authentication change, malformed responses, and network errors.
6. Keep this repair independent of A14 agentic generation and A14.1's broad rename. If Codex is concurrently changing related files, coordinate on current `main` and avoid reverting those changes.

## Regression coverage

- Add deterministic, **no-paid-API-call** tests with mocked HTTP transport for ChatGPT-plan successful SSE completion and any legitimately supported completed-JSON form; provider rejection with HTTP 200 `other-object` envelope; ordinary non-200 rejection; malformed/partial SSE; missing `output_text`; invalid structured conversion; timeout; cancellation; and account/model binding changes.
- Include a regression fixture reflecting the **shape** of the reported HTTP 200 `other-object` response, redacted of all sensitive payloads. Verify that a true provider rejection is distinguished from a parse error, and a valid completion is not incorrectly rejected.
- Test API endpoint behavior and frontend Σ toggle/error recovery: source remains intact, no conversion artifact on failure, no mode switch into missing Markdown, one dismissible toast, and a successful subsequent explicit retry.
- Verify both research-problem and strategy-approach conversion, and plain ↔ Markdown where supported. Run focused backend tests, `./sigma test`, frontend build/typecheck, and available browser tests. Record **actual** results and any untested live-provider behavior; do not claim a live success from mocks.

## Acceptance criteria

1. With a supported ChatGPT-plan connection, a real successful conversion produces current, rendered Markdown, with source text preserved.
2. The reported failure is explained with a reproducible root cause and a targeted fix, or clearly documented as a genuine upstream rejection with appropriate handling; no speculative success claim.
3. On any failure, the user stays in a usable plain-text view, can retry explicitly, sees one accurate dismissible error, and no conversion is stored.
4. No unapproved billing fallback, credential leakage, implicit model change, or regression to agentic strategy generation.
5. Tests and build results are documented. **Commit and push directly to `main`**, no pull request. Report commit SHA and remaining limitations.

## Out of scope

Changing the approved SIGMA artwork or Home layout; broad redesign of text editing; replacing the AI conversion feature with a local Markdown heuristic; changing the multi-agent Generate Strategy workflow; a wholesale rewrite of authentication or billing infrastructure without evidence it is necessary.
