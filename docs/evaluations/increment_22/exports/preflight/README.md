# T146 provider preflight result

The authorized read-only metadata lookup was attempted once on 2026-10-25 UTC:

- Request: `GET /v1/models/gpt-6.1-sol`
- Project context: `proj_ZqoKimk90I8vLSFDM7FGeLVj` via `OpenAI-Project`
- Result: HTTP `401 Unauthorized`; model availability and key/project binding were not verified.
- Request ID: `48778463-30fd-4aa0-af48-eb420425bfab`
- No authorization value, response body, or response headers were retained. See
  `models-api-preflight.json` for the sanitized record.
- No Responses/inference request was sent. Research generation calls, tokens,
  and research spend: zero. The experiment did not start, so there are no arm
  results or duration measurements.

**Stop condition:** the configured credential was rejected by the Models API
under the configured project context, and its non-secret classification did
not establish that it is a project-scoped key. The project association and
`gpt-6.1-sol` availability therefore remain unverified. Replace or repair the
runtime credential so it is a valid project-scoped key for the configured
project, then request another preflight. No research request may be sent until
that succeeds.
