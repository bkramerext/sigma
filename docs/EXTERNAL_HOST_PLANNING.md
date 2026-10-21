# External hosting planning

**Status:** Planning only. Not an implementation assignment or an authorization to change SIGMA's architecture.  
**Date:** October 21, 2026

## Purpose and guiding constraint

Make SIGMA accessible to a small number of outside users as a **genuine, interactive, polished research showcase**, while retaining a useful locally running application. The intended audience includes people evaluating the product and engineering approach, particularly Onebrief. This is not a plan to launch a production SaaS business.

**Design test:** Does a decision make the demonstration more compelling, trustworthy during ordinary use, or simpler to deliver? If not, defer it. Showcase quality is not the same as production infrastructure complexity. We should spend effort on a pleasing experience and avoid preventable loss of users' specifications, strategies, or results.

Do not begin implementation until this plan is revisited and a specific assignment is approved. Reinspect the then-current repository; the notes below describe the October 21 baseline.

## Scope and priorities

| Concern | Position |
| --- | --- |
| Working hosted application | **Required.** Read-only demos are explicitly out of scope. |
| Local SIGMA | **Required.** Continue to run locally with local persistent storage; filesystem or SQLite is acceptable. |
| A few concurrent visitors | **Required.** Good interactions, independent workspaces, no lost edits. |
| User identification and private investigations | **Required for hosted use.** Minimal sign-in, ownership and server-side authorization. |
| AI proposals | **Required.** Prefer visitors' own ChatGPT accounts if supported and eligible, without charging the SIGMA owner unexpectedly. |
| Clear privacy policy | **Required.** Persistent, unobtrusive lower-right Home link; publicly readable page. |
| Data portability / export-import | **Non-goal.** Do not build it merely to satisfy conventional SaaS expectations. |
| Production-grade operations / availability | **Non-goal.** No elaborate disaster recovery, observability stack, or multi-region design. |
| Long-running autonomous investigations | **Undecided.** Don't build a durable agent orchestration system until the demonstration requires it. |
| Large-scale multi-tenancy, collaboration, public editing | **Non-goals for first hosted release.** |
| Preservation of approved UI artwork | **Required.** No unrequested Home redesign. |

Reliability is a non-goal in the *operational platform* sense, not permission to lose user work. Persistence, transactional integrity, understandable error states, and safe retry behavior remain requirements.

## Two operating modes

### Local mode

`./sigma ui` should remain a first-class experience. Investigations, strategies, and history live on the user's machine. The current implementation uses per-project JSON files and filesystem locking. A future switch to local SQLite is an **option**, not a prerequisite; it is attractive only if it materially reduces divergence between local and hosted code. Do not force a cloud account for local manual research.

### Hosted mode

A visitor reaches SIGMA through a normal HTTPS URL. They can browse included public examples, sign in, create an investigation, edit strategies, use AI where authorized, and return to their own work later. Persistent research data is stored in the cloud, not on the developer's Mac. Cloudflare is the preferred infrastructure to evaluate, not a commitment to a particular database or execution runtime.

**Cloudflare Tunnel** is an expedient way to expose the locally running *full* application for a controlled demonstration. It is not the same as an independently hosted application: the Mac must remain online, and multi-user data separation and public authentication would still need attention. A static read-only frontend is not an acceptable substitute.

## Hosted user experience

### Home

Preserve SIGMA's existing approved Home artwork and visual identity. Retain the existing prominent New/Open affordances; do not clutter the entrance with account and infrastructure controls.

- **New Investigation** (currently called **New Project**) creates an investigation owned by the signed-in user, private by default. If a visitor is not signed in, request sign-in at the point of action and resume the intended action without discarding entered information.
- **Open Investigation** lists the user's own investigations, any explicitly shared ones if that feature later exists, and public examples. It does not ask hosted users to type a local filesystem path.
- **Recent Investigations** shows the user's own recent activity, subject to the existing compact Home layout; another visitor's private work never appears.
- **Explore examples** allows visitors to inspect included sample investigations. A future **Fork** action could make an editable private copy, but public browsing/forking must not silently mutate a shared canonical sample.
- **Account identity** should be discreet. A sign-out option and clear current-account indication are sufficient initially.
- **Privacy Policy** is a persistent small link at the **lower-right corner of Home**, visible before sign-in, opening a dedicated readable page.

