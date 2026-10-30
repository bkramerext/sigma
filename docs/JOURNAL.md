# SIGMA Journal

A day-by-day account of building SIGMA.

## Day 0 — October 20, 2026

**Theme: Foundations** — Getting SIGMA off the ground.

SIGMA started as an idea: what if an AI research system could pursue a difficult problem over time, remember what it learned, and avoid repeating the same mistakes?

We began building the application around that idea, with Python and FastAPI for the backend, React and TypeScript for the browser, and local projects for saving investigations. Even on the first day we had the beginnings of a real application: projects, strategies, mathematical samples, history, and AI-assisted strategy proposals. Generated proposals were drafts that needed explicit approval before being saved.

We also established the development workflow. ChatGPT helped with design and assignments; Codex implemented them. Versioned specifications and automated tests helped us keep track of the work.

### The first integration problems

Getting the application running exposed problems almost immediately. The Home artwork was missing from the build, and then a UI mockup accidentally became the actual background image. Both were fixed, but they established a pattern that would repeat: something that looked correct in the source code didn't necessarily look correct in the browser.

The first ChatGPT connection worked, although the UI could mistake an expired status check for an expired account connection. That became another follow-up.

### Day 0 retrospective

We had a workspace we could run and improve. The important decision was to make research persistent from the start. Strategies, edits, history, and eventually evidence needed to survive individual conversations. Otherwise SIGMA wouldn't be much different from using ChatGPT directly.

## Day 1 — October 21, 2026

**Theme: Stabilization** — Making the basics work reliably.

Day 1 was spent turning the initial application into something that behaved the way I expected. There was a lot of UI work, but also plenty going on beneath the surface. We were discovering the difference between having features and having features that worked together.

### Getting the workspace right

We reorganized Home around Projects, Samples, and Recent Projects. The copper artwork and slogan took several rounds of adjustment across browser sizes. We simplified project and strategy controls, added inline editing, made strategy creation clearer, and improved forking, renaming, and removal.

One seemingly small issue turned into an important design rule: opening a sample should create an independent working copy. The original must remain unchanged, and the copy should appear in Recent Projects. Getting that right involved identity, naming, persistence, and tests.

We also worked on mathematical text. SIGMA needed to preserve the editable source while supporting Markdown and typeset equations. Formatting could improve readability without quietly changing the research.

### A surprising number of bugs

Markdown conversion sometimes failed even when the AI provider had successfully returned a response. Our code was making assumptions about the response format, then reporting the wrong kind of error. We fixed parsing, response-size limits, and error handling so a failed conversion would leave the source intact.

Startup and shutdown needed attention too. Suspended processes and orphaned servers could keep ports occupied and prevent a restart. We made the launcher more careful about verifying process ownership before stopping anything.

These weren't glamorous fixes, but an application that can't reliably save work, report an error, or restart isn't ready for a more complicated research engine.

### Making strategy generation dependable

We separated ordinary Generate Strategy from the more ambitious multi-agent workflow. It became one bounded AI request returning an editable, unsaved draft. Only an explicit Save changed the project, and cancellation or errors shouldn't corrupt existing work.

A real-browser check with deterministic provider responses passed. That showed the application flow worked; it wasn't a demonstration of autonomous mathematical discovery.

### Day 1 retrospective

Day 1 taught us how much work lives between a plausible implementation and a usable product. Many bugs crossed boundaries: frontend and backend, saved state and temporary drafts, provider output and local error handling, or browser behavior and tests.

The foundation was stronger, and we were ready to move beyond generating research ideas toward actually investigating them.

## Day 2 — October 22, 2026

**Theme: Research Engine** — Giving SIGMA the ability to conduct and preserve investigations.

Day 2 was when SIGMA began to look like the research application I'd imagined. We added a proper Research Sessions interface, improved strategy management, and built the controls needed to supervise and inspect AI research.

### From strategies to sessions

A strategy describes an approach to a problem. A research session is where SIGMA actually works on it. We made that distinction clearer in the interface, while continuing to standardize headings, buttons, editing, and status displays.

I was increasingly concerned that SIGMA should feel like one application rather than a collection of independently developed screens. We also resisted adding controls just because we could.

### Recording what actually happened

