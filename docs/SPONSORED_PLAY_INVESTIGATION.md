# Sponsored Play investigation

**Working branch:** `green/issue-280-invited-welcome`
**Investigation base before the latest error:** `fe742e6`
**Pushed diagnostic commit:** `1fef972`
**Latest pushed code:** `99c2927`. Current uncommitted changes are welcome-dialog sizing/spacing and this new diagnostic observation.
**State:** The current Play failure is identified as a pre-inference admission rejection. The payload-level reason remains under investigation. Do not describe sponsored Play as fixed yet.

## Regular-account ChatGPT connection follow-up (2026-10-27)

At 7:15 PM PDT the user reported that a signed-in, non-sponsored member saw the
**Connect to ChatGPT** pill. Clicking it displayed a red `AI account change
failed` message below the pill. This differs from the sponsored path, which
uses SIGMA's sponsored provider and does not need the member's personal
ChatGPT registration.

Source tracing found a specific failure path: for an authenticated local
member without sponsorship eligibility, the pill passed the globally active
ChatGPT registration ID to `/api/ai/auth/begin`. If that active registration is
the designated sponsor account, the server correctly rejects personal
reauthorization through the sponsor account. The frontend `aiPost` helper read
only JSON `error`, while FastAPI returns HTTP exceptions in JSON `detail`, so
the user saw the generic fallback instead of the server's reason. The
screenshot itself does not expose which account ID was sent, so that detail is
a source-verified mechanism matching the failure, not a captured live request.

The user also explicitly required that no Cancel button appear below the
ChatGPT pill. That inline action was removed. Closing the ChatGPT sign-in
popup now cancels the pending attempt; the real-Chrome acceptance verifies
there is no Cancel button under the pill while the normal-member connection is
pending.

The local non-sponsored member path now starts a new ChatGPT account flow
without sending the globally active account ID. `aiPost` also displays
FastAPI's `detail` when a request fails. Real-Chrome acceptance sets a
non-sponsored member's active registration to the sponsor registration and
verifies that the new flow omits `account_id` and completes, while existing
sponsored selection and sponsor renewal checks still pass. `./sigma test`
passed all steps, including Ruff, Pyright, frontend typecheck, and production
build. No live OAuth, paid provider call, or production change was made.

## Retrospective: what is known

The user is signed in locally with `nontrivialzeeros@gmail.com`. The account has shown the sponsored ChatGPT pill. SIGMA's designated sponsor ChatGPT account is `zetacontinuation@gmail.com`; the user authorized that account in the browser and received the “Return to SIGMA to continue” confirmation. The private diagnostic log recorded sponsor OAuth `started` at `2026-10-27T22:37:03Z` and `connected` at `2026-10-27T22:37:18Z` (3:37 PM PDT). An earlier read-only account-state check also showed the member eligible for sponsored access and model mode `sponsored`. These facts establish the sign-in and sponsorship state; by themselves, they do not establish that inference works.

There have been several different Play errors over time. Earlier messages mentioned an expired ChatGPT session, sponsor-session provisioning/reconnection, and temporary sponsored unavailability. Source inspection showed sponsored requests are intended to use the server-held sponsor ChatGPT session rather than the member's personal ChatGPT credential. Those earlier provider/authentication messages are distinct from the latest error, which rejects the request before provider dispatch. The live cause of the earlier provider errors was not established by an inference response, so do not conflate them with the current failure.

## User-visible symptom record

The reproducible context reported by the user is a local run started with `./sigma start --nav`, signed in as the sponsored member `nontrivialzeeros@gmail.com`. The header showed the sponsored ChatGPT pill. The user expected that member's configured allowance (first tested at `$0.01`, later raised to `$0.25`) to be visible and decremented by use. The designated sponsor is `zetacontinuation@gmail.com`. The latest failure occurred while opening an existing project with substantial saved research history and pressing Play; it did not create a running session or change saved research.

Observed user-facing errors must be kept separate because they point to different layers:

