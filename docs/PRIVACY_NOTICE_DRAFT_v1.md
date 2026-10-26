# SIGMA Privacy Notice — proposed version 1.0

**Status:** Draft for Brian's approval. Do not treat or publish this text as
approved policy until the owner resolves the questions at the end.

**Prepared:** 2026-10-26  
**Proposed version:** 1.0  
**Proposed public route:** `/privacy`

The unauthenticated `/privacy` page uses the following proposed wording and is
marked as a draft. It is linked from feedback collection, invitation requests,
and About. No production deployment was performed.

## Proposed notice wording

### Information SIGMA handles

If you sign in, SIGMA receives your Google account identifier and verified
email from Google and stores account, access, and session records. SIGMA uses
browser cookies for Google sign-in and your SIGMA session. A denied sign-in can
also create a short-lived record used to support an invitation request.

If you send product feedback, SIGMA stores the feedback text, submission time,
status, and any optional contact email. If you are signed in, it also associates
the verified account identifier and email. Feedback rate limits use the signed-in Google subject or a random signed-out
browser token; the database stores a hash of that key and a request counter,
not the anonymous token itself. Feedback is not sent to AI or email providers by
this workflow.

If you request an invitation, SIGMA stores the verified Google account
identifier, verified email, request time, and review/notification status. The
notification email containing the verified account email and request time is
sent to `zetacontinuation@gmail.com` through authenticated SMTP.

For an authorized account, SIGMA stores project names and research questions,
settings, strategies, session prompts and results, evidence, code and execution
outputs, reports, and generated paper files. SIGMA also records account-level
research usage and spending estimates for the sponsored service.

### How information is used and shared

SIGMA uses account information to authenticate users, control access, isolate
private workspaces, and administer invitations. Administrators can review
invitation requests and feedback. Optional feedback contact details are shown
to those administrators so they can follow up; SIGMA does not require an email
address to submit feedback.

When a user chooses an AI research feature, SIGMA sends the request and
relevant project context to OpenAI using either the selected ChatGPT account
authorization or an explicitly selected API-key billing path. These are
separate paths; SIGMA does not silently switch between them. OpenAI handles
data under the terms and settings of the selected account. SIGMA cannot promise
OpenAI retention, training, or other data-use practices in this notice.

Google processes sign-in requests. Invitation notifications contain the
verified account email and request time and are sent through the configured
authenticated SMTP account to zetacontinuation@gmail.com. Feedback content is
not included in those emails.

### Storage, access, and retention

In the hosted configuration, authentication and administrative records use a
SQLite database, and authenticated users' projects and research records use
owner-specific workspace storage. The repository's Compose configuration places
persistent state on the SIGMA state volume and applies rotating local container
logs. The code does not establish a fixed retention period for feedback,
invitation records, account records, research content, or usage records, and it
does not provide a complete account-and-data deletion workflow.

The repository includes optional state-disk snapshot tooling, but this notice
cannot confirm whether snapshots are enabled for a particular deployment, the
configured snapshot count, or how deletion applies to snapshots. SIGMA does
not claim encryption at rest. The deployed host, region, infrastructure
logging, and any additional operator retention settings require confirmation.

### Cookies and service logs

Hosted Google sign-in uses short-lived flow and denied-access cookies and an
eight-hour session cookie. The feedback form may set a random, HTTP-only
browser cookie for rate limiting. The application also writes service logs;
the exact data visible in infrastructure and provider logs and their retention
depends on deployment and operator configuration and has not been fully
established.

### Questions and requests

A privacy contact and process for access, correction, or deletion requests
have not yet been approved. No response time or deletion guarantee is
established here. Please do not treat the invitation email address as a
confirmed privacy-request contact until the owner approves it.

## Questions requiring owner resolution before publication

1. What legal entity/operator name and privacy contact should the notice name?
   Who handles access, correction, and deletion requests, and what process and
   response expectations should be stated?
2. Which jurisdictions and audience should the notice cover?
3. What is the actual hosted location/region and what application, host, edge,
   and provider logs are enabled, which fields can they contain, and how long
   are they retained?
4. Are disk snapshots active for this deployment? What is the configured
   snapshot count, and how are deleted records reflected in snapshots?
5. What retention and deletion process should apply to feedback, invitations,
   auth/audit records, usage ledgers, workspaces, generated artifacts, and
   backups? Current code has no complete user-facing deletion workflow.
6. Which current Google, OpenAI ChatGPT-plan/API, SMTP, and hosting terms apply
   to the actual deployment? Confirm and link the relevant terms without making
   unsupported training, retention, or encryption promises.
7. Does the owner approve storing optional contact email alongside feedback,
   visible to SIGMA administrators, and the 5-per-24-hour feedback limit?

## Implementation audit basis

- `src/sigma/cloud_auth.py`: Google subject/email sessions, denied-access and
  invitation records, invitation SMTP payload, SQLite auth data, administrator
  access, and the new feedback records/rate-limit table.
- `src/sigma/cloud_workspaces.py`, `src/sigma/storage.py`, and
  `src/sigma/projects.py`: owner-specific project storage and local/persistent
  storage roots.
- `src/sigma/proposals.py`, `src/sigma/openai_connection.py`, and
  `src/sigma/chatgpt_auth.py`: explicit OpenAI API-key and ChatGPT account
  authorization request paths.
- `deploy/compose.yaml`, `deploy/Caddyfile`, and `deploy/nginx.conf`: hosted
  state mount, service logging rotation, HTTPS reverse proxy, and SPA route
  fallback. Caddy access logging is not configured in the checked-in site
  file; external edge/host logging was not independently audited.
- `deploy/backup-state.sh` and `deploy/backup-retention.py`: optional snapshot
  workflow supports a configured minimum of 14 recovery points, but repository
  code does not prove it is installed or active on a particular host.

This draft reflects repository behavior, not a legal review or a claim about
provider/host policies. Re-audit and version the notice when deployment,
provider, data, or retention behavior changes.