Sessions began producing better records: outcomes, assessments, arguments, objections, and inspectable artifacts. We added Report Artifact exports and improved the presentation of mathematical material.

This was central to the original idea. Research shouldn't disappear into a conversation transcript. Its findings and failures should be available to future sessions and to anyone reviewing the work.

We strengthened the Investigator/Skeptic process, with more attention to whether a conclusion was backed by evidence rather than merely well argued.

### Research papers and broader problems

We implemented AI-authored research papers using saved research. That opened the possibility of eventually producing something resembling a mathematical paper from a sustained investigation. But a well-written paper isn't necessarily correct. We kept verification status separate from presentation quality and noted formal proof tools as future work.

We added broader sample investigations and project difficulty settings. SIGMA wasn't meant to be limited to the Riemann Hypothesis. We also prepared multi-strategy research and isolated Python execution, with two Codex sessions working on those capabilities overnight.

### Day 2 retrospective

SIGMA was becoming a system that could carry out research, preserve what happened, and use those records later. We still hadn't shown that multiple agents would outperform a simpler approach. But we were building the machinery needed to test that question.

## Day 3 — October 23, 2026

**Theme: Software Factory** — Putting four AI workers to work.

Day 3 brought two big developments: SIGMA's research engine became substantially more capable, and the way we were building SIGMA changed.

### Research across strategies

The overnight work produced multi-strategy research and isolated Python execution. We added SageMath support, improved research memory and citations, and made it possible to intervene while a session was running.

SIGMA could run bounded investigations across strategies, execute experiments, and save the results. The goal wasn't more agents talking to one another; it was research that accumulated useful, inspectable evidence.

### An interesting mathematical trial

We ran a bounded live investigation of the maximum number of regions formed by lines in a plane.

The Investigator found an upper bound but initially hadn't shown it was attainable. The Skeptic identified that gap, and a later round provided the needed construction, giving the familiar result:

$$
1+\frac{n(n+1)}{2}
$$

That was encouraging. The Skeptic found a real gap, and the Investigator responded with something useful.

But the test also showed weaknesses in our audit records. We hadn't preserved every input, some longer outputs were truncated, and usage accounting wasn't entirely consistent. We fixed the recording problems afterward, but that couldn't retroactively certify the original run.

A good answer and a trustworthy research process aren't the same thing.

### The software factory takes shape

We expanded to four Codex workers—Blue, Green, Red, and Gray—with ChatGPT coordinating their work. Each had its own checkout and responsibilities. GitHub tickets became assignments, PRs became integration points, and tests were part of the handoff.

I still directed the product and reviewed what actually ran, but I wasn't writing the implementation. The arrangement enabled substantially more parallel work. It also brought new problems: workers couldn't share their live context, changes could collide, and handoffs had to be clear enough for another agent to take over.

We started formalizing ownership, acceptance criteria, review, and merging.

### Preparing for the cloud

We explored hosting choices, Google sign-in, private workspaces, and sponsored research with spending limits. We chose Google Compute Engine and prepared deployment plans for sigma-research.duckdns.org. The system wasn't deployed yet.

### Day 3 retrospective

The pace of parallel AI development was impressive. Coordinating it was also becoming an engineering problem of its own. We needed shared records, clear assignments, tests, and someone keeping track of how the pieces fit together.

Meanwhile, the research engine had moved well beyond individual AI responses. Both developments were promising, and both needed more testing.

## Day 4 — October 24, 2026

**Theme: Research Quality** — Making research more cumulative, inspectable, and trustworthy.

Day 4 was less about entirely new capabilities and more about making the research engine do meaningful work with what it already had. We also learned some hard lessons about coordinating coding agents.

### Better outcomes and papers

We improved research conclusions, resumable papers, and how findings connected to their supporting work. We kept clarifying the difference between a strategy, a session, and a conclusion.

A strategy needed to be a meaningful approach to solving a problem, not merely a generic plan to investigate it. That distinction mattered for both generation and subsequent research.

Outcome gained Simple and Advanced views. I wanted a readable summary without hiding the evidence and qualifications needed for serious review.

### Making research cumulative

Blue spent much of the day improving how one research session could contribute to another. We added a view of the current research state, more conservative verification labels, and ways to carry selected evidence into later work.

Recorded Python and SageMath results could also feed later Investigator and Skeptic reasoning. Importantly, the system needed to remember where the evidence came from, what was actually selected, and where its limits were.

