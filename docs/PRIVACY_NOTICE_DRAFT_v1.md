# SIGMA Privacy Notice — proposed version 1.0

**Status:** Candidate wording for owner review.

**Prepared:** 2026-10-26
**Proposed version:** 1.0
**Public route:** `/privacy`

The public page and this document should remain aligned. This wording describes
known SIGMA application behavior; deployment-specific physical location and
backup settings are configured by the operator.

## Proposed notice wording

### Information SIGMA stores

When you sign in with Google, SIGMA receives your stable Google account
identifier and verified email address. SIGMA stores them with your access role,
whether access is active, assigned workspace, sponsored eligibility, selected
model-access mode, and connection status. The hosted sign-in session is
represented by a browser cookie and a hashed session token in SIGMA's
authentication database. Sessions last up to eight hours. Sign-in flow data
expires after five minutes; a temporary denied-sign-in record expires after ten
minutes.

If you request an invitation, SIGMA stores your Google account identifier,
verified email, request time, and request/notification/review status. SIGMA
sends your verified email and request time through its configured mail service
to the SIGMA invitation administrator. If you send product feedback, SIGMA
stores your message, submission time, status, and any optional contact email.
When signed in, the feedback record is associated with your account identifier
and email. Feedback is reviewed in SIGMA's administrator interface; it is not
sent to an AI or mail provider. Feedback submissions are limited to five per
24 hours per signed-in account or signed-out browser.

Your account workspace can contain project titles and questions, project
settings, strategies, research prompts and results, evidence, uploaded or
imported project files, code and execution output, analyses, reports, and
generated papers. SIGMA also stores research-session identifiers and
sponsored-service accounting records, including reserved and estimated usage,
call status, and token counts when the provider returns them. Usage estimates
are used to enforce SIGMA spending limits and may differ from a provider's
final bill.

### How SIGMA uses and shares information

SIGMA uses your Google account information to sign you in, apply access rules,
and keep your projects in your account workspace. SIGMA administrators can
review invitation requests and product feedback, including any optional
contact email.

When you run an AI research feature, SIGMA sends the prompt and the project
context required or selected for that action to the configured AI provider.
In hosted sponsored mode, requests are sent to OpenAI using SIGMA's server-side
service credential. The provider returns a response to SIGMA, and research
results are saved in the project. Do not include information in a research
request that you do not want sent to the selected provider.

For an invitation request, SIGMA's configured mail service receives the
verified email and request time so it can notify the invitation administrator.
Product feedback is not included in invitation email. SIGMA does not send
feedback messages to AI providers.

### Where information is stored and how long it remains

In hosted SIGMA, authentication, access, invitation, and feedback records are
kept in server-side SQLite databases. Each signed-in account has a separate
server-side workspace for its projects and research files. Sponsored usage
records are kept in a server-side accounting ledger. The service stores these
in its configured persistent storage; the exact physical hosting location and
backup schedule are set by the operator.

SIGMA has no general time-based deletion schedule for account, invitation,
feedback, research, or sponsored-usage records. Signing out ends your browser
session but does not erase these records. Project controls can remove project
data where available, but the hosted service does not currently offer a control
that deletes all information associated with an account. If the operator makes
backups, copies may remain according to the operator's backup schedule.

### Cookies and account controls

Hosted sign-in uses Secure, HttpOnly, SameSite=Lax cookies for the sign-in flow
and session. The session cookie expires after eight hours; the short-lived
sign-in and denied-access cookies expire after five and ten minutes
respectively. The feedback form uses a random, HttpOnly cookie to apply its
five-per-day limit to signed-out browsers. Signing out removes the active
session; it does not delete saved projects or records described above. For a
request about your account data, contact the SIGMA administrator who invited
you.

## Implementation basis

- `src/sigma/cloud_auth.py`: account identity/access state, sessions, denied
  sign-ins, invitation requests, feedback content, and administrator review.
- `src/sigma/cloud_workspaces.py`: server-generated per-account workspace
  mapping and workspace directory access boundaries.
- `src/sigma/cloud_research.py`: research jobs and sponsored call reservations,
  usage estimates, statuses, and available token counts.
- `src/sigma/openai_connection.py` and `src/sigma/cloud_research.py`: selected
  provider request path and hosted sponsored inference.
- `deploy/compose.yaml` and `deploy/compose.gce.yaml`: hosted persistence and
  service configuration. Physical hosting location and backup schedule are
  operator settings, not application constants.

Review this version when storage, providers, request contents, or deployment
retention settings change. Version remains 1.0.
