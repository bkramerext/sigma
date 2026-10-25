# T89 stock sample curation: implementation increment 1

## Scope and preservation

Started from `main` at `8562c89` on `gray/t89-stock-sample-curation`, after PR #115 merged; later merged `main` at `950c810` without rewriting history. This increment updates all 17 project introductions, supplies practical first strategies to seven samples with empty/weak entry points, and makes three explicit difficulty judgments. It does not delete or merge samples, change scientific scope, create research outcomes, alter existing saved session evidence, or spend inference credits. Original project IDs and saved research histories remain intact. The earlier Maximum Regions strategy is retained verbatim with provenance in removed-strategy history; its active replacement is a human-authored, timestamped strategy event. Other strategy additions are human-authored, timestamped events through the shared typed project service.

The full inventory and PR #74 evidence remain in [the T89 audit](t89-stock-sample-catalog.md). The summary below records what this implementation actually changed.

## Before and after examples

| Sample | Before | After |
|---|---|---|
| Algorithm design | Opened with a dense specification (“Design an algorithm for a build system…”); no strategies. | Opens with the recognizable build-system problem. Two paths now separate a correctness-first recomputation baseline from a bounded dynamic-order experiment, each with a proof/measurement boundary. |
| Riemann Hypothesis | Opened with a formal prove-or-counterexample instruction before naming the problem's broader significance. | Opens by explaining why the location of zeta zeros matters, then states RH plainly and preserves its open status and strict evidence boundary. Added one bounded implication-chain strategy; existing three routes remain unchanged. RH remains the flagship. |
| Operation Narrow Passage | Opened as an all-caps “MILITARY CRISIS SIMULATION” with a large unstructured decision space and no strategies. | Opens as a fictional crisis scenario about a narrow passage and uncertain escalation. Two starter paths map information gaps and compare bounded options; both label judgments as conditional. |
| Xenopus regeneration | Opened with “FUNDAMENTAL QUESTION” and unexplained stage-specific terminology. | Opens with the accessible observation that tail regrowth changes over development, then preserves the species, stage, prior-art, dataset, and replication constraints. Existing five strategies and the research record are untouched. |
| Constrained binary strings | Had an accurate but terse title/problem and no strategy. | Opens with the familiar “How many binary strings…” question and adds a state-recurrence route with small-case checks and induction. Difficulty remains Easy. |
| Maximum Regions | Its only active strategy stated the exact maximum and supplied a complete proof and attaining arrangement. | The full strategy record, ID, original text, and provider provenance remain in removed history. The active path now asks the visitor to discover an upper bound and a matching construction without stating the answer. |

All 17 intros were reviewed and revised for a human-readable lead while retaining the original question and its scientific constraints: algorithm-design; alternating-zeta-boundary; arrival-sequel; counting-constrained-binary-strings; euler-product-primes; first-principles-catalysis; handshake-count-easy; jesus-cannabis; maximum-regions-by-lines; nonconsecutive-subset-sums; operation-narrow-passage; riemann-hypothesis-research; scientific-investigation; theta-functional-equation; warp-drive-engineering; warp-drive-physics; xenopus-tail-regeneration. Large original method, evidence, and exit criteria remain after the new lead. The highly detailed Arrival and biology prompts remain long; a structural rewrite would need separate editorial review to avoid losing guardrails.

Twelve starting strategies were added across seven projects with no or insufficient entry path: algorithm-design (2), constrained binary strings (1), Operation Narrow Passage (2), RH (1), scientific investigation (2), Warp Drive Engineering (2), and Warp Drive Physics (2). Maximum Regions received one non-spoiling active starter. Its earlier full proof is preserved unchanged, with original strategy ID and OpenAI model provenance, in the sample's removed-strategy history. The test suite verifies both the archival record and the active starter.

## Difficulty and domain review

| Sample | Effective domain | Difficulty decision |
|---|---|---|
| Algorithm design | Computer Science | Medium retained |
| Alternating zeta boundary | Mathematics | Hard retained |
| Arrival sequel | Other | Hard retained; “Other” reflects the current domain enum, which has no literary/creative category |
| Constrained binary strings | Mathematics | Easy retained |
| Euler product | Mathematics | Medium retained |
| First-principles catalysis | Chemistry | Hard retained |
| Handshake count | Mathematics | Easy retained |
| Jesus/cannabis | Religion | Unset; editorial rating needs review because the sample mixes historical, textual, and scientific evidence questions |
| Maximum regions | Mathematics | Easy retained |
| Nonconsecutive subset sums | Mathematics | Set to Hard: its general equidistribution target has substantial proof obligations beyond the finite fixture |
| Operation Narrow Passage | Military | Set to Hard: the scenario requires multi-actor uncertainty and conditional strategic analysis |
| Riemann Hypothesis | Mathematics | Hard retained |
| Scientific investigation | Physics | Medium retained |
| Theta functional equation | Mathematics | Hard retained |
| Warp drive feasibility | Engineering | Set to Hard: it spans theoretical constraints, system feasibility, and currently speculative requirements |
| Warp drive design | Physics | Hard retained |
| Xenopus regeneration | Biology | Hard retained |

