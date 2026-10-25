# SIGMA

**Strategy Investigation, Generation, Measurement & Assessment**

SIGMA grew from an investigation into the Riemann Hypothesis and the idea that even an unsolved question should leave a useful, inspectable record of what was tried, what failed, and what remains unknown.

The central proposition must withstand scrutiny: **does persistent, multi-agent investigation produce better-supported, more useful research than a simpler AI assistant operating with comparable resources?** That advantage has not been established. Testing it is part of SIGMA's purpose. And we're prepared to simplify SIGMA if the answer is no.

SIGMA is a local research workspace for turning a difficult question into a set of trackable approaches, bounded AI research sessions, experiments, and inspectable evidence. It helps you keep the useful parts of an investigation together: what was tried, what the agents challenged, what the experiments showed, and what is still unresolved.

SIGMA can use AI to help investigate a question, but it does not establish that an answer is correct. Model agreement and computational results are evidence to inspect, not mathematical proof. The Riemann Hypothesis sample is an open problem, not a claimed solution.

For more background on the research approach and its underlying rationale, see [Product Rationale](docs/PRODUCT_RATIONALE.md).

## SIGMA in use

Create a project or start from a sample, write or generate strategies, then choose strategies for a research session. Investigator and Skeptic roles work through bounded steps; SIGMA saves findings, objections, optional computation, and unresolved questions so you can review and continue the work. You remain in control of starting, pausing, stopping, and evaluating investigations.

AI can reformat plain-text project descriptions and saved Conclusions as Markdown with typeset equations. The saved text remains available; formatting does not verify the mathematics. Investigator and Skeptic currently use the same underlying model, so their structured challenge is not independent model validation. Different-model review is a potential future enhancement.

## Run SIGMA locally

SIGMA's local development setup supports macOS and Linux. Install:

- Python 3.11 or newer
- [uv](https://docs.astral.sh/uv/)
- Node.js 20.19 or newer, with npm

Clone the repository, enter it, then install the locked Python and frontend dependencies and start the application:

```sh
git clone https://github.com/bkramerext/sigma.git
cd sigma
./sigma setup
./sigma start --navigate
```

SIGMA opens **http://127.0.0.1:5173** in your browser. If it does not, open that address yourself. Choose a sample or create a project. Press **Ctrl+C** in the terminal to stop both local servers; `./sigma shutdown` is also available. The default project location is `projects/` in the checkout. To use another existing absolute directory, set `SIGMA_PROJECTS_ROOT` in the environment before starting SIGMA.

Manual project and strategy work does not require an AI account. To use AI, choose **Connect AI** in SIGMA and continue with ChatGPT; eligible usage depends on your account and plan limits. You may instead choose the optional API-key mode, which uses separately billed API usage. To configure that mode, put `OPENAI_API_KEY` in the repository-root `.env` file or the server environment, then restart SIGMA. Keep secrets out of frontend configuration and project files.

### Optional local Google administrator login

The usual local launch is single-user and does not require an administrator account. If you want to exercise local Google sign-in and access management, configure a Google OAuth web client and bootstrap the first administrator:

1. In the Google OAuth client, add `http://127.0.0.1:5173` as an authorized JavaScript origin and `http://127.0.0.1:5173/api/cloud-auth/callback` as the authorized redirect URI.
2. Put the client ID and secret in the checkout's ignored `.env` file:

   ```dotenv
   GOOGLE_OIDC_CLIENT_ID=your-client-id.apps.googleusercontent.com
   GOOGLE_OIDC_CLIENT_SECRET=your-client-secret
   ```

3. In the same shell you will use to launch SIGMA, set `SIGMA_CLOUD_BOOTSTRAP_ADMIN_EMAIL` to the operator's actual Google account, then start SIGMA:

   ```sh
   export SIGMA_CLOUD_BOOTSTRAP_ADMIN_EMAIL="you@gmail.com"
   ./sigma start --navigate
   ```

   If you keep this setting in a shell startup file, load that file in the launching shell first. The first successful verified Google sign-in binds that account as administrator for this local installation. Local auth data is stored under `~/.sigma/local-cloud-auth`; other users need an explicit access grant. This local setup does not administer a hosted SIGMA deployment.

For hosted setup, see [Cloud Deployment](docs/CLOUD_DEPLOYMENT.md); do not reuse the local loopback OAuth settings for a hosted service.

### Optional scientific Python sandbox

Research sessions can use a local Docker-compatible runtime for isolated Python experiments. Build the pinned image once:

```sh
docker build -t sigma-research-python:0.1 sandbox-poc
```

This capability is optional. See [Research Python Execution](docs/RESEARCH_PYTHON_EXECUTION.md) for its limits and security assumptions, and [Sage Execution](docs/SAGE_EXECUTION.md) for separate SageMath setup.

## Project documentation

- [Getting Started](docs/GETTING_STARTED.md): product workflow and local usage
- [Status](docs/STATUS.md): implemented behavior, verification, and known limits
- [Research Quality Charter](docs/RESEARCH_QUALITY_CHARTER.md): evidence and research-quality standards
- [Research Python Execution](docs/RESEARCH_PYTHON_EXECUTION.md): optional computation setup and boundaries
- [Cloud Deployment](docs/CLOUD_DEPLOYMENT.md): hosted deployment and identity configuration
- [Software Factory](docs/SOFTWARE_FACTORY.md): how SIGMA is developed and reviewed
- [WOLF](WOLF.md): narrative about SIGMA's multi-agent system and engineering

Run `./sigma --help` for CLI commands. The offline project checks are available with `./sigma test`.

## How SIGMA is built

SIGMA is developed through human-directed, AI-assisted software engineering (sometimes informally called “vibe coding”). Brian sets product direction and evaluates the running application; ChatGPT and Codex contribute design, implementation, testing, and review. [WOLF](WOLF.md) describes this collaboration.
