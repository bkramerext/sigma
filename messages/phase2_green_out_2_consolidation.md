# Green: Phase 2 I2 — single PR and best-available research (owner override)

> **Research-quality addendum (Nov 1):** Read [evidence versus plausible reasoning](phase2_green_out_evidence_action.md). Trace actual claim → supplied evidence → Skeptic objection → follow-up execution/derivation → observed result → corrected conclusion for pivotal claims across domains. Existing I2 resumes retain their frozen v2 instructions; fresh sessions receive the new v3 research guidance. This does not authorize new provider work or change the existing research protocol.

**Authoritative user decision, November 1, 2026.** This supersedes the five-project all-or-nothing paper-consumer gate and the separate export-PR instructions in `phase2_green_out_2.md`, the old #434 handoff contract and `phase2_green_out_2_context_unblock.md`. Preserve the earlier messages as history. **This does not cancel the goal of good, complete research.**

## Repository change already made

- PR #434's existing five partial project bundles, exact `MANIFEST.json`, `EXPORT_VALIDATION.md` and failed-response sidecar were merged **into PR #433's feature branch**, not main, at commit `f803880188d36ebc55b429873eacbed568fbb120`. #434 is now merged/closed as a separate PR.
- **Continue ALL Phase 2 implementation, research, artifacts, publication, tests, and handoffs on #433** (`phase2/green-iteration-1`). No more independent export PRs are required.
- The revised contract is `docs/evaluations/research_quality/handoff/README.md` on #433. The old `releases/phase2-i2-v1/` archive keeps its original `STAGING` status and all 40/60 execution counters; do not rewrite historical evidence.

## Research-to-papers selection policy

**Paper writing uses the scientifically strongest reviewed research available *per subject*, across versions; it does not need five new 12/12 protocols or an atomic five-project READY marker.** A partial research session may provide genuine useful conditional results or counterexamples; explicitly disclose missing final Skeptic work, invalid responses and unverified assertions. Neither newest iteration nor completed-turn count alone determines the best research.

- Green must still pursue high-quality full research and complete valid turns when safe. Preserve partial states, peer context, conclusions, source bodies and methodological provenance. Work can run on independent projects in parallel without changing scheduler/loop.
- Publish each new genuine research bundle and its hashes on **#433**, in a new versioned location. Do not overwrite the merged I2 archival exports.
- For each candidate, give the coordinator a specific quality comparison to prior I1/I2 and strongest earlier underlying research: central results, proof/evidence, skeptical objections, invalidating counterexamples, untested assumptions and provenance gaps.
- The scientific coordinator makes an explicit per-project `SELECTED_FOR_PAPER_INPUT` / `CONDITIONAL` / `HOLD` judgment with chosen immutable commit and bundle SHA. The paper coordinator may use a reviewed qualified candidate, with its limitations, even when another subject is blocked. Green does **not** retroactively certify incomplete protocols or turn labels.

## Current recovery and verification

At the last archived I2 checkpoint: **40/60** authentic completed turns; four completed-but-invalid responses, two Agent dispatch-unknown Skeptics, 16 plan-sharing limit errors. Retain those facts. The short-term context citation fix and focused test were committed on #433 (through `6cf15c6` before consolidation); the longer evidence-catalog design is [#447](https://github.com/bkramerext/sigma/issues/447). Do not treat the patch as a fix for all four invalid responses.

After pulling the latest #433 head, run focused evidence-context tests and `./sigma test`. Do not dispatch new provider work until current code verifies and provider authorization is established; never replay dispatch-unknown requests, forge missing Skeptics, or spend metered API allowance without authorization. If one project remains blocked, advance other safe work; do not restart near-complete projects solely for a clean 12/12 label.

**Report back:** current code SHA and verification, newly preserved bundles, per-project scientific quality comparison, any safely completed turns, and separate remaining technical/protocol blockers. Use one cumulative #433 report and no #434 synchronization.
