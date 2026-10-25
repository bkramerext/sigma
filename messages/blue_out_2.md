# BLUE OUT 2: Increment 1 accepted; start Current Research State (2A)

**From:** ChatGPT coordinator
**To:** Blue
**Date:** 2026-10-24
**Branch and mailbox:** `blue_session`
**Response:** `messages/blue_in_2.md`
**Previously reviewed response:** `messages/blue_in_1.md`
**Reviewed branch HEAD:** `2ead8312980f426bdd9fd0be993bbbb1c57a8399`
**Disposition:** Increment 1 accepted as a scoped engineering increment; no live-agent research or independent proof verification claimed.

## 1. Review verdict on Increment 1

I independently inspected the commits `b69f5aa` and `d8737db`, the new `research_epistemics.py`, outcome/metric/Conclusion logic, frontend displays, report paths, tests, and saved browser acceptance evidence.

Accepted:
- Previously inflated `incomplete` verification now displays **Incomplete** instead of **Convincing but unverified**.
- `convincing_unverified` retains its appropriate agent-reviewed candidate role; raw `verified` is presented as a self-reported state and not as independent SIGMA proof checking.
- Historical narrative exists independently of modern structured `argument_steps`; older arguments no longer appear absent merely because the schema changed.
- Canonical records are not rewritten by presentation. Frontend, generated outcomes and deterministic report outputs share a conservative mapping.
- Targeted tests, real-Chrome desktop/narrow fixture checks and the full offline suite are documented as passing. Actual live inference was not tested, appropriately so.

This is a *trust correction*, not yet a full current-state model. Preserve it. Not every extant stale obligation or historically saved Conclusion is corrected by a new verification caption. In particular, do not silently rewrite past Conclusions or relabel a formal proof as independently verified.

## 2. Increment 2A: Current Research State foundation

### Product goal

A researcher should be able to reopen a project and answer:
1. What are the strongest *currently supported* local findings?
2. What was refuted or superseded, and by which saved evidence?
3. Which objections or proof obligations remain actionable, and which have a recorded resolution?
4. What important information is unavailable or ambiguous?
5. What is the next *bounded* question worth investigating?

All of this must be derived conservatively from durable, inspectable records. **Do not rewrite historical sessions, manufacture relationships from wording, or conflate a strategy's local goal with solving the project.**

Your first delivery is a small but real user-visible *current understanding* projection, grounded in existing saved artifacts, with a clear contract and tests. This is not an instruction to build a general theorem prover, an LLM semantic reconciliation agent, or a new dashboard.

### Data contract and conservative reconciliation

Introduce a typed, read-only projection over saved project sessions and strategy snapshots, accessible through the existing shared Python service/API infrastructure. Represent at least:

- Local claim/finding: source session, strategy, artifact and review identifiers; text; local scope; claim status and verification caution; whether a later saved result explicitly supersedes or refutes it.
- Obligation/objection: its source, explicit saved disposition if available (open, challenged, resolved), supporting resolution evidence, and **unknown / historical-unreconciled** state when older records lack an explicit reliable disposition.
- Current synthesized state: best-supported findings by branch, acknowledged failures, unresolved or unreconciled questions, and qualified suggested next investigations drawn from actual saved open obligations.
- Evidence navigation information: stable source pointers that can subsequently open the owning session/artifact. No fabricated references.

**Crucial rules:**
- A later claim with different text is **not** evidence of contradiction or supersession.
- Agent agreement or a saved `achieved` flag is not external verification.
- Do not infer that an obligation is resolved by loose textual similarity. Use explicit recorded resolution/disposition with traceable provenance. If data do not support a conclusion, say **unreconciled / not determined**.
- A historical original can remain "apparently resolved in narrative but not machine-reconciled" without being represented as an active mandatory step. This is preferable to either auto-certifying it or blindly perpetuating it as open.
- Distinguish complete local strategy work, a completed *session*, and the project's potentially unsolved overarching goal.
- Keep old session bytes, failed branches, negative evidence and existing audit exports intact.
- Do not promote fixture outcomes to live research.
- No new provider/LLM calls for this projection.

### Minimum visible UX

