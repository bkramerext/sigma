# A22 — Cloud deployment and organization-ready access

Status: Requirements specification. Do not begin A22 until the user explicitly starts it; the starting A-number may change as earlier work progresses.

## Objective

Deploy SIGMA for a polished, reliable external demonstration while preserving today's local-first workflow. Keep scope bounded. Resolve implementation choices independently; do not insert discretionary approval gates or expand scope. A time-boxed feasibility check for Cloudflare runtime compatibility is part of A22, not a separate project. Choose the smallest maintainable architecture that meets the requirements.

## Must-have requirements

### 1. Preserve local operation

- Preserve existing local startup, shutdown, tests, filesystem-backed projects/sessions, and agent behavior.
- Existing commands including ./sigma start, ./sigma test, and ./sigma shutdown must continue to work as before.
- No Cloudflare account, cloud credentials, cloud network access, or sign-in is required for local operation.
- Share core research logic across local/cloud modes as practical. Put cloud-specific identity, authorization, persistence, execution and deployment concerns behind explicit interfaces/adapters.
- Do not weaken local security or silently migrate/rewrite local user data.

### 2. Cloudflare hosting and operational cost controls

- Use Cloudflare as the preferred cloud platform. Conduct an early, time-boxed feasibility check of the existing Python backend/research engine, long-running agent work, and persistence. Cloudflare Workers are not a conventional persistent Python server; evaluate a Cloudflare-native option and a small hybrid option. Select and document the smallest reliable approach without an open-ended architecture investigation.
- Provide public HTTPS access and a configurable custom domain. A workers.dev address may be used during setup/testing. Do not buy a domain on the user's behalf or make a purchased domain a prerequisite for implementation/tests.
- Document required Cloudflare account registration, any required paid plan, billing setup, deployment secrets, DNS/domain configuration, expected recurring platform costs and likely variable costs. Separate platform charges from model-provider inference costs. Do not claim an exact total before validating current pricing/usage.
- Secure deployment credentials with least-privilege tokens/secrets. Support reproducible deployment and rollback. Provide basic health/error visibility.
- Enforce per-user session/call/time/token/cost limits and a global configurable inference-spend ceiling. Prevent concurrent or repeated requests from bypassing budgets. Fail safely if usage cannot be bounded; no surprise agent calls.
- No live or paid model calls in automated acceptance tests.

### 3. Authentication and authorization

- Public unauthenticated visitors can use the Demo (requirements below).
- Provide federated sign-in, initially with Google. Keep authorization logic independent of the identity provider so another provider can be added if the target organization's identity setup requires it. Do not assume a company email address necessarily has a Google-hosted mailbox.
- Put the sign-in experience on the Home page, above the project area. Guests can continue into the Demo without signing in.
- Support these authorization paths:
  1. Unauthenticated guest: read-only Demo only.
  2. Individually invited/authorized user: private workspace.
  3. User whose verified email domain matches an administrator-configured allowed domain: private workspace.
  4. Designated administrator: Access Management and deployment-level administrative capabilities.
- Domain-level invites must be configurable, not hardcoded. Support allowed email domains plus individually authorized email addresses, with clear precedence and revocation semantics.
- For initial testing, gmail.com may be configured temporarily as an allowed domain to test with the user's existing Google account. This is configuration, never a special-case code path. Document removal/replacement before a real external demonstration.
- Individual invitations are authorization entries only. “Invite” does not send email. No email-sending service or invitation-email workflow is required.
- No purchased domain, Google Workspace, or paid test identity is required for development or acceptance testing. Automated identity fixtures must cover matching domains, nonmatching domains, individual authorization, revocation, identity-provider claims and malformed/unverified identities. Real Google sign-in can be tested with the user's existing account via individual authorization or the temporary gmail.com rule.
- Do not hardcode a organization domain, user email, or administrator identity into application code. Bootstrap the first administrator via documented deployment configuration/secret, then let that administrator manage authorization in SIGMA.
- Cloudflare Access may be used if it materially simplifies deployment, but it is not a requirement. Do not force the entire public Demo behind an Access login. If using Access, ensure guest routes remain public and backend identity claims are verified. Direct OAuth is also acceptable. Choose one approach and implement it end-to-end.
- Enforce authentication, authorization, workspace ownership and administrator privileges server-side on every applicable operation. Hiding controls is not security. Verify identity through a trusted provider flow and use a stable identity key; do not trust browser-supplied identity/email headers.
- Revocation must prevent subsequent access, including API and session access. Preserve a revoked user's data by default; deletion is a separate explicit administrative action.
- Access Management is visible and usable only by administrators. Local mode retains the current single-user experience without login; local owner may use local administration without cloud identity.

### 4. Public read-only Demo

