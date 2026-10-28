# Sponsored Play investigation

**Working branch:** `green/issue-280-invited-welcome`
**Investigation base before the latest error:** `fe742e6`
**Pushed diagnostic commit:** `1fef972`
**Current worktree change:** guest-header pill visibility update, browser checks, and this symptom-log expansion are tested; pending commit/push.
**State:** The current Play failure is identified as a pre-inference admission rejection. The payload-level reason remains under investigation. Do not describe sponsored Play as fixed yet.

## Retrospective: what is known

The user is signed in locally with `nontrivialzeeros@gmail.com`. The account has shown the sponsored ChatGPT pill. SIGMA's designated sponsor ChatGPT account is `zetacontinuation@gmail.com`; the user authorized that account in the browser and received the “Return to SIGMA to continue” confirmation. The private diagnostic log recorded sponsor OAuth `started` at `2026-10-27T22:37:03Z` and `connected` at `2026-10-27T22:37:18Z` (3:37 PM PDT). An earlier read-only account-state check also showed the member eligible for sponsored access and model mode `sponsored`. These facts establish the sign-in and sponsorship state; by themselves, they do not establish that inference works.

There have been several different Play errors over time. Earlier messages mentioned an expired ChatGPT session, sponsor-session provisioning/reconnection, and temporary sponsored unavailability. Source inspection showed sponsored requests are intended to use the server-held sponsor ChatGPT session rather than the member's personal ChatGPT credential. Those earlier provider/authentication messages are distinct from the latest error, which rejects the request before provider dispatch. The live cause of the earlier provider errors was not established by an inference response, so do not conflate them with the current failure.

## User-visible symptom record

The reproducible context reported by the user is a local run started with `./sigma start --nav`, signed in as the sponsored member `nontrivialzeeros@gmail.com`. The header showed the sponsored ChatGPT pill. The user expected that member's configured allowance (first tested at `$0.01`, later raised to `$0.25`) to be visible and decremented by use. The designated sponsor is `zetacontinuation@gmail.com`. The latest failure occurred while opening an existing project with substantial saved research history and pressing Play; it did not create a running session or change saved research.

Observed user-facing errors must be kept separate because they point to different layers:

1. **Personal ChatGPT-session expiry:** `Your ChatGPT session has expired. Please sign in again to continue.` The user clarified that sponsored inference should use the server's designated sponsor account, not require the sponsored member to connect a personal ChatGPT account. This was the first indication that provider selection might be wrong, but later source inspection and subsequent errors moved the investigation to other layers; it is not proof of the current failure cause.
2. **Sponsor setup/unavailability:** messages included `The administrator must provision or renew the configured ChatGPT sponsor session on the server. Google sign-in does not authorize ChatGPT plan use. No API-key fallback was selected; saved research is unchanged.`, an instruction to reconnect the sponsor in Admin Settings, and `SIGMA-sponsored ChatGPT is temporarily unavailable. Please try again later. Saved research is unchanged.` The user had completed the sponsor browser authorization and saw “Return to SIGMA to continue.” No successful real inference response was observed, so the relationship between those earlier errors and the sponsor credential remains unresolved.
3. **Large/garbled error presentation:** after Play failed, the user saw two simultaneous oversized toasts. The upper toast said the server returned an unusually long HTTP 400 response and SIGMA shortened it; the lower toast exposed a long, partly truncated body with obligation identifiers and explanatory prose. The upper toast was a consequence of the lower oversized API error, not a second diagnosis. This presentation made the underlying rejection hard to read and risked covering project content. Toast length/count were bounded in a prior patch; the latest failure is now reported as one shorter admission error.
4. **Latest reproducible admission rejection:** Play reports `Research was not started; no provider call was made. Establish the known-mechanism frontier: 15 unresolved prior-session obligations exceed the safe context bound; Find a novel temporal coupling, not another marker: 14 unresolved prior-session obligations exceed the safe context bound. Saved research is unchanged. Disable the affected strategy or start a new, narrower strategy informed by its saved findings.` This occurs before a provider call, so it cannot be fixed by reconnecting ChatGPT or changing the sponsor account. The named strategies and exact omission counts are evidence from the user's actual project, not generated by the tests.

The user also reported an earlier unrelated 1 MB research-provider transport error and that changing the project's Maximum agent calls had no effect. The call-limit issue was later traced to local sponsored users incorrectly receiving a hosted six-call cap and was separately fixed/tested; it is not the cause of the current 400. Keep this distinction in future handoffs so prior symptoms are not collapsed into one guessed root cause.

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

Commit `1fef972` logs a bounded, numeric-only `sponsor_context` status from sponsored admission: omitted count, selected snapshot bytes, and maximum byte sizes for obligation text, scope assumptions, rationale, and provenance. It writes no obligation text, project/session/strategy IDs, account identity, prompts, credentials, or provider response. A focused regression asserts the status contains only bounded safe characters. This measurement is intended to discriminate oversized content fields from simple aggregate pressure before another product change is chosen.

Validation on `1fef972`:

- `tests/research_sessions.py`: passed.
- Focused `tests/cloud_auth.py`: passed (57 tests).
- An initial `./sigma test` run exposed one assertion that assumed a single diagnostics event. It was corrected to expect both `sponsor_context` and `sponsor_play`.
- Final `./sigma test` passed all scenarios, Ruff, formatting, Pyright, frontend typecheck, and production build.
- No live provider call has been made.

## Next steps

1. Commit and push the guest-only ChatGPT pill removal separately from any Play fix.
2. After the user restarts `1fef972` (or a later branch head) and makes one deliberate Play attempt, read `sponsor-diagnostics.log` directly and record the aggregate/component sizes here. This is a diagnostic retry, not a claim that Play is fixed.
3. Choose a fix based on measured sizes. Preserve unresolved obligation text/scope and provenance, the 256 KB agent-context ceiling, membership checks, and sponsored spending limits. If mandatory evidence still cannot fit safely, retain the fail-closed guard and make recovery understandable instead of hiding evidence.
4. Run full tests and real-browser checks on the chosen implementation, then update this journal with exact results.
5. Only after the new evidence shows provider dispatch should sponsor-session/provider response diagnosis resume. Confirm eventual Play success from a real sponsored attempt; offline fixtures cannot establish it.

## Trial log

| Trial | Change / action | Observation | Result |
|---|---|---|---|
| 1 | Read shared diagnostics after 5:11 PM attempt | `sponsor_play post_400_large`; response was HTTP 400 at admission | Identified current failure layer, not sponsor auth |
| 2 | `6ae3f78`: add request/inference stage logging and toast bounds | Full test and hosted Chrome check passed; later user attempt still failed preflight | Better observability; not a Play fix |
| 3 | `53e1bbf`: compact repeated source references; synthetic 15-obligation/32-source regression | Offline tests passed; user's 5:36 PM attempt still omitted 15 + 14 obligations | Failed to fix user's real payload; synthetic case was insufficient |
| 4 | `1fef972`: record aggregate and component byte maxima only | Focused research-session/cloud-auth tests and final `./sigma test` passed | Await measured user payload before changing bounds |
| 5 | Hide ChatGPT connection pill in Guest mode on Home and project headers | Hosted Chrome and guest sample browser checks passed; six visible project-header actions confirmed | Guest layout change complete; unrelated to the Play preflight block |