The potential rename from **Project** to **Investigation** is a separate product decision; use existing UI vocabulary until explicitly approved. Avoid redesigning the UI as part of a hosting assignment.

### Ownership and sharing

Do **not** put everyone in a single shared editable project collection. The initial hosted model is individual private investigations plus a small curated public example library. Public examples should be protected against visitor edits. Publishing, invitations, collaborative editing, moderation, and community contribution workflows are later possibilities, not current scope.

One shared database for multiple users is fine. Isolation is logical and enforced by the backend, not by separate databases or hidden frontend controls. Every read and mutation must resolve the authenticated principal and check ownership/visibility. A project UUID is not authorization.

## Identity and AI access: separate responsibilities

**SIGMA identity** answers who owns the investigation. **AI authorization** answers whose allowance or bill pays for an inference. They must not be conflated.

Prefer a minimal social sign-in rather than building passwords. Google or GitHub identity are practical fallback options; using ChatGPT sign-in as the single identity would be even more frictionless **only if the supported hosted OAuth program permits it and yields a stable, verified identity suitable for SIGMA accounts**. This is unresolved and must be verified before choosing the login design.

The existing Sign in with ChatGPT flow was implemented for an open-source **locally hosted** application, with loopback authorization and local credential storage. Do not assume its client registration, redirect behavior, terms, token-sharing permissions, or model allowances transfer unchanged to a publicly hosted site. Specifically verify:

1. Whether public hosted SIGMA is eligible for a supported Sign in with ChatGPT integration and what registration, redirect URI, client type, and security requirements apply.
2. Whether ChatGPT **Free** accounts can authorize this use, which models/features they can use, and how rate/credit exhaustion is surfaced. No claim of guaranteed free inference without verification.
3. Whether the identity scopes and verified subject can be used for SIGMA user accounts, or whether a separate Google/GitHub sign-in is necessary.
4. Whether the resulting tokens are tied to the individual signed-in visitor and can be safely stored/used server-side in a hosted multi-user environment.
5. What the user sees on disconnect, expired credentials, unsupported accounts, exhausted limits, and temporary network failures.

Retain explicit API-key billing as an optional separate mode if appropriate. **Never silently fall back to a key paid for by the application owner.** Do not expose provider tokens to other users or to browser JavaScript. Protect any server-stored tokens and OAuth session state, and ensure account switching cannot attach a response to the wrong user's investigation.

**Go/no-go dependency:** Public-hosted ChatGPT authorization is the biggest unresolved product assumption. Test it with an actual Free account before promising visitors that experience. If unavailable, decide explicitly whether separately billed API access or a limited demonstration is acceptable; do not quietly change the economics.

## Persistence and Python domain model

The existing research concepts—investigations, strategies, ordered active strategies, immutable-ish history/events, model settings and proposal review—should remain Python domain objects independent of storage. Prefer a small, explicit persistence boundary so local and hosted execution share business rules.

Conceptual operations (illustrative, not a prescribed class API):

```python
create_investigation(owner_id, draft)
get_investigation(principal, investigation_id)
list_investigations(principal)
save_investigation(principal, investigation_id, expected_revision, changes)
record_event(principal, investigation_id, event)
```

**Cloud storage candidate:** One Cloudflare **D1** database for users, investigations, strategies and event history; **R2** only if artifacts grow beyond ordinary structured data. D1 is SQLite-compatible at the SQL level but is not a local `sqlite3` file accessible to an arbitrary FastAPI process. Its binding/HTTP interfaces, transaction limitations, deployment model and concurrency semantics must be assessed before settling on it.

**ORM choice depends on runtime:**

- If Python/FastAPI runs on a conventional server or container with PostgreSQL, SQLAlchemy 2.x is a reasonable mature ORM.
- If we choose Cloudflare D1, a focused SQL repository using its supported access mechanism may be simpler than forcing SQLAlchemy's ordinary SQLite dialect over an incompatible connection.
- If local SQLite simplifies the codebase, use it deliberately, but do not mistake SQL compatibility for interchangeable D1 and local connection/transaction APIs.

