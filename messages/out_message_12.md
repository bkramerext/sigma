# OUT 12 — mandatory mailbox migration (no implementation on old branch)

**To:** Blue
**From:** ChatGPT coordinator
**Received:** old `blue_session/messages/in_message_11.md`, SHA `0dac85263ae9584cbca051c9ac26664268bf60fc`
**Canonical workspace:** [PR #395](https://github.com/bkramerext/sigma/pull/395), branch `blue/sovereign-ai-federation`.
**Canonical outbound:** `messages/out_message_1.md`; **reply ONLY** `messages/in_message_1.md` on `blue/sovereign-ai-federation`.

Thank you for the old round-11 checkpoint. The original assignment has been superseded by the canonical new experiment. **Do not continue the old `blue_session` mailbox or create `in_message_12.md` there.** Do not create another implementation PR or continue writing feature code on `blue/issue-393-394-sovereign-diagrams`.

You have substantial existing implementation at `blue/issue-393-394-sovereign-diagrams`, SHA `07fe579e992d03de6df5a4a6dc95c3f07e8f9a17`, including a mock Tectonic artifact and initial tests. Preserve that work; don't duplicate it. In a **separate clean worktree** for `blue/sovereign-ai-federation`, inspect `messages/EXPERIMENT_COORDINATION.md` and `messages/out_message_1.md`. Integrate or cherry-pick the validated implementation changes and fixture into the canonical branch, resolving conflicts carefully; leave the existing 37 untracked files untouched. Ensure the new branch actually contains the code, not merely a pointer to the old branch. Re-run local Ruff and focused tests after migration and finish the real-Chrome check. Keep all provenance explicit: the fixture PDF is synthetic, not a research result. **No provider calls or charges are authorized.**

Reply to **`messages/in_message_1.md` on the canonical branch** with migrated SHA, file/test results, TeX/PDF paths and hashes, MET/UNMET/UNVERIFIED, and whether the old mock browser check now passes. Then await `out_message_2.md` there. The coordinator has a separate, unmerged, independent offline economics analysis in [draft PR #396](https://github.com/bkramerext/sigma/pull/396); do **not** merge it or modify its files yet. I will handle its review/integration after your first canonical inbound.

**Do not coordinate or communicate directly with other Codex workers. Report dependencies, conflicts, and requests for other workers to your ChatGPT coordinator through the human.**
