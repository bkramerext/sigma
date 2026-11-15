# T128 GCE host readiness

This procedure checks the prepared Ubuntu host independently of T129
application configuration. It does not read or require `/etc/sigma/deploy.env`,
OAuth values, secret contents, DNS, or an active `sigma.service`. It performs
read-only checks; it does not start, stop, enable, or reboot anything.

## Reproducible host components

- `deploy/install-gce-host.sh` pins Ubuntu 24.04 Docker packages, creates the
  dedicated non-privileged `sigma-sandbox` user, configures its rootless daemon,
  enables lingering, and installs the host service units. It does not enable
  the production application or edit credentials. Run it only after the state
  disk has been prepared and mounted.
- `deploy/build-sandbox-images.sh`, run as `sigma-sandbox`, builds and inspects
  both runner images using the rootless socket. Python dependencies are pinned
  in `sandbox-poc/requirements.txt`; the Sage base image is digest-pinned.
- Host Python/uv/Tectonic installs are intentionally unnecessary. The service
  image builds from the repository `Dockerfile`, which pins uv, installs the
  application with `uv sync --locked`, and installs checksum-verified Tectonic.
  The runtime proof runs inside that image. Installing a second copy of those
  dependencies on the VM would create a separate, unneeded runtime.
- `deploy/prepare_state_disk.py` owns the UUID-backed `/etc/fstab` mount
  contract, including `nodev,nosuid,noexec`. It refuses conflicting mount
  entries and never formats the disk. Never rerun filesystem setup with a
  different UUID or alter a working mount to satisfy a failed check.

## Operator procedure

1. Confirm the mounted state disk is the already identified persistent disk.
   Do not format it. If its UUID-backed mount is not yet configured, use the
   approved one-time disk procedure in [the operations runbook](OPERATION_RUNBOOK.md).
2. Stage the reviewed checkout at `/opt/sigma/current`, then run:

   ```sh
   sudo /opt/sigma/current/deploy/install-gce-host.sh
   sudo -u sigma-sandbox env XDG_RUNTIME_DIR="/run/user/$(id -u sigma-sandbox)" \
     /opt/sigma/current/deploy/build-sandbox-images.sh
   sudo /usr/local/libexec/sigma/gce_preflight.py --host-readiness --json
   ```

   Host readiness exit status 0 means all host checks pass, 1 means a failed
   invariant, and 2 means a prerequisite is missing. The host gate does not
   make production configuration ready.
3. After a planned VM reboot, run the same read-only gate with
   `--after-reboot`:

   ```sh
   sudo /usr/local/libexec/sigma/gce_preflight.py --after-reboot --json
   ```

   This checks the mounted UUID/options, active and enabled system Docker and
   rootless sandbox units, sandbox user lingering, socket security, and both
   images again. It intentionally accepts an inactive/disabled `sigma.service`
   when T129 has not installed production configuration.
4. T129 remains separate: install protected deploy configuration and secret
   files, then run the production gate without `--host-readiness`:

   ```sh
   sudo /usr/local/libexec/sigma/gce_preflight.py --json
   ```

   Only the production gate decides whether configured Compose and credentials
   are ready. Do not enable `sigma.service` based on the host-only result.

## Evidence boundary

Offline automated checks can verify the readiness decision paths and systemd
contracts. They cannot prove that a particular GCE disk survived a reboot, that
the VM is running the reviewed checkout, or that Docker actually recovers its
images and isolation boundary after a real reboot. Those require a read-only
operator invocation on the live VM and sanitized output. Do not report local
tests as hosted acceptance.
