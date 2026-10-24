# Local administrator UI preview

Start the existing SIGMA Home UI with a simulated administrator:

```sh
./sigma start --admin --navigate
```

Or omit `--navigate` and open `http://127.0.0.1:5173` in the browser. Click **Access Management** in the account controls at the upper-right of Home. Add an email or exact domain rule, change the role, or revoke it to inspect the administrator workflow. The dialog prominently identifies the simulated preview and shows `admin-preview@local.invalid` as its identity.

**No Google OAuth application, cloud account, payment card, or API calls are required.** Preview rules live in Vite's process memory and disappear when the UI server restarts. They are not real authorizations and do not modify the cloud SQLite grants table. The Python API remains the usual local API; only the browser-facing Vite middleware simulates the identity status and access-management routes. The fake middleware is activated only by the explicit `--admin` flag and rejects non-loopback requests. It must not be enabled on a remotely exposed Vite server. The launcher explicitly disables backend cloud authorization in preview mode.

Stop with Ctrl+C or `./sigma shutdown`. Start again without `--admin` to return to the normal local SIGMA UI.

For optional Chrome verification while the preview is running:

```sh
uv run --with playwright python browser_checks/t22_admin_preview.py
```

This checks the visible dialog, fake add/revoke, and the untouched local backend status. It does not verify real hosted Google OAuth or production cloud access control.