- Unauthenticated visitors land in or can enter a curated shared Demo project. Provide a clear sign-in option on Home.
- The Demo is shared and curated, not duplicated into every guest workspace. Guest users do not get a shared/global editable project list.
- Guests can inspect existing project details, strategies, sessions, outcomes and artifacts. They may create/download Project Audit exports and Research Reports using the combined A17.5 export dialog.
- Disable all mutations and agent actions for guests: New, Generate, Edit, Fork, Remove, drag/reorder, Start, Resume, Stop and any other project/session mutations. Settings may be opened and inspected but all fields and actions are disabled.
- Guest report generation operates only on saved Demo data, makes no model calls, and does not modify the Demo.
- Read-only enforcement must exist in backend authorization as well as the UI. Guest attempts to call mutation APIs directly must be denied. Protect against editing through guessed project/session IDs.
- Demo data must be seeded/managed reproducibly and must not contain secrets, credentials, private user data or misleading claims presented as verified results.

### 5. Private per-user workspaces and storage

- Every authenticated authorized non-guest user gets a private workspace, provisioned at first successful sign-in. Recents/projects show only that user's projects. No global/shared Recents list.
- Projects, strategies, sessions, artifacts, settings and exports are isolated by user/workspace. One user cannot read, modify, remove, export or infer another user's private data by manipulating IDs, APIs, URLs, or requests.
- An owner/admin workspace is private like any other; it is not mixed with user projects. Administrator privileges allow access management and operational controls, not silent browsing of private research contents unless a narrowly documented operational need requires it.
- Choose persistent cloud storage appropriate to the selected runtime. Evaluate D1 for relational/user/project/session metadata and R2 for larger artifacts/exports if Cloudflare-native; if hybrid, use durable database/filesystem storage appropriate to that host. Do not assume ephemeral Worker local filesystem is durable. Record schema, ownership model, migration and backup/restore procedures.
- Support durable session sequence numbering, session resume/recovery semantics, export/import considerations and safe concurrent writes. Use atomic transactions or equivalent where needed.
- Backups and recovery must be documented and exercised. Secrets never enter project data, exports, logs or reports.

### 6. Agent execution and session reliability

- Authenticated users can use SIGMA's real research workflow, subject to bounded limits. Agent runs must execute durably, with explicit states, progress, cancellation/stop/resume semantics and recovery after process/deployment restart.
- Do not rely on one long HTTP request or ephemeral process memory as the sole record of an agent run. Persist checkpoints, call attempts, outputs, budgets, and lifecycle transitions before reporting success.
- Stop/resume, idempotency and ambiguous provider completion must avoid unintentional duplicate calls/billing. A provider response that was never durably saved cannot be claimed as recovered.
- Preserve existing agent role separation, artifacts, outcomes, context reconstruction, provenance, limits and error feedback. Report failure clearly; do not leave the UI implying success after network/backend failure.
- Enforce concurrency limits and backpressure. Guest sessions cannot run agents. Handle provider secrets securely and never expose a server-held shared key to browsers.
- Provide a practical mechanism for the user to configure supported model access in cloud deployment without putting secrets in client code. Do not assume a ChatGPT subscription can be used as a hosted service credential unless technically supported and permitted; verify actual provider/transport requirements.

### 7. Administration and operations

- Provide a small administrator-only Access Management UI: list individually authorized email addresses and allowed domains; add/remove individual authorization; add/remove allowed domain; show basic account/access state; and identify the initial administrator/bootstrap procedure. No email sending.
- Domain changes and revocation take effect server-side promptly. Validate domain syntax and normalize case/whitespace; require verified identity email before applying domain authorization. Never use suffix matching that accepts lookalike domains (e.g. notexample.org matching example.org).
- Provide configurable global and per-user limits, basic health/error reporting, and enough audit events to investigate authorization changes, agent starts/stops and budget denials without logging secrets or full private artifacts.
- Secure configuration and secrets, use least privilege, protect against CSRF/session fixation/token theft, validate uploads/exports/inputs, apply security headers and rate limits, and keep dependencies updated.
- Apply the CSO threat model throughout implementation: public guest-to-private escalation, cross-workspace data access, unauthorized admin, spoofed identity claims, agent-budget abuse, secret leakage, untrusted model output injection, export path/injection vulnerabilities, and data loss/replay after interruption.
- Provide a concise incident/recovery playbook for revoking access, disabling agent execution, rotating credentials, restoring data and rolling back deployment.

### 8. Project export/report support

- Retain the A17.5 combined Project Audit / Research Report export experience in cloud mode. Audit format is JSON. Research Report supports Text, HTML and LaTeX; the format dropdown is disabled for Project Audit.
- Filename stem is editable. The extension is controlled by export type/format: always .json for Project Audit; .txt, .html, or .tex for reports. Changing type/format preserves the stem and changes only the extension.
- The “Open in browser tab” option is a checkbox. Create and Cancel use standard dialog styling.
- Reports and exports include only data the current user is authorized to access; guest reports only contain Demo data. HTML/LaTeX output must safely escape untrusted project/model content. Export operations must not invoke agents or bill inference.

