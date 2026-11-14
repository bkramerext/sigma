# Getting Started with SIGMA

SIGMA is a local workspace for investigating difficult questions with multiple research strategies, AI agents, computational experiments, and inspectable evidence.

## Install and start

Local installation, prerequisites, startup, Google sign-in, personal and sponsored ChatGPT credentials, API keys, macOS Keychain, local spending guards, and troubleshooting are documented together in **[Local Hosting](LOCAL_HOSTING.md)**. The consolidated local-hosting procedure is **not yet retested end to end** and should be maintained as implementation changes.

From an already cloned and configured local checkout:

~~~sh
./sigma setup
./sigma start --navigate
~~~

Open **http://127.0.0.1:5173** if needed. Press **Ctrl+C** to stop or run `./sigma shutdown` in another terminal. Manual project editing does not require an AI connection.

To open the two-agent chat directly, run `./sigma chat`. It uses the selected
ChatGPT or API-key connection. Send a human message to start; AI #1 and AI #2
then alternate until you stop the exchange or send another human message.
The Model and Thinking pills show the settings for this chat. They cycle through
models verified for the selected account and the reasoning levels supported by
the selected model. A new chat starts with the verified default model and Low
thinking. The active transcript's full path appears in the chat window; messages
are appended to a private, timestamped Markdown file in SIGMA's state directory
with a `YYYYMMDD_HHMMSS` timestamp and no ID in the filename. The transcript is not saved as a SIGMA
project. These chat settings are separate from project settings and are reset
to the account's defaults when the chat page is reopened.
The **Repeated** field at the top of the page optionally prepends the same text
to each AI #1 and AI #2 request. Changes apply to subsequent turns, including
turns later in an active exchange; repeated text is not added to the transcript.

## Start a project

Home offers **Samples** and **Recent** projects. Choose a sample to create your own editable copy, reopen a recent project, or select **New Project** to enter a title, research problem, research type, and difficulty.

The project workspace organizes your question, **research sessions**, and **strategies**. Expand or collapse sections to focus on the work. Edit project details and limits through the project controls and **Settings**. Changes to a sample copy do not alter the shipped sample.

A **strategy** is a bounded research approach, not an attempt to solve the entire project in one step. Use **New** to write one, or **Generate** to request an AI proposal. Review the proposed approach before saving it. Strategies persist across sessions; a failed investigation does not erase the strategy or its evidence. You can revise, disable, remove from the active pool, or fork strategies where the UI offers those actions.

Generated strategies identify a promising direction, the reasoning behind it, and an initial test with local success and failure criteria. Generation normally uses two model calls for an initial proposal and independent review; the project's model-call setting is a ceiling, not a target. The 50,000-character approach limit is a storage bound, not a generation target. Detailed evidence gathering and rigorous investigation belong in research sessions.

## Connect AI and investigate

Select **Connect AI** to continue with ChatGPT. Eligible usage depends on your account and plan limits. You may explicitly choose **API-key billing** instead; it is separately billed, and SIGMA never silently switches between the two modes. Manual project and strategy editing works without AI.

Select enabled strategies, then start a session. **v2 hierarchy:** `Session → research round → turn per strategy → Investigator call → Skeptic call`. A **turn** is one Investigator/Skeptic pair (for example, **Turn 2 of 3** within a round); the saved **cycle** counts these turn slots, **not** research rounds. Strategies may progress concurrently, but the two calls within a turn are sequential. Defaults: `3 rounds × 3 turns/round × 3 strategies × 2 calls/turn = 54` **maximum** calls; stopping and budgets may reduce this. Session controls let you inspect, pause, stop, or revisit work.

Turns can produce saved findings, evidence, objections, unresolved obligations, and next questions; a turn does not necessarily yield an accepted finding. Later turns and rounds receive **bounded selections** of earlier local and peer evidence, **not necessarily full artifacts**; originals remain saved. Agents are prompted to check peer assumptions and address prior criticism, but their assessments are unverified. At each completed scheduling **wave**, SIGMA records a portfolio review; **there is no separate round-end merge**. Further rounds allow new tests to build on objections, but the scheduler enforces order, limits, and persistence—not improved reasoning.

**Concurrent research:** Project Settings → Limits controls the maximum number of active sessions in that project, including queued sessions. With a limit above one, you can start or resume another session while one is already running, even from another browser window. Different projects and signed-in users have independent research workspaces. On the hosted service, worker and queue capacity are also bounded per user and globally (defaults: 2 running and 4 queued per user, 4 running and 16 queued globally). A session waiting for a worker remains queued without dispatching or billing a provider call; account allowances and global spending ceilings still apply. The hosting operator can override these capacities with `SIGMA_CLOUD_*_MAX_CONCURRENT` and `SIGMA_CLOUD_*_MAX_QUEUED` settings. Existing server-side environment overrides take precedence over the defaults.

