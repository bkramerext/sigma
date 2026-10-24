# Long-form paper generation

Status: implemented on `t45-long-paper-generation` after explicit user authorization.
No live or paid provider call was used for implementation or verification.

## Design

The old path sent the full snapshot in one request and asked for the whole paper
in one response. It rejected snapshots above 100,000 bytes, while one API-key
response was limited to 12,000 output tokens and 1 MB. Increasing only the input
cap would still leave long manuscripts vulnerable to output truncation.

The new path keeps the complete normalized snapshot and its SHA-256. At 100,000
bytes or less, the existing one-call workflow remains available. Larger
snapshots automatically use long-form authoring; the checkbox can select that
workflow for a smaller snapshot too.

Long-form work proceeds in bounded stages:

1. Flatten saved fields into UTF-8-safe fragments associated with their stable
   project, strategy, session, artifact, run, or step ID and field path. Pack
   at most 100 field fragments into each 48 KB request, with at most 512
   evidence batches.
2. Extract up to three concise, source-referenced notes per batch. Every
   fragment must be marked as covered by a note or explicitly omitted with a
   reason. The omission ledger retains the exact field pointer, stable source
   ID, and reason. Preserve negative and conflicting findings, methods,
   limitations, and open questions. Reduce the index hierarchically only when
   needed to fit the bounded outline request; report compacted notes and source
   IDs lost during reduction.
3. Generate an outline and shared claim register with at most 48 sections.
   Generate each section in its own structured response, with only its assigned
   evidence notes and claim definitions.
4. Validate references and obligations against the complete frozen snapshot,
   assemble TeX from structured prose, compile, then publish one immutable
   paper version containing the snapshot, draft, warnings, and PDF.

The full snapshot remains attached to the paper. Coverage status is a model
self-assessment, not independent semantic verification; explicit omissions and
reduction losses are listed in the paper metadata and UI. A visible warning
says compacted indexing may not preserve every source detail; section claims
must cite stable source IDs. No stage claims that a model reviewed every
semantic detail of the frozen data or independently verified conclusions.

Before a long run, preflight reports snapshot size, source count, evidence-batch
count, calls by stage, and the maximum requested API-key output tokens. It
identifies a compatible checkpoint, completed batches/reduction groups/outline
sections, and attempts already made in current and prior runs. The user
confirms before any provider request. Generation is bound to the preflight
snapshot hash; changed research requires renewed confirmation. The browser
streams stage progress and cancellation. API-key and ChatGPT-plan billing
identities remain unchanged, with no automatic fallback.

Completed long-form stages are checkpointed atomically in the project's private
`papers/.long-paper-work/` directory. A retry resumes only when the snapshot
hash, project identity, hashed provider identity, model, and reasoning effort
still match. Checkpoints contain no credentials. Completed batches, outline,
and sections are reused. A counted request that completes immediately before a
process crash but before its result is checkpointed can be repeated on retry.
The browser offers an explicit restart after confirmation when work is
exhausted or incompatible; it clears completed work but preserves prior-run and
lifetime call-attempt accounting in the next checkpoint and final paper record.

## Current bounds

| Stage | Bound | Behavior at the bound |
|---|---:|---|
| Frozen evidence snapshot | 20 MB | Reject before provider use; no evidence is dropped |
| Evidence request/index | 48 KB; 100 fields; 3 extracted notes; 512 batches | Every field has a covered/omitted status; source-linked conflicts and omissions are retained |
| Long-paper outline | 220 KB input; 48 sections; 200 claims | Reject malformed or over-bound structured output |
| Provider requests | 120 seconds each; 593 calls maximum | Stop without publishing; completed checkpoints remain resumable |
| API-key response | 12,000 requested output tokens and 1 MB response | Reject incomplete/oversized response; no partial paper published |
| ChatGPT-plan response | 4 MB streamed response | Reject incomplete/oversized response; no partial paper published |
| Each authored section | 250 KB serialized output | Reject oversized section; prior completed sections remain checkpointed |
| TeX compilation for papers | 50 MB source; 300 seconds; 80 MB PDF | Tectonic runs in untrusted mode; no PDF is published on failure |
| Saved paper version | 100 MB including snapshot and PDF | Reject publication atomically |

