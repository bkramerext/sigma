# Blue inbound 4 — sponsor renewal UI is unavailable

**Batch:** 2026-10-29 21:19–21:32 PDT (2026-10-30 04:19–04:32 UTC), approximately 13 minutes.
This closes the bounded sponsor-connection/PDF batch requested by `out_message_4.md`.

## Result

- I closed the existing Chrome tab and reopened the authenticated SIGMA app. The project page loaded, but the user-visible sponsor renewal attempt continued to show: `HTTP 403 Forbidden: Use Admin Settings to renew the sponsor account.`
- The user opened **Administrator Settings** and supplied a screenshot. The visible panel has only **Access Management** and **Account usage** tabs. Access Management shows invitation/reload requests, authorized users, member roles, allowance values, and remove/reload controls. There is no sponsor-account renewal control or ChatGPT connection control on this page.
- Source inspection corroborates the UI mismatch: `/api/ai/auth/begin` returns the 403 instruction for a sponsor account ID, while a separate `/api/ai/sponsor-auth/begin` route exists. The message directs the operator to a screen that does not expose renewal. The normal `Connect to ChatGPT` action appears to invoke the personal-auth route; the sponsor-specific route is available only when the frontend recognizes `localSponsorNeedsReconnect` and the sponsored pill is activated. I did not change code or bypass the UI.
- The user says the message persists after reopening the page. No supported sponsor OAuth flow completed in this batch; no callback was initiated after Uvicorn access logging was disabled.

## PDFs and provider work

- Genuine PDFs generated: **0**. No saved project was sent to a provider, no research session was started, and no project was modified.
- Provider calls: **0**; additional spend: **$0**. The blocker is the unusable/misleading sponsor renewal path, not lack of human availability to select the designated account.
- PDF metadata, hashes, and model receipts: not applicable.
- No tests or CI were run. No implementation, research, or status changes were made.

## Dependency for next iteration

Please provide a supported operator path to renew the designated sponsor connection, or correct the UI/error guidance so an authenticated local administrator can reach `/api/ai/sponsor-auth/begin`. The visible Administrator Settings page has no such control. Keep callback URL access logging disabled for any subsequent OAuth attempt. After sponsor connection succeeds, resume real PDF generation from the already-openable Nonconsecutive v9 or Xenopus v9 as originally assigned.

This report contains no credential, callback URL, or token. No changes were made to the numbered outbound messages.
