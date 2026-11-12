# SIGMA Release Notes

## Version 0.1.6 — Initial Preview
*October 30, 2026*

**Our first release for a small group of early users.**

SIGMA (Strategy Investigation, Generation, Measurement & Assessment) is an experimental AI research application designed to investigate difficult questions through multiple strategies and preserve what is learned along the way.

Rather than producing a single answer, SIGMA uses Investigator and Skeptic roles to explore ideas, challenge assumptions, examine evidence, and identify unresolved questions.

### What's included

- **Multi-strategy research:** Explore several approaches to the same problem and compare their findings.
- **Investigator and Skeptic collaboration:** Structured exchanges examine promising ideas and challenge conclusions.
- **Persistent research history:** Return to saved sessions, findings, evidence, and Current Understanding.
- **Research papers:** Generate LaTeX papers and PDFs from completed research, with saved versions available for review.
- **Example projects:** Explore mathematics, biology, and military-planning research examples.
- **Google sign-in and invitations:** Authorized participants can maintain their own research workspaces.
- **AI access and usage controls:** Supported connection options and allowances help manage research costs.

### What we're looking for

This is an early preview intended for a small number of people willing to experiment with SIGMA and provide feedback.

We're especially interested in whether the research process is understandable, whether the results are useful, and where the experience becomes confusing or unreliable.

SIGMA is experimental. Its AI-generated findings and papers should be reviewed critically and should not be treated as independently verified conclusions.

---

## Version 0.1.7 — Reliability and Access Improvements
*October 30, 2026*

**A follow-up release focused on making SIGMA more reliable and easier to use during the initial preview.**

Version 0.1.7 builds on the initial release with improvements to research execution, simultaneous usage, account access, and deployment reliability.

### What's improved

- **More reliable research sessions:** Improved recovery from interrupted and incomplete AI responses, preserving useful progress.
- **Better concurrent usage:** Multiple users and projects can perform research simultaneously, with stronger safeguards around resource limits and session isolation.
- **Safer session management:** Improved handling of Stop, Resume, interrupted workers, and recovery after failures.
- **Improved invitation and authorization workflows:** Authorized Google-account domains can grant membership automatically, while existing invitation workflows remain available.
- **Better administrator notifications:** Improved notification handling for invitation requests and feedback.
- **More reliable paper generation:** Better handling of simultaneous PDF compilation and recovery from compilation-related failures.
- **Safer application updates:** A branded maintenance page appears during disruptive production updates, reducing confusion while SIGMA is temporarily unavailable.
- **Improved browser refresh behavior:** Better handling of cached application assets during software updates.

### For early users

The focus remains on collecting practical feedback from a small group of researchers and curious users.

We want to learn whether SIGMA's multi-agent approach produces useful insights, how well it handles real research questions, and which improvements would make it more valuable.

**Build identifier reported in About:** `66ca59a`.

### Known limitations

SIGMA remains an experimental research application. Investigator/Skeptic agreement is not independent verification, and generated research papers may contain errors or unsupported conclusions.

Please report confusing behavior, unsuccessful investigations, missing evidence, or unexpected results. Negative findings are valuable feedback too.

---

## Version 0.2.0 — Deeper Research, Better Papers
*November 4, 2026*

**A substantial expansion of SIGMA as a research workbench.** Version 0.2.0 goes beyond producing an answer: it gives investigators more room to explore difficult questions, scrutinize the evidence, preserve the work, and turn results into papers that are easier to evaluate.

### Research process and scientific rigor