Controlled tests with scripted model responses showed that evidence could be preserved and reused. They were not demonstrations of autonomous mathematical discovery. The research-quality changes were integrated with the current UI.

### Explaining SIGMA

We improved the About dialog and its illustration of strategies and the Investigator/Skeptic process. We were careful not to present the Python coordinator as a third AI agent or suggest agent agreement amounted to proof.

We also refined Home artwork and account controls. Explaining the product clearly turned out to be part of building it: a good diagram helps, but a misleading one can make matters worse.

### Branches become a problem

Red's work exposed an awkward integration issue. The branch called authoritative didn't have all the latest changes. Another branch had newer UI and artwork but was based on much older code.

Merging either wholesale risked losing another worker's changes. We created a fresh integration branch from current main and selectively brought over the work we wanted. The originals remained as recovery points, and the new PR still needed CI and browser verification.

Separate branches weren't enough; we needed an unambiguous understanding of what was current.

### The limits of autonomous coordination

We experimented with a mailbox that let a worker poll for new instructions after finishing a task. The idea was appealing, but the coordinator couldn't reliably run at the same pace. We discussed more automation without claiming it was already operating.

Often shorter assignments, clearer handoffs, and more frequent integration were more useful than another layer of orchestration.

### Day 4 retrospective

Research was becoming better at preserving and carrying forward findings. Meanwhile, the software factory was showing its limits: parallel development helped, but poor branch discipline and extra handoffs could eat into the advantage.

We ended the day with stronger research capabilities and better UI explanations, but some integration work remained. Next came deployment.

## Day 5 — October 25, 2026 (deployment continued into October 26 UTC)

**Theme: Going Live** — Getting SIGMA onto the public internet.

Day 5 was the day SIGMA went live.

Getting there involved a surprising amount of work that had little to do with the research engine itself. We needed to finish integration, check the real cloud machine, sort out Docker and deployment configuration, and get public traffic to the running application.

By the end of the day, I could open SIGMA at https://sigma-research.duckdns.org/.

### Finishing integration

We cleared remaining development work and reviewed the PR queue. Changes improved release checks, Docker preflight behavior, backup and rollback procedures, and browser acceptance.

We also stopped work on another Codex coordination launcher. It might be useful someday, but we didn't need more coordination infrastructure before launch. We had enough machinery for the moment.

### Working on the real VM

Red reached the Google Compute Engine VM and checked the actual deployment environment. The rootless Docker preflight had a bug: some inspection ran with the wrong user and socket settings, so a working sandbox could appear broken.

We corrected the checker and ran it on the real machine. The checks covered sandbox isolation, Python and SageMath images, persistent storage, network exposure, DNS, TLS, and services.

This was different from verifying configuration in a local checkout. We were finally testing the machine that would run SIGMA.

We also discovered the provisioned VM and disk were smaller than an earlier estimate. That didn't prevent the preview, but it warranted another look before sustained hosted research.

### The first deployment

Gray handled deployment. We checked the installed release and prepared a recovery point first. We wanted to deploy the intended commit, not an old release that happened to be on the machine.

The application started with healthy containers, but a manually run preflight appeared to fail. Gray stopped the service instead of waving away the warning. The manual invocation had omitted an argument already supplied by the system service; with that corrected, all 23 production preflight checks passed.

Then another problem surfaced: the application was running, but the website still showed the temporary readiness page. Caddy wasn't forwarding requests to SIGMA. We corrected the reverse proxy, checked HTTPS routing, and tried again.

That was the moment the application became accessible from the internet.

### Trying the hosted application

Naturally, the first thing we did was use it. And naturally, we found problems.

Model availability couldn't always be verified, leaving some controls disabled. One mathematical research session paused almost immediately because previous unresolved obligations exceeded its context limit. Others hit conservative cost reserves. Paper generation sometimes refused to proceed because SIGMA thought the research had changed.

These weren't necessarily one problem, and we didn't want to fix them by disabling safeguards. We opened separate issues. Context and spending limits mattered, but SIGMA also needed to offer a way forward when a limit was reached.

The hosted application was running. We hadn't shown that all its core research workflows worked reliably in production.

### What we had actually verified

