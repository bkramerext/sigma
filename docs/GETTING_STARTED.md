# Getting Started with SIGMA

SIGMA is a local workspace for investigating difficult questions with multiple research strategies, AI agents, computational experiments, and inspectable evidence.

## Install and start

On macOS or Linux, install Python 3.11+, [uv](https://docs.astral.sh/uv/), Node.js 20.19+, and npm. From the repository root:

```sh
./sigma setup
./sigma start
```

Open **http://127.0.0.1:5173** if the browser does not open automatically. Stop SIGMA with **Ctrl+C**, or use `./sigma shutdown` from another terminal. Running `./sigma start` again replaces a verified local instance; unrelated services using the ports are left alone.

To preview sponsored mode locally for the Google account you sign in with, run
`./sigma start --sponsored`. For eligible accounts, the pill shows the
remaining allowance from the local sponsored ledger and forces sponsored
provider selection. Sponsored inference uses SIGMA's designated
`zetacontinuation@gmail.com` ChatGPT account, never the signed-in member's
ChatGPT session. For local use, SIGMA reads that account from the private
`SIGMA_AUTH_HOME` store and pins it to the designated sponsor email. Local
spend is reserved against the signed-in member's configured allowance before
provider dispatch. Local sponsored inference selects ChatGPT when
`SIGMA_CLOUD_INFERENCE_PROVIDER` is unset. If the operator provisions a dedicated
SIGMA-sponsored OpenAI API service key, local sponsored Play can instead use:

```bash
SIGMA_CLOUD_INFERENCE_PROVIDER=api_key
SIGMA_CLOUD_OPENAI_API_KEY_FILE=/absolute/path/to/sigma-sponsored-api-key
./sigma start --sponsored
```

The key file must contain the sponsored project's API key. A direct
`SIGMA_CLOUD_OPENAI_API_KEY` environment variable is also supported, but do not
set both sources. SIGMA does not use the personal `OPENAI_API_KEY` for sponsored
calls. The operator must confirm the sponsored API project's billing and usage
limits before supplying this key; API usage is billed separately from a ChatGPT
plan. To roll back local service-key routing, unset
`SIGMA_CLOUD_INFERENCE_PROVIDER` and the dedicated key setting, then restart.
An account with only `$0.01` remaining may still be unable to start a call:
the server reserves a conservative, model-specific amount before each provider
request and never exceeds the member's allowance.
In local sponsored mode, **Project Settings → Limits** keeps the saved project
call allowance (up to 30 calls); the hosted six-call cap does not apply. Local
sponsored sessions remain capped at 15 minutes and $0.25 per session, with the
member's remaining account allowance enforced separately before each call.
Hosted deployments retain their own provider setting. The option does not
enable the hosted forced-sponsored setting. Use `./sigma start` to return to
normal local mode.

If sponsored Play is temporarily unavailable, the signed-in member's research
is preserved. The backend reports token-free status codes in the private,
bounded `sponsor-diagnostics.log` file at the checkout root. Run
`tail -n 30 sponsor-diagnostics.log` there to read the latest entries. The
`sponsor_play` event shows whether the start request was accepted or rejected;
`sponsor_inference` records call start, provider HTTP status, completion, and
fixed failure categories. Endpoint-specific `sponsor_sessions_api`,
`sponsor_config_api`, `sponsor_limits_api`, and `sponsor_project_api` events
record failed project requests, including whether the error body was unusually
large. No prompt, response, provider message, identity, or credential is
written to this log.
`credential_missing` means the server has no usable sponsor session. The
eligible local member can click the sponsored pill to start the pinned sponsor
reconnect flow and complete ChatGPT sign-in as `zetacontinuation@gmail.com`;
local administrators can also start it from **Admin Settings**. The OAuth flow
is bound to SIGMA's saved sponsor account, and an eligible member cannot access
admin settings. The same log records
`sponsor_oauth status=started`, then `connected`, `failed`, or `cancelled` so
the operator can tell whether renewal completed. A member's Google sign-in
alone does not renew the server's sponsor credential. A failed personal
ChatGPT connection returns an eligible member to sponsored mode; only a
successful personal connection selects personal mode.

To test with mock identities and controls, use `./sigma start --mock-auth`.
The mock member's $25 allowance is simulated. For its sponsored presentation,
combine the options: `./sigma start --mock-auth --sponsored`.

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

Use the workspace's **Report / Export** actions to create a complete, importable project file or readable text/HTML reports. The project file contains the project and its saved research history, evidence, and artifacts in one JSON bundle; use **Import Project** to restore it. For AI-authored TeX papers, SIGMA can use staged long-form generation for large evidence snapshots. The dialog shows provider-use bounds before you start; progress, cancellation, and resumable checkpoints are available. A paper preserves the exported Outcome and underlying research records, including any saved reasoning and optional conclusion. Review its omission warnings, objections, limitations, and verification status before relying on it. When material evidence is omitted, the paper marks conclusions provisional and does not leave affected claims established. Missing Outcome conclusions are not invented. Reports communicate findings, not independent verification.

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

For command and API details, see `./sigma --help` and the relevant technical docs. For implemented behavior and known verification limits, see [Status](STATUS.md). The [Backlog](BACKLOG.md) tracks future ideas.

**Research integrity:** SIGMA is an investigation tool. Distinguish conjectures, computations, agent-reviewed arguments, and independently verified results. Its Riemann Hypothesis sample is not a claimed proof.