1. **Personal ChatGPT-session expiry:** `Your ChatGPT session has expired. Please sign in again to continue.` The user clarified that sponsored inference should use the server's designated sponsor account, not require the sponsored member to connect a personal ChatGPT account. This was the first indication that provider selection might be wrong, but later source inspection and subsequent errors moved the investigation to other layers; it is not proof of the current failure cause.
2. **Sponsor setup/unavailability:** messages included `The administrator must provision or renew the configured ChatGPT sponsor session on the server. Google sign-in does not authorize ChatGPT plan use. No API-key fallback was selected; saved research is unchanged.`, an instruction to reconnect the sponsor in Admin Settings, and `SIGMA-sponsored ChatGPT is temporarily unavailable. Please try again later. Saved research is unchanged.` The user had completed the sponsor browser authorization and saw “Return to SIGMA to continue.” No successful real inference response was observed, so the relationship between those earlier errors and the sponsor credential remains unresolved.
3. **Large/garbled error presentation:** after Play failed, the user saw two simultaneous oversized toasts. The upper toast said the server returned an unusually long HTTP 400 response and SIGMA shortened it; the lower toast exposed a long, partly truncated body with obligation identifiers and explanatory prose. The upper toast was a consequence of the lower oversized API error, not a second diagnosis. This presentation made the underlying rejection hard to read and risked covering project content. Toast length/count were bounded in a prior patch; the latest failure is now reported as one shorter admission error.
4. **Latest reproducible admission rejection:** the prior attempt reported `Research was not started; no provider call was made. Establish the known-mechanism frontier: 15 unresolved prior-session obligations exceed the safe context bound; Find a novel temporal coupling, not another marker: 14 unresolved prior-session obligations exceed the safe context bound. Saved research is unchanged. Disable the affected strategy or start a new, narrower strategy informed by its saved findings.` The new attempt reports `Research was not started; no provider call was made. Gap removal and Gaussian binomial sums: 12 unresolved prior-session obligations exceed the safe context bound. Saved research is unchanged. Disable the affected strategy or start a new, narrower strategy informed by its saved findings.` Both happen before provider dispatch, so neither is evidence about the sponsor credential. These named strategies and counts are from the user's actual project, not generated by tests.

The user also reported an earlier unrelated 1 MB research-provider transport error and that changing the project's Maximum agent calls had no effect. The call-limit issue was later traced to local sponsored users incorrectly receiving a hosted six-call cap and was separately fixed/tested; it is not the cause of the current 400. Keep this distinction in future handoffs so prior symptoms are not collapsed into one guessed root cause.

### Latest retry: 2026-10-27, 5:52 PM PDT

The user tried Play again and received the 400 shown above for “Gap removal and Gaussian binomial sums” (12 omitted obligations). I read the shared `sponsor-diagnostics.log` directly. It records:

```text
2026-10-28T00:52:28+00:00 sponsor_context status=o12_b31118_t156_a414_r0_p416
2026-10-28T00:52:28+00:00 sponsor_play status=post_400
```

This means 12 obligations were omitted and the selected obligations already occupied 31,118 JSON bytes against the 32,000-byte snapshot cap. The largest individual text, scope-assumption, rationale, and provenance fields measured 156, 414, 0, and 416 bytes respectively. This points to aggregate context volume across many obligations, not a single huge text or scope field. The `sponsor_play post_400` and absence of any later `sponsor_inference call_started` show no provider dispatch occurred for this retry. The diagnostics do not log the total byte size of omitted obligations, so they do not yet quantify the exact additional bytes required. Do not raise the cap blindly: the complete role context still has a separate 256 KB limit and other mandatory project/history inputs.

The user raised the local sponsored allowance to $0.25 after using $0.01 to exercise the reload flow. No live or paid inference was run by the coding agent. Project call-budget settings and provider authorization are separate concerns; the call-budget dialog issue and earlier 1 MB response issue are not evidence about this latest preflight rejection.

## Attempt and evidence timeline

### 2026-10-27, 5:11 PM PDT

The user reported that Play produced two oversized toasts. The first said the server returned an unusually long HTTP 400 error; the second exposed a truncated error containing an unresolved-obligation context-bound message. The shared private diagnostics log recorded:

```text
2026-10-28T00:11:09+00:00 sponsor_play status=post_400_large
```

The timestamp is 5:11:09 PM PDT. The API error and the matching server guard establish that session admission rejected the request before any provider call. The sponsor ChatGPT credential was not exercised by this attempt.

### First diagnostic and toast patch

Commit `6ae3f78` added token-free request-stage diagnostics, bounded toast text, a 60-second/five-toast UI cap, and documentation for reading the shared private log. `./sigma test` passed on that commit, and the hosted browser check passed. This did not by itself fix Play.

### First context-compaction attempt

Commit `53e1bbf` compacted repeated provenance references in frozen historical obligations to first/latest pointers, while retaining obligation text, scope, and durable source records. It also shortened the admission error and removed the Play component's duplicate toast report. A synthetic research-session regression with 15 obligations and 32 source artifacts each passed, as did `./sigma test` and the hosted Chrome check.

That synthetic regression was inadequate for the user's project. It exercised repeated source references but not the user's actual payload composition across strategies. The user retried and still received HTTP 400:

