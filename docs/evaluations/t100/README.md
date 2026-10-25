# T100 local persistent-disk acceptance

`local` remains the default storage backend and continues using the established
`SIGMA_PROJECTS_ROOT`, Recent index and local account paths. `persistent_disk`
uses the same POSIX file and SQLite services on a developer's local filesystem
that the GCE deployment uses on its mounted disk. The mode requires an absolute,
owned mode-0700 `SIGMA_STORAGE_ROOT`, derives auth/workspace paths beneath it,
and requires authenticated workspace scoping. Misconfiguration stops startup;
requests cannot fall through to the local project directory.

## Credential-free local procedure

From the repository root, with Python/uv, npm, and Google Chrome installed:

```sh
T100_TMP="$(mktemp -d)"
chmod 700 "$T100_TMP"
export SIGMA_STORAGE_BACKEND=persistent_disk
export SIGMA_STORAGE_ROOT="$T100_TMP"
uv run --locked python tests/storage.py
uv run --with playwright python browser_checks/t100_persistent_disk.py
unset SIGMA_STORAGE_BACKEND SIGMA_STORAGE_ROOT
rm -rf "$T100_TMP"
```

Both checks create a fresh isolated private root for their run. Their test-only
`cloud_workspace_test_app` adapter assigns two named simulated Google subjects
from `X-Test-*` request headers and supplies the sign-in status only to that
browser test. The real FastAPI project, strategy, Recent, export, auth mapping,
workspace and research storage services are used. This fixture is not Google
OAuth, is not imported by normal launch, and does not make an inference request.
The procedure needs no GCP credentials, GCP resources, or paid API key.

The test starts and stops the API process to exercise backend restart. It copies
the complete storage root to a different private path and verifies that A's
owner mapping, project ID/content, strategy, export and Recent entry reopen there
while B remains denied. Workspace-relative path rebasing handles that local
restore relocation; it leaves the stock sample catalog untouched. It also
checks invalid roots and out-of-root workspace configuration fail at startup.

For a container smoke on a local Docker engine, run:

```sh
deploy/validate-persistent-local.sh
```

This builds the backend image, creates a disposable private Docker volume,
starts the real backend in `persistent_disk`, and verifies the SQLite auth DB
survives backend restart and container recreation. It uses fixture Google
configuration and does not contact Google or an inference provider. The image
and volume are cleaned up after the run.

## GCE mount guard

The GCE override maps the mounted host disk's `auth/` directory to
`/var/lib/sigma-auth`, sets `SIGMA_STORAGE_BACKEND=persistent_disk`, and uses
that mount as `SIGMA_STORAGE_ROOT`. Start or recreate the service with:

```sh
sudo env SIGMA_DEPLOY_ENV_FILE=/etc/sigma/deploy.env \
  SIGMA_STATE_DISK_MOUNT=/srv/sigma-state \
  /opt/sigma/current/deploy/start-gce.sh
```

The script rejects symlink mount/state paths, checks `mountpoint` before
creating the `auth` directory, sets it to mode 0700 owned by the backend's
configured numeric UID/GID, then invokes Compose. A missing disk mount exits
before any backend container can write to the VM boot filesystem. If deployment
overrides the Compose UID/GID defaults, export the same `SIGMA_BACKEND_UID` and
`SIGMA_BACKEND_GID` values for this host script. Local checks intentionally do
not require a block-device mount.

## Browser evidence

`browser_checks/t100_persistent_disk.py` uses installed Google Chrome against
the actual local Vite UI and FastAPI API in `persistent_disk` mode. It opens the
stock Nonconsecutive Subset Sums sample as an independent copy, edits project
details and an existing strategy in the UI, saves, reloads, reopens from Recent,
restarts the backend, and checks again. It verifies unchanged project and
strategy IDs, changed text, a Recent entry, denied access from subject B, and an
unchanged stock sample. The screenshot `persistent-disk-chrome.png` is saved by
the run. Auth is the explicit isolated fixture described above, not real OAuth.
