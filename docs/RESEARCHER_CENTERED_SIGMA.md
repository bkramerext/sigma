# Researcher-centered SIGMA initiative

Coordinator scope and mailbox: [blue_out_1](../messages/blue_out_1.md).
Working branch: `blue_session`. Only Increment 1 is authorized by this message;
subsequent increments require the next numbered coordinator assignment.

## Increment 1 — truthful confidence and argument availability

Implemented a shared Python presentation vocabulary in
`src/sigma/research_epistemics.py`. Public Outcomes, operational/research metrics,
deterministic text/HTML/TeX reports, and newly generated Conclusions use it.
The frontend consumes these service labels in normal and rendered Outcome,
Status, detailed Solution review and the Conclusion's current-verification line.
There is no second status-to-confidence mapping in the frontend.

| Saved verification code | Human-readable meaning |
|---|---|
| `incomplete` | Incomplete |
| `convincing_unverified` | Convincing but unverified |
| `unknown` or an unrecognized declaration | Unknown |
| Absent declaration | Not recorded; legacy public reviews may retain their existing derived Unknown default |
| `verified` | Reported verified; not independently checked by SIGMA |

Raw codes, saved role outputs, artifacts and persisted Conclusions remain intact.
A `verified` string is a declaration, not checker provenance; SIGMA has no
independent proof-checking service. A structured candidate with incomplete,
unknown, missing or only self-declared verified status is not promoted to a
complete reviewed positive result. The supported agent-reviewed unverified
candidate path remains available with `convincing_unverified` and structured
steps. Execution failure remains a separate status and still carries its caveat.

Historical records without structured steps are classified by representation:
structured steps, available narrative, or no recorded argument narrative.
Nonempty prose establishes availability only; it does not establish a valid or
complete proof. The unchanged Maximum Regions archive now says **Mixed ·
unstructured argument, unassessed**, and points to Reasoning / proof and the
research artifacts. Its historical Conclusion fallback supplies the same
availability notice, without inventing a historical answer or structured steps.
A stored Conclusion remains byte-for-byte intact with a current verification
caption beside it. Newly generated Conclusions include the canonical label.

Standalone reports derive current labels from the raw review rather than trusting
an archive's cached metric prose. Raw verification codes remain separately
available. Report rendering and public projection do not rewrite the input
archive. AI paper authoring was not invoked; its source snapshot receives the
same public Outcome projection, but generated prose is not evaluated here.

## Verification and evidence

[Evidence index](evaluations/INCREMENT_1/README.md) records commands, the actual
Chrome matrix, screenshots and full offline results. The browser check uses the
unchanged historical Maximum Regions argument and five deterministic archived
Nonconsecutive sessions. Additional records change only verification declarations
for presentation regression; they are explicitly not new research results.
The source archives, canonical samples and preexisting temporary session records
are hash-checked for immutability. No provider inference is submitted.

## Scope boundary and next proposal

No T48 contradiction classification, obligation reconciliation, findings-fork
redesign, default Markdown-mode change, new evidence navigation or broad UI
redesign is included. Those require later coordinator scope. The next useful
focus is a conservative current-state projection over explicit obligation
resolutions and supersessions, after independent review of this increment.
Live research quality, independent proof verification, live feedback uptake and
AI paper quality remain unverified. Engineering checks and fixture rendering do
not establish those properties.

## Increment 2 — current understanding foundation

Scope: [blue_out_2](../messages/blue_out_2.md) with the standing export supplement
[blue_out_3](../messages/blue_out_3.md). The permanent human-directed cycle is
[Blue operating protocol](BLUE_OPERATING_PROTOCOL.md). The next assignment is
expected in `blue_out_4.md`; no later increment is started by this document.

### Contract and what the view means

`src/sigma/research_state.py` provides a typed, deterministic, read-only
projection. `GET /api/projects/current-understanding?path=…` reads saved session
files without recovery, restart, directory creation or provider dispatch. The
ordinary sessions response additionally carries a projection over the same
returned session list, so the browser can refresh it alongside session history.
Existing lifecycle recovery behavior remains in the ordinary sessions endpoint;
the new standalone current-state read does not invoke it.

The version-1 contract contains:

- `findings`: every retained local claim, investigated claim, raw review status,
  scope/assumptions, evidence kind, verification caution and composite source ID.
  `review_ref` is an explicit record path, not a fabricated historical UUID.
- `current_finding_ids`: the latest saved reviewed finding for each strategy,
  excluding explicitly superseded/refuted targets. “Current” means latest
  recorded review, **not** a semantic ranking of truth or independent support.
- `obligations`: exact scoped declaration identities, original source pointers,
  recorded dispositions, evidence/rationale, and actionability qualification.
  IDs reuse the existing T37 project/strategy/assumption/text identity. Similar
  wording and matching text in another scope cannot resolve an obligation.
