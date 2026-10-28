# Sponsored Play investigation

**Working branch:** `green/issue-280-invited-welcome`  
**Latest pushed commit at the start of this investigation:** `fe742e6`  
**Current investigation patch:** uncommitted; adds safe context-size diagnostics and updates regression coverage.  
**State:** The current Play failure is identified as a pre-inference admission rejection. The payload-level reason remains under investigation. Do not describe sponsored Play as fixed yet.

## Retrospective: what is known

The user is signed in locally with `nontrivialzeeros@gmail.com`. The account has shown the sponsored ChatGPT pill. SIGMA's designated sponsor ChatGPT account is `zetacontinuation@gmail.com`; the user authorized that account in the browser and received the “Return to SIGMA to continue” confirmation. The private diagnostic log recorded sponsor OAuth `started` at `2026-10-27T22:37:03Z` and `connected` at `2026-10-27T22:37:18Z` (3:37 PM PDT). An earlier read-only account-state check also showed the member eligible for sponsored access and model mode `sponsored`. These facts establish the sign-in and sponsorship state; by themselves, they do not establish that inference works.

There have been several different Play errors over time. Earlier messages mentioned an expired ChatGPT session, sponsor-session provisioning/reconnection, and temporary sponsored unavailability. Source inspection showed sponsored requests are intended to use the server-held sponsor ChatGPT session rather than the member's personal ChatGPT credential. Those earlier provider/authentication messages are distinct from the latest error, which rejects the request before provider dispatch. The live cause of the earlier provider errors was not established by an inference response, so do not conflate them with the current failure.

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

The guest welcome copy now says guests may explore without running or saving projects, may request an invitation to become a member, and that the administrator decides whether to include sponsorship when granting the invitation. The welcome dialog has a single “Let's get started” action; Google sign-in is not placed inside that dialog. In the header, keep “Sign in with Google” and “Invite me!” as distinct guest choices. The user agreed to hide “Connect to ChatGPT” in Guest mode because it cannot be used there; that header-pill change remains to be implemented and is separate from the Play admission failure.

## Current implementation facts

- The admission code builds one prior-obligation snapshot across the selected strategies.
- `MAX_PRIOR_OBLIGATION_CONTEXT_BYTES` is 32,000 bytes.
- `MAX_PRIOR_SESSION_OBLIGATIONS_PER_STRATEGY` is 24; the user's 15 and 14 omitted counts are below this count ceiling, pointing to aggregate byte pressure instead.
- The attempted compactor retains each obligation's text and scope but only reduces selected provenance arrays. It does not currently compact oversized `scope_assumptions` or `rationale` fields.
- `MAX_AGENT_CONTEXT_BYTES` is 256,000 bytes. Blindly increasing the 32 KB snapshot bound could move the failure to this later safety limit or crowd out other mandatory inputs, so do not increase it without measurements.
- `sponsor_play` diagnostics show only the HTTP result. No `sponsor_inference call_started` entry follows the sponsor OAuth connection or these two failed starts.

## Current working theory and uncertainty

**High confidence:** the latest reported Play attempt is rejected during local research-session admission because prior-session obligations do not fit the frozen context byte bound. No provider request is made, so this specific 400 is not evidence of a ChatGPT sponsor-session failure.

**Open question:** why do the real obligations still exceed the bound after provenance compaction? Plausible causes include large scope-assumption or rationale fields, the aggregate budget being shared across selected strategies, or another unusually large field. The user's actual saved session payload has not yet been measured by this code revision. Do not choose among these causes by guessing.

**Not yet established:** whether removing this preflight block will result in a successful sponsored ChatGPT response. A live sponsored inference has not yet been observed in the diagnostics log.

## Current trial: safe size diagnostics

The current uncommitted patch logs a bounded, numeric-only `sponsor_context` status from sponsored admission: omitted count, selected snapshot bytes, and maximum byte sizes for obligation text, scope assumptions, rationale, and provenance. It writes no obligation text, project/session/strategy IDs, account identity, prompts, credentials, or provider response. A focused regression asserts the status contains only bounded safe characters. This measurement is intended to discriminate oversized content fields from simple aggregate pressure before another product change is chosen.

Validation so far on this working patch:

- `tests/research_sessions.py`: passed.
- Focused `tests/cloud_auth.py`: passed (57 tests).
- Ruff on touched Python files: passed.
- An initial `./sigma test` run exposed one test expectation that assumed a single diagnostics event; the instrumentation now correctly emits both `sponsor_context` and `sponsor_play`. The assertion was updated. The focused `tests/cloud_auth.py` run passed (57 tests). A subsequent full `./sigma test` passed all scenarios, Ruff, formatting, Pyright, frontend typecheck, and production build.
- No live provider call has been made.

## Next steps

1. Complete the active `./sigma test`; fix any remaining regression before committing.
2. Commit/push the safe size instrumentation and this journal to the existing feature branch.
3. After the user restarts that code and makes one deliberate Play attempt, read `sponsor-diagnostics.log` directly and record the exact aggregate/component sizes here. This is a diagnostic retry, not a claim that Play is fixed.
4. Choose a fix based on measured sizes. Preserve unresolved obligation text/scope and provenance, the 256 KB agent-context ceiling, membership checks, and sponsored spending limits. If mandatory evidence still cannot fit safely, retain the fail-closed guard and make recovery understandable instead of hiding evidence.
5. Only after the new evidence shows provider dispatch should sponsor-session/provider response diagnosis resume. Confirm eventual Play success from a real sponsored attempt; offline fixtures cannot establish it.

## Trial log

| Trial | Change / action | Observation | Result |
|---|---|---|---|
| 1 | Read shared diagnostics after 5:11 PM attempt | `sponsor_play post_400_large`; response was HTTP 400 at admission | Identified current failure layer, not sponsor auth |
| 2 | `6ae3f78`: add request/inference stage logging and toast bounds | Full test and hosted Chrome check passed; later user attempt still failed preflight | Better observability; not a Play fix |
| 3 | `53e1bbf`: compact repeated source references; synthetic 15-obligation/32-source regression | Offline tests passed; user's 5:36 PM attempt still omitted 15 + 14 obligations | Failed to fix user's real payload; synthetic case was insufficient |
| 4 | Current instrumentation: record aggregate and component byte maxima only | Focused research-session and cloud-auth tests passed; final `./sigma test` passed all steps | Await measured user payload before changing bounds |