We had verified the release, healthy services, persistent state, sandbox configuration, network routing, TLS, and public access.

We hadn't yet completed the full hosted browser matrix, multi-account sign-in, sustained sponsored research, paper generation, or a full recovery rehearsal. And none of those infrastructure checks showed that SIGMA produced better mathematics.

I wanted those distinctions to remain clear even as we celebrated going live.

### Day 5 retrospective

The accomplishment was straightforward: **SIGMA was running on the public internet.**

The route wasn't completely smooth. Some failures came from running checks in the wrong context; others were real deployment problems. We had to understand each one rather than assume a green test or healthy container meant everything worked.

Once the site was live, using it immediately exposed the next set of problems. That was part of the point of deploying it. Day 6 would be about getting the pieces to work together.

## Day 6 — October 26, 2026

**Theme: Product Convergence** — Bringing all the pieces together.

Day 5 got SIGMA onto the internet. Day 6 was about making it work.

We had a running application, but using it exposed problems that hadn't shown up in development. Research sessions could stop almost immediately, model selection wasn't always available, and paper generation could reject a reasonable request. At the same time, we were still changing some fundamental parts of the product.

It turned into another busy day of parallel development, testing, fixing, and merging.

### Getting research working

We went back to the problems found during the first hosted trial.

Model availability involved an authentication boundary blocking requests it shouldn't have blocked. We corrected that without opening up operations that require authorization.

Research sessions had a different problem. SIGMA was protecting itself from excessive context, but could leave the user with no useful way forward. We improved recovery so a blocked investigation could continue through a smaller, focused piece of work.

Paper generation had its own issue with detecting changes to saved research. We tightened the checks to distinguish meaningful changes from harmless updates.

Fixes made it into the codebase in stages. Follow-up work and verification remained, particularly around paper generation. We weren't going to declare everything fixed just because a test passed.

### Getting sign-in right

We spent a surprising amount of time on sign-in.

SIGMA needs to accommodate guests, invited users, administrators, personal AI connections, and sponsored inference. That's quite a few ideas to fit into a simple interface.

We settled on a cleaner approach: guests can explore SIGMA, and signing in happens through a consistent control on Home. We refined dialogs, account indicators, model controls, and invitations around that.

We made local sign-in easier to test without real Google accounts or paid AI calls. This gave us a way to exercise the application in the browser.

Several rounds of review caught inconsistent pill dimensions, misplaced tooltips, and navigation behavior. Much of the underlying authentication work was merged, but a follow-up UI and browser-test PR still needed attention.

### One file per project

A major architectural change replaced directory-based project storage with a single JSON file containing the complete project.

That sounds simple until you consider everything a project collects: strategies, research sessions, evidence, artifacts, execution records, and sometimes binary data.

We needed to preserve all of it, support interrupted work, safely migrate older projects, and work in both local and private cloud workspaces.

The implementation went through several rounds of integration and testing, including real Docker execution, interrupted research, saved artifacts, and export/import round trips. The single-file work was merged into main.

This was also a step toward one SIGMA application running locally or in the cloud, rather than two implementations drifting apart.

### Getting the rest of the product into shape

There was plenty of smaller work too.

We cleaned up Guest Home, fixed tooltips and alignment, improved indicators for running sessions and Recent Projects, and continued standardizing controls. Not exciting features, but they made SIGMA easier to use.

Cloud work continued on user isolation, storage, backups, privacy and terms, administrator controls, and Google OAuth configuration. Getting a website online had been one milestone. Getting it ready for users was another.

We also worked on documentation. The README gained real screenshots of Home and a mathematical investigation exploring several strategies. We shortened the setup instructions. WOLF became a more personal account of what I've learned building a product with AI: when engineering judgment matters, when to delegate, how to keep independent workers coordinated, and why a respectful attitude matters. We retired old planning documents as well.

### Keeping the software factory moving

The four workers kept producing work, but integration still demanded attention. A worker could finish against a version of main that had already moved on, and passing local tests didn't guarantee a clean merge.

We spent time resolving those differences, reviewing PRs, and checking that fixes hadn't broken something else. I became more willing to have ChatGPT handle integration directly rather than send every PR back to its original worker. Another handoff isn't useful when the coordinator already has the broader picture.

We merged substantial work and closed a number of tickets.

### Day 6 retrospective