- **Structured research rounds.** Investigator and Skeptic exchanges now follow configurable rounds and paired turns. The new default is three rounds with three paired turns per round: **18 AI agent calls per enabled strategy**. The interface also shows the total across enabled strategies.
- **Parallel strategies, ordered debates.** Independent strategies can advance concurrently within shared capacity limits, while Investigator and Skeptic calls remain sequential within each strategy. Longer sessions preserve the relationships between findings, reviews, and open obligations.
- **Longer-running research.** The default session duration is 60 minutes, with an **Unlimited** option for the overall research deadline. Per-call, spending, usage, and configured turn limits still apply.
- **Durable continuation.** Interrupted or provider-limited sessions can resume from saved work, even when the connected provider account changes. Completed role calls, findings, evidence, attempted calls, and uncertain usage are preserved rather than restarted or silently replayed.
- **More careful scientific outcomes.** SIGMA now separates scientific acceptability from merely reaching a scheduler limit. Substantive challenges and conflicting evidence remain blocking; nonblocking peer-inspection tasks can be identified without treating a promising candidate result as independently proven. Multiple strategies are reconciled without discarding disagreements or negative findings.
- **Improved research methodology.** Stronger adversarial review, explicit evidence provenance, smaller bounded context packages, and clearer source-availability records reduce unsupported claims. The system distinguishes retrieved and inspected reference material from an unvisited link.

### Project Types and research standards

- **Built-in and custom Project Types.** Create projects using subject-specific conventions or define custom types inherited from other types. Common research and publication standards are kept separate from disciplinary guidance; Literature has been added alongside the scientific and mathematical subjects.
- **Reference selection per user.** Enable or disable individual research and publication references, with settings isolated between users. Changes apply to new work without rewriting frozen references in existing sessions or papers.
- **Reference compilation and reuse.** SIGMA can compile the selected methodology material into concise, durable guidance once per research session, and separately for paper writing. Selected, omitted, unavailable, and hashed excerpts remain traceable. Reference compilation has its own accounting and guarded retry behavior.

### Better papers

- **More faithful writing.** Paper generation more carefully traces claims to saved research, recognizes counterexamples and uncertainty, and distinguishes verified evidence from open questions. Subject-specific guidance improves mathematical, physical, and literary presentation.
- **Resumable multi-section authoring.** Long-form papers retain planning, section, and proofreading checkpoints. Completed sections remain saved if another section encounters a provider failure, and bounded automatic retries help recover from transient interruptions.
- **Iterative LaTeX proofreading.** Up to three proofreading passes, stopping early when changes converge, improve presentation while protecting the scientific meaning of the manuscript.
- **Paper Score.** Saved papers can be scored against a weighted, versioned rubric on a 100-point scale. The score appears in paper metadata and a detailed review dialog. **This is an editorial quality assessment, not independent scientific validation.**
- **Plain-language explanations.** The Explain-it-to-me-like-I'm-5 feature can generate and cache an accessible explanation of a saved paper.
- **Paper archives and downloads.** Paper versions, readable filenames, LaTeX source, PDFs, and provenance are easier to locate and inspect.

### Explore, organize, and share

- **Research Q&A.** Ask questions about saved sessions, artifacts, findings, and Current Understanding. Answers retain a frozen evidence basis and validated citation links, and are included in project export/import.
- **An expanded sample library.** New example investigations cover AI agent reliability, sovereign AI, biology, mathematics, qubit decoherence, warp-drive physics, and literary analysis of *The Crucible*. Public sample papers are supported where complete, approved PDF and score artifacts are available.
- **Project version pinning.** Pin a preferred project version in place, temporarily hiding its unpinned siblings without deleting anything.
- **Save As and project email.** Duplicate a saved project under a new identity, preserving its independent history and related work. Share an importable project bundle by email, with optional PDF and LaTeX attachments, when SMTP is configured.
- **Clearer workflow and navigation.** Revised session controls, project summaries, step progress, logs, citations, tooltips, exports, and workflow documentation make long investigations easier to follow.

### Reliability and limitations

This release strengthens recovery from interrupted streams, provider errors, capacity limits, context growth, and incomplete paper-writing calls. SIGMA records uncertainties about AI usage rather than assuming a failed request was free or safe to replay.

**SIGMA remains experimental.** Investigator/Skeptic agreement, a completed research schedule, and a high paper score are not substitutes for independent review. Generated claims and citations should be checked before relying on or publishing them.

<details>
<summary>Maintainer release boundary</summary>

