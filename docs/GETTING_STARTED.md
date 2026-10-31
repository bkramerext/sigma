# Getting Started with SIGMA

SIGMA is a local workspace for investigating difficult questions with multiple research strategies, AI agents, computational experiments, and inspectable evidence.

## Install and start

On macOS or Linux, install Python 3.11+, [uv](https://docs.astral.sh/uv/), Node.js 20.19+, and npm. From the repository root:

```sh
./sigma setup
./sigma start
```

Open **http://127.0.0.1:5173** if the browser does not open automatically. Stop SIGMA with **Ctrl+C**, or use `./sigma shutdown` from another terminal. Running `./sigma start` again replaces a verified local instance; unrelated services using the ports are left alone.

For an eligible Google account, normal `./sigma start` sign-in selects
sponsored mode by default. The pill shows the remaining allowance from the
local sponsored ledger. Sponsored inference uses SIGMA's designated
`zetacontinuation@gmail.com` ChatGPT account, never the signed-in member's
ChatGPT session. For local use, SIGMA reads that account from the private
`SIGMA_AUTH_HOME` store and pins it to the designated sponsor email. Local
spend is reserved against the signed-in member's configured allowance before
provider dispatch. Local sponsored inference selects ChatGPT when
`SIGMA_CLOUD_INFERENCE_PROVIDER` is unset. Local sponsored research has a bounded **$50-per-UTC-calendar-month shared
API-rate-equivalent ceiling** when no explicit global ceiling is configured.
Past months' settled usage no longer consumes the new month's allowance;
unresolved reserved and unknown provider calls remain held until reconciled.
This is separate from each member's individual allowance, which remains subject
to its own configured accounting or an administrator-approved reload.

To inspect durable spending obligations without exposing account identities:

```sh
uv run --locked --no-sync python scripts/inspect_cloud_spend.py
```

The diagnostic shows the full historical ledger; it does not establish which
configuration the running backend actually uses. A connected ChatGPT account
may separately reach a provider plan/app usage limit; changing the SIGMA
ceiling cannot bypass it.

An operator-set `SIGMA_CLOUD_GLOBAL_SPEND_CEILING_USD` overrides the local
default and is **cumulative unless `SIGMA_CLOUD_GLOBAL_SPEND_WINDOW=calendar_month`
is explicitly selected**. For example, after approving a $5 *cumulative*
local ceiling:

```sh
SIGMA_CLOUD_GLOBAL_SPEND_CEILING_USD=5.00 ./sigma start
```

The ledger is never reset by changing these settings. A production-hosted
deployment also defaults to cumulative global spend accounting unless the
operator explicitly configures a different window. Changes to actual API
billing exposure still require the operator's approval; a SIGMA allowance
does not provide provider-side payment authorization.

If the operator provisions a dedicated
SIGMA-sponsored OpenAI API service key, local sponsored Play can instead use:

```bash
SIGMA_CLOUD_INFERENCE_PROVIDER=api_key
SIGMA_CLOUD_OPENAI_API_KEY_FILE=/absolute/path/to/sigma-sponsored-api-key
./sigma start
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
In sponsored mode, **Project Settings → Limits** controls session duration,
call, round, and estimated-cost limits. Sponsorship governs money allowance
only; member and configured global spend ceilings are enforced before each call.
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
`credential_missing` means the server has no usable sponsor session. Only a
verified local administrator can renew the shared sponsor credential through
the admin-only `/api/ai/sponsor-auth/begin` maintenance flow. The member-facing
Sponsored ChatGPT pill never starts that flow. A sponsored member is not asked
to authorize or reconnect the sponsor account. The OAuth flow is bound to
SIGMA's saved sponsor account. The same log records
`sponsor_oauth status=started`, then `connected`, `failed`, or `cancelled` so
the operator can tell whether renewal completed. A member's Google sign-in
alone does not renew the server's sponsor credential. Clicking **Sponsored
ChatGPT** starts authorization for the user's own personal ChatGPT account.
After connection, the pill reads **Disconnect from ChatGPT**; disconnecting
returns to sponsored mode without changing shared sponsor credentials. If
personal authorization fails or is cancelled, **Connect to ChatGPT** remains
available and the selected funding mode is preserved.

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

**Concurrent research:** Project Settings → Limits controls the maximum number of active sessions in that project, including queued sessions. With a limit above one, you can start or resume another session while one is already running, even from another browser window. Different projects and signed-in users have independent research workspaces. On the hosted service, worker and queue capacity are also bounded per user and globally (defaults: 2 running and 4 queued per user, 4 running and 16 queued globally). A session waiting for a worker remains queued without dispatching or billing a provider call; account allowances and global spending ceilings still apply. The hosting operator can override these capacities with `SIGMA_CLOUD_*_MAX_CONCURRENT` and `SIGMA_CLOUD_*_MAX_QUEUED` settings. Existing server-side environment overrides take precedence over the defaults.

Review the **Outcome** and its conclusion alongside detailed findings, objections, experiments, and unresolved questions. A successful numerical test or agreement between agents is **not** a mathematical proof. SIGMA preserves partial and negative results so they can inform later investigations.

## Reports and exports

Use the workspace's **Report / Export** actions to create a complete, importable project file or readable text/HTML reports. The project file contains the project and its saved research history, evidence, and artifacts in one JSON bundle; use **Import Project** to restore it. For AI-authored TeX papers, SIGMA can use staged long-form generation for large evidence snapshots. The dialog shows provider-use bounds before you start; progress, cancellation, and resumable checkpoints are available. A paper preserves the exported Outcome and underlying research records, including any saved reasoning and optional conclusion. Review its omission warnings, objections, limitations, and verification status before relying on it. When material evidence is omitted, the paper marks conclusions provisional and does not leave affected claims established. Missing Outcome conclusions are not invented. Reports communicate findings, not independent verification.

To turn completed work into a reusable catalog sample, pass a complete Project
file bundle to `./sigma make_sample bundle.json --name my-sample`. The sample
keeps validated paper metadata, TeX, PDF bytes, research evidence, and
provenance. Project Audit JSON is a review view and contains no binary paper
files; converting that audit alone cannot restore PDFs.

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
