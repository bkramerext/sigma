# Local mock-auth walkthrough

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