Day 6 wasn't about one big new capability. It was about getting a lot of existing capabilities to work together.

We made progress on authentication, portable projects, research recovery, cloud readiness, and the UI. We also kept closing the gap between what tests say works and what actually happens when someone uses SIGMA.

There was still work to do. Cloud feature parity and isolation needed acceptance, some PRs remained open, and a running application didn't tell us whether its research was any good.

But SIGMA was looking less like a development project and more like a product. That was the real progress of Day 6.

## Day 7 — October 27, 2026

**Theme: The Invited Experience** — Making SIGMA ready for someone other than me.

By Day 7, SIGMA had most of the pieces I wanted. The question was becoming whether another person could arrive, understand what was available, and actually use it.

I wanted the first experience to feel complete rather than merely demonstrate that the underlying features existed. A working application needed to do something useful, and its limits needed to be clear.

That meant taking extra care with the parts a new user would encounter first, even as I was eager to finish.

### Making an invitation mean something

We finished bringing together the guest, invited-member, and sponsored-research experiences.

A guest needed a clear way to ask for access. An invited member needed to understand what had been granted. A sponsored user needed to see the allowance available for research without confusing that with their own ChatGPT account.

Green's work added the invited welcome and sponsored-access controls, including a more personal set of welcome messages. It also made the remaining sponsorship allowance visible and provided a way to force sponsored mode for the hosted launch.

The UI needed to stay simple even though the rules beneath it weren't. I wanted a person to recognize what they could do from the account controls, not have to understand our authentication architecture.

### When accounts and funding overlap

One question exposed how complicated the design could become: what happens if a sponsored user later connects and uses their own ChatGPT account?

Signing in to SIGMA, being eligible for sponsorship, and having a working inference connection are different things. A personal account connection doesn't necessarily prove that the account can execute the requested research. Automatically switching funding sources could also change spending behavior in surprising ways.

We considered the additional state transitions, then decided not to build them yet.

That was a useful decision. An edge case can be real without needing a solution before the first outside user arrives. SIGMA already had enough complexity to test.

### More than one research session

Blue finished another important piece of work: a configurable maximum number of concurrent research sessions per project.

The default remained one, but the limit could now be raised in Project Settings. The setting had to survive project export and import, and admission needed to work across both local sessions and the hosted reservation ledger.

The difficult part wasn't the input field. Older saved reservations didn't have all the information the new accounting expected. An independent review found that some active sessions might escape the new count after an upgrade.

Blue corrected the migration behavior and added regression coverage. Then Green's changes landed first, so Blue had to reconcile the concurrency work with the new sponsorship logic. Both sets of changes were tested together before merging.

It was a good example of the value of review: the feature looked finished, but one older-state case could have undermined its central guarantee.

### Closing the work, not just the tickets

By the end of the day, Green's and Blue's PRs were merged, and we closed the corresponding tickets for concurrent sessions, sponsored allowance controls, and the Invite me action.

The four color workers were clear of their current assignments. That was satisfying after days of overlapping branches, handoffs, and integration conflicts.

It didn't mean every problem had disappeared. A hosted paper-generation request had still returned an OpenAI HTTP 400, and production verification remained important. We kept that issue open instead of treating a merged change as proof that the live workflow worked.

We also prepared the next deployment. I corrected the release target to 0.1.2 and found why production displayed an unknown build identifier: the frontend Docker build didn't receive the Git commit, and it had no Git history from which to recover it. Red was assigned to fix that permanently, including a regression check, before deploying.

A release should identify exactly what code is running. We'd already learned not to trust container health alone as evidence that the public site was serving the intended UI.

### Day 7 retrospective

Day 7 brought a change in perspective. Earlier in the week, I was asking whether SIGMA could do the research and preserve the evidence. Now I was asking what would happen when someone else tried it.

That shifted attention toward invitations, allowances, clear account states, concurrency, and reliable releases. None of those features was the original reason for building SIGMA, but they were part of making the research engine usable.

There was still a temptation to keep adding one more fix before showing SIGMA to anyone. We made one deliberate choice not to do that.

SIGMA was substantially closer to a demonstration I could put in someone's hands. The next test wasn't another merge. It was whether the deployed experience lived up to what we'd built.


## Day 8 — October 28, 2026

