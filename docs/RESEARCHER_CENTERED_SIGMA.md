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
