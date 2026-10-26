# T88 hosted personal connection boundary

Hosted connection selection is persisted in the `user_state.model_access`
column keyed by the verified Google OIDC `sub`. New hosted accounts start on
`personal`; returning users retain their existing selection. The authenticated
`POST /api/ai/mode` endpoint accepts only `personal` or `sponsored`, checks the
current user's eligibility and remaining sponsored allowance, and stores the
choice server-side. It does not accept credentials or an identity from the
browser.

`openai_connection.auth_context()` is the routing boundary. For `personal`, it
calls `cloud_personal.auth_context()` and receives an empty, unavailable
credential context. It never reads the sponsor store and no hosted personal
OAuth endpoint is enabled. Inference therefore stops before provider dispatch;
there is no sponsored or personal fallback. For `sponsored`, routing reads only
SIGMA's configured sponsor connection. Existing `cloud_research` budget,
allowance, call-reservation, failure-hold, and concurrency controls remain the
admission path for hosted inference.

The future credential-store boundary is `ai_store.transaction()` while the
verified workspace scope is bound. Hosted user stores are rooted under the
private sponsor auth home at `personal-users/<subject-hash>/`; the path contains
neither the raw Google subject nor email. `cloud_sponsor` uses the separate
`sponsor_transaction()` and temporarily binds ChatGPT auth refresh to the
sponsor directory. This keeps the designated sponsor account independent of a
request's user context. No credentials are returned in connection, status, or
model APIs; the browser only receives connection state and allowance data.

The existing local ChatGPT sign-in, callback, token validation, and refresh
remain unchanged. Deterministic tests exercise subject-scoped store isolation
and refresh rotation without an external call. Hosted personal authorization
remains unavailable: SIGMA has no confirmed OpenAI-supported hosted plan-access
flow or approved local-helper transfer. A future adapter may replace
`cloud_personal.auth_context()` only after that access path is confirmed and
must keep credentials server-side in the current verified-subject store. Do not
infer plan-inference permission from a website sign-in client.
