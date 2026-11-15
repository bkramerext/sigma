# SIGMA Local Hosting

> **Maintenance and retest warning (November 13, 2026):** This guide consolidates the repository's existing local setup instructions and current implementation details, but **the complete procedure has NOT been retested from a clean installation**. Individual commands and paths may drift as SIGMA changes. Maintainers should keep this document current whenever startup, credentials, OAuth callbacks, sponsor authorization, spending controls, or local services change; verify it end to end on a fresh checkout and update this notice with the actual results. Do not treat a successful developer setup as clean-install acceptance.

This is the practical guide to running SIGMA on your own macOS or Linux machine. It is **not** a guide to deploying the public GCE service. For product usage after installation, see [Getting Started](GETTING_STARTED.md); for hosted operation, see [Cloud Deployment](CLOUD_DEPLOYMENT.md) and the [Deployment Runbook](DEPLOYMENT_RUNBOOK.md).


## Run locally

Requires **macOS or Linux**, **Python 3.11+**, **[uv](https://docs.astral.sh/uv/)**, and **Node.js 20.19+** with npm. SIGMA uses Zstandard-compressed project bundles; `./sigma setup` installs `zstd` via Homebrew (macOS) or apt (Debian/Ubuntu Linux) when it is missing. From a terminal:

```sh
git clone https://github.com/bkramerext/sigma.git
cd sigma
./sigma setup
./sigma start --navigate
```

If the browser does not open, visit **http://127.0.0.1:5173**. Press **Ctrl+C** in the launcher terminal to stop. The default project directory is `projects/`; set `SIGMA_PROJECTS_ROOT` to an **existing absolute directory** before starting to store projects elsewhere.

You can create projects and strategies without an AI connection. To use AI research, choose **Connect AI** for a ChatGPT connection (subject to account and provider limits), or set a separately billed `OPENAI_API_KEY` in the server environment or ignored `.env` and restart. **ChatGPT connection and Google sign-in are different:** the former supplies access to an inference provider; the latter identifies a SIGMA user for account and membership controls. Provider usage and billing are not included with a local installation.

`./sigma setup` installs the locked Python development environment with `uv sync --locked --group dev` and the frontend dependencies with `npm ci`. Earlier developer-worktree startup was reported as successful on macOS, but **this consolidated local-hosting procedure has not been clean-install retested**. See [Getting Started](GETTING_STARTED.md) for troubleshooting.

## Connection and identity choices

**Google sign-in and AI inference are separate.** Google OAuth signs a user into SIGMA and identifies their workspace, membership, and administrator role. Personal ChatGPT authorization provides an inference account selected by that user. Sponsored ChatGPT uses **a separately provisioned, SIGMA-owned sponsor credential** (which may happen to have the same email address as someone's personal ChatGPT connection). An API key uses **OpenAI Platform API billing**, separate from the ChatGPT subscription.

| Setting or resource | Local purpose | Required? |
| --- | --- | --- |
| `GOOGLE_OIDC_CLIENT_ID` and `GOOGLE_OIDC_CLIENT_SECRET` | Google's local web OAuth client for authenticated SIGMA sign-in and optional Gmail integration | Only for Google sign-in/Gmail |
| `SIGMA_CLOUD_ADMIN_CONTACT_EMAIL` | Google email designated as local SIGMA administrator and contact | Required for local administrator sign-in and related setup |
| `SIGMA_CLOUD_SPONSOR_EMAIL` | **Exact ChatGPT email of the designated sponsor**; validates the SIGMA-owned sponsor registration | Required for Sponsored ChatGPT, not for a personal connection |
| `SIGMA_AUTH_HOME` | Optional absolute private directory for the sponsor credential store; default is `~/.config/sigma` | Optional unless using a custom location |
| `SIGMA_CLOUD_INFERENCE_PROVIDER` | Sponsor's inference transport: `chatgpt` (local default) or explicitly `api_key` | Optional for default sponsored ChatGPT |
| `OPENAI_API_KEY` | Optional personal/direct API-key transport, billed on the OpenAI Platform | Only for direct API-key use |
| `SIGMA_CLOUD_OPENAI_API_KEY_FILE` / `SIGMA_CLOUD_OPENAI_API_KEY` | A **separate** dedicated key for API-key-backed SIGMA sponsorship | Only if sponsored provider is `api_key`; choose one source |
| `OPENAI_PROJECT_ID` | Optional shell variable sometimes used by other OpenAI tooling; **not required by SIGMA's local provider selection** | No |
| `SIGMA_CLOUD_GLOBAL_SPEND_CEILING_USD` | SIGMA's internal shared estimated-use ceiling, **not** the OpenAI API project's spending limit | Optional |
| `SIGMA_CLOUD_GLOBAL_SPEND_WINDOW` | `calendar_month` for monthly rollover of an explicit ceiling; otherwise explicit ceilings default to cumulative | Optional |

**Different emails are legitimate:** the Google administrator, the selected personal ChatGPT user, and the sponsored ChatGPT account are different roles. Configure each intentionally; do not infer the sponsor from the Google sign-in or the most recent personal ChatGPT connection.

### Local `.env` versus shell profile

Use the **checkout-root, Git-ignored `.env`** for local settings (mode `600` is recommended), or export them in the shell before launching SIGMA. **Every checkout/worktree has its own `.env`.** Exported variables take precedence over `.env`, **even when exported as an empty string**. `.env` files are parsed as data: do not put shell commands or `$(...)` substitution into `.env`. Do not commit OAuth secrets, API keys, or private account stores.

A basic authenticated + sponsored configuration could look like this (replace the placeholders; the sponsor must also be authorized separately):

~~~dotenv
GOOGLE_OIDC_CLIENT_ID=your-google-web-client-id
GOOGLE_OIDC_CLIENT_SECRET=your-google-web-client-secret
SIGMA_CLOUD_ADMIN_CONTACT_EMAIL=your-google-admin@example.com
SIGMA_CLOUD_SPONSOR_EMAIL=your-designated-chatgpt-sponsor@example.com
# Optional: local Sponsored ChatGPT is already the default inference provider.
# SIGMA_CLOUD_INFERENCE_PROVIDER=chatgpt
~~~

## ChatGPT inference choices

### Personal ChatGPT

With SIGMA running, select **Connect AI** / **Connect to ChatGPT** and explicitly sign into the desired ChatGPT account. This personal connection is distinct from Google sign-in. Successful Google sign-in **does not** grant OpenAI model access. Disconnecting personal ChatGPT returns an eligible user to Sponsored ChatGPT mode but **does not register, repair, or refresh the sponsor credential**.

### Sponsored ChatGPT (local)

1. Configure `SIGMA_CLOUD_SPONSOR_EMAIL` to the exact, verified email of the intended sponsor ChatGPT account, in the checkout `.env` or backend launching environment. **Missing this setting causes sponsored connection failure**, even when the same ChatGPT account works in personal mode.
2. Leave `SIGMA_CLOUD_INFERENCE_PROVIDER` unset (the local default is `chatgpt`), or explicitly select `chatgpt`. Avoid copying the hosted deployment's `api_key` configuration unintentionally.
3. The sponsor must **separately authorize plan use**, using SIGMA's **administrator-only sponsor authorization/renewal flow** (`/api/ai/sponsor-auth/begin`). A regular user's Sponsored ChatGPT pill does **not** provision the sponsor. If a private sponsor registration already exists, SIGMA matches it against `SIGMA_CLOUD_SPONSOR_EMAIL`.
4. The dedicated sponsor credentials are in the private sponsor store at `SIGMA_AUTH_HOME` or, by default, `~/.config/sigma`. This is separate from a signed-in member's personal credential store. SIGMA validates the store path/ownership and protected credentials; do not manually copy tokens from personal storage into sponsor storage.
5. Restart the local backend after environment changes (`./sigma start`). Sign in with an eligible local Google account, select Sponsored ChatGPT, and confirm connection status before running or resuming a saved research session.

**Sponsor authorization and API billing are independent.** Sponsored ChatGPT normally uses the designated ChatGPT plan and remains subject to actual provider and SIGMA usage limits. Hosted SIGMA may instead use an explicitly configured, separately billed API service key. A **Sponsored ChatGPT · Unlimited** allowance label, where shown, does not guarantee unlimited provider usage or override a provider hard spending cap.

### Direct OpenAI API key (optional)

A local API-key connection uses `OPENAI_API_KEY` and **separate OpenAI Platform billing**; it is not required for personal or sponsored ChatGPT. You can set the key privately in the server environment or ignored checkout `.env` and explicitly choose API-key billing in the UI.

**On macOS, you can keep an API key in the login Keychain** instead of plaintext shell startup files. Create a matching generic-password item once, using a private interactive password prompt:

~~~sh
security add-generic-password -a "$USER" -s sigma-research-api-key -w
~~~

The Keychain item must use account **`$USER`**, service **`sigma-research-api-key`**, and the OpenAI API key as its password. Your login Keychain must be unlocked, and macOS must authorize the requesting shell/`security` process. An existing item needs no recreation.

An optional `~/.zprofile` or other login-shell profile entry retrieves the key on startup:

~~~sh
# Optional: project identifier for other tools, not required by SIGMA.
# export OPENAI_PROJECT_ID="proj_your_project_id"
if security find-generic-password \
    -a "$USER" \
    -s sigma-research-api-key >/dev/null 2>&1; then
    export OPENAI_API_KEY="$(
        security find-generic-password \
            -a "$USER" \
            -s sigma-research-api-key \
            -w
    )"
fi
~~~

Validate **without printing the secret**:

~~~sh
security find-generic-password -a "$USER" -s sigma-research-api-key >/dev/null 2>&1 \
  && echo "Keychain entry accessible" \
  || echo "Keychain entry missing or inaccessible"
[[ -n "$OPENAI_API_KEY" ]] && echo "OPENAI_API_KEY exported"
~~~

The profile's `if` silently skips the export when the item is missing or access is denied. Reopen the terminal or source the updated profile to apply changes. This Keychain snippet only creates/exports **`OPENAI_API_KEY`**; it **does not** provision the Sponsored ChatGPT credential or dedicated sponsored API service key. Do not echo an API key, paste it into an issue, or check it into Git.

### Sponsored API-key transport (advanced)

An operator can opt into API-key-funded local sponsorship with a **dedicated** service key, distinct from personal `OPENAI_API_KEY`:

~~~sh
SIGMA_CLOUD_INFERENCE_PROVIDER=api_key
SIGMA_CLOUD_OPENAI_API_KEY_FILE=/absolute/private/path/to/sponsor-api-key
./sigma start
~~~

A direct `SIGMA_CLOUD_OPENAI_API_KEY` environment value is an alternative to `_FILE`; **do not configure both**. The operator must approve API billing and the OpenAI project's provider-side limits separately. Changing a user's SIGMA allowance or the global ceiling does not authorize or remove OpenAI's hard billing limits. Unset sponsored API-key overrides and restart to return to the local ChatGPT sponsor default.

## Spending limits and safety

In ordinary local sponsored mode, SIGMA uses an estimated **$50-per-UTC-calendar-month shared ceiling** if no override is set. This is an *internal, API-rate-equivalent accounting guard*, not a bill or an indication of remaining provider usage. Member allowances, call/token quotas, and provider limits are separate.

If you explicitly set `SIGMA_CLOUD_GLOBAL_SPEND_CEILING_USD`, the default accounting window becomes **cumulative**, unless you also explicitly set `SIGMA_CLOUD_GLOBAL_SPEND_WINDOW=calendar_month`. For example, a `1000.00` ceiling would raise the **internal** permitted estimated use—it would not repair a missing sponsor login, change the API project's hard spend limit, or add ChatGPT plan usage. Set ceilings only with operator approval.

Read the durable historical ledger (no identities or tokens printed):

~~~sh
uv run --locked --no-sync python scripts/inspect_cloud_spend.py
~~~

A fresh session or changed ceiling never resets previously recorded spending obligations. Existing sessions retain their recorded limits and transport and should be resumed rather than restarted unless the UI directs otherwise.


## Optional: test Google sign-in locally

Google authentication is **not required** for ordinary local use. To exercise the authenticated account flow, create a Google OAuth **web** client with:

- Authorized JavaScript origin: `http://127.0.0.1:5173`
- Authorized redirect URI: `http://127.0.0.1:5173/api/cloud-auth/callback`

Put `GOOGLE_OIDC_CLIENT_ID` (the Google OAuth application's identifier) and `GOOGLE_OIDC_CLIENT_SECRET` (its server-side credential) in the checkout-root `.env` or the server environment. **Each Git checkout/worktree needs its own `.env`**: Git ignores this file, so it will not follow you into a new checkout. If another local checkout already has working credentials, copy its `.env` to this checkout and restrict access with `chmod 600 .env`. Never commit or share the secrets. Exported shell variables take precedence over `.env`, even when exported as empty strings.

Set your administrator contact in `.env` or export it, then launch SIGMA:

```sh
export SIGMA_CLOUD_ADMIN_CONTACT_EMAIL="you@gmail.com"
./sigma start --navigate
```

Use the **Google Sign In** pill to choose a real Google account. **Do not pass `--signin` for this test**: that option now supplies a local administrator identity without performing Google OAuth. Sign in with the account matching `SIGMA_CLOUD_ADMIN_CONTACT_EMAIL` to establish the local administrator; other accounts require membership grants. Local authentication state is stored under `~/.sigma/local-cloud-auth`. Use separate browser profiles when testing multiple accounts.

This is a **local authentication test**, not a hosted deployment. For hosted configuration and administrator operations, see [Cloud Deployment](CLOUD_DEPLOYMENT.md). For a provider-free UI simulation of membership, allowances, and errors, see [Local Mock Authentication](LOCAL_MOCK_AUTH.md). Mock identities are not real Google accounts and mock research is not AI inference.

## Optional: local feedback and Email Project (Gmail or SMTP)

Local SIGMA can send **Send Feedback** notifications and **Email Project** messages (including JSON, PDF, and LaTeX attachments).

**Gmail through Google sign-in (recommended for localhost):** Set `GOOGLE_OIDC_CLIENT_ID` and `GOOGLE_OIDC_CLIENT_SECRET` (or its `_FILE` form) in this checkout's ignored `.env`. Use the **same local Google web OAuth client** as SIGMA's UI, with `http://127.0.0.1:5173/api/cloud-auth/callback` as an authorized redirect URI. Then run:

```sh
./sigma send_feedback "hello world" --transport gmail
./sigma send_feedback "hello world" --transport gmail --attach ./path/to/file.pdf
```

Use `--attach PATH` to send a single local file as a MIME attachment with a feedback test message. Both Gmail API and SMTP are supported. Relative, absolute, and `~/` paths work. Files over 18 MB, missing files, and unreadable files are rejected before opening Google authorization or contacting the mail provider. The CLI does not persist an application Feedback record, and the browser Feedback endpoint is unchanged.

The command opens your default browser for Google's explicit **Gmail Send** permission, captures the OAuth callback using a temporary localhost listener, stores an account-bound grant privately under `~/.sigma/local-cloud-auth/gmail-send-token.json`, and sends one feedback test message. It does **not** start the SIGMA UI, need a separate terminal, or read browser session cookies. It verifies the Google account you select through the OAuth identity token and uses that verified address as the feedback contact; `SIGMA_CLOUD_ADMIN_CONTACT_EMAIL` is the test recipient and can be a different mailbox. The command reuses an existing matching grant on later calls. Add `--reauthorize` if you want to choose a different sending account. If port 5173 is free, the CLI listens for the Google callback itself. If your **updated local SIGMA UI is already running** on that port, the CLI uses its local-only callback handoff instead; you do not need to navigate through the UI or stop it. An older running SIGMA process without the new handoff must be restarted once, or shut down with `./sigma shutdown`. An unrelated process on the port is never stopped or trusted. Production is not modified.

Gmail's `gmail.send` scope may require app verification or tester authorization. An External Testing OAuth app may issue a refresh token that expires after seven days. If consent is blocked, resolve it in the **local OAuth project**, not the production deployment.

**SMTP alternative:** Local email can also use SMTP. **Google OAuth branding verification is not required for SMTP.** The sender needs an SMTP credential, such as a Gmail **app password**, not your normal Google-account password. Gmail accounts must meet Google's eligibility requirements for app passwords.

**Not clean-install retested:** Verify Gmail and SMTP flows on the actual OS and OAuth client before relying on these instructions.

Keep the credential outside the repository. For an existing local setup, check whether the password file already exists:

```sh
ls -l ~/.config/sigma/smtp-password
```

Do **not** print or paste its contents. A private password file should be accessible only to your user (for example, permissions `600`). If you need to create it, use a protected local file containing only the app password. The example path is a convention, **not** a password that SIGMA creates automatically.

Configure the local checkout's ignored `.env` file (or export equivalent shell variables):

```dotenv
SIGMA_EMAIL_SMTP_HOST=smtp.gmail.com
SIGMA_EMAIL_SMTP_PORT=587
SIGMA_EMAIL_SMTP_USERNAME=your-sending-account@gmail.com
SIGMA_EMAIL_SMTP_PASSWORD_FILE=/absolute/path/to/.config/sigma/smtp-password
SIGMA_CLOUD_ADMIN_CONTACT_EMAIL=your-google-sign-in@gmail.com
```

Replace the example addresses and file path with your own; **the password-file path must be absolute**. In `.env`, `~` and `$HOME` are **not expanded**, so use your real home-directory path. The SMTP username is the account that sends mail. The administrator contact is the local sign-in/admin address; these may be different.

From the checkout, test the SMTP transport directly (without requiring a running browser or sending a feedback database record):

```sh
./sigma send_feedback "hello world" --transport smtp
```

The diagnostic prints which transport was selected, whether SMTP credentials are configured, and whether the mail provider accepted delivery; it never prints the password. It sends the test message to `SIGMA_CLOUD_ADMIN_CONTACT_EMAIL`. SMTP testing uses the configured local contact address, while Gmail OAuth testing uses the Google-verified sender as its contact. Normal browser **Send Feedback** uses the authenticated Google account's email as its contact address, or an optional unverified contact address for guests.

If you previously configured `SIGMA_GMAIL_TOKEN_FILE`, `SIGMA_EMAIL_GMAIL_TOKEN_FILE`, or `SIGMA_INVITATION_GMAIL_TOKEN_FILE`, ordinary feedback sending prefers the Gmail API path instead of SMTP. The `--transport smtp` flag overrides this **for the CLI invocation only**; to use SMTP in the browser, remove/disable the Gmail token-file setting from the local backend environment and restart `./sigma start`. Environment variables exported in your shell override the ignored `.env`, even if empty. Never commit credentials or copy the protected password file into Git.

## Local verification and troubleshooting

1. Run `./sigma setup` and `./sigma start --navigate` from the intended checkout, not another developer worktree.
2. Verify the Google sign-in identity, model connection pill, and which of Personal ChatGPT / Sponsored ChatGPT / API-key mode is actually selected. An account may be a Google administrator while using a different ChatGPT sponsor account.
3. Check the current backend's local sponsor diagnostics, not old entries from a different date:

   ~~~sh
   tail -n 30 sponsor-diagnostics.log
   ~~~

4. `sponsor_connection status=storage_or_configuration_unavailable` means a configuration or protected sponsor-store operation failed. First verify that `SIGMA_CLOUD_SPONSOR_EMAIL` is set for **the running backend**; then check the chosen sponsor store's path and safe directory/file permissions. It does **not** establish that the ChatGPT usage limit was reached. `credential_missing` means the sponsor registration lacks a usable session and may require administrator-only renewal.
5. `sponsor_play` and `sponsor_inference` entries help distinguish startup, provider call, and rejection issues; endpoint entries such as `sponsor_sessions_api status=post_400` do not alone identify their cause. Do not publish credentials or raw account stores to diagnose them.
6. Run `./sigma test` for offline tests; use `./sigma shutdown` to stop verified SIGMA-owned local servers. Normal Ctrl+C from the launcher terminal also shuts down its managed processes.

**Local versus production:** A local sponsor using a ChatGPT plan can work while hosted SIGMA, explicitly configured with `SIGMA_CLOUD_INFERENCE_PROVIDER=api_key`, encounters `HTTP 429 project_spend_limit_exceeded`. Those are **different provider transports and billing controls**. Reproducing the hosted hard-cap failure locally requires deliberately selecting a key from the same exhausted API project; do not do so merely to troubleshoot the unrelated local sponsor credential.

## Local storage and optional execution

The normal project root is `projects/` within the checkout; `SIGMA_PROJECTS_ROOT` can point to an existing absolute directory. For local persistent-disk-style test storage, set `SIGMA_STORAGE_BACKEND=persistent_disk` and an existing, private absolute `SIGMA_STORAGE_ROOT`; see [T100 local persistent-disk acceptance](evaluations/t100/README.md). No Google Cloud resource is required for a local checkout.


## Optional: scientific computation

Build the optional Python execution sandbox with:

```sh
docker build -t sigma-research-python:0.1 sandbox-poc
```

Docker and the sandbox image are **not required** for the basic local UI. See [Python Execution](RESEARCH_PYTHON_EXECUTION.md) and [Sage Execution](SAGE_EXECUTION.md) for isolation assumptions, setup, and limitations.

## Maintenance expectations

**This guide has not been clean-install retested as a whole.** A maintainer changing the local launcher, `.env` loading, OAuth redirect ports, auth-store schema, sponsored authorization, API routing, cost accounting, mail configuration, or local sandbox should update this page **in the same change**, verify the affected commands, and record the OS, checkout SHA, and date of any end-to-end validation. Do not claim installation steps are proven because individual tests passed. Document configuration keys and safe verification procedures; never document actual keys, secrets, personal credentials, or local private paths.

