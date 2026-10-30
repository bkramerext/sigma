# Blue inbound 3 — connection and latest-project readiness

**Batch:** 2026-10-29 21:09–21:19 PDT (2026-10-30 04:09–04:19 UTC), about 10 minutes.
No paper was generated; this report closes the bounded connection check requested in `out_message_3.md`.

## Connection and durability

- The standard SIGMA Google sign-in route was opened. The user selected an account, the callback returned to SIGMA, and authenticated app routes loaded. I did not read or independently verify the account identity from browser storage.
- The separate SIGMA ChatGPT sponsor flow did **not** start. The token-free `sponsor-diagnostics.log` contains no sponsor OAuth start event. The authenticated page still requires a click on its `Connect to ChatGPT` / `Sponsored ChatGPT` pill to initiate that supported flow. I cannot invoke it from the shell without the browser's authenticated session, and did not inspect or extract browser cookies.
- The earlier connection snapshot was `api_key`; I did not use that route. ChatGPT inference calls: **0**; additional spend: **$0**.
- SIGMA's normal sponsor auth store defaults to the private durable `~/.config/sigma` directory. Its normal ChatGPT auth service stores and refreshes the connection; no token should be manually copied or saved. No auth-home override was set for the running SIGMA app.
- Local Google login sessions have an 8-hour TTL in this checkout. A run longer than that may require Google sign-in again; overnight continuity beyond that window is not established.

Operational note: after the Google callback, the default local Uvicorn access log emitted the callback URL including a short-lived authorization-code query parameter to terminal output. I did not copy or save its value, and it is not in the repository or this message. Suppress or redact that access-log field before another OAuth callback; I did not initiate a second OAuth attempt.

## Latest saved project versions

The latest saved versions found across accessible local project stores are below. Project records have no owner field, so I make no claim that these are owned by the sponsor. I did not copy or modify any project. The read-only `inspect_project` call used implementation checkout HEAD `ec06223e86f2ebac3116024e22b1afc1be2e6d1d`.

| Topic | Latest saved project | Scope | Read-only open with current checkout |
|---|---|---|---|
| Maximum Regions | “Maximum Regions Formed by Lines: Working #15”, ID `3bceaf43-e6c2-4e83-b4d3-817583723d25`, `sigma_blue/projects/maximum-regions-by-lines-19.sigma` | schema 7; 4 saved sessions; configured `gpt-6.1-sol` / high | **Failed**: `Project change text must be canonical` |
| Nonconsecutive Subset Sums | “Nonconsecutive Subset Sums Modulo 3 v9”, ID `57d67c57-15dc-433d-828a-7953f7986ff8`, `sigma_gray/projects/nonconsecutive-subset-sums-9.sigma` | schema 8; 7 saved sessions; configured `gpt-6.1-sol` / high | **Opened read-only** |
| Xenopus Tadpoles | “Why Do Xenopus Tadpoles Temporarily Lose Tail Regeneration? v9”, ID `01de54c9-9593-413a-9577-1a952d28da70`, `sigma_green/projects/xenopus-tail-regeneration-5.sigma` | schema 9; 7 saved sessions; configured `gpt-6.1-sol` / high | **Opened read-only** |
| Operation Narrow Passage | “Operation Narrow Passage v5”, ID `d2049039-ae76-4523-8583-e44c270d24b0`, `sigma_green/projects/operation-narrow-passage-3.sigma` | schema 10; 4 saved sessions; configured `gpt-6.1-sol` / high | **Failed**: current code accepts project schemas 1–9 only |

No SIGMA export snapshot hashes were captured. The prior Tadpoles v1 workspace copy has zero sessions; v9 is the latest saved-session candidate found. The local app remains on its pre-existing profile and server configuration.

## PDF disposition

- Real end-to-end PDFs: **none**; no generation path was entered.
- PDF paths, SHA-256, sizes, page counts, model/effort receipts, generation elapsed time, and reference-paper comparisons: **not applicable**.
- Maximum Regions and ONP cannot currently be opened by the running implementation; Nonconsecutive v9 and Xenopus v9 opened without writes. This is source inspection only, not paper generation.
- Research sessions, evidence, and strategies changed: **none**. No tests, code edits, deployments, or project writes occurred in this batch. The previously uncommitted #336 edits remain untouched in `/tmp/sigma-336`.

## Acceptance disposition and next dependency

- Latest four project versions identified: **MET**.
- Read-only project access: **PARTIAL** (2 opened, 2 rejected by the current parser).
- Designated ChatGPT sponsor connection: **UNMET** (the authenticated-page pill still needs one normal click and account approval).
- Actual PDF generation and content comparison: **UNMET / UNVERIFIED**.
- Credential handling: **UNMET as an operational safeguard** because local Uvicorn printed a short-lived OAuth callback code once; it was not retained or transmitted, but callback logging should be redacted before another OAuth flow.

Before another paper batch, establish the supported ChatGPT connection through SIGMA's authenticated UI, keep the same private auth store, redact callback codes from local access logs, and have an implementation that can open the latest Maximum Regions and ONP schemas. No credentials or project contents are requested in this handoff.
