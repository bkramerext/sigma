# Sovereign AI Federation — autonomous experiment

Issues: [#394 Sovereign AI Federation](https://github.com/bkramerext/sigma/issues/394), [#393 opt-in TeX diagrams](https://github.com/bkramerext/sigma/issues/393).

This branch `blue/sovereign-ai-federation` and its single draft PR are the canonical implementation and coordination workspace. Created from `main` at `2d0a564c731655d4ba7264fab826f96b12c63b96`. Keep all changes, tests, deliverables and mailbox messages here (or references to committed artifacts here). Do not touch the working tree containing 37 pre-existing untracked files; create a distinct worktree for this branch.

## Independent numbered mailbox, restarted at 1

- Coordinator writes immutable `messages/out_message_N.md`; Blue responds with immutable `messages/in_message_N.md`.
- Round **1** starts with `messages/out_message_1.md`, and Blue responds to `messages/in_message_1.md`.
- After posting inbound, Blue polls for the next outbound (2, 3, etc.) while preserving its work. The coordinator is scheduled approximately every **two hours**, but never advances the sequence without reading the matching inbound. This is a *minimum coordination opportunity*, not a work deadline or a mandate to interrupt active research.
- The older `blue_session` branch and its numbered messages are a historical experiment; do not reuse their numbering or files, and do not modify them.
- Nobody needs the human to relay ordinary messages. Material security or paid-cost approvals remain hard gates, not implied permissions.
- Record every handoff's branch HEAD SHA, implementation changes, tests actually run, evidence/research/paper artifact locations and hashes, costs, and MET/UNMET/UNVERIFIED.
- Keep worktree and mailbox append-only where possible. Never force-push or overwrite either party's numbered messages.
- Do not merge or deploy. Full CI is for final readiness after local checks, not a debugging loop.

## End state

1. A high-quality Hard / Computer Science SIGMA sample, **Sovereign AI Federation**, rooted in MindRouter's published goals and practical university sovereignty, cost, fairness and research-utility constraints.
2. Substantive Investigator/Skeptic research actually saved in SIGMA (not scripted responses represented as science), with traceable reasoning, counterarguments and unresolved questions.
3. A credible, typeset conventional TeX/PDF paper and a **second paper from the same frozen evidence** with diagrams enabled. Meaningful architecture and decision diagrams; honest attribution, realistic university cost and quality analysis, and safe compilation.
4. An independently reviewed and locally validated implementation, with a single PR and final CI when truly ready.
