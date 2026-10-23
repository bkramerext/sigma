# A24 — Research outcome metrics

**Status:** Complete

## Objective

Show one compact metrics table within every research outcome. Keep operational
measurements separate from research-quality measurements, and derive both from
persisted session evidence. Preserve existing outcome labels, solution reviews,
strategy attribution, and the Strategy Assessments table.

| Operational measurements | Research-quality measurements |
| --- | --- |
| Participating agents | Strategies investigated |
| Model calls by status | Research cycles |
| Input, output, cached, and total tokens | Outcome classification |
| Session wall-clock and agent call durations | Verification status |
| Python executions by status | Open proof obligations |
| Research/Python artifact counts and storage | Evidence-backed conclusions |
| Provider failures and repeated attempts | Strategy contribution |
| Estimated monetary cost when substantiated | Unresolved objections |

## Accounting rules

- Count distinct persisted provider step IDs and Python execution IDs. Recovery
  and reuse attach the original computation ID; they do not create another run.
- Count a strategy as investigated only when it has a dispatched role step.
  Count a cycle once per strategy/cycle key, even when branches execute
  concurrently. Wall time is elapsed session time; per-role durations sum
  distinct call intervals and may overlap.
- Token totals use only persisted provider usage. Missing input/output metadata
  makes their aggregate unavailable; missing cached-token detail makes only the
  cached total unavailable. Cached tokens are a subset of input tokens.
- A 4xx response is a rejection when a saved HTTP status or safe diagnostic
  supports that classification. Timeouts, interruptions, and other failures
  remain distinct. No automatic retry is assumed; a repeated attempt is counted
  only when distinct persisted steps repeat a strategy/role/cycle key.
- ChatGPT-plan allowance consumption is unknown even when the provider reports
  token counts. Show no dollar cost for plan mode. API-key dollar estimates
  require complete actual usage, cached-token detail, and a known applicable
  model price; otherwise show unavailable.
- `—` means evidence is unavailable or incomplete; `0` means the evidence
  supports a measured zero. Missing historical attribution stays unknown.
- A successful computation, engineering completion, agent agreement, or
  evidence-linked conclusion does not imply mathematical verification.

## Acceptance

- Deterministic backend regressions cover incomplete records, token gaps, HTTP
  rejection, timeout/cancellation/recovery, repeated attempts, reused Python
  executions, concurrent strategies, cost availability, and research-quality
  attribution.
- Frontend/browser checks verify the compact table, unavailable values, and
  truthful verification wording.
- JSON audit export and text/HTML project reports include the same outcome
  metrics.
- `./sigma test` and relevant real-browser checks pass. No live provider calls
  are required or authorized for this assignment.
