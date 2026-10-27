# SIGMA

**Strategy Investigation, Generation, Measurement & Assessment**

SIGMA grew from an investigation into the Riemann Hypothesis and the idea that even an unsolved question should leave a useful, inspectable record of what was tried, what failed, and what remains unknown.

SIGMA is a local research workspace for turning a difficult question into trackable approaches, bounded AI research sessions, optional computational experiments, and inspectable evidence. Investigator and Skeptic roles examine selected strategies; SIGMA saves findings, objections, and unresolved questions so you can review and continue the work.

SIGMA helps organize an investigation; it does not establish that an answer is correct. Investigator and Skeptic currently use the same underlying model, so their structured challenge is not independent validation. Model agreement and computational results are evidence to inspect, not mathematical proof. The Riemann Hypothesis sample is an open problem, not a claimed solution. Whether persistent, multi-agent investigation produces better-supported research than a simpler assistant with comparable resources remains unproven; evaluating that proposition is part of SIGMA's purpose. See [Product Rationale](docs/PRODUCT_RATIONALE.md) for more context.

## SIGMA in use

Create a project or start from a sample, write or generate strategies, then choose strategies for a research session. Sessions run in bounded steps and can be paused or stopped. Review the Outcome alongside findings, objections, experiments, and open questions. Reports and exports preserve research records for inspection; they do not independently verify conclusions.

### Screenshots

**SIGMA Home** — start a new investigation or explore sample research projects.

![SIGMA Home page](assets/screenshot_home_page.png)

**Exploring multiple strategies to prove a theorem** — develop and compare different approaches to a mathematical problem, investigate their proof obligations, and preserve findings and unresolved questions.

![SIGMA strategies for a mathematical theorem](assets/screenshot_strategies.png)

## Run SIGMA locally

Requires **macOS or Linux**, **Python 3.11+**, **[uv](https://docs.astral.sh/uv/)**, and **Node.js 20.19+** with npm.

```sh
git clone https://github.com/bkramerext/sigma.git
cd sigma
./sigma setup
./sigma start --navigate
```

Open **http://127.0.0.1:5173** if the browser doesn't launch automatically. Press **Ctrl+C** to stop SIGMA. Projects are stored in `projects/` by default; set `SIGMA_PROJECTS_ROOT` to use another existing absolute directory.

You can create projects and strategies without an AI account. For AI research, use **Connect AI** with ChatGPT (subject to account limits), or configure a separately billed `OPENAI_API_KEY` in your server environment or the ignored `.env` file and restart.

### Optional features

- **Google sign-in testing:** Local use needs no administrator login. To test access controls, configure a Google OAuth web client with origin `http://127.0.0.1:5173` and callback `http://127.0.0.1:5173/api/cloud-auth/callback`. Set `GOOGLE_OIDC_CLIENT_ID` and `GOOGLE_OIDC_CLIENT_SECRET` in `.env`, then run:
  ```sh
  export SIGMA_CLOUD_ADMIN_CONTACT_EMAIL="you@gmail.com"
  ./sigma start --navigate --signin
  ```
  The first verified sign-in matching that address becomes the local administrator. Other users require access grants. Use a separate browser profile when testing invitations. Local auth state lives in `~/.sigma/local-cloud-auth`; hosted sign-in requires separate configuration. See [Cloud Deployment](docs/CLOUD_DEPLOYMENT.md).
- **Scientific Python experiments:** Build the optional sandbox with `docker build -t sigma-research-python:0.1 sandbox-poc`. See [Python Execution](docs/RESEARCH_PYTHON_EXECUTION.md) and [Sage Execution](docs/SAGE_EXECUTION.md) for setup and limits.

## Learn more

- [Getting Started](docs/GETTING_STARTED.md) — workflows and usage
- [Status](docs/STATUS.md) — features and known limits
- [Product Rationale](docs/PRODUCT_RATIONALE.md) and [Research Quality Charter](docs/RESEARCH_QUALITY_CHARTER.md) — goals and evidence standards
- [Cloud Deployment](docs/CLOUD_DEPLOYMENT.md) — hosted setup
- [Software Factory](docs/SOFTWARE_FACTORY.md) and [WOLF](WOLF.md) — how SIGMA is built through human-directed AI collaboration

Run `./sigma --help` for commands or `./sigma test` for local checks.
