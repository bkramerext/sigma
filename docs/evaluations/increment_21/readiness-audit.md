# Increment 21: matched-budget evaluation readiness audit

**Audit date:** 2026-10-25  
**Base:** `690fff6d42476bf4ef81befd3104883bc5d0edcd` (current `main`, including T118/PR #123)  
**Scope:** T114/118 research-comparison readiness, not a scored trial.  
**Provider calls / spend:** 0 / $0.

## Finding

The written T114 Revision 2 design is a useful, bounded comparison protocol, but its own state is **proposed, not frozen, not executed, and not authorized for paid inference**. The offline scripts verify reproducible packet construction, normalization, record limits, and task-cluster summaries. They do not make the live comparison run-ready: there is no demonstrated model-input isolation, matched arm adapter, authorized model/configuration, independent curator, key custodian, or independent graders.

The design compares two Investigator/Skeptic cycles (up to four calls) against one persistent single-role conversation instructed to self-criticize and revise (up to four calls), with the same selected model, packet, tools, output contract, and stated per-arm ceilings. It covers **36 pairs / 72 arm records**, but the independent unit remains **six task families**. It can only inform a bounded within-session decision; it says nothing about cross-session persistence (#119).

## Requirement audit

| Requirement | What is specified and implemented | Finding before any freeze/run |
|---|---|---|
| Independent task selection and contamination | `tasks.json` has six fixed synthetic tasks. `manifest()` includes all six and randomizes pair order, A/B assignment, and execution order with a seed. `agent_packet.py` uses a positive allowlist. | **Not confirmed independent.** The JSON's “independently authored” string is not provenance. M1 is a recognizable Petersen-graph counterexample and M2 a standard Hall-condition obstruction; the task set and evaluator references are public in the repository. No independent curator has documented authorship/model-family provenance, recognizability, contamination risk, ambiguity, variant validity, or retain/replace decisions. The random seed randomizes arms and run order, not task selection. Keep all tasks high-risk until that review; replace or exclude contaminated items before freezing, never after outcomes. |
| Blinding and execution schedule | Shared six-field normalizer, role-word substitution, anonymous scorer IDs, arm guesses/confidence, and no arm metadata in `scorer_packet()`. The manifest records randomized arm assignment and proposed run order. | **Structural only.** Normalization removes a small list of literal identity terms; it cannot erase style or less direct cues. The scripts do not provision separate model/scorer workspaces, custody the arm map, randomize artifact order independently per real grader, or establish independent graders. The record auditor checks a submitted `schedule_position` against planned order, but without a live runner or trusted dispatch log this is only a record assertion, not proof of actual execution order. An allowlist function is not a process/filesystem/network isolation boundary. |
| Strong single-role baseline | The spec gives one persistent conversation up to four calls, explicit self-critique/revision, same final contract, and no other arm's outputs. | **Specified, not executable or verified.** There is no baseline run adapter or frozen baseline prompt test. The normalizer accepts a JSON object but does not prove it received four-turn self-review, the intended prior-turn context, or the same task/tool controls. A one-pass or differently configured baseline could be unfairly weak; do not score until the actual adapter and prompt are reviewed. |
| Matched resources | Proposed caps are 4 calls, 48k input / 16k output / 64k total tokens, one local tool call, 600 seconds and $0.55 per arm; current design totals $39.60 across 72 arms. Audit checks per-record provider/model label, token usage, calls, tools, time and cost against declared caps. | **Bounds are matched on paper; enforcement is not demonstrated.** Draft model/provider are null. The manifest does not freeze sampling/reasoning parameters or API mode, and the record validator cannot establish actual provider billing, request settings, tool permissions/use, or equal effective opportunities. No current price check or enforceable spend cap is attached. The shakedown's $1.25 total cap is a proposal, not authorization. |
| Output contract and truncation | Six normalized fields have the same final character limits; clipping is visible. T114 requires a pre-run max-boundary probe and preservation of upstream truncation. | **Offline transformation only.** No test traverses both actual request formats, provider responses, SIGMA parsing/saving, and normalized output. The current production schema has smaller field limits in places; the shakedown is unapproved. Upstream clipping remains a reported incomplete outcome and must never be selectively dropped. |
| Analysis and claims | Paired differences are summarized over six task-cluster means, with exploratory t interval and sign-flip sensitivity; both graders and key-pass endpoint are retained. | **Appropriately cautious if reported as specified.** Repeats and evidence variants do not increase independent `n=6`; intervals are fragile and not confirmatory. Blinding failures, critical integrity failures, invalid pairs, costs, adverse cases and task-level effects must remain visible. No general multi-agent superiority or persistence claim follows. |
| Empirical evidence | One historical live four-call SIGMA session is archived; prior causal-control runs used scripted provider responses. Offline dry-run makes 72 synthetic records. | **No comparison result.** The retrospective records no matched single-role baseline, a historical aggregate token count defect, incomplete exact inputs/truncated fields, and zero new calls. Synthetic/scripted orchestration evidence only establishes software wiring, not research effectiveness. |

### Task-set review

The checked-in agent packets contain no key/rubric field, and the positive
allowlist emits only instruction, question, and the selected evidence. That is
a useful data-shaping control, but the reference answers are publicly present
in `docs/evaluations/increment14/evaluator_only.md` and protocol tests. The
independent curator must therefore review likely training/public exposure and
must not treat repository placement as secrecy.

| Task | Packet-level validity and material risk |
|---|---|
| E1, sensor/firmware drift | The six observations are deliberately too small and confounded for a causal estimate; matched room/temperature cells support only a cautious descriptive contrast. The task supports a falsifiable randomized crossover proposal, but favors a caution answer and has no independent noise/calibrator data. |
| S1, synthetic policy notice | The signed primary notice supports what the notice says (July 1), while the secondary summary conflicts. This does not prove real-world enforcement. A curator should check that the rubric accepts that scope and does not treat a synthetic document's authority as external truth. |
| C1, duplicate external charge | The trace makes the lost-ack/retry failure concrete; DB uniqueness alone cannot guarantee exactly-once external effects absent endpoint idempotency/reconciliation. This is a familiar reliability pattern and may have ceiling/familiarity effects. |
| P1, two-site distribution | The supplied capacities and unknown route/handling times require conditional feasibility. With one vehicle lost and no replacement, full 110-unit delivery cannot be guaranteed; a proposed route must not assert unknown A-to-B or handling time. This item previously needed a grading correction and merits curator recheck. |
| M1, minimum-degree graph claim | The provided graph is the Petersen graph, a standard girth-five counterexample. Offline code checks degree three and absence of 3/4-cycles; this validates the fixture, not model reasoning. High recognizability and training contamination risk. |
| M2, machine assignment lemma | The supplied compatibility sets directly exhibit the standard Hall-condition obstruction (`T1,T2,T3` have only `{A,B}`). High recognizability and likely ceiling risk. |

The present/withheld packets are paired within each arm and share the same
question, but their text and evidence differ by design. A curator must confirm
each pair changes only its intended evidence and that withheld packets do not
hint at a key. The task IDs and variants are not independently selected by the
program; only arm assignments and execution order are randomized.

### Native-to-common output projection risk

The current normalizer does not yet demonstrate an information-equivalent
projection. `_from_sigma()` maps `evidence` only from
`investigator_output.evidence_status`, which is capped at 500 characters in the
production `Investigator` schema, while the baseline's common `evidence` field
allows 2,000. It does not include the Investigator's
`computational_citations` or the Skeptic's `computation_feedback`; a citations
name in the truncation-field lookup does not make those values appear in the
normalized output. It also omits structured Investigator reasoning steps,
Skeptic reasoning assessments, and the structured assumptions/reviews fields.
When a Skeptic response is present, the current `or`
selection drops its separate objections list; when Skeptic remaining
obligations are present, it drops Investigator open obligations. This can hide
SIGMA evidence/obligations from scorers while a baseline can place them in its
free-form fields. The reverse advantage is also possible where combining two
role fields gives SIGMA more source text before the common cap.

The current production schema limits also differ from the preregistration's
historical 2,000/2,500 description: `Investigator.claim`/`method` allow 3,000 /
6,000 characters and `Skeptic.solution_claim`/`argument_summary`/`response`
allow 2,000 / 4,000 / 6,000. The common result transformation is only tested
with short hand-built examples, not full real session records or a frozen
baseline prompt. Before freeze, owners need a mapping/assessment that preserves
the same task-relevant content and provenance within identical final limits,
plus boundary checks against current actual schemas. I left this mapping
unchanged because selecting an evaluator-visible projection changes the
scoring contract; current readiness therefore remains blocked.

## Harness audit and narrow correction

The offline 72-record path passed, but a direct adversarial probe found that the generic record auditor accepted six complete task clusters with only one pair each. T114 requires the full 36-cell matrix (six tasks × two evidence variants × three repeats); accepting an undersized manifest could silently turn a draft subset into a seemingly complete report.

The default version-3 audit recomputes the canonical design and requires the complete task/variant/repeat matrix, A/B map and planned order, task/packet/protocol/agent-packet/auditor/evaluator-key/scoring-schema hashes, analysis unit, and fixed protocol ceilings before checking records. Each record must carry a `schedule_position` that matches its pair and arm in the planned order. The one-pair unit fixture must opt into `allow_partial_fixture=True`; the 23 mutation controls in the offline dry-run reject older schema, removed/changed cells and positions, altered seed, changed caps/hashes, and existing pairing/usage/provenance failures. This closes the demonstrated incomplete-manifest path and verifies submitted schedule-position records. It does **not** authenticate those positions against actual dispatch, authenticate approval, sign a manifest, verify transcript bytes from their hashes, control a live provider, or prove isolation; those remain explicit live gates.

The schedule probe reverses the record list while preserving each record's
position (which correctly passes because list order is not execution chronology)
and separately changes a record's position (which is rejected). The zero-cost
result is preserved in
[`evidence/execution-order-probe.txt`](evidence/execution-order-probe.txt).

## Reproducible verification

From repository root on this base, all commands below are offline and make no provider/network calls:

- `uv run --locked python tests/increment14_protocol.py` — PASS.
- `uv run --locked python tests/increment14_audit.py` — PASS.
- `uv run --locked python scripts/increment15_offline_pairs.py --output docs/evaluations/increment_21/evidence/offline-pairs.json` — PASS, 72 synthetic records / 36 pairs / zero calls or spend; 19 unsafe mutations rejected.
- `uv run --locked python scripts/increment15_readiness.py --output docs/evaluations/increment_21/evidence/readiness.json` — PASS as a readiness check; result `BLOCKED_FOR_LIVE_PILOT`, 0 calls, and all live gates false.
- `uv run --locked python scripts/increment15_retrospective.py --output docs/evaluations/increment_21/evidence/retrospective.json` — PASS; comparison not established.
- `./sigma test` — PASS after `npm --prefix frontend ci` installed the locked frontend toolchain. Includes these checks, Ruff/format, Pyright (0 diagnostics), frontend typecheck and production build.
- `git diff --check` — PASS.

Machine outputs and SHA-256 hashes for the audited scripts/tests are in `evidence/`. These validate offline behavior only. No live shakedown, scored run, cloud action, or real-browser workflow was needed or performed.

No SIGMA project or session was exercised for this harness-only audit. The
explicit export omission and its reason are recorded in
[`exports/manifest.json`](exports/manifest.json); no prior-increment export or
synthetic fixture was represented as newly exercised project data.

The readiness script computes the draft pair count and packet hashes but sets
its live-adapter, isolation, grader, and cost-enforcement fields to false in
code; those fields are not dynamically proved by its own run. Treat it as an
explicit blocker snapshot, not a self-certifying readiness approval. The
proposed $39.60 full-study total and separate $1.25 shakedown cap are draft
ceilings only.

The offline plan also does not establish independent random task selection:
all six task IDs are fixed in the checked-in catalog. A human curator's
independence and contamination review is still required before deciding to
retain or replace them. The harness randomizes scheduling from a seed; it does
not choose tasks independently.

## Remaining decision and gates

The coordinator retains the decision whether and when to authorize a provider experiment. Until then, this is an **offline readiness result**, not a frozen/approved run and not a negative or positive empirical finding. Before any run: independent curator provenance/contamination review and any replacements; sealed key custody; independent grader recruitment and blinded packet/order review; signed immutable manifest; frozen exact prompt, API mode, model revision and sampling settings; verified same-model/resource/tool policies; live-adapter and process-isolation tests; provider usage/cost capture; current pricing and hard enforcement; and separate explicit authorization. Do not interpret a passing full test suite or synthetic report as research effectiveness.
