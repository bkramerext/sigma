# Host Caddy maintenance cutover (issue #383)

Production's public TLS endpoint is **host Caddy**, not Nginx. The app and Compose edge are behind it.

## One-time host setup (Red)

1. Install `deploy/maintenance/index.html` as `/var/www/sigma-maintenance/index.html` and `assets/maintainance-page.png` as `/var/www/sigma-maintenance/maintainance-page.png`. These files must be readable by the host Caddy service and must live outside the application containers.
2. Install the host Caddy site from `deploy/host-caddy.Caddyfile` into the existing Caddy configuration (preserve unrelated sites). Create `/etc/caddy/sigma-maintenance` writable only by root; leave it empty in normal operation.
3. Validate with `caddy validate --config /etc/caddy/Caddyfile` and reload Caddy.
4. Confirm normal traffic works. Do not switch production into maintenance merely to install files.

## Cutover

Before stopping SIGMA, run `sudo python3 /opt/sigma/current/deploy/maintenance/switch.py on`. Verify the public endpoint returns HTTP 503 and the maintenance image path returns 200. Stop/start the app, verify the replacement using the existing release health checks, then run `sudo python3 /opt/sigma/current/deploy/maintenance/switch.py off`. Verify normal traffic and image route no longer serves maintenance content.

The switch uses an imported Caddy snippet and reload, not GCloud resource changes. The snippet is persistent across application restarts. If deployment fails, keep the maintenance response up while restoring a healthy previous release; disable only after recovery checks pass. The host configuration and static files must be installed before integrating this into automated deployments. Red owns the production activation and rollback checks.

For manual recovery, use the same `on` / `off` command. The switch validates the Caddy config before reload and restores the prior snippet if validation/reload fails. Never assume an unsuccessful deployment has disabled maintenance.
