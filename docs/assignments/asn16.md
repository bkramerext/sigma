# A16: Agentic Generate Strategy

**Status:** Planned, deferred until A15's basic Generate Strategy path is validated.

## Goal

Extend SIGMA's working Generate Strategy experience into a **bounded, genuine multi-agent research workflow**. The user can generate a candidate, subject it to independent skeptical review, conditionally revise or try a different mechanism, and inspect the resulting **editable, unsaved** draft before explicitly saving it.

This assignment owns the *heavy* agentic scope previously described in `docs/assignments/asn14.md` and in the first version of `docs/assignments/asn15.md`. The detailed A14 design remains reference material; A15 is now the narrower **single-request baseline**. Some agentic implementation may already exist: inspect and reuse it; do not rebuild it for the sake of assignment numbering.

## Scope

1. **Explore:** A role-specific LLM invocation develops a concrete strategy mechanism from the authoritative investigation problem, optional user guidance, and the complete known strategy corpus, including prior/removed attempts where available.
2. **Challenge:** A **separate, fresh LLM invocation** critically examines relevance, mathematical assumptions, proof obligations, counterexamples, and substantive overlap with earlier strategies. Same underlying model is acceptable; invocations and roles must genuinely be separate.
3. **Decide:** Python coordinator interprets the actual critique and chooses **present, revise, retry with a different mechanism, or stop**. No scripted/fake agent stages. Limit to **6 model calls** and **2 candidate attempts**, with bounded time and output.
4. **Progress:** Existing navy/copper Generate Strategy dialog displays real, ordered, typed events for work that actually ran. Show one current action, a concise completed ledger, truthful failure/limit states, accessible reduced-motion behavior, and real cancellation. Do not expose private chain-of-thought.
5. **Quality:** Each candidate states a concrete mechanism, assumptions, obligations, useful tests and failure modes. Distinguish established facts from conjectures and model suggestions. A cosmetic rephrasing of an existing strategy is not an appreciably distinct approach. No fabricated proof, experiment or literature search.
6. **Human authority:** Return an editable **unsaved** strategy and public review summary, or an honest no-viable-proposal result. Persist only on explicit **Save strategy**. Preserve history, provenance, receipts, account/model/thinking binding and source revision safeguards.
7. **Resilience:** Handle malformed provider output, provider rejection (including HTTP 200 error envelopes), invalid/missing terminal progress events, timeout, cancellation, disconnect, concurrent runs, and identity changes without corrupting investigation data. Reuse the existing request-error toast and maintain a recoverable UI; no silent billing fallback, implicit model switch or automatic retries.

## Acceptance and tests

Use the existing sample fixture `samples/counting-constrained-binary-strings/project.json`, starting with zero strategies. Verify a real Explore → Challenge → Decide path produces a reviewable unsaved draft; cancel leaves zero strategies; explicit save produces one persistent strategy. Run again with that strategy present and verify mechanism-aware overlap checking and an acceptable distinct proposal **or** justified no-viable-proposal outcome.

Add deterministic mocked-provider backend/API tests for distinct proposal, overlap/retry, targeted revision, exhausted budget, malformed/refused output, cancellation/disconnect, account/model change, timeout and receipt integrity. Add browser tests for truthful progress, reduced motion, cancel, error recovery, editable result, save and reopen. No paid API calls in automated tests. Run `./sigma test`, frontend build/typecheck and relevant browser checks, and report actual results and limitations in `docs/STATUS.md`.

## Dependencies and boundaries

- **A15:** A functioning basic Generate Strategy path, with reliable request, validation, draft, explicit save, persistence and failure recovery.
- **A14:** Existing detailed agentic design and prior implementation; treat it as historical/specification context, not a separate mandate to add more complexity to A15.
- **A14.2:** Markdown conversion is a separate feature.

No new Generate Scenario feature, autonomous proof execution, new agent framework without demonstrated need, approved-artwork changes, Home redesign or unrelated migration.

**Delivery:** When A16 is authorized, commit directly to `main` without a PR; report SHA, actual tests and remaining limitations.