Deployed v0.1.7 SHA: \`802e9b6b7da5829868070f760e17280cd8a927f2\`.
Deployed v0.2.0 SHA: \`9d938907ffd02fb89c9d10545e8df61484310cbd\`.
Deployed v0.2.1 SHA: \`5435e14eeea159ab207ad50016577b9a9542ae59\`.
Each section describes the changes since the preceding deployed version.
</details>

---

## Version 0.2.1 — Paper Workflow and Production Resilience
*November 6, 2026 · Deployed from `5435e14eeea159ab207ad50016577b9a9542ae59`*

**A focused follow-up to make paper generation more dependable, visible, and easier to control.** This release describes the changes merged after v0.2.0 and was deployed to production on November 6, 2026.

### A simpler Papers workspace

- **Papers alongside Sessions.** Paper generation moves out of a modal dialog into a collapsible **Papers** section on each project, with individual paper cards, familiar Play/Stop controls, progress steps, downloads, browser viewing, scoring, and explanations.
- **Clearer progress.** The writing stage reports completed and total sections when known, including after refresh and continuation. Reference review, evidence extraction, writing, validation, proofreading, and PDF compilation use consistent pending, active, and completed labels. Errors are presented without burying the user in internal diagnostic chatter.
- **More intuitive controls.** Start over clears the unfinished paper work but does not automatically generate a new paper. When the reset completes, the paper remains in place with **Play** available; it no longer presents Start over again. The reset displays **Paper generation starting over**.
- **Polished paper cards.** Each paper has its own container and spacing. High-scoring papers show a star by the paper title for scores **above 70**. Activity indicators, hover behavior, action menus, confirmation popovers, and loading labels are aligned with the rest of SIGMA.

### Generation continuity and resource protection

- **Queued paper generation.** Starting a paper in another project queues it when the generation slot is occupied. Yellow indicates waiting, green indicates active generation. Queue state and cancellation are durable enough to explain interruptions without silently replaying unknown AI work.
- **Checkpoint-first recovery.** Section drafts and provider accounting survive interruptions, failed PDFs, Stop/Continue, and transient network or provider failures. Compilation diagnostics are preserved privately while the user sees a concise recoverable message.
- **Production memory protection.** A backend watchdog can restart an unresponsive service. Memory-pressure monitoring limits new AI work and halts active work at critical thresholds while preserving recoverable state. Administrators can receive urgent alerts.
- **Persistent operational diagnostics.** Backend memory and activity logging are retained on persistent storage, with automatic log retention and more usable project/session diagnostics. Resource limits were adjusted for the larger production host.
- **Smaller memory footprint.** Paper-list rendering and routine progress checks avoid loading unnecessarily large paper checkpoints.

### Additional improvements

Research Q&A browser pages scroll correctly; literature-specific research and paper guidance is improved; opening projects has a consistent status indicator; browser favicon activity settles back to idle; and session/paper controls, tooltips, spacing, and error notices are more consistent.

**Status:** Deployed to production. The next section records the subsequent release.

---

## Version 0.2.2 — Research Controls and Reliable Papers
*November 8, 2026*

**A follow-up release focused on clearer research requirements, user-wide controls, and reliable paper work.**

### Research settings and project descriptions

- **Research Ethos and user-wide settings.** Model, reasoning effort, research limits, preferences, and Research Ethos are managed as user-scoped settings and apply consistently across projects.
- **Separate project requirements.** Projects distinguish the research subject, desired outcomes, and paper requirements, preserving those fields through editing and portable project files.
- **Provider choice and safeguards.** Provider-specific settings and status remain explicit; SIGMA does not silently switch billing modes or discard existing provider bindings.

### More dependable papers and exports

- **Resumable paper writing.** Saved checkpoints preserve completed writing when a later section or PDF build fails. Progress and completion messages describe the actual saved state, and interrupted paid work is not silently replayed.
- **More useful paper activity.** Writing stages provide clearer, bounded status while preserving detailed diagnostics in operational evidence rather than presenting misleading success.
- **Portable project bundles.** New exports compress large binary members while retaining import support for earlier bundle formats.
- **Consistent research and paper presentation.** Project controls, paper actions, mathematical TeX, sample descriptions, and browser workflows receive focused usability and correctness fixes.

### Reliability and limitations

Production deployments use a keyless, guarded release path with a fresh isolated recovery drill, exact-SHA image provenance, and a maintenance window. Recovery checks and deployment status do not independently validate the scientific correctness of generated findings or papers.

**Status:** Deployed to production from merged `main` SHA
`469c955dfadb5a7bd17b72fc069a3365b4f20ba7`. The operations runbook records
the recovery snapshot, restore verification, image identities, cutover window,
and production health evidence.

---

## Version 0.3.0 — Durable Paper Recovery and Clearer Controls
*Release candidate · November 8, 2026 · Production deployment pending*

**A reliability-focused update that makes interrupted paper generation resume where it left off, while making research controls and project actions more consistent.** This draft covers changes merged after the v0.2.2 production source, reviewed through main SHA 666200d0aab76fea700d9904cd7b5ee33580e751. Changes merged before the final freeze will be reviewed for inclusion.

### Paper generation that continues from saved work

- **Checkpoints through the entire paper workflow.** Accepted drafts, corrected LaTeX after proofreading, individual verified PDF passes, the published PDF, and scoring progress retain enough evidence to resume at the next unfinished stage instead of returning to Writing sections.
- **Resume at Score or Finish.** Stopping and restarting after the PDF is saved can resume scoring without authoring the paper again or creating a duplicate paper version. Previously interrupted papers that have an existing published PDF and a legacy progress record can also recover.
- **More reliable PDF retries.** Individual compilation passes retain their inputs, output hashes, pass cursor, and diagnostics. Resume validates what was saved, reuses completed work, and cleans up temporary staged PDFs at completion.
- **Correct invalidation when options change.** Changes that invalidate corrected LaTeX can trigger the appropriate proofreading again; unchanged, verified stages are not needlessly repeated. Existing provider-accounting protections still apply.

### Model, Markdown, and scoring controls

- **Model/Thinking changes no longer block Markdown conversion.** A model or reasoning-effort selection can change while a conversion is running. Each saved result retains the model and effort actually used for that request, while account/billing and source-integrity checks remain in place.
- **More accurate Rescore availability.** Paper scoring checks current provider eligibility and account binding when the action is used, and explains why Rescore is unavailable rather than relying on stale page state.
- **Clearer model visibility.** Compact, consistently sized model, reasoning-effort, and sponsored-provider controls make the current selection easier to see.

### Consistent project and administrator interfaces

- **Simpler project creation.** Project Type and Difficulty fields align consistently, Difficulty uses SIGMA's styled dropdown, and redundant explanatory text is removed.
- **Cleaner reference and strategy editing.** Common and custom Project Type references use consistent add, enable, edit, and remove controls. Strategy actions and paper/browser actions use consistent icon sizes, order, hover text, and dismissal behavior.
- **Better administrative and saved-answer controls.** Administrator actions, feedback review status, and allowance refresh are clearer. Saved Q&A browser/remove actions and session-log toolbar alignment are standardized.
- **More predictable dialogs.** Close controls, Escape behavior, menu placement, and layout spacing have been refined.

### Sample research

- **Riemann Hypothesis example project.** A new bundled sample explores how SIGMA investigates this longstanding unsolved mathematical problem. It is a research exercise, not a claim of a proof or solution.

### Reliability and limitations

SIGMA retains saved research and paper evidence across supported interruptions; a completed stage is only reused when its checkpoint remains valid. Uncertain AI-provider attempts are not assumed to be free or safe to replay.

SIGMA remains an experimental research application. Investigator/Skeptic agreement and editorial paper scores are not scientific validation; review generated findings, evidence, citations, and papers independently.

**Release status:** The v0.3.0 version files and lockfiles are prepared from source cutoff `ef463bd0fb06dcd9f437651d6dff803bd206b545` with documentation-only additions. The final release commit is the merged version-bump commit after green exact-SHA CI. **Not yet deployed:** isolated restore verification, guarded cutover and production acceptance remain pending. Production is still documented at v0.2.2.



---

## Version 0.3.1 — Source Materials and Collaboration Trial
*Release notes draft · November 9, 2026 · Deployment not yet confirmed*

**SIGMA v0.3.1 expands the evidence researchers can bring to a project, introduces shared-project collaboration on a trial basis, and improves paper evaluation, reliability, and navigation.**

### Source Materials

- **Project attachments and PDFs.** Researchers can supply documents, research papers, technical reports, observations, experimental results, and other project-specific evidence.
- **Purpose.** Source Materials establish the facts and background the Investigator and Skeptic should use when exploring the research question. Supplied materials are treated as accepted premises **within that investigation**, not as independently established truth outside the project.
- **Preparation and reuse.** SIGMA compiles relevant supplied content for use in research and retains source materials with the project, including portable project exports and imports.

### Research inputs have distinct roles

- **Source Materials:** *What is assumed true* for the investigation—the supplied facts and evidence.
- **Research Standards:** *How to investigate*—methodology, reasoning practices, and research expectations.
- **Publication Standards:** *How to present the paper*—structure, conventions, and editorial requirements.

These inputs serve different purposes: attaching source evidence does not replace research methodology or publication guidance.

### Project collaboration — trial feature

- Invite other Google-account users by email to work on a shared project, including its research, papers, and Q&A.
- The project owner controls the project title, Research category, and Difficulty; collaborators can contribute to the permitted research content.
- Participants can stop their own research or paper execution without giving other collaborators permission to stop it.
- Saved sessions, papers, and Q&A carry creator attribution and recorded Model/Thinking information.
- Collaboration remains **experimental and in trial**. Multi-user behavior may still have limitations or unexpected results; this release does not represent a production-readiness guarantee for collaborative workflows.

### Personal settings and paper evaluation

- **User-scoped Model/Thinking.** AI model and reasoning-effort choices belong to individual accounts, including when people collaborate on the same project.
- **Refined User Settings.** Model and Limits controls are more compact and consistent with other SIGMA selectors.
- **Standalone PDF scoring.** The `sigma score_paper <pdf>` command evaluates a local PDF using SIGMA's paper rubric, showing category explanations and weights. An imported PDF does not have the original research archive for full evidence verification.

### Usability, speed, and fixes

- More consistent project and source-material actions, spacing, icons, dialogs, and tooltips.
- Faster loading of Samples, Saved projects, and saved papers, with clearer navigation.
- Restored the Math-project Lean proof-verification action as a **coming-soon preview**, not an enabled proof engine.
- Improved sign-in isolation across browser windows and invitation navigation.
- Strengthened shared-project permissions, cancellation controls, execution leases, and provenance across Stop, Resume, deletion, and Rescore.
- Improved mathematical typesetting in generated papers and fixed assorted interface-state regressions.

### Limitations and release status

SIGMA remains experimental. Supplied source material can be incomplete or wrong; treating it as an investigation premise is not independent verification. Investigator/Skeptic agreement and paper scores do not establish scientific validity. Review generated findings, citations, and PDFs before relying on or publishing them.

**Status:** These notes describe the proposed v0.3.1 release contents. Merging this documentation does **not** deploy v0.3.1 or certify that every feature has completed production smoke testing.

---

## Version 0.4.0 — Open Exploration and Collaborative Research
*Released November 12, 2026 · Production deployment verified*

**SIGMA is easier to explore without an account and more capable when researchers work together.** Version 0.4.0 introduces an anonymous hands-on playground, completes major collaborative execution and recovery work, and makes research limitations and progress easier to understand.

### Explore SIGMA without signing in

- **A hands-on Guest Mode.** Visitors can open sample projects, inspect saved research and papers, create and edit their own temporary projects, add strategies, and export their work without signing in.
- **Start with examples.** Guest Mode opens the Samples collection by default. Available sample research, saved answers, paper PDFs, LaTeX files, and scores can be explored without generating new AI output.
- **Clear AI-action previews.** Starting a Session or Paper, or selecting Q/A Ask, shows a short, dismissible explanation of the member-only AI feature instead of performing model calls. Other AI-powered actions similarly avoid fabricated output or unexpected provider usage.
- **Private but temporary workspaces.** Guest projects are isolated from other visitors and signed-in members. They are not permanent account storage: export anything you want to keep before the temporary guest workspace expires.

### Research together in one shared project

- **Independent work by collaborators.** Multiple authorized researchers can run separate Sessions and Research Q/A operations in the same project without mixing answers, progress, or creator identities.
- **Safe Paper sharing and queues.** Collaborators can start separate numbered Paper runs; queued work remains distinct and published PDFs retain their correct creator attribution. Each participant controls their own executions without stopping another person's work.
- **Live collaboration awareness.** Project and Home activity indicators show active and queued work, including the creator and Model/Thinking information. Shared changes refresh in other windows, with safeguards against overwriting another person's edits.
- **Preserved ownership and history.** Creator permissions, collaborator removal, saved research, Paper artifacts, and Q/A provenance are checked throughout the workflow. Older single-user projects remain readable through the collaboration migration.

### Stronger recovery and research safeguards

- **Recovery after interrupted workers.** Session, Paper, and Q/A work retain durable checkpoints. Backend process failures, restarts, and stale-worker recovery are handled without silently replaying uncertain paid AI calls.
- **Paper restart from saved work.** Shift-click a saved Paper heading to choose a confirmed restart point, such as the validated manuscript or the writing stage. A new attempt preserves the original PDF, manuscript, and frozen research evidence.
- **More helpful Source Material errors.** Research startup now distinguishes SIGMA's source-size and dispatch-packet guards from a model's context window, reports usable source-size diagnostics where available, and explains how to reduce excessive source input.
- **Source Material recovery fixes (#796).** Recovered source-material configuration and Resume behavior more reliably after interrupted or failed research startup.
- **Larger research dispatch packets (#790).** Expanded the bounded research dispatch limit to 512 kB, with preflight checks that reject oversized inputs before provider work and without silently truncating supplied evidence.
- **Preflight checks before provider work.** Inputs that necessarily exceed SIGMA's dispatch limits can be rejected before unnecessary reference compilation or research calls. SIGMA does not silently truncate the supplied evidence.

### Smaller improvements that add up

- **Consistent controls and attribution.** Cleaner action spacing, activity hover details, model labels, session metadata, and upper-right dismissal controls make the interface easier to navigate.
- **More predictable account behavior.** New browser windows inherit the appropriate recent sign-in, while sign-out works on the first click and guest access stays separate from member data.
- **Markdown and mathematical text.** AI Markdown formatting uses the economy model with Medium thinking, independently of the research model. Current Understanding can be formatted, and generated mathematical content receives additional rendering fixes.
- **Faster, stronger verification.** SIGMA's full core test plan is balanced across eight measured CI shards, while browser acceptance and real two-creator PDF compilation remain mandatory release gates.

### Known limitations and release status

Guest Mode does not grant AI execution or durable account storage. Members must have authorized access and an appropriate ChatGPT connection to generate research, answers, or papers. Live two-real-Google-account collaboration smoke testing remains a separate release-acceptance step; automated test accounts do not substitute for it.

SIGMA remains experimental. Source Materials can contain incorrect premises, Investigator/Skeptic agreement is not independent verification, and a high Paper Score does not establish scientific correctness. Review generated research, citations, and papers critically.

**Approved source cutoff:** `dae6de2690fa47e79bd53fb98ace565ad5789210`.
**Release SHA:** `02cd31299deb9581bf31de60aafcfe057012733a`.
**Production deployment:** November 12, 2026; exact-SHA CI and production
acceptance passed. Live two-real-account collaboration smoke testing remains
pending.
