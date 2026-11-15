# A20 — AI-authored research paper

**Workstream:** Green screen (dedicated Codex worker).
**Status:** Assigned; implementation and verification not yet performed.
**Objective:** Transform SIGMA's durable research evidence into a coherent, researcher-quality, AI-authored paper, delivered as a professionally typeset PDF. This is **authorship and synthesis**, not a template rendering of project fields.

## Product contract

The existing Project Audit and deterministic Research Report are evidence-preserving exports. **Do not replace or degrade them.** Add a clearly differentiated **AI-authored paper** workflow. A paper should read as though a careful researcher wrote it: a meaningful title, abstract, problem framing, methods, central findings and reasoning, limitations, and conclusions. The author selects and synthesizes salient evidence, reconciles disagreement, and explains important failed approaches without dumping the agent transcript.

The paper's claims must be traceable to a specific immutable snapshot of project/session/strategy artifacts. The author may improve exposition, but **must not fabricate experiments, citations, proof steps, external references, agent consensus, or verification**. Distinguish established results, model-generated conjectures, unresolved objections, and limitations. A mathematically plausible argument is not formally verified merely because Investigator and Skeptic agree. If the record cannot support a publishable conclusion, produce an honest exploratory or negative-results paper rather than manufacturing success.

This stage is separate from research execution: **Research → Critical assessment → Paper generation**. Generating a paper must not mutate research outcomes, strategy attribution, or session history. Regeneration uses the then-current snapshot and creates a new durable paper version; prior versions remain available and reproducible as records.

## Investigate and design before coding

Trace existing export API, HTML/LaTeX/PDF compiler, provider integration and authentication, model budgets, project storage, and UI patterns. Read `docs/HUMAN-AI-INTERACTION.md`, `docs/STATUS.md`, A17.5, A17.7.1, and A17.8. Reuse the existing secure bounded LaTeX compilation path where appropriate, but do not mistake a formatted export for an authored paper.

Choose the smallest robust architecture. Define:
- A bounded, explicitly user-triggered generation operation, with selected model/provider, visible progress, cancellation/recovery, costs/call limits where available, and honest error handling (including network/provider failures with toast and coherent UI state).
- **Export/generation waiting feedback:** When the user starts AI paper generation from Export, immediately show an unmistakable in-progress indicator on the Export/Generate action (for example, spinner plus **Generating paper…**), and keep it visible for the full asynchronous generation and PDF-compilation interval. Disable duplicate submissions while pending; do not leave the dialog looking idle or imply that a download is already ready. On success, transition clearly to preview/download availability. On cancellation or failure, remove the busy state, show an actionable error/toast, and allow retry without losing the chosen options. Include an accessible live status and verify the behavior under deliberately delayed mock generation and failure.
- An evidence package built from a **frozen snapshot** with stable source identifiers, including relevant project objective, strategy descriptions, sessions, artifacts, critiques, outcomes, and verification caveats. Define context-window truncation and omission policy; never silently omit evidence that materially contradicts the proposed conclusion.
- A structured paper-draft contract that separates claims and their artifact references from prose. Validate citations against the snapshot and flag unsupported statements, contradictions, and missing obligations. Do not pretend an LLM-only review is independent mathematical verification.
- A reliable rendering path from validated draft to well-typeset LaTeX and real PDF, with safe escaping, mathematical notation, bibliography only when genuine sources exist, bounded compilation, and actionable compiler diagnostics. Avoid executing model-supplied LaTeX as unrestricted code; prefer a controlled document renderer and structured content.
- Durable versioned paper artifacts with snapshot provenance, generation metadata, provider/model, time, validation warnings, and PDF availability. Define behavior for project edits/deletion, regeneration, partial failures, and restart.
- UI entry point, naming and preview/download behavior that **clearly distinguishes** AI-authored paper from deterministic audit/report exports. Avoid clutter or broad UI redesign; use established SIGMA interaction styles. Generation must never be represented as a free deterministic export.

## Scope and quality bar

A20 is a focused publication capability, **not** an expansion of the research agents, an automatic proof checker, a citation-search product, or an academic submission system. Do not introduce external scholarly citations unless an explicit evidence source exists; no fabricated bibliographies. Do not add a separate autonomous research phase or silently launch additional research sessions. Keep provider usage bounded; do not incur new paid API charges without approval.

Use Maximum Regions Formed by Lines as the primary example. The resulting paper should explain both the upper bound and the general-position attainability argument **if those claims are supported by actual saved evidence**; otherwise accurately identify what is missing. Test at least one other project type or research state (for example, unresolved or adversarial findings) to ensure the author does not force all work into a theorem-proof narrative. A fictional military scenario, if used, must be labeled fictional and not dressed up as observed events.

## Verification and acceptance

1. **Authorship:** Human inspection shows a coherent original research narrative, not a field dump or stitched transcript; the structure fits the subject and maturity of the work.
2. **Evidence fidelity:** Every material finding is grounded in stable artifact references; a planted unsupported claim, contradicted result, invented citation, and incomplete proof are detected or clearly qualified. No false independent-verification claim.
3. **Snapshot integrity:** Paper versions link to the exact source snapshot; regenerating after research changes does not overwrite or silently rewrite earlier papers.
4. **Operational behavior:** Progress, cancel, retry, provider timeout/rate limit/connection error, interrupted generation, context limits, compiler unavailability and malformed model output are recoverable and clearly presented; no false success or partial PDF.
5. **PDF quality:** Real compiled PDF, correct math and Unicode where supported, legible typography, safe LaTeX, appropriate sectioning, accurate citations/footnotes and no spurious bibliography. Verify by opening and visually inspecting the actual PDF, not only checking bytes.
6. **Compatibility:** Project Audit and existing deterministic text/HTML/LaTeX reports retain their semantics. Research sessions and strategy assessments are unchanged by paper generation.
7. **Testing:** Run `./sigma test`, targeted persistence/API/provider/validation tests, and real-browser checks with isolated mock provider. Include adversarial paper-draft fixtures. Conduct a bounded real-provider trial only if existing authorization permits; otherwise explicitly mark authored prose quality unverified.
8. **Evidence and judgment:** In `docs/STATUS.md`, record design choices, exact tests, artifacts, screenshots/PDF inspection, real-provider observations, limitations, and an explicit recommendation for human acceptance. Do not declare A20 complete without human review.

**Delivery requirement:** Work on a dedicated A20 feature branch. When implementation and verification are ready, push the branch and **open a pull request targeting `main`**. Include a concise implementation summary, test evidence, sample generated-paper artifacts or screenshots, known limitations, and any unmet acceptance criteria in the PR description. Do not merge the PR yourself; wait for human review and approval.

**Coordination:** A20 owns the authored-paper pipeline and its UI. Avoid conflicting edits to A17.8 or other workstreams. If concurrent changes touch export or session UI, coordinate through small isolated commits/PRs and reconcile on the latest main before merging. Escalate scope, billing, and destructive decisions. Do not quietly broaden the assignment.