```text
Research was not started; no provider call was made. Establish the known-mechanism frontier: 15 unresolved prior-session obligations exceed the safe context bound; Find a novel temporal coupling, not another marker: 14 unresolved prior-session obligations exceed the safe context bound. Saved research is unchanged. Disable the affected strategy or start a new, narrower strategy informed by its saved findings.
```

The shared log recorded:

```text
2026-10-28T00:36:09+00:00 sponsor_play status=post_400
```

This is 5:36:09 PM PDT. It proves the first compaction attempt did not resolve the actual admission block. It also disproves the assumption that repeated provenance pointers were the only fields consuming the 32 KB budget. My earlier “high confidence” statement overreached: confidence was warranted for the failure category, not for the fix.

### Guest onboarding copy and pill layout

The guest welcome copy says guests may explore without running or saving projects, may request an invitation to become a member, and that the administrator decides whether to include sponsorship when granting the invitation. The welcome dialog has a single “Let's get started” action; Google sign-in is not placed inside that dialog. The user agreed to hide “Connect to ChatGPT” in Guest mode because it cannot be used there; the current patch implements this on Home and project headers and verifies six visible project-header actions. This change is unrelated to the Play admission failure.

### Backend restart check: 2026-10-27, 6:05 PM PDT

The 6:02 PM retry was handled by PID 79836, whose Uvicorn process started at
5:56:42 PM. The working-tree change from a 32,000-byte to a 64,000-byte prior
obligation snapshot was written at 6:04:31 PM. Therefore the 6:02 response came
from the pre-change process; it is not evidence that the 64 KB fix failed. The
source now has the 64 KB cap, and the next meaningful trial must run after the
backend reloads that module. The prior user authorization for one more trial
still applies. The trial may reach real sponsor inference and consume allowance.

The same read-only project measurement indicates that, once context admission
passes, the existing conservative per-call dollar reservation may be another
gate: for the saved `gpt-6.1-sol` model and 12,000 output-token ceiling, the
formula estimated about $0.29–$0.35 per call against the $0.25 session cap.
This is an estimate from the existing published-price reservation formula, not
a provider charge or proof that the next trial will reach that gate. Do not
raise the spending cap or weaken the reservation without authorization.

## Current implementation facts

- The admission code builds one prior-obligation snapshot across the selected strategies.
- `MAX_PRIOR_OBLIGATION_CONTEXT_BYTES` is now 64,000 bytes. The 6:02 retry ran
  before the backend loaded this source change.
- `MAX_PRIOR_SESSION_OBLIGATIONS_PER_STRATEGY` is 24; the user's 15 and 14 omitted counts are below this count ceiling, pointing to aggregate byte pressure instead.
- The attempted compactor retains each obligation's text and scope but only reduces selected provenance arrays. It does not currently compact oversized `scope_assumptions` or `rationale` fields.
- `MAX_AGENT_CONTEXT_BYTES` is 256,000 bytes. A read-only reconstruction of the saved ledger retained all 39 unresolved obligations with role contexts between 44,679 and 58,606 bytes, below this ceiling.
- `sponsor_play` diagnostics show only the HTTP result. No `sponsor_inference call_started` entry follows the sponsor OAuth connection or these two failed starts.

## Current working theory and uncertainty

**High confidence:** the 6:02 PM Play attempt was rejected before provider dispatch, but it used a backend process started before the 64 KB fix was written. It does not test whether that fix clears admission.

**Open question:** whether the 64 KB snapshot admits the actual ledger through to dispatch. The read-only reconstruction retained all 39 unresolved obligations and stayed within the independent 256 KB full-context ceiling. An existing conservative call-cost reserve is estimated at $0.29–$0.35 against the $0.25 sponsored per-session cap for the saved model/settings, and may be the next gate; this has not been observed live.

**Not yet established:** whether a real sponsored inference can complete successfully after admission. The next authorized trial may consume allowance if it reaches dispatch.
## Current trial: safe size diagnostics

Commit `1fef972` logs a bounded, numeric-only `sponsor_context` status from sponsored admission: omitted count, selected snapshot bytes, and maximum byte sizes for obligation text, scope assumptions, rationale, and provenance. It writes no obligation text, project/session/strategy IDs, account identity, prompts, credentials, or provider response. A focused regression asserts the status contains only bounded safe characters. This measurement is intended to discriminate oversized content fields from simple aggregate pressure before another product change is chosen.

Validation on `1fef972`:

- `tests/research_sessions.py`: passed.
- Focused `tests/cloud_auth.py`: passed (57 tests).
- An initial `./sigma test` run exposed one assertion that assumed a single diagnostics event. It was corrected to expect both `sponsor_context` and `sponsor_play`.
- Final `./sigma test` passed all scenarios, Ruff, formatting, Pyright, frontend typecheck, and production build.
- No live provider call has been made.

