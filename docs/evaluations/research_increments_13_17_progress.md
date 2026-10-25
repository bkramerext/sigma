# Research effectiveness: Increments 13–17

**Scope:** One cumulative branch, `coordinator/research-increments-13-17`, based on PR #82 merge `7e664bcd`. **Checkpoint:** Increment 13 implemented and under exact-head CI. Increments 14–17 are not started and require a discussion after this checkpoint. No Codex, paid provider, or cloud operations were used.

## Increment 13: adversarial acceptance and reproducibility

### Findings and remediations

| ID | Severity | Adversarial failure or gap | Action |
| --- | --- | --- | --- |
| F13.1 | High | Saved-question selection matched strategy + artifact ID, not the source session and exact proposed text frozen into the next session's context. A mismatched/duplicated context extract could authorize an unrepresented question. | Now require a unique (strategy, session, artifact) key and the exact question text in the matching frozen source. Missing, duplicated, foreign, truncated, and text-conflicting inputs refuse automatic carry. `39b953f`, `3aa2a5b`. |
| F13.2 | Medium | Later paused, stopped or failed research could be skipped when searching backward, accidentally reviving an older strategy question without acknowledging intervening work. | Such records are not automatic endorsements and block fallback when they contain newer artifacts in that strategy. Explicit human continuation remains separate. `b0031da`. |
| F13.3 | Medium | An execution with only a saved `completed` status, but no source program or result, appeared in the completion count without an explicit missing-I/O warning in the default Outcome. | Preserve the reported status, mark it as *reported*, separately count completed-status records without saved source/output, warn before authored conclusions in UI and TXT/HTML/TeX. Conflicting statuses still do not count as completed. `961a47f`, `1fc92aa`, `970b226`, `2a27036`. |
| F13.4 | Acceptance gap | Prior Chrome checks passed but did not retain viewable screenshots in CI for critical Outcome variants and failure statuses. | Capture desktop, 375px and 320px Simple/Advanced and interrupted/missing-output evidence; upload screenshots as finite-retention workflow artifacts. Chrome assertions enforce placement, count, lack of overflow and no provider call. `8bb6248`, `af82f20`, `5c02a0f`. |

### Controls

- Unit regressions reject mismatched source session/strategy/question, collisions, truncated or missing fields, interrupted sessions and stale question resurrection while preserving valid terminal same-strategy carry. Existing real persisted dispatch tests still validate immutable historical session bytes, proper strategy attribution and explicit researcher-approved priority.
- `tests/increment13_integrity.py` runs through `./sigma test`: one status-only completed record is warned about before a misleading authored conclusion in all TXT/HTML/TeX outputs; conflicting statuses are not treated as unambiguous completion; saved source/output distinguish the warning condition. The fixtures are offline synthetic data, **not** independently run experiments.
- Real Chromium exercises the actual UI with a historical archived session and synthetic missing-evidence variants. Screenshots are captured at 1440, 375 and 320 pixels. The provider session-start endpoint is watched and must not be called; no live inference or paid usage.
- Reviewed archived records and original history immutability tests; code only computes projections or prepares a new snapshot and does not rewrite old records.

### Limitations and decisions

- **Not validated:** Autonomous research quality, benefits of automatic continuation, semantic correctness of evidence, model honesty, causal utility of a Skeptic, or advantage over a single-role baseline. Those require later preregistered and authorized work.
- A strategy can be edited while keeping its identity; we did not introduce speculative automatic cancellation of old history based on cosmetic edits. A later targeted test can establish whether changed strategy text causes stale automatic questions. Existing user-approved continuations remain authoritative.
- The browser is headless real Chromium, not a physical mobile device. Screenshot inspection is visual evidence of rendered layout, not a user study. Report test data are synthetic; full CI does not prove the mathematics.
- The source and UI changes stay within existing Project, Strategy, Session and Evidence semantics. No new agent, model, provider, data migration or benchmark answer key.
- **Merge decision:** This PR stays unmerged and cumulative until the 13–17 program is reviewed; stop for human discussion before starting 14.

### CI and review gate

Exact-branch-head full `./sigma test` and Research Outcome browser acceptance must both pass. Earlier failed CI due a new fixture's Ruff formatting; it was corrected without changing production behavior. Later workflow-config failure from referencing a job-ineligible runner path was corrected, and screenshot artifacts are now captured. The latest head and its completed runs must be independently checked before claiming MET.

**Increment 13 preliminary state:** Implementation MET, adversarial coverage MET at offline/Chrome-fixture scope, final exact-head CI pending. Research superiority UNVERIFIED.
