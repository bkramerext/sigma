# SIGMA Personal ChatGPT Companion — prototype

This is an **experimental connection test** for a production-compatible
architecture, not a finished production feature. OpenAI's existing loopback
account chooser runs in a separate desktop process. The website never receives
the user's ChatGPT access or refresh token, and the companion must stay online
during Personal inference. No new OAuth client approval is requested.

**End users will not clone SIGMA.** Distribute a standalone, signed/notarized
companion app from SIGMA's trusted Downloads page after it passes security
review. A manual GitHub Actions workflow builds an unsigned **prototype**
macOS executable and uploads an artifact for development validation.
Do not direct ordinary users to clone a repository, run a Python module, or
bypass macOS security warnings. The current prototype is not user-release-ready.

## Local developer reproduction

Start ordinary SIGMA and confirm Personal ChatGPT behaves as it always did.
Then stop it and run:

```sh
./sigma start --prod --signin --navigate
```

Sign in to SIGMA with Google and select Personal in the **existing** pill.
Click the Personal ChatGPT pill to open the companion pairing dialog.
Create a pairing code. The code is single-use and expires after three minutes.

In a **second local terminal**, use the companion entry point installed from
your development environment:

```sh
sigma-personal-companion --server http://127.0.0.1:5173 --code '<CODE_FROM_UI>' --choose-account
```

For a packaged build, run that standalone executable instead. The companion
opens OpenAI's existing account chooser in a browser and receives its
`127.0.0.1` callback directly. It stores credentials under
`~/.config/sigma-personal-companion` (mode 0700), not in ordinary
`~/.config/sigma`, the SIGMA repository, or SIGMA's cloud storage.

The dialog should show the companion as connected. Submit a small test prompt.
The server queues the request for that Google user; the companion fetches it,
uses a model allowed by the selected ChatGPT plan, and returns only the answer.
No provider token is transmitted to SIGMA. SIGMA's backend cannot make direct
Personal provider requests in the `--prod` experiment.

Restart without `--prod` to confirm existing localhost personal connections
are unchanged.

## Prototype safety and limitations

- The server's queue and paired-worker state are **in memory**, intentionally
  limited to a single backend process. Restarting clears its pairing state.
  These routes must not be enabled on real production until persistent,
  fenced, per-user dispatch and full identity/transport review are complete.
- This is a **single-turn test path**, not yet integrated into SIGMA research
  Sessions, papers, full model selection or durable resumability.
- A dispatched request remains marked **dispatched** if the companion
  disconnects. It is never silently replayed, and re-pairing revokes the
  prior companion's routing capability.
- Each new pairing code is random, one-use, and short lived. The bearer is
  used only for companion requests and exists in process memory. Never place
  it, a provider token, or a raw OAuth callback URL in logs or GitHub.
- Hosted usage requires **HTTPS**. The prototype allows HTTP only for
  `127.0.0.1`/localhost development. There is no hosted OAuth callback.
- The companion identity label is reported by the paired worker, not
  independently verified by SIGMA's server. A production design must
  strengthen signed provider-identity attestation before presenting it as
  provider-verified.
- No credential upload, sponsorship fallback, API key substitution, or
  OpenAI permission application is involved.
- A packaged macOS build is currently unsigned. It is for development
  inspection only; do not distribute it to nontechnical end users until
  signed, notarized, and published through the trusted site.