## Next steps

1. Verify the 64 KB change with regression coverage, full tests, and browser checks.
2. Regression now covers 39 unresolved obligations across three strategies with 32 source references apiece: the snapshot exceeds 32 KB, retains all items, and fits 64 KB. Full `./sigma test` and real-Chrome guest/sample plus local sponsored-limit checks passed. Restart the backend and use the one remaining Play attempt authorized by the user. Read the safe diagnostics immediately afterward to distinguish admission, dispatch, and provider outcomes.
3. If the trial reaches the measured reserve gate or fails at the provider, stop speculative changes and escalate with this journal. Keep membership checks, the 256 KB context ceiling, cost reservations, and allowance accounting intact.

## Trial log

| Trial | Change / action | Observation | Result |
|---|---|---|---|
| 1 | Read shared diagnostics after 5:11 PM attempt | `sponsor_play post_400_large`; response was HTTP 400 at admission | Identified current failure layer, not sponsor auth |
| 2 | `6ae3f78`: add request/inference stage logging and toast bounds | Full test and hosted Chrome check passed; later user attempt still failed preflight | Better observability; not a Play fix |
| 3 | `53e1bbf`: compact repeated source references; synthetic 15-obligation/32-source regression | Offline tests passed; user's 5:36 PM attempt still omitted 15 + 14 obligations | Failed to fix user's real payload; synthetic case was insufficient |
| 4 | `1fef972`: record aggregate and component byte maxima only | Focused research-session/cloud-auth tests and final `./sigma test` passed | Await measured user payload before changing bounds |
| 5 | Hide ChatGPT connection pill in Guest mode on Home and project headers | Hosted Chrome and guest sample browser checks passed; six visible project-header actions confirmed | Guest layout change complete; unrelated to the Play preflight block |
| 6 | User retry on instrumented local backend (running checkout SHA not confirmed); read shared diagnostics directly | “Gap removal and Gaussian binomial sums”: 12 obligations omitted; 31,118 selected JSON bytes; max text/scope/rationale/provenance fields 156/414/0/416 bytes; `post_400`, no provider dispatch | Aggregate prior-obligation volume exceeds the snapshot budget; not a sponsor-auth result. Need a lossless bounded representation or measured safe budget change |

| 7 | Compare the 6:02 PM diagnostic with live backend PID and working-tree timestamp | Backend PID 79836 started 5:56:42 PM; 64 KB source change timestamp 6:04:31 PM | The retry ran old code and cannot evaluate the 64 KB fix. User has one authorized trial remaining after backend restart. |

### Next sponsored retry: 2026-10-27, 6:18 PM PDT

The user restarted the backend and made the authorized trial. The response changed
to `HTTP 400 Bad Request: Cloud research is disabled until a valid default
per-user inference allowance of at most $15 is configured.` The shared log has
`sponsor_context status=o0_b2_t0_a0_r0_p0` followed by `sponsor_play status=post_400`;
there is no `sponsor_inference call_started`. This means the 64 KB context gate
was cleared and the request stopped in job preparation, before provider
dispatch.

The cause is an unconditional `_user_spend_ceiling_decimal()` call in
`prepare_job()`. It requires a configured fallback even when the signed-in
member already has an explicit allowance in SIGMA's account grant. The checkout
`.env` contains no `SIGMA_CLOUD_USER_SPEND_CEILING_USD`; the user had already
set an explicit account allowance. Job preparation now validates the effective
account allowance: an explicit member/domain amount works without a default,
while an account relying on the fallback still requires a valid configured
default. Global ceilings and the per-account maximum remain enforced.

The user also reported that invitation welcome should dismiss on backdrop click,
and that signing into Google from guest Play must return to the current project.
The welcome now dismisses on backdrop click. Google login stores only a
validated `/project?path=...` continuation with its short-lived OAuth flow; the
callback uses it only after authorization succeeds, and unapproved/denied flows
retain the existing invitation path. A regression rejects external return URLs.

Verification on this change: focused `tests/cloud_research.py` and
`tests/cloud_auth.py` passed. Real Chrome guest workflow passed with outside
click dismissal, expanded Samples persistence after returning from a project,
and the project continuation URL. Real Chrome local sponsored limits check
passed. Full `./sigma test` passed. No live provider call was made by the agent.
The next user trial may reach sponsor inference. The separate conservative
per-call reservation against the unchanged $0.25 session cap remains a known
possible next gate; no spending guard was relaxed.
