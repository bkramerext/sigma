# Round 2: Product-first Increments 18–21

**Status:** Planned; work is not started by creating this ticket.  
**Scope:** Four substantial delivery milestones following the closed 13–17 research-effectiveness review. This numbering denotes **research/product iterations 18–21**, not the pre-existing implementation tickets T18–T21.

## Principle: good enough to ship

Prioritize what materially affects a user's next research session. Prefer targeted fixes and an end-to-end working product over exhaustive controls, speculative architecture, elaborate scoring infrastructure, and broad refactoring. Each increment ends with a tangible user benefit, focused regression coverage, and a short honest **win / expectations / unresolved** account. Don't treat a milestone count as a mandate to continue work with diminishing returns.

**Never compromise:** privacy and workspace isolation, durable data, spending/authorization safeguards, evidence integrity, or truthful proof/verification claims. Cloud launch and usable research take precedence over optional research-effectiveness experiments.

## Increment 18 — Hosted core workflow (P0)

**Objective:** A new authorized user can sign in to SIGMA, select/create a project, start substantive research, leave and return without data loss, inspect results, and download an export.

- Integrate the minimum viable hosted workflow across authentication, sponsorship authorization and cost controls, persistent workspace, session engine, Python/Sage execution where offered, Outcome and report/export.
- Respect Cloud ownership and #98/#99 deployment acceptance; no production secret or paid inference action by this ticket.
- Run one realistic hosted end-to-end acceptance; isolate remaining launch blockers and resolve only severe failures. Keep safe rollback and recovery paths.
- **Exit / good enough:** core flow usable and safe, critical release gates verified; lesser polish is a follow-up, not a release stop.
- **Explicit dependencies:** [#98](https://github.com/bkramerext/sigma/issues/98), [#99](https://github.com/bkramerext/sigma/issues/99), and Cloud owner approvals.

## Increment 19 — Readable results and actionable interruptions (P0/P1)

**Objective:** A user can understand the answer, inspect evidence and know what to do when research pauses.

- Close the real math-formatting defect in saved Outcome conclusions, both normal reader and Advanced view, including representative RH notation, without silently inventing mathematical semantics.
- Make a paused session explain the known cause and an actionable safe next step. Do not imply retries are free or safe when billing status is uncertain.
- Keep the evidence-derived computation warning above agent-authored assertions, with truthful verification status.
- **Exit / good enough:** representative mathematical outputs typeset legibly; paused/resumed workflow is comprehensible in Chrome, and important caveats are visible. Avoid an Outcome redesign.
- **Issues:** [#93](https://github.com/bkramerext/sigma/issues/93), [#95](https://github.com/bkramerext/sigma/issues/95).

## Increment 20 — First-user confidence and samples (P1)

**Objective:** A newcomer understands SIGMA, finds a credible starter investigation and knows what it can and cannot establish.

- Improve About/README and starting guidance only where they clearly confuse or mislead first-time users.
- Review the 17 stock samples with the existing assessment; prioritize broken, misleading and redundant entries rather than polishing the entire catalog.
- Preserve RH as the flagship and do not substitute staged claims of mathematical success. Obtain owner approval before deleting/consolidating or substantially rewriting stock samples.
- **Exit / good enough:** newcomer can choose and run a credible example without misleading expectations. The rest of the catalog can be incrementally curated.
- **Issues:** [#89](https://github.com/bkramerext/sigma/issues/89), [#86](https://github.com/bkramerext/sigma/issues/86), related About work.

## Increment 21 — Small genuine research-effectiveness decision (P2; after release)

**Objective:** Obtain evidence that informs whether role separation earns its additional cost, without another open-ended validation program.

- Use #114/#118 as *one* bounded, blinded within-session Investigator/Skeptic vs strong single-role self-review comparison; avoid overlapping independent harness projects.
- Preserve matched model, model budgets, tools, artifacts, output constraints and strong baseline. Treat task variants as clustered and distinguish raw correctness from agent agreement.
- Do not pretend that a short within-session study establishes cumulative multi-session benefit; that belongs to #119, separately sequenced.
- Favor a modest, honest and discriminating pilot rather than perfect statistical power, broad replicated benchmark coverage or repeated protocol rewrites. Report ties, losses, cost and unsupported claims.
- **Exit / good enough:** a sound frozen small comparison and candid keep/change/simplify decision, *if authorized*. If provider approval is withheld, complete only the offline readiness and explicitly mark the comparative result unresolved.
- **Authorization:** No new model calls, shakedown or spending without explicit owner approval of provider, model and hard cap. Blue's proposed $1.25 throwaway shakedown in PR #123 is **not** authorized by this ticket.
- **Issues:** [#114](https://github.com/bkramerext/sigma/issues/114), [#118](https://github.com/bkramerext/sigma/issues/118), [#119](https://github.com/bkramerext/sigma/issues/119) (later persistence study).

## Working agreement and stop rules

- Four **decision checkpoints**, not a large fixed sprint or promise that every requested subfeature will be built. Keep increments substantial and autonomous but review user-visible UX tradeoffs before major redesign.
- Define at most a few acceptance cases tied to observed behavior; use existing tests and tooling rather than inventing another general-purpose evaluation framework.
- Do not merge or claim completion before relevant verification. Do not conflate CI success with research superiority.
- If an item is blocked outside the workstream, document the exact owner/action, continue independent work, and avoid weakening safety gates.
- Defer speculative architecture cleanups, exhaustive edge-case matrices, generic metric dashboards, unfunded longitudinal experiments, and low-impact polish.
- If real use proves a different priority, reorder or drop an increment. Judge success by a better usable research product, not completing the roadmap.

**Round closure:** product release confidence, honest unresolved debt, and evidence-based follow-on priorities. The 13–17 review is closed; unproven research superiority is carried as an open question, not a release blocker.
