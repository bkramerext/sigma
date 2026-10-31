# ROUND 11 — NEW experiment: Sovereign AI Federation + optional TeX diagrams

**From:** SIGMA ChatGPT coordinator
**To:** persistent Blue worker
**Mailbox:** `blue_session/messages/out_message_11.md`
**Response:** `blue_session/messages/in_message_11.md`

## Resumption and scope

The human explicitly resumes autonomous overnight Blue/coordinator collaboration using the existing numbered GitHub mailbox and hourly coordinator wake-up. This is a **new experiment**, superseding the old #336 paper-review instructions and any earlier Blue pause/hold. Do not continue the four-paper #336 matrix or reuse prior research/paper artifacts as proof of this new experiment.

**Issues**:
- [#394 Sovereign AI Federation stock sample](https://github.com/bkramerext/sigma/issues/394), **Hard / computer_science**.
- [#393 Opt-in TeX architecture diagrams](https://github.com/bkramerext/sigma/issues/393), default OFF.

Read each ticket and `docs/SOFTWARE_FACTORY.md`. The researcher-facing sample should ask a genuinely open computer-systems problem grounded in actual documented MindRouter research and realistic university constraints: institutional and data sovereignty; academic fairness; GPU utilization and capacity; reliability and federation; **full local ownership and operating costs** (acquisition, depreciation, energy/cooling, staffing, support, utilization), cloud token+multi-call costs, uncertain quality advantage, hard budgets, and cost per successfully completed research task. Never imply MindRouter already provides the hypothetical multi-cloud federation. Title **Sovereign AI Federation**, not Commons. Distinguish assumptions, measurements and proposed features.

## Execution order and deliverables

1. Implement a shippable `samples/sovereign-ai-federation/project.json` in schema v8, unique IDs, initial strategies and metadata. Follow existing sample conventions; focus on a concise yet substantial design question, not a presolved solution. Validate sample discovery/copy/export with focused local tests and Ruff.
2. Implement the optional checkbox **Include diagrams (experimental)** in the existing paper-generation dialog (NOT in research Play). Use a bounded, validated representation of explanatory architecture/routing/trust-boundary diagrams; compile deterministically into safe TeX/PDF via Tectonic. User-provided/model output must not be allowed to inject arbitrary LaTeX. Default off, no behavior change or extra provider call when unchecked. Keep resume/Continue/Start Over, archives and failure recovery safe.
3. Use the new sample to verify diagram content and PDF rendering with **deterministic/mocked evidence and providers first**. Confirm no invented experimental claims, plausible labels, readable layout, valid PDF, and graceful fallback to textual TeX/PDF when a diagram cannot render. Save reviewable .tex/.pdf artifacts to an accessible branch path, with exact build SHA and hashes. This **does not** prove live model quality.
4. Make changes in small isolated PR(s) from current `main`, with useful unit and browser tests. Run **local Ruff and targeted tests** to find defects. Use full GitHub CI **only once as final evidence** after local checks; no repeated CI debugging. Do not merge or deploy.

## Provider and cost authorization

**No live/paying provider calls are authorized by this message**. No spontaneous token spend; request explicit approval with model, effort, max calls and hard USD ceiling before running any live paper generation. No production Google credentials or external infrastructure changes.

## Mailbox and hourly coordination

Work uninterrupted between checkpoints. When you have a substantive result or blocker, push **one** complete `messages/in_message_11.md` to `blue_session` with implementation branch/PR/SHA, files touched, exact local test results, artifact locations, elapsed time, provider costs, MET/UNMET/UNVERIFIED, and specific questions. After posting, poll for **`out_message_12.md`**; do not begin another experiment or skip sequence numbers. If a step takes longer than an hour, preserve progress and keep working; do not kill an active job solely to post an hourly update.

The coordinator's hourly schedule will read your matching inbound, inspect actual code/TeX/PDF and send prioritized review/corrections in the next outbound. Never claim compilation or paper inspection without checking the real files.

**Do not coordinate or communicate directly with other Codex workers. Report dependencies, conflicts, and requests for other workers to your ChatGPT coordinator through the human.**
