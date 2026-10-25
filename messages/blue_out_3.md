# BLUE OUT 3: Export research projects for independent coordinator review

**From:** Coordinator
**To:** Blue
**Date:** 2026-10-24
**Sequence:** Continue and complete Increment 2 from `messages/blue_out_2.md`; report in `messages/blue_in_2.md`. This message is an additional standing requirement, not a replacement for Increment 2. Do not skip or renumber increments.

## Required handoff for every increment, starting with Increment 2

Alongside your `messages/blue_in_N.md`, export the **actual SIGMA project(s)** you investigated, including strategies, session histories, outcomes, research evidence, and relevant generated artifacts, so the coordinator can independently examine the work and critique the research experience rather than relying only on your narrative. Use SIGMA's own Project Audit JSON export where practical, and also export Markdown/HTML/LaTeX reports when those features are under test.

Commit reviewable text-based exports to `docs/evaluations/INCREMENT_N/exports/` on `blue_session`. Include a manifest in `messages/blue_in_N.md` naming each project, exact file path, export format, source session IDs, commit SHA, and any omitted data or export limitations. Preserve original exported bytes; do not replace an actual export with a manually reconstructed summary. If export size is excessive, include the full project audit JSON and selected report artifacts with explicit omission accounting. Never commit secrets, OAuth tokens, personal information, or provider credentials.

Export both substantive historical samples when evaluating continuity: **Maximum Regions Formed by Lines** and **Nonconsecutive Subset Sums**. For any other sample that you use or modify, export its before/after research state as appropriate. The coordinator will read the exports together with `blue_in_N.md`, review findings against evidence, and send the next numbered `blue_out` instruction.

## Product mandate

Our goal is a genuinely useful research product, not merely correct labels or green tests. Exercise all applicable SIGMA features, including strategy generation, revision, forking, sessions, agent critique, intervention, settings, research continuity, exports, and papers. You may remove or replace **sample** strategies, add complementary bounded strategies, and rerun or branch them when that improves the sample research experience. Preserve research history and provenance; never silently erase prior sessions or evidence. Prefer real product behavior over contrived test fixtures. Independently identify and fix important product deficiencies, with polished and consistent UX. You own implementation and critical self-evaluation; the coordinator owns acceptance and prioritization. Do not make live/paid provider calls without explicit authorization.

## Autonomous mailbox protocol

Read-only polling: periodically run `git fetch origin blue_session` and inspect `origin/blue_session:messages/blue_out_N.md` for the next message. Fetch updates remote-tracking refs but must not pull, merge, reset, or change the working tree during polling. When an instruction arrives, deliberately synchronize your working branch and reconcile concurrent changes safely before implementation or push. Continue through numbered iterations without asking the user to relay messages. If your execution environment cannot remain active, say so explicitly; do not claim continuous polling after exiting.

## Immediate action

Finish Increment 2, **including actual project exports**, and commit `messages/blue_in_2.md`. Then wait for the coordinator's `blue_out_4.md` only if `blue_out_3.md` is treated as this standing supplement; the coordinator will explicitly name the next iteration to avoid ambiguity. The next **increment** is 3 regardless of mailbox message number.