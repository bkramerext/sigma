# SIGMA Information Flow

This document describes how SIGMA's research is organized and how saved information informs subsequent work, both within a session and across sessions.

SIGMA investigates a question using one or more **strategies**—different approaches to the same problem. An Investigator develops an idea; a Skeptic challenges it. The point of repeating that exchange is to **use what was learned to decide what to investigate next**, not merely to generate more text.

## Reference materials: guidance entering the workflow

SIGMA distinguishes **reference materials selected for the project's research type** from **evidence generated during investigation**. Some references are common to all project types; others are specific to a field such as Mathematics or Physics. References carry a title and a source link so people can inspect the original material.

| Category | When it enters the workflow | Purpose |
| --- | --- | --- |
| **Research Standards** | At research-session startup and in subsequent Investigator/Skeptic work | Guide research methods: how to develop and test claims, scrutinize assumptions, evaluate evidence, and describe uncertainty |
| **Publication Standards** | When producing a paper from saved research | Guide presentation and writing: structure, clarity, disclosure of limitations, and publication conventions |

**Research Standards are not research results.** When a new session starts, SIGMA selects the applicable methodological references and attempts to retrieve usable source text. Selected sources must have verified, nonempty retrieved excerpts before the session can dispatch research calls; an inaccessible or invalid selected reference blocks a new session with an actionable error. Selecting **no references** is permitted. If reference compilation is enabled with selected sources, SIGMA prepares bounded methodological guidance from those references before research, and does not silently substitute uncompiled notes when that compilation fails.

During the research loop, the compiled methodological guidance or selected source material helps orient Investigator and Skeptic calls. This is different from the **saved findings, objections, evidence, and obligations** produced by previous turns. Source material should be attributed and assessed; a methodology document is not proof that a particular research claim is true. Because agent context is bounded, do not assume every reference or every saved finding is reproduced in full in every subsequent call.

**Publication Standards have a different entry point.** They inform optional paper planning and drafting **after research has been saved**. They do not act as another Investigator/Skeptic turn and should not be confused with the research standards used for the investigation. Paper-writing standards guide how results are reported; they do not independently validate them.

## Session: the entire investigation

A **session** is one run of the selected strategies, with its own settings, time and spending limits, saved research history, and final **Session Outcome**. It coordinates the strategies, preserves findings and objections (including failures), and can end early if limits are reached or further work is not useful. A new session is a separate run, not the next round of the previous one.

## Turn: one proposal and one critique

A **turn** is one Investigator/Skeptic pair **within one strategy**:

1. **Investigator call:** Develop or revise a claim, argument, experiment, or next question using selected earlier evidence.
2. **Skeptic call:** Examine that work, challenge assumptions, look for counterexamples or unsupported claims, and record objections or remaining obligations.

The two calls are sequential. Their output is saved and can influence the next turn. A turn may produce an accepted finding, a rejected idea, or unresolved questions—none is guaranteed.

## Round: another pass over the strategies

A **round** gives each enabled strategy a configured number of turns. In subsequent rounds, strategies can build on what earlier work established **or failed to establish**: unanswered questions, Skeptic objections, new tests, and relevant findings from other strategies.

**Why have both turns and rounds?** Turns supply the immediate *propose → criticize → revise* feedback loop. Rounds provide a larger *revisit and deepen* opportunity across the configured strategies. They are a scheduling and research-organization boundary, **not a separate AI operation**, a requirement that every strategy finish in lockstep, or a magic quality-improvement step. There is **no automatic round-end merge or synthesis call**.

## How information moves between calls, turns, and rounds

A **pair** and a **turn** mean the same thing in SIGMA: one Investigator call followed by one Skeptic call. Information moves at different boundaries:

1. **Within a pair (one turn):** The Investigator receives its research question and a selected context packet. Its proposed reasoning, assumptions, evidence, tests, and open questions are then available to the Skeptic, which challenges them and records criticism and unresolved obligations. The Skeptic does not independently redo the whole investigation by default.
2. **From one turn to the next:** SIGMA saves the pair's research artifact, including the Investigator's work, Skeptic feedback, objections, evidence references, and next question. A later Investigator can use **selected portions** of this history to revise a claim, test an objection, or pursue a new line of inquiry. It is not a blank restart, but the previous exchange is not blindly accepted as true.
3. **From one round to the next:** There is **no special handoff or merge at the round boundary**. Saved work and still-open obligations remain available for selection just as they do between turns. A later round gives strategies more opportunities to build on earlier results and criticism; the next round does not automatically receive a complete, consolidated report of every strategy's work.
4. **Between strategies:** SIGMA can supply selected findings or objections from another strategy as **peer evidence** in later calls. Those results are attributed to their source and must be evaluated rather than treated as independently verified. Strategies may progress concurrently, so a call cannot assume it has received everything other strategies will eventually produce.