- `changes`: explicit local counterexample reports, source-linked obligation
  dispositions, explicitly saved claim relations, and later available reviews.
  A later review is not automatically a correction, contradiction or supersession.
- `next_investigations`: proposals drawn only from recorded current open work,
  never automatic strategy creation or a mandatory rerun of stale historical notes.
- `failures` and `limitations`: failed/incomplete execution states, unavailable
  records, ambiguous/dangling references and the boundary of what was reconciled.
  `project_status` remains `not_determined`; a local/session result is not silently
  converted into a project-level theorem or discovery.

An obligation-ID disposition needs an existing target, an explicit rationale,
and available unambiguous evidence. Artifact references cannot point into the
future. Step references additionally require a completed, timestamped step in
the same owning session, preceding the disposition artifact. Resulting states
are **resolved reported**, **superseded reported**, **retracted reported**, or
**open reported**; none means independent proof verification. A later declaration
can reopen work rather than inherit an older closure. Unsupported references are
counted, not silently accepted. Duplicate composite identities and foreign
project records are excluded with an uncertainty notice.

Without such a disposition, a legacy note can remain **historical unreconciled**.
An exact later `resolved_objections` entry with a source link is exposed as a
narrative notice, not a machine resolution. It is not matched by loose textual
similarity. Latest partial-review open notes can be proposed for investigation;
unlinked older duties are kept visible without being blindly recycled into
mandatory steps. Their absence from the proposal list does not mean resolution.

Optional `finding_relations` explicitly identify the source session/artifact,
`refutes` or `supersedes`, a rationale and basis references. They are read only;
no new agent prompt or writer emits them in this increment. Minimal synthetic
fixtures exercise that contract. Existing peer-handoff retractions are deliberately
not interpreted as retracting a whole mathematical claim.

### Real historical detail discovered in the exports

The unchanged Maximum Regions archive actually contains ten structured
obligation-review entries. Four target the identified open/objection declarations
and have usable construction-step provenance. The new view reports those four
resolutions as agent-reported/unverified. The separate final “Finish and state…”
note remains unreconciled and is **not** proposed as another required run.
Unmatched review IDs are counted as unavailable to this projection rather than
mining prompt archives or manufacturing an obligation identity. All original
review content remains in the complete audit export for independent inspection.

This refines the earlier study's diagnosis: the defect was not simply an absence
of all machine-readable resolution evidence; existing evidence was not presented
as a coherent current state. A synthetic variant with the ID-linked reviews
removed separately tests the genuinely narrative-only reconciliation boundary.
It is not substituted for the original provider archive.

For Nonconsecutive, the saved `decisive_counterexample` reason is scoped to the
investigated guessed recurrence. The later Gaussian-normalization repair and
its earlier faulty explanation remain inspectable, without inventing a formal
supersession relation. Finite computations do not close the recurrence or density
proof obligations. All five sessions remain explicitly deterministic evidence.

### Visible experience and boundaries

A single foldable Current understanding section appears before the full session
history, with **Current findings**, **What changed / superseded**, and **Open or
not yet reconciled**. Previews are bounded and explicitly marked when shortened;
full source records remain accessible. Source controls expand the owning session,
open the evidence and exact artifact, focus it and scroll to it. Desktop uses
three compact columns; narrow screens stack them. Existing header controls,
Conclusion modes, strategy editing/forking and report generation are unchanged.

Complete Project Audit JSON and deterministic text/HTML/TeX exports for all three
exercised copies are committed under
[evidence exports](evaluations/increment_2/exports/README.md). A subsequent real
browser download confirms identical audit content and retains its own original
bytes. Current-understanding API responses are separately retained. No export
was manually reconstructed or relabeled as native Markdown. Existing audit and
HTML/TeX report content is intentionally unchanged in 2A; integrating the current
state into forks/reports needs the coordinator's next bounded scope.

### Validation and remaining work

Focused regressions cover the unaltered archives, explicit ID-linked resolution,
reopening, narrative-only notices, unrelated/complementary claims, explicit
synthetic claim relations, missing/foreign/future evidence, stable ordering/IDs,
read-only running/empty/failed histories and unsafe history storage. The new
scenario is part of `./sigma test`. Actual commands/results, Chrome journeys,
screenshots and source hashes are linked from
[Increment 2 evidence](evaluations/increment_2/README.md).

Current research state is now easier to inspect; fresh intellectual progress is
not claimed. Live generation, intervention uptake, independent correctness and
paper quality remain N/O. Historical ambiguities remain visible. The next useful
bounded direction is to let a reviewed current-state snapshot inform a proposed
continuation without reviving discharged duties; it must retain the underlying
sources and never silently edit the strategy. That is a proposal for coordinator
scope, not authorization to begin it.