**Theme: The Reality Test** — Finding out what works when someone actually uses SIGMA.

Day 7 ended with SIGMA looking almost ready for an outside user. Day 8 was spent discovering the distance between having the pieces and having them work together.

I wanted to get through a straightforward sequence: sign in with Google, request an invitation, approve it as an administrator, and run a small sponsored research session. We had built each part. But the live sequence was still finding problems that automated tests hadn't caught.

### The sign-in that wasn't

The first failure was almost comical. The Google sign-in control was there, but the Welcome dialog covered it. Green added a way to sign in from the dialog, then verified the control itself in Chromium.

That solved one problem and revealed another. Clicking the pill took me to a local API page that said **“Cloud authentication is not ready”** instead of Google's account chooser. The browser test had proved that a link navigated to the expected endpoint. It hadn't proved that the real application could complete the next step.

Once we got farther into the account flow, a signed-in Google user who wasn't a member or administrator had no **Invite Me!** control. That was exactly the person the invitation feature was supposed to serve. We sent Green back to the actual identity and eligibility rules rather than declaring success on the strength of another mocked test.

We also tested product feedback from a signed-in account and anonymously. Both submissions appeared in the administrator's table. That was a genuine success. But the signed-in email appeared under the feedback message while the Contact column still said “Not provided.” We decided to call that column **Google account** and give it enough room to display the address properly.

These weren't obscure failures. They were things a first-time user would notice immediately.

### Making research understandable—and runnable

We continued improving the research experience itself. A session can explore several strategies, with Investigators proposing ideas and Skeptics challenging them over multiple turns. The first version of the About diagram described those mechanics in terms that made sense to the system, but not necessarily to a person seeing SIGMA for the first time. We reworked the explanation so the concepts emerged naturally and the exploration space was easier to grasp.

We also examined why a session could take many minutes. A few visible exchanges can conceal multiple provider calls, scheduling decisions, persistence steps, and budget checks. Waiting longer is acceptable if it buys better research, but we didn't yet have evidence that it did.

Red improved the session lifecycle and created a deterministic happy-path exercise around the Maximum Regions Formed by Lines problem. The work included fairer scheduling, clearer limits, and more realistic browser coverage. PR #317 passed verification and was merged. It was meaningful progress toward playable sessions, though a scripted exchange still wasn't a demonstration of live mathematical research quality.

### The bigger question

A story about Timothy Gowers using ChatGPT to produce original additive-combinatorics mathematics brought the original ambition back into focus. If a standalone model can make a discovery from a plain problem statement, SIGMA ought to be at least as capable. Its orchestration should help, not interfere.

That gave us a sharper scientific question. Breaking research into Investigator and Skeptic turns might improve it by catching errors and exploring alternatives. But it might also interrupt a line of reasoning that would have succeeded if the model had simply been allowed to think. We connected a new advanced mathematics sample to the planned blind comparison of SIGMA against a standalone model, including the possibility that SIGMA could lose.

Then we deliberately put that evaluation aside. We weren't ready to distinguish a failure of mathematical reasoning from a failure of sign-in, scheduling, context management, or spending controls.

### Learning to break SIGMA on purpose

Instead, we opened a whole-system reliability effort. The idea was to give a Codex worker more than a checklist: a repeatable process for stressing SIGMA, watching what happens, preserving evidence, finding root causes, fixing defects, and running the same scenarios again.

It would cover authentication, permissions, research execution, concurrency, cost accounting, persistence, exports, provider failures, browser behavior, and recovery. It would also deliberately combine them. A session cancelled during a budget reservation while another session starts is more revealing than two isolated green tests.

We wanted better observability, not just more assertions. And we wanted longer stress runs to be available without making every routine CI cycle painfully slow.

### Day 8 retrospective

Day 8 didn't end with the smooth first-user demonstration I had hoped for. Green's sign-in and invitation work was still being corrected, and the complete sponsored Easy session remained unverified.

But the day changed how I thought about readiness. The standard wasn't whether a feature existed or whether a test passed. It was whether the application behaved correctly when a person used it, whether failures could be understood, and whether the system could recover without losing work or miscounting money.

The ambition to do serious research hadn't diminished. We had simply become more precise about what needed to be trustworthy before we asked SIGMA to attempt it.


## Day 9 — October 29, 2026

