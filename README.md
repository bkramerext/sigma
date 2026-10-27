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

## Local mock-auth walkthrough

The mock-auth selector is a development-only tool for manually inspecting the hosted identity UI without Google OAuth. It must only be used with a loopback development server. It is not an authentication method for deployment and does not emulate Google's identity verification or OpenAI inference.

Start the interactive mock sign-in walkthrough with `./sigma start --mock-auth --navigate`. The launcher enables mock mode only for its loopback child processes and disables local auto-admin. Do not combine `--mock-auth` with `--signin`.

For advanced manual configuration, set these variables in that checkout's ignored .env file:

```dotenv
SIGMA_CLOUD_AUTH_ENABLED=true
SIGMA_CLOUD_AUTH_LOCAL=true
SIGMA_MOCK_AUTH=1
SIGMA_CLOUD_PUBLIC_ORIGIN=http://127.0.0.1:5173
SIGMA_CLOUD_AUTH_HOME=/absolute/path/to/a/private/local/mock-auth-state
```

Use an absolute, user-owned directory with permissions restricted to the current user. Start SIGMA using the usual local development command and open http://127.0.0.1:5173. The Home page and project view show **MOCK AUTH · LOCAL ONLY** when the server confirms that all gates are satisfied.

Available identities are Guest, Member A, Member B, Administrator, and Uninvited. Selecting one replaces the current server-side session. Guest clears authenticated access; Uninvited opens the existing access-denied/invitation screen. Mock invitation requests are recorded locally and do not send email.

**Deterministic local simulation:** for a selected mock member, the walkthrough exposes simulated Personal or SIGMA-sponsored access, an allowance state (Available `$25`, Low `$1`, or Exhausted `$0`), and a provider state (Connected, Unavailable, or Error). These are fixture values saved for that mock identity; they do not query an account, consume or reserve hosted allowance, or contact a provider. Selecting SIGMA-sponsored plus Exhausted makes the mock research route end in a simulated allowance-exhausted failure. Selecting Provider Unavailable or Error makes it end in the corresponding simulated provider failure.

The mock research route supports one enabled saved strategy and a short deterministic session lifecycle: queued, simulated Investigator and Skeptic progress, then a result. With available simulated funding and a Connected simulated provider, it can create a clearly labeled, deliberately inconclusive fixture artifact. Exhaustion or provider failure creates no artifact. This exercises the local UI, persistence, status, and recovery flow; it is not AI inference, mathematical research, a test of real provider connectivity, or hosted sponsorship behavior. The browser walkthrough verifies the exhausted and unavailable cases; unit tests also cover the deterministic completed and failure outcomes.

To prevent real charges, mock mode routes the UI's research start through this provider-free simulation. The ordinary research-execution start endpoint, `/api/ai/*`, `/api/cloud-research/*`, and project write endpoints outside the explicit safe-project and mock-route allowlist are denied by the server in mock mode. The mock scenario controls and research route also require the explicitly enabled same-origin loopback configuration. Do not treat the Connected state as a real connection, use mock allowance values as a billing estimate, or expect the hosted service, Google OAuth, or deployed behavior to be simulated. Never set these variables on a public or deployed server.