The **Session Outcome** summarizes the session's results and remaining uncertainty, including partial or negative findings. Compare it with the saved artifacts, objections, and experiments; neither agent agreement nor a numerical test independently proves a claim.

## Reports and exports

Use the workspace's **Report / Export** actions to create a complete, importable project file or readable text/HTML reports. The project file contains the project and its saved research history, evidence, and artifacts in one JSON bundle; use **Import Project** to restore it. For AI-authored TeX papers, SIGMA can use staged long-form generation for large evidence snapshots. The dialog shows provider-use bounds before you start; progress, cancellation, and resumable checkpoints are available. A paper preserves the exported Outcome and underlying research records, including any saved reasoning and optional conclusion. Review its omission warnings, objections, limitations, and verification status before relying on it. When material evidence is omitted, the paper marks conclusions provisional and does not leave affected claims established. Missing Outcome conclusions are not invented. Reports communicate findings, not independent verification.

The optional **Issues and Bugs** paper section records problems observed in SIGMA's own generation and typesetting process, including repairs and unresolved layout diagnostics. It excludes defects in the input research and does not prevent SIGMA from saving a paper if the optional section itself cannot compile.

To curate and publish a complete research project as a bundled **Sample snapshot**,
export its Project file (not the Project Audit JSON), then run from a local Git
checkout:

```sh
./sigma make_sample ~/Downloads/sovereign-ai-v12.bundle.json
```

The command strips a trailing version suffix (such as `v12`) from the sample
title, matches the existing catalog entry by title or derives a new identifier,
and replaces that sample's source-controlled snapshot. `--name` is an optional
override. It commits **only `samples/<identifier>/`** on the current branch; it
does not push, deploy, or commit the source export or unrelated staged work.
Stop any active sessions before exporting; inspect the resulting commit before
pushing. Publishing requires a configured local Git author identity.

Curated samples are marked ★ on Home's **Samples** tab regardless of paper
score. The star opens a selected published paper, and opening the sample creates
an independent working project with its complete saved sessions, papers, TeX,
PDFs, and frozen evidence. Original model names, thinking levels and scores
remain intact; the original Google account's execution attribution is removed
from copied metadata. Cited scientific authors are not removed from paper
content. No paid model calls are made during promotion. Legacy uncurated samples
continue to work.

## Optional computational experiments

Research agents can execute scientific Python in a locally prepared, isolated Docker container. To enable that capability, install a working Docker-compatible runtime and build the image once:

```sh
docker build -t sigma-research-python:0.1 sandbox-poc
```

The runtime does not pull images during a research call. Computations run without network access or host project mounts and retain code, output, status, and provenance. For execution limits and security assumptions, see [Research Python Execution](RESEARCH_PYTHON_EXECUTION.md). SageMath requires separate optional setup; see [Sage Execution](SAGE_EXECUTION.md).

## Useful commands and troubleshooting

```sh
./sigma test                         # Offline checks; no paid AI calls
./sigma inspect projects/my-project.sigma
./sigma strategies projects/my-project.sigma
./sigma shutdown                     # Stop verified local SIGMA instances
```

New projects normally live in the repository's `projects/` directory. Set `SIGMA_PROJECTS_ROOT` to an existing absolute directory before launch to use a different location. Project data stays local; do not put credentials in project files.

The ordinary local app uses `SIGMA_STORAGE_BACKEND=local` (the default) and keeps its established project and state paths. To exercise the same authenticated, file-backed storage layout used with a GCE Persistent Disk on a local machine, use a private directory and set `SIGMA_STORAGE_BACKEND=persistent_disk` plus `SIGMA_STORAGE_ROOT` to its absolute path. The app derives its auth database and owner workspaces below that root and fails closed if authentication or the root is unsafe. No GCP resource is needed. A copy/paste fixture procedure, including two simulated Google subjects, backend restart, full-root restore, and the real Chrome workflow, is in [T100 local persistent-disk acceptance](evaluations/t100/README.md).

If **Connect AI** or generation fails, check the connection status and usage limits before retrying. For optional API-key billing, put `OPENAI_API_KEY` in the repository-root `.env` file or server environment and restart SIGMA. Never put secrets in frontend configuration.

For command and API details, see `./sigma --help` and the relevant technical docs. For active work and verification evidence, see [ticket tracking](TICKET_TRACKING.md), the active ticket, and the relevant PR handoff under `messages/`. The [Backlog](BACKLOG.md) tracks future ideas.

**Research integrity:** SIGMA is an investigation tool. Distinguish conjectures, computations, agent-reviewed arguments, and independently verified results. Its Riemann Hypothesis sample is not a claimed proof.
