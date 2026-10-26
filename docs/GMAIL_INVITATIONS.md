# Gmail API invitation delivery (T81)

SIGMA can deliver invitation notifications through the Gmail API instead of SMTP.
The sender must be the Google account that authorized the `gmail.send` scope.
The existing SMTP path remains available when Gmail API is not configured.

## Local setup

1. Enable Gmail API in the Google Cloud OAuth project and create a Desktop OAuth client.
2. Authorize the sender using the `https://www.googleapis.com/auth/gmail.send` scope.
3. Store the resulting OAuth token JSON securely outside the repository. It must
   contain `client_id`, `client_secret`, and `refresh_token`.
4. Set these server-side environment variables:

   - `SIGMA_INVITATION_GMAIL_TOKEN_FILE=/absolute/path/to/gmail-token.json`
   - `SIGMA_INVITATION_GMAIL_SENDER=zetacontinuation@gmail.com`

When `SIGMA_INVITATION_GMAIL_TOKEN_FILE` is set, SIGMA uses Gmail API delivery.
Otherwise it uses the existing `SIGMA_INVITATION_SMTP_*` settings. Do not place
the token in the repo, Docker image, project files, frontend configuration, or
logs. Keep the token file readable only by the SIGMA server account.

## Production deployment

Copy the authorized token file to a protected location readable by the
production backend, mount it read-only inside the application container,
and set the two variables above in the backend environment. The environment
variable must refer to the **container-visible** path. Do not configure a
host-only path without mounting it.

The access token is refreshed using Google's OAuth token endpoint on each
invitation request. The refresh token is not modified. If the refresh token
is revoked or expires, sending fails safely and the invitation request stays
pending for retry. The API sends only to the configured invitation recipient.

**OAuth Testing limitation:** External Google OAuth apps in Testing can issue
refresh tokens that expire after seven days for the `gmail.send` scope.
Resolve OAuth publishing/verification requirements before treating this as
unattended production delivery. Publishing is a separate operational decision
and may require Google's verification process.

## Acceptance

Run `uv run python -m unittest discover -s tests -p gmail_delivery.py` locally. Then test an actual
denied-access invitation request in a non-production environment and confirm
the notification reaches the designated recipient. Production acceptance also
requires verifying the container mount, permissions, token refresh, and
failure behavior. Do not close T81 until feedback and privacy acceptance are
completed as well.
