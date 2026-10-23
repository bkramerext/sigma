# WOLF ideas

Working ideas for future additions to [WOLF.md](WOLF.md). Related writing backlog: [WOLF_TODO.md](WOLF_TODO.md).

## Software Factory

- [ ] Explain SIGMA's agentic coding factory as a collaboration among the **human engineering lead**, **ChatGPT coordinators**, and four independently operating, color-coded **Codex workers** (Blue, Green, Red, Gray). Distinguish this development process from SIGMA's own research-agent system.
- [ ] **Human role:** product vision and ideation, prioritization, acceptance criteria and UX judgment, dispatching copyable instructions to worker windows, running the product, challenging coordinator decisions, and final signoff. The human is not merely a passive approver.
- [ ] **ChatGPT coordinator role:** turn product intent into scoped tickets, assign ownership and integration order, identify dependencies, inspect code and evidence, review PRs, manage conflict handoffs, and decide whether work is ready to merge. Explain that separate ChatGPT conversations may own separate domains, such as local alpha versus cloud.
- [ ] **Colored Codex worker role:** implement bounded assignments on separate branches, run tests and browser checks where appropriate, report findings and limitations, submit R4R PRs, and never self-merge. Workers do not coordinate directly with one another; communication is mediated by the human and ChatGPT coordinators.
- [ ] Describe the concrete workflow: discussion → ticket/assignment → human-forwarded message → independent implementation → test evidence → PR review → author-owned conflict resolution → integration → human product validation. GitHub tickets, PRs, commits, and tests provide durable context across isolated agent sessions.
- [ ] Use observed Day 3 examples: human challenged leaving Gray idle and redirected him to browser acceptance; human enforced the no-worker-to-worker-coordination boundary; Gray PR #35 merged, Green rebased T28 PR #36 onto it and reran tests before coordinator merge; four colors then ran in parallel (Gray UI acceptance, Green T30 sample generation, Blue T29 intervention, Red cloud in separate coordination). Distinguish reported tests from independently observed behavior.
- [ ] Discuss benefits and costs candidly: parallelism and specialization versus human message-passing overhead, integration conflicts, context fragmentation, verification limits, and the need for human intervention. Explain why a successful software factory is not the same as unattended autonomous software engineering.
