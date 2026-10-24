# Getting Started with SIGMA

SIGMA is a local workspace for investigating difficult questions with multiple research strategies, AI agents, computational experiments, and inspectable evidence.

## Install and start

On macOS or Linux, install Python 3.11+, [uv](https://docs.astral.sh/uv/), Node.js 20.19+, and npm. From the repository root:

```sh
./sigma setup
./sigma start
```

Open **http://127.0.0.1:5173** if the browser does not open automatically. Stop SIGMA with **Ctrl+C**, or use `./sigma shutdown` from another terminal. Running `./sigma start` again replaces a verified local instance; unrelated services using the ports are left alone.

## Start a project

Home offers **Samples** and **Recent** projects. Choose a sample to create your own editable copy, reopen a recent project, or select **New Project** to enter a title, research problem, research type, and difficulty.

The project workspace organizes your question, **research sessions**, and **strategies**. Expand or collapse sections to focus on the work. Edit project details and limits through the project controls and **Settings**. Changes to a sample copy do not alter the shipped sample.

A **strategy** is a bounded research approach, not an attempt to solve the entire project in one step. Use **New** to write one, or **Generate** to request an AI proposal. Review the proposed approach before saving it. Strategies persist across sessions; a failed investigation does not erase the strategy or its evidence. You can revise, disable, remove from the active pool, or fork strategies where the UI offers those actions.

Generated strategies identify a promising direction, the reasoning behind it, and an initial test with local success and failure criteria. Generation normally uses two model calls for an initial proposal and independent review; the project's model-call setting is a ceiling, not a target. The 50,000-character approach limit is a storage bound, not a generation target. Detailed evidence gathering and rigorous investigation belong in research sessions.

## Connect AI and investigate

Select **Connect AI** to continue with ChatGPT. Eligible usage depends on your account and plan limits. You may explicitly choose **API-key billing** instead; it is separately billed, and SIGMA never silently switches between the two modes. Manual project and strategy editing works without AI.

Select the strategies you want to investigate, then start a **research session** using its controls. Investigator and Skeptic agents examine claims, challenge reasoning, and record evidence under bounded call and spending limits. Use the session controls to inspect progress, pause or stop work, and revisit earlier sessions. Available controls and limits depend on the current session state.

Review the **Outcome** and its conclusion alongside detailed findings, objections, experiments, and unresolved questions. A successful numerical test or agreement between agents is **not** a mathematical proof. SIGMA preserves partial and negative results so they can inform later investigations.

## Reports and exports

Use the workspace's **Report / Export** actions to produce audit data or readable reports in the formats offered by the dialog. For AI-authored TeX papers, SIGMA can use staged long-form generation for large evidence snapshots, with a preflight showing provider-call ceilings and explicit confirmation. Progress, cancellation, and resumable checkpoints are available. A paper preserves the exported Outcome and underlying research records, including any saved reasoning and optional conclusion. Review its omission warnings, objections, limitations, and verification status before relying on it. When material evidence is omitted, the paper marks conclusions provisional and does not leave affected claims established. Missing Outcome conclusions are not invented. Reports communicate findings, not independent verification.

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

If **Connect AI** or generation fails, check the connection status and usage limits before retrying. For optional API-key billing, put `OPENAI_API_KEY` in the repository-root `.env` file or server environment and restart SIGMA. Never put secrets in frontend configuration.

For command and API details, see `./sigma --help` and the relevant technical docs. For implemented behavior and known verification limits, see [Status](STATUS.md). The [Backlog](BACKLOG.md) tracks future ideas.

**Research integrity:** SIGMA is an investigation tool. Distinguish conjectures, computations, agent-reviewed arguments, and independently verified results. Its Riemann Hypothesis sample is not a claimed proof.
