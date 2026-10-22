# A15: Make Generate Strategy work end to end

**Status:** Ready for Codex implementation. **Priority:** Complete the existing Generate Strategy workflow; do not invent a new agent architecture.

**Assignment history:** The former A15 specification for Plain/Markdown/Rendered text views is preserved verbatim in `docs/assignments/asn15-text-representations-original.md`. This A15 supersedes that assignment number for the next development task. A14.2 covers the separate Markdown conversion regression; do not absorb that work here.

## Objective

Deliver a functional, reliable **Generate Strategy** workflow, from clicking **Generate with AI** to a reviewable, editable **unsaved** proposal and an explicitly saved persistent strategy. A14 already defines the intended multi-agent behavior in `docs/assignments/asn14.md`; treat that document as the product/agentic contract. **A15 is implementation completion, integration, diagnosis and verification**, not a speculative redesign or a new Generate Scenario feature.

Read the current implementation, tests, `docs/HUMAN-AI-INTERACTION.md`, `docs/agent-output-design.md`, and `docs/STATUS.md` before editing. Start by identifying what is already implemented and the first concrete failure along the actual path. Fix defects in place and avoid duplicate frameworks.

## Required functional path

1. From an open mathematical investigation, **New Strategy → Generate with AI** opens the existing dialog. Accept an optional starting point, but work with an empty one. Respect the selected model, thinking effort, connected identity and billing mode. Do not change settings implicitly.
2. Load the current authoritative research problem and **all** existing and previously attempted strategy mechanisms, including removed/abandoned entries as available. Preserve original mathematical notation, source content, and source revision/binding checks. Handle too-large context honestly, never silently drop prior strategies.
3. Run real bounded agent activity: **Explore** proposes a concrete mechanism; a **separate invocation** independently **Challenges** its relevance, assumptions, proof obligations, possible counterexamples and substantive overlap; the coordinator then **Decides** to present, revise, try a distinct direction or stop. Branches must be driven by actual review results, not pre-scripted stages. Retain A14's ceilings of **6 model calls** and **2 candidate attempts**, finite deadlines, explicit cancellation and no automatic provider retries or billing fallback.
4. Stream **actual, typed, ordered progress events** into the existing dark-navy/copper dialog. Report only work that started/completed, with a truthful current activity and compact completed ledger. Handle malformed, missing or interrupted terminal events as failures. No fake percentages, fabricated research/testing, or exposure of hidden reasoning.
5. On viable completion, populate the **existing editable strategy draft** (title, summary, approach, concrete first tests/obligations/failure modes as appropriate) and public review summary. Nothing is added to the investigation until the user explicitly chooses **Save strategy**. Reject/cancel/close leaves the pool unchanged. Saving must preserve signed receipt/provenance and project identity/history; reopening shows the saved strategy.
6. A second generation after a saved strategy must compare the **underlying mathematical mechanism** against previous approaches. Cosmetic rewording is not sufficient. When the bounded search finds no defensible distinct proposal, display a truthful no-viable-proposal outcome rather than manufacturing success.
7. On provider rejection (including a ChatGPT-plan HTTP 200 error envelope), authentication/account/model change, timeout, network failure, malformed output, concurrent run or cancellation, restore a usable dialog, preserve the user's starting point and investigation data, release run gates, and allow an **explicit** retry. Use the existing **single dismissible request-failure toast** plus appropriate inline UI state; do not show success or switch to an empty/irrelevant view. Do not expose credentials, raw provider payloads or sensitive source text in diagnostics.

## First acceptance scenario

Use the committed stock fixture `examples/counting-constrained-binary-strings/project.json` (zero strategies). Do not alter the canonical fixture.

- Open a managed copy. Verify zero strategies and the original research problem.
- Trigger Generate with AI with **no starting point**. Observe real Explore → Challenge → conditional Decision activity and a complete unsaved, editable draft. The content must have a concrete mathematical mechanism and falsifiable or provable obligations.
- Cancel/reject once and confirm zero saved strategies. Repeat, then explicitly save a valid draft; verify **exactly one** strategy with correct attribution, persisted on reopening.
- Trigger generation again and verify that the reviewer considers the saved strategy and rejects merely renamed versions of its mechanism. A legitimately different strategy or a justified no-viable-proposal result is acceptable.
- Verify cancellation during an in-flight stage and a simulated provider failure do not alter the strategy pool, original research problem or user settings.

Use A14's test-only oracle `n=0,1,2,5,10 → 1,2,3,13,144` for checking proposed examples. Do not feed a preselected solution into the generation prompt.

## Test requirements

Add or repair deterministic **mock-provider, no-paid-call** backend and API tests for: distinct accepted candidate, duplicate rejected then retry, targeted revision, exhausted candidates, malformed/refused output, provider rejection including HTTP 200 error-object, truncated/invalid progress stream, timeout, cancellation/disconnect, changed identity/model/billing mode, concurrent run gate, source revision conflict, receipt integrity and save/reopen.

Exercise the **real frontend path** in browser tests: entry from New Strategy, optional starting point, chronological progress, reduced motion, cancel/close, error toast and recovery, completed editable draft, explicit save, and persistence after reopen. Test the zero-strategy fixture and a nonempty strategy pool. Do not use mocked UI timers to imply real backend progress.

Run `./sigma test`, the frontend build/typecheck and applicable browser tests; record exact commands, pass/fail counts and limitations in `docs/STATUS.md`. Do not claim a successful live-model run unless it was actually performed. A manual live-provider smoke test, if available and explicitly authorized, should use the current account/billing selection with no hidden fallback.

## Delivery and boundaries

- Preserve approved artwork, Home layout, investigation workspace design and text-view behavior. Do not change A14.2 Markdown conversion or the broader A14.1 Project → Investigation migration except for integration fixes needed by Generate Strategy.
- No new Scenario generator, autonomous experiment execution, proof claims, broad architecture rewrite, provider switch or extra product features.
- Commit and push **directly to `main`**, no pull request. Report the commit SHA, observed root cause(s), tests actually run and any remaining blockers.

**Definition of done:** A user can generate a genuinely reviewed strategy through real agent calls, see truthful progress, edit the result, explicitly save it, reopen it, and repeat with meaningful overlap checking; errors/cancellation preserve all prior research and recover cleanly.