**Saved history is not the same as model context.** SIGMA preserves the full original research records, but each agent call receives a **bounded selection** of relevant prior material, source identifiers, and explicit omissions when necessary to fit context limits. A finding that was saved but not supplied to a particular call cannot legitimately be claimed as reviewed by that call. The **Session Outcome** summarizes the session afterward; it is not an additional Investigator/Skeptic turn.

## After the last round: Session Outcome and Current Understanding

**Session Outcome** answers, as far as the saved evidence allows, *“What did this particular investigation establish?”* SIGMA evaluates the **latest saved reviewed finding from each participating strategy** instead of arbitrarily selecting the last agent to finish. It also checks recorded contradictions, negative findings, and retractions from earlier artifacts. The Outcome describes candidate conclusions, findings across strategies, limitations, and uncertainty. **All completed rounds remain in the saved history**, but there is **no extra final AI call that rereads and jointly reasons over every artifact from every round**. Earlier arguments are not all independently re-proved or given equal weight by the outcome evaluator.

**Current Understanding** answers a different question: *“Across this project's saved sessions, where does the research stand now?”* It is a **read-only, evidence-linked overview** built from project history, not another agent or a new research session. It shows the latest recorded reviews **per strategy**, earlier findings and reported changes, unresolved or unreconciled obligations, failed/partial attempts, and possible next investigations. A later session can contribute to it without erasing earlier work.

| | Session Outcome | Current Understanding |
| --- | --- | --- |
| Scope | One session, across its strategies and completed rounds | All available saved sessions in the project |
| Purpose | Assess what this investigation established | Show the current state of research and what might be worth investigating next |
| Evidence | Saved session artifacts; latest strategy findings plus relevant recorded conflicts and retractions | Saved findings and explicit evidence-linked changes/obligation dispositions across session history |
| Limits | Not a new synthesis/proof pass over all rounds | Not an independently verified truth model; later wording alone does not erase, refute, or supersede earlier findings |

Neither view declares a project solved merely because an Investigator and Skeptic agree. In Current Understanding, an earlier claim is marked refuted or superseded only when a suitably supported, explicit saved relationship says so; otherwise the earlier record remains inspectable.

## Example: the default 54-call ceiling

| Level | Default | What it means |
| --- | --- | --- |
| Session | 1 | One investigation of the project question |
| Strategies | 3 | Three approaches can make progress concurrently |
| Rounds | 3 | Three passes of research across the enabled strategies |
| Turns | 3 per strategy per round | Each strategy has three chances to propose, critique, and refine during a round |
| Agent calls | 2 per turn | One Investigator call followed by one Skeptic call |

**3 rounds × 3 turns × 3 strategies × 2 calls = 54 maximum agent calls.** This is a ceiling, not a promise to execute all calls or produce 27 accepted findings.

## Paper Generation: turning saved research into a draft

Paper generation is an **optional, separate workflow after research**. It does not run another research round or restart the Investigator/Skeptic loop. Its input is the project's **saved session research**—the recorded claims, arguments, evidence, Skeptic objections, unresolved obligations, computational results, and provenance. SIGMA can draw on multiple saved sessions and preserve qualifications rather than assuming that the last claim is correct.

1. **Assemble and inspect source material.** SIGMA takes a bounded, evidence-linked snapshot of saved research for the paper. For larger histories, it organizes or reduces material into manageable inputs so writing can proceed without treating every raw transcript line as equally important. Missing evidence, negative results, and uncertainty must remain distinguishable from supported conclusions.
2. **Apply publication reference materials.** SIGMA selects the **Publication Standards** associated with the project type (including applicable common standards). These guide the *writing process*—organization, argument presentation, reporting and citation conventions, and disclosure of limitations. Where configured, publication-reference compilation turns selected standards into an actionable writing checklist. **Publication Standards are not the research evidence behind the paper's claims**, and must not be cited as though they validate the investigation. Research Standards shaped the earlier investigation; they are not interchangeable with Publication Standards.
3. **Plan and write.** Depending on the amount and structure of saved material, SIGMA may use a shorter drafting path or plan sections and generate them separately. The draft should distinguish investigated claims from established results, ground statements in saved evidence, acknowledge criticism and unresolved questions, and use appropriate sections, tables, and diagrams when requested.
4. **Review and refine.** SIGMA validates the structured draft and runs editorial/proofreading checks, with bounded correction passes that can stop early when no actionable issues remain. These checks can improve consistency and presentation, but **are not independent scientific verification** and cannot manufacture missing experiments, proofs, or citations.
5. **Compile, inspect, and export.** SIGMA converts the paper to TeX, attempts PDF compilation, and performs output checks such as page-layout/overlap validation. The saved paper and its source remain available for inspection and export. A successfully generated PDF is **a draft for human review**, not a journal submission or proof that its claims are correct.

The information flow is therefore **saved research → evidence selection/organization → publication guidance → paper planning and drafting → proofreading/validation → TeX/PDF export**. The **Session Outcome** and **Current Understanding** help people interpret research, but they do not replace the underlying saved evidence that a paper should trace its claims to.