## Nice-to-have — explicitly deferred, discuss only after A22 exits

These are not to be implemented in A22. At A22 exit, revisit this list with the user and decide what, if anything, belongs in a later increment.

- Multiple identity providers beyond initial Google integration, unless required to make the agreed organization access workflow actually work.
- Shared projects, collaboration, concurrent editing, project sharing/permissions and team workspaces.
- Advanced workspace administration.
- Public self-registration controls beyond specified domain/individual authorization paths.
- User-facing usage dashboards, invoices, subscription billing or monetization.
- Rich administrative analytics, organizational dashboards and elaborate audit UI.
- Sophisticated search across all users/projects, vector databases or semantic cross-workspace retrieval.
- Advanced enterprise integrations (SCIM, SSO policy administration, enterprise identity lifecycle) unless a required organization identity setup cannot otherwise authenticate.
- Multiple regions, high availability guarantees and large-scale autoscaling beyond what the initial demonstration needs.
- Email delivery for invitations or notifications.
- Custom branded marketing site or public directory of projects.
- A purchased custom domain is desired for presentation but must not block development or acceptance testing; use a configurable deployment URL until a domain is deliberately selected.

## Non-goals

- Replacing or discontinuing local SIGMA.
- Turning A22 into a general-purpose multi-tenant SaaS business.
- Public unrestricted access to agent execution.
- Guest project creation or a global project/Recents feed.
- Visitors mutating the canonical Demo project.
- Shared team projects/collaborative editing in this increment.
- User subscription plans, payments, metering invoices or commercial billing.
- Sending invitation emails or building email infrastructure.
- Purchasing a domain or any paid test identity/domain for development.
- A wholesale rewrite of the research engine merely to use one Cloudflare product. Select a hybrid deployment if it is clearly the smaller reliable solution.
- Implementing nice-to-haves before A22 exits.
- Treating green tests alone as proof of research quality or security; acceptance must include adversarial tenant-isolation and authorization tests.

## Acceptance criteria

### Product and access
- Guest can open SIGMA without signing in, inspect the seeded Demo and create/download all supported exports/reports; all mutations and agent starts are blocked in UI and backend.
- Sign-in appears above Projects on Home. Successful authorized login opens that user's private workspace. Sign-out returns to guest Demo.
- Individual authorization and configured domain authorization each grant access. An unapproved identity receives only guest Demo access. The temporary gmail.com rule is configuration-only and has a documented cleanup step before real external use.
- Access Management is administrator-only; bootstrap works on a fresh deployment. Add/revoke domain and email rules and prove the server immediately enforces changes. No email is sent.
- Two separate users cannot access each other's projects, sessions, artifacts, settings, or exports, even by direct API/ID manipulation. Recents are private.
- Owner/admin can configure resource ceilings; concurrent and repeated requests cannot exceed them. Guest actions cannot trigger inference.
- Local mode continues working without cloud identity/credentials and preserves current project/session data and existing CLI commands.

### Durability, security and quality
- Agent work survives supported process/restart/deployment events according to documented semantics; progress, budget, outputs and terminal states remain consistent. Ambiguous provider attempts cannot be replayed without explicit safe policy.
- Cloud persistence and backup/restore are tested. Cross-user export leakage, spoofed identity, domain lookalikes, unauthorized admin, guest mutation, HTML/LaTeX injection, CSRF/session attacks, and budget/concurrency bypass have regression coverage.
- Run existing tests and update/stabilize them, plus backend/API/security tests, local/cloud-mode tests, and real-browser desktop/mobile end-to-end checks using mock providers. No paid model calls in tests.
- Run the repository's complete standard verification (test suite, lint/format, static type checks, frontend typecheck/build, browser scenarios) and fix failures/flakiness. Record exact commands/results; never claim unrun checks passed.
- Provide a concise deployment/operations guide covering registration, billing, DNS/domain setup, secrets, deploy/rollback, authentication and domain authorization, model access, budgets, backups/restoration and incident response.
- Demonstrate a full happy path: guest Demo → Google sign-in → private workspace → run bounded research → inspect results → export → sign out → guest Demo; plus denied access and isolation paths.

## Definition of done

A22 exits only when acceptance criteria are verified, local operation is preserved, a working cloud deployment is available, costs/limits are configured and documented, and the deployment/operations guide is complete. Nice-to-haves must remain unimplemented and be reviewed for prioritization with the user at A22 exit. Record remaining risks and limitations explicitly. Do not create discretionary sub-projects or stop for intermediate approval; make defensible choices within this scope and raise only genuinely blocking user decisions.