**Theme: Making the Research Publishable** — Turning accumulated investigations into papers without losing their meaning.

By Day 9, SIGMA could do more than run research sessions. It could preserve their work, and we were getting close to a version I could put in someone else's hands. But one conspicuous gap remained: the system needed to turn a project's investigations into a coherent paper.

That sounds like a formatting task. It isn't. A project may contain multiple sessions, several strategies, contradictory findings, incomplete attempts, and useful ideas that never became the final answer. The paper needs to understand that body of work rather than simply print the latest session or declare one session a winner.

### A paper isn't a transcript

We refined the paper-generation process around a principle I wanted to preserve: research sessions aren't a collection of “winning and losing sessions.” Even an unsuccessful investigation can contain an insight, a counterexample, or a limitation that matters to the final account.

The system needed to synthesize evidence across the project, plan a narrative, write sections, and then typeset and compile the result. We also discussed whether a structured representation between research evidence and TeX would make the system less vulnerable to formatting problems. TeX is good at typesetting, but it shouldn't have to carry all the responsibility for organizing scientific claims.

I wanted the output to read like a paper, not a system log. That meant reducing repetitive process commentary, keeping implementation minutiae out of the main argument, and making additional detail an explicit option. We introduced an extra-detail checkbox rather than assuming every generated paper should expose the machinery behind its production.

### The cost of waiting without knowing

The first paper runs made a different problem painfully visible: long stretches of **“Writing paper...”** with little indication of what was happening.

We worked on finer-grained progress reporting, retries, and recovery so the UI could distinguish planning, writing, typesetting, and compilation. I also insisted that paper generation remain robust when a section was imperfect. A logical concern or an uncertain claim should be represented honestly in the paper; it shouldn't automatically abort the entire operation after several minutes of waiting.

The five-minute timeout was especially frustrating. A large paper can legitimately take longer than that. We discussed raising the limit substantially and ensuring that an interrupted browser or closed laptop didn't throw away completed work. The goal was not to promise instant generation. It was to make a long-running operation comprehensible and recoverable.

### Four very different tests

We exercised the pipeline against four projects: **Maximum Regions Formed by Lines**, **Nonconsecutive Subset Sums Modulo 3**, **Xenopus Tadpoles**, and **Operation Narrow Passage**.

The range was deliberate. The first two required mathematical exposition and careful notation. Tadpoles demanded a scientific narrative. Operation Narrow Passage was a military-planning investigation, not a math problem, and its paper needed a different style. A generic template that happened to work for one subject wasn't enough.

We inspected both the PDFs and their underlying TeX. The iterations exposed missing or weak abstracts, repetition, typography and escaping problems, citation weaknesses, and evidence that wasn't always carried cleanly into the final narrative. Some runs looked promising; others needed another round. We kept iterating instead of mistaking successful PDF compilation for a successful paper.

Blue's paper-quality work moved through successive rounds, with improvements to section planning, evidence handling, and fallbacks. By the end of the day, the work was converging, but it wasn't yet the moment to claim the papers were final. We were aiming for one more disciplined round rather than endless polishing.

### Keeping changes reviewable

The paper work happened alongside the rest of the software factory. We continued coordinating branches, reviewing PRs, and keeping deployment separate from active development. Gray's work on research-session strategy inference also received scrutiny: a session being deleted while inference was in flight exposed a locking race that needed correction before the work could be considered safe.

Those are easy details to overlook when attention is on the visible result. But the credibility of a generated paper depends on the reliability of the machinery beneath it: which evidence was used, whether work survived interruption, and whether concurrent operations could corrupt the state being summarized.

### Day 9 retrospective

Day 9 changed the standard for paper generation. Producing a PDF was only the beginning. The output needed to make sense to a reader, respect the project's evidence, fit the subject matter, and avoid exposing every internal detail as if it were a research result.

It also reinforced a broader lesson from the week: a feature that works under ideal conditions isn't finished if ordinary use makes it confusing or brittle. Progress reporting, timeouts, retries, and recovery aren't decorations around the research. They determine whether a person can trust the process enough to let it run.

We ended the day closer to a publishable account of SIGMA's work, but still with an important final evaluation ahead. I wanted the next round to be decisive, and I wanted to judge the papers by what they communicated—not merely by whether they compiled.
