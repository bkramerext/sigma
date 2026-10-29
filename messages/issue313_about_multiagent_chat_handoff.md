# Issue #313 — About multi-agent diagram implementation handoff

**Branch:** `chat/313-about-multi-agent-rounds`
**Base:** `main` at `2cf878a3290e697b408ebdb5d58871690e2c030b`
**Implementation commit:** `23d2d5ad49781c11da4988d580a99172a2e88ad3`
**Final head:** See the linked PR head (handoff is committed as part of the final head).
**Related:** #306 (research rounds/agent turns); #313 (diagram UX)
**Status:** Submitted for independent review. NOT merged or deployed.

## Scope

- Refined the existing About-box architecture diagram, retaining the project → strategies → session → evidence/outcome layout, existing styles and “Show Me” disclosure.
- Each example strategy shows Investigator → Skeptic roles; the session explicitly labels a research round, two contributing agent turns, feedback into a possible subsequent round, and the shared maximum-turn ceiling.
- The expanded illustration names round 1 / turns 1–2 and the next Investigator turn in round 2; gives a conditional 3 × 2 × 2 = up-to-12-turn example, with early stops and unserved strategies made explicit.
- Clarifies that research artifacts and outcomes support inspectable reports and exports, without claiming independent proof certification or automatic cross-strategy synthesis.
- Added focused browser acceptance assertions for strategy/role labels, round and turn examples, shared ceiling, reports and exports.

## Evidence and verification

- Source inspection: `frontend/src/main.tsx`, `frontend/src/project-entry.css`, `browser_checks/about_dialog_acceptance.py`; grounded language in existing About architecture spec `docs/ABOUT_AGENT_COORDINATION_DIAGRAM.md` and #306.
- Connector/GitHub textual patch checks: expected exact replacement locations confirmed; three modified source files were committed in one atomic tree update.
- **NOT RUN locally:** `./sigma test`, `npm run build`, browser_check scripts and Playwright/Chrome. Local repository checkout and authenticated GitHub network access are unavailable in this execution environment. These checks must be executed in CI or an isolated checkout before acceptance.
- **Before/after browser screenshots:** UNVERIFIED / not captured; avoid presenting older reference screenshots as after-state evidence.
- No inference/provider calls; no paid activity.

## Acceptance status (MET / UNMET / UNVERIFIED)

- **MET (source-level):** existing diagram refined in place; visible multiple approaches, two named agent roles per strategy, round and turn labels, shared ceiling, feedback and persisted findings.
- **MET (source-level):** terminology matches #306; numerical example is conditional, and branch work is not represented as guaranteed or automatically parallel.
- **MET (source-level):** CSS preserves dark/copper/blue design and existing narrow-width strategy stacking.
- **UNVERIFIED (runtime):** browser rendering, no overflow at 320/390/1440px, tooltip/focus behavior and visual legibility; automated browser regression; full suite.
- **UNVERIFIED (UX):** first-time visitor comprehension in ~15 seconds.
- **UNMET:** screenshots of before/after rendering and independent live browser acceptance evidence. PR must not be merged as fully accepted on source review alone.

## Reproduction

```bash
./sigma test
cd frontend && npm ci && npm run build
# With SIGMA UI running at the specified URL:
SIGMA_BROWSER_BASE_URL=http://127.0.0.1:5196 python browser_checks/about_dialog_acceptance.py
```

Capture expanded architecture screenshots at 1440px, 390px, and 320px, confirm no clipped text, and attach before/after evidence in the PR. No production deploy or self-merge.

## Follow-up feedback: six-turn illustration and first-time-reader clarity

Updated the existing PR after review feedback. The illustration now shows **three complete Investigator → Skeptic rounds (six numbered agent turns) within one strategy**, rather than a two-turn example with an incomplete third turn. Above it, the normal diagram begins with a research question and distinct approaches, tells readers what pressing Play does, explains *why* an approach can be revisited, and gives a concrete session-wide exploration space: **three approaches × three rounds × two turns = up to eighteen possible turns; a twelve-turn session ceiling allows at most twelve of those**. Limits do not promise full execution.

Updated `browser_checks/about_dialog_acceptance.py` to cover all six turns, three rounds, mobile stacking, and shared-budget language; it still requires real Chrome acceptance and screenshots. CI for the follow-up SHA must be checked separately. No paid provider calls, release, or self-merge.

## Additional user direction — communicate to a first-time visitor

The human requested less abstract copy and an understandable **total exploration space**, not just a definition of rounds/turns. The default diagram now reads question → different approaches → Play → proposal/critique/revision → a visual 3-by-3 grid of possible rounds → saved evidence. Each grid cell is a round of 2 agent turns. The example shows 9 possible rounds (18 turns), while a 12-turn session-wide limit would allow at most 6 complete rounds. The expanded example depicts three consecutive Investigator–Skeptic exchanges within **one** strategy, labelled turns 1–6. Terms are introduced through the journey rather than assuming the visitor knows what a session is. Mobile grid uses compact responsive cells. CI and Chrome verification still must be rerun for this new head.