No domain change was warranted. Arrival remains `Other` because the supported catalog taxonomy has no creative-writing category. The two warp-drive samples remain separate pending a product decision about whether a physics-to-engineering pathway is more useful than two projects. Jesus/cannabis stays unrated for review rather than receiving a guessed label.

## Recommended newcomer presentation

Lead with a small “choose a kind of investigation” set rather than presenting all 17 as equivalent:

1. **A quick mathematical foothold:** Handshake Count (Easy) or Constrained Binary Strings (Easy), with concrete counting/recurrence starters.
2. **A compact proof challenge:** Maximum Regions (Easy) offers a memorable geometric question and can teach upper bounds plus constructions; its eventual stock history should be genuine and carefully sourced.
3. **A decision under uncertainty:** Operation Narrow Passage (Hard) offers a narrative scenario and bounded analysis paths. Mark the scenario clearly as fictional.
4. **The flagship open problem:** Riemann Hypothesis (Hard), with an explicit “still open” framing and honest bounded routes.

Keep the broader catalog discoverable by domain and difficulty. Surface Xenopus, catalysis, alternating zeta, and warp-drive investigations as advanced choices with their evidence and scope prerequisites visible. Keep the five subset-sum sessions labeled deterministic fixtures in every presentation; do not market them as provider research.

## Authentic stock-session roadmap (proposal only)

No live session is included in this increment. Request a separately approved budget and provider hard cap before making any paid call. Proposed order:

1. **Maximum Regions:** one authentic session attempting a proof through upper bound and construction, with an adversarial counterexample pass. Candidate historical evaluator export from PR #74 can be assessed for provenance, but must remain supplemental until its complete source and authorship chain are verified; do not import it as stock history by assumption.
2. **Operation Narrow Passage:** one authentic session comparing a small set of conditional options against the fictional scenario. Preserve assumptions, uncertainty, and any unsupported prediction; do not present simulated consequences as historical fact.
3. **Riemann Hypothesis:** one bounded session on a single lemma or implication. A legitimate dead end or unresolved obligation is a valuable result. No claim that RH is solved or that numerical checks prove it.

For every imported session preserve the raw transcript, provider/model/mode, timestamps, exact token/cost metadata, citations, generated evidence/artifacts and their hashes, session identity, source project identity, and the unmodified original history. Append the stock session as a separately provenance-labeled record; never edit or replace earlier project events. Keep deterministic subset-sum fixtures explicitly tagged as fixtures. Before import, check that the product’s session evidence format can retain all of this metadata without lossy conversion.

### Illustrative bounded cost envelope

Planning estimate only, not authorization: 6 Maximum Regions calls, 8 Narrow Passage calls, and 8 RH calls (22 total), each budgeted at up to 20,000 input and 4,000 output tokens using gpt-6.1-sol published rates of $2/M input and $10/M output. That models 440,000 input tokens ($0.88) plus 88,000 output tokens ($0.88), or **$1.76 estimated**. Seek a separate **$2.50 hard spend cap** before any provider work, with actual call/token limits and a stop rule. The model is only an estimate: retries, context growth, caching, and provider accounting can change cost, and no call was made in this increment. Rates: [OpenAI API pricing](https://developers.openai.com/api/docs/pricing).

## Acceptance matrix

| Requirement | Result | Evidence / limits |
|---|---|---|
| Polish human-facing introductions across all 17 | PASS | All 17 canonical prompts have a new conversational lead; original detailed constraints remain. |
| Improve safe starting strategies and avoid giving away the flagship discovery | PASS | Added 12 bounded strategies across seven projects; replaced Maximum Regions’ active spoiler with a bounded discovery path while preserving the complete original strategy, identity, provenance, and removal event in history. |
| Verify difficulty/domain | PASS with review item | Three ratings set to Hard. Remaining current ratings retained; Jesus/cannabis remains unset and Arrival remains Other pending taxonomy/editorial review. |
| Identify first collection and newcomer presentation | PASS | Four-entry pathway above; broader samples remain discoverable. |
| Plan authentic sessions, costs, provenance | PASS, proposal only | Three priority projects, immutable provenance policy, modeled $1.76 / requested $2.50 hard cap; no paid calls. |
| Preserve identities/history/copy compatibility | PASS | Project IDs stable; strategy additions/removal use typed events; the original Maximum Regions strategy remains archived exactly. Source/copy/export checks requested below. Existing session evidence was not edited. |
| Avoid UI, deployment, and benchmark ownership areas | PASS | No such files changed. |
| Focused sample and real-browser checks | PASS | `tests/recents.py`, `tests/test_sample_copies.py` (9 tests), `tests/make_sample.py`, `tests/example_math.py`, and `tests/agentic.py` passed. Real Chrome recents/copy/strategy/source-immutability check passed on isolated ports with fixture auth. |
| Full `./sigma test` | FAIL (existing tooling assertion) | The suite stops at unchanged `tests/tooling.py:177`: mocked `stop_servers` is called zero times where the test expects one. Every later suite command was run individually in isolated state and passed. |
| Authentic provider sessions | BLOCKED pending separate budget approval | No paid calls were made. Proposed cap and provenance controls are recorded above. |