Do not prematurely rewrite the current JSON persistence merely to align with an undecided cloud platform. Compare a minimal D1 adapter with a conventional hosted Python + relational database solution based on implementation effort and demonstration experience.

A provisional hosted schema might contain `users`, `investigations` (owner, visibility, revision), `strategies`, and `events`; actual normalization and migrations should follow the current domain invariants. Public sample investigations should be seeded idempotently and never overwrite visitor edits or personal copies.

## Concurrency and protecting research work

This is a **must-have**, even for a handful of users. A pleasing demo cannot silently discard a visitor's specification, strategy, or AI output.

- Give each investigation a monotonically increasing **revision** or equivalent optimistic-concurrency token. Mutations include the version the editor read. Reject a stale write with a clear conflict response rather than overwriting newer work.
- Commit each logical mutation and its associated history/event **atomically**. A partial strategy save with missing history, or vice versa, is not acceptable.
- Enforce identity/ownership on the server for reads, updates, deletes, history and AI-related persistence. Test direct API access across two accounts.
- Protect against two tabs editing the same investigation, simultaneous AI proposal completion, repeated submissions, and browser/network retries. Where operations can be repeated, use idempotency or a well-defined duplicate policy.
- Keep **draft generation separate from explicit save**, as SIGMA does today. An AI response must not silently replace user-authored work. Preserve an unsaved draft across authentication interruptions where feasible.
- Surface conflicts with a clear recovery path that preserves the user's pending text. Avoid making visitors understand database revisions or manually reconcile JSON.
- A failed network request must not claim a save succeeded; conversely, an acknowledged successful save must survive reload and reopening.

For D1 specifically, verify that the chosen mutation pattern can enforce the revision check and required atomic writes under its actual transaction model. Do not rely on read-then-write without a concurrency guarantee.

## Hosting architecture candidates

**Candidate A: Cloudflare-hosted frontend + suitable Python backend + database.** Minimal change to Python business logic, but involves operating a small Python server/container and connecting to storage. Could be simplest engineering route even if the infrastructure bill is somewhat higher.

**Candidate B: Cloudflare frontend + Workers-based API + D1.** Consolidates infrastructure but may require substantial changes to FastAPI/Python runtime assumptions, file APIs, locking, local loopback OAuth, and background execution. Do not estimate this as a mere deployment configuration change.

**Candidate C: Cloudflare Tunnel to local full-stack SIGMA.** Fastest controlled hands-on access; no independent cloud persistence. Useful for an early demonstration, but not equivalent to hosted multi-user SIGMA.

The Vite development proxy currently targets localhost, and `./sigma ui` manages local processes. Hosted mode needs production static asset serving, HTTPS routing, allowed origins, safe cookie/session behavior, and server-side API configuration. The local launcher should not be broken in the process.

**Selection criterion:** lowest implementation complexity that provides authentic interactive use, correct ownership, safe writes and good AI access for a few visitors. No requirement to use Cloudflare for every component.

## Privacy policy and data handling

Place the unobtrusive **Privacy Policy** link at Home's lower-right, without changing approved artwork. The policy should state what the actual deployed system does, not promise unimplemented protections.

Cover, in ordinary language:

- What account identity information is retained and why.
- What investigation data is stored: problem statements, strategies, edits, events/history, model preferences, AI-generated proposals **when saved**, and any future artifacts.
- Which data is transmitted to OpenAI during an AI request, and how OpenAI's handling differs from SIGMA's own storage.
- Whether authorization tokens are stored, their purpose, and how disconnection works.
- Private-by-default ownership and the exact behavior of public examples or any later sharing.
- How long data is kept and what deletion does **as implemented**; don't promise export, guaranteed erasure windows, or backup deletion procedures that do not exist.
- Basic access/security measures and a real operator contact route when one is available.

Do not claim zero retention, encryption at rest, regulatory compliance, or AI-provider training exclusions without validating the actual configuration and policies. The privacy page must be readable without logging in. An appropriate review of the final public policy is advisable before opening the site to others.

## Long-running investigations: decision deferred

Today's AI interaction is human-guided strategy generation with explicit review/save. That is enough for the first hosted demo unless the product narrative changes. Long-running, multi-agent research may eventually require queued execution, durable checkpoints, budgets, cancellation, isolation and progress reporting. Do **not** implement that system now or impose its abstractions on simple proposal generation.

