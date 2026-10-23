# T24 data contract for T25

T24 supplies outcome measurements and references to saved evidence. T25 owns
the **Sessions → Outcome** presentation and its collapsible Status, Strategy
Assessments, Metrics and Provenance subsections. T24 adds no Outcome table or
replacement hierarchy. The canonical ticket is `tickets/t24.md` in the pending
PR #11 ticket migration; this document describes the implementation contract,
not a second ticket.

## Metrics

Session reads (`get_session`, `list_sessions`, and their API routes) add
`outcome.metrics` as a projection of persisted session evidence. JSON audit
exports carry the same object. Reading a session does not write these derived
aggregates back into research history.

```text
outcome.metrics
  operational: [{label: string, value: string, detail?: string}]
  research_quality: [{label: string, value: string, detail?: string}]
  sources:
    session_id: string | null
    step_ids: string[]
    artifact_ids: string[]
    execution_ids: string[]
    strategy_ids: string[]
```

The two metric lists are independent, with no equal-length requirement. They
contain display-ready values: `—` means unavailable, while `0` requires saved
evidence supporting zero. Do not parse the values for numeric calculations or
use the labels as persistent identifiers. `detail` explains accounting limits.
Historical payloads without metrics/sources must remain viewable in T25.
Text and HTML reports render each nonempty group independently.

`sources` is a deduplicated inventory of existing IDs contributing to the
projection, scoped to its session. It is not a per-row source graph, a mapping
of every source to every metric, or verification authority. Missing IDs are
omitted; a missing session ID is null. Its step IDs refer to `session.steps`,
artifact IDs to `session.artifacts`, execution IDs to embedded or saved Python
execution records, and strategy IDs to investigated strategies. It does not
add selected but unrun strategies or count a reused execution twice.

## Structured provenance already available to T25

The session response and JSON audit export preserve the underlying structured
records; provenance is not limited to the textual metric values:

| Evidence | Source fields when persisted |
| --- | --- |
| Session and selected strategy | `session.id`, `project_id`, `strategy_id`, `strategy_ids`, `strategy_snapshot`, `strategy_runs` |
| Model, effort, billing mode | `session.model`, `reasoning_effort`, `mode` (saved session configuration; not an independent provider receipt) |
| Role and attempt | `steps[].id`, `role`, `strategy_id`, `cycle`, `call_number`, `status`, timestamps, `failure_kind`, `provider_http_status`, `interruption_reason` |
| Evidence included in a role call | Step `context_artifact_ids`, `prior_session_artifact_ids`, `peer_strategy_artifact_ids`, `peer_handoff_artifact_ids`, `peer_handoff_ids` |
| Saved finding and reviewed claim | Artifact `id`, `session_id`, `strategy_id`, `strategy_cycle` (legacy single-strategy `sequence`), `investigator_output`, `skeptic_output`, `objective_review.basis_artifact_ids`, `strategy_review.basis_artifact_ids` |
| Outcome and attribution citations | `outcome.basis_artifact_ids`, `outcome.solution_review.basis_artifact_ids`, `strategy_assessments[].basis_artifact_ids` |
| Earlier sessions and peer evidence | `prior_session_findings` with source session/strategy/artifact IDs; `peer_handoffs_prompted`, portfolio relations and saved peer handoffs |
| Python origin and reuse | Investigator output `python_code`, `python_execution`, optional `python_execution_reuse_reason`; execution `id`, `session_id`, `strategy_id`, `cycle`, `status` |
| Exact computation evidence | Execution `source`, `stdout`, `stderr`, `exit_code`, environment/limits, timestamps and `artifacts[]` with `filename`, `size_bytes`, `sha256` |

Original Python records are inspectable at
`GET /api/projects/research-executions/{execution_id}?path=...`; captured bytes
at the corresponding `/artifacts/{filename}?path=...` route are checked against
the saved hash. Reused evidence keeps its original session/strategy/cycle and
execution ID; the consuming Investigator output records the reuse reason.
An interrupted reservation means the program may have run, not that it failed
without effects or produced a conclusion. Preserve the raw execution status.

## Limits T25 must expose honestly

- Historical records may lack origin fields, usage metadata, timestamps or
  file hashes. Missing data remain unknown. Do not backfill invented IDs.
- Artifacts do not store explicit Investigator/Skeptic step foreign keys.
  Strategy/cycle/role narrows the candidate steps but is not an exact attempt
  link when that role was retried. T24 does not guess that association.
- Model/effort are recorded at session scope, not independently stamped by the
  provider on each response. Provider request IDs and billed plan allowance
  consumption are not supplied by this projection.
- The source inventory does not describe a dependency graph for each numeric
  subtotal or each claim. Inspect the originating records/citations instead.
- Raw session provenance and Python file evidence are preserved in JSON/API
  records; text/HTML metrics summaries do not reproduce the entire audit trail.
- Verification labels and citations are model/coordinator evidence. There is
  no independent proof checker, and computational success, agent agreement,
  source linkage and completed engineering work do not establish proof.
- Live research effectiveness and revised Python guidance remain unvalidated;
  deterministic fixture tests cannot close that gap.

## Accounting and validation

Distinct persisted step/execution IDs prevent recovery/reuse double-counting.
Concurrent wall time remains separate from summed role durations. Provider
rejections, timeout, cancellation, interruption, unknown status and repeated
attempts stay distinct. Dollar estimates require actual complete token usage
and applicable reviewed prices; plan consumption stays unknown.

Deterministic tests cover incomplete records, concurrent/recovered sessions,
provider failures, missing usage/cost metadata, reused execution IDs, unchanged
source records and unequal/empty metric groups in both text and HTML exports.
The existing Chrome scenario checks that metrics and source IDs remain present
in the API while Outcome interactions remain unchanged. T25 adds the eventual
Metrics/Provenance presentation and its accessibility checks.
