# T146 provider preflight evidence

All attempts used only the authenticated Models API `GET /v1/models/gpt-6.1-sol` with the configured non-secret project context. No Responses/inference request was used for model preflight. Sanitized attempt records preserve HTTP status, model ID when returned, request IDs, project context, and credential classification; no authorization value or response body is stored.

- Attempt 1: HTTP 401; project binding/model availability not established.
- Attempt 2: HTTP 200; returned `gpt-6.1-sol`; project-scoped key and project header accepted.
- Attempt 3: HTTP 200; returned `gpt-6.1-sol`; project-scoped key and project header accepted.

The first rejection is retained as negative evidence. The current successful evidence is in `models-api-preflight-attempt-3-success.json`. These are read-only metadata lookups, not research turns. Research generation begins only in the paired trial artifacts.