Avoid painting ourselves into an obvious corner: keep research state and AI invocation reasonably separate, and avoid assuming an HTTP request can run forever. Beyond that, wait for a concrete demonstration use case.

## Costs and effort: preliminary only

Cloudflare's entry-level Workers/D1/R2 pricing may make a light-traffic deployment inexpensive, but **the cheapest Cloudflare bill is not necessarily the cheapest engineering architecture**. A conventional Python backend may add server cost and save implementation time. Domain, authentication provider, database operations and storage can add charges; AI inference is a separate and potentially dominant cost. Recheck current pricing and free-tier allowances when implementation is scheduled.

Working estimates, highly dependent on the chosen architecture and auth feasibility:

| Deliverable | Rough engineering effort |
| --- | --- |
| Controlled, authenticated full-app Tunnel demonstration | ~1–2 days, after checking existing local-app security assumptions |
| Small hosted single-owner interactive deployment | ~3–6 days if existing Python backend can largely be retained |
| Hosted few-user experience with identity, ownership, safe concurrent writes, privacy page and tested AI connection | ~2–4 weeks, potentially more if public ChatGPT sign-in is unavailable or runtime migration is substantial |

These are planning ranges, not commitments. They do not include building autonomous agents or production SaaS operations. Avoid presenting a precise monthly total until the backend/runtime and inference model are chosen.

## Risks and concrete discriminating tests

1. **Hosted ChatGPT authorization:** Run a minimal, documented hosted OAuth proof of concept, including a Free account, account switching, expiry, and exhausted allowance. Failure may change the demo's economics or login UX.
2. **D1 transaction semantics:** Implement a tiny two-writer revision-checked update with event insertion; verify exactly one competing write succeeds and the loser retains its draft.
3. **Python runtime fit:** Prove the selected hosting option supports the current backend's required dependencies, response streaming, OAuth callbacks, and reasonable request lifetimes without a major rewrite.
4. **Multi-user isolation:** Two test accounts create investigations; verify no cross-account list, read, edit, or AI-result association is possible, including direct API calls.
5. **Experience test:** Real browser checks for New/Open/Recents, login interruption and resume, AI proposal/review/save, refresh/reopen, two-tab conflicts, and small-screen layout. Verify original Home artwork remains unchanged.
6. **Local regression:** `./sigma setup`, `./sigma test`, `./sigma ui`, and existing local projects must continue to work. Cloud hosting cannot become a prerequisite for local manual research.

## Decisions intentionally left open

- Is the first outside demo a controlled Tunnel, or a genuinely independent cloud deployment?
- Is SIGMA identity provided by ChatGPT, Google/GitHub, or a small combination?
- Can Free ChatGPT accounts use a supported hosted authorization flow for SIGMA?
- Does the Python backend stay on a conventional server, or is a Workers-compatible API worth the migration?
- Is a shared local/cloud SQL domain persistence layer simpler than preserving local JSON plus a cloud adapter?
- Do we need Fork for the first demo, or only a safe way to start from curated examples?
- Is there a concrete long-running investigation experience worth demonstrating?
- When, if ever, should UI terminology change from Project to Investigation?

**Do not turn open questions into hidden assumptions or implementation gates.** Return to them when a specific external-hosting assignment is commissioned.

## Suggested implementation sequence when resumed

1. Verify hosted ChatGPT authorization and Free-account behavior; make an explicit decision on identity and billing.
2. Select the smallest viable backend/database arrangement using a thin concurrency/transaction proof of concept.
3. Implement per-user authentication/ownership and safe, revision-checked persistence without disturbing local SIGMA.
4. Adapt hosted New/Open/Recents and public sample behavior; preserve the existing visual design.
5. Add the truthful public Privacy Policy page and lower-right Home link.
6. Run a small, real-browser, two-account end-to-end demo with concurrent edits and actual AI use.
7. Stop when the showcase is convincing. Do not add portability, production operations or autonomous orchestration by inertia.

The central requirement is simple: **a handful of visitors should be able to use SIGMA as a real research tool, enjoy the experience, and trust that their work won't disappear.**
