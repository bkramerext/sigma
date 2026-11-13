# SIGMA

**Strategy Investigation, Generation, Measurement & Assessment**

**[See it in action](https://sigma-research.duckdns.org/)**

SIGMA is a **multi-user, collaborative research workspace** for exploring difficult questions with AI. Multiple researchers can work on **the same shared project**, contributing to its strategies, research sessions, findings, and papers rather than exchanging disconnected copies. Investigator and Skeptic agents examine competing approaches while SIGMA preserves evidence, objections, and open questions for the whole team. Research remains cost-conscious and inspectable.

This effort grew from an investigation into the Riemann Hypothesis and the idea that even an unsolved question should leave a useful, inspectable record of what was tried, what failed, and what remains unknown.

A SIGMA project contains a question, candidate strategies, research sessions, and saved evidence. During a session, Investigator and Skeptic roles examine selected strategies in bounded exchanges. SIGMA records findings, objections, unresolved questions, and available computational results so a person can inspect and continue the investigation. Research can involve multiple strategies, with evidence carried forward between steps and sessions.

SIGMA does **not** establish that an answer is correct. Investigator and Skeptic currently use the same underlying model; their exchange is structured criticism, not independent validation. Model agreement and computational results are evidence to examine, not mathematical proof. The Riemann Hypothesis sample is an open problem, not a claimed solution. Whether persistent multi-agent investigation produces better-supported research than a simpler assistant given comparable resources remains unproven. See [Product Rationale](docs/PRODUCT_RATIONALE.md) and [Research Quality Charter](docs/RESEARCH_QUALITY_CHARTER.md).

## Using SIGMA

**Explore without signing in:** Public visitors can open an immutable sample into a private, temporary browser-cookie workspace, create or edit their own drafts and strategies, inspect saved sample research and papers, and export their work. Their temporary projects appear only in their browser's **My Work**; they are not shared with other visitors. A guest workspace expires after eight hours of inactivity and may disappear earlier on a backend restart or if cookies are cleared. Export anything you want to keep. Starting research Sessions, generating Papers, asking model-backed Q/A, AI Markdown formatting, and Score/Rescore explain what they would do instead of invoking a model. Sign-in is **not required** to explore; Google sign-in and ChatGPT execution remain for authorized Members/Admins.

Create a project or start from a sample, then invite collaborators to investigate the question together. Everyone authorized for a shared project works with the **same ongoing research record**—strategies, sessions, evidence, and papers—across their own signed-in accounts. You can also work privately. The overview below shows how SIGMA preserves findings and can optionally develop saved research into a paper. For session controls and limits, see [Connect AI and investigate](docs/GETTING_STARTED.md#connect-ai-and-investigate).

## Workflow

<p align="center"><img src="assets/workflow.svg" alt="SIGMA workflow: Project → Strategies → Research → Refine → Optional paper → Review/export" width="75%" /></p>

- **Create a project:** Choose a subject or sample and frame the question.
- **Collaborate on the same project:** Add other Google-account users in Project Settings → Collaborators. They see the shared project in **My Work** and contribute to its research rather than working on separate copies.
- **Explore strategies:** Develop approaches to the question and select which to investigate.
- **Run research:** Investigator and Skeptic examine selected strategies; SIGMA saves findings, evidence, objections, and open questions.
- **Review and refine:** Inspect sessions, the Outcome, and Current Understanding. Revise strategies or run more sessions when useful; research can be iterative.
- **Draft a paper (optional):** SIGMA can synthesize saved research into an academic draft. A draft is not proof or independent verification.
- **Review and export:** Export research records and reports for inspection or sharing, with no paper required. If you create a paper, review its claims, evidence, citations, and limitations before exporting PDF or TeX. You decide whether and where to share or publish a paper; SIGMA does not submit papers to journals.

## Collaborate with other researchers

SIGMA supports **multiple people working on one project**. A project owner can invite collaborators by their Google account email addresses in **Project Settings → Collaborators**. Invited users sign in with their own accounts and find the shared project under **My Work**, marked with a collaboration icon. An invitation email provides a direct link to the project when a public SIGMA URL is configured.

A collaborator works in the owner's shared project, not a fork or emailed snapshot. Authorized participants can inspect and build upon the same project question, strategies, research history, and generated papers. Changes are attributed to the owner or collaborator who made them. Project changes are saved as they are made; returning to the project shows its latest saved state.

Access is controlled by verified Google sign-in and project membership. The owner can remove any collaborator; a collaborator can remove only collaborators they added. SIGMA checks revisions to reject conflicting or stale edits, and coordinates execution so simultaneous users do not run conflicting research or paper work on the same project.

**Private projects are still supported.** You can use SIGMA locally without Google sign-in; authenticated collaboration requires the local or hosted deployment to be configured for Google-based accounts. Sharing access to a project is different from exporting or emailing a copy.

SIGMA supports ordinary local use without a Google account, local testing of Google-authenticated access, and a separately configured hosted deployment. Hosted access, membership, and provider funding depend on the deployment's configuration; a local launch does not automatically connect to the hosted service.

## Example Outcome Papers

These papers are **proofs of concept**, demonstrating what SIGMA can produce today rather than its intended final quality. Research and paper authoring remain works in progress; further improvements to SIGMA are expected to improve the clarity, rigor, and presentation of future papers. **These examples are experimental AI-generated work, not independently verified publications.** Eight papers are available now, including the six reference research papers, Maximum Regions by Lines, and Operation Narrow Passage; a ninth literature example is coming soon. Each available PDF is accompanied by its TeX source, with both archived under `papers/`.

<table>
<tr>
<td width="33%" valign="top"><p><sub><img src="papers/icons/mathematics.svg" width="18" height="18" alt="" /></sub> <strong>Mathematics · Easy</strong></p><p><strong><a href="https://cdn.jsdelivr.net/gh/bkramerext/sigma@main/papers/maximum-regions.pdf">Maximum Regions by Lines</a></strong> · <a href="https://github.com/bkramerext/sigma/raw/refs/heads/main/papers/maximum-regions.tex?download=1">Download TeX</a></p><p>A geometric proof of the maximum regions formed by lines.</p></td>
<td width="33%" valign="top"><p><sub><img src="papers/icons/mathematics.svg" width="18" height="18" alt="" /></sub> <strong>Mathematics · Hard</strong></p><p><strong><a href="https://cdn.jsdelivr.net/gh/bkramerext/sigma@main/papers/nonconsecutive-subset-sums-modulo-3-golden5.pdf">Nonconsecutive Subset Sums Modulo 3</a></strong> · <a href="https://github.com/bkramerext/sigma/raw/refs/heads/main/papers/nonconsecutive-subset-sums-modulo-3-golden5.tex?download=1">Download TeX</a></p><p>Exact counts and a corrected identity; the recurrence remains unproved.</p></td>
<td width="34%" valign="top"><p><sub><img src="papers/icons/physics.svg" width="18" height="18" alt="" /></sub> <strong>Physics · Hard</strong></p><p><strong><a href="https://cdn.jsdelivr.net/gh/bkramerext/sigma@main/papers/warp-drive-design-golden5.pdf">Warp Drive Design</a></strong> · <a href="https://github.com/bkramerext/sigma/raw/refs/heads/main/papers/warp-drive-design-golden5.tex?download=1">Download TeX</a> · <a href="https://raw.githubusercontent.com/bkramerext/sigma/c835a4e54c122c43781efa6bb68c89223ce44908/assets/warp_drive_q_a_no_x.png">Research Q/A example</a></p><p>General-relativistic shift-bubble analysis, without claiming practical propulsion.</p></td>
</tr>
<tr>
<td width="33%" valign="top"><p><sub><img src="papers/icons/computing.svg" width="18" height="18" alt="" /></sub> <strong>AI systems · Hard</strong></p><p><strong><a href="https://cdn.jsdelivr.net/gh/bkramerext/sigma@main/papers/agent-reliability-v1-golden5.pdf">Agent Reliability v1</a></strong> · <a href="https://github.com/bkramerext/sigma/raw/refs/heads/main/papers/agent-reliability-v1-golden5.tex?download=1">Download TeX</a></p><p>Distinguishing real agent actions from convincing reports, and testing recovery guarantees.</p></td>
<td width="33%" valign="top"><p><sub><img src="papers/icons/computing.svg" width="18" height="18" alt="" /></sub> <strong>AI systems · Hard</strong></p><p><strong><a href="https://cdn.jsdelivr.net/gh/bkramerext/sigma@main/papers/sovereign-ai-federation-v2-golden5.pdf">Sovereign AI Federation v2</a></strong> · <a href="https://github.com/bkramerext/sigma/raw/refs/heads/main/papers/sovereign-ai-federation-v2-golden5.tex?download=1">Download TeX</a></p><p>Sharing university AI capacity while preserving data authority and spending controls.</p></td>
<td width="34%" valign="top"><p><sub><img src="papers/icons/physics.svg" width="18" height="18" alt="" /></sub> <strong>Physics · Hard</strong></p><p><strong><a href="https://cdn.jsdelivr.net/gh/bkramerext/sigma@main/papers/when-does-qubit-decoherence-require-a-non-markovian-model-v1-v1.pdf">Qubit Decoherence and Non-Markovian Models</a></strong> · <a href="https://github.com/bkramerext/sigma/raw/refs/heads/main/papers/when-does-qubit-decoherence-require-a-non-markovian-model-v1-v1.tex?download=1">Download TeX</a></p><p>When coherence decay can distinguish memory effects from alternatives.</p></td>
</tr>
<tr>
<td width="33%" valign="top"><p><sub><img src="papers/icons/biology.svg" width="18" height="18" alt="" /></sub> <strong>Biology · Hard</strong></p><p><strong><a href="https://cdn.jsdelivr.net/gh/bkramerext/sigma@main/papers/xenopus-tadpoles-v9-golden5.pdf">Xenopus Tadpoles</a></strong> · <a href="https://github.com/bkramerext/sigma/raw/refs/heads/main/papers/xenopus-tadpoles-v9-golden5.tex?download=1">Download TeX</a></p><p>Why tail regeneration fades during development; evidence and open questions.</p></td>
<td width="33%" valign="top"><p><sub><img src="papers/icons/military.svg" width="18" height="18" alt="" /></sub> <strong>Military planning · Hard</strong></p><p><strong><a href="https://cdn.jsdelivr.net/gh/bkramerext/sigma@main/papers/operation-narrow-passage.pdf">Operation Narrow Passage</a></strong> · <a href="https://github.com/bkramerext/sigma/raw/refs/heads/main/papers/operation-narrow-passage.tex?download=1">Download TeX</a></p><p>Competing objectives and uncertainty in a fictional crisis.</p></td>
<td width="34%" valign="top"><p><sub><img src="papers/icons/literature.svg" width="18" height="18" alt="" /></sub> <strong>Literature · Hard</strong></p><p><strong>The Crucible: Early American Culture and Authorship</strong> · <em>Coming soon...</em></p><p>Miller’s Salem drama as a lens on early American culture, his influences, and artistic intentions.</p></td>
</tr>
</table>

## Screenshots

**Home** — start an investigation or explore sample projects.

![SIGMA Home page](assets/screenshot_home_page.png)

**Strategies** — compare approaches to a mathematical question and preserve their outstanding obligations.

![SIGMA strategies for a mathematical theorem](assets/screenshot_strategies.png)

## Research loop

A research **session** runs selected strategies through **rounds** of Investigator/Skeptic **turns**. Each turn pairs one Investigator proposal with one Skeptic critique; later turns and rounds can use selected earlier findings and objections. The default configuration allows up to **54 agent calls** across 3 rounds, 3 turns per strategy per round, and 3 strategies. See [Information Flow](docs/INFORMATION_FLOW.md) for how work and evidence move between turns, rounds, and strategies—and how Session Outcome and Current Understanding summarize the results.


## Run locally

Requires **macOS or Linux**, **Python 3.11+**, **uv**, and **Node.js 20.19+** with npm.

~~~sh
git clone https://github.com/bkramerext/sigma.git
cd sigma
./sigma setup
./sigma start --navigate
~~~

Open **http://127.0.0.1:5173** if needed. Manual project editing works without Google or AI sign-in. Local Google OAuth, personal and sponsored ChatGPT, optional API-key billing, macOS Keychain, sending email, spending limits, and diagnostics are documented in **[Local Hosting](docs/LOCAL_HOSTING.md)**.

**Installation documentation disclaimer:** The Local Hosting guide has **not been retested end to end** on a clean installation and must be maintained as setup and authentication change.

## Documentation

- [Local Hosting](docs/LOCAL_HOSTING.md) — complete local installation, identities, AI providers, secrets, email and troubleshooting (not clean-install retested)
- [Getting Started](docs/GETTING_STARTED.md) — workflows, setup, and troubleshooting
- [Journal](docs/JOURNAL.md) — day-by-day story of building SIGMA
- [Product Rationale](docs/PRODUCT_RATIONALE.md) and [Research Quality Charter](docs/RESEARCH_QUALITY_CHARTER.md) — research goals and evidence standards
- [Research and Writing Reference Scores](docs/REFERENCE_SCORES.md) — all 28 curated reference links, selection scores, and remaining limitations; see [Reference Curation Audit](docs/REFERENCE_CURATION.md) for detailed assessments
- [Cloud Deployment](docs/CLOUD_DEPLOYMENT.md) and [Deployment Runbook](docs/DEPLOYMENT_RUNBOOK.md) — hosted configuration and release procedure
- [Local Mock Authentication](docs/LOCAL_MOCK_AUTH.md) — developer-only account and provider-state simulation
- [Software Factory](docs/SOFTWARE_FACTORY.md) and [WOLF](WOLF.md) — human-directed development process

Run `./sigma --help` for commands or `./sigma test` for local checks.

Release notes: [v0.1.6 Initial Preview and v0.1.7 Reliability and Access Improvements](docs/RELEASE_NOTES.md).
