# SIGMA

**Strategy Investigation, Generation, Measurement & Assessment**

SIGMA grew from an investigation into the Riemann Hypothesis and the idea that even an unsolved question should leave a useful, inspectable record of what was tried, what failed, and what remains unknown.

SIGMA is a local research workspace for turning a difficult question into trackable approaches, bounded AI research sessions, optional computational experiments, and inspectable evidence. Investigator and Skeptic roles examine selected strategies; SIGMA saves findings, objections, and unresolved questions so you can review and continue the work.

SIGMA helps organize an investigation; it does not establish that an answer is correct. Investigator and Skeptic currently use the same underlying model, so their structured challenge is not independent validation. Model agreement and computational results are evidence to inspect, not mathematical proof. The Riemann Hypothesis sample is an open problem, not a claimed solution. Whether persistent, multi-agent investigation produces better-supported research than a simpler assistant with comparable resources remains unproven; evaluating that proposition is part of SIGMA's purpose. See [Product Rationale](docs/PRODUCT_RATIONALE.md) for more context.

## SIGMA in use

Create a project or start from a sample, write or generate strategies, then choose strategies for a research session. Sessions run in bounded steps and can be paused or stopped. Review the Outcome alongside findings, objections, experiments, and open questions. Reports and exports preserve research records for inspection; they do not independently verify conclusions.

### Screenshots

The following owner-provided screenshots are pending. They will be placed here when supplied; no substitute images are included.

**SIGMA Home** — owner-provided screenshot pending.

<!-- Screenshot placement: SIGMA Home. Insert the owner-provided image here. -->

**Riemann Hypothesis investigation** — owner-provided screenshot pending.

<!-- Screenshot placement: Riemann Hypothesis investigation. Insert the owner-provided image here. -->

## Run SIGMA locally

The local development setup supports macOS and Linux. Install:

- Python 3.11 or newer
- [uv](https://docs.astral.sh/uv/)
- Node.js 20.19 or newer, with npm

Clone the repository, install the locked Python and frontend dependencies, and start the application:

```sh
git clone https://github.com/bkramerext/sigma.git
cd sigma
./sigma setup
./sigma start --navigate
```

SIGMA opens **http://127.0.0.1:5173** in your browser. If it does not, open that address yourself. Choose a sample or create a project. Press **Ctrl+C** in the terminal to stop both local servers; `./sigma shutdown` is also available. By default, projects live in the checkout's `projects/` directory. To use a different existing absolute directory, set `SIGMA_PROJECTS_ROOT` before starting SIGMA.

Manual project and strategy work does not require an AI account. To use AI, select **Connect AI** and continue with ChatGPT; eligible usage depends on your account and plan limits. You may instead choose API-key billing, which uses separately billed API usage. Put `OPENAI_API_KEY` in the repository-root `.env` file or the server environment, then restart SIGMA. Keep secrets out of frontend configuration and project files.

### Optional local Google administrator login and required sign-in testing

The ordinary local launch is single-user and does not require an administrator account. To exercise local Google sign-in and access management, configure a Google OAuth web client and bootstrap the first administrator:

1. Add `http://127.0.0.1:5173` as an authorized JavaScript origin and `http://127.0.0.1:5173/api/cloud-auth/callback` as an authorized redirect URI in the OAuth client.
2. Put the client ID and secret in the checkout's ignored `.env` file:

   ```dotenv
   GOOGLE_OIDC_CLIENT_ID=your-client-id.apps.googleusercontent.com
   GOOGLE_OIDC_CLIENT_SECRET=your-client-secret
   ```

3. In the same shell used to launch SIGMA, set `SIGMA_CLOUD_ADMIN_CONTACT_EMAIL` to the designated administrator's actual Google account and start SIGMA:

   ```sh
   export SIGMA_CLOUD_ADMIN_CONTACT_EMAIL="you@gmail.com"
   ./sigma start --navigate --signin
   ```

   `--signin` requires real Google sign-in and access authorization on localhost. It is useful for acceptance testing the Invite Me workflow with an unapproved Google account. The flag fails closed if OAuth client credentials or the administrator contact are missing. Without the flag, existing behavior remains unchanged, including automatic local Google auth when the administrator contact is configured. Use a separate browser profile to avoid reusing an administrator session.

   If you keep this setting in a shell startup file, load that file in the launching shell first. On a fresh local auth database, the first successful verified Google sign-in matching this address binds that account as administrator. Later changes to the contact address update invitation requests and preserve the existing administrator email and Google subject binding. Local auth data is stored under `~/.sigma/local-cloud-auth`; other users need an explicit access grant. This local setup does not administer a hosted SIGMA deployment.

For hosted setup, see [Cloud Deployment](docs/CLOUD_DEPLOYMENT.md). Hosted deployments require their own OAuth and administrator configuration; do not reuse the local loopback OAuth settings.

### JSON project regression and integration tests

The JSON project bundle and project creation simulations run on every pull
request through the JSON project regressions workflow. Run them locally with:

```sh
python3 scripts/test_t249_integration.py
```

To additionally verify real Docker-backed execution, binary artifacts,
export/import integrity, and interruption recovery, first build the sandbox
images described below, then run:

```sh
python3 scripts/test_t249_integration.py --docker
```

The runner does not modify Git history or push reports. Docker lifecycle
coverage is opt-in because it requires a running daemon and sandbox image.

### Optional scientific Python sandbox

Research sessions can use a local Docker-compatible runtime for isolated Python experiments. Build the pinned image once:

```sh
docker build -t sigma-research-python:0.1 sandbox-poc
```

This capability is optional. See [Research Python Execution](docs/RESEARCH_PYTHON_EXECUTION.md) for its limits and security assumptions, and [Sage Execution](docs/SAGE_EXECUTION.md) for separate SageMath setup.

## Project documentation

- [Getting Started](docs/GETTING_STARTED.md): product workflow and local usage
- [Status](docs/STATUS.md): implemented behavior, verification, and known limits
- [Product Rationale](docs/PRODUCT_RATIONALE.md): goals and assumptions behind SIGMA
- [Research Quality Charter](docs/RESEARCH_QUALITY_CHARTER.md): evidence and research-quality standards
- [Research Python Execution](docs/RESEARCH_PYTHON_EXECUTION.md): optional computation setup and boundaries
- [Cloud Deployment](docs/CLOUD_DEPLOYMENT.md): hosted deployment and identity configuration
- [Software Factory](docs/SOFTWARE_FACTORY.md): how SIGMA is developed and reviewed
- [WOLF](WOLF.md): the human-directed AI collaboration behind SIGMA

Run `./sigma --help` for CLI commands. Offline project and repository checks are available with `./sigma test`.

## About development

SIGMA is built through human-directed, AI-assisted software engineering. Brian sets product direction and evaluates the running application; ChatGPT and Codex contribute design, implementation, testing, and review. [WOLF](WOLF.md) describes this collaboration and distinguishes SIGMA's research agents from the engineering process used to build it.
