# Hosted production issues handoff

## Google sign-in

The production edge already waits for both frontend and backend health. The
backend health check runs `sigma.deployment_health`, which validates cloud
authentication configuration before the edge accepts traffic. No startup
ordering gap was found in `deploy/compose.yaml` or `deploy/start-gce.sh`.

The callback had a cold-start failure window: it consumed the single-use OAuth
flow and exchanged Google's one-time authorization code before fetching OIDC
discovery and signing keys. A transient failure on either metadata GET made
the first sign-in unrecoverable. The callback now retries those safe reads,
caches validated Google signing keys for one hour, refreshes once for a newly
rotated key, and consumes the flow only after metadata is available. If all
metadata retries fail, the flow and authorization code remain available for a
retry. Tests exercise both an in-request transient failure and a full metadata
outage followed by a retry of the same callback.

## Sponsored research spending cap

`project_spend_limit_exceeded` is returned by OpenAI when the API key's
associated API project has reached its enforced hard spend limit. SIGMA's
user/global research allowance cannot override this provider-side limit. The
existing retry policy already stops automatically for this condition; this
change expands its regression coverage and gives the user the exact operator
setting to inspect.

An OpenAI organization or project owner should open **OpenAI Platform →
Organization settings → [the project that owns the deployed SIGMA API key] →
Limits**. Review **Monthly spend limit** and **Enforce a hard limit**. If
spending should continue, raise the monthly limit or disable the hard limit
after reviewing usage and authorization; otherwise wait for the monthly reset.
Also check the organization spend limit and prepaid credit balance. OpenAI's
[project management guide](https://help.openai.com/en/articles/9186755-managing-projects-in-the-api-platform)
describes the project Limits page, and its
[spend-limit troubleshooting guide](https://help.openai.com/en/articles/6614457-troubleshooting-api-usage-and-spend-limits)
maps this exact error code to an enforced project hard limit. No API key,
project selection, provider spend cap, or paid request was changed by this PR.

## Checks and limitations

The focused Google auth and reference compiler tests passed locally; exact
full-suite and browser results are recorded in `docs/STATUS.md`. The real
production Google round trip and the provider cap change require their
respective external operator settings and are not claimed as verified here.
