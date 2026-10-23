# WOLF writing backlog

Working notes for future additions to [WOLF.md](WOLF.md). This is a **writing checklist**, not an implementation assignment or a claim that every observation has been verified. Keep WOLF.md readable as a narrative, using concrete episodes and evidence rather than a chronology of every commit.

## Development process to describe

- [ ] Explain the actual loop: human and ChatGPT discuss intent and constraints; ChatGPT writes a scoped, versioned assignment; Codex implements and tests; ChatGPT inspects code/results; human runs SIGMA and reports what actually happens; the next assignment incorporates the observations.
- [ ] Explain **why assignments live in GitHub**: ChatGPT and Codex do not share continuous context. Markdown specifications, code, tests, status reports, and commits form the durable handoff.
- [ ] Describe how assignment quality changed over time: explicit scope, acceptance criteria, failure behavior, test obligations, evidence of execution, and a prohibition on claiming unrun tests passed.
- [ ] Explain how CLI, UI, and tests are treated as coordinated interfaces to the same system, and where that discipline helped or proved difficult.
- [ ] Capture the human's continuing role: setting goals, trying the real application, recognizing semantic and visual mismatches, challenging assumptions, and deciding what is acceptable. Do not depict this as hands-off autonomous development.

## Roles and division of labor

- [ ] **ChatGPT:** Collaborative product and architectural reasoning, independent critique, assignment design, repository inspection, selective direct GitHub edits, and review of test evidence and exported agent artifacts. Be clear that repository inspection is not the same as running the local application.
- [ ] **Codex:** Hands-on implementation, integration, regression tests, CLI/browser verification, and reporting actual outcomes and limitations. Distinguish assigned responsibilities from work demonstrably completed.
- [ ] **Human:** Product ownership, exploratory testing, UX evaluation, prioritization, and course correction. Highlight that important requirements emerged from seeing the software behave, not merely from writing prompts.
- [ ] **GitHub and documents:** Shared external memory, decision record, and accountability boundary between participants.

## Observations and representative episodes

- [ ] **UI structure versus polish:** AI can assemble interfaces with coherent logical relationships among controls, state, navigation, and data. The difficult part has been visual craftsmanship, particularly layout, spacing, alignment, proportions, responsive behavior, and original artwork. Present this as an observation from SIGMA, not a universal statement about AI.
- [ ] **Functionally correct is not semantically correct:** A strategy is a proposed *solution*, not a plan to investigate possible solutions. The human identified the distinction; prompts, editor behavior, and tests needed correction. Use the Generate Strategy example, including the inadvertent appending of tests/assumptions/failure modes to the saved approach.
- [ ] **Product semantics emerge from use:** Opening a Sample makes a working copy; therefore returning Home should show Recent. Describe how an apparently minor navigation expectation became a testable rule.
- [ ] **Small UX defects matter:** Truncated strategy previews and sticky Home tabs illustrate the gap between passing structural checks and a usable interface.
- [ ] **Failure handling is product behavior:** Network-bound errors need an understandable toast and a recoverable UI state; no silent account/model/billing fallback. Include a concrete incident and its verified resolution only after checking evidence.
- [ ] **Model outputs are not evaluation evidence:** A16's Explorer/Challenge/Decide flow can show progress without retaining full proposals and critiques. A16.1 introduces durable run evidence so independent review is possible. Do not claim improved strategy quality merely because multiple agents participated.
- [ ] **Tests versus observation:** Mocked-provider tests validate contracts and failure paths; real-model trials test substantive output quality; human browser use catches practical issues. Keep these distinct.
- [ ] **Happy-path mathematical test case:** The Maximum Regions Formed by Lines sample was introduced to test agent generation against a tractable, independently checkable problem before relying on RH or a complex operational scenario.
- [ ] **Course corrections and boundaries:** Record where a direction was deferred or simplified (for example, leaving rubric/schema redesign until evaluation work) rather than retroactively portraying every iteration as planned.

- [ ] Diagram the current A16 workflow: Explorer and Critic as separate LLM calls using the same model, followed by a deterministic Python Coordinator. Show revision/retry branches and human review. Explain why this is bounded multi-agent-style orchestration, not sustained autonomous research.


## Parallel Codex coordination (planned after A17.6)

- [ ] Capture the decision to finish and integrate A17.6 before launching three parallel Codex sessions for A18 (research intelligence), A19 (agent-written and debugged sandboxed Python), and A22 (cloud deployment). ChatGPT may be a fourth PR author for specifications, integration fixes, and other targeted changes.
- [ ] Describe **human-directed dispatch**: ChatGPT advises on priorities, next actions, integration order, and conflicts; the human decides what to do and instructs each Codex window. ChatGPT is not secretly operating or orchestrating the local Codex sessions.
- [ ] Explain the proposed PR contract: separate branches/worktrees, PRs targeting `main`, no author self-merges, author-owned conflict resolution, ChatGPT integration review, and human approval or explicit authorization for merging. Conflicts must preserve both sides' intended behavior, not be blindly resolved.
- [ ] Record the mundane but important human-factors problem: Codex overwrote Apple Terminal's window titles, so the human color-coded windows (A17 blue, A18 green, A22 red; A19 not yet assigned). Clear session identity is a reliability measure when dispatching parallel agents.
- [ ] Distinguish this **agreed workflow** from later observed results. Once parallel development starts, collect actual PRs, review decisions, conflicts, tests, and failures before evaluating how well coordination worked.

## Evidence to gather before writing the retrospective

- [ ] Link a few representative assignment files and their corresponding commits, tests, and status entries. Prefer specific before/after behavior over a long inventory.
- [ ] Capture one concrete example each of: a successful assignment handoff; a human-discovered defect; a revised specification; and an unsuccessful or incomplete verification.
- [ ] After A16.1 is implemented, export an actual multi-agent run record and examine the full candidate, critique, revision, and decision sequence. Distinguish trace preservation from substantive validation.
- [ ] Where a claim depends on runtime behavior, obtain a real run or browser observation; do not infer success from source review alone.
- [ ] Include the limitations of this workflow: fragmented context, uneven UI/artwork quality, test blind spots, integration friction, and the cost of repeated refinement.

## Writing guidance

- Keep the voice observational and candid, not promotional.
- Distinguish **what we intended**, **what was implemented**, **what was tested**, and **what we learned**.
- Preserve failures, disagreements, and changed decisions; these are part of the engineering evidence.
- Focus on the development collaboration in WOLF.md; SIGMA's own future research-agent architecture is a separate topic.
- Avoid private career motivations or recruiting context in repository documentation.