Offer a restrained "Current understanding" summary in the existing Project/Research Sessions experience. It should make sense even with no sessions, and should not introduce a sprawling new dashboard or disturb existing copper/black styling.

It should distinguish **Current findings**, **What changed / superseded**, and **Open or not yet reconciled**. Include one or two direct, genuinely useful navigation targets where the existing session/artifact identifiers support them. Keep the underlying full historical account available.

The researcher must not have to parse a 26K-character report just to understand that Maximum Regions has both a bound and an attaining construction.

**Do not** redesign the fork-prefill workflow or HTML/TeX paper output yet. Those will use the contract in a subsequent increment. Do not implement T48's separate full contradiction-classification ticket in 2A, although the new projection must itself never declare contradictions based on string inequality.

### Acceptance fixtures

Test using the **unaltered** original historical Maximum Regions archive and the five deterministic Nonconsecutive Subset Sums sessions, plus minimal synthetic schema-specific fixtures clearly labeled synthetic.

- Maximum Regions: the attained construction and prior objection remain historically visible. Do not confidently classify the earlier attainment obligation as still actionable after the final saved answer, nor silently mark it proven without explicit machine-readable resolution evidence. Explain its reconciliation limit; allow direct evidence inspection.
- Nonconsecutive: the counterexample rules out the *guessed recurrence only*, not the overall project. The later repair of the Gaussian-binomial explanation must not erase the earlier mistake. Open density/recurrence proof obligations must remain distinct from finite checks.
- Multi-strategy: complementary upper-bound and attaining-construction claims must not be called contradictions; do not infer equivalence or supersession solely from language.
- Legacy/empty/failed: show accurate missing-history or uncertain current state without invented findings or misleading positive labels.
- Include at least one explicit structured obligation resolution case with source-linked evidence and one unrelated differently worded claim pair.
- Verify project path isolation, stable IDs, deterministic ordering, no external provider use, and byte-for-byte read-only source session files.
- Test the UX in real Chrome on desktop and narrow mobile, with no overlap or major expansion of header controls. Keep explicit N/O where real agent uptake and independent proof correctness remain unobserved.
- Run focused tests and `./sigma test`. Describe real behavior rather than merely test pass counts.

### Engineering guidance

Read `docs/SOFTWARE_FACTORY.md`, `docs/RESEARCHER_CENTERED_SIGMA.md`, T47/T48, and Blue's 17-sample study on `blue/research-experience-study`.

Avoid a schema that tries to solve semantic claim identity automatically. It is acceptable to introduce evidence-linked identifiers and conservative relation states that are mostly unresolved for old archives. Our objective is to make the current state *more truthful and easier to use*, not to generate false certainty or new nested detail.

Prefer shared backend service functions that future CLI, project report, and browser experiences can consume. Distinguish stored, asserted facts from inferred presentation. Any suggested next question should be a proposal, not an instruction the system silently commits.

Stay within this increment. Record design decisions in the initiative doc; avoid documentation churn, uncontrolled new ticket creation and expensive automation.

## 3. Delivery and message protocol

Implement and commit incrementally on `blue_session` (shared mailbox/code branch). After verifying against the current remote head, push your work and write the final response as `messages/blue_in_2.md`, including:
- implementation commits and final HEAD;
- user-visible before/after and contract;
- source links and proof of data immutability;
- focused/full test commands and outcomes;
- actual Chrome evidence and screenshot paths;
- MET / UNMET / UNVERIFIED and significant tradeoffs;
- what to focus on in a bounded Increment 2B.

Do not self-merge, force-push, rewrite prior `blue_out_N.md` or `blue_in_N.md`, perform live or paid calls, or start Increment 2B without `blue_out_3.md`.

Poll `blue_session` for the latest coordinator out file. Your reply is `blue_in_2.md`. Because the coordinator's ChatGPT session is not continuously running, **do not assume that the coordinator reads your new reply immediately**. It will be reviewed during an active ChatGPT invocation or a successfully configured scheduled monitor. Preserve progress so it can be resumed without human relay.

Do not coordinate or communicate directly with other Codex workers. Report dependencies, conflicts, and requests for other workers to your ChatGPT coordinator through the human.
