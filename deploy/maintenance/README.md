# Host Caddy maintenance cutover (issue #383)

Production's public TLS endpoint is **host Caddy**, not Nginx. The app and Compose edge are behind it.

## One-time host setup (Red)

1. Install `deploy/maintenance/index.html` as `/var/www/sigma-maintenance/index.html` and `assets/maintainance-page.png` as `/var/www/sigma-maintenance/maintainance-page.png`. These files must be readable by the host Caddy service and must live outside the application containers.
2. Install the host Caddy site from `deploy/host-caddy.Caddyfile` into the existing Caddy configuration (preserve unrelated sites). Create `/etc/caddy/sigma-maintenance` writable only by root; leave it empty in normal operation.
3. Install `deploy/maintenance/switch.py` as `/usr/local/libexec/sigma/maintenance-switch.py` (root-owned, mode 0755). The release script detects this installed path and toggles maintenance only for disruptive upgrades. Do not install the switch until the static files, snippet directory, and Caddy configuration are in place.
4. Validate with `caddy validate --config /etc/caddy/Caddyfile` and reload Caddy.
5. Confirm normal traffic works. Do not switch production into maintenance merely to install files.

## Cutover

For manual cutovers, before stopping SIGMA, run `sudo python3 /opt/sigma/current/deploy/maintenance/switch.py on`. Verify the public endpoint displays the maintenance page with HTTP 503 and the maintenance image path returns HTTP 200. Stop/start the app, verify the replacement using the existing release health checks, then run `sudo python3 /opt/sigma/current/deploy/maintenance/switch.py off`. Verify normal traffic and image route no longer serves maintenance content.

The automated release script uses the same switch when installed, enabling it immediately before stopping SIGMA and disabling it only after container health checks pass. The switch uses an imported Caddy snippet and reload, not GCloud resource changes. The snippet is persistent across application restarts. If deployment fails, keep the maintenance response up while restoring a healthy previous release; disable only after recovery checks pass. The host configuration and static files must be installed before integrating this into automated deployments. Red owns the production activation and rollback checks.

For manual recovery, use the same `on` / `off` command. The switch validates the Caddy config before reload and restores the prior snippet if validation/reload fails. Never assume an unsuccessful deployment has disabled maintenance.
