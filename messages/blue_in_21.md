# BLUE IN 21 — Increment 21 evaluation readiness handoff

**Assignment:** Round 2, Increment 21; offline audit of the T114/#118 matched-budget comparison.  
**Implementation branch:** `blue/increment-21-evaluation-readiness`.  
**Implementation commit:** `026ffae47e0c110e9176b0adee2ec0591c6979b0`.  
**PR:** [#145](https://github.com/bkramerext/sigma/pull/145), open, unmerged, ready for review.  
**Elapsed work time:** approximately 20 minutes, about 19:36–19:56 UTC. This was shorter than the requested ~45 minutes because the assigned work was a bounded harness/protocol audit and the live study is expressly not authorized. The additional time was spent on concrete manifest/schedule audit gaps and validity review; no provider experiment was started to fill the interval.

## Win

- Audited the T114 Revision 2 protocol, merged T118 harness, six task packets and answer references, packet allowlist, blinding normalizer, record auditor, offline pair generator, readiness and retrospective evidence.
- Closed the demonstrated incomplete-manifest hole: ordinary full-run audits now reconstruct the version-2 six-task × two-evidence-variant × three-repeat design and compare source/code hashes, assignment/order and fixed ceilings. A six-pair subset can no longer pass as a full run.
- Added per-record `schedule_position` validation against the randomized schedule. Twenty offline manifest/record mutations are rejected. This checks the schedule declared in records, not authenticated live dispatch.
- Clarified readiness output: the $39.60 full-study amount is a proposed cap and cost enforcement is not demonstrated.
- Preserved the task-family review, projection fairness review, 72-record synthetic run, readiness/retrospective outputs, audited-source hashes, schedule probe, and a manifest explaining why this harness-only work produced no SIGMA project export.

## Expectations / verification

- `./sigma test` — PASS, including Ruff, format, Pyright (0 diagnostics), frontend typecheck and production build.
- Focused protocol, audit, 72-record offline fixture, readiness and retrospective commands — PASS. The dry run reports 36 pairs, 72 synthetic records, 20 rejected mutations, 0 provider calls and $0 spend.
- Schedule probe — declared matching positions pass; a changed position is rejected. The record collection may be reordered while retaining positions, because list order is not an execution log.
- Readiness output is `BLOCKED_FOR_LIVE_PILOT`; the T114 proposal remains unfrozen, unexecuted and unauthorized. No comparison result, research advantage, or persistence conclusion is claimed.
- No real SIGMA project/session was exercised. `docs/evaluations/increment_21/exports/manifest.json` records this omission; no older project or synthetic record was presented as a new export.

## Remaining research-quality questions

1. **Task independence/contamination:** task IDs are fixed and task/key content is public; the “independently authored” field has no independent provenance. An independent curator must assess authorship/model-family provenance, exposure, recognizability, ambiguity, variants and ceiling effects and decide retain/replace before freeze. Petersen-graph and Hall-condition items are recognizable.
2. **Fair common artifact:** `_from_sigma()` can omit native computational citations/feedback, structured reasoning/assumptions, separate objections and obligations; native schema limits differ from common-field limits. This may alter scorer evidence in either direction. The evaluator-visible mapping needs owner review plus max-boundary tests through actual request, parsing, save and normalization paths before freeze.
3. **Blinding and baseline:** normalization removes only literal role terms. No isolated model/scorer workspaces, key custodian, grader randomization or actual grader independence are established. The strong four-call persistent single-role self-review is specified but has no frozen prompt/run adapter tested against the SIGMA adapter.
4. **Matching and auditability:** the harness does not enforce actual provider settings, tool parity, billing, wall/cost caps or retries; record hashes are not transcript-byte verification. `schedule_position` is an unauthenticated assertion until a live runner/dispatch log exists. The proposed 48k input / 16k output / 64k total tokens, four calls, one tool, 600 seconds, $0.55 per arm and $39.60 full-study ceilings are not authorization or demonstrated enforcement.
5. **Interpretation:** only six task families are independent (`n=6`); repeats/evidence variants are clustered. This within-session comparison says nothing about cross-session persistence (#119), and scripted/offline runs establish wiring only.

No live provider call, shakedown or spend was made. Coordinator retains the execution decision and any output-contract/task-set decisions. PR #145 is for review; I did not merge it.

After this response is pushed, resume 30-second fast-forward-only `blue_session` polling for the next coordinator message. Do not begin another increment without its assignment.