These are finite safety and billing bounds, not promises of unlimited generation.
The general deterministic report exporter retains its existing 2 MB source,
45-second, and 20 MB PDF limits; the larger limits apply only to AI-authored
papers.

## Verification

- `tests/papers.py` uses the Xenopus sample seed and a synthetic archived step
  to build an exact 483,485-byte evidence snapshot, verifies multi-batch
  preflight and generation, checks conflicting findings across sessions, and
  verifies exact field-omission reporting. It interrupts an evidence batch,
  index reduction, and section authoring; retries skip successfully checkpointed
  batches/reduction groups/outline. Simulated TeX compilation/publication
  failures retry without repeating completed provider stages. It exhausts the
  call budget, confirms preflight accounting, then tests explicit reset with
  prior attempts retained. Provider calls use a local fake.
- `browser_checks/t45_long_paper.py` uses real Chrome and the deterministic local
  provider fixture to open the Xenopus sample, confirm long-form call bounds,
  stream progress, save a multi-section paper, compile it with local Tectonic,
  and retrieve the PDF.
- A separate local Tectonic check compiled a 2,102,178-byte comment-heavy TeX
  source under the expanded paper source bound.
- A 48-section synthetic manuscript compiled from 2,303,560 bytes of TeX into
  a 614,123-byte PDF. The generated one-page fixture PDF was visually inspected
  from Chrome; no biological result is implied by that fixture.
- `env -u SIGMA_CLOUD_BOOTSTRAP_ADMIN_EMAIL ./sigma test` passed all scenarios,
  Ruff check/format, Pyright, frontend typecheck, and production build. The
  environment variable must be unset because it changes a tooling scenario's
  expected local configuration.
- Real Chrome T45 passed again after the review fixes using the Xenopus sample
  and deterministic local fixture; no provider inference or paid usage.

The preflight shows itemized call ceilings, structured input byte ceilings, and
the maximum requested API-key output-token ceiling. This is not expected token
consumption or a dollar estimate; no live model output quality, real account
allowance, or API cost was measured. ChatGPT-plan use is described in terms of
provider allowance because the client cannot convert it to dollars.

## Research integrity (issue #71)

The bounded index is an aid to synthesis, not a substitute for retained
reasoning. Long-form TeX adds a source-linked appendix from the frozen records
for structured reasoning steps, epistemic status, artifact references, Skeptic
assessments and objections, methods, negative findings, contradictions, and
unresolved obligations. Negative and limitation notes plus source-linked
conflict/gap notes are retained across checkpointing and index reduction and
appear in the appendix. This is deterministic rendering of saved records; it
does not claim independent scientific or mathematical verification.

Every field the extractor marks omitted remains listed with its saved source,
field pointer, and reason. Omissions of research fields are treated as material
unless the pointer names known record bookkeeping (IDs, timestamps, or record
kind). A material omission replaces the abstract and conclusion with a
prominent scope warning, marks every `established` claim `unresolved`, and
retains the full snapshot and omission ledger for review. This conservative
policy avoids presenting a result as established when the index cannot show
that the relevant evidence was considered.

The paper consumer accepts the structured outcome shape defined in Red's
PR #70 and the shared contract in issue #71 without scenario-specific logic.
Deterministic math and experimental fixtures exercise the saved shape, step
reviews, cross-session conflicts, and omissions. PR #70 remains a separate,
open producer change at this revision; until it is integrated, the paper can
preserve only structured outcome data actually present in a project's frozen
records. The consumer tests do not replace integration verification against
the merged producer.
